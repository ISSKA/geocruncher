# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_FAULTS_V4 = VkProfilerSettings(
    version=4,
    computation='faults',
    steps=['load_model', 'tesselate_faults', 'generate_mesh'])
