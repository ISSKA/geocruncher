import typing
from dataclasses import dataclass

import pykarstnsim_core


@dataclass
class Waypoint:
    origin: pykarstnsim_core.Vector3
    radius: typing.Optional[float] = None
    impact_radius: typing.Optional[float] = None
