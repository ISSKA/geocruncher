import os

import pytest

os.environ.setdefault("REDIS_HOST", "localhost")


@pytest.fixture(autouse=True)
def reset_progress_recorder_task():
    import geocruncher.profiler.profiler as profiler_module

    # Reset the profiler manager and progress recorder before and after each test
    profiler_module._profiler_manager._current_profiler = None
    profiler_module._progress_recorder.task = None
    yield
    profiler_module._profiler_manager._current_profiler = None
    profiler_module._progress_recorder.task = None
