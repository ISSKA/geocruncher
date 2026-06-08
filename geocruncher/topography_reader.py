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

    lines = dem.splitlines()
    # We do not actually care about the first 2 line (ncols, nrows), skip them
    xllcorner = _header_float(r"-?\d+\.?\d*", lines[2])
    yllcorner = _header_float(r"-?\d+\.?\d*", lines[3])
    cellsize = _header_float(r"\d+\.?\d*", lines[4])

    offset = 5  # Skip the required header lines
    if len(lines) > offset and lines[offset].strip().startswith("NODATA_value"):
        logger.warning("Skipping NODATA_value line")
        offset += 1

    data_string = "\n".join(lines[offset:])
    zmap = np.loadtxt(StringIO(data_string), dtype=np.float64)
    zmap = zmap[::-1].T

    return ImplicitDTM((xllcorner, yllcorner), (float(cellsize), float(cellsize)), zmap)
