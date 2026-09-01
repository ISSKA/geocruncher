"""
GeoAlgo is a set of C++ algorithms that enable the computation of ground water body meshes
"""

import PyGeoAlgo as ga

from geocruncher.contracts.computations import GwbMeshesResult

from .contracts import GeoAlgoOutput, Spring
from .profiler import profile_step, start_step


class GeoAlgo:
    @staticmethod
    def output(unit_meshes: dict[str, bytes], springs: list[Spring]) -> GeoAlgoOutput:
        start_step("load_mesh")
        s = [
            ga.Spring(
                spring["id"],
                ga.Point_3(
                    spring["location"]["x"],
                    spring["location"]["y"],
                    spring["location"]["z"],
                ),
                spring["unit_id"],
            )
            for spring in springs
        ]

        m = [
            ga.UnitMesh(ga.FileIO.load_from_bytes(mesh), int(unit_id))
            for unit_id, mesh in unit_meshes.items()
        ]
        profile_step("load_mesh")

        start_step("compute")
        aquifer_calc = ga.AquiferCalc(m, s)
        aquifers = aquifer_calc.calculate()
        profile_step("compute")

        start_step("generate_mesh")
        metadata: list[GwbMeshesResult] = []
        meshes = []
        for aquifer in aquifers:
            metadata.append(
                {
                    "unit_id": aquifer.unit_id,
                    "spring_id": aquifer.spring.id,
                    "volume": aquifer.volume,
                }
            )
            meshes.append(ga.FileIO.write_to_bytes(aquifer.mesh))

        profile_step("generate_mesh")
        return {"metadata": metadata, "meshes": meshes}
