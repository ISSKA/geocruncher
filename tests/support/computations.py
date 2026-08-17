from types import SimpleNamespace

import pytest

import geocruncher.computations as computations


class FakeBox:
    def __init__(self, xmin, ymin, zmin, xmax, ymax, zmax):
        self.xmin = xmin
        self.ymin = ymin
        self.zmin = zmin
        self.xmax = xmax
        self.ymax = ymax
        self.zmax = zmax

    def as_tuple(self):
        return (self.xmin, self.ymin, self.zmin, self.xmax, self.ymax, self.zmax)


class FakeProfiler:
    def __init__(self, settings):
        self.settings = settings
        self.metadata = {}
        self.saved = False

    def set_metadata(self, key, value):
        self.metadata[key] = value
        return self

    def update_metadata(self, metadata):
        if metadata:
            self.metadata.update(metadata)
        return self

    def save_results(self):
        self.saved = True
        return self


@pytest.fixture
def computation_fakes(monkeypatch):
    records = SimpleNamespace(
        parsed=[],
        adapted=[],
        models=[],
        profilers=[],
        profile_steps=[],
    )

    class FakeGeologicalModel:
        def __init__(self, project_data, use_cache):
            self.project_data = project_data
            self.use_cache = use_cache
            self.box = FakeBox(0, 10, 20, 100, 210, 320)
            records.models.append(self)

        def getbox(self):
            return self.box

    def fake_deserialize_geological_model(model_data):
        records.parsed.append(model_data)
        return {"parsed": model_data}

    def fake_build_gmlib_project_data(message, extent, dem, *, validate_input):
        records.adapted.append((message, extent, dem, validate_input))
        return {"message": message, "extent": extent, "dem": dem}

    def fake_set_profiler(settings):
        profiler = FakeProfiler(settings)
        records.profilers.append(profiler)
        return profiler

    monkeypatch.setattr(computations, "Box", FakeBox)
    monkeypatch.setattr(computations, "GeologicalModel", FakeGeologicalModel)
    monkeypatch.setattr(
        computations,
        "deserialize_geological_model",
        fake_deserialize_geological_model,
    )
    monkeypatch.setattr(
        computations, "build_gmlib_project_data", fake_build_gmlib_project_data
    )
    monkeypatch.setattr(computations, "set_profiler", fake_set_profiler)
    monkeypatch.setattr(
        computations, "profile_step", lambda step: records.profile_steps.append(step)
    )

    monkeypatch.setattr(
        computations.MetadataHelpers, "num_erode_series", staticmethod(lambda model: 1)
    )
    monkeypatch.setattr(
        computations.MetadataHelpers, "num_onlap_series", staticmethod(lambda model: 2)
    )
    monkeypatch.setattr(
        computations.MetadataHelpers, "num_units", staticmethod(lambda model: 3)
    )
    monkeypatch.setattr(
        computations.MetadataHelpers, "num_finite_faults", staticmethod(lambda model: 4)
    )
    monkeypatch.setattr(
        computations.MetadataHelpers,
        "num_infinite_faults",
        staticmethod(lambda model: 5),
    )
    monkeypatch.setattr(
        computations.MetadataHelpers,
        "num_stops_on_relations",
        staticmethod(lambda model: 6),
    )
    monkeypatch.setattr(
        computations.MetadataHelpers,
        "num_contact_data",
        staticmethod(lambda model, unit=True, fault=True: 7),
    )
    monkeypatch.setattr(
        computations.MetadataHelpers,
        "num_dips",
        staticmethod(lambda model, unit=True, fault=True: 8),
    )

    return records


MODEL_METADATA = {
    "num_erode_series": 1,
    "num_onlap_series": 2,
    "num_units": 3,
    "num_finite_faults": 4,
    "num_infinite_faults": 5,
    "num_stops_on_relations": 6,
    "num_contact_data": 7,
    "num_dips": 8,
}


def assert_metadata_contains(metadata, expected):
    assert {key: metadata[key] for key in expected} == expected
