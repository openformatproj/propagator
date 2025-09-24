# Propagator

**Propagator** is a lightweight, flexible, and dependency-aware build and update engine for Python. It allows you to define a directed acyclic graph (DAG) of resources, where each resource can be a file or any other entity, and specify how to build or update them based on their dependencies.

Think of it as a Python-native alternative to `make`, designed for orchestrating complex data processing, code generation, or compilation pipelines directly within your application.

## Features

-   **Dependency Management**: Define dependencies between resources to create a clear and robust execution graph.
   -   **Topological Execution**: Resources are processed in a topologically sorted order, ensuring dependencies are met before a resource is built or updated.
   -   **Automatic Update Propagation**: The engine automatically detects if a dependency is newer than a target resource and triggers an update.
   -   **Cyclic Dependency Detection**: Automatically detects and reports cyclic dependencies to prevent infinite loops.
   -   **Custom Build/Update Logic**: Provide your own Python functions for building and updating each resource, giving you full control over the process.
   -   **Error Handling**: Captures exceptions during execution and provides detailed error reports. Propagation can be configured to stop on first error or to collect all errors.
   -   **Progress and History**: Visual feedback during execution via a progress bar (`alive-progress`) and a detailed history of all events and errors.
   -   **Graph Visualization**: A utility to display the dependency graph using `matplotlib` and `networkx` for easy debugging and visualization.

## Core Concepts

1.  **Resource**: The fundamental unit in the system. A resource represents an entity (like a file) that can be created or updated. It has:
    -   `location`: A handle to the resource (e.g., a `pathlib.Path`).
    -   `identifier`: A unique `str` name for the resource.
    -   `builder`: A Python function to create the resource if it doesn't exist.
    -   `updater`: A Python function to update the resource if its dependencies have changed.

2.  **Dependency**: A relationship between two resources. If `Resource B` depends on `Resource A`, it means `A` is a *requirement* for `B`. `B` cannot be built or updated until `A` is available and up-to-date.

3.  **Propagator**: The main engine that manages the dependency graph and orchestrates the execution. You add dependencies to the propagator and then call `run()` to start the process.

## Installation

The engine relies on a few external libraries. You can install them using pip:

```bash
pip install networkx matplotlib alive-progress
```

Then, simply place the `propagator` directory within your project's source tree.

## Quick Start

Here is a simple example of compiling two `.c` files into object files and then linking them into a final executable.

```python
import pathlib
import subprocess
from propagator.engine import Propagator, Resource, FileLocation, void_function

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

1.  Save the code above as `example.py`.
2.  Place `engine.py` in a `propagator` subdirectory.
3.  Run `python example.py`.

The script will first build all targets. If you run it again, it will do nothing. If you `touch src/lib.c` and run it again, it will intelligently recompile `lib.o` and relink `program`, but it will not recompile `main.o`.

## API Reference

### `propagator.engine.Propagator`

-   `add(requirement: Resource, target: Resource)`: Adds a dependency to the graph.
-   `run(block_propagation_level: PropagationLevel = PropagationLevel.COLLECT_ALL_ERRORS)`: Executes the build/update process.
    -   `PropagationLevel.COLLECT_ALL_ERRORS` (0): Never stops on error; collects all errors.
    -   `PropagationLevel.STOP_ON_CRITICAL_ERROR` (1): Stops if a build/update fails or a requirement is missing.
    -   `PropagationLevel.STOP_ON_ANY_ERROR` (2): Stops on any error, including "not performed" warnings.
-   `show()`: Displays a plot of the dependency graph.
-   `history`: A list of `Event` and `Error` objects in chronological order of occurrence.
-   `events`: A list of successful `Event` objects.
-   `errors`: A list of `Error` objects.