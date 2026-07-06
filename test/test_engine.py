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


def test_poll_status(propagator_instance, tmp_path):
    """Tests the poll() method to correctly classify TODO, OUT_OF_DATE, and DONE states."""
    req_path = tmp_path / "req.txt"
    target_path = tmp_path / "target.txt"

    req = Resource(FileLocation(req_path), "req", void_function, void_function)
    target = Resource(FileLocation(target_path), "target", void_function, void_function)
    propagator_instance.add(req, target)

    # 1. Initially, neither exists -> both should be "TODO"
    status = propagator_instance.poll()
    assert status["req"] == "TODO"
    assert status["target"] == "TODO"

    # 2. Create req, but not target -> req is "DONE", target is "TODO"
    req_path.write_text("source")
    status = propagator_instance.poll()
    assert status["req"] == "DONE"
    assert status["target"] == "TODO"

    # 3. Create target after req -> both are "DONE"
    time.sleep(0.05)
    target_path.write_text("built")
    status = propagator_instance.poll()
    assert status["req"] == "DONE"
    assert status["target"] == "DONE"

    # 4. Modify req to be newer than target -> req is "DONE", target is "OUT_OF_DATE"
    time.sleep(0.05)
    req_path.write_text("updated source")
    status = propagator_instance.poll()
    assert status["req"] == "DONE"
    assert status["target"] == "OUT_OF_DATE"


def test_rollback_resource(propagator_instance, tmp_path):
    """Tests the rollback_resource() method to transitively unlink output files of descendants."""
    res1_path = tmp_path / "res1.txt"
    res2_path = tmp_path / "res2.txt"
    res3_path = tmp_path / "res3.txt"

    res1 = Resource(FileLocation(res1_path), "res1", void_function, void_function)
    res2 = Resource(FileLocation(res2_path), "res2", void_function, void_function)
    res3 = Resource(FileLocation(res3_path), "res3", void_function, void_function)

    # Chain: res1 -> res2 -> res3
    propagator_instance.add(res1, res2)
    propagator_instance.add(res2, res3)

    # Create files for all resources
    res1_path.write_text("1")
    res2_path.write_text("2")
    res3_path.write_text("3")

    # Invalidate res2 recursively
    propagator_instance.rollback_resource("res2")

    # res1 should still exist (upstream)
    assert res1_path.exists()
    # res2 and res3 should be deleted (descendants)
    assert not res2_path.exists()
    assert not res3_path.exists()


def test_branch_failure_isolation(propagator_instance, tmp_path):
    """Tests that a failure in one branch isolates execution, letting sibling branches complete successfully."""
    # DAG layout:
    #   branch_a_req (success) -> branch_a_target (success)
    #   branch_b_req (fails)   -> branch_b_target (blocked)
    
    a_req_path = tmp_path / "a_req.txt"
    a_target_path = tmp_path / "a_target.txt"
    b_req_path = tmp_path / "b_req.txt"
    b_target_path = tmp_path / "b_target.txt"

    # Branch A: successful
    def a_builder(location, requirements):
        location.path.write_text("success_a")
        return "A Done"
    a_req = Resource(FileLocation(a_req_path), "a_req", void_function, void_function)
    a_target = Resource(FileLocation(a_target_path), "a_target", a_builder, void_function)
    a_req_path.write_text("ready")

    # Branch B: fails due to missing requirement
    b_req = Resource(FileLocation(b_req_path), "b_req", void_function, void_function)
    # b_req_path is NOT written (missing requirement)
    
    b_target = Resource(FileLocation(b_target_path), "b_target", void_function, void_function)

    propagator_instance.add(a_req, a_target)
    propagator_instance.add(b_req, b_target)

    # Running Propagator will throw error overall because of branch B failure,
    # but branch A should still finish!
    with pytest.raises(Error) as excinfo:
        propagator_instance.run(max_workers=2)

    assert excinfo.value.t == ErrorTypes.PROPAGATION
    # Branch A target should have successfully completed and written its file
    assert a_target_path.exists()
    assert a_target_path.read_text() == "success_a"
    # Branch B target should be blocked
    assert not b_target_path.exists()


def test_invalid_dependency_addition(propagator_instance):
    """Assert that adding invalid dependency formats raises NOT_VALID_DEPENDENCY."""
    invalid_res = Resource(None, "invalid_task", void_function, void_function)
    valid_res = Resource(FileLocation(pathlib.Path("valid")), "valid_task", void_function, void_function)
    
    with pytest.raises(Error) as excinfo:
        propagator_instance.add(invalid_res, valid_res)
    assert excinfo.value.t == ErrorTypes.NOT_VALID_DEPENDENCY


def test_parallel_execution_and_topological_order(propagator_instance, tmp_path):
    """Verify that independent tasks execute in parallel and respect topological ordering."""
    import threading
    execution_order = []
    append_lock = threading.Lock()
    
    def make_action(name, delay):
        def action(location, requirements):
            time.sleep(delay)
            with append_lock:
                execution_order.append(name)
            location.path.write_text("DONE")
            return f"Task {name} completed"
        return action

    res_parent = Resource(FileLocation(tmp_path / "parent.done"), "parent", make_action("parent", 0.1), make_action("parent", 0.1))
    res_a = Resource(FileLocation(tmp_path / "child_a.done"), "child_a", make_action("child_a", 0.3), make_action("child_a", 0.3))
    res_b = Resource(FileLocation(tmp_path / "child_b.done"), "child_b", make_action("child_b", 0.3), make_action("child_b", 0.3))
    res_join = Resource(FileLocation(tmp_path / "join.done"), "join", make_action("join", 0.05), make_action("join", 0.05))
    
    propagator_instance.add(res_parent, res_a)
    propagator_instance.add(res_parent, res_b)
    propagator_instance.add(res_a, res_join)
    propagator_instance.add(res_b, res_join)
    
    start_time = time.time()
    propagator_instance.run(max_workers=4)
    total_duration = time.time() - start_time

    assert res_parent.exists()
    assert res_a.exists()
    assert res_b.exists()
    assert res_join.exists()

    assert execution_order[0] == "parent"
    assert execution_order[-1] == "join"
    
    # child_a and child_b take 0.3s each. If they run sequentially, total time >= 0.1 + 0.3 + 0.3 + 0.05 = 0.75s.
    # Concurrently: ~ 0.1 + 0.3 + 0.05 = 0.45s.
    # Assert duration is less than 0.70s to prove parallel speedup.
    assert total_duration < 0.70