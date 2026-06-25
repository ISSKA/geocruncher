import json
import tarfile
from io import BytesIO

from celery.result import AsyncResult, states
from flask import Flask, Response, request, send_file
from pydantic import TypeAdapter, ValidationError

from geocruncher.computations import (
    IntersectionsData,
    KarstNSimData,
    MeshesData,
    Spring,
    TunnelMeshesData,
)

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

_meshes_adapter = TypeAdapter(MeshesData)
_tunnel_meshes_adapter = TypeAdapter(TunnelMeshesData)
_intersections_adapter = TypeAdapter(IntersectionsData)
_gwb_meshes_adapter = TypeAdapter(list[Spring])
_karstnsim_adapter = TypeAdapter(KarstNSimData)


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


def compute_meshes_or_faults(is_meshes: bool):
    if request.method == "POST":
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        try:
            data: MeshesData = _meshes_adapter.validate_json(request.form["data"])
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        xml_file = request.files.get("xml")
        dem_file = request.files.get("dem")
        if xml_file is None or dem_file is None:
            return Response("Missing xml or dem file", 400, mimetype="text/plain")
        xml = xml_file.read()
        dem = dem_file.read()
        xml_key = generate_key()
        dem_key = generate_key()
        r.set(xml_key, xml)
        r.set(dem_key, dem)
        output_key = generate_key()
        res = (tasks.compute_meshes if is_meshes else tasks.compute_faults).delay(
            data, xml_key, dem_key, output_key, metadata
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

        xml_file = request.files.get("xml")
        dem_file = request.files.get("dem")
        if xml_file is None or dem_file is None:
            return Response("Missing xml or dem file", 400, mimetype="text/plain")
        xml = xml_file.read()
        dem = dem_file.read()
        xml_key = generate_key()
        dem_key = generate_key()
        r.set(xml_key, xml)
        r.set(dem_key, dem)

        gwb_meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every other uploaded file as a groundwater body mesh
            if key in ["xml", "dem"]:
                continue
            hset_bytes(r, gwb_meshes_key, key, value.read())
        output_key = generate_key()

        res = tasks.compute_intersections.delay(
            data, xml_key, dem_key, gwb_meshes_key, output_key, metadata
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

        xml_file = request.files.get("xml")
        dem_file = request.files.get("dem")
        if xml_file is None or dem_file is None:
            return Response("Missing xml or dem file", 400, mimetype="text/plain")
        xml = xml_file.read()
        dem = dem_file.read()
        xml_key = generate_key()
        dem_key = generate_key()
        r.set(xml_key, xml)
        r.set(dem_key, dem)
        gwb_meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every other uploaded file as a groundwater body mesh
            if key in ["xml", "dem"]:
                continue
            hset_bytes(r, gwb_meshes_key, key, value.read())
        output_key = generate_key()
        res = tasks.compute_voxels.delay(
            data, xml_key, dem_key, gwb_meshes_key, output_key, metadata
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


@app.route("/compute/karstnsim", methods=["POST", "GET"])
def compute_karstnsim():
    if request.method == "POST":
        try:
            data: KarstNSimData = _karstnsim_adapter.validate_json(request.form["data"])
        except ValidationError as e:
            return Response(e.json(), 400, mimetype="application/json")
        metadata = parse_metadata_from_request()

        files_key = generate_key()
        hset_bytes(r, files_key, "dem", request.files["dem"].read())
        hset_bytes(r, files_key, "voxels", request.files["voxels"].read())
        for key, f in request.files.items():
            if key.startswith("fault_"):
                hset_bytes(r, files_key, key, f.read())

        output_key = generate_key()
        res = tasks.compute_karstnsim.delay(data, files_key, output_key, metadata)
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
        output = get_hash_bytes(r, output_key)
        r.delete(output_key)
        if not output:
            return Response("", 204, mimetype="text/plain")
        return send_file(
            filemap_to_tar(output),
            mimetype="application/x-tar",
            as_attachment=True,
            download_name="karstnsim.tar",
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
