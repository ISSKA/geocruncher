"""
GeoAlgo is a set of C++ algorithms that enable the computation of ground water body meshes
"""
import PyGeoAlgo as ga

from .profiler.profiler import get_current_profiler


class GeoAlgo:
    @staticmethod
    def output(unit_meshes: list, springs: list) -> list:
        s = [ga.Spring(spring.id, ga.Point_3(spring.location.x, spring.location.y,
                                             spring.location.z), spring.unit_id) for spring in springs]
        m = [ga.UnitMesh(ga.FileIO.load_off_from_string(
            mesh.mesh), mesh.unit_id) for mesh in unit_meshes]
        get_current_profiler().profile('load_off')

        aquifer_calc = ga.AquiferCalc(m, s)
        aquifers = aquifer_calc.calculate()
        get_current_profiler().profile('compute')

        output = [{"mesh": ga.FileIO.write_off_to_string(aquifer.mesh), "unit_id": aquifer.unit_id,
                   "spring_id": aquifer.spring.id, "volume": aquifer.volume} for aquifer in aquifers]
        get_current_profiler().profile('generate_off')
        return output
