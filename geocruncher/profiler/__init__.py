from .profiler import VkProfiler, set_profiler, get_current_profiler, profile_step
from .util import VkProfilerSettings
from .settings.tunnel_meshes import PROFILER_TUNNEL_MESHES_V4
from .settings.meshes import PROFILER_MESHES_V5
from .settings.intersections import PROFILER_INTERSECTIONS_V5
from .settings.faults import PROFILER_FAULTS_V4
from .settings.voxels import PROFILER_VOXELS_V3
from .settings.gwb_meshes import PROFILER_GWB_MESHES_V3

PROFILES = {
    'tunnel_meshes': PROFILER_TUNNEL_MESHES_V4,
    'meshes': PROFILER_MESHES_V5,
    'intersections': PROFILER_INTERSECTIONS_V5,
    'faults': PROFILER_FAULTS_V4,
    'voxels': PROFILER_VOXELS_V3,
    'gwb_meshes': PROFILER_GWB_MESHES_V3
}

__all__ = [
    'VkProfiler', 
    'VkProfilerSettings',
    'set_profiler', 
    'get_current_profiler', 
    'profile_step',
    'PROFILES'
]