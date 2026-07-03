import json
from collections import defaultdict

from celery import Task

from geocruncher import computation_models, computations
from geocruncher.karstnsim.models import KarstNSimData
from geocruncher.karstnsim.simulation import run_karstnsim
from geocruncher.profiler import ProfilerMetadata
from geocruncher.profiler.profiler import set_current_task

from .celery import app
from .redis import redis_client as r
from .utils import get_and_delete, get_hash_bytes, hset_bytes


@app.task(bind=True)
def compute_tunnel_meshes(
    self: Task,
    data: computation_models.TunnelMeshesData,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    meshes = computations.compute_tunnel_meshes(data, metadata)
    for field, value in meshes.items():
        hset_bytes(r, output_key, field, value)
    return output_key


@app.task(bind=True)
def compute_meshes(
    self: Task,
    data: computation_models.MeshesData,
    xml_key: str,
    dem_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    generated_meshes = computations.compute_meshes(data, xml, dem, metadata)

    # write unit files
    for rank, mesh in generated_meshes["mesh"].items():
        field = f"rank_{rank}"
        hset_bytes(r, output_key, field, mesh)

    # write fault files
    for name, mesh in generated_meshes["fault"].items():
        field = f"fault_{name}"
        hset_bytes(r, output_key, field, mesh)
    return output_key


@app.task(bind=True)
def compute_intersections(
    self: Task,
    data: computation_models.IntersectionsData,
    xml_key: str,
    dem_key: str,
    gwb_meshes_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    gwb_meshes = defaultdict(list)
    if "springs" in data or "drillholes" in data:
        gwb = get_hash_bytes(r, gwb_meshes_key)
        for name, mesh in gwb.items():
            # Syntax: f"{id}_{subID}"
            gwb_id = name.decode("utf-8").split("_")[0]
            gwb_meshes[gwb_id].append(mesh)
        r.delete(gwb_meshes_key)

    outputs = computations.compute_intersections(data, xml, dem, gwb_meshes, metadata)

    r.set(output_key, json.dumps(outputs, separators=(",", ":")))
    return output_key


@app.task(bind=True)
def compute_faults(
    self: Task,
    data: computation_models.MeshesData,
    xml_key: str,
    dem_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    generated_meshes = computations.compute_faults(data, xml, dem, metadata)

    # write fault files
    for name, mesh in generated_meshes["fault"].items():
        field = f"fault_{name}"
        hset_bytes(r, output_key, field, mesh)
    return output_key


@app.task(bind=True)
def compute_voxels(
    self: Task,
    data: computation_models.MeshesData,
    xml_key: str,
    dem_key: str,
    gwb_meshes_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    gwb_meshes = defaultdict(list)
    gwb = get_hash_bytes(r, gwb_meshes_key)
    for name, mesh in gwb.items():
        gwb_id = name.decode("utf-8").split("_")[0]  # Syntax: f"{id}_{subID}"
        gwb_meshes[gwb_id].append(mesh)
    r.delete(gwb_meshes_key)

    voxels = computations.compute_voxels(data, xml, dem, gwb_meshes, metadata)

    r.set(output_key, voxels)
    return output_key


@app.task(bind=True)
def compute_gwb_meshes(
    self: Task,
    data: list[computation_models.Spring],
    meshes_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    # get existing meshes for groundwater bodies
    unit_meshes: dict[str, bytes] = {}
    stored = get_hash_bytes(r, meshes_key)
    for unit_id, mesh in stored.items():
        unit_meshes[unit_id.decode("utf-8")] = mesh
    r.delete(meshes_key)

    results = computations.compute_gwb_meshes(unit_meshes, data, metadata)

    # write metadata
    r.hset(
        output_key, "metadata", json.dumps(results["metadata"], separators=(",", ":"))
    )

    # write gwb files
    for id, mesh in enumerate(results["meshes"]):
        hset_bytes(r, output_key, f"mesh_{id}", mesh)

    return output_key


@app.task(bind=True)
def compute_karstnsim(
    self: Task,
    data: KarstNSimData,
    files_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    stored = get_hash_bytes(r, files_key)
    r.delete(files_key)

    dem_bytes = stored[b"dem"]
    voxels_str = stored[b"voxels"].decode("utf-8")
    fault_bytes = {
        int(k.decode().split("_")[1]): v
        for k, v in stored.items()
        if k.startswith(b"fault_")
    }

    result_bytes = run_karstnsim(data, dem_bytes, voxels_str, fault_bytes, metadata)
    r.set(output_key, result_bytes)
    return output_key
