# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_KARSTNSIM_V3 = VkProfilerSettings(
    version=1,
    computation="karstnsim",
    steps=[
        "build_content",
        "load_project_box",
        "load_springs",
        "load_water_tables",
        "load_faults",
        "load_sinks",
        "run_karstnsim",
        "serialize_result",
    ],
)
