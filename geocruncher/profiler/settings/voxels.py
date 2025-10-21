# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_VOXELS_V3 = VkProfilerSettings(
    version=3,
    computation='voxels',
    steps=['load_model', 'grid', 'read_gwbs', 'test_inside_gwbs',
        'ranks', 'generate_vox'])
