import json
import logging
import tarfile
from io import BytesIO

from celery.result import AsyncResult, states
from flask import Flask, Response, jsonify, request, send_file
from pydantic import TypeAdapter, ValidationError

from geocruncher.contracts import (
    EvaluationExtent,
    EvaluationExtentValidationError,
    IntersectionsData,
    MeshesData,
    Spring,
    TunnelMeshesData,
    validate_evaluation_extent,
)
from geocruncher.geological_model.gmlib.adapter import load_trusted_gmlib_model
from geocruncher.geological_model.input import (
    GeologicalModelValidationError,
    parse_geological_model,
)
from geocruncher.profiler.predict import DurationPredictor
from geocruncher.profiler.util import MetadataHelpers

from . import tasks
from .redis import redis_client as r
from .utils import (
    generate_key,
    get_bytes,
    get_hash_bytes,
    hset_bytes,
    parse_metadata_from_request,
)

app = Flask(__name__)
logger = logging.getLogger(__name__)
predictor: DurationPredictor | None = None

_meshes_adapter = TypeAdapter(MeshesData)
_tunnel_meshes_adapter = TypeAdapter(TunnelMeshesData)
_intersections_adapter = TypeAdapter(IntersectionsData)
_gwb_meshes_adapter = TypeAdapter(list[Spring])


def load_duration_predictor() -> None:
    """Load duration models created by training script"""
    global predictor
    try:
        predictor = DurationPredictor()
    except (FileNotFoundError, RuntimeError, ValueError):
        logger.exception("Could not load duration models")
        predictor = None


def get_duration_predictor() -> DurationPredictor | None:
    if predictor is None:
        load_duration_predictor()
    return predictor


load_duration_predictor()


def gwb_part_count() -> int:
    ids = {key.split("_", 1)[0] for key in request.files if key not in {"model", "dem"}}
    return len(ids)


def uploaded_mesh_sizes() -> list[int]:
    sizes = []
    for key, file in request.files.items():
        if key in {"model", "dem"}:
            continue
        position = file.stream.tell()
        content = file.read()
        file.stream.seek(position)
        sizes.append(len(content))
    return sizes


def uploaded_mesh_features() -> dict[str, int | float]:
    sizes = uploaded_mesh_sizes()
    total = sum(sizes)
    return {
        "total_mesh_bytes": total,
        "mesh_bytes_per_unit": total / len(sizes) if sizes else 0,
    }


def data_adapter(computation_type):
    adapters = {
        "meshes": _meshes_adapter,
        "faults": _meshes_adapter,
        "voxels": _meshes_adapter,
        "intersections": _intersections_adapter,
        "tunnel_meshes": _tunnel_meshes_adapter,
        "gwb_meshes": _gwb_meshes_adapter,
    }
    try:
        return adapters[computation_type]
    except KeyError:
        raise ValueError(f"Unknown computation type: {computation_type!r}") from None


def sum_estimates(estimates: list[dict]) -> dict:
    if len(estimates) == 1:
        return {
            key: estimates[0][key] for key in ("lower", "p10", "p50", "p90", "upper")
        }
    return {
        key: sum(estimate[key] for estimate in estimates)
        for key in ("lower", "p10", "p50", "p90", "upper")
    }


def model_factors(computation_type, data, model, gwb_part_count):
    predictor = get_duration_predictor()
    if predictor is None:
        raise RuntimeError("Duration models are not initialized")
    features = set(predictor.meta["features"][computation_type])
    factors = {}
    if computation_type in {"meshes", "faults", "voxels", "intersections"}:
        factors.update(
            {
                "num_units": MetadataHelpers.num_units(model),
                "num_fault_unit_pairs": MetadataHelpers.num_fault_unit_pairs(model),
                "num_infinite_faults": MetadataHelpers.num_infinite_faults(model),
                "num_dips": MetadataHelpers.num_dips(
                    model, unit=computation_type != "faults"
                ),
                "num_finite_faults": MetadataHelpers.num_finite_faults(model),
                "num_contact_data": MetadataHelpers.num_contact_data(
                    model, unit=computation_type != "faults"
                ),
                "num_stops_on_relations": MetadataHelpers.num_stops_on_relations(model),
            }
        )
    if computation_type in {"meshes", "voxels", "intersections"}:
        factors.update(
            {
                "num_erode_series": MetadataHelpers.num_erode_series(model),
                "num_onlap_series": MetadataHelpers.num_onlap_series(model),
            }
        )
    if computation_type in {"meshes", "faults", "voxels"}:
        resolution = data["resolution"]
        factors.update(
            {
                "resolution_x": resolution["x"],
                "resolution_y": resolution["y"],
                "resolution_z": resolution["z"],
                "resolution": resolution["x"] * resolution["y"] * resolution["z"],
            }
        )
    if computation_type in {"meshes", "faults", "voxels", "intersections"}:
        box = data["box"]
        size_x = box["xmax"] - box["xmin"]
        size_y = box["ymax"] - box["ymin"]
        size_z = box["zmax"] - box["zmin"]
        factors.update(
            {
                "box_size_x": size_x,
                "box_size_y": size_y,
                "box_size_z": size_z,
                "box_volume": size_x * size_y * size_z,
            }
        )
    if computation_type == "voxels":
        factors["num_gwb_parts"] = gwb_part_count
    if computation_type == "intersections":
        factors.update(
            {
                "resolution": data["resolution"],
                "num_gwb_parts": gwb_part_count,
                "compute_map": data["computeMap"],
                "num_springs": len(data.get("springs") or {}),
                "num_drillholes": len(data.get("drillholes") or {}),
                "num_sections": len(data["toCompute"]),
            }
        )
    return {
        "computation_type": computation_type,
        **{name: factors[name] for name in features},
    }


