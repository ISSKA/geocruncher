"""
GeoAlgo is a set of C++ algorithms that enable the computation of ground water body meshes
"""
import PyGeoAlgo as ga

from .profiler.profiler import get_current_profiler


class GeoAlgo:
    @staticmethod
    def output(unit_meshes: dict[str, bytes], springs: list) -> tuple[list, dict[str, bytes]]:
        s = [ga.Spring(spring['id'], ga.Point_3(spring['location']['x'], spring['location']['y'],
                                                spring['location']['z']), spring['unit_id']) for spring in springs]

        m = [ga.UnitMesh(ga.FileIO.load_from_bytes(
            mesh), int(unit_id)) for unit_id, mesh in unit_meshes.items()]
        get_current_profiler().profile('load_off')

        aquifer_calc = ga.AquiferCalc(m, s)
        aquifers = aquifer_calc.calculate()
        get_current_profiler().profile('compute')

        metadata = [{"unit_id": aquifer.unit_id, "spring_id": aquifer.spring.id,
                     "volume": aquifer.volume} for aquifer in aquifers]
        meshes = {}
        for aquifer in aquifers:
            meshes[aquifer.unit_id] = ga.FileIO.write_to_bytes(aquifer.mesh)

        get_current_profiler().profile('generate_off')
        return metadata, meshes
