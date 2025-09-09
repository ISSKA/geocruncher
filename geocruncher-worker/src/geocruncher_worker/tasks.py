import json
from collections import defaultdict

import geocruncher_common.models as models
import geocruncher_worker.computations as computations
from geocruncher_common.celery_app import app
from geocruncher_common.redis import redis_client as r
from geocruncher_common.utils import get_and_delete


@app.task
def compute_tunnel_meshes(data: models.TunnelMeshesData, output_key: str) -> str:
    meshes = computations.compute_tunnel_meshes(data)
    for field, value in meshes.items():
        r.hset(output_key, field, value)
    return output_key


@app.task
def compute_meshes(data: models.MeshesData, xml_key: str, dem_key: str, output_key: str) -> str:
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode('utf-8')

    generated_meshes = computations.compute_meshes(data, xml, dem)

    # write unit files
    for rank, mesh in generated_meshes['mesh'].items():
        field = f"rank_{rank}"
        r.hset(output_key, field, mesh)

    # write fault files
    for name, mesh in generated_meshes['fault'].items():
        field = f"fault_{name}"
        r.hset(output_key, field, mesh)
    return output_key


@app.task
def compute_intersections(data: models.IntersectionsData, xml_key: str, dem_key: str, gwb_meshes_key: str, output_key: str) -> str:
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode('utf-8')

    gwb_meshes = defaultdict(list)
    if 'springs' in data or 'drillholes' in data:
        gwb = r.hgetall(gwb_meshes_key)
        for name, mesh in gwb.items():
            # Syntax: f"{id}_{subID}"
            gwb_id = name.decode('utf-8').split('_')[0]
            gwb_meshes[gwb_id].append(mesh)
        r.delete(gwb_meshes_key)

    outputs = computations.compute_intersections(data, xml, dem, gwb_meshes)

    r.set(output_key, json.dumps(outputs, separators=(',', ':')))
    return output_key


@app.task
def compute_faults(data: models.MeshesData, xml_key: str, dem_key: str, output_key: str) -> str:
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode('utf-8')

    generated_meshes = computations.compute_faults(data, xml, dem)

    # write fault files
    for name, mesh in generated_meshes['fault'].items():
        field = f"fault_{name}"
        r.hset(output_key, field, mesh)
    return output_key


@app.task
def compute_voxels(data: models.MeshesData, xml_key: str, dem_key: str, gwb_meshes_key: str, output_key: str) -> str:
    xml = get_and_delete(r, xml_key)
    dem = get_and_delete(r, dem_key).decode('utf-8')

    gwb_meshes = defaultdict(list)
    gwb = r.hgetall(gwb_meshes_key)
    for name, mesh in gwb.items():
        gwb_id = name.decode('utf-8').split('_')[0]  # Syntax: f"{id}_{subID}"
        gwb_meshes[gwb_id].append(mesh)
    r.delete(gwb_meshes_key)

    voxels = computations.compute_voxels(data, xml, dem, gwb_meshes)

    r.set(output_key, voxels)
    return output_key


@app.task
def compute_gwb_meshes(data: list[models.Spring], meshes_key: str, output_key: str) -> str:

    # get existing meshes for groundwater bodies
    unit_meshes: dict[str, bytes] = {}
    stored = r.hgetall(meshes_key)
    for unit_id, mesh in stored.items():
        unit_meshes[unit_id.decode('utf-8')] = mesh
    r.delete(meshes_key)

    results = computations.compute_gwb_meshes(unit_meshes, data)

    # write metadata
    r.hset(output_key, "metadata", json.dumps(results["metadata"], separators=(',', ':')))

    # write gwb files
    for id, mesh in enumerate(results["meshes"]):
        r.hset(output_key, f"mesh_{id}", mesh)

    return output_key
