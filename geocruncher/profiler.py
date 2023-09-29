from typing import NamedTuple, List
import time
import datetime

import cProfile
import pstats
import io
from pstats import SortKey
import json

pr = cProfile.Profile()

# Profiles


class VkProfilerSettings(NamedTuple):
    # version of the profiler
    version: int
    # name of the type of computation
    computation: str
    # list of names of the steps to record
    steps: List[str]
    # additional metadata for this computation
    metadata: List[str]


# if the profiling characteristics change, make a new version.
# the code will then append the stats to an appropriate CSV file, not mixing between versions
PROFILER_TUNNEL_MESHES_V1 = VkProfilerSettings(
    1,
    'tunnel_meshes',
    ['sympy_parse_diff_function', 'interpolate_function',
        'project_points', 'connect_vertices', 'generate_off', 'write_output'],
    ['start_time', 'num_waypoints', 'shape'])
PROFILER_MESHES_V1 = VkProfilerSettings(
    1,
    'meshes',
    ['load_model', 'setup', 'grid', 'ranks', 'volume',
        'marching_cubes', 'faults', 'generate_off', 'write_output'],
    ['start_time', 'num_series', 'num_units', 'num_faults', 'num_interfaces', 'num_foliations', 'resolution'])
PROFILER_INTERSECTIONS_V1 = VkProfilerSettings(
    1,
    'intersections',
    ['load_model', 'step 2'],
    ['start_time'])
PROFILER_FAULTS_V1 = VkProfilerSettings(
    1,
    'faults',
    ['load_model', 'step 2'],
    ['start_time'])
PROFILER_FAULTS_INTERSECTIONS_V1 = VkProfilerSettings(
    1,
    'faults_intersections',
    ['load_model', 'step 2'],
    ['start_time'])
PROFILER_VOXELS_V1 = VkProfilerSettings(
    1,
    'voxels',
    ['load_model', 'step 2'],
    ['start_time'])
DUMMY_PROFILER = VkProfilerSettings(1, 'dummy', [], [])


# all profiles indexes by the computation type
# if a new version of a profiler is made, change the key here to automatically choose the new one in main
PROFILES = dict({
    'tunnel_meshes': PROFILER_TUNNEL_MESHES_V1,
    'meshes': PROFILER_MESHES_V1,
    'intersections': PROFILER_INTERSECTIONS_V1,
    'faults': PROFILER_FAULTS_V1,
    'faults_intersections': PROFILER_FAULTS_INTERSECTIONS_V1,
    'voxels': PROFILER_VOXELS_V1
})

# Profiler class


class VkProfiler():
    def __init__(self, settings: VkProfilerSettings):

        # set the start time, to calculate relative durations
        self._last_profiled = time.process_time()
        self._settings = settings
        # dictionnary where each step's name maps to the total fractional seconds spent on that step
        # make the dictionnary with a default value for each step
        self._steps = dict(
            [[step, {'profile': list(), 'time': 0}] for step in settings.steps])
        # make the dictionnary with a default value for each metadata
        self._metadata = dict([[meta, None] for meta in settings.metadata])

        # set the metadata that's on every computation
        self.set_profiler_metadata(
            'start_time', datetime.datetime.utcnow().isoformat())
        pr.enable()

    def profile(self, step: str):
        """Profile a step by name. To be called when the step in question is done.
        Also works inside loops (total time per step gets summed up). For loops, it is recommanded to profile just before entering, and at the end of every iteration, so the first profile in the loop is consistant"""
        if step in self._steps:
            now = time.process_time()

            # TODO: WIP extracting stats from cProfile
            # stop tracking previous step
            pr.disable()
            # s = io.StringIO()
            # pr.create_stats()
            # ps = pstats.Stats(pr).sort_stats(
            #     SortKey.TIME, SortKey.NAME)
            # ps.print_stats(15)
            # ps.get_stats_profile()

            # file_path = "/home/build/geocruncher-profiling/cprofile.txt"
            # with open(file_path, "w+", encoding="utf8") as f:
            #     f.write(step + "\n\n")
            #     f.write(str(pr.stats))

            # add for the step the difference between now and the last profiled time
            # since we add, the profile function works in loops. on each loop iteration, the step's time will be increased
            self._steps[step]['time'] += now - self._last_profiled
            self._last_profiled = now
            # start tracking next step
            pr.enable()
        return self

    def set_profiler_metadata(self, metadata: str, value):
        if metadata in self._metadata:
            self._metadata[metadata] = value
        return self

    def save_profiler_results(self):
        """For now, make a JSON file for each profiling"""
        # make sure profiling is stopped
        pr.disable()

        # TODO: make path configurable
        file_path = "/home/build/geocruncher-profiling/" + \
            self._settings.computation + "_v" + \
            str(self._settings.version) + ".csv"
        # if the file doesn't exist, we need to write the header. otherwise, just the new line
        with open(file_path, "a+", encoding="utf8") as f:
            f.seek(0)
            if len(f.read()) == 0:
                # file was just created. append header
                f.write(_get_csv_header(self._settings))
            f.write(_get_csv_line(self._metadata, self._steps))
        return self

# Utilities


def _get_csv_header(settings: VkProfilerSettings, separator=';'):
    return separator.join(settings.metadata) + separator + separator.join(settings.steps) + '\n'


def _get_csv_line(metadata: dict, steps: dict, separator=';'):
    return separator.join(str(x) for x in metadata.values()) + separator + separator.join(_s_to_ms(x['time']) for x in steps.values()) + '\n'


def _s_to_ms(s: float) -> str:
    """format seconds to millisecond string with 5 decimals"""
    return '%.5f' % (s * 1000)

# Global reference


# In order for any code to be able to profile code with the current profiler
# a reference to the current profiler is kept here
# make a default dummy profiler, so code doesn't crash if no profiler was initialized
_global_profiler = VkProfiler(DUMMY_PROFILER)


def set_current_profiler(profiler: VkProfiler):
    global _global_profiler
    _global_profiler = profiler


def get_current_profiler():
    return _global_profiler
