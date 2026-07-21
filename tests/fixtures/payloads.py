MESHES_DATA = {"resolution": {"x": 2, "y": 3, "z": 4}}

INTERSECTIONS_DATA = {
    "resolution": 25,
    "toCompute": {
        "section-a": [
            {
                "xmin": 0,
                "ymin": 1,
                "zmin": 2,
                "xmax": 10,
                "ymax": 11,
                "zmax": 12,
            }
        ]
    },
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

KARSTNSIM_DATA = {
    "simulation_params": {"seed": 7, "nSinks": 1},
    "project_box": {
        "width": 10.0,
        "height": 10.0,
        "min_elevation": 0.0,
        "max_elevation": 10.0,
    },
    "dem_resolution": {"x": 2, "y": 2},
    "stratigraphy": [{"name": "Unit", "permeability": "Karstified", "stratiUnitId": 1}],
    "voxels_header": {
        "xmin": 0.0,
        "xmax": 10.0,
        "ymin": 0.0,
        "ymax": 10.0,
        "zmin": 0.0,
        "zmax": 10.0,
        "nx": 1,
        "ny": 1,
        "nz": 1,
        "novalue": 0,
    },
    "voxels_units": [1],
    "fault_ids": [1],
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
}

KARSTNSIM_DEM_BYTES = b"dem-bytes"
KARSTNSIM_VOXELS_STR = "header\nrank gwb_id\n1 1\n"
KARSTNSIM_FAULT_BYTES = {1: b"fault-bytes"}
