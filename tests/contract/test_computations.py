from types import SimpleNamespace

import numpy as np
import pytest

import geocruncher.computations as computations
from tests.support import computations as computation_support

MODEL_METADATA = computation_support.MODEL_METADATA
assert_metadata_contains = computation_support.assert_metadata_contains
computation_fakes = computation_support.computation_fakes


######## Tests ########


def test_compute_meshes_builds_model_uses_custom_box_and_passes_metadata(
    monkeypatch, computation_fakes
):
    generated = {}

    def fake_generate_volumes(model, shape, box):
        generated["model"] = model
        generated["shape"] = shape
        generated["box"] = box
        return {"mesh": {"unit-1": b"unit"}, "fault": {"fault-a": b"fault"}}

    monkeypatch.setattr(computations, "generate_volumes", fake_generate_volumes)

    result = computations.compute_meshes(
        {
            "resolution": {"x": 2, "y": 3, "z": 4},
            "box": {
                "xmin": 1,
                "ymin": 2,
                "zmin": 3,
                "xmax": 4,
                "ymax": 5,
                "zmax": 6,
            },
        },
        xml="<xml />",
        dem="dem",
        metadata={"env": "test"},
    )

    assert result == {"mesh": {"unit-1": b"unit"}, "fault": {"fault-a": b"fault"}}
    assert computation_fakes.extracted == [("<xml />", "dem")]
    assert computation_fakes.models[0].project_data == {"xml": "<xml />", "dem": "dem"}
    assert computation_fakes.models[0].use_cache is False
    assert generated["model"] == computation_fakes.models[0]
    assert generated["shape"] == (2, 3, 4)
    assert generated["box"].as_tuple() == (1, 2, 3, 4, 5, 6)
    assert computation_fakes.profile_steps == ["load_model"]
    assert computation_fakes.profilers[0].metadata["resolution"] == 24
    assert computation_fakes.profilers[0].metadata["env"] == "test"
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        MODEL_METADATA,
    )
    assert computation_fakes.profilers[0].saved is True


def test_compute_meshes_uses_model_box_when_box_is_absent(
    monkeypatch, computation_fakes
):
    generated = {}

    def fake_generate_volumes(model, shape, box):
        generated["model"] = model
        generated["shape"] = shape
        generated["box"] = box
        return {"mesh": {}, "fault": {}}

    monkeypatch.setattr(computations, "generate_volumes", fake_generate_volumes)

    result = computations.compute_meshes(
        {"resolution": {"x": 1, "y": 2, "z": 3}},
        xml="xml",
        dem="dem",
    )

    assert result == {"mesh": {}, "fault": {}}
    assert generated["model"] is computation_fakes.models[0]
    assert generated["shape"] == (1, 2, 3)
    assert generated["box"] is computation_fakes.models[0].box
    assert computation_fakes.profile_steps == ["load_model"]
    assert computation_fakes.profilers[0].metadata["resolution"] == 6
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        MODEL_METADATA,
    )
    assert computation_fakes.profilers[0].saved is True


def test_compute_faults_uses_model_box_and_wraps_fault_output(
    monkeypatch, computation_fakes
):
    generated = {}

    def fake_generate_faults_files(model, shape, box):
        generated["model"] = model
        generated["shape"] = shape
        generated["box"] = box
        return {"fault-a": b"fault"}

    monkeypatch.setattr(
        computations, "generate_faults_files", fake_generate_faults_files
    )

    result = computations.compute_faults(
        {"resolution": {"x": 5, "y": 6, "z": 7}},
        xml="xml",
        dem="dem",
        metadata={"env": "test"},
    )

    assert result == {"mesh": {}, "fault": {"fault-a": b"fault"}}
    assert generated["model"] is computation_fakes.models[0]
    assert generated["shape"] == (5, 6, 7)
    assert generated["box"] is computation_fakes.models[0].box
    assert computation_fakes.profile_steps == ["load_model"]
    assert computation_fakes.profilers[0].metadata["resolution"] == 210
    assert computation_fakes.profilers[0].metadata["env"] == "test"
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        {
            "num_finite_faults": 4,
            "num_infinite_faults": 5,
            "num_stops_on_relations": 6,
            "num_contact_data": 7,
            "num_dips": 8,
        },
    )
    assert computation_fakes.profilers[0].saved is True


