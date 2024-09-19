# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_GWB_MESHES_V1 = VkProfilerSettings(
    1,
    'gwb_meshes',
    ['load_off', 'compute', 'generate_off'],
    ['start_time', 'num_units', 'num_springs'])
