# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_FAULTS_V5 = VkProfilerSettings(
    version=5,
    computation="faults",
    steps=["load_model", "tesselate_faults", "generate_mesh"],
)
