import pytest


def test_camel_case_aliases():
    from geocruncher.karstnsim.models import SimulationParametersInput

    params = SimulationParametersInput.model_validate(
        {
            "kPts": 15,
            "cohesionFactor": 0.8,
            "nSinks": 200,
            "seed": 99,
        }
    )

    assert params.k_pts == 15
    assert params.cohesion_factor == 0.8
    assert params.n_sinks == 200
    assert params.seed == 99


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
    from pydantic import ValidationError

    from geocruncher.karstnsim.models import SimulationParametersInput

    with pytest.raises(ValidationError):
        SimulationParametersInput(**{field: value})


def test_project_box_rejects_invalid_elevation_range():
    from pydantic import ValidationError

    from geocruncher.karstnsim.models import ProjectBoxInput

    with pytest.raises(ValidationError):
        ProjectBoxInput(
            width=100,
            height=100,
            min_elevation=300,
            max_elevation=100,
        )


def test_project_box_depth_property():
    from geocruncher.karstnsim.models import ProjectBoxInput

    box = ProjectBoxInput.model_validate(
        {
            "width": 1000.0,
            "height": 500.0,
            "min_elevation": 120.0,
            "max_elevation": 320.0,
        }
    )
    assert box.depth == pytest.approx(200.0)


def test_geological_unit_rejects_invalid_permeability():
    from pydantic import ValidationError

    from geocruncher.karstnsim.models import GeologicalUnitInput

    with pytest.raises(ValidationError):
        GeologicalUnitInput.model_validate(
            {
                "name": "Aquifer",
                "permeability": "NotARealValue",
                "stratiUnitId": 7,
            }
        )
