import pytest
import pathlib
import time

from propagator import Propagator, Resource, FileLocation, void_function, Error, ErrorTypes, EventTypes, PropagationLevel


@pytest.fixture
def propagator_instance():
    """Returns a clean Propagator instance for each test."""
    return Propagator()


def test_add_dependency(propagator_instance, tmp_path):
    """Tests that a valid dependency can be added."""
    req = Resource(FileLocation(tmp_path / "req.txt"), "req.txt", void_function, void_function)
    target = Resource(FileLocation(tmp_path / "target.txt"), "target.txt", void_function, void_function)
    propagator_instance.add(req, target)
    assert propagator_instance.graph.has_edge("req.txt", "target.txt")


def test_add_conflict_identifier_raises_error(propagator_instance, tmp_path):
    """Tests that adding a resource with a conflicting identifier raises an error."""
    res1 = Resource(FileLocation(tmp_path / "file1.txt"), "file1.txt", void_function, void_function)
    res2 = Resource(FileLocation(pathlib.Path("some/other/path")), res1.identifier, void_function, void_function)
    target1 = Resource(FileLocation(tmp_path / "target1.txt"), "target1.txt", void_function, void_function)
    target2 = Resource(FileLocation(tmp_path / "target2.txt"), "target2.txt", void_function, void_function)
    
    propagator_instance.add(res1, target1)
    with pytest.raises(Error) as excinfo:
        propagator_instance.add(res2, target2)
    
    assert excinfo.value.t == ErrorTypes.RESOURCES_IDENTIFIERS


def test_add_conflict_location_raises_error(propagator_instance, tmp_path):
    """Tests that adding a resource with a conflicting location raises an error."""
    res1 = Resource(FileLocation(tmp_path / "file.txt"), "file.txt", void_function, void_function)
    res2 = Resource(res1.location, "different-identifier", void_function, void_function)
    target1 = Resource(FileLocation(tmp_path / "target1.txt"), "target1.txt", void_function, void_function)
    target2 = Resource(FileLocation(tmp_path / "target2.txt"), "target2.txt", void_function, void_function)

    propagator_instance.add(res1, target1)
    with pytest.raises(Error) as excinfo:
        propagator_instance.add(res2, target2)

    assert excinfo.value.t == ErrorTypes.IDENTIFIERS_LOCATION


def test_cyclic_dependency_raises_error(propagator_instance, tmp_path):
    """Tests that a cyclic dependency is detected and raises an error on run."""
    A = Resource(FileLocation(tmp_path / "A.txt"), "A.txt", void_function, void_function)
    B = Resource(FileLocation(tmp_path / "B.txt"), "B.txt", void_function, void_function)
    C = Resource(FileLocation(tmp_path / "C.txt"), "C.txt", void_function, void_function)

    propagator_instance.add(A, B)
    propagator_instance.add(B, C)
    propagator_instance.add(C, A) # Cycle

    with pytest.raises(Error) as excinfo:
        propagator_instance.run()
    
    assert excinfo.value.t == ErrorTypes.CYCLIC_GRAPH


