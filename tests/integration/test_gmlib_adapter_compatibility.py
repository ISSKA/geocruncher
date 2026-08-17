"""Regression test for parity between the legacy XML importer and the gmlib adapter.

The protobuf message is deliberately constructed from the legacy importer output
instead of loaded from ``geocruncher_project.pb``. This isolates the adapter and
verifies that equivalent geological input produces the same gmlib structures and
defaults. Remove this test once legacy XML parity is no longer a migration concern."""

from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pytest
from isska.geocruncher.v1 import project_pb as project_proto

from geocruncher.geomodeller_import import extract_project_data
from geocruncher.gmlib_adapter import EvaluationExtent, build_gmlib_project_data

pytestmark = pytest.mark.integration


def test_matches_legacy_xml_import_for_equivalent_fixture_data(dummy_project):
    legacy = extract_project_data(dummy_project.xml, dummy_project.dem)
    message, legacy_name_by_uuid = _protobuf_equivalent_of(legacy)

    box = legacy["box"]
    extent: EvaluationExtent = {
        "xmin": box["Xmin"],
        "ymin": box["Ymin"],
        "zmin": box["Zmin"],
        "xmax": box["Xmax"],
        "ymax": box["Ymax"],
        "zmax": box["Zmax"],
    }
    adapted = build_gmlib_project_data(message, extent, dummy_project.dem)

    assert adapted["box"] == legacy["box"]
    assert legacy["crs"] == ("local", None)
    assert adapted["crs"] == (None, None)
    _assert_piles_equal(adapted["pile"], legacy["pile"], legacy_name_by_uuid)
    _assert_faults_equal(
        adapted["faults_data"], legacy["faults_data"], legacy_name_by_uuid
    )
    _assert_formations_equal(
        adapted["formations"], legacy["formations"], legacy_name_by_uuid
    )
    _assert_topographies_equal(adapted["topography"], legacy["topography"])


def _protobuf_equivalent_of(project_data):
    """Build the normalized message represented by a legacy importer result."""
    pile = project_data["pile"]
    legacy_name_by_uuid = {}

    def mapped_uuid(kind, name):
        value = str(uuid5(NAMESPACE_URL, f"geocruncher-test:{kind}:{name}"))
        legacy_name_by_uuid[value] = name
        return value

    series_uuid = {
        series.name: mapped_uuid("series", series.name) for series in pile.all_series
    }
    unit_uuid = {
        name: mapped_uuid("unit", name)
        for series in pile.all_series
        for name in series.formations
    }
    fault_uuid = {
        name: mapped_uuid("fault", name) for name in project_data["faults_data"]
    }

    series_messages = []
    for series in pile.all_series:
        potential = series.potential_data
        units = []
        for index, name in enumerate(series.formations):
            contacts = potential.interfaces[index] if potential is not None else []
            # Legacy XML aggregates orientations at series level. Their original
            # unit ownership is immaterial to gmlib, so keep them on one unit.
            orientations = (
                _orientations_from_potential(potential)
                if index == 0 and potential is not None
                else []
            )
            units.append(
                project_proto.Unit(
                    uuid=unit_uuid[name],
                    contact_points=_protobuf_points(contacts),
                    orientations=orientations,
                )
            )

        series_messages.append(
            project_proto.Series(
                uuid=series_uuid[series.name],
                relation={
                    "onlap": project_proto.SeriesRelation.ONLAP,
                    "erode": project_proto.SeriesRelation.ERODE,
                }[series.relation],
                units=units,
                influenced_by_faults=[
                    fault_uuid[name] for name in series.influenced_by_fault or []
                ],
            )
        )

    fault_messages = []
    for name, fault in project_data["faults_data"].items():
        finite = None
        if not fault.infinite:
            finite = project_proto.FiniteFault(
                lateral_extent=float(fault.lateral_extent),
                vertical_extent=float(fault.vertical_extent),
                influence_radius=float(fault.influence_radius),
            )
        fault_messages.append(
            project_proto.Fault(
                uuid=fault_uuid[name],
                contact_points=_protobuf_points(fault.potential_data.interfaces[0]),
                orientations=_orientations_from_potential(fault.potential_data),
                stops_on=[fault_uuid[stopped_on] for stopped_on in fault.stops_on],
                finite=finite,
            )
        )

    reference = {
        "base": project_proto.StratigraphicReference.BASE,
        "top": project_proto.StratigraphicReference.TOP,
    }[pile.reference]
    return (
        project_proto.GeologicalModel(
            stratigraphy=project_proto.StratigraphicColumn(
                reference=reference,
                series=series_messages,
            ),
            faults=fault_messages,
        ),
        legacy_name_by_uuid,
    )


