# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

import re
from io import StringIO

import numpy as np
from gmlib.topography_reader import ImplicitDTM


def ascii_grid_to_implicit_dtm(dem: str) -> ImplicitDTM:
    """Read ASCIIGrid DEM datapoints and return a GMLIB ImplicitDTM."""
    with StringIO(dem) as f:
        # We do not actually care about the first 2 line (ncols, nrows), skip them
        f.readline()
        f.readline()
        xllcorner = float(re.findall(r"-?\d+\.?\d+", f.readline())[0])
        yllcorner = float(re.findall(r"-?\d+\.?\d+", f.readline())[0])
        cellsize = float(re.findall(r"\d+\.?\d*", f.readline())[0])
        f.readline()
        zmap = []
        line = f.readline().strip().split()
        while line:
            reversed_arr = np.array([float(s) for s in line])
            zmap.append(reversed_arr)
            line = f.readline().strip().split()
        zmap = np.array(zmap[::-1])

        return ImplicitDTM((xllcorner, yllcorner), (float(cellsize), float(cellsize)), zmap.transpose())