def test_build_non_existent_target(propagator_instance, tmp_path):
    """Tests that a non-existent target is built."""
    req_path = tmp_path / "req.txt"
    req_path.write_text("source")
    target_path = tmp_path / "target.txt"

    def builder(location, requirements):
        location.path.write_text("built")
        return "Built"

    req = Resource(FileLocation(req_path), "req", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", builder, void_function)

    propagator_instance.add(req, target)
    propagator_instance.run()

    assert target_path.exists()
    assert target_path.read_text() == "built"
    assert any(e.t == EventTypes.PERFORMED_BUILD for e in propagator_instance.events)


def test_update_outdated_target(propagator_instance, tmp_path):
    """Tests that an outdated target is updated."""
    req_path = tmp_path / "req.txt"
    target_path = tmp_path / "target.txt"

    # Create target first, then requirement, so target is older
    target_path.write_text("initial")
    time.sleep(0.01)
    req_path.write_text("source")

    def updater(location, requirements):
        location.path.write_text("updated")
        return "Updated"

    req = Resource(FileLocation(req_path), "req", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", void_function, updater)

    propagator_instance.add(req, target)
    propagator_instance.run()

    assert target_path.read_text() == "updated"
    assert any(e.t == EventTypes.PERFORMED_UPDATE for e in propagator_instance.events)


def test_no_update_for_up_to_date_target(propagator_instance, tmp_path):
    """Tests that an up-to-date target is not updated."""
    req_path = tmp_path / "req.txt"
    target_path = tmp_path / "target.txt"

    # Create requirement first, then target, so target is newer
    req_path.write_text("source")
    time.sleep(0.01)
    target_path.write_text("initial")

    update_was_called = False
    def updater(location, requirements):
        nonlocal update_was_called
        update_was_called = True

    req = Resource(FileLocation(req_path), "req", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", void_function, updater)

    propagator_instance.add(req, target)
    propagator_instance.run()

    assert not update_was_called
    assert target_path.read_text() == "initial"
    assert not any(e.t == EventTypes.PERFORMED_UPDATE for e in propagator_instance.events)


def test_missing_requirement_collect_all_errors(propagator_instance, tmp_path):
    """Tests that a missing requirement generates an error with COLLECT_ALL_ERRORS."""
    target = Resource(FileLocation(tmp_path / "target.txt"), "target.txt", void_function, void_function)
    req = Resource(FileLocation(tmp_path / "req.txt"), "req.txt", void_function, void_function)
    
    propagator_instance.add(req, target)
    with pytest.raises(Error) as excinfo:
        propagator_instance.run(block_propagation_level=PropagationLevel.COLLECT_ALL_ERRORS)
    assert excinfo.value.t == ErrorTypes.PROPAGATION
    assert any(e.t == ErrorTypes.NOT_FOUND_REQUIREMENT for e in propagator_instance.errors)


def test_missing_requirement_stop_on_critical_error(propagator_instance, tmp_path):
    """Tests that a missing requirement stops propagation with STOP_ON_CRITICAL_ERROR."""
    target = Resource(FileLocation(tmp_path / "target.txt"), "target.txt", void_function, void_function)
    req = Resource(FileLocation(tmp_path / "req.txt"), "req.txt", void_function, void_function)

    propagator_instance.add(req, target)
    with pytest.raises(Error) as excinfo:
        propagator_instance.run(block_propagation_level=PropagationLevel.STOP_ON_CRITICAL_ERROR)
    
    assert excinfo.value.t == ErrorTypes.PROPAGATION
    assert any(e.t == ErrorTypes.NOT_FOUND_REQUIREMENT for e in propagator_instance.errors)


def test_build_not_performed_raises_error(propagator_instance, tmp_path):
    """Tests that a build function not performing a build raises a NOT_PERFORMED_BUILD error."""
    target_path = tmp_path / "target.txt"

    def no_op_builder(location, requirements):
        return "This builder does nothing"

    req = Resource(FileLocation(tmp_path / "req.txt"), "req.txt", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", no_op_builder, void_function)
    propagator_instance.add(req, target)
    
    with pytest.raises(Error) as excinfo:
        propagator_instance.run(block_propagation_level=PropagationLevel.COLLECT_ALL_ERRORS)
    assert excinfo.value.t == ErrorTypes.PROPAGATION
    assert any(e.t == ErrorTypes.NOT_PERFORMED_BUILD for e in propagator_instance.errors)


def test_failing_build_function_raises_error(propagator_instance, tmp_path):
    """Tests that a build function raising an exception results in a FAILED_BUILD error."""
    target_path = tmp_path / "target.txt"

    def failing_builder(location, requirements):
        raise ValueError("Intentional build failure")

    req_path = tmp_path / "req.txt"
    req_path.write_text("source")
    req = Resource(FileLocation(req_path), "req.txt", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", failing_builder, void_function)
    propagator_instance.add(req, target)

    with pytest.raises(Error) as excinfo:
        propagator_instance.run(block_propagation_level=PropagationLevel.COLLECT_ALL_ERRORS)
    assert excinfo.value.t == ErrorTypes.PROPAGATION
    assert any(e.t == ErrorTypes.FAILED_BUILD for e in propagator_instance.errors)


def test_valid_dependency():
    """Tests the valid_dependency static method."""
    res1 = Resource(FileLocation(pathlib.Path("path1")), "res1", void_function, void_function)
    res2 = Resource(FileLocation(pathlib.Path("path2")), "res2", void_function, void_function)

    assert Propagator.valid_dependency(res1, res2)