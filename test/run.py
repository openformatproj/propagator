import pathlib
import os
import propagator.engine as prop

this_path = os.path.dirname(os.path.realpath(__file__))

# Three files, A, B and C. C depends on A and B (A -> C, B -> C): this means when either A or B is more recent than C, C is updated when propagator.run() is launched.
# C is updated according to the following update function (updater):

def c_updater(location, requirements):
    with open(requirements['A'].location, 'r', encoding='utf-8') as reader:
        with open(location, 'w', encoding='utf-8') as writer:
            writer.write(reader.read())
    return "Written A in C"

# Which copies the content of A in C

all_resources_available = False
try:
    # Declare resources. For each of them, a builder and an updater must be provided. Both must either leave the resource unaltered and raise an Exception or effectively build/update the resource, returning a descriptive message. If a build/update is launched but the function neither raises an exception nor builds/updates the resource, a NOT_PERFORMED_BUILD/NOT_PERFORMED_UPDATE error is collected. Use void_function if the resource doesn't need to be built or updated
    A = prop.Resource(pathlib.Path(f'{this_path}/a.txt'), 'A', prop.void_function, prop.void_function)
    B = prop.Resource(pathlib.Path(f'{this_path}/b.txt'), 'B', prop.void_function, prop.void_function)
    C = prop.Resource(pathlib.Path(f'{this_path}/c.txt'), 'C', prop.void_function, c_updater)
    all_resources_available = True
except prop.Error as e:
    print(f'KO. {e}.')
if all_resources_available:
    propagator = prop.Propagator()
    try:
        propagator.add(A, C) # A -> C
        propagator.add(B, C) # B -> C
        print('\nRunning propagator...\n')
        propagator.run()
        print('\n... OK\n')
    except prop.Error as e:
        print(f'\n... KO. {e}.\n')
    history = propagator.history
    if (len(history) > 0):
        print('History:\n')
        i = 1
        for h in history:
            print(f'\t{i}) {type(h).__name__}: {h.details}')
            i = i+1
        print('\n')
    # propagator.show() Show a graph of dependencies
