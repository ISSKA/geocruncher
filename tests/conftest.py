import json
import os
import struct
import zipfile
from pathlib import Path

import pytest

os.environ.setdefault("REDIS_HOST", "localhost")

TESTS_DIR = Path(__file__).parent

KARSTNSIM_DATA_ZIP = Path(
    os.environ.get(
        "KARSTNSIM_DATA_ZIP",
        TESTS_DIR / "fixtures" / "control_project.zip",
    )
)


@pytest.fixture(scope="session")
def karstnsim_zip():
    with zipfile.ZipFile(KARSTNSIM_DATA_ZIP, "r") as zf:
        yield zf


def _read(zf: zipfile.ZipFile, filename: str) -> bytes:
    return zf.read(filename)


def _read_text(zf: zipfile.ZipFile, filename: str) -> str:
    return zf.read(filename).decode("utf-8")


@pytest.fixture(autouse=True)
def reset_progress_recorder_task():
    import geocruncher.profiler.profiler as profiler_module

    # Reset the profiler manager and progress recorder before and after each test
    profiler_module._profiler_manager._current_profiler = None
    profiler_module._progress_recorder.task = None
    yield
    profiler_module._profiler_manager._current_profiler = None
    profiler_module._progress_recorder.task = None


@pytest.fixture(scope="session")
def karstnsim_data_adapter():
    from pydantic import TypeAdapter

    from geocruncher.karstnsim.models import KarstNSimData

    return TypeAdapter(KarstNSimData)


# ---------------------------------------------------------------------------
# Fault binary → OFF conversion
# ---------------------------------------------------------------------------


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
def karstnsim_dem_bytes(karstnsim_zip) -> bytes:
    return _read(karstnsim_zip, "dem_values.bin")


@pytest.fixture(scope="session")
def karstnsim_voxels_str(karstnsim_zip) -> str:
    return _read_text(karstnsim_zip, "voxels.txt")


@pytest.fixture(scope="session")
def karstnsim_fault_bytes(karstnsim_zip) -> dict[int, bytes]:
    """Dict of fault_id -> OFF bytes."""
    result = {}

    for name in sorted(karstnsim_zip.namelist()):
        if name.startswith("fault_") and name.endswith(".bin"):
            fault_id = int(Path(name).stem.split("_")[1])
            result[fault_id] = _read(karstnsim_zip, name)

    assert result, "No fault_*.bin files found in zip"
    return result


@pytest.fixture(scope="session")
def karstnsim_data_dict(karstnsim_zip, karstnsim_voxels_str) -> dict:
    """The JSON body that Spring would POST to /compute/karstnsim."""

    config = json.loads(_read_text(karstnsim_zip, "config.json"))
    project_box = json.loads(_read_text(karstnsim_zip, "project_box.json"))
    dem_res = json.loads(_read_text(karstnsim_zip, "dem_resolution.json"))
    stratigraphy = json.loads(_read_text(karstnsim_zip, "stratigraphy.json"))
    vox_units = json.loads(_read_text(karstnsim_zip, "voxels_units.json"))

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
        json.loads(_read_text(karstnsim_zip, name))
        for name in sorted(karstnsim_zip.namelist())
        if name.startswith("gwb_") and name.endswith(".json")
    ]

    springs = [
        json.loads(_read_text(karstnsim_zip, name))
        for name in sorted(karstnsim_zip.namelist())
        if name.startswith("poi_") and name.endswith(".json")
    ]

    fault_ids = [
        int(Path(name).stem.split("_")[1])
        for name in sorted(karstnsim_zip.namelist())
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