def estimate_request(computation_type):
    predictor = get_duration_predictor()
    if predictor is None:
        return Response(
            "Duration models are not initialized", 503, mimetype="text/plain"
        )

    raw_data = request.form.get("data")
    if raw_data is None:
        return Response("Missing form field: data", 400, mimetype="text/plain")
    try:
        data = data_adapter(computation_type).validate_json(raw_data)
    except (ValidationError, ValueError) as error:
        return Response(str(error), 400, mimetype="text/plain")

    try:
        if computation_type == "tunnel_meshes":
            estimates = [
                predictor.predict(
                    {
                        "computation_type": computation_type,
                        "num_waypoints": len(tunnel["functions"]) + 1,
                        "shape": tunnel["shape"],
                    }
                )
                for tunnel in data["tunnels"]
            ]
        elif computation_type == "gwb_meshes":
            estimates = [
                predictor.predict(
                    {
                        "computation_type": computation_type,
                        "num_units": len(request.files),
                        "num_springs": len(data),
                        **uploaded_mesh_features(),
                    }
                )
            ]
        else:
            inputs = read_geological_inputs(data["box"])
            if isinstance(inputs, Response):
                return inputs
            model_data, dem_bytes = inputs
            dem = dem_bytes.decode("utf-8")
            model = load_trusted_gmlib_model(model_data, data["box"], dem)
            estimates = [
                predictor.predict(
                    model_factors(
                        computation_type,
                        data,
                        model,
                        gwb_part_count(),
                    )
                )
            ]
    except RuntimeError as error:
        logger.exception("Duration model artifacts are inconsistent")
        return Response(str(error), 503, mimetype="text/plain")
    except (GeologicalModelValidationError, ValueError, KeyError) as error:
        return Response(str(error), 400, mimetype="text/plain")

    return jsonify(sum_estimates(estimates))


@app.post("/estimate/<computation_type>")
def estimate(computation_type):
    """Estimate duration for a computation type based on its inputs"""
    return estimate_request(computation_type)


def filemap_to_tar(files: dict[bytes, bytes]) -> BytesIO:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w") as tar:
        for name, value in files.items():
            info = tarfile.TarInfo(name.decode("utf-8"))
            info.size = len(value)
            tar.addfile(info, BytesIO(value))
    output.seek(0)
    return output


def non_success_response(res: AsyncResult) -> Response | None:
    """Returns a Response if the state is not SUCCESS, otherwise None.
    Additionally, cleans up task result if state is FAILURE or REVOKED"""
    state = res.state
    if state == states.SUCCESS:
        return None

    if state in {states.FAILURE, states.REVOKED}:
        res.forget()

    return Response(state, mimetype="text/plain")


def read_geological_inputs(
    extent: EvaluationExtent,
) -> tuple[bytes, bytes] | Response:
    """Read and validate the protobuf model and DEM uploads."""
    model_file = request.files.get("model")
    dem_file = request.files.get("dem")
    if model_file is None or dem_file is None:
        return Response("Missing model or dem file", 400, mimetype="text/plain")

    model_data = model_file.read()
    try:
        parse_geological_model(model_data)
        validate_evaluation_extent(extent)
    except (GeologicalModelValidationError, EvaluationExtentValidationError) as error:
        return Response(str(error), 400, mimetype="text/plain")
    return model_data, dem_file.read()


def compute_meshes_or_faults(is_meshes: bool):
    if request.method == "POST":
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        try:
            data: MeshesData = _meshes_adapter.validate_json(request.form["data"])
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        inputs = read_geological_inputs(data["box"])
        if isinstance(inputs, Response):
            return inputs
        model_data, dem = inputs
        model_key = generate_key()
        dem_key = generate_key()
        r.set(model_key, model_data)
        r.set(dem_key, dem)
        output_key = generate_key()
        res = (tasks.compute_meshes if is_meshes else tasks.compute_faults).delay(
            data, model_key, dem_key, output_key, metadata
        )
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if _id is None or _id == "":
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        # TODO: catch errors
        output_key = res.get()
        meshes = get_hash_bytes(r, output_key)
        r.delete(output_key)
        if not meshes:
            return Response("", 204, mimetype="text/plain")

        output = filemap_to_tar(meshes)
        return send_file(
            output,
            mimetype="application/x-tar",
            as_attachment=True,
            download_name="meshes.tar",
        )


