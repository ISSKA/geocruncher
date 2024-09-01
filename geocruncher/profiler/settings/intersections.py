# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_INTERSECTIONS_V3 = VkProfilerSettings(
    3,
    'intersections',
    ['load_model', 'hydro_setup', 'hydro_project_drillholes', 'hydro_project_springs', 'hydro_test_inside_gwbs', 'hydro_combine_gwbs',
        'fault_sections_grid', 'fault_sections_tesselate', 'sections_ranks', 'map_grid', 'map_ranks', 'fault_map_grid', 'fault_map_tesselate'],
    ['start_time', 'num_series', 'num_units', 'num_finite_faults', 'num_infinite_faults', 'num_interfaces', 'num_foliations', 'resolution', 'num_sections', 'compute_map', 'num_springs', 'num_drillholes', 'num_gwb_parts'])