def test_compute_faults_uses_custom_box(monkeypatch, computation_fakes):
    generated = {}

    def fake_generate_faults_files(model, shape, box):
        generated["model"] = model
        generated["shape"] = shape
        generated["box"] = box
        return {"fault-a": b"fault"}

    monkeypatch.setattr(
        computations, "generate_faults_files", fake_generate_faults_files
    )

    result = computations.compute_faults(
        computations.MeshesData(
            resolution={"x": 2, "y": 3, "z": 4},
            box={
                "xmin": 11,
                "ymin": 12,
                "zmin": 13,
                "xmax": 14,
                "ymax": 15,
                "zmax": 16,
            },
        ),
        xml="xml",
        dem="dem",
    )

    assert result == {"mesh": {}, "fault": {"fault-a": b"fault"}}
    assert generated["model"] is computation_fakes.models[0]
    assert generated["shape"] == (2, 3, 4)
    assert generated["box"].as_tuple() == (11, 12, 13, 14, 15, 16)
    assert computation_fakes.profile_steps == ["load_model"]


def test_compute_voxels_passes_shape_box_gwbs_and_metadata(
    monkeypatch, computation_fakes
):
    voxel_call = {}

    class FakeVoxels:
        @staticmethod
        def output(model, shape, box, gwb_meshes):
            voxel_call["model"] = model
            voxel_call["shape"] = shape
            voxel_call["box"] = box
            voxel_call["gwb_meshes"] = gwb_meshes
            return "vox-output"

    monkeypatch.setattr(computations, "Voxels", FakeVoxels)

    gwb_meshes = {"10": [b"a"], "11": [b"b", b"c"]}
    result = computations.compute_voxels(
        {"resolution": {"x": 2, "y": 4, "z": 6}},
        xml="xml",
        dem="dem",
        gwb_meshes=gwb_meshes,
        metadata={"env": "test"},
    )

    assert result == "vox-output"
    assert voxel_call["model"] is computation_fakes.models[0]
    assert voxel_call["shape"] == (2, 4, 6)
    assert voxel_call["box"] is computation_fakes.models[0].box
    assert voxel_call["gwb_meshes"] is gwb_meshes
    assert computation_fakes.profile_steps == ["load_model"]
    assert computation_fakes.profilers[0].metadata["num_gwb_parts"] == 2
    assert computation_fakes.profilers[0].metadata["env"] == "test"
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        {
            "num_erode_series": 1,
            "num_onlap_series": 2,
            "num_units": 3,
        },
    )
    assert computation_fakes.profilers[0].saved is True


def test_compute_voxels_uses_custom_box(monkeypatch, computation_fakes):
    voxel_call = {}

    class FakeVoxels:
        @staticmethod
        def output(model, shape, box, gwb_meshes):
            voxel_call["model"] = model
            voxel_call["shape"] = shape
            voxel_call["box"] = box
            voxel_call["gwb_meshes"] = gwb_meshes
            return "vox-output"

    monkeypatch.setattr(computations, "Voxels", FakeVoxels)

    gwb_meshes = {"10": [b"mesh"]}
    result = computations.compute_voxels(
        computations.MeshesData(
            resolution={"x": 3, "y": 4, "z": 5},
            box={
                "xmin": 21,
                "ymin": 22,
                "zmin": 23,
                "xmax": 24,
                "ymax": 25,
                "zmax": 26,
            },
        ),
        xml="xml",
        dem="dem",
        gwb_meshes=gwb_meshes,
    )

    assert result == "vox-output"
    assert voxel_call["model"] is computation_fakes.models[0]
    assert voxel_call["shape"] == (3, 4, 5)
    assert voxel_call["box"].as_tuple() == (21, 22, 23, 24, 25, 26)
    assert voxel_call["gwb_meshes"] is gwb_meshes
    assert computation_fakes.profile_steps == ["load_model"]


