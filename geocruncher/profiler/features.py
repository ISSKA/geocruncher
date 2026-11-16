"""Build profiler features from computation inputs."""

from collections.abc import Mapping

from isska.geocruncher.v1 import project_pb as project_proto

from geocruncher.profiler.util import MetadataHelpers


def select_features(
    computation_type: str, factors: dict, feature_names: list[str]
) -> dict:
    return {
        "computation_type": computation_type,
        **{name: factors[name] for name in feature_names},
    }


def add_request_features(
    factors: dict, computation_type: str, data: Mapping, gwb_part_count: int
) -> None:
    if computation_type in {"meshes", "faults", "voxels"}:
        resolution = data["resolution"]
        factors.update(
            {
                "resolution_x": resolution["x"],
                "resolution_y": resolution["y"],
                "resolution_z": resolution["z"],
                "resolution": resolution["x"] * resolution["y"] * resolution["z"],
            }
        )
    if computation_type in {"meshes", "faults", "voxels", "intersections"}:
        factors.update(MetadataHelpers.box_size(data["box"]))
    if computation_type == "voxels":
        factors["num_gwb_parts"] = gwb_part_count
    if computation_type == "intersections":
        factors.update(
            {
                "num_gwb_parts": gwb_part_count,
                "compute_map": data["computeMap"],
                "num_springs": len(data.get("springs") or {}),
                "num_drillholes": len(data.get("drillholes") or {}),
                "num_sections": len(data["toCompute"]),
            }
        )


def protobuf_model_factors(
    computation_type: str,
    data: Mapping,
    model: project_proto.GeologicalModel,
    gwb_part_count: int,
    feature_names: list[str],
) -> dict:
    series = list(model.stratigraphy.series) if model.stratigraphy is not None else []
    faults = list(model.faults)
    finite_faults = sum(fault.has_field("finite") for fault in faults)
    factors = {
        "num_units": sum(len(series_item.units) for series_item in series),
        "num_fault_unit_pairs": sum(
            len(series_item.units) * len(series_item.influenced_by_faults)
            for series_item in series
        ),
        "num_infinite_faults": len(faults) - finite_faults,
        "num_finite_faults": finite_faults,
        "num_dips": sum(
            len(unit.orientations)
            for series_item in series
            for unit in series_item.units
        )
        + sum(len(fault.orientations) for fault in faults),
        "num_contact_data": (
            sum(
                len(unit.contact_points)
                for series_item in series
                for unit in series_item.units
            )
            + sum(len(fault.contact_points) for fault in faults)
        )
        // 2,
        "num_stops_on_relations": sum(len(fault.stops_on) for fault in faults),
        "num_erode_series": sum(
            series_item.relation == project_proto.SeriesRelation.ERODE
            for series_item in series
        ),
        "num_onlap_series": sum(
            series_item.relation == project_proto.SeriesRelation.ONLAP
            for series_item in series
        ),
    }
    if computation_type == "faults":
        factors["num_dips"] = sum(len(fault.orientations) for fault in faults)
        factors["num_contact_data"] = (
            sum(len(fault.contact_points) for fault in faults) // 2
        )
    add_request_features(factors, computation_type, data, gwb_part_count)
    return select_features(computation_type, factors, feature_names)
