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
):
    from geocruncher.computations import KarstNSimData
    from geocruncher.karstnsim.simulation import run_karstnsim

    data = KarstNSimData.model_validate(karstnsim_data_dict)

    return run_karstnsim(
        data,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    )


class TestKarstNSimOutput:
    def test_returns_bytes(self, simulation_result, tmp_path):
        assert simulation_result

        assert isinstance(simulation_result, bytes)
        (tmp_path / "output.txt").write_bytes(simulation_result)

    def test_output_structure(self, simulation_result):
        text = simulation_result.decode()

        assert "# Run info" in text
        assert "# Data" in text

    def test_output_metadata_json(
        self,
        simulation_result,
        karstnsim_voxels_str,
    ):
        from geocruncher.karstnsim.input import load_voxels

        text = simulation_result.decode()
        info = text.split("# Run info\n")[1].split("\n# Data")[0]
        parsed = json.loads(info)

        metadata = parsed["metadata"]

        assert "config" in parsed
        assert metadata["generationDurationS"] > 0
        assert "generationTime" in metadata

        header, _ = load_voxels(karstnsim_voxels_str.splitlines())
        assert metadata["computeResolution"] == {
            "x": header.nx,
            "y": header.ny,
            "z": header.nz,
        }

    def test_invalid_spring_raises_value_error(
        self,
        karstnsim_data_dict,
        karstnsim_dem_bytes,
        karstnsim_voxels_str,
        karstnsim_fault_bytes,
    ):
        from geocruncher.computations import KarstNSimData
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
        text = simulation_result.decode()

        actual_run_info, actual_data = text.split("\n# Data\n", maxsplit=1)
        expected_run_info, expected_data = control_output.split(
            "\n# Data\n", maxsplit=1
        )

        actual = json.loads(actual_run_info.split("# Run info\n", maxsplit=1)[1])
        expected = json.loads(expected_run_info.split("# Run info\n", maxsplit=1)[1])

        actual["metadata"]["generationTime"] = "<generationTime>"
        actual["metadata"]["generationDurationS"] = "<generationDurationS>"

        assert actual == expected
        assert actual_data.rstrip("\n") == expected_data.rstrip("\n")
