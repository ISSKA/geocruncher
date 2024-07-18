# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_FAULTS_INTERSECTIONS_V2 = VkProfilerSettings(
    2,
    'faults_intersections',
    ['load_model', 'sections_grid', 'sections_tesselate',
        'map_grid', 'map_tesselate'],
    ['start_time', 'num_finite_faults', 'num_infinite_faults', 'num_interfaces', 'num_foliations', 'resolution', 'num_sections', 'compute_map'])