def test_compute_gwb_meshes_delegates_to_geo_algo_and_profiles_metadata(
    monkeypatch, computation_fakes
):
    geo_algo_call = {}

    class FakeGeoAlgo:
        @staticmethod
        def output(unit_meshes, springs):
            geo_algo_call["unit_meshes"] = unit_meshes
            geo_algo_call["springs"] = springs
            return {
                "metadata": [{"unit_id": 7, "spring_id": 9, "volume": 12.5}],
                "meshes": [b"gwb"],
            }

    monkeypatch.setattr(computations, "GeoAlgo", FakeGeoAlgo)

    unit_meshes = {"7": b"unit"}
    springs = [
        computations.Spring(
            id=9, location=computations.Vec3Float(x=1, y=2, z=3), unit_id=7
        )
    ]

    result = computations.compute_gwb_meshes(
        unit_meshes, springs, metadata={"env": "test"}
    )

    assert result == {
        "metadata": [{"unit_id": 7, "spring_id": 9, "volume": 12.5}],
        "meshes": [b"gwb"],
    }
    assert geo_algo_call["unit_meshes"] is unit_meshes
    assert geo_algo_call["springs"] is springs
    assert computation_fakes.profilers[0].metadata == {
        "num_units": 1,
        "num_springs": 1,
        "env": "test",
    }
    assert computation_fakes.profilers[0].saved is True


def test_compute_tunnel_meshes_profiles_each_tunnel_and_applies_sub_tunnel_scale(
    monkeypatch, computation_fakes
):
    segment_calls = []
    mesh_calls = []

    monkeypatch.setattr(
        computations,
        "get_circle_segment",
        lambda radius, nb_vertices: (
            segment_calls.append(("circle", radius, nb_vertices)) or ["circle-segment"]
        ),
    )
    monkeypatch.setattr(
        computations,
        "get_rectangle_segment",
        lambda width, height, nb_vertices: (
            segment_calls.append(("rectangle", width, height, nb_vertices))
            or ["rectangle-segment"]
        ),
    )

    def fake_tunnel_to_meshes(
        functions, step, segment, idx_start, t_start, idx_end, t_end
    ):
        mesh_calls.append(
            {
                "functions": functions,
                "step": step,
                "segment": segment,
                "idx_start": idx_start,
                "t_start": t_start,
                "idx_end": idx_end,
                "t_end": t_end,
            }
        )
        return f"{segment[0]}-mesh".encode()

    monkeypatch.setattr(computations, "tunnel_to_meshes", fake_tunnel_to_meshes)

    result = computations.compute_tunnel_meshes(
        {
            "tunnels": [
                {
                    "name": "main",
                    "shape": computations.TunnelShape.CIRCLE,
                    "functions": [{"x": "t", "y": "0", "z": "0"}],
                    "radius": 2.0,
                },
                {
                    "name": "service",
                    "shape": computations.TunnelShape.RECTANGLE,
                    "functions": [
                        {"x": "t", "y": "0", "z": "0"},
                        {"x": "t", "y": "1", "z": "0"},
                    ],
                    "width": 4.0,
                    "height": 6.0,
                },
            ],
            "nb_vertices": 8,
            "step": 0.25,
            "idxStart": 1,
            "idxEnd": 2,
            "tStart": 0.5,
            "tEnd": 1.5,
        },
        metadata={"env": "test"},
    )

    assert result == {
        "main": b"circle-segment-mesh",
        "service": b"rectangle-segment-mesh",
    }

    assert segment_calls == [
        ("circle", pytest.approx(2.2), 8),
        ("rectangle", pytest.approx(4.4), pytest.approx(6.6), 8),
    ]

    assert [call["segment"] for call in mesh_calls] == [
        ["circle-segment"],
        ["rectangle-segment"],
    ]
    assert [call["functions"] for call in mesh_calls] == [
        [{"x": "t", "y": "0", "z": "0"}],
        [
            {"x": "t", "y": "0", "z": "0"},
            {"x": "t", "y": "1", "z": "0"},
        ],
    ]

    expected_mesh_args = {
        "step": 0.25,
        "idx_start": 1,
        "t_start": 0.5,
        "idx_end": 2,
        "t_end": 1.5,
    }
    assert [{key: call[key] for key in expected_mesh_args} for call in mesh_calls] == [
        expected_mesh_args,
        expected_mesh_args,
    ]

    assert [profiler.metadata["shape"] for profiler in computation_fakes.profilers] == [
        computations.TunnelShape.CIRCLE,
        computations.TunnelShape.RECTANGLE,
    ]

    assert [
        profiler.metadata["num_waypoints"] for profiler in computation_fakes.profilers
    ] == [2, 3]

    assert all(
        profiler.metadata["env"] == "test" for profiler in computation_fakes.profilers
    )

    assert all(profiler.saved for profiler in computation_fakes.profilers)


