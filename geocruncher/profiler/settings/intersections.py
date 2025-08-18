# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_INTERSECTIONS_V4 = VkProfilerSettings(
    4,
    'intersections',
    ['load_model', 'cross_section_grid','map_grid', 'ranks', 'tesselate_faults',
     'hydro_setup', 'hydro_project_drillholes', 'hydro_project_springs', 'hydro_project_gwbs'],
    ['start_time', 'num_series', 'num_units', 'num_finite_faults', 'num_infinite_faults', 'num_interfaces', 'num_foliations', 'resolution', 'num_sections', 'compute_map', 'num_springs', 'num_drillholes', 'num_gwb_parts'])
