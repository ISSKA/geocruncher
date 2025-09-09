import typing
import celery
from geocruncher_common.celery_app import app
from geocruncher_common.models import TunnelMeshesData, MeshesData, IntersectionsData, Spring

class StubException(Exception):
    def __init__(self):
        super().__init__("This is a stub file. The real implementation is in the geocruncher-worker package. This method should never be called directly.")

@app.task
def compute_tunnel_meshes(data: TunnelMeshesData, output_key: str) -> str:
    raise StubException()


@app.task
def compute_meshes(data: MeshesData, xml_key: str, dem_key: str, output_key: str) -> str:
    raise StubException()


@app.task
def compute_intersections(data: IntersectionsData, xml_key: str, dem_key: str, gwb_meshes_key: str, output_key: str) -> str:
    raise StubException()


@app.task
def compute_faults(data: MeshesData, xml_key: str, dem_key: str, output_key: str) -> str:
    raise StubException()


@app.task
def compute_voxels(data: MeshesData, xml_key: str, dem_key: str, gwb_meshes_key: str, output_key: str) -> str:
    raise StubException()

@app.task
def compute_gwb_meshes(data: list[Spring], meshes_key: str, output_key: str) -> str:
    raise StubException()
