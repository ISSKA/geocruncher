# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_GWB_MESHES_V2 = VkProfilerSettings(
    2,
    'gwb_meshes',
    ['load_mesh', 'compute', 'generate_mesh'],
    ['start_time', 'num_units', 'num_springs'])
