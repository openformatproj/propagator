from .prop_types import EventTypes, ErrorTypes

EVENT_MESSAGES = {
    EventTypes.LAUNCHED_BUILD: "build of '{resource.identifier}' launched",
    EventTypes.PERFORMED_BUILD: "build of '{resource.identifier}' performed",
    EventTypes.LAUNCHED_UPDATE: "update of '{resource.identifier}' launched",
    EventTypes.PERFORMED_UPDATE: "update of '{resource.identifier}' performed",
}

ERROR_MESSAGES = {
    ErrorTypes.BAD_PATH: "bad path",
    ErrorTypes.NOT_VALID_DEPENDENCY: "dependency between '{requirement.identifier}' and '{target.identifier}' is not valid",
    ErrorTypes.RESOURCES_IDENTIFIERS: "more resources have the same identifier '{resource.identifier}'",
    ErrorTypes.IDENTIFIERS_LOCATION: "resources '{resource1.identifier}' and '{resource2.identifier}' point to the same location '{resource1.location}'",
    ErrorTypes.CYCLIC_GRAPH: "found cyclic dependencies",
    ErrorTypes.FAILED_BUILD: "build of '{resource.identifier}' failed, build function raised an exception",
    ErrorTypes.NOT_PERFORMED_BUILD: "build of '{resource.identifier}' hasn't been really performed (build function hasn't builded anything)",
    ErrorTypes.NOT_FOUND_REQUIREMENT: "requirement '{requirement.identifier}' for '{target.identifier}' doesn't exist, update is not possible",
    ErrorTypes.FAILED_UPDATE: "update of '{resource.identifier}' failed, update function raised an exception",
    ErrorTypes.NOT_PERFORMED_UPDATE: "update of '{resource.identifier}' hasn't been really performed (update function hasn't updated anything)",
    ErrorTypes.PROPAGATION: "'{count}' errors have been detected during propagation",
}