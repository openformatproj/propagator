import networkx as nx
import pathlib # https://realpython.com/python-pathlib/
import matplotlib.pyplot as plt
from enum import IntEnum
from abc import ABC, abstractmethod
from alive_progress import alive_bar
from . import conf

class EventTypes(IntEnum):
    LAUNCHED_BUILD = 0
    PERFORMED_BUILD = 1
    LAUNCHED_UPDATE = 2
    PERFORMED_UPDATE = 3

class PropagationLevel(IntEnum):
    COLLECT_ALL_ERRORS = 0  # Never stops on error; collects all errors.
    STOP_ON_CRITICAL_ERROR = 1 # Stops if a build/update fails or a requirement is missing.
    STOP_ON_ANY_ERROR = 2   # Stops on any error, including "not performed" warnings.

class Event:
    def __init__(self, t, *args):
        message_template = conf.EVENT_MESSAGES[t]
        self.details = message_template.format(resource=args[0])
        self.external_details = None

    def add_external_details(self, details):
        self.details += f' -> {details}'
        self.external_details = details

class ErrorTypes(IntEnum):
    BAD_PATH = 0
    NOT_VALID_DEPENDENCY = 1
    RESOURCES_IDENTIFIERS = 2
    IDENTIFIERS_LOCATION = 3
    CYCLIC_GRAPH = 4
    FAILED_BUILD = 5
    NOT_PERFORMED_BUILD = 6
    NOT_FOUND_REQUIREMENT = 7
    FAILED_UPDATE = 8
    NOT_PERFORMED_UPDATE = 9
    PROPAGATION = 10

class Error(Exception):
    def __init__(self, t, *args):
        message_template = conf.ERROR_MESSAGES[t]
        match t:
            case ErrorTypes.BAD_PATH | ErrorTypes.CYCLIC_GRAPH:
                self.details = message_template
            case ErrorTypes.NOT_VALID_DEPENDENCY:
                self.details = message_template.format(requirement=args[0], target=args[1])
            case ErrorTypes.RESOURCES_IDENTIFIERS:
                self.details = message_template.format(resource=args[0])
            case ErrorTypes.IDENTIFIERS_LOCATION:
                self.details = message_template.format(resource1=args[0], resource2=args[1])
            case (
                ErrorTypes.FAILED_BUILD
                | ErrorTypes.NOT_PERFORMED_BUILD
                | ErrorTypes.FAILED_UPDATE
                | ErrorTypes.NOT_PERFORMED_UPDATE
            ):
                self.details = message_template.format(resource=args[0])
            case ErrorTypes.NOT_FOUND_REQUIREMENT:
                self.details = message_template.format(requirement=args[0], target=args[1])
            case ErrorTypes.PROPAGATION:
                self.details = message_template.format(count=args[0])
        super().__init__(self.details)
        self.external_details = None

    def add_external_details(self, details):
        self.details += f' -> {details}'
        self.external_details = details

class Location(ABC):
    @abstractmethod
    def exists(self) -> bool:
        pass

    @abstractmethod
    def get_state_token(self) -> any:
        """Returns a comparable token representing the state (e.g., timestamp, hash)."""
        pass

class FileLocation(Location):
    def __init__(self, path: pathlib.Path):
        self.path = path
    def exists(self) -> bool:
        return self.path.exists()
    def get_state_token(self) -> float:
        return self.path.lstat().st_mtime if self.exists() else -1.0

class Resource:
    def __init__(self, location: Location, identifier, builder, updater):
        self.location = location
        self.identifier = identifier
        self.builder = builder
        self.updater = updater

    def __eq__(self, other):
        if not isinstance(other, Resource):
            return NotImplemented
        # Compare based on identifier, location, builder, and updater to define resource equality
        return self.identifier == other.identifier and self.location == other.location and self.builder == other.builder and self.updater == other.updater

    def __hash__(self):
        # Hash based on immutable attributes that define uniqueness
        return hash((self.identifier, self.location, self.builder, self.updater))

    def exists(self):
        return self.location.exists()
    def build(self, requirements):
        return self.builder(self.location, requirements)
    def update(self, requirements):
        return self.updater(self.location, requirements)
    def __le__(self, other):
        # Compare based on the state token provided by the Location object
        return self.location.get_state_token() <= other.location.get_state_token()
        return NotImplemented
    def __lt__(self, other):
        return self.location.get_state_token() < other.location.get_state_token()
        return NotImplemented

