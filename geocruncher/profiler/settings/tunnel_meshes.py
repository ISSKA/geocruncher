# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_TUNNEL_MESHES_V2 = VkProfilerSettings(
    2,
    'tunnel_meshes',
    ['sympy_parse_diff_function', 'interpolate_function',
        'project_points', 'connect_vertices', 'generate_off'],
    ['start_time', 'num_waypoints', 'shape'])
