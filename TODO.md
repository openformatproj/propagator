# Propagator Future Features (TODO)

This file lists potential features and improvements for the `propagator` engine.

## Core Engine Enhancements

-   [ ] **Content-Based Hashing for Change Detection**
    -   **Description:** Currently, change detection relies on file modification timestamps (`mtime`). This can be brittle. Implementing content-based hashing (e.g., SHA256) would make change detection more robust. A resource would only be considered "changed" if its content has actually changed.
    -   **Implementation:**
        -   Create a state file (e.g., `propagator.state.json`) to store the hashes of resources after a successful run.
        -   On the next run, compare the current hash of a resource against the stored hash to determine if it needs an update.
        -   This could be an optional mode or a new `Location` type (e.g., `HashedFileLocation`).

-   [ ] **Parallel Execution**
    -   **Description:** The current engine processes resources serially. For large graphs with independent branches, this is inefficient.
    -   **Implementation:**
        -   Use Python's `concurrent.futures.ThreadPoolExecutor` or `ProcessPoolExecutor` to process nodes that do not depend on each other in parallel.
        -   This would require careful management of task scheduling to ensure dependencies are met before a task is submitted to the pool.

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