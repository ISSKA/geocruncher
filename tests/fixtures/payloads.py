import numpy as np

BOX = {
    "xmin": 0,
    "ymin": 1,
    "zmin": 2,
    "xmax": 10,
    "ymax": 11,
    "zmax": 12,
}

MESHES_DATA = {"resolution": {"x": 2, "y": 3, "z": 4}, "box": BOX}

INTERSECTIONS_DATA = {
    "resolution": 25,
    "box": BOX,
    "toCompute": {"section-a": [BOX]},
    "computeMap": False,
    "springs": {"7": {"x": 1, "y": 2, "z": 3}},
}

TUNNEL_MESHES_DATA = {
    "tunnels": [
        {
            "name": "main",
            "shape": "Circle",
            "functions": [{"x": "t", "y": "0", "z": "0"}],
            "radius": 2.0,
        }
    ],
    "nb_vertices": 8,
    "step": 0.5,
    "idxStart": -1,
    "idxEnd": -1,
    "tStart": 0.0,
    "tEnd": 1.0,
}

GWB_MESHES_DATA = [{"id": 9, "location": {"x": 1, "y": 2, "z": 3}, "unit_id": 1}]

GENERATED_NETWORK_DATA = {
    "generation_params": {"seed": 7, "n_sinks": 1},
    "project_box": {
        "width": 10.0,
        "height": 10.0,
        "min_elevation": 0.0,
        "max_elevation": 10.0,
    },
    "dem_resolution": {
        "x": 4,
        "y": 4,
    },
    "stratigraphy": [
        {"name": "Unit", "permeability": "Karstified", "strati_unit_id": 1}
    ],
    "voxels_units": [1, 1, 1, 1],
    "fault_ids": [1, 2],
    "springs": [
        {
            "poi_id": 1,
            "x": 5.0,
            "y": 5.0,
            "z": 1.0,
            "catchment": [[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [0.0, 0.0]],
        }
    ],
    "gwbs": [{"gwb_id": 1, "spring_id": 1}],
    "is_base": False,
}

GENERATED_NETWORK_DEM_BYTES = np.array(
    [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16],
    ],
    dtype=np.float32,
).tobytes()

GENERATED_NETWORK_VOXELS_STR = """
XMIN=0 XMAX=10 YMIN=0 YMAX=10 ZMIN=0 ZMAX=10 NUMBERX=2 NUMBERY=2 NUMBERZ=1 NOVALUE=0
rank gwb_id
1 10
2 20
3 30
4 40
""".strip()

GENERATED_NETWORK_FAULT_BYTES = {1: b"fault 1 data", 2: b"fault 2 data"}
