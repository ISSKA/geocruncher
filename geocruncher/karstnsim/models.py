# Based on https://github.com/ISSKA/pykarstnsim-demo/blob/main/src/pykarstnsim_demo/models

import enum
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, RootModel
from pydantic.alias_generators import to_camel

from geocruncher.geometry import Vec2Float, Vec3Float, Vec3Int
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
    width: float
    height: float
    min_elevation: float
    max_elevation: float

    @property
    def depth(self) -> float:
        return self.max_elevation - self.min_elevation


class KarstNSimDemResolution(BaseModel):
    n_cols: int
    n_rows: int


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
    nx: int
    ny: int
    nz: int
    novalue: int


KarstNSimVoxelsUnits = RootModel[list[int]]


class KarstNSimGroundwaterBody(BaseModel):
    gwb_id: int
    spring_id: int


class SimulationParameters(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    name: str = "Karst Network"
    seed: int = 42
    k_pts: int = 10
    cohesion_factor: float = 0.9
    n_sinks: int = 100
    search_radius: Literal["auto"] | float = "auto"
    inception_surface_constraint_weight: float = 1.0
    max_inception_surface_distance: Literal["auto"] | float = "auto"
    r_min_pervious: Literal["auto"] | float = "auto"
    r_min_impervious: Literal["auto"] | float = "auto"


@dataclass
class KarstNSimContent:
    """Replaces VkZipContent — holds all parsed simulation inputs"""

    simulation_params: SimulationParameters
    project_box: KarstNSimProjectBox
    dem_resolution: KarstNSimDemResolution
    surface_data: np.ndarray  # resampled, flipped, shape (ny, nx)
    stratigraphy: KarstNSimStratigraphy
    compute_resolution: Vec3Int
    voxels_header: KarstNSimVoxelsHeader
    voxels: np.ndarray  # shape (nx, ny, nz, 2)
    voxels_units: KarstNSimVoxelsUnits
    faults: list[TriangleMesh]
    springs: list[KarstNSimSpring]
    gwbs: list[KarstNSimGroundwaterBody]
    surface_resolution: Vec2Float
    resampled_dem_resolution: KarstNSimDemResolution


class KarstNSimData(BaseModel):
    """Data given to the KarstNSim computation.
    Binary inputs (dem_values, voxels, faults) are sent as separate files."""

    simulation_params: SimulationParameters
    project_box: KarstNSimProjectBox
    dem_resolution: KarstNSimDemResolution
    stratigraphy: list[KarstNSimGeologicalUnit]
    voxels_header: KarstNSimVoxelsHeader
    voxels_units: list[int]
    fault_ids: list[int]
    springs: list[KarstNSimSpring]
    gwbs: list[KarstNSimGroundwaterBody]