def test_compute_tunnel_meshes_elliptic_tunnel_without_sub_tunnel_scale_when_start_is_minus_one(
    monkeypatch, computation_fakes
):
    segment_calls = []
    mesh_calls = []

    monkeypatch.setattr(
        computations,
        "get_elliptic_segment",
        lambda width, height, nb_vertices: (
            segment_calls.append(("elliptic", width, height, nb_vertices))
            or ["elliptic-segment"]
        ),
    )

    def fake_tunnel_to_meshes(
        functions, step, segment, idx_start, t_start, idx_end, t_end
    ):
        mesh_calls.append(
            {
                "functions": functions,
                "step": step,
                "segment": segment,
                "idx_start": idx_start,
                "t_start": t_start,
                "idx_end": idx_end,
                "t_end": t_end,
            }
        )
        return b"elliptic-mesh"

    monkeypatch.setattr(computations, "tunnel_to_meshes", fake_tunnel_to_meshes)

    functions = [computations.TunnelFunction(x="t", y="t + 1", z="0")]
    data = computations.TunnelMeshesData(
        tunnels=[
            computations.Tunnel(
                name="bypass",
                shape=computations.TunnelShape.ELLIPTIC,
                functions=functions,
                width=4.0,
                height=6.0,
            )
        ],
        nb_vertices=12,
        step=0.5,
        idxStart=-1,
        idxEnd=3,
        tStart=0.0,
        tEnd=2.0,
    )
    result = computations.compute_tunnel_meshes(
        data,
        metadata={"env": "test"},
    )

    assert result == {"bypass": b"elliptic-mesh"}
    assert segment_calls == [("elliptic", 4.0, 6.0, 12)]
    assert mesh_calls == [
        {
            "functions": functions,
            "step": 0.5,
            "segment": ["elliptic-segment"],
            "idx_start": -1,
            "t_start": 0.0,
            "idx_end": 3,
            "t_end": 2.0,
        }
    ]
    assert computation_fakes.profilers[0].metadata["shape"] == (
        computations.TunnelShape.ELLIPTIC
    )
    assert computation_fakes.profilers[0].metadata["num_waypoints"] == 2
    assert computation_fakes.profilers[0].metadata["env"] == "test"
    assert computation_fakes.profilers[0].saved is True


