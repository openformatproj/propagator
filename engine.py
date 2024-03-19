import networkx as nx
import pathlib # https://realpython.com/python-pathlib/
import matplotlib.pyplot as plt
from alive_progress import alive_bar

class EventTypes:
    LAUNCHED_BUILD = 0
    PERFORMED_BUILD = 1
    LAUNCHED_UPDATE = 2
    PERFORMED_UPDATE = 3

class Event:
    def __init__(self, t, *args):
        match t:
            case EventTypes.LAUNCHED_BUILD:
                self.details = f"build of '{args[0].identifier}' launched"
            case EventTypes.PERFORMED_BUILD:
                self.details = f"build of '{args[0].identifier}' performed"
            case EventTypes.LAUNCHED_UPDATE:
                self.details = f"update of '{args[0].identifier}' launched"
            case EventTypes.PERFORMED_UPDATE:
                self.details = f"update of '{args[0].identifier}' performed"
    def add_details(self, e):
        self.details += f' -> {e}'

class ErrorTypes:
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
        match t:
            case ErrorTypes.BAD_PATH:
                self.details = "bad path"
            case ErrorTypes.NOT_VALID_DEPENDENCY:
                self.details = f"dependency between '{args[0].identifier}' and '{args[1].identifier}' is not valid"
            case ErrorTypes.RESOURCES_IDENTIFIERS:
                self.details = f"more resources have the same identifier '{args[0].identifier}'"
            case ErrorTypes.IDENTIFIERS_LOCATION:
                self.details = f"resources '{args[0].identifier}' and '{args[1].identifier}' point to the same location '{args[0].location}'"
            case ErrorTypes.CYCLIC_GRAPH:
                self.details = "found cyclic dependencies"
            case ErrorTypes.FAILED_BUILD:
                self.details = f"build of '{args[0].identifier}' failed, build function raised an exception"
            case ErrorTypes.NOT_PERFORMED_BUILD:
                self.details = f"build of '{args[0].identifier}' hasn't been really performed (build function hasn't builded anything)"
            case ErrorTypes.NOT_FOUND_REQUIREMENT:
                self.details = f"requirement '{args[0].identifier}' for '{args[1].identifier}' doesn't exist, update is not possible"
            case ErrorTypes.FAILED_UPDATE:
                self.details = f"update of '{args[0].identifier}' failed, update function raised an exception"
            case ErrorTypes.NOT_PERFORMED_UPDATE:
                self.details = f"update of '{args[0].identifier}' hasn't been really performed (update function hasn't updated anything)"
            case ErrorTypes.PROPAGATION:
                self.details = f"'{args[0]}' errors have been detected during propagation"
        super().__init__(self.details)
    def add_details(self, e):
        self.details += f' -> {e}'

ResourceTypes = [
    pathlib.Path
]

class Resource:
    def __init__(self, location, identifier, builder, updater):
        self.location = location
        self.identifier = identifier
        self.builder = builder
        self.updater = updater
        # TODO check if location exists or is creatable
        # raise Error(ErrorTypes.BAD_PATH)
    def exists(self):
        for t in ResourceTypes:
            if isinstance(self.location, t):
                match t:
                    case pathlib.Path:
                        return self.location.exists()
    def build(self, requirements):
        return self.builder(self.location, requirements)
    def update(self, requirements):
        return self.updater(self.location, requirements)
    def __le__(self, other):
        for t in ResourceTypes:
            if isinstance(self.location, t):
                match t:
                    case pathlib.Path:
                        for t in ResourceTypes:
                            if isinstance(other.location, t):
                                match t:
                                    case pathlib.Path:
                                        return self.location.lstat().st_mtime <= other.location.lstat().st_mtime
    def __lt__(self, other):
        for t in ResourceTypes:
            if isinstance(self.location, t):
                match t:
                    case pathlib.Path:
                        for t in ResourceTypes:
                            if isinstance(other.location, t):
                                match t:
                                    case pathlib.Path:
                                        return self.location.lstat().st_mtime < other.location.lstat().st_mtime

