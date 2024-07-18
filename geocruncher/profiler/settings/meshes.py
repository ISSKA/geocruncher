# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_MESHES_V1 = VkProfilerSettings(
    1,
    'meshes',
    ['load_model', 'grid', 'ranks', 'volume',
        'marching_cubes', 'tesselate_faults', 'generate_off', 'write_output'],
    ['start_time', 'num_series', 'num_units', 'num_finite_faults', 'num_infinite_faults', 'num_interfaces', 'num_foliations', 'resolution'])
