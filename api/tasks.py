import json
from collections import defaultdict

from celery import Task

from geocruncher import computations
from geocruncher.contracts import (
    IntersectionsData,
    MeshesData,
    Spring,
    TunnelMeshesData,
)
from geocruncher.profiler import ProfilerMetadata
from geocruncher.profiler.profiler import set_current_task

from .celery import app
from .redis import redis_client as r
from .utils import get_and_delete, get_hash_bytes, hset_bytes


@app.task(bind=True)
def compute_tunnel_meshes(
    self: Task,
    data: TunnelMeshesData,
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
    data: MeshesData,
    model_key: str,
    dem_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    model_data = get_and_delete(r, model_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    generated_meshes = computations.compute_meshes(data, model_data, dem, metadata)

    # write unit files
    for unit_uuid, mesh in generated_meshes["mesh"].items():
        field = f"unit_{unit_uuid}"
        hset_bytes(r, output_key, field, mesh)

    # write fault files
    for name, mesh in generated_meshes["fault"].items():
        field = f"fault_{name}"
        hset_bytes(r, output_key, field, mesh)
    return output_key


@app.task(bind=True)
def compute_intersections(
    self: Task,
    data: IntersectionsData,
    model_key: str,
    dem_key: str,
    gwb_meshes_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    model_data = get_and_delete(r, model_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    gwb_meshes = defaultdict(list)
    if "springs" in data or "drillholes" in data:
        gwb = get_hash_bytes(r, gwb_meshes_key)
        for name, mesh in gwb.items():
            # Syntax: f"{id}_{subID}"
            gwb_id = name.decode("utf-8").split("_")[0]
            gwb_meshes[gwb_id].append(mesh)
        r.delete(gwb_meshes_key)

    outputs = computations.compute_intersections(
        data, model_data, dem, gwb_meshes, metadata
    )

    r.set(output_key, json.dumps(outputs, separators=(",", ":")))
    return output_key


@app.task(bind=True)
def compute_faults(
    self: Task,
    data: MeshesData,
    model_key: str,
    dem_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    model_data = get_and_delete(r, model_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    generated_meshes = computations.compute_faults(data, model_data, dem, metadata)

    # write fault files
    for name, mesh in generated_meshes["fault"].items():
        field = f"fault_{name}"
        hset_bytes(r, output_key, field, mesh)
    return output_key


@app.task(bind=True)
def compute_voxels(
    self: Task,
    data: MeshesData,
    model_key: str,
    dem_key: str,
    gwb_meshes_key: str,
    output_key: str,
    metadata: ProfilerMetadata | None = None,
) -> str:
    set_current_task(self)
    model_data = get_and_delete(r, model_key)
    dem = get_and_delete(r, dem_key).decode("utf-8")

    gwb_meshes = defaultdict(list)
    gwb = get_hash_bytes(r, gwb_meshes_key)
    for name, mesh in gwb.items():
        gwb_id = name.decode("utf-8").split("_")[0]  # Syntax: f"{id}_{subID}"
        gwb_meshes[gwb_id].append(mesh)
    r.delete(gwb_meshes_key)

    voxels = computations.compute_voxels(data, model_data, dem, gwb_meshes, metadata)

    r.set(output_key, voxels)
    return output_key


@app.task(bind=True)
def compute_gwb_meshes(
    self: Task,
    data: list[Spring],
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
