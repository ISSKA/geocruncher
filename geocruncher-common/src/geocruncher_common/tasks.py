"""Celery tasks for geocruncher computations.
This is a stub file. The real implementation is in the geocruncher-worker package.
This file exists so that the API doesn't depend on any of the worker specific dependencies.
This should be kept in sync with the real implementation in geocruncher-worker.
"""

from geocruncher_common.celery_app import app
from geocruncher_common.models import (
    TunnelMeshesData,
    MeshesData,
    IntersectionsData,
    Spring,
)


class StubException(Exception):
    def __init__(self):
        super().__init__(
            "This is a stub file. The real implementation is in the geocruncher-worker package. This method should never be called directly, use .delay() instead!"
        )


@app.task(name="geocruncher.compute.tunnel_meshes")
def compute_tunnel_meshes(data: TunnelMeshesData, output_key: str) -> str:
    raise StubException()


@app.task(name="geocruncher.compute.meshes")
def compute_meshes(
    data: MeshesData, xml_key: str, dem_key: str, output_key: str
) -> str:
    raise StubException()


@app.task(name="geocruncher.compute.intersections")
def compute_intersections(
    data: IntersectionsData,
    xml_key: str,
    dem_key: str,
    gwb_meshes_key: str,
    output_key: str,
) -> str:
    raise StubException()


@app.task(name="geocruncher.compute.faults")
def compute_faults(
    data: MeshesData, xml_key: str, dem_key: str, output_key: str
) -> str:
    raise StubException()


@app.task(name="geocruncher.compute.voxels")
def compute_voxels(
    data: MeshesData, xml_key: str, dem_key: str, gwb_meshes_key: str, output_key: str
) -> str:
    raise StubException()


@app.task(name="geocruncher.compute.gwb_meshes")
def compute_gwb_meshes(data: list[Spring], meshes_key: str, output_key: str) -> str:
    raise StubException()
