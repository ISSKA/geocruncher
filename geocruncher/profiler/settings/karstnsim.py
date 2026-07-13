# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate file, not mixing between versions
from ..util import VkProfilerSettings

PROFILER_KARSTNSIM_V2 = VkProfilerSettings(
    version=1,
    computation="karstnsim",
    steps=[
        "build_content",
        "load_project_box",
        "load_surface",
        "load_springs",
        "load_water_tables",
        "associate_springs_water_tables",
        "load_faults",
        "load_sinks",
        "compute_dimensions",
        "run_karstnsim",
        "serialize_result",
    ],
)
