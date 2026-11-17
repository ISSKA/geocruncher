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
from geocruncher.generated_network.models import GeneratedNetworkData
from geocruncher.geological_model.input import (
    GeologicalModelValidationError,
    parse_geological_model,
)
from geocruncher.profiler.features import protobuf_model_factors
from geocruncher.profiler.predict import DurationPredictor

from . import tasks
from .redis import redis_client as r
from .utils import (
    generate_key,
    get_bytes,
    get_hash_bytes,
    gwb_part_count,
    hset_bytes,
    parse_metadata_from_request,
    sum_estimates,
    uploaded_mesh_features,
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
            model_data, _ = inputs
            model = parse_geological_model(model_data)
            estimates = [
                predictor.predict(
                    protobuf_model_factors(
                        computation_type,
                        data,
                        model,
                        gwb_part_count(),
                        predictor.meta["features"][computation_type],
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


@app.route("/compute/generated_network", methods=["POST", "GET"])
def compute_generated_network():
    if request.method == "POST":
        try:
            data: GeneratedNetworkData = GeneratedNetworkData.model_validate_json(
                request.form["data"]
            )
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        files_key = generate_key()
        if "dem" not in request.files or "voxels" not in request.files:
            return Response("Missing dem or voxels file", 400, mimetype="text/plain")
        hset_bytes(r, files_key, "dem", request.files["dem"].read())
        hset_bytes(r, files_key, "voxels", request.files["voxels"].read())

        for fault_id in data.fault_ids:
            fault_file_key = f"fault_{fault_id}"
            if fault_file_key not in request.files:
                return Response(
                    f"Missing fault file for fault ID {fault_id}",
                    400,
                    mimetype="text/plain",
                )
            hset_bytes(
                r, files_key, fault_file_key, request.files[fault_file_key].read()
            )

        output_key = generate_key()
        # dump the data to JSON because GeneratedNetworkData model and other models it contains are not serializable by Celery
        res = tasks.compute_generated_network.delay(
            GeneratedNetworkData.model_dump_json(data),
            files_key,
            output_key,
            metadata,
        )
        return Response(res.id, 202, mimetype="text/plain")

    elif request.method == "GET":
        _id = request.args.get("id")
        if not _id:
            return Response("Missing parameter id", 400, mimetype="text/plain")
        res = AsyncResult(_id)
        response = non_success_response(res)
        if response is not None:
            return response
        output_key = res.get()
        output = get_bytes(r, output_key)
        r.delete(output_key)
        if not output:
            return Response("", 204, mimetype="text/plain")
        return Response(output, mimetype="application/json")


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