def _protobuf_points(rows):
    return [
        project_proto.Point3(x=float(x), y=float(y), z=float(z)) for x, y, z in rows
    ]


def _orientations_from_potential(potential):
    return [
        project_proto.Orientation(
            position=project_proto.Point3(
                x=float(x),
                y=float(y),
                z=float(z),
            ),
            normal=project_proto.Vector3(
                x=float(nx),
                y=float(ny),
                z=float(nz),
            ),
        )
        for (x, y, z), (nx, ny, nz) in zip(
            potential.gradients.locations,
            potential.gradients.values,
            strict=True,
        )
    ]


def _assert_piles_equal(actual, expected, legacy_name_by_uuid):
    assert actual.reference == expected.reference
    assert len(actual.all_series) == len(expected.all_series)
    for actual_series, expected_series in zip(
        actual.all_series, expected.all_series, strict=True
    ):
        assert legacy_name_by_uuid[actual_series.name] == expected_series.name
        assert [legacy_name_by_uuid[name] for name in actual_series.formations] == (
            expected_series.formations
        )
        assert actual_series.relation == expected_series.relation
        assert _legacy_names(
            actual_series.influenced_by_fault, legacy_name_by_uuid
        ) == (expected_series.influenced_by_fault or [])
        _assert_potentials_equal(
            actual_series.potential_data, expected_series.potential_data
        )


def _assert_faults_equal(actual, expected, legacy_name_by_uuid):
    actual_by_legacy_name = {
        legacy_name_by_uuid[name]: fault for name, fault in actual.items()
    }
    assert list(actual_by_legacy_name) == list(expected)
    for name, expected_fault in expected.items():
        actual_fault = actual_by_legacy_name[name]
        assert legacy_name_by_uuid[actual_fault.name] == expected_fault.name
        assert actual_fault.infinite == expected_fault.infinite
        assert actual_fault.color == expected_fault.color
        assert _legacy_names(actual_fault.stops_on, legacy_name_by_uuid) == (
            expected_fault.stops_on
        )
        if not expected_fault.infinite:
            assert actual_fault.center_type == expected_fault.center_type
            assert actual_fault.lateral_extent == expected_fault.lateral_extent
            assert actual_fault.vertical_extent == expected_fault.vertical_extent
            assert actual_fault.influence_radius == expected_fault.influence_radius
        _assert_potentials_equal(
            actual_fault.potential_data, expected_fault.potential_data
        )


def _assert_potentials_equal(actual, expected):
    assert (actual is None) == (expected is None)
    if actual is None or expected is None:
        return

    actual_covariance = actual.covariance_model
    expected_covariance = expected.covariance_model
    assert actual_covariance.covariance_model == expected_covariance.covariance_model
    assert actual_covariance.drift_order == expected_covariance.drift_order
    for field in (
        "range",
        "gradient_variance",
        "gradient_nugget",
        "potential_nugget",
    ):
        assert getattr(actual_covariance, field) == pytest.approx(
            getattr(expected_covariance, field)
        )

    actual_orientations = np.hstack(
        (actual.gradients.locations, actual.gradients.values)
    )
    expected_orientations = np.hstack(
        (expected.gradients.locations, expected.gradients.values)
    )
    np.testing.assert_allclose(
        _sorted_rows(actual_orientations), _sorted_rows(expected_orientations)
    )
    assert len(actual.interfaces) == len(expected.interfaces)
    for actual_interface, expected_interface in zip(
        actual.interfaces, expected.interfaces, strict=True
    ):
        np.testing.assert_allclose(
            _sorted_rows(actual_interface), _sorted_rows(expected_interface)
        )


def _assert_formations_equal(actual, expected, legacy_name_by_uuid):
    def by_legacy_name(formations):
        return {
            legacy_name_by_uuid.get(formation.name, formation.name): (
                formation.color,
                formation.is_dummy,
            )
            for formation in formations
        }

    # XML graphic order differs from canonical stratigraphic wire order.
    assert by_legacy_name(actual) == by_legacy_name(expected)


def _assert_topographies_equal(actual, expected):
    np.testing.assert_array_equal(actual.origin, expected.origin)
    np.testing.assert_array_equal(actual.steps, expected.steps)
    np.testing.assert_array_equal(actual.z, expected.z)


def _legacy_names(values, legacy_name_by_uuid):
    return [legacy_name_by_uuid[value] for value in values or []]


def _sorted_rows(rows):
    array = np.asarray(rows)
    return np.asarray(sorted(map(tuple, array.tolist())), dtype=array.dtype).reshape(
        array.shape
    )
