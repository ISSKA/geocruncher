"""
GeoAlgo is a set of C++ algorithms that enable the computation of ground water body meshes
"""
from typing import TypedDict
import PyGeoAlgo as ga

from .profiler import profile_step

class GwbMeshesResult(TypedDict):
    """Data returned by the gwb meshes computation"""
    unit_id: int
    """Geological Model Unit ID"""
    spring_id: int
    """Point of interest ID"""
    volume: float
    """Volume of the mesh"""

class GeoAlgoOutput(TypedDict):
    """Data returned by the GeoAlgo output"""
    metadata: list[GwbMeshesResult]
    meshes: list[bytes]

class GeoAlgo:
    @staticmethod
    def output(unit_meshes: dict[str, bytes], springs: list) -> GeoAlgoOutput:
        s = [ga.Spring(spring['id'], ga.Point_3(spring['location']['x'], spring['location']['y'],
                                                spring['location']['z']), spring['unit_id']) for spring in springs]

        m = [ga.UnitMesh(ga.FileIO.load_from_bytes(
            mesh), int(unit_id)) for unit_id, mesh in unit_meshes.items()]
        profile_step('load_mesh')

        aquifer_calc = ga.AquiferCalc(m, s)
        aquifers = aquifer_calc.calculate()
        profile_step('compute')

        metadata = []
        meshes = []
        for aquifer in aquifers:
            metadata.append({
                "unit_id": aquifer.unit_id,
                "spring_id": aquifer.spring.id,
                "volume": aquifer.volume
            })
            meshes.append(ga.FileIO.write_to_bytes(aquifer.mesh))

        profile_step("generate_mesh")
        return {"metadata": metadata, "meshes": meshes}