def test_compute_intersections_without_hydro_or_map_skips_optional_branches(
    monkeypatch, computation_fakes
):
    vertical_xyz = np.array([[1, 2, 3]])
    calls = SimpleNamespace(
        resolutions=[],
        vertical_slices=[],
        rank_calls=[],
        fault_calls=[],
        hydro_calls=[],
        map_calls=[],
    )

    def fake_calculate_resolution(width, height, target):
        calls.resolutions.append((width, height, target))
        return (3, 4)

    def fake_compute_vertical_slice_points(x_coord, y_coord, z_coord, resolution):
        calls.vertical_slices.append((x_coord, y_coord, z_coord, resolution))
        return vertical_xyz

    def fake_compute_cross_section_ranks(xyz, resolution, model, topography):
        calls.rank_calls.append((xyz, resolution, model, topography))
        return [["rank"]]

    def fake_compute_fault_intersections(xyz, resolution, model):
        calls.fault_calls.append((xyz, resolution, model))
        return [{"fault": [[0.5]]}]

    monkeypatch.setattr(computations, "calculate_resolution", fake_calculate_resolution)
    monkeypatch.setattr(
        computations,
        "compute_vertical_slice_points",
        fake_compute_vertical_slice_points,
    )
    monkeypatch.setattr(
        computations, "compute_cross_section_ranks", fake_compute_cross_section_ranks
    )
    monkeypatch.setattr(
        computations, "compute_fault_intersections", fake_compute_fault_intersections
    )
    monkeypatch.setattr(
        computations,
        "project_hydro_features_on_slice",
        lambda *args: calls.hydro_calls.append(args),
    )
    monkeypatch.setattr(
        computations, "compute_map_points", lambda *args: calls.map_calls.append(args)
    )

    result = computations.compute_intersections(
        {
            "resolution": 50,
            "toCompute": {
                "section-a": [
                    {
                        "xmin": 1.2,
                        "ymin": 3.8,
                        "zmin": 5.2,
                        "xmax": 11.7,
                        "ymax": 3.8,
                        "zmax": 25.8,
                    }
                ]
            },
            "computeMap": False,
        },
        xml="xml",
        dem="dem",
        gwb_meshes={},
        metadata={"env": "test"},
    )

    assert result == {
        "mesh": {
            "forCrossSections": {"section-a": [[["rank"]]]},
            "drillholes": {"section-a": []},
            "springs": {"section-a": []},
            "matrixGwb": {"section-a": []},
        },
        "fault": {
            "forCrossSections": {"section-a": [[{"fault": [[0.5]]}]]},
            "forMaps": {},
        },
    }
    assert calls.resolutions == [(11.0, 21, 50)]
    assert calls.vertical_slices == [((1, 12), (4, 4), (5, 26), (3, 4))]
    assert calls.hydro_calls == []
    assert calls.map_calls == []
    assert calls.rank_calls[0][2] is computation_fakes.models[0]
    assert calls.rank_calls[0][3] is True
    assert calls.fault_calls[0][2] is computation_fakes.models[0]
    assert computation_fakes.profile_steps == ["load_model", "cross_section_grid"]
    assert computation_fakes.profilers[0].metadata["compute_map"] is False
    assert computation_fakes.profilers[0].metadata["num_gwb_parts"] == 0
    assert computation_fakes.profilers[0].metadata["env"] == "test"
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        MODEL_METADATA,
    )
    assert computation_fakes.profilers[0].saved is True


def test_compute_intersections_with_only_gwb_meshes_runs_hydro_projection(
    monkeypatch, computation_fakes
):
    vertical_xyz = np.array([[1, 2, 3]])
    hydro_calls = []

    monkeypatch.setattr(
        computations, "calculate_resolution", lambda width, height, target: (2, 3)
    )
    monkeypatch.setattr(
        computations,
        "compute_vertical_slice_points",
        lambda x_coord, y_coord, z_coord, resolution: vertical_xyz,
    )
    monkeypatch.setattr(
        computations,
        "compute_cross_section_ranks",
        lambda xyz, resolution, model, topography: [["rank"]],
    )
    monkeypatch.setattr(
        computations,
        "compute_fault_intersections",
        lambda xyz, resolution, model: [{"fault": [[1.0]]}],
    )

    def fake_project_hydro_features_on_slice(
        lower_left,
        upper_right,
        xyz,
        springs,
        drillholes,
        gwb_meshes,
        max_dist_proj,
    ):
        hydro_calls.append(
            {
                "lower_left": lower_left.copy(),
                "upper_right": upper_right.copy(),
                "springs": springs,
                "drillholes": drillholes,
                "gwb_meshes": gwb_meshes,
                "max_dist_proj": max_dist_proj,
            }
        )
        return {}, {}, [12]

    monkeypatch.setattr(
        computations,
        "project_hydro_features_on_slice",
        fake_project_hydro_features_on_slice,
    )

    gwb_meshes = {"12": [b"mesh"]}
    result = computations.compute_intersections(
        {
            "resolution": 20,
            "toCompute": {
                "section-a": [
                    {
                        "xmin": 0,
                        "ymin": 0,
                        "zmin": 0,
                        "xmax": 10,
                        "ymax": 0,
                        "zmax": 5,
                    }
                ]
            },
            "computeMap": False,
        },
        xml="xml",
        dem="dem",
        gwb_meshes=gwb_meshes,
    )

    assert result["mesh"]["drillholes"] == {"section-a": [{}]}
    assert result["mesh"]["springs"] == {"section-a": [{}]}
    assert result["mesh"]["matrixGwb"] == {"section-a": [[12]]}
    assert len(hydro_calls) == 1
    np.testing.assert_array_equal(hydro_calls[0]["lower_left"], np.array([0, 0, 0]))
    np.testing.assert_array_equal(hydro_calls[0]["upper_right"], np.array([10, 0, 5]))
    assert hydro_calls[0]["springs"] == {}
    assert hydro_calls[0]["drillholes"] == {}
    assert hydro_calls[0]["gwb_meshes"] == gwb_meshes
    assert hydro_calls[0]["max_dist_proj"] == pytest.approx(40.0)
    assert computation_fakes.profilers[0].metadata["num_springs"] == 0
    assert computation_fakes.profilers[0].metadata["num_drillholes"] == 0
    assert computation_fakes.profilers[0].metadata["num_gwb_parts"] == 1


