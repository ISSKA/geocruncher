# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_KARSTNSIM_V1 = VkProfilerSettings(
    version=1,
    computation="karstnsim",
    steps=[
        "load_project_data",
        "configuration",
        "run_karstnsim",
    ],
)
