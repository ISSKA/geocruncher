# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_INTERSECTIONS_V5 = VkProfilerSettings(
    version=5,
    computation='intersections',
    steps=['load_model', 'cross_section_grid','map_grid', 'ranks', 'tesselate_faults',
     'hydro_setup', 'hydro_project_drillholes', 'hydro_project_springs', 'hydro_project_gwbs'])
