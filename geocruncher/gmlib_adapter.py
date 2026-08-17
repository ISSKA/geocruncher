"""Adapt normalized geological model protobuf input to legacy gmlib data."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import TypedDict, cast

from forgeo.gmlib.geomodeller_project import Formation
from forgeo.gmlib.topography_reader import ImplicitDTM
from isska.geocruncher.v1 import project_pb as project_proto

from .contracts import (
    EvaluationExtent,
    validate_evaluation_extent,
)
from .geological_model_input import validate_geological_model
from .gmlib_compatibility import (
    GmlibCompatibilityFactory,
    GmlibFaultData,
    GmlibPile,
    GmlibSeriesData,
)
from .topography_reader import ascii_grid_to_implicit_dtm


class LegacyGmlibBox(TypedDict):
    """Legacy gmlib spelling of a project-space computation extent."""

    Xmin: float
    Ymin: float
    Zmin: float
    Xmax: float
    Ymax: float
    Zmax: float


class GmlibProjectData(TypedDict):
    """Complete dictionary accepted by the legacy gmlib GeologicalModel."""

    box: LegacyGmlibBox
    crs: tuple[None, None]
    pile: GmlibPile
    faults_data: dict[str, GmlibFaultData]
    topography: ImplicitDTM
    formations: list[Formation]


def build_gmlib_project_data(
    model: project_proto.GeologicalModel,
    extent: EvaluationExtent,
    dem: str,
    *,
    factory: GmlibCompatibilityFactory | None = None,
    validate_input: bool = True,
) -> GmlibProjectData:
    """Adapt a v1 model to the dictionary expected by gmlib.

    Validation is enabled by default for standalone callers. The worker disables
    it for payloads already validated at HTTP ingress.
    """
    if validate_input:
        validate_geological_model(model)
        validate_evaluation_extent(extent)
    if factory is None:
        factory = GmlibCompatibilityFactory()

    box = _make_box(extent)
    stratigraphy = model.stratigraphy
    assert stratigraphy is not None

    series_data = [
        _make_series_data(series, box, factory) for series in stratigraphy.series
    ]
    pile = factory.make_pile(_reference_name(stratigraphy.reference), series_data)

    faults_data = {
        fault.uuid: _make_fault_data(fault, box, factory) for fault in model.faults
    }

    formations = [
        factory.make_formation(unit.uuid)
        for series in stratigraphy.series
        for unit in series.units
    ]
    formations.append(factory.make_dummy_formation())

    return {
        "box": box,
        "crs": (None, None),
        "pile": pile,
        "faults_data": faults_data,
        "topography": ascii_grid_to_implicit_dtm(dem),
        "formations": formations,
    }


def _make_box(extent: EvaluationExtent) -> LegacyGmlibBox:
    return {
        "Xmin": extent["xmin"],
        "Ymin": extent["ymin"],
        "Zmin": extent["zmin"],
        "Xmax": extent["xmax"],
        "Ymax": extent["ymax"],
        "Zmax": extent["zmax"],
    }


def _make_series_data(
    series: project_proto.Series,
    box: LegacyGmlibBox,
    factory: GmlibCompatibilityFactory,
) -> GmlibSeriesData:
    has_contacts = any(unit.contact_points for unit in series.units)
    orientations = [
        orientation for unit in series.units for orientation in unit.orientations
    ]

    potential_data = None
    if has_contacts and orientations:
        locations, values = _orientation_arrays(orientations)
        potential_data = factory.make_potential_data(
            cast(Mapping[str, float], box),
            gradient_locations=locations,
            gradient_values=values,
            interfaces=[
                [_point_tuple(point) for point in unit.contact_points]
                for unit in series.units
            ],
        )

    return factory.make_series_data(
        series.uuid,
        formations=[unit.uuid for unit in series.units],
        relation=_relation_name(series.relation),
        potential_data=potential_data,
        influenced_by_faults=series.influenced_by_faults,
    )


def _make_fault_data(
    fault: project_proto.Fault,
    box: LegacyGmlibBox,
    factory: GmlibCompatibilityFactory,
) -> GmlibFaultData:
    locations, values = _orientation_arrays(fault.orientations)
    potential_data = factory.make_potential_data(
        cast(Mapping[str, float], box),
        gradient_locations=locations,
        gradient_values=values,
        interfaces=[[_point_tuple(point) for point in fault.contact_points]],
    )

    if fault.has_field("finite"):
        finite = fault.finite
        assert finite is not None
        return factory.make_finite_fault_data(
            fault.uuid,
            potential_data=potential_data,
            lateral_extent=finite.lateral_extent,
            vertical_extent=finite.vertical_extent,
            influence_radius=finite.influence_radius,
            stops_on=fault.stops_on,
        )

    return factory.make_infinite_fault_data(
        fault.uuid,
        potential_data=potential_data,
        stops_on=fault.stops_on,
    )


def _orientation_arrays(
    orientations: Iterable[project_proto.Orientation],
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    locations = []
    values = []
    for orientation in orientations:
        position = orientation.position
        normal = orientation.normal
        assert position is not None
        assert normal is not None
        locations.append(_point_tuple(position))
        length = math.sqrt(normal.x**2 + normal.y**2 + normal.z**2)
        values.append((normal.x / length, normal.y / length, normal.z / length))
    return locations, values


def _point_tuple(point: project_proto.Point3) -> tuple[float, float, float]:
    return point.x, point.y, point.z


def _reference_name(reference: project_proto.StratigraphicReference) -> str:
    if reference == project_proto.StratigraphicReference.BASE:
        return "base"
    if reference == project_proto.StratigraphicReference.TOP:
        return "top"
    raise AssertionError("validated stratigraphic reference is unsupported")


def _relation_name(relation: project_proto.SeriesRelation) -> str:
    if relation == project_proto.SeriesRelation.ONLAP:
        return "onlap"
    if relation == project_proto.SeriesRelation.ERODE:
        return "erode"
    raise AssertionError("validated series relation is unsupported")