def test_compute_intersections_with_hydro_and_map_populates_optional_outputs(
    monkeypatch, computation_fakes
):
    vertical_xyz = np.array([[1, 2, 3]])
    map_xyz = np.array([[4, 5, 6]])
    hydro_calls = []
    rank_calls = []
    fault_calls = []
    map_calls = []

    monkeypatch.setattr(
        computations,
        "calculate_resolution",
        lambda width, height, target: (int(width) + target, int(height) + target),
    )
    monkeypatch.setattr(
        computations,
        "compute_vertical_slice_points",
        lambda x_coord, y_coord, z_coord, resolution: vertical_xyz,
    )

    def fake_compute_cross_section_ranks(xyz, resolution, model, topography):
        rank_calls.append((xyz, resolution, model, topography))
        return [["map-rank" if not topography else "section-rank"]]

    def fake_compute_fault_intersections(xyz, resolution, model):
        fault_calls.append((xyz, resolution, model))
        return [{"fault": [[float(resolution[0])]]}]

    def fake_project_hydro_features_on_slice(
        lower_left,
        upper_right,
        xyz,
        springs,
        drillholes,
        gwb_meshes,
        max_dist_proj,
    ):
        hydro_calls.append(
            {
                "lower_left": lower_left.copy(),
                "upper_right": upper_right.copy(),
                "xyz": xyz,
                "springs": springs,
                "drillholes": drillholes,
                "gwb_meshes": gwb_meshes,
                "max_dist_proj": max_dist_proj,
            }
        )
        return {"dh": [[0, 1]]}, {"spring": [2, 3]}, [9]

    def fake_compute_map_points(box, resolution, model):
        map_calls.append((box, resolution, model))
        return map_xyz

    monkeypatch.setattr(
        computations, "compute_cross_section_ranks", fake_compute_cross_section_ranks
    )
    monkeypatch.setattr(
        computations, "compute_fault_intersections", fake_compute_fault_intersections
    )
    monkeypatch.setattr(
        computations,
        "project_hydro_features_on_slice",
        fake_project_hydro_features_on_slice,
    )
    monkeypatch.setattr(computations, "compute_map_points", fake_compute_map_points)

    springs = {"spring": computations.Vec3Float(x=2, y=3, z=4)}
    drillholes = {
        "dh": computations.BoxDict(xmin=1, ymin=2, zmin=3, xmax=4, ymax=5, zmax=6)
    }
    gwb_meshes = {"9": [b"mesh"]}

    result = computations.compute_intersections(
        computations.IntersectionsData(
            resolution=10,
            springs=springs,
            drillholes=drillholes,
            toCompute={
                "vertical": [
                    {
                        "xmin": 2,
                        "ymin": 5,
                        "zmin": 0,
                        "xmax": 2,
                        "ymax": 5,
                        "zmax": 4,
                    }
                ]
            },
            computeMap=True,
        ),
        xml="xml",
        dem="dem",
        gwb_meshes=gwb_meshes,
    )

    assert result["mesh"]["forCrossSections"] == {"vertical": [[["section-rank"]]]}
    assert result["mesh"]["drillholes"] == {"vertical": [{"dh": [[0, 1]]}]}
    assert result["mesh"]["springs"] == {"vertical": [{"spring": [2, 3]}]}
    assert result["mesh"]["matrixGwb"] == {"vertical": [[9]]}
    assert result["mesh"]["forMaps"] == [["map-rank"]]
    assert result["fault"]["forMaps"] == [{"fault": [[110.0]]}]

    np.testing.assert_array_equal(hydro_calls[0]["xyz"], vertical_xyz)
    np.testing.assert_array_equal(hydro_calls[0]["lower_left"], np.array([1, 4, 0]))
    np.testing.assert_array_equal(hydro_calls[0]["upper_right"], np.array([3, 6, 4]))
    assert hydro_calls[0]["springs"] == springs
    assert hydro_calls[0]["drillholes"] == drillholes
    assert hydro_calls[0]["gwb_meshes"] == gwb_meshes
    assert hydro_calls[0]["max_dist_proj"] == pytest.approx(40.0)

    assert map_calls[0][0] is computation_fakes.models[0].box
    assert map_calls[0][1] == (110, 210)
    assert map_calls[0][2] is computation_fakes.models[0]

    np.testing.assert_array_equal(rank_calls[0][0], vertical_xyz)
    assert rank_calls[0][1:] == ((10, 14), computation_fakes.models[0], True)
    np.testing.assert_array_equal(rank_calls[1][0], map_xyz)
    assert rank_calls[1][1:] == ((110, 210), computation_fakes.models[0], False)

    np.testing.assert_array_equal(fault_calls[0][0], vertical_xyz)
    assert fault_calls[0][1] == (10, 14)
    assert fault_calls[0][2] is computation_fakes.models[0]
    np.testing.assert_array_equal(fault_calls[1][0], map_xyz)
    assert fault_calls[1][1] == (110, 210)
    assert fault_calls[1][2] is computation_fakes.models[0]

    assert computation_fakes.profile_steps == [
        "load_model",
        "cross_section_grid",
        "map_grid",
    ]
    assert computation_fakes.profilers[0].metadata["compute_map"] is True
    assert computation_fakes.profilers[0].metadata["num_springs"] == 1
    assert computation_fakes.profilers[0].metadata["num_drillholes"] == 1
    assert computation_fakes.profilers[0].metadata["num_gwb_parts"] == 1
    assert_metadata_contains(
        computation_fakes.profilers[0].metadata,
        MODEL_METADATA,
    )
    assert computation_fakes.profilers[0].saved is True


