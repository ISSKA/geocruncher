from typing import NamedTuple, List
import time
import datetime


class ProfilerSettings(NamedTuple):
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
PROFILER_TUNNEL_MESHES_V1 = ProfilerSettings(
    1,
    'tunnel_meshes',
    ['read_input', 'sympy_parse_diff_function', 'interpolate_function',
        'project_points', 'connect_vertices', 'generate_off', 'write_output'],
    ['start_time', 'is_sub_tunnel', 'step_size'])
PROFILER_MESHES_V1 = ProfilerSettings(
    1,
    'meshes',
    ['init', 'step 2'],
    ['start_time'])
PROFILER_INTERSECTIONS_V1 = ProfilerSettings(
    1,
    'intersections',
    ['init', 'step 2'],
    ['start_time'])
PROFILER_FAULTS_V1 = ProfilerSettings(
    1,
    'faults',
    ['init', 'step 2'],
    ['start_time'])
PROFILER_FAULTS_INTERSECTIONS_V1 = ProfilerSettings(
    1,
    'faults_intersections',
    ['init', 'step 2'],
    ['start_time'])
PROFILER_VOXELS_V1 = ProfilerSettings(
    1,
    'voxels',
    ['init', 'step 2'],
    ['start_time'])


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


# profiler is not init as long as the settings are None
_settings = None
# dictionnary where each step's name maps to the total fractional seconds spent on that step
_steps = dict()
_metadata = dict()
_last_profiled = None


def init_profiler(settings: ProfilerSettings):
    """Init the profiler. To be called once at the beginning of the geocruncher process"""
    global _settings, _steps, _last_profiled, _metadata
    # set the start time, to calculate relative durations
    _last_profiled = time.process_time()
    _settings = settings
    # make the dictionnary with a default value for each step
    _steps = dict([[step, 0] for step in _settings.steps])
    # make the dictionnary with a default value for each metadata
    _metadata = dict([[meta, None] for meta in _settings.metadata])

    # set the metadata that's on every computation
    set_profiler_metadata("start_time", datetime.datetime.utcnow().isoformat())


def profile(step: str):
    """Profile a step by name. To be called when the step in question is done.
    Also works inside loops (total time per step gets summed up). For loops, it is recommanded to also profile just before entering, and at the end of every iteration, so the first profile in the loop is consistant"""
    global _steps, _last_profiled
    if _settings is not None and step in _steps:
        now = time.process_time()
        # add for the step the difference between now and the last profiled time
        # since we add, the profile function works in loops. on each loop iteration, the step's time will be increased
        _steps[step] += now - _last_profiled
        _last_profiled = now


def set_profiler_metadata(metadata: str, value):
    global _metadata
    if metadata in _metadata:
        _metadata[metadata] = value


def save_profiler_results():
    """For now, make a JSON file for each profiling"""
    global _steps, _settings
    if _settings is not None:
        file_path = "/home/build/geocruncher-profiling/" + \
            _settings.computation + "_v" + str(_settings.version) + ".csv"
        # if the file doesn't exist, we need to write the header. otherwise, just the new line
        with open(file_path, "a+", encoding="utf8") as f:
            f.seek(0)
            if len(f.read()) == 0:
                # file was just created. append header
                f.write(_get_csv_header(_settings))
            f.write(_get_csv_line(_metadata, _steps))


def _get_csv_header(settings: ProfilerSettings, separator=';'):
    return separator.join(settings.metadata) + separator + separator.join(settings.steps) + '\n'


def _get_csv_line(metadata: dict, steps: dict, separator=';'):
    return separator.join(str(x) for x in metadata.values()) + separator + separator.join(_s_to_ms(x) for x in steps.values()) + '\n'


def _s_to_ms(s: float) -> str:
    """format seconds to millisecond string with 5 decimals"""
    return '%.5f' % (s * 1000)
