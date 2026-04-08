# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_MESHES_V6 = VkProfilerSettings(
    version=6,
    computation="meshes",
    steps=[
        "load_model",
        "ranks",
        "volume",
        "marching_cubes",
        "tesselate_faults",
        "generate_mesh",
    ],
)
