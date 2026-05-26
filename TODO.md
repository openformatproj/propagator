# Propagator Future Features (TODO)

This file lists potential features and improvements for the `propagator` engine.

## Core Engine Enhancements

-   [ ] **Content-Based Hashing for Change Detection**
    -   **Description:** Currently, change detection relies on file modification timestamps (`mtime`). This can be brittle. Implementing content-based hashing (e.g., SHA256) would make change detection more robust. A resource would only be considered "changed" if its content has actually changed.
    -   **Implementation:**
        -   Create a state file (e.g., `propagator.state.json`) to store the hashes of resources after a successful run.
        -   On the next run, compare the current hash of a resource against the stored hash to determine if it needs an update.
        -   This could be an optional mode or a new `Location` type (e.g., `HashedFileLocation`).

-   [x] **Parallel Execution** (Completed)
    -   **Description:** Use a parallel execution engine to build independent dependency tasks concurrently.
    -   **Implementation:** Leverages a robust `concurrent.futures.ThreadPoolExecutor` to execute tasks in parallel while strictly respecting topological dependencies.

-   [x] **Dynamic Cache-Aware Polling (`poll()`)** (Completed)
    -   **Description:** Query and inspect the topological status of resources.
    -   **Implementation:** Computes `TODO`, `OUT_OF_DATE`, and `DONE` for all resources based on target existence and modification times.

-   [x] **Recursive Downstream Rollback (`rollback_resource()`)** (Completed)
    -   **Description:** Cleanly roll back tasks without leaving stale downstream artifacts.
    -   **Implementation:** Transitively unlinks the output files of a node and all its descendants.

-   [x] **Branch-Level Failure Isolation** (Completed)
    -   **Description:** Isolate exceptions so sibling branches can run to completion.
    -   **Implementation:** Cascade skips downstream using dummy futures rather than terminating the global scheduler thread.

-   [ ] **Distributed Execution Model**
    -   **Description:** Extend the parallel execution model to support distributed systems. This would allow build/update tasks to be executed across multiple machines, enabling much larger-scale processing.
    -   **Implementation:**
        -   Abstract the execution backend. The current `ThreadPoolExecutor` would become the default local backend.
        -   Investigate and add new backends using libraries like `Dask`, `Ray`, or a custom RPC/queue-based system (e.g., Celery with RabbitMQ/Redis).
        -   This would likely require making `Resource` and `Location` objects serializable or finding a way to reference them across a distributed network.

-   [ ] **"Dry Run" Mode**
    -   **Description:** Add a `dry_run=True` flag to the `run()` method to simulate a run without executing the actual `build` or `update` functions.
    -   **Implementation:**
        -   When `dry_run` is active, the engine would perform all checks and, instead of executing a build/update, it would log a message indicating what action *would* have been taken.
        -   This is extremely useful for debugging and for understanding the impact of changes before committing to a long build process.

## Usability and DX Improvements

-   [ ] **Enhanced Logging and Verbosity Levels**
    -   **Description:** Implement different verbosity levels for logging output. A quiet mode could show only errors, while a verbose mode could show detailed information about every check being performed.

-   [ ] **Plugin System for `Location` Types**
    -   **Description:** To make the engine even more extensible, create a simple plugin system where users can register their own custom `Location` subclasses (e.g., for S3, databases, web APIs) without modifying the core engine code.

## Testing

-   [x] **Create a Comprehensive Unit Test Suite** (Completed)
    -   **Description:** Establish robust unit testing covering engine stability and features.
    -   **Implementation:** Created 15 clean, high-coverage unit tests verifying cyclic graphs, conflicts, compilation levels, custom resource behaviors, polling states, rollbacks, and parallel isolation.