class Propagator:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.resources = {}
        self.events = []
        self.errors = []
        self.history = []
    @staticmethod
    def valid_dependency(requirement, target):
        return isinstance(requirement.location, Location) and isinstance(target.location, Location)
    def add(self, requirement, target):
        if not Propagator.valid_dependency(requirement, target):
            raise Error(ErrorTypes.NOT_VALID_DEPENDENCY, requirement, target)

        for res in (requirement, target):
            if res.identifier in self.resources:
                # If identifier exists, ensure the new resource is identical to the existing one.
                # If they are different, it's an error.
                if self.resources[res.identifier] != res:
                    raise Error(ErrorTypes.RESOURCES_IDENTIFIERS, res)
                # If they are identical, it's a no-op for adding the resource itself.
            else:
                # If identifier is new, check for location conflicts with existing resources.
                for existing_res in self.resources.values():
                    if res.location == existing_res.location:
                        raise Error(ErrorTypes.IDENTIFIERS_LOCATION, res, existing_res)
                self.resources[res.identifier] = res

        self.graph.add_edges_from([(requirement.identifier, target.identifier)])

    def show(self):
        pos = nx.spring_layout(self.graph)
        nx.draw_networkx_nodes(self.graph, pos, cmap=plt.get_cmap('jet'), node_size = 500)
        nx.draw_networkx_labels(self.graph, pos)
        nx.draw_networkx_edges(self.graph, pos, arrows=True)
        plt.show()

    def run(self, block_propagation_level: PropagationLevel = PropagationLevel.COLLECT_ALL_ERRORS):
        self.events = []
        self.errors = []
        self.history = []
        if not nx.is_directed_acyclic_graph(self.graph):
            raise Error(ErrorTypes.CYCLIC_GRAPH)
        identifiers = list(nx.topological_sort(self.graph))
        with alive_bar(len(identifiers)) as bar:
            for identifier in identifiers:
                target = self.resources[identifier]
                requirement_identifiers = list(self.graph.predecessors(identifier))
                requirements = {}
                all_requirements_found = True
                for identifier in requirement_identifiers:
                    requirement = self.resources[identifier]
                    if not requirement.exists():
                        self.errors.append(Error(ErrorTypes.NOT_FOUND_REQUIREMENT, requirement, target)) # Requirement missing
                        self.history.append(self.errors[-1])
                        all_requirements_found = False
                    else:
                        requirements[identifier] = requirement
                if not all_requirements_found: # not all requirements have been found
                    bar()
                    if block_propagation_level >= 1:
                        break # Stop propagation if level 1 and requirements are missing
                    continue
                if not target.exists():
                    try:
                        self.events.append(Event(EventTypes.LAUNCHED_BUILD, target))
                        self.history.append(self.events[-1])
                        details = target.build(requirements)
                        if not target.exists():
                            self.errors.append(Error(ErrorTypes.NOT_PERFORMED_BUILD, target))
                            self.history.append(self.errors[-1])
                            if block_propagation_level >= 2:
                                bar()
                                break # Stop propagation if level 2 and build not performed
                        else:
                            event = Event(EventTypes.PERFORMED_BUILD, target)
                            event.add_external_details(details) # Build successful
                            self.events.append(event)
                            self.history.append(self.events[-1])
                    except Exception as e:
                        error = Error(ErrorTypes.FAILED_BUILD, target)
                        error.add_external_details(e)
                        self.errors.append(error)
                        self.history.append(self.errors[-1])
                        if block_propagation_level >= 1:
                            bar() # Build failed
                            break # Stop propagation if level 1 and build failed
                    bar()
                else:
                    launched_update = False
                    failed_update = False
                    update_details = None # Initialize update_details
                    for identifier in requirement_identifiers: # Iterate through requirements to check if any are newer
                        requirement = self.resources[identifier]
                        if target <= requirement: # This requirement may be more recent than target
                            try:
                                launched_update = True
                                self.events.append(Event(EventTypes.LAUNCHED_UPDATE, target))
                                self.history.append(self.events[-1])
                                details = target.update(requirements)
                            except Exception as e:
                                error = Error(ErrorTypes.FAILED_UPDATE, target)
                                error.add_external_details(e)
                                self.errors.append(error)
                                self.history.append(self.errors[-1])
                                failed_update = True
                            break # Stop checking requirements if one triggers an update attempt
                    if not failed_update:
                        not_performed_update = False
                        for identifier in requirement_identifiers: # Re-check if target is still older after update attempt
                            requirement = self.resources[identifier]
                            if target < requirement: # Target is still older than this requirement
                                self.errors.append(Error(ErrorTypes.NOT_PERFORMED_UPDATE, target))
                                self.history.append(self.errors[-1])
                                not_performed_update = True
                                break # Stop checking if one indicates not performed
                        if not_performed_update and block_propagation_level >= 2:
                            bar()
                            break # Stop propagation if level 2 and update not performed
                    elif block_propagation_level >= 1:
                        bar()
                        break # Stop propagation if level 1 and update failed
                    if launched_update and not not_performed_update:
                        event = Event(EventTypes.PERFORMED_UPDATE, target) # 'update_details' is now guaranteed to be defined if launched_update is True
                        event.add_external_details(update_details)
                        self.events.append(event)
                        self.history.append(self.events[-1])
                    bar()
        errs = len(self.errors)
        if errs > 0:
            raise Error(ErrorTypes.PROPAGATION, errs)
def void_function(location, requirements):
    pass
