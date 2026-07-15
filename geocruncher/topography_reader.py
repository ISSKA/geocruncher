# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

import logging
import re
from io import StringIO

import numpy as np
from forgeo.gmlib.topography_reader import ImplicitDTM

logger = logging.getLogger(__name__)


def _header_float(pattern: str, line: str) -> float:
    match = re.search(pattern, line)
    if match is None:
        raise ValueError(f"Invalid ASCIIGrid header line: {line}")
    return float(match[0])


def ascii_grid_to_implicit_dtm(dem: str) -> ImplicitDTM:
    """Read ASCIIGrid DEM datapoints and return a GMLIB ImplicitDTM."""

    USEFUL_HEADERS = {"xllcorner", "yllcorner", "cellsize", "dx", "dy"}

    headers: dict[str, float] = {}
    lines = dem.splitlines()

    offset = 0
    for line in lines:
        keyword, _, value = line.strip().partition(" ")
        # Stop parsing headers when we reach the first line that starts with a number (first line of the data section)
        if re.match(r"^[-\d]|^[+-]?(nan|inf)", keyword, re.IGNORECASE):
            break
        try:
            parsed = float(value.strip())
        except ValueError:
            break
        if keyword.lower() in USEFUL_HEADERS:
            headers[keyword.lower()] = parsed
        offset += 1

    xllcorner = headers["xllcorner"]
    yllcorner = headers["yllcorner"]

    if "cellsize" in headers:
        dx = dy = headers["cellsize"]
    elif "dx" in headers and "dy" in headers:
        dx, dy = headers["dx"], headers["dy"]

    data_string = "\n".join(lines[offset:])
    zmap = np.loadtxt(StringIO(data_string), dtype=np.float64)
    zmap = zmap[::-1].T

    return ImplicitDTM((xllcorner, yllcorner), (dx, dy), zmap)
