from enum import IntEnum

class EventTypes(IntEnum):
    LAUNCHED_BUILD = 0
    PERFORMED_BUILD = 1
    LAUNCHED_UPDATE = 2
    PERFORMED_UPDATE = 3

class PropagationLevel(IntEnum):
    COLLECT_ALL_ERRORS = 0  # Never stops on error; collects all errors.
    STOP_ON_CRITICAL_ERROR = 1 # Stops if a build/update fails or a requirement is missing.
    STOP_ON_ANY_ERROR = 2   # Stops on any error, including "not performed" warnings.

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