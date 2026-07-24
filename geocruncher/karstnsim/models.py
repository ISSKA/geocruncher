# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/models

import enum
from dataclasses import dataclass
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator
from pydantic.alias_generators import to_camel

from geocruncher.geometry import Vec2Float, Vec2Int, Vec3Int
from geocruncher.mesh_io.mesh_io import TriangleMesh


class Permeability(enum.Enum):
    Karstified = "Karstified"
    NonKarstified = "NonKarstified"
    PorousPermeability = "PorousPermeability"
    Undefined = "Undefined"


PERMEABILITY_MAP: dict[Permeability, float] = {
    Permeability.Karstified: 0.5,
    Permeability.NonKarstified: 0.0,
    Permeability.PorousPermeability: 0.0,
    Permeability.Undefined: 0.0,
}

########## API INPUT MODELS ##########
# Models used to validate the input data received from the API


class ApiInputModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ProjectBoxInput(ApiInputModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    min_elevation: float
    max_elevation: float

    @property
    def depth(self) -> float:
        return self.max_elevation - self.min_elevation

    @model_validator(mode="after")
    def validate_depth(self):
        if self.depth <= 0:
            raise ValueError("max_elevation must be greater than min_elevation")
        return self


class GeologicalUnitInput(ApiInputModel):
    name: str
    permeability: Permeability
    strati_unit_id: int


StratigraphyInput = RootModel[list[GeologicalUnitInput]]


class SpringInput(ApiInputModel):
    """Spring as received from the API — distinct from computations.Spring (gwb meshes)"""

    x: float
    y: float
    z: float
    poi_id: int
    catchment: list[tuple[float, float]]


VoxelsUnitsInput = RootModel[list[int]]


class GroundwaterBodyInput(ApiInputModel):
    gwb_id: int
    spring_id: int


class SimulationParametersInput(ApiInputModel):
    name: str = "Karst Network"
    seed: int = Field(default=-1, ge=-1)
    k_pts: int = Field(default=20, gt=0)
    cohesion_factor: float = Field(default=0.9, ge=0.0, le=1.0)
    n_sinks: int = Field(default=100, gt=0)

    search_radius: Literal["auto"] | Annotated[float, Field(ge=0.0)] = "auto"
    inception_surface_constraint_weight: Annotated[float, Field(ge=0.0)] = 1.0
    max_inception_surface_distance: (
        Literal["auto"] | Annotated[float, Field(ge=0.0)]
    ) = "auto"
    r_min_pervious: Literal["auto"] | Annotated[float, Field(ge=0.0, le=1.0)] = "auto"
    r_min_impervious: Literal["auto"] | Annotated[float, Field(ge=0.0, le=1.0)] = "auto"


class KarstNSimData(ApiInputModel):
    """Data given to the KarstNSim computation.
    Binary inputs (dem_values, voxels, faults) are sent as separate files."""

    simulation_params: SimulationParametersInput
    project_box: ProjectBoxInput
    dem_resolution: Vec2Int
    stratigraphy: list[GeologicalUnitInput]
    voxels_units: list[int]
    fault_ids: list[int]
    springs: list[SpringInput]
    gwbs: list[GroundwaterBodyInput]


@dataclass
class KarstNSimContent:
    """Prepared content for the KarstNSim computation, after loading and processing the input data."""

    simulation_params: SimulationParametersInput
    project_box: ProjectBoxInput
    surface_data: np.ndarray
    stratigraphy: StratigraphyInput
    compute_resolution: Vec3Int
    voxels: np.ndarray
    voxels_units: VoxelsUnitsInput
    faults: list[TriangleMesh]
    springs: list[SpringInput]
    gwbs: list[GroundwaterBodyInput]
    surface_resolution: Vec2Float
    resampled_dem_resolution: Vec2Int
