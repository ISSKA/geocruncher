from pathlib import Path
import cProfile
import time
import datetime

from .util import VkProfilerSettings
from .settings.tunnel_meshes import PROFILER_TUNNEL_MESHES_V2
from .settings.meshes import PROFILER_MESHES_V3
from .settings.intersections import PROFILER_INTERSECTIONS_V2
from .settings.faults import PROFILER_FAULTS_V2
from .settings.faults_intersections import PROFILER_FAULTS_INTERSECTIONS_V2
from .settings.voxels import PROFILER_VOXELS_V2


def _get_csv_header(settings: VkProfilerSettings, separator=';'):
    """Produce a CSV header line for the given profiler settings"""
    return separator.join(settings.metadata) + separator + separator.join(settings.steps) + '\n'


def _get_csv_line(metadata: dict, steps: dict, separator=';'):
    """Produce a CSV line for the given profiler metadata and steps"""
    return separator.join(str(x) for x in metadata.values()) + separator + separator.join(_s_to_ms(x['time']) for x in steps.values()) + '\n'


def _s_to_ms(s: float) -> str:
    """Format seconds to millisecond string with 5 decimals"""
    return '%.5f' % (s * 1000)


class VkProfiler():
    # Instance of cProfile used by every VkProfiler
    _pr = cProfile.Profile()

    def __init__(self, settings: VkProfilerSettings):

        # set the start time, to calculate relative durations
        self._last_profiled = time.process_time()
        self._settings = settings
        # dictionnary where each step's name maps to the total fractional seconds spent on that step (time)
        # TODO: as well as the top function calls calculated by cProfile (profile)
        # make the dictionnary with a default value for each step
        self._steps = dict(
            [[step, {'profile': list(), 'time': 0}] for step in settings.steps])
        # make the dictionnary with a default value for each metadata
        self._metadata = dict([[meta, None] for meta in settings.metadata])

        # set the metadata that's on every computation
        self.set_profiler_metadata(
            'start_time', datetime.datetime.utcnow().isoformat())
        self._pr.enable()

    def profile(self, step: str):
        """Profile a step by name. To be called when the step in question is done.
        Also works inside loops (total time per step gets summed up). For loops, it is recommanded to profile at least just before entering and at the end of every iteration, so the first profile in the loop is consistant"""
        if step in self._steps:
            now = time.process_time()

            # stop tracking previous step
            self._pr.disable()
            # TODO: WIP extracting stats from cProfile
            # _pr.create_stats()
            # ps = pstats.Stats(_pr).sort_stats(
            #     SortKey.TIME, SortKey.NAME)
            # ps.get_stats_profile()

            # add for the step the difference between now and the last profiled time
            # since we add, the profile function works in loops. on each loop iteration, the step's time will be increased
            self._steps[step]['time'] += now - self._last_profiled
            self._last_profiled = now
            # start tracking next step
            self._pr.enable()
        return self

    def set_profiler_metadata(self, metadata: str, value):
        if metadata in self._metadata:
            self._metadata[metadata] = value
        return self

    def save_profiler_results(self):
        """Currently saves the results as CSV. In the future, the results will be saved to a database"""
        # make sure profiling is stopped
        self._pr.disable()

        if _is_profiling_enabled:
            file_name = self._settings.computation + \
                "_v" + str(self._settings.version) + ".csv"
            file_path = _profiler_output_folder.joinpath(file_name)
            # if the file doesn't exist, we need to write the header. otherwise, just the new line
            with open(file_path, "a+", encoding="utf8") as f:
                f.seek(0)
                if len(f.read()) == 0:
                    # file was just created. append header
                    f.write(_get_csv_header(self._settings))
                f.write(_get_csv_line(self._metadata, self._steps))
        return self

# Globals


# Geocruncher profiling is disabled by default
# It can be enabled by calling `set_is_profiling_enabled`
_is_profiling_enabled = False
# The output folder of the profiler is the working directory by default
# It can be modified by calling `set_profiler_output_folder`
_profiler_output_folder = Path.cwd()
# In order for any code to be able to profile code with the current profiler,
# a reference to the current profiler is kept here
# make a default dummy profiler, so code doesn't crash if no profiler was initialized or profiling is disabled
_global_profiler = VkProfiler(VkProfilerSettings(1, 'dummy', [], []))

# Public API


# all profiles indexed by the computation type
# if a new version of a profiler is made, change the key here to automatically choose the new one in main
PROFILES = dict({
    'tunnel_meshes': PROFILER_TUNNEL_MESHES_V2,
    'meshes': PROFILER_MESHES_V3,
    'intersections': PROFILER_INTERSECTIONS_V2,
    'faults': PROFILER_FAULTS_V2,
    'faults_intersections': PROFILER_FAULTS_INTERSECTIONS_V2,
    'voxels': PROFILER_VOXELS_V2
})


def set_is_profiling_enabled(is_profiling_enabled: bool) -> None:
    """Toggle the status of profiling. When disabled, calling `set_current_profiler` will do nothing"""
    global _is_profiling_enabled
    _is_profiling_enabled = is_profiling_enabled


def set_profiler_output_folder(profiler_output_folder: Path) -> None:
    """Choose the folder in which the profiler outputs results. Path is not checked. Defaults to working directory"""
    global _profiler_output_folder
    _profiler_output_folder = profiler_output_folder


def set_current_profiler(profiler: VkProfiler) -> None:
    """Set the current profiler, which will subsequently be returned by calls to `get_current_profiler`"""
    # Ignore setting the current profiler unless profiling is enabled
    if _is_profiling_enabled:
        global _global_profiler
        _global_profiler = profiler


def get_current_profiler() -> VkProfiler:
    return _global_profiler
