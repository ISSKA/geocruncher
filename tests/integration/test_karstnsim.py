import importlib.util
import json
from math import isclose

import pytest

from geocruncher.karstnsim.models import KarstNSimData

pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("pykarstnsim"),
    reason="pykarstnsim not installed",
)


@pytest.fixture(scope="module")
def simulation_result(
    karstnsim_data_dict,
    karstnsim_dem_bytes,
    karstnsim_voxels_str,
    karstnsim_fault_bytes,
):
    from geocruncher.karstnsim.simulation import run_karstnsim

    data = KarstNSimData.model_validate(karstnsim_data_dict)

    return run_karstnsim(
        data,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    )


class TestKarstNSimOutput:
    def test_invalid_spring_raises_value_error(
        self,
        karstnsim_data_dict,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    ):
        from geocruncher.karstnsim.simulation import run_karstnsim

        broken = KarstNSimData.model_validate({**karstnsim_data_dict, "gwbs": []})

        with pytest.raises(ValueError, match="groundwater body"):
            run_karstnsim(
                broken,
                karstnsim_dem_bytes,
                karstnsim_voxels_str,
                karstnsim_fault_bytes,
            )

    def test_matches_control_output(self, simulation_result, control_output):
        actual = json.loads(simulation_result)
        expected = json.loads(control_output)

        assert len(actual["segments"]) == len(expected["segments"])

        for i, (a_seg, e_seg) in enumerate(
            zip(actual["segments"], expected["segments"])
        ):
            for key in ("start", "end"):
                a_pt = a_seg[key]
                e_pt = e_seg[key]
                assert a_pt["branch_id"] == e_pt["branch_id"], (
                    f"segment {i} {key} branch_id mismatch"
                )
                assert a_pt["vadose_flag"] == e_pt["vadose_flag"], (
                    f"segment {i} {key} vadose_flag mismatch"
                )
                for field in ("x", "y", "z", "cost", "equivalent_radius"):
                    assert isclose(a_pt[field], e_pt[field], rel_tol=1e-3), (
                        f"segment {i} {key}.{field}: {a_pt[field]} != {e_pt[field]}"
                    )
