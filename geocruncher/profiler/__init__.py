from .profiler import (
    VkProfiler,
    get_current_profiler,
    profile_step,
    set_profiler,
    start_step,
)
from .settings.faults import PROFILER_FAULTS_V5
from .settings.gwb_meshes import PROFILER_GWB_MESHES_V3
from .settings.intersections import PROFILER_INTERSECTIONS_V5
from .settings.karstnsim import PROFILER_KARSTNSIM_V3
from .settings.meshes import PROFILER_MESHES_V6
from .settings.tunnel_meshes import PROFILER_TUNNEL_MESHES_V4
from .settings.voxels import PROFILER_VOXELS_V3
from .util import ProfilerMetadata, VkProfilerSettings

PROFILES = {
    "tunnel_meshes": PROFILER_TUNNEL_MESHES_V4,
    "meshes": PROFILER_MESHES_V6,
    "intersections": PROFILER_INTERSECTIONS_V5,
    "faults": PROFILER_FAULTS_V5,
    "voxels": PROFILER_VOXELS_V3,
    "gwb_meshes": PROFILER_GWB_MESHES_V3,
    "karstnsim": PROFILER_KARSTNSIM_V3,
}

__all__ = [
    "VkProfiler",
    "VkProfilerSettings",
    "ProfilerMetadata",
    "set_profiler",
    "get_current_profiler",
    "profile_step",
    "start_step",
    "PROFILES",
]
