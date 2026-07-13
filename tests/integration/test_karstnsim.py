import importlib.util
import json

import pytest

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
    karstnsim_data_adapter,
):
    from geocruncher.karstnsim.simulation import run_karstnsim

    data = karstnsim_data_adapter.validate_python(karstnsim_data_dict)

    return run_karstnsim(
        data,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    )


class TestKarstNSimOutput:
    def test_returns_bytes(self, simulation_result):
        assert simulation_result

        assert isinstance(simulation_result, bytes)

    def test_invalid_spring_raises_value_error(
        self,
        karstnsim_data_dict,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
        karstnsim_data_adapter,
    ):
        from geocruncher.karstnsim.simulation import run_karstnsim

        broken = karstnsim_data_adapter.validate_python(
            {**karstnsim_data_dict, "gwbs": []}
        )

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

        assert actual == expected