@app.route("/compute/tunnel_meshes", methods=["POST", "GET"])
def compute_tunnel_meshes():
    if request.method == "POST":
        try:
            data: TunnelMeshesData = _tunnel_meshes_adapter.validate_json(
                request.form["data"]
            )
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        output_key = generate_key()
        res = tasks.compute_tunnel_meshes.delay(data, output_key, metadata)
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if _id is None or _id == "":
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        # TODO: catch errors
        output_key = res.get()
        meshes = get_hash_bytes(r, output_key)
        r.delete(output_key)
        if not meshes:
            return Response("", 204, mimetype="text/plain")

        output = filemap_to_tar(meshes)
        return send_file(
            output,
            mimetype="application/x-tar",
            as_attachment=True,
            download_name="tunnel_meshes.tar",
        )


@app.route("/compute/meshes", methods=["POST", "GET"])
def compute_meshes():
    return compute_meshes_or_faults(True)


@app.route("/compute/intersections", methods=["POST", "GET"])
def compute_intersections():
    if request.method == "POST":
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        try:
            data: IntersectionsData = _intersections_adapter.validate_json(
                request.form["data"]
            )
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        inputs = read_geological_inputs(data["box"])
        if isinstance(inputs, Response):
            return inputs
        model_data, dem = inputs
        model_key = generate_key()
        dem_key = generate_key()
        r.set(model_key, model_data)
        r.set(dem_key, dem)

        gwb_meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every other uploaded file as a groundwater body mesh
            if key in ["model", "dem"]:
                continue
            hset_bytes(r, gwb_meshes_key, key, value.read())
        output_key = generate_key()

        res = tasks.compute_intersections.delay(
            data, model_key, dem_key, gwb_meshes_key, output_key, metadata
        )
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if _id is None or _id == "":
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        # TODO: catch errors
        output_key = res.get()
        output = get_bytes(r, output_key)
        r.delete(output_key)
        if not output:
            return Response("", 204, mimetype="text/plain")

        return Response(output.decode("utf-8"), mimetype="application/json")


@app.route("/compute/faults", methods=["POST", "GET"])
def compute_faults():
    return compute_meshes_or_faults(False)


@app.route("/compute/voxels", methods=["POST", "GET"])
def compute_voxels():
    if request.method == "POST":
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        try:
            data: MeshesData = _meshes_adapter.validate_json(request.form["data"])
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        inputs = read_geological_inputs(data["box"])
        if isinstance(inputs, Response):
            return inputs
        model_data, dem = inputs
        model_key = generate_key()
        dem_key = generate_key()
        r.set(model_key, model_data)
        r.set(dem_key, dem)
        gwb_meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every other uploaded file as a groundwater body mesh
            if key in ["model", "dem"]:
                continue
            hset_bytes(r, gwb_meshes_key, key, value.read())
        output_key = generate_key()
        res = tasks.compute_voxels.delay(
            data, model_key, dem_key, gwb_meshes_key, output_key, metadata
        )
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if _id is None or _id == "":
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        # TODO: catch errors
        output_key = res.get()
        mesh = get_bytes(r, output_key)
        r.delete(output_key)
        if not mesh:
            return Response("", 204, mimetype="text/plain")

        return Response(mesh.decode("utf-8"), mimetype="text/plain")


@app.route("/compute/gwb_meshes", methods=["POST", "GET"])
def compute_gwb_meshes():
    if request.method == "POST":
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        try:
            data: list[Spring] = _gwb_meshes_adapter.validate_json(request.form["data"])
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every uploaded file as a unit mesh
            hset_bytes(r, meshes_key, key, value.read())
        output_key = generate_key()

        res = tasks.compute_gwb_meshes.delay(data, meshes_key, output_key, metadata)
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if _id is None or _id == "":
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        # TODO: catch errors
        output_key = res.get()
        meshes_and_metadata = get_hash_bytes(r, output_key)
        r.delete(output_key)
        if not meshes_and_metadata:
            return Response("", 204, mimetype="text/plain")

        output = filemap_to_tar(meshes_and_metadata)
        return send_file(
            output,
            mimetype="application/x-tar",
            as_attachment=True,
            download_name="gwb_meshes.tar",
        )


@app.post("/poll")
def poll():
    """Poll many computation statuses at the same time"""
    data = request.json
    result = {}
    for _id in data:
        res = AsyncResult(str(_id))
        meta = res._get_task_meta()["result"]
        result[str(_id)] = {
            "state": res.state,
            "progress": meta if isinstance(meta, dict) else None,
        }
    return Response(
        json.dumps(result, separators=(",", ":")), mimetype="application/json"
    )


@app.post("/revoke")
def revoke():
    """Revoke a task by id"""
    _id = request.args.get("id")
    if not _id or _id == "":
        return Response("Missing parameter id", 400, mimetype="text/plain")

    res = AsyncResult(_id)
    res.revoke(terminate=True, wait=True, timeout=2)
    if res.state != states.REVOKED:
        return Response(f"Task {_id} could not be revoked", 500, mimetype="text/plain")
    else:
        return Response(f"Task {_id} revoked", 200, mimetype="text/plain")


def main():
    # Development server
    app.run(debug=True, host="0.0.0.0")


if __name__ == "__main__":
    main()
