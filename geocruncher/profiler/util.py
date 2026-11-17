from collections.abc import Mapping
from typing import Any, NamedTuple

from forgeo.gmlib.GeologicalModel3D import GeologicalModel

from geocruncher.contracts.computations import EvaluationExtent

type ProfilerMetadata = Mapping[str, Any]


class VkProfilerSettings(NamedTuple):
    # version of the profiler
    version: int
    # name of the type of computation
    computation: str
    # list of names of the steps to record
    steps: list[str]


class MetadataHelpers:
    """Static functions that help gather metadata for the profiling"""

    @staticmethod
    def num_erode_series(model: GeologicalModel) -> int:
        return len([s for s in model.pile.all_series if s.relation == "erode"])

    @staticmethod
    def num_onlap_series(model: GeologicalModel) -> int:
        return len([s for s in model.pile.all_series if s.relation == "onlap"])

    @staticmethod
    def num_units(model: GeologicalModel) -> int:
        # remove 1 from nbformations because it always includes the dummy
        return model.nbformations() - 1

    @staticmethod
    def num_finite_faults(model: GeologicalModel) -> int:
        return len([x for name, x in model.faults_data.items() if not x.infinite])

    @staticmethod
    def num_infinite_faults(model: GeologicalModel) -> int:
        return len([x for name, x in model.faults_data.items() if x.infinite])

    @staticmethod
    def num_stops_on_relations(model: GeologicalModel) -> int:
        return sum([len(x.stops_on) for name, x in model.faults_data.items()])

    @staticmethod
    def num_contact_data(model: GeologicalModel, unit=True, fault=True) -> int:
        num_unit_contact_data = 0
        num_fault_contact_data = 0
        if unit:
            # divide interfaces by 2, because they are lines made of 2 points
            num_unit_contact_data = (
                len(
                    [
                        a
                        for s in model.pile.all_series
                        if s.potential_data is not None
                        for i in s.potential_data.interfaces
                        for a in i
                    ]
                )
                // 2
            )
        if fault:
            num_fault_contact_data = (
                len(
                    [
                        a
                        for f in model.faults_data.values()
                        if f.potential_data is not None
                        for i in f.potential_data.interfaces
                        for a in i
                    ]
                )
                // 2
            )

        return num_unit_contact_data + num_fault_contact_data

    @staticmethod
    def num_dips(model: GeologicalModel, unit=True, fault=True) -> int:
        num_unit_dips = 0
        num_fault_dips = 0
        if unit:
            num_unit_dips = len(
                [
                    loc
                    for s in model.pile.all_series
                    if s.potential_data is not None
                    for loc in s.potential_data.gradients.locations
                ]
            )
        if fault:
            num_fault_dips = len(
                [
                    loc
                    for f in model.faults_data.values()
                    if f.potential_data is not None
                    for loc in f.potential_data.gradients.locations
                ]
            )

        return num_unit_dips + num_fault_dips

    @staticmethod
    def num_fault_unit_pairs(model: GeologicalModel) -> int:
        return sum(
            len(series.formations) * len(series.influenced_by_fault or [])
            for series in model.pile.all_series
        )

    @staticmethod
    def box_size(box: EvaluationExtent) -> dict[str, float]:
        size_x = box["xmax"] - box["xmin"]
        size_y = box["ymax"] - box["ymin"]
        size_z = box["zmax"] - box["zmin"]
        return {
            "box_size_x": size_x,
            "box_size_y": size_y,
            "box_size_z": size_z,
            "box_volume": size_x * size_y * size_z,
        }

    @staticmethod
    def grid_resolution(shape: tuple[int, int, int]) -> dict[str, int]:
        return {
            "resolution_x": shape[0],
            "resolution_y": shape[1],
            "resolution_z": shape[2],
            "resolution": shape[0] * shape[1] * shape[2],
        }

    @staticmethod
    def mesh_bytes(
        meshes: dict[str, bytes] | dict[str, list[bytes]],
    ) -> dict[str, int]:
        sizes = [
            len(mesh)
            for mesh_or_meshes in meshes.values()
            for mesh in (
                mesh_or_meshes if isinstance(mesh_or_meshes, list) else [mesh_or_meshes]
            )
        ]
        return {
            "total_mesh_bytes": sum(sizes),
            "mesh_bytes_per_unit": sum(sizes) // len(meshes) if meshes else 0,
        }
