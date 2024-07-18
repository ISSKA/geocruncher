"""
    Adapted from GMLIB geomodeller_project.py and topography_reader.py
    to allow importing from strings instead of files
"""

import numpy as np
import lxml.etree as etree
from gmlib.geomodeller_project import nsmap, extract_crs, read_box, read_modeled_faults_data, read_pile, read_formations
from .topography_reader import ascii_grid_to_implicit_dtm


def extract_tree(xml: str):
    root = etree.fromstring(xml)
    for ns, uri in nsmap.items():
        assert ns in root.nsmap
        assert root.nsmap[ns] == uri
    return root


def extract_project_data(xml: str, dem: str, scalardt=np.dtype("d")):
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
