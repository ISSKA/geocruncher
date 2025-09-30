# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_GWB_MESHES_V3 = VkProfilerSettings(
    version=3,
    computation='gwb_meshes',
    steps=['load_mesh', 'compute', 'generate_mesh'])
