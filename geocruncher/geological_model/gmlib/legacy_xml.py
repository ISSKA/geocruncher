"""Legacy GeoModeller XML importer adapted from gmlib.

It accepts XML and DEM content directly instead of reading files. It is no longer
used by GeoCruncher's production code paths and is retained only as a regression
oracle for legacy XML parity. Remove it once that parity is no longer a migration
concern.
"""

import lxml.etree as etree
import numpy as np
from forgeo.gmlib.geomodeller_project import (
    extract_crs,
    nsmap,
    read_box,
    read_formations,
    read_modeled_faults_data,
    read_pile,
)

from .topography import ascii_grid_to_implicit_dtm

type XmlInput = bytes | str


def extract_tree(xml: XmlInput):
    root = etree.fromstring(xml)
    for ns, uri in nsmap.items():
        assert ns in root.nsmap
        assert root.nsmap[ns] == uri
    return root


def extract_project_data(xml: XmlInput, dem: str, scalardt=np.dtype("d")):
    root = extract_tree(xml)
    crs = extract_crs(root)
    box = read_box(root)
    faults_data = read_modeled_faults_data(root, box, scalardt)
    pile = read_pile(root, box, scalardt)
    topography = ascii_grid_to_implicit_dtm(dem)
    formations = read_formations(root)
    return {
        "box": box,
        "crs": crs,
        "pile": pile,
        "faults_data": faults_data,
        "topography": topography,
        "formations": formations,
    }
