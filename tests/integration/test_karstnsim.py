import importlib.util
import json
from math import isclose

import pytest

from geocruncher.generated_network.models import GeneratedNetworkData

pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("pykarstnsim"),
    reason="pykarstnsim not installed",
)


@pytest.fixture(scope="module")
def simulation_result(generated_network_project):
    from geocruncher.generated_network.simulation import run_karstnsim

    data = GeneratedNetworkData.model_validate(generated_network_project.data_dict)

    return run_karstnsim(
        data,
        generated_network_project.dem_bytes,
        generated_network_project.voxels_str,
        generated_network_project.fault_bytes,
    )


def test_invalid_spring_raises_value_error(generated_network_project):
    from geocruncher.generated_network.simulation import run_karstnsim

    broken = GeneratedNetworkData.model_validate(
        {**generated_network_project.data_dict, "gwbs": []}
    )

    with pytest.raises(ValueError, match="groundwater body"):
        run_karstnsim(
            broken,
            generated_network_project.dem_bytes,
            generated_network_project.voxels_str,
            generated_network_project.fault_bytes,
        )


def test_raises_when_simulation_returns_none(generated_network_project, monkeypatch):
    from geocruncher.generated_network import simulation as sim_module
    from geocruncher.generated_network.simulation import run_karstnsim

    monkeypatch.setattr(sim_module, "run_simulation", lambda *args, **kwargs: None)

    data = GeneratedNetworkData.model_validate(generated_network_project.data_dict)

    with pytest.raises(ValueError, match="no result"):
        run_karstnsim(
            data,
            generated_network_project.dem_bytes,
            generated_network_project.voxels_str,
            generated_network_project.fault_bytes,
        )


def test_matches_control_output(simulation_result, control_output):
    actual = json.loads(simulation_result)
    expected = json.loads(control_output)

    assert len(actual) == len(expected)

    for i, (a_seg, e_seg) in enumerate(zip(actual, expected)):
        for key in ("start", "end"):
            a_pt = a_seg[key]
            e_pt = e_seg[key]
            assert a_pt["branchId"] == e_pt["branchId"], (
                f"segment {i} {key} branchId mismatch"
            )
            assert a_pt["vadoseFlag"] == e_pt["vadoseFlag"], (
                f"segment {i} {key} vadoseFlag mismatch"
            )
            for field in ("x", "y", "z", "cost", "equivalentRadius"):
                assert isclose(a_pt[field], e_pt[field], rel_tol=1e-3), (
                    f"segment {i} {key}.{field}: {a_pt[field]} != {e_pt[field]}"
                )
