import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import KARSTNSIM_DATA_ZIP


@pytest.fixture(scope="session")
def control_zip():
    with zipfile.ZipFile(KARSTNSIM_DATA_ZIP, "r") as zf:
        yield zf


@pytest.fixture(scope="session")
def control_output():
    return (
        Path(__file__).parent.parent / "fixtures" / "control_output.txt"
    ).read_text()


def _read(zf: zipfile.ZipFile, filename: str) -> bytes:
    return zf.read(filename)


def _read_text(zf: zipfile.ZipFile, filename: str) -> str:
    return zf.read(filename).decode("utf-8")


@dataclass(frozen=True)
class DummyProject:
    """Direct computation inputs: XML bytes and decoded DEM text.

    API smoke tests use ``fixture_bytes`` for multipart uploads; the API task
    layer decodes DEM bytes before calling the computation functions.
    """

    xml: bytes
    dem: str


@pytest.fixture(scope="module")
def computations():
    pytest.importorskip("DracoPy")
    pytest.importorskip("PyGeoAlgo")
    pytest.importorskip("forgeo")
    pytest.importorskip("pyvista")
    return pytest.importorskip("geocruncher.computations")


@pytest.fixture(scope="module")
def mesh_io():
    return pytest.importorskip("geocruncher.mesh_io.mesh_io")


@pytest.fixture(scope="module")
def dummy_project_dir():
    return Path(__file__).resolve().parents[1] / "fixtures" / "dummy_project"


@pytest.fixture(scope="module")
def dummy_project(dummy_project_dir):
    return DummyProject(
        xml=dummy_project_dir.joinpath("geocruncher_project.xml").read_bytes(),
        dem=dummy_project_dir.joinpath("geocruncher_dem.asc").read_text(),
    )


@pytest.fixture
def fixture_json(dummy_project_dir):
    def load(name):
        return json.loads(dummy_project_dir.joinpath(name).read_text())

    return load


@pytest.fixture
def fixture_bytes(dummy_project_dir):
    def load(name):
        return dummy_project_dir.joinpath(name).read_bytes()

    return load


@pytest.fixture
def fixture_text(dummy_project_dir):
    def load(name):
        return dummy_project_dir.joinpath(name).read_text()

    return load


@pytest.fixture
def decode_meshes(mesh_io):
    def decode(meshes):
        summaries = {}
        for name, data in meshes.items():
            assert isinstance(data, bytes)
            polydata = mesh_io.read_mesh_to_polydata(data)
            assert polydata.n_points > 0
            assert polydata.n_cells > 0
            assert np.isfinite(polydata.bounds).all()
            summaries[name] = (polydata.n_points, polydata.n_cells)
        return summaries

    return decode


######## Fault binary to OFF conversion ########


def fault_bin_to_off(bin_bytes: bytes) -> bytes:
    """Convert the Angular custom binary fault format to OFF bytes."""
    offset = 0
    n_verts = struct.unpack_from("<i", bin_bytes, offset)[0]
    offset += 4

    verts = []
    for _ in range(n_verts):
        x, y, z = struct.unpack_from("<fff", bin_bytes, offset)
        offset += 12
        verts.append((x, y, z))

    n_tris = struct.unpack_from("<i", bin_bytes, offset)[0]
    offset += 4

    tris = []
    for _ in range(n_tris):
        a, b, c = struct.unpack_from("<iii", bin_bytes, offset)
        offset += 12
        tris.append((a, b, c))

    lines = ["OFF", f"{n_verts} {n_tris} 0"]
    lines.extend(f"{x} {y} {z}" for x, y, z in verts)
    lines.extend(f"3 {a} {b} {c}" for a, b, c in tris)

    return "\n".join(lines).encode("utf-8")


######## Raw file fixtures ########


@pytest.fixture(scope="session")
def karstnsim_dem_bytes(control_zip) -> bytes:
    return _read(control_zip, "dem_values.bin")


@pytest.fixture(scope="session")
def karstnsim_voxels_str(control_zip) -> str:
    return _read_text(control_zip, "voxels.txt")


@pytest.fixture(scope="session")
def karstnsim_fault_bytes(control_zip) -> dict[int, bytes]:
    """Dict of fault_id -> OFF bytes."""
    result = {}

    for name in sorted(control_zip.namelist()):
        if name.startswith("fault_") and name.endswith(".bin"):
            fault_id = int(Path(name).stem.split("_")[1])
            result[fault_id] = fault_bin_to_off(_read(control_zip, name))

    assert result, "No fault_*.bin files found in zip"
    return result


@pytest.fixture(scope="session")
def karstnsim_data_dict(control_zip, karstnsim_voxels_str) -> dict:
    """The JSON body that Spring would POST to /compute/karstnsim."""

    config = json.loads(_read_text(control_zip, "config.json"))
    project_box = json.loads(_read_text(control_zip, "project_box.json"))
    dem_res = json.loads(_read_text(control_zip, "dem_resolution.json"))
    stratigraphy = json.loads(_read_text(control_zip, "stratigraphy.json"))
    vox_units = json.loads(_read_text(control_zip, "voxels_units.json"))

    # Parse voxels header
    header_line = karstnsim_voxels_str.splitlines()[0]
    parts = dict(p.split("=") for p in header_line.split())

    voxels_header = {
        "xmin": float(parts["XMIN"]),
        "xmax": float(parts["XMAX"]),
        "ymin": float(parts["YMIN"]),
        "ymax": float(parts["YMAX"]),
        "zmin": float(parts["ZMIN"]),
        "zmax": float(parts["ZMAX"]),
        "nx": int(parts["NUMBERX"]),
        "ny": int(parts["NUMBERY"]),
        "nz": int(parts["NUMBERZ"]),
        "novalue": int(parts["NOVALUE"]),
    }

    gwbs = [
        json.loads(_read_text(control_zip, name))
        for name in sorted(control_zip.namelist())
        if name.startswith("gwb_") and name.endswith(".json")
    ]

    springs = [
        json.loads(_read_text(control_zip, name))
        for name in sorted(control_zip.namelist())
        if name.startswith("poi_") and name.endswith(".json")
    ]

    fault_ids = [
        int(Path(name).stem.split("_")[1])
        for name in sorted(control_zip.namelist())
        if name.startswith("fault_") and name.endswith(".bin")
    ]

    return {
        "simulation_params": config,
        "project_box": project_box,
        "dem_resolution": dem_res,
        "stratigraphy": stratigraphy,
        "voxels_header": voxels_header,
        "voxels_units": vox_units,
        "fault_ids": fault_ids,
        "springs": springs,
        "gwbs": gwbs,
    }
