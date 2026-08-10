import numpy as np
import pytest
from forgeo.gmlib.GeologicalModel3D import (
    covariance_data,
    drift_basis,
    gradient_data,
    interface_data,
)
from forgeo.gmlib.geomodeller_data import FaultData, Pile, PotentialData, SeriesData
from forgeo.gmlib.geomodeller_project import Formation

from geocruncher.gmlib_compatibility import (
    DEFAULT_COVARIANCE_MODEL,
    DEFAULT_DRIFT_ORDER,
    DEFAULT_FORMATION_COLOR,
    DEFAULT_POTENTIAL_NUGGET,
    DEFAULT_RANGE,
    DUMMY_FORMATION_NAME,
    GmlibCompatibilityFactory,
)

BOX = {
    "Xmin": 0.0,
    "Xmax": 100.0,
    "Ymin": -50.0,
    "Ymax": 150.0,
    "Zmin": 10.0,
    "Zmax": 60.0,
}


def test_builds_rescaled_covariance_defaults_without_xml():
    covariance = GmlibCompatibilityFactory().make_covariance_model(BOX)

    assert covariance.covariance_model == DEFAULT_COVARIANCE_MODEL
    assert covariance.drift_order == DEFAULT_DRIFT_ORDER
    assert covariance.range == DEFAULT_RANGE
    assert covariance.gradient_variance == pytest.approx(
        ((19_000.0 / 200.0) ** 2) / 42.0
    )
    assert covariance.gradient_nugget == pytest.approx(0.01 * (1.0 / 200.0) ** 2)
    assert covariance.potential_nugget == DEFAULT_POTENTIAL_NUGGET


def test_rejects_box_without_a_positive_dimension():
    box = {key: 0.0 for key in BOX}

    with pytest.raises(ValueError, match="positive longest dimension"):
        GmlibCompatibilityFactory().make_covariance_model(box)


def test_builds_potential_data_with_gmlib_dtype_and_empty_interface_shape():
    factory = GmlibCompatibilityFactory(np.float32)

    potential = factory.make_potential_data(
        BOX,
        gradient_locations=[[1.0, 2.0, 3.0]],
        gradient_values=[[0.0, 0.0, 1.0]],
        interfaces=[[], [[4.0, 5.0, 6.0]]],
    )

    assert isinstance(potential, PotentialData)
    assert potential.gradients.locations.dtype == np.dtype(np.float32)
    assert potential.gradients.values.dtype == np.dtype(np.float32)
    assert potential.gradients.locations.shape == (1, 3)
    assert potential.interfaces[0].shape == (0, 3)
    assert potential.interfaces[1].shape == (1, 3)
    assert all(
        interface.dtype == np.dtype(np.float32) for interface in potential.interfaces
    )


def test_potential_data_is_consumed_by_gmlib_conversion_functions():
    potential = GmlibCompatibilityFactory().make_potential_data(
        BOX,
        gradient_locations=[[1.0, 2.0, 3.0]],
        gradient_values=[[0.0, 0.0, 1.0]],
        interfaces=[[[4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]],
    )

    assert covariance_data(potential) is not None
    assert len(drift_basis(potential)) == 3
    assert gradient_data(potential) is not None
    assert interface_data(potential) is not None


@pytest.mark.parametrize(
    ("locations", "values", "match"),
    [
        ([1.0, 2.0, 3.0], [[0.0, 0.0, 1.0]], "gradient_locations"),
        (
            [[1.0, 2.0, 3.0]],
            [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
            "same shape",
        ),
    ],
)
def test_rejects_invalid_gradient_array_shapes(locations, values, match):
    with pytest.raises(ValueError, match=match):
        GmlibCompatibilityFactory().make_potential_data(
            BOX,
            gradient_locations=locations,
            gradient_values=values,
            interfaces=[],
        )


def test_builds_series_and_pile_legacy_objects():
    factory = GmlibCompatibilityFactory()
    first = factory.make_series_data(
        "series-1",
        formations=["unit-1"],
        relation="onlap",
        potential_data=None,
    )
    second = factory.make_series_data(
        "series-2",
        formations=["unit-2", "unit-3"],
        relation="erode",
        potential_data=None,
        influenced_by_faults=["fault-1"],
    )
    pile = factory.make_pile("base", [first, second])

    assert isinstance(first, SeriesData)
    assert first.influenced_by_fault is None
    assert second.influenced_by_fault == ["fault-1"]
    assert isinstance(pile, Pile)
    assert pile.reference == "base"
    assert pile.all_series == [first, second]


def test_builds_infinite_and_finite_fault_legacy_objects():
    factory = GmlibCompatibilityFactory()
    potential = factory.make_potential_data(
        BOX,
        gradient_locations=[[1.0, 2.0, 3.0]],
        gradient_values=[[0.0, 0.0, 1.0]],
        interfaces=[[[4.0, 5.0, 6.0]]],
    )

    infinite = factory.make_infinite_fault_data(
        "infinite", potential_data=potential, stops_on=["other"]
    )
    finite = factory.make_finite_fault_data(
        "finite",
        potential_data=potential,
        lateral_extent=10.0,
        vertical_extent=20.0,
        influence_radius=30.0,
    )

    assert isinstance(infinite, FaultData)
    assert infinite.infinite is True
    assert infinite.stops_on == ["other"]
    assert infinite.color is None
    assert finite.infinite is False
    assert finite.center_type == "mean_center"
    assert finite.lateral_extent == 10.0
    assert finite.vertical_extent == 20.0
    assert finite.influence_radius == 30.0
    assert isinstance(finite.lateral_extent, np.float64)
    assert finite.potential_data is potential


def test_builds_formation_defaults():
    factory = GmlibCompatibilityFactory()

    formation = factory.make_formation("unit-1")
    dummy = factory.make_dummy_formation()

    assert isinstance(formation, Formation)
    assert formation == Formation("unit-1", DEFAULT_FORMATION_COLOR, False)
    assert dummy == Formation(DUMMY_FORMATION_NAME, DEFAULT_FORMATION_COLOR, True)
