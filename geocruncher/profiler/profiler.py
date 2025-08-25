import cProfile
import time
import datetime
from typing import Optional

from .util import VkProfilerSettings
from .config import ProfilerConfig
from .storage import ProfilerStorage

class VkProfiler():

    def __init__(self, settings: VkProfilerSettings, storage: Optional[ProfilerStorage] = None):
        self._pr = cProfile.Profile()
        # set the start time, to calculate relative durations
        self._last_profiled = time.process_time()
        self.settings = settings
        self.storage = storage
        # dictionnary where each step's name maps to the total fractional seconds spent on that step (time)
        # TODO: as well as the top function calls calculated by cProfile (profile)
        # make the dictionnary with a default value for each step
        self._steps = dict(
            [[step, {'profile': list(), 'time': 0}] for step in settings.steps])
        # make the dictionnary with a default value for each metadata
        self._metadata = dict([[meta, None] for meta in settings.metadata])

        # set the metadata that's on every computation
        self.set_metadata(
            'start_time', datetime.datetime.now().isoformat())

        if self.storage:
            self._pr.enable()

    def profile(self, step: str) -> 'VkProfiler':
        """Profile a step by name. To be called when the step in question is done.
        Also works inside loops (total time per step gets summed up). For loops, it is recommended 
        to profile at least just before entering and at the end of every iteration, so the first 
        profile in the loop is consistent"""
        if not self.storage or step not in self._steps:
            return self
        now = time.process_time()

        # stop tracking previous step
        self._pr.disable()

        # add for the step the difference between now and the last profiled time
        # since we add, the profile function works in loops. on each loop iteration, the step's time will be increased
        self._steps[step]['time'] += now - self._last_profiled
        self._last_profiled = now
        # start tracking next step
        self._pr.enable()
        return self

    def set_metadata(self, metadata: str, value) -> 'VkProfiler':
        if metadata in self._metadata:
            self._metadata[metadata] = value
        return self

    def save_results(self) -> 'VkProfiler':
        """Save profiling results using configured storage"""
        self._pr.disable()
        
        if self.storage:
            self.storage.save(
                self.settings.computation,
                self.settings.version,
                self._metadata,
                self._steps
            )
        
        return self

class ProfilerManager:
    """Manages global profiler state"""

    def __init__(self):
        self.config = ProfilerConfig()
        self.storage = self.config.create_storage()
        self._current_profiler: Optional[VkProfiler] = None

    def create_profiler(self, settings: VkProfilerSettings) -> None:
        """Create a new profiler instance"""
        profiler = VkProfiler(settings, self.storage)
        self._current_profiler = profiler

    def get_current_profiler(self) -> Optional[VkProfiler]:
        """Get the current profiler instance"""
        return self._current_profiler


# Global profiler manager instance
_profiler_manager = ProfilerManager()

# Public API

def set_profiler(settings: VkProfilerSettings) -> None:
    """Create a new profiler with the given settings"""
    _profiler_manager.create_profiler(settings)


def get_current_profiler() -> Optional[VkProfiler]:
    """Get the current profiler instance"""
    return _profiler_manager.get_current_profiler()


def profile_step(step: str) -> None:
    """Profile a step using the current profiler"""
    profiler = get_current_profiler()
    if profiler:
        profiler.profile(step)
