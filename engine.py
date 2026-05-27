import networkx as nx
import pathlib # https://realpython.com/python-pathlib/
import matplotlib.pyplot as plt
import concurrent.futures
import threading
from abc import ABC, abstractmethod
from . import conf
from alive_progress import alive_bar
from .prop_types import EventTypes, PropagationLevel, ErrorTypes

class Event:
    def __init__(self, t, *args):
        self.t = t # Store the event type
        message_template = conf.EVENT_MESSAGES[t]
        self.details = message_template.format(resource=args[0])
        self.external_details = None

    def add_external_details(self, details):
        self.details += f' -> {details}'
        self.external_details = details

class Error(Exception):
    def __init__(self, t, *args):
        self.t = t # Store the error type
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
    def __eq__(self, other):
        if not isinstance(other, FileLocation):
            return NotImplemented
        return self.path == other.path
    def __hash__(self):
        return hash(self.path)


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
    def __lt__(self, other):
        return self.location.get_state_token() < other.location.get_state_token()

class Propagator:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.resources = {}
        self.events = []
        self.errors = []
        self.history = []
        self._lock = threading.Lock() # For thread-safe list appends
    @staticmethod
    def valid_dependency(requirement, target):
        return (hasattr(requirement, 'location') and isinstance(requirement.location, Location) and
                hasattr(target, 'location') and isinstance(target.location, Location))
    def add(self, requirement, target):
        if not self.valid_dependency(requirement, target):
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

    def _process_resource(self, identifier: str, block_propagation_level: PropagationLevel):
        """Processes a single resource. This method is designed to be run in a worker thread."""
        target = self.resources[identifier]
        requirement_identifiers = list(self.graph.predecessors(identifier))
        requirements = {req_id: self.resources[req_id] for req_id in requirement_identifiers}

        local_events = []
        local_errors = []

        # Check if all requirements exist (this is a secondary check, as the main loop should prevent this)
        for req in requirements.values():
            if not req.exists():
                local_errors.append(Error(ErrorTypes.NOT_FOUND_REQUIREMENT, req, target))
                return local_events, local_errors

        if not target.exists():
            try:
                local_events.append(Event(EventTypes.LAUNCHED_BUILD, target))
                details = target.build(requirements)
                if not target.exists():
                    local_errors.append(Error(ErrorTypes.NOT_PERFORMED_BUILD, target))
                else:
                    event = Event(EventTypes.PERFORMED_BUILD, target)
                    event.add_external_details(details)
                    local_events.append(event)
            except Exception as e:
                error = Error(ErrorTypes.FAILED_BUILD, target)
                error.add_external_details(e)
                local_errors.append(error)
        else:
            # Check if an update is needed
            needs_update = any(target <= req for req in requirements.values())
            if needs_update:
                try:
                    local_events.append(Event(EventTypes.LAUNCHED_UPDATE, target))
                    update_details = target.update(requirements)

                    # Verify update was successful
                    if any(target < req for req in requirements.values()):
                         local_errors.append(Error(ErrorTypes.NOT_PERFORMED_UPDATE, target))
                    else:
                        event = Event(EventTypes.PERFORMED_UPDATE, target)
                        event.add_external_details(update_details)
                        local_events.append(event)
                except Exception as e:
                    error = Error(ErrorTypes.FAILED_UPDATE, target)
                    error.add_external_details(e)
                    local_errors.append(error)

        return local_events, local_errors

    def run(self, block_propagation_level: PropagationLevel = PropagationLevel.COLLECT_ALL_ERRORS, max_workers: int = None):
        self.events = []
        self.errors = []
        self.history = []
        if not nx.is_directed_acyclic_graph(self.graph):
            raise Error(ErrorTypes.CYCLIC_GRAPH)

        identifiers = list(nx.topological_sort(self.graph))
        futures = {} # {identifier: Future}

        bar_manager = alive_bar(len(identifiers))
        bar = bar_manager.__enter__()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                for identifier in identifiers:
                    # Wait for all dependencies of the current node to complete
                    dep_futures = [futures[pred] for pred in self.graph.predecessors(identifier) if pred in futures]
                    if dep_futures:
                        concurrent.futures.wait(dep_futures)

                    # Pre-check: ensure all direct file requirements for the current node exist before submission.
                    all_reqs_exist = True
                    for pred_id in self.graph.predecessors(identifier):
                        if not self.resources[pred_id].exists():
                            error = Error(ErrorTypes.NOT_FOUND_REQUIREMENT, self.resources[pred_id], self.resources[identifier])
                            with self._lock:
                                self.errors.append(error)
                                self.history.append(error)
                            all_reqs_exist = False
                    
                    # Check if any dependency failed
                    should_skip = False
                    for fut in dep_futures:
                        _, dep_errors = fut.result()
                        if dep_errors:
                            should_skip = True
                            break

                    # Combine checks: skip if a dependency failed OR a direct requirement is missing
                    should_skip = should_skip or not all_reqs_exist

                    if should_skip:
                        # Create a dummy completed future representing the skipped/failed dependency to propagate failure
                        dummy_fut = concurrent.futures.Future()
                        dummy_fut.set_result(([], [Error(ErrorTypes.FAILED_BUILD, self.resources[identifier])]))
                        futures[identifier] = dummy_fut
                        bar()
                        continue

                    future = executor.submit(self._process_resource, identifier, block_propagation_level)
                    futures[identifier] = future

                    # Update progress bar and history as tasks complete
                    future.add_done_callback(lambda f: self._collect_results(f, bar))

            # Final collection of any remaining results
            for future in futures.values():
                if not future.done():
                    future.result() # Wait for any stragglers
        finally:
            # Ensure the bar is closed even if errors occur
            bar_manager.__exit__(None, None, None)

        errs = len(self.errors)
        if errs > 0:
            raise Error(ErrorTypes.PROPAGATION, errs)

    def _collect_results(self, future, bar):
        """Thread-safe callback to collect results from a completed future."""
        try:
            local_events, local_errors = future.result()
            with self._lock:
                self.events.extend(local_events)
                self.errors.extend(local_errors)
                self.history.extend(local_events)
                self.history.extend(local_errors)
                # Consider sorting history by a timestamp if exact order is critical
            bar()
        except Exception as e:
            # This would catch errors in the _process_resource logic itself, not the build/update functions
            # For simplicity, we'll just advance the bar. A more robust implementation might log this.
            bar()

    def poll(self) -> dict:
        """
        Dynamically analyzes the execution state of all resources in the graph.
        Returns a dictionary mapping resource identifiers to their current status:
        - "TODO": Output does not exist and needs building.
        - "OUT_OF_DATE": Output exists, but some predecessors have newer timestamps.
        - "DONE": Output exists and is newer than all predecessors.
        """
        import networkx as nx
        status_map = {}
        if not nx.is_directed_acyclic_graph(self.graph):
            raise Error(ErrorTypes.CYCLIC_GRAPH)
            
        identifiers = list(nx.topological_sort(self.graph))
        for identifier in identifiers:
            res = self.resources[identifier]
            if not res.exists():
                status_map[identifier] = "TODO"
            else:
                predecessors = list(self.graph.predecessors(identifier))
                needs_update = False
                for pred_id in predecessors:
                    pred = self.resources[pred_id]
                    if res <= pred:  # Target is older than or equal to requirement
                        needs_update = True
                        break
                if needs_update:
                    status_map[identifier] = "OUT_OF_DATE"
                else:
                    status_map[identifier] = "DONE"
        return status_map

    def rollback_resource(self, identifier: str):
        """
        Recursively deletes (unlinks) the output files of the target resource
        and all of its downstream dependents transitively.
        """
        import networkx as nx
        if identifier not in self.resources:
            raise KeyError(f"Resource '{identifier}' not found in the Propagator graph.")
            
        # Find all downstream transitively dependent resource identifiers
        downstream = nx.descendants(self.graph, identifier) | {identifier}
        for desc_id in downstream:
            res = self.resources[desc_id]
            if isinstance(res.location, FileLocation) and res.location.exists():
                try:
                    res.location.path.unlink()
                except OSError:
                    pass

    def show(self):
        pos = nx.spring_layout(self.graph)
        nx.draw_networkx_nodes(self.graph, pos, cmap=plt.get_cmap('jet'), node_size = 500)
        nx.draw_networkx_labels(self.graph, pos)
        nx.draw_networkx_edges(self.graph, pos, arrows=True)
        plt.show()

def void_function(location, requirements):
    pass
