from io import BytesIO
import tarfile
import json
from flask import Flask, request, make_response, send_file
from .utils.redis_client import redis_client as r
from .utils.utils import generate_key
from . import tasks
from .celery import app as celery

app = Flask(__name__)


def respond_with_key(res: celery.AsyncResult) -> Flask.response_class:
    response = make_response(res.id, 202)
    response.mimetype = "text/plain"
    return response


def respond_with_state(res: celery.AsyncResult) -> Flask.response_class:
    response = make_response(res.state, 200)
    response.mimetype = "text/plain"
    return response


def asyncResultFromRequest() -> celery.AsyncResult:
    _id = request.args.get('id')
    # TODO: check id exists
    return celery.AsyncResult(_id)


def filemap_to_tar(files: dict[bytes, bytes]) -> BytesIO:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        for name, value in files.items():
            info = tarfile.TarInfo(name.decode('utf-8'))
            info.size = len(value)
            tar.addfile(info, BytesIO(value))
    output.seek(0)
    return output


@app.route("/compute/tunnel_meshes", methods=['POST', 'GET'])
def tunnel_meshes():
    if request.method == 'POST':
        # when there are no files, we receive an application/json, and the body is the data directly
        # TODO: validate data
        data = request.json
        output_key = generate_key()
        res = tasks.compute_tunnel_meshes.delay(data, output_key)
        return respond_with_key(res)

    elif request.method == 'GET':
        res = asyncResultFromRequest()
        if res.state != 'SUCCESS':
            return respond_with_state(res)
        # TODO: forget about task once it was retreived once
        # TODO: catch errors
        output_key = res.get()
        meshes = r.hgetall(output_key)
        r.delete(output_key)

        output = filemap_to_tar(meshes)
        return send_file(output, mimetype="application/x-tar", as_attachment=True, download_name="tunnel_meshes.tar")


@app.route("/compute/meshes", methods=['POST', 'GET'])
def compute_meshes():
    if request.method == 'POST':
        # when files are uploaded, we receive a multipart/form-data. The JSON data is encoded in the data form field
        # TODO: validate data
        data = json.loads(request.form['data'])
        # TODO: check files exists
        xml = request.files.get('xml').read()
        dem = request.files.get('dem').read()
        xml_key = generate_key()
        dem_key = generate_key()
        r.set(xml_key, xml)
        r.set(dem_key, dem)
        output_key = generate_key()
        res = tasks.compute_meshes.delay(data, xml_key, dem_key, output_key)
        return respond_with_key(res)

    elif request.method == 'GET':
        res = asyncResultFromRequest()
        if res.state != 'SUCCESS':
            return respond_with_state(res)
        # TODO: forget about task once it was retreived once
        # TODO: catch errors
        output_key = res.get()
        meshes = r.hgetall(output_key)
        r.delete(output_key)

        output = filemap_to_tar(meshes)
        return send_file(output, mimetype="application/x-tar", as_attachment=True, download_name="meshes.tar")


def main():
    app.run()


if __name__ == '__main__':
    main()
