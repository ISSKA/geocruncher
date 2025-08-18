from .profiler import VkProfiler, set_profiler, get_current_profiler, profile_step
from .util import VkProfilerSettings
from .settings.tunnel_meshes import PROFILER_TUNNEL_MESHES_V3
from .settings.meshes import PROFILER_MESHES_V4
from .settings.intersections import PROFILER_INTERSECTIONS_V4
from .settings.faults import PROFILER_FAULTS_V3
from .settings.voxels import PROFILER_VOXELS_V2
from .settings.gwb_meshes import PROFILER_GWB_MESHES_V2

PROFILES = {
    'tunnel_meshes': PROFILER_TUNNEL_MESHES_V3,
    'meshes': PROFILER_MESHES_V4,
    'intersections': PROFILER_INTERSECTIONS_V4,
    'faults': PROFILER_FAULTS_V3,
    'voxels': PROFILER_VOXELS_V2,
    'gwb_meshes': PROFILER_GWB_MESHES_V2
}

__all__ = [
    'VkProfiler', 
    'VkProfilerSettings',
    'set_profiler', 
    'get_current_profiler', 
    'profile_step',
    'PROFILES'
]