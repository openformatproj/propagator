- [Propagator](#propagator)
  - [Features](#features)
  - [Core Concepts](#core-concepts)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
    - [Running the Example](#running-the-example)
  - [Extending Propagator](#extending-propagator)
    - [Custom Location Types](#custom-location-types)
  - [Testing](#testing)
  - [API Reference](#api-reference)
    - [`propagator.Propagator`](#propagatorpropagator)
  - [Future Enhancements](#future-enhancements)

# Propagator

**Propagator** is a lightweight, flexible, and dependency-aware build and update engine for Python. It allows you to define a directed acyclic graph (DAG) of resources, where each resource can be a file or any other entity, and specify how to build or update them based on their dependencies.

Think of it as a Python-native alternative to `make`, designed for orchestrating complex data processing, code generation, or compilation pipelines directly within your application.

## Features

-   **Dependency Management**: Define dependencies between resources to create a clear and robust execution graph.
    -   **Topological Execution**: Resources are processed in a topologically sorted order, ensuring dependencies are met before a resource is built or updated.
    -   **Automatic Update Propagation**: The engine automatically detects if a dependency is newer than a target resource and triggers an update.
    -   **Parallel Execution**: The engine leverages Python's `concurrent.futures.ThreadPoolExecutor` to automatically execute independent build or update tasks in parallel. This can lead to significant speed improvements on multi-core systems. The degree of parallelism can be controlled via the `max_workers` parameter in the `run()` method.
    -   **Branch-Level Failure Isolation**: When independent branches fail, failure cascades topologically only to their downstream dependents while allowing sibling parallel branches to execute normally.
    -   **Granular Cache Polling**: Programmatically inspect the exact cache and build status of all nodes topologically (`TODO`, `OUT_OF_DATE`, or `DONE`).
    -   **Recursive Downstream Rollback**: Invalidate specific nodes by deleting their files and automatically unlinking all of their transitively dependent downstream resources.
    -   **Cyclic Dependency Detection**: Automatically detects and reports cyclic dependencies to prevent infinite loops.
    -   **Custom Build/Update Logic**: Provide your own Python functions for building and updating each resource, giving you full control over the process.
    -   **Error Handling**: Captures exceptions during execution and provides detailed error reports. Propagation can be configured to stop on first error or to collect all errors.
    -   **Progress and History**: Visual feedback during execution via a progress bar (`alive-progress`) and a detailed history of all events and errors.
    -   **Graph Visualization**: A utility to display the dependency graph using `matplotlib` and `networkx` for easy debugging and visualization.

## Core Concepts

1.  **Resource**: The fundamental unit in the system. A resource represents an entity (like a file) that can be created or updated. It has:
    -   `location`: A `Location` object that points to the resource and provides state information (e.g., `FileLocation` which wraps a `pathlib.Path`).
    -   `identifier`: A unique `str` name for the resource.
    -   `builder`: A Python function to create the resource if it doesn't exist. Use `propagator.void_function` if no build action is needed (e.g., for source files that are only requirements).
    -   `updater`: A Python function to update the resource if its dependencies have changed. Use `propagator.void_function` if no update action is needed (e.g., if the resource is always rebuilt or never changes).

2.  **Dependency**: A relationship between two resources. If `Resource B` depends on `Resource A`, it means `A` is a *requirement* for `B`. `B` cannot be built or updated until `A` is available and up-to-date.

3.  **Propagator**: The main engine that manages the dependency graph and orchestrates the execution. You add dependencies to the propagator and then call `run()` to start the process.

## Installation

1.  **Clone the Repository**

    First, clone the repository from GitHub to your local machine and navigate into the project directory.

    ```bash
    git clone https://github.com/openformatproj/propagator.git
    ```

2.  **Create and Activate a Virtual Environment**

    From the root of the project directory, create and activate a Python virtual environment. This ensures that dependencies are managed cleanly.

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies and the Package**

    Install the required libraries and then install the `propagator` package itself in "editable" mode. This mode makes the package available to your environment, which is necessary for both running examples and the test suite.

    ```bash
    pip install -r propagator/requirements.txt
    pip install -e .
    ```

## Quick Start

Here is a simple example of compiling two `.c` files into object files and then linking them into a final executable.

```python
import pathlib
import subprocess
from propagator import Propagator, Resource, FileLocation, void_function

# Helper function to run shell commands
def run_command(command):
    print(f"Executing: {' '.join(command)}")
    subprocess.run(command, check=True)

# --- 1. Define Builder and Updater Functions ---

# Builder for compiling a .c file to a .o file
def compile_c_file(location, requirements):
    # requirements is a dict of {'identifier': Resource}
    source_file = list(requirements.values())[0].location.path
    command = ["gcc", "-c", str(source_file), "-o", str(location.path)]
    run_command(command)
    return f"Compiled {source_file.name}"

# Builder for linking .o files into an executable
def link_objects(location, requirements):
    object_files = [str(r.location.path) for r in requirements.values()]
    command = ["gcc"] + object_files + ["-o", str(location.path)]
    run_command(command)
    return f"Linked {len(object_files)} object(s)"

# --- 2. Define Resources ---

SRC_DIR = pathlib.Path("src")
OBJ_DIR = pathlib.Path("obj")
BIN_DIR = pathlib.Path("bin")

# Ensure directories exist
SRC_DIR.mkdir(exist_ok=True)
OBJ_DIR.mkdir(exist_ok=True)
BIN_DIR.mkdir(exist_ok=True)

# Create dummy source files
(SRC_DIR / "main.c").write_text('int main() { return 0; }')
(SRC_DIR / "lib.c").write_text('void lib_func() {}')

# Source file resources (they have no builder/updater)
main_c = Resource(FileLocation(SRC_DIR / "main.c"), "main.c", void_function, void_function)
lib_c = Resource(FileLocation(SRC_DIR / "lib.c"), "lib.c", void_function, void_function)

# Object file resources
main_o = Resource(FileLocation(OBJ_DIR / "main.o"), "main.o", compile_c_file, compile_c_file)
lib_o = Resource(FileLocation(OBJ_DIR / "lib.o"), "lib.o", compile_c_file, compile_c_file)

# Executable resource
program = Resource(FileLocation(BIN_DIR / "program"), "program", link_objects, link_objects)

# --- 3. Set up the Propagator and Add Dependencies ---

p = Propagator()

# Dependencies for object files
p.add(requirement=main_c, target=main_o) # main.o depends on main.c
p.add(requirement=lib_c, target=lib_o)   # lib.o depends on lib.c

# Dependencies for the final program
p.add(requirement=main_o, target=program) # program depends on main.o
p.add(requirement=lib_o, target=program)  # program depends on lib.o

# --- 4. Visualize and Run ---

print("Dependency Graph:")
p.show()

print("\nRunning propagator...")
try:
    p.run()
    print("\nPropagation successful!")
    for event in p.history:
        print(f"- {event.details}")
except Exception as e:
    print(f"\nPropagation failed: {e}")
    for error in p.errors:
        print(f"- {error.details}")

```

### Running the Example

1.  Save the code above as `example.py` in your project directory.
2.  Make sure you have activated your virtual environment (`source venv/bin/activate`).
3.  Run the script from your terminal:
    `python example.py`

The script will first build all targets. If you run it again, it will do nothing. If you `touch src/lib.c` and run it again, it will intelligently recompile `lib.o` and relink `program`, but it will not recompile `main.o`.

## Extending Propagator

### Custom Location Types

The `propagator` engine is designed to be flexible, allowing you to define your own `Location` types beyond the default `FileLocation`. This enables you to manage resources that are not files, such as database entries, API endpoints, or cloud storage objects.

To create a custom `Location` type, you need to subclass `propagator.Location` (assuming `propagator.Location` is the base abstract class, or `propagator.FileLocation` if your custom location is file-like but needs additional logic) and implement the following methods:

-   `exists(self) -> bool`: Returns `True` if the resource at this location exists, `False` otherwise.
-   `get_timestamp(self) -> float`: Returns a timestamp (e.g., Unix timestamp) representing the last modification time of the resource. This is crucial for dependency checking.
-   `is_older_than(self, other_location: 'Location') -> bool`: Compares the timestamp of this location with another `Location` object. Returns `True` if this location's resource is older than `other_location`'s resource, `False` otherwise.

Here's an example of a hypothetical `DatabaseEntryLocation`:

```python
import datetime
from propagator import Location # Assuming propagator.Location is the base class

class DatabaseEntryLocation(Location):
    def __init__(self, table_name: str, entry_id: str):
        self.table_name = table_name
        self.entry_id = entry_id
        # In a real scenario, you'd have a database connection here
        # For this example, we'll simulate existence and timestamps

    def exists(self) -> bool:
        # Simulate checking if a database entry exists
        # e.g., SELECT COUNT(*) FROM {self.table_name} WHERE id = {self.entry_id}
        print(f"Checking existence for DB entry {self.entry_id} in {self.table_name}")
        return True # For demonstration purposes

    def get_timestamp(self) -> float:
        # Simulate getting the last update timestamp from the database
        # e.g., SELECT last_modified FROM {self.table_name} WHERE id = {self.entry_id}
        # For demonstration, return current time or a fixed time
        print(f"Getting timestamp for DB entry {self.entry_id} in {self.table_name}")
        return datetime.datetime.now().timestamp()

    def is_older_than(self, other_location: 'Location') -> bool:
        # This method is crucial for dependency checking
        # It determines if the resource at this location needs to be updated
        if not isinstance(other_location, Location):
            # If comparing with a non-Location type, we can't determine age
            return False 
        
        # A resource that doesn't exist is considered "older" than anything that does,
        # implying it needs to be built.
        if not self.exists():
            return True
        
        # If the other resource doesn't exist, this one isn't older than it.
        # (It might be newer, or both might not exist, but it doesn't need updating based on other)
        if not other_location.exists():
            return False

        # If both exist, compare their timestamps
        return self.get_timestamp() < other_location.get_timestamp()

    def __str__(self):
        return f"DB:{self.table_name}/{self.entry_id}"

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return (isinstance(other, DatabaseEntryLocation) and
                self.table_name == other.table_name and
                self.entry_id == other.entry_id)

    def __hash__(self):
        return hash((self.table_name, self.entry_id))
```

## Testing

The project includes a test suite using `pytest`. To run the tests, first ensure you have followed the installation steps.

From the root of the project directory, simply run:

```bash
pytest
```

Pytest will automatically discover and run all the tests in the `test/` directory, reporting the results to your console.

## API Reference

### `propagator.Propagator`

-   `add(requirement: Resource, target: Resource)`: Adds a dependency to the graph.
-   `run(block_propagation_level: PropagationLevel = PropagationLevel.COLLECT_ALL_ERRORS, max_workers: int = None)`: Executes the build/update process.
    -   `block_propagation_level`: Controls error handling behavior.
        -   `PropagationLevel.COLLECT_ALL_ERRORS` (0): The engine attempts to process as many resources as possible, collecting all errors (e.g., `NOT_FOUND_REQUIREMENT`, `FAILED_BUILD`, `NOT_PERFORMED_BUILD`/`UPDATE`). The `run()` method will raise a single `Error` exception at the end if any errors occurred.
        -   `PropagationLevel.STOP_ON_CRITICAL_ERROR` (1): Stops propagation immediately upon encountering a critical error, such as a `NOT_FOUND_REQUIREMENT` or `FAILED_BUILD`/`FAILED_UPDATE`. Non-critical errors like `NOT_PERFORMED_BUILD`/`UPDATE` are still collected but do not halt execution.
        -   `PropagationLevel.STOP_ON_ANY_ERROR` (2): Stops propagation immediately upon encountering *any* error, whether critical or non-critical. This includes `NOT_PERFORMED_BUILD`/`UPDATE` errors.
    -   `max_workers`: The maximum number of threads to use for parallel execution. Defaults to the system's default for `ThreadPoolExecutor`.
-   `poll() -> Dict[str, str]`: Dynamically analyzes the execution state of all resources in the graph. Returns a dictionary mapping resource identifiers to their current status:
    -   `"TODO"`: Target needs to be built.
    -   `"OUT_OF_DATE"`: Target exists, but some dependency has been updated more recently.
    -   `"DONE"`: Target is compiled and newer than all dependencies.
-   `rollback_resource(identifier: str)`: Recursively deletes (unlinks) the output files of the target resource and all of its downstream dependents transitively.
-   `show()`: Displays a plot of the dependency graph.
-   `history`: A list of `Event` and `Error` objects in chronological order of occurrence.
-   `events`: A list of successful `Event` objects.
-   `errors`: A list of `Error` objects.

## Future Enhancements

The `propagator` engine is under active development, and several key features are planned to further enhance its capabilities:

-   **"Dry Run" Mode**: A planned feature to simulate a propagation run without actually executing any build or update functions. This will be invaluable for debugging and understanding the impact of changes before committing to them.
-   **Content-Based Hashing for Change Detection**: Currently, change detection relies on file modification timestamps. Future plans include implementing content-based hashing (e.g., SHA256) to provide a more robust and accurate way to determine if a resource has truly changed, independent of its timestamp.
-   **Enhanced Logging and Verbosity Levels**: More granular control over logging output to provide clearer insights into the propagation process, from quiet mode (errors only) to highly verbose debugging information.
-   **Plugin System for Custom Location Types**: Further abstraction to allow users to easily register and use their own custom `Location` subclasses (e.g., for S3, databases, web APIs) without modifying the core engine.

Stay tuned for these and other improvements!