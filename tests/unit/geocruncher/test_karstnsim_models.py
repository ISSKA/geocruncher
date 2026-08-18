import pytest
from pydantic import ValidationError

from geocruncher.karstnsim.models import (
    GeologicalUnitInput,
    ProjectBoxInput,
    SimulationParametersInput,
)

######## SimulationParametersInput tests ########


def test_simulation_parameters_defaults():
    params = SimulationParametersInput.model_validate({})

    assert params.seed == -1
    assert params.k_pts == 20
    assert params.cohesion_factor == 0.9
    assert params.n_sinks == 100


@pytest.mark.parametrize(
    "field,value",
    [
        ("k_pts", 0),
        ("n_sinks", 0),
        ("cohesion_factor", -0.1),
        ("cohesion_factor", 1.1),
        ("seed", -2),
    ],
)
def test_simulation_parameters_rejects_invalid_parameters(field, value):
    with pytest.raises(ValidationError):
        SimulationParametersInput(**{field: value})


######## ProjectBoxInput tests ########


def test_project_box_rejects_non_positive_dimensions():
    with pytest.raises(ValidationError):
        ProjectBoxInput(
            width=0,
            height=100,
            min_elevation=100,
            max_elevation=200,
        )

    with pytest.raises(ValidationError):
        ProjectBoxInput(
            width=100,
            height=-50,
            min_elevation=100,
            max_elevation=200,
        )


def test_project_box_rejects_invalid_elevation_range():
    with pytest.raises(ValidationError):
        ProjectBoxInput(
            width=100,
            height=100,
            min_elevation=300,
            max_elevation=100,
        )


def test_project_box_depth_property():
    box = ProjectBoxInput.model_validate(
        {
            "width": 1000.0,
            "height": 500.0,
            "min_elevation": 120.0,
            "max_elevation": 320.0,
        }
    )
    assert box.depth == pytest.approx(200.0)


######## GeologicalUnitInput tests ########


def test_geological_unit_rejects_invalid_permeability():
    with pytest.raises(ValidationError):
        GeologicalUnitInput.model_validate(
            {
                "name": "Aquifer",
                "permeability": "NotARealValue",
                "strati_unit_id": 7,
            }
        )
