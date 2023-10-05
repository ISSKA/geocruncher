# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_VOXELS_V1 = VkProfilerSettings(
    1,
    'voxels',
    ['load_model', 'grid', 'read_gwbs', 'test_inside_gwbs',
        'ranks', 'generate_vox', 'write_output'],
    ['start_time', 'num_series', 'num_units', 'num_gwb_parts', 'resolution'])
