# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_FAULTS_V3 = VkProfilerSettings(
    3,
    'faults',
    ['load_model', 'tesselate_faults', 'generate_mesh'],
    ['start_time', 'num_finite_faults', 'num_infinite_faults', 'num_interfaces', 'num_foliations', 'resolution'])