class TestKarstNSimDataContract:
    def test_required_top_level_fields(self, karst_nsim_data_dict):
        from geocruncher.computations import KarstNSimData

        data = KarstNSimData.model_validate(karst_nsim_data_dict)
        # all fields must be present and non-empty
        assert data.simulation_params is not None
        assert data.project_box is not None
        assert data.dem_resolution is not None
        assert data.stratigraphy
        assert data.voxels_header is not None
        assert data.voxels_units
        assert data.fault_ids
        assert data.springs
        assert data.gwbs

    def test_simulation_params_camel_case_aliases(self):
        from geocruncher.computations import KarstNSimData

        payload = {
            "simulation_params": {
                "kPts": 15,
                "cohesionFactor": 0.8,
                "nSinks": 200,
                "seed": 99,
                "searchRadius": "auto",
                "inceptionSurfaceConstraintWeight": 1.0,
                "maxInceptionSurfaceDistance": "auto",
                "rMinPervious": "auto",
                "rMinImpervious": "auto",
            },
            "project_box": {
                "width": 1000,
                "height": 1000,
                "min_elevation": 0,
                "max_elevation": 500,
            },
            "dem_resolution": {"n_cols": 10, "n_rows": 10},
            "stratigraphy": [
                {"name": "Unit", "permeability": "Karstified", "stratiUnitId": 1}
            ],
            "voxels_header": {
                "xmin": 0,
                "xmax": 1000,
                "ymin": 0,
                "ymax": 1000,
                "zmin": 0,
                "zmax": 500,
                "nx": 5,
                "ny": 5,
                "nz": 5,
                "novalue": 0,
            },
            "voxels_units": [1],
            "fault_ids": [1],
            "springs": [
                {
                    "poi_id": 1,
                    "x": 500,
                    "y": 500,
                    "z": 100,
                    "catchment": [[0, 0], [0, 1000], [1000, 1000], [0, 0]],
                }
            ],
            "gwbs": [{"gwb_id": 1, "spring_id": 1}],
        }
        data = KarstNSimData.model_validate(payload)
        assert data.simulation_params.k_pts == 15
        assert data.simulation_params.cohesion_factor == 0.8
        assert data.simulation_params.n_sinks == 200
