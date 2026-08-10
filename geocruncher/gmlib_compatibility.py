"""XML-free construction of the legacy gmlib input data structures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
from forgeo.gmlib.geomodeller_data import (
    FaultData,
    GradientData,
    Pile,
    PotentialData,
    SeriesData,
)
from forgeo.gmlib.geomodeller_project import Formation
from numpy.typing import ArrayLike, DTypeLike

DEFAULT_COVARIANCE_MODEL = "cubique"
DEFAULT_DRIFT_ORDER = 1
DEFAULT_RANGE = 19_000.0
DEFAULT_RAW_GRADIENT_VARIANCE = 1.0
DEFAULT_RAW_GRADIENT_NUGGET = 0.01
DEFAULT_POTENTIAL_NUGGET = 1.0e-6

DEFAULT_FORMATION_COLOR = (0.0, 100.0 / 255.0, 0.0)
DUMMY_FORMATION_NAME = "dummyFormation"
DEFAULT_SCALAR_DTYPE = np.dtype("d")


@dataclass(slots=True)
class GmlibCovarianceModel:
    """The effective covariance fields consumed by the legacy gmlib model."""

    covariance_model: str
    drift_order: int
    range: float
    gradient_variance: float
    gradient_nugget: float
    potential_nugget: float


class GmlibPotentialData(PotentialData):
    """Typed form of gmlib's dynamically populated potential data container."""

    covariance_model: GmlibCovarianceModel
    gradients: GradientData
    interfaces: list[np.ndarray]


class GmlibSeriesData(SeriesData):
    """Typed form of gmlib's mutable series data container."""

    formations: list[str]
    relation: str
    influenced_by_fault: list[str] | None
    potential_data: GmlibPotentialData | None


class GmlibPile(Pile):
    """Typed form of gmlib's mutable stratigraphic pile container."""

    all_series: list[GmlibSeriesData]


class GmlibFaultData(FaultData):
    """Typed form of gmlib's mutable fault data container."""

    infinite: bool
    center_type: str | None
    influence_radius: object
    lateral_extent: object
    vertical_extent: object
    stops_on: list[str]
    potential_data: GmlibPotentialData
    color: None


class GmlibCompatibilityFactory:
    """Build legacy gmlib inputs without passing through GeoModeller XML."""

    def __init__(self, scalar_dtype: DTypeLike | None = None) -> None:
        if scalar_dtype is None:
            scalar_dtype = DEFAULT_SCALAR_DTYPE
        self.scalar_dtype = np.dtype(scalar_dtype)

    def make_covariance_model(self, box: Mapping[str, float]) -> GmlibCovarianceModel:
        """Create the v1 covariance defaults rescaled for an evaluation box."""
        longest_dimension = max(
            box[axis + "max"] - box[axis + "min"] for axis in ("X", "Y", "Z")
        )
        if longest_dimension <= 0.0:
            raise ValueError("evaluation box must have a positive longest dimension")

        return GmlibCovarianceModel(
            covariance_model=DEFAULT_COVARIANCE_MODEL,
            drift_order=DEFAULT_DRIFT_ORDER,
            range=DEFAULT_RANGE,
            gradient_variance=(
                (DEFAULT_RANGE / longest_dimension) ** 2
                * DEFAULT_RAW_GRADIENT_VARIANCE
                / 42.0
            ),
            gradient_nugget=(
                DEFAULT_RAW_GRADIENT_NUGGET * (1.0 / longest_dimension) ** 2
            ),
            potential_nugget=DEFAULT_POTENTIAL_NUGGET,
        )

    def make_potential_data(
        self,
        box: Mapping[str, float],
        *,
        gradient_locations: ArrayLike,
        gradient_values: ArrayLike,
        interfaces: Iterable[ArrayLike],
    ) -> GmlibPotentialData:
        """Create legacy potential data with consistently shaped scalar arrays."""
        locations = self._point_array(gradient_locations, "gradient_locations")
        values = self._point_array(gradient_values, "gradient_values")
        if locations.shape != values.shape:
            raise ValueError(
                "gradient_locations and gradient_values must have the same shape"
            )

        potential_data = GmlibPotentialData()
        potential_data.covariance_model = self.make_covariance_model(box)
        potential_data.gradients = GradientData(locations, values)
        potential_data.interfaces = [
            self._point_array(interface, f"interfaces[{index}]")
            for index, interface in enumerate(interfaces)
        ]
        return potential_data

    def make_series_data(
        self,
        name: str,
        *,
        formations: Iterable[str],
        relation: str,
        potential_data: GmlibPotentialData | None,
        influenced_by_faults: Iterable[str] = (),
    ) -> GmlibSeriesData:
        """Create a fully initialized legacy series data object."""
        if relation not in ("onlap", "erode"):
            raise ValueError("series relation must be 'onlap' or 'erode'")

        series_data = GmlibSeriesData(name)
        series_data.formations = list(formations)
        series_data.relation = relation
        influencing_faults = list(influenced_by_faults)
        series_data.influenced_by_fault = influencing_faults or None
        series_data.potential_data = potential_data
        return series_data

    def make_pile(self, reference: str, series: Iterable[GmlibSeriesData]) -> GmlibPile:
        """Create a fully initialized legacy stratigraphic pile."""
        pile = GmlibPile(reference)
        pile.all_series = list(series)
        return pile

    def make_infinite_fault_data(
        self,
        name: str,
        *,
        potential_data: GmlibPotentialData,
        stops_on: Iterable[str] = (),
    ) -> GmlibFaultData:
        """Create an infinite legacy fault data object."""
        fault_data = self._make_fault_data(name, potential_data, stops_on)
        fault_data.infinite = True
        return fault_data

    def make_finite_fault_data(
        self,
        name: str,
        *,
        potential_data: GmlibPotentialData,
        lateral_extent: float,
        vertical_extent: float,
        influence_radius: float,
        stops_on: Iterable[str] = (),
    ) -> GmlibFaultData:
        """Create a finite mean-centered legacy fault data object."""
        fault_data = self._make_fault_data(name, potential_data, stops_on)
        fault_data.infinite = False
        fault_data.center_type = "mean_center"
        fault_data.lateral_extent = self.scalar_dtype.type(lateral_extent)
        fault_data.vertical_extent = self.scalar_dtype.type(vertical_extent)
        fault_data.influence_radius = self.scalar_dtype.type(influence_radius)
        return fault_data

    @staticmethod
    def make_formation(name: str) -> Formation:
        """Create a non-dummy formation using the v1 compatibility colour."""
        return Formation(
            name=name,
            color=DEFAULT_FORMATION_COLOR,
            is_dummy=False,
        )

    @staticmethod
    def make_dummy_formation() -> Formation:
        """Create the v1 dummy formation expected by the legacy model."""
        return Formation(
            name=DUMMY_FORMATION_NAME,
            color=DEFAULT_FORMATION_COLOR,
            is_dummy=True,
        )

    @staticmethod
    def _make_fault_data(
        name: str,
        potential_data: GmlibPotentialData,
        stops_on: Iterable[str],
    ) -> GmlibFaultData:
        fault_data = GmlibFaultData(name)
        fault_data.potential_data = potential_data
        fault_data.stops_on = list(stops_on)
        fault_data.color = None
        return fault_data

    def _point_array(self, values: ArrayLike, name: str) -> np.ndarray:
        array = np.asarray(values, dtype=self.scalar_dtype)
        if array.ndim == 1 and array.size == 0:
            return array.reshape((0, 3))
        if array.ndim != 2 or array.shape[1] != 3:
            raise ValueError(f"{name} must have shape (N, 3)")
        return array
