"""
GeoAlgo is a set of C++ algorithms that enable the computation of ground water body meshes
"""
from typing import TypedDict
import PyGeoAlgo as ga

from .profiler.profiler import get_current_profiler

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
        get_current_profiler().profile('load_off')

        aquifer_calc = ga.AquiferCalc(m, s)
        aquifers = aquifer_calc.calculate()
        get_current_profiler().profile('compute')

        metadata = []
        meshes = []
        for aquifer in aquifers:
            metadata.append({
                "unit_id": aquifer.unit_id,
                "spring_id": aquifer.spring.id,
                "volume": aquifer.volume
            })
            meshes.append(ga.FileIO.write_to_bytes(aquifer.mesh))

        get_current_profiler().profile('generate_off')
        return {"metadata": metadata, "meshes": meshes}
