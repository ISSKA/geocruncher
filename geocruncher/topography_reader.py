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
        
    lines = dem.splitlines()
    # We do not actually care about the first 2 line (ncols, nrows), skip them
    xllcorner = float(re.search(r"-?\d+\.?\d*", lines[2])[0])
    yllcorner = float(re.search(r"-?\d+\.?\d*", lines[3])[0])
    cellsize = float(re.search(r"\d+\.?\d*", lines[4])[0])
    
    data_string = '\n'.join(lines[6:])
    zmap = np.loadtxt(StringIO(data_string), dtype=np.float64)
    zmap = zmap[::-1].T

    return ImplicitDTM((xllcorner, yllcorner), (float(cellsize), float(cellsize)), zmap)