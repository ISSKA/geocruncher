# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_GENERATED_NETWORK_V1 = VkProfilerSettings(
    version=1,
    computation="generated_network",
    steps=[
        "run_generation",
    ],
)