class Propagator:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.resources = {}
        self.events = []
        self.errors = []
        self.history = []
    @staticmethod
    def valid_dependency(requirement, target):
        for t in ResourceTypes:
            if isinstance(requirement.location, t):
                match t:
                    case pathlib.Path:
                        for t in ResourceTypes:
                            if isinstance(target.location, t):
                                match t:
                                    case pathlib.Path:
                                        return True
    def add(self, requirement, target):
        if not Propagator.valid_dependency(requirement, target):
            raise Error(ErrorTypes.NOT_VALID_DEPENDENCY, requirement, target)
        for i in (requirement, target):
            if i.identifier in self.resources:
                if not self.resources[i.identifier] == i:
                    raise Error(ErrorTypes.RESOURCES_IDENTIFIERS, i)
            else:
                for _, resource in self.resources.items():
                    if i.location == resource.location:
                        raise Error(ErrorTypes.IDENTIFIERS_LOCATION, i, resource)
                self.resources[i.identifier] = i
        self.graph.add_edges_from([(requirement.identifier, target.identifier)])
    def show(self):
        pos = nx.spring_layout(self.graph)
        nx.draw_networkx_nodes(self.graph, pos, cmap=plt.get_cmap('jet'), node_size = 500)
        nx.draw_networkx_labels(self.graph, pos)
        nx.draw_networkx_edges(self.graph, pos, arrows=True)
        plt.show()
    def run(self, block_propagation_level = 0):
    # block_propagation_level = 0: once started, propagation is never blocked: errors are only collected until the last resource is processed
    # block_propagation_level = 1: once started, propagation is blocked just when an error (except for NOT_PERFORMED_BUILD and NOT_PERFORMED_UPDATE) is raised
    # block_propagation_level = 2: once started, propagation is blocked just when an error is raised
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
                        self.errors.append(Error(ErrorTypes.NOT_FOUND_REQUIREMENT, requirement, target))
                        self.history.append(self.errors[-1])
                        all_requirements_found = False
                    else:
                        requirements[identifier] = requirement
                if not all_requirements_found: # not all requirements have been found
                    bar()
                    if block_propagation_level >= 1:
                        break
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
                                break
                        else:
                            event = Event(EventTypes.PERFORMED_BUILD, target)
                            event.add_details(details)
                            self.events.append(event)
                            self.history.append(self.events[-1])
                    except Exception as e:
                        error = Error(ErrorTypes.FAILED_BUILD, target)
                        error.add_details(e)
                        self.errors.append(error)
                        self.history.append(self.errors[-1])
                        if block_propagation_level >= 1:
                            bar()
                            break
                    bar()
                else:
                    launched_update = False
                    failed_update = False
                    for identifier in requirement_identifiers:
                        requirement = self.resources[identifier]
                        if target <= requirement: # this requirement may be more recent than target
                            try:
                                launched_update = True
                                self.events.append(Event(EventTypes.LAUNCHED_UPDATE, target))
                                self.history.append(self.events[-1])
                                details = target.update(requirements)
                            except Exception as e:
                                error = Error(ErrorTypes.FAILED_UPDATE, target)
                                error.add_details(e)
                                self.errors.append(error)
                                self.history.append(self.errors[-1])
                                failed_update = True
                            break
                    if not failed_update:
                        not_performed_update = False
                        for identifier in requirement_identifiers:
                            requirement = self.resources[identifier]
                            if target < requirement: # target is still older than this requirement
                                self.errors.append(Error(ErrorTypes.NOT_PERFORMED_UPDATE, target))
                                self.history.append(self.errors[-1])
                                not_performed_update = True
                                break
                        if not_performed_update and block_propagation_level >= 2:
                            bar()
                            break
                    elif block_propagation_level >= 1:
                        bar()
                        break
                    if launched_update and not not_performed_update:
                        event = Event(EventTypes.PERFORMED_UPDATE, target)
                        event.add_details(details)
                        self.events.append(event)
                        self.history.append(self.events[-1])
                    bar()
        errs = len(self.errors)
        if errs > 0:
            raise Error(ErrorTypes.PROPAGATION, errs)

def void_builder(location, requirements):
    pass

def void_updater(location, requirements):
    pass
