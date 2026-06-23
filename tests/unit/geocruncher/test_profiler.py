from geocruncher.profiler import VkProfiler
from geocruncher.profiler.config import ProfilerConfig
from geocruncher.profiler.storage import ProfilerStorage
from geocruncher.profiler.util import VkProfilerSettings


class FakeStorage(ProfilerStorage):
    def __init__(self):
        self.calls = []

    def save(self, computation, version, metadata, steps):
        self.calls.append((computation, version, metadata, steps))


def test_profiler_update_metadata_merges_values():
    profiler = VkProfiler(
        VkProfilerSettings(version=2, computation="unit", steps=[]),
        storage=None,
    )

    profiler.update_metadata({"user": "test", "sample_count": 3})

    assert profiler._metadata["user"] == "test"
    assert profiler._metadata["sample_count"] == 3
    assert "start_time" in profiler._metadata


def test_profiler_update_metadata_ignores_none():
    profiler = VkProfiler(
        VkProfilerSettings(version=2, computation="unit", steps=[]),
        storage=None,
    )
    before = dict(profiler._metadata)

    profiler.update_metadata(None)

    assert profiler._metadata == before


def test_profiler_ignores_unknown_steps():
    storage = FakeStorage()
    profiler = VkProfiler(
        VkProfilerSettings(version=1, computation="unit", steps=["known"]),
        storage=storage,
    )

    assert profiler.profile("unknown") is profiler

    assert profiler._steps == {"known": {"time": 0.0}}


def test_profiler_save_results_calls_storage_when_storage_is_provided():
    storage = FakeStorage()
    profiler = VkProfiler(
        VkProfilerSettings(version=7, computation="unit", steps=["known"]),
        storage=storage,
    )
    profiler.set_metadata("case", "provided")

    profiler.save_results()

    assert len(storage.calls) == 1
    computation, version, metadata, steps = storage.calls[0]
    assert computation == "unit"
    assert version == 7
    assert metadata["case"] == "provided"
    assert steps == {"known": {"time": 0.0}}


def test_profiler_save_results_is_noop_without_storage():
    profiler = VkProfiler(
        VkProfilerSettings(version=1, computation="unit", steps=["known"]),
        storage=None,
    )

    assert profiler.save_results() is profiler


def test_profiler_config_does_not_create_storage_when_disabled(monkeypatch):
    monkeypatch.setenv("PROFILING_ENABLED", "false")

    config = ProfilerConfig()

    assert config.create_storage() is None
