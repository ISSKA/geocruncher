# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_INTERSECTIONS_V4 = VkProfilerSettings.create_with_common_metadata(
    4,
    'intersections',
    ['load_model', 'cross_section_grid','map_grid', 'ranks', 'tesselate_faults',
     'hydro_setup', 'hydro_project_drillholes', 'hydro_project_springs', 'hydro_project_gwbs'],
    ['num_series', 'num_units', 'num_finite_faults', 'num_infinite_faults', 'num_contact_data', 'num_dips',
      'resolution', 'num_sections', 'compute_map', 'num_springs', 'num_drillholes', 'num_gwb_parts'])
