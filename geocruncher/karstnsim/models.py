# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/models

import enum
from dataclasses import dataclass
from typing import Literal, TypedDict

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator
from pydantic.alias_generators import to_camel

from geocruncher.geometry import Vec2Float, Vec2Int, Vec3Float, Vec3Int
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


class KarstNSimProjectBox(BaseModel):
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


class KarstNSimGeologicalUnit(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)
    name: str
    permeability: Permeability
    strati_unit_id: int


KarstNSimStratigraphy = RootModel[list[KarstNSimGeologicalUnit]]


class KarstNSimSpring(Vec3Float):
    """Spring as received from the API — distinct from computations.Spring (gwb meshes)"""

    poi_id: int
    catchment: list[tuple[float, float]]


class KarstNSimVoxelsHeader(BaseModel):
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    nx: int = Field(gt=0)
    ny: int = Field(gt=0)
    nz: int = Field(gt=0)
    novalue: int

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.xmax <= self.xmin:
            raise ValueError("xmax must be greater than xmin")
        if self.ymax <= self.ymin:
            raise ValueError("ymax must be greater than ymin")
        if self.zmax <= self.zmin:
            raise ValueError("zmax must be greater than zmin")
        return self


KarstNSimVoxelsUnits = RootModel[list[int]]


class KarstNSimGroundwaterBody(BaseModel):
    gwb_id: int
    spring_id: int


class SimulationParameters(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    name: str = "Karst Network"
    seed: int = Field(default=-1, ge=-1)
    k_pts: int = Field(default=20, gt=0)
    cohesion_factor: float = Field(default=0.9, ge=0.0, le=1.0)
    n_sinks: int = Field(default=100, gt=0)

    search_radius: Literal["auto"] | float = Field(default="auto", ge=0.0)
    inception_surface_constraint_weight: float = Field(default=1.0, ge=0.0)
    max_inception_surface_distance: Literal["auto"] | float = Field(
        default="auto", ge=0.0
    )
    r_min_pervious: Literal["auto"] | float = Field(default="auto", ge=0.0, le=1.0)
    r_min_impervious: Literal["auto"] | float = Field(default="auto", ge=0.0, le=1.0)


@dataclass
class KarstNSimContent:
    """Replaces VkZipContent — holds all parsed simulation inputs"""

    simulation_params: SimulationParameters
    project_box: KarstNSimProjectBox
    surface_data: np.ndarray
    stratigraphy: KarstNSimStratigraphy
    compute_resolution: Vec3Int
    voxels_header: KarstNSimVoxelsHeader
    voxels: np.ndarray
    voxels_units: KarstNSimVoxelsUnits
    faults: list[TriangleMesh]
    springs: list[KarstNSimSpring]
    gwbs: list[KarstNSimGroundwaterBody]
    surface_resolution: Vec2Float
    resampled_dem_resolution: Vec2Int


class KarstNSimData(TypedDict):
    """Data given to the KarstNSim computation.
    Binary inputs (dem_values, voxels, faults) are sent as separate files."""

    simulation_params: SimulationParameters
    project_box: KarstNSimProjectBox
    dem_resolution: Vec2Int
    stratigraphy: list[KarstNSimGeologicalUnit]
    voxels_header: KarstNSimVoxelsHeader
    voxels_units: list[int]
    fault_ids: list[int]
    springs: list[KarstNSimSpring]
    gwbs: list[KarstNSimGroundwaterBody]
