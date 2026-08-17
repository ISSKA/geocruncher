from typing import cast

import numpy as np
import pytest
from forgeo.gmlib.GeologicalModel3D import GeologicalModel
from isska.geocruncher.v1 import project_pb as project_proto

from geocruncher.contracts import EvaluationExtent, EvaluationExtentValidationError
from geocruncher.geological_model_input import GeologicalModelValidationError
from geocruncher.gmlib_adapter import build_gmlib_project_data
from geocruncher.gmlib_compatibility import (
    DEFAULT_FORMATION_COLOR,
    DUMMY_FORMATION_NAME,
)

SERIES_MODELED = "00000000-0000-0000-0000-000000000001"
SERIES_CONTACTS_ONLY = "00000000-0000-0000-0000-000000000002"
SERIES_ORIENTATIONS_ONLY = "00000000-0000-0000-0000-000000000003"
UNIT_FIRST = "00000000-0000-0000-0000-000000000011"
UNIT_EMPTY = "00000000-0000-0000-0000-000000000012"
UNIT_CONTACTS_ONLY = "00000000-0000-0000-0000-000000000013"
UNIT_ORIENTATIONS_ONLY = "00000000-0000-0000-0000-000000000014"
FAULT_INFINITE = "00000000-0000-0000-0000-000000000021"
FAULT_FINITE = "00000000-0000-0000-0000-000000000022"

EXTENT: EvaluationExtent = {
    "xmin": 0.0,
    "ymin": -50.0,
    "zmin": 10.0,
    "xmax": 100.0,
    "ymax": 150.0,
    "zmax": 60.0,
}

DEM = "\n".join(
    [
        "ncols 2",
        "nrows 2",
        "xllcorner 10",
        "yllcorner -20",
        "cellsize 5",
        "1 2",
        "3 4",
    ]
)


def point(x, y, z):
    return project_proto.Point3(x=x, y=y, z=z)


def orientation(x, y, z, nx, ny, nz):
    return project_proto.Orientation(
        position=point(x, y, z),
        normal=project_proto.Vector3(x=nx, y=ny, z=nz),
    )


def model_message():
    return project_proto.GeologicalModel(
        stratigraphy=project_proto.StratigraphicColumn(
            reference=project_proto.StratigraphicReference.TOP,
            series=[
                project_proto.Series(
                    uuid=SERIES_MODELED,
                    relation=project_proto.SeriesRelation.ONLAP,
                    units=[
                        project_proto.Unit(
                            uuid=UNIT_FIRST,
                            contact_points=[point(1, 2, 3), point(4, 5, 6)],
                            orientations=[orientation(7, 8, 9, 0, 0, 1)],
                        ),
                        project_proto.Unit(
                            uuid=UNIT_EMPTY,
                            orientations=[orientation(10, 11, 12, 0, 1, 0)],
                        ),
                    ],
                    influenced_by_faults=[FAULT_FINITE],
                ),
                project_proto.Series(
                    uuid=SERIES_CONTACTS_ONLY,
                    relation=project_proto.SeriesRelation.ERODE,
                    units=[
                        project_proto.Unit(
                            uuid=UNIT_CONTACTS_ONLY,
                            contact_points=[point(13, 14, 15)],
                        )
                    ],
                ),
                project_proto.Series(
                    uuid=SERIES_ORIENTATIONS_ONLY,
                    relation=project_proto.SeriesRelation.ONLAP,
                    units=[
                        project_proto.Unit(
                            uuid=UNIT_ORIENTATIONS_ONLY,
                            orientations=[orientation(16, 17, 18, 1, 0, 0)],
                        )
                    ],
                ),
            ],
        ),
        faults=[
            project_proto.Fault(
                uuid=FAULT_INFINITE,
                contact_points=[point(20, 21, 22)],
                orientations=[orientation(23, 24, 25, 0, 1, 0)],
            ),
            project_proto.Fault(
                uuid=FAULT_FINITE,
                contact_points=[point(26, 27, 28), point(29, 30, 31)],
                orientations=[orientation(32, 33, 34, 1, 0, 0)],
                stops_on=[FAULT_INFINITE],
                finite=project_proto.FiniteFault(
                    lateral_extent=100.0,
                    vertical_extent=200.0,
                    influence_radius=300.0,
                ),
            ),
        ],
    )


def test_builds_complete_gmlib_project_dictionary():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)

    assert project_data["box"] == {
        "Xmin": 0.0,
        "Ymin": -50.0,
        "Zmin": 10.0,
        "Xmax": 100.0,
        "Ymax": 150.0,
        "Zmax": 60.0,
    }
    assert project_data["crs"] == (None, None)
    assert project_data["pile"].reference == "top"
    assert [series.name for series in project_data["pile"].all_series] == [
        SERIES_MODELED,
        SERIES_CONTACTS_ONLY,
        SERIES_ORIENTATIONS_ONLY,
    ]
    assert list(project_data["faults_data"]) == [FAULT_INFINITE, FAULT_FINITE]
    np.testing.assert_allclose(project_data["topography"].origin, [10, -20])


