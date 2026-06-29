import enum
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, RootModel
from pydantic.alias_generators import to_camel


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


class Point2D(BaseModel):
    x: float
    y: float


class Point3D(Point2D):
    z: float


class KarstProjectBox(BaseModel):
    width: float
    height: float
    min_elevation: float
    max_elevation: float

    @property
    def depth(self) -> float:
        return self.max_elevation - self.min_elevation


class KarstDemResolution(BaseModel):
    n_cols: int
    n_rows: int


class KarstGeologicalUnit(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)
    name: str
    permeability: Permeability
    strati_unit_id: int


KarstStratigraphy = RootModel[list[KarstGeologicalUnit]]


class KarstSpring(Point3D):
    """Spring as received from the API — distinct from computations.Spring (gwb meshes)"""

    poi_id: int
    catchment: list[tuple[float, float]]


class KarstVoxelsHeader(BaseModel):
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


KarstVoxelsUnits = RootModel[list[int]]


class KarstGroundwaterBody(BaseModel):
    gwb_id: int
    spring_id: int


@dataclass
class KarstFault:
    vertices: np.ndarray  # shape (n, 3), float32
    triangles: np.ndarray  # shape (m, 3), int32


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
