"""Parsing and semantic validation for geological model protobuf input."""

from __future__ import annotations

import math
import uuid as uuid_module
from typing import Never

from isska.geocruncher.v1 import project_pb as project_proto


class GeologicalModelValidationError(ValueError):
    """Raised when a protobuf geological model violates the contract."""


NORMAL_LENGTH_TOLERANCE = 1.0e-3
"""Allowed absolute error in exported orientation-normal length."""


def parse_geological_model(data: bytes) -> project_proto.GeologicalModel:
    """Deserialize and validate a binary v1 geological model payload."""
    message = deserialize_geological_model(data)
    validate_geological_model(message)
    return message


def deserialize_geological_model(data: bytes) -> project_proto.GeologicalModel:
    """Deserialize a binary v1 payload without semantic validation."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    try:
        return project_proto.GeologicalModel.from_binary(data)
    except Exception as error:
        raise GeologicalModelValidationError(
            f"invalid GeologicalModel protobuf: {error}"
        ) from error


def validate_geological_model(message: project_proto.GeologicalModel) -> None:
    """Validate a generated v1 geological model message without modifying it."""
    if not message.has_field("stratigraphy"):
        _invalid("stratigraphy", "is required")

    stratigraphy = message.stratigraphy
    assert stratigraphy is not None
    _validate_reference(stratigraphy.reference)

    entity_uuids: set[str] = set()
    for series_index, series in enumerate(stratigraphy.series):
        _validate_series(series, series_index, entity_uuids)
    for fault_index, fault in enumerate(message.faults):
        _validate_fault(fault, fault_index, entity_uuids)

    fault_uuids = {fault.uuid for fault in message.faults}
    for series_index, series in enumerate(stratigraphy.series):
        for reference_index, fault_uuid in enumerate(series.influenced_by_faults):
            _validate_fault_reference(
                fault_uuid,
                fault_uuids,
                f"stratigraphy.series[{series_index}].influenced_by_faults[{reference_index}]",
            )

    for fault_index, fault in enumerate(message.faults):
        for reference_index, stopped_on_uuid in enumerate(fault.stops_on):
            path = f"faults[{fault_index}].stops_on[{reference_index}]"
            _validate_fault_reference(stopped_on_uuid, fault_uuids, path)
            if stopped_on_uuid == fault.uuid:
                _invalid(path, "must not reference the owning fault")

    _validate_stops_on_acyclic(message.faults)


def _validate_reference(reference: project_proto.StratigraphicReference) -> None:
    if reference not in (
        project_proto.StratigraphicReference.BASE,
        project_proto.StratigraphicReference.TOP,
    ):
        _invalid("stratigraphy.reference", "must be BASE or TOP")


def _validate_series(
    series: project_proto.Series,
    index: int,
    entity_uuids: set[str],
) -> None:
    path = f"stratigraphy.series[{index}]"
    _validate_entity_uuid(series.uuid, f"{path}.uuid", entity_uuids)
    _validate_relation(series.relation, f"{path}.relation")
    for unit_index, unit in enumerate(series.units):
        _validate_unit(unit, unit_index, path, entity_uuids)


def _validate_relation(relation: project_proto.SeriesRelation, path: str) -> None:
    if relation not in (
        project_proto.SeriesRelation.ONLAP,
        project_proto.SeriesRelation.ERODE,
    ):
        _invalid(path, "must be ONLAP or ERODE")


def _validate_unit(
    unit: project_proto.Unit,
    index: int,
    series_path: str,
    entity_uuids: set[str],
) -> None:
    path = f"{series_path}.units[{index}]"
    _validate_entity_uuid(unit.uuid, f"{path}.uuid", entity_uuids)
    for point_index, point in enumerate(unit.contact_points):
        _validate_point(point, f"{path}.contact_points[{point_index}]")
    for orientation_index, orientation in enumerate(unit.orientations):
        _validate_orientation(orientation, f"{path}.orientations[{orientation_index}]")


def _validate_fault(
    fault: project_proto.Fault,
    index: int,
    entity_uuids: set[str],
) -> None:
    path = f"faults[{index}]"
    _validate_entity_uuid(fault.uuid, f"{path}.uuid", entity_uuids)
    if not fault.contact_points:
        _invalid(f"{path}.contact_points", "must contain at least one point")
    if not fault.orientations:
        _invalid(f"{path}.orientations", "must contain at least one orientation")

    for point_index, point in enumerate(fault.contact_points):
        _validate_point(point, f"{path}.contact_points[{point_index}]")
    for orientation_index, orientation in enumerate(fault.orientations):
        _validate_orientation(orientation, f"{path}.orientations[{orientation_index}]")

    if fault.has_field("finite"):
        assert fault.finite is not None
        _validate_finite_fault(fault.finite, f"{path}.finite")


def _validate_point(point: project_proto.Point3, path: str) -> None:
    _finite(point.x, f"{path}.x")
    _finite(point.y, f"{path}.y")
    _finite(point.z, f"{path}.z")


def _validate_orientation(orientation: project_proto.Orientation, path: str) -> None:
    if not orientation.has_field("position"):
        _invalid(f"{path}.position", "is required")
    if not orientation.has_field("normal"):
        _invalid(f"{path}.normal", "is required")
    assert orientation.position is not None
    assert orientation.normal is not None

    _validate_point(orientation.position, f"{path}.position")
    normal = orientation.normal
    _finite(normal.x, f"{path}.normal.x")
    _finite(normal.y, f"{path}.normal.y")
    _finite(normal.z, f"{path}.normal.z")
    length = math.sqrt(normal.x**2 + normal.y**2 + normal.z**2)
    if not math.isclose(length, 1.0, rel_tol=0.0, abs_tol=NORMAL_LENGTH_TOLERANCE):
        _invalid(
            f"{path}.normal",
            f"must have unit length within {NORMAL_LENGTH_TOLERANCE:g} tolerance",
        )


def _validate_finite_fault(finite: project_proto.FiniteFault, path: str) -> None:
    _positive_finite(finite.lateral_extent, f"{path}.lateral_extent")
    _positive_finite(finite.vertical_extent, f"{path}.vertical_extent")
    _positive_finite(finite.influence_radius, f"{path}.influence_radius")


def _finite(value: float, path: str) -> float:
    if not math.isfinite(value):
        _invalid(path, "must be finite")
    return value


def _positive_finite(value: float, path: str) -> None:
    if _finite(value, path) <= 0.0:
        _invalid(path, "must be positive")


def _validate_entity_uuid(value: str, path: str, seen: set[str]) -> None:
    if not value:
        _invalid(path, "must not be empty")
    try:
        uuid_module.UUID(value)
    except (ValueError, AttributeError) as error:
        raise GeologicalModelValidationError(f"{path}: must be a valid UUID") from error
    if value in seen:
        _invalid(path, f"duplicate entity UUID {value!r}")
    seen.add(value)


def _validate_fault_reference(value: str, fault_uuids: set[str], path: str) -> None:
    if not value:
        _invalid(path, "must not be empty")
    try:
        uuid_module.UUID(value)
    except (ValueError, AttributeError) as error:
        raise GeologicalModelValidationError(f"{path}: must be a valid UUID") from error
    if value not in fault_uuids:
        _invalid(path, f"references unknown fault UUID {value!r}")


def _validate_stops_on_acyclic(faults: list[project_proto.Fault]) -> None:
    dependencies = {fault.uuid: fault.stops_on for fault in faults}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(fault_uuid: str) -> None:
        if fault_uuid in visiting:
            _invalid("faults.stops_on", f"contains a cycle through {fault_uuid!r}")
        if fault_uuid in visited:
            return
        visiting.add(fault_uuid)
        for dependency_uuid in dependencies[fault_uuid]:
            visit(dependency_uuid)
        visiting.remove(fault_uuid)
        visited.add(fault_uuid)

    for fault_uuid in dependencies:
        visit(fault_uuid)


def _invalid(path: str, reason: str) -> Never:
    raise GeologicalModelValidationError(f"{path}: {reason}")
