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


def ascii_grid_to_implicit_dtm(dem: str) -> ImplicitDTM:
    """Read ASCIIGrid DEM datapoints and return a GMLIB ImplicitDTM."""

    USEFUL_HEADERS = {"xllcorner", "yllcorner", "cellsize", "dx", "dy"}

    headers: dict[str, float] = {}
    lines = dem.splitlines()

    offset = 0
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Invalid header line: {line!r}")

        keyword, value = parts
        # Stop parsing headers when we reach the first line that starts with a number (first line of the data section)
        if re.match(r"^[-\d]|^[+-]?(nan|inf)", keyword, re.IGNORECASE):
            break
        try:
            parsed = float(value.strip())
        except ValueError as e:
            raise ValueError(
                f"Invalid value for header '{keyword}': {value!r} in DEM"
            ) from e
        if keyword.lower() in USEFUL_HEADERS:
            headers[keyword.lower()] = parsed
        offset += 1

    try:
        xllcorner = headers["xllcorner"]
        yllcorner = headers["yllcorner"]
    except KeyError as e:
        raise ValueError(f"Missing required header: {e.args[0]} in DEM") from e

    if "cellsize" in headers:
        dx = dy = headers["cellsize"]
    elif "dx" in headers and "dy" in headers:
        dx, dy = headers["dx"], headers["dy"]
    else:
        raise ValueError("Missing cellsize or dx/dy header in DEM.")

    data_string = "\n".join(lines[offset:])
    zmap = np.loadtxt(StringIO(data_string), dtype=np.float64)
    zmap = zmap[::-1].T

    return ImplicitDTM((xllcorner, yllcorner), (dx, dy), zmap)