def test_dictionary_is_accepted_by_geological_model():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)

    model = GeologicalModel(project_data, use_cache=False)

    assert model.pile.reference == "top"
    assert model.pile_formations == [UNIT_FIRST, UNIT_ORIENTATIONS_ONLY]
    assert list(model.faults) == [FAULT_INFINITE, FAULT_FINITE]


def test_maps_modeled_series_observations_in_unit_wire_order():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)
    series = project_data["pile"].all_series[0]
    potential = series.potential_data

    assert series.formations == [UNIT_FIRST, UNIT_EMPTY]
    assert series.relation == "onlap"
    assert series.influenced_by_fault == [FAULT_FINITE]
    assert potential is not None
    np.testing.assert_allclose(potential.interfaces[0], [[1, 2, 3], [4, 5, 6]])
    assert potential.interfaces[1].shape == (0, 3)
    np.testing.assert_allclose(
        potential.gradients.locations,
        [[7, 8, 9], [10, 11, 12]],
    )
    np.testing.assert_allclose(potential.gradients.values, [[0, 0, 1], [0, 1, 0]])


def test_leaves_incomplete_series_without_potential_data():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)
    contacts_only, orientations_only = project_data["pile"].all_series[1:]

    assert contacts_only.potential_data is None
    assert orientations_only.potential_data is None
    assert contacts_only.influenced_by_fault is None
    assert orientations_only.influenced_by_fault is None


def test_maps_infinite_and_finite_faults():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)
    infinite = project_data["faults_data"][FAULT_INFINITE]
    finite = project_data["faults_data"][FAULT_FINITE]

    assert infinite.infinite is True
    assert infinite.stops_on == []
    assert infinite.color is None
    np.testing.assert_allclose(infinite.potential_data.interfaces[0], [[20, 21, 22]])
    assert finite.infinite is False
    assert finite.center_type == "mean_center"
    assert finite.stops_on == [FAULT_INFINITE]
    assert finite.lateral_extent == 100.0
    assert finite.vertical_extent == 200.0
    assert finite.influence_radius == 300.0
    np.testing.assert_allclose(
        finite.potential_data.interfaces[0],
        [[26, 27, 28], [29, 30, 31]],
    )
    np.testing.assert_allclose(
        finite.potential_data.gradients.locations, [[32, 33, 34]]
    )


def test_builds_ordered_formations_and_dummy():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)
    formations = project_data["formations"]

    assert [formation.name for formation in formations] == [
        UNIT_FIRST,
        UNIT_EMPTY,
        UNIT_CONTACTS_ONLY,
        UNIT_ORIENTATIONS_ONLY,
        DUMMY_FORMATION_NAME,
    ]
    assert all(formation.color == DEFAULT_FORMATION_COLOR for formation in formations)
    assert [formation.is_dummy for formation in formations] == [
        False,
        False,
        False,
        False,
        True,
    ]


def test_uses_evaluation_extent_for_covariance_rescaling():
    project_data = build_gmlib_project_data(model_message(), EXTENT, DEM)
    potential = project_data["pile"].all_series[0].potential_data
    assert potential is not None
    covariance = potential.covariance_model

    assert covariance.gradient_variance == pytest.approx(
        ((19_000.0 / 200.0) ** 2) / 42.0
    )
    assert covariance.gradient_nugget == pytest.approx(0.01 * (1.0 / 200.0) ** 2)


def test_validates_model_before_adapting_it():
    model = model_message()
    model.stratigraphy.series[0].uuid = "not-a-uuid"

    with pytest.raises(GeologicalModelValidationError, match="valid UUID"):
        build_gmlib_project_data(model, EXTENT, DEM)


def test_can_skip_validation_for_input_validated_at_http_ingress():
    model = model_message()
    model.stratigraphy.series[0].units[0].orientations[
        0
    ].normal = project_proto.Vector3(x=0.0, y=0.0, z=1.01)
    extent = cast(EvaluationExtent, {**EXTENT, "xmax": EXTENT["xmin"]})

    project_data = build_gmlib_project_data(
        model,
        extent,
        DEM,
        validate_input=False,
    )

    potential = project_data["pile"].all_series[0].potential_data
    assert potential is not None
    np.testing.assert_allclose(potential.gradients.values[0], [0.0, 0.0, 1.0])


def test_normalizes_accepted_orientation_rounding_error():
    model = model_message()
    model.stratigraphy.series[0].units[0].orientations[
        0
    ].normal = project_proto.Vector3(x=0.0, y=0.0, z=1.0009)

    project_data = build_gmlib_project_data(model, EXTENT, DEM)
    potential = project_data["pile"].all_series[0].potential_data

    assert potential is not None
    np.testing.assert_allclose(potential.gradients.values[0], [0.0, 0.0, 1.0])


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("xmax", 0.0, "box.xmin must be less than box.xmax"),
        ("ymin", float("inf"), "box.ymin and box.ymax must be finite"),
    ],
)
def test_rejects_invalid_evaluation_extent(field, value, match):
    extent = cast(EvaluationExtent, dict(EXTENT))
    extent[field] = value

    with pytest.raises(EvaluationExtentValidationError, match=match):
        build_gmlib_project_data(model_message(), extent, DEM)
