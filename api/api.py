from io import BytesIO
import tarfile
import json
from flask import Flask, request, make_response, send_file
from .redis import redis_client as r
from .utils import generate_key
from . import tasks
from .celery import app as celery

app = Flask(__name__)

# TODO: implement revoking tasks https://docs.celeryq.dev/en/stable/userguide/workers.html#revoke-revoking-tasks

def filemap_to_tar(files: dict[bytes, bytes]) -> BytesIO:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        for name, value in files.items():
            info = tarfile.TarInfo(name.decode('utf-8'))
            info.size = len(value)
            tar.addfile(info, BytesIO(value))
    output.seek(0)
    return output


def compute_meshes_or_faults(is_meshes: bool):
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
        res = (tasks.compute_meshes if is_meshes else tasks.compute_faults).delay(
            data, xml_key, dem_key, output_key)
        return res.id, 202

    elif request.method == 'GET':
        _id = request.args.get('id')
        if _id is None or _id == '':
            return "Missing parameter id", 400
        res = celery.AsyncResult(_id)
        if res.state != 'SUCCESS':
            return res.state
        # TODO: catch errors
        output_key = res.get()
        meshes = r.hgetall(output_key)
        r.delete(output_key)
        if not meshes:
            return '', 204

        output = filemap_to_tar(meshes)
        return send_file(output, mimetype="application/x-tar", as_attachment=True, download_name="meshes.tar")


def compute_intersections_or_faults_intersections(is_intersections: bool):
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
        if is_intersections:
            gwb_meshes_key = generate_key()
            for key, value in request.files.items():
                # consider every other uploaded file as a groundwater body mesh
                if key in ['xml', 'dem']:
                    continue
                r.hset(gwb_meshes_key, key, value.read())
        output_key = generate_key()
        if is_intersections:
            res = tasks.compute_intersections.delay(
                data, xml_key, dem_key, gwb_meshes_key, output_key)
        else:
            res = tasks.compute_faults_intersections.delay(
                data, xml_key, dem_key, output_key)
        return res.id, 202

    elif request.method == 'GET':
        _id = request.args.get('id')
        if _id is None or _id == '':
            return "Missing parameter id", 400
        res = celery.AsyncResult(_id)
        if res.state != 'SUCCESS':
            return res.state
        # TODO: catch errors
        output_key = res.get()
        output = r.get(output_key)
        r.delete(output_key)
        if not output:
            return '', 204

        response = make_response(output.decode('utf-8'))
        response.mimetype = "application/json"
        return


@app.route("/compute/tunnel_meshes", methods=['POST', 'GET'])
def tunnel_meshes():
    if request.method == 'POST':
        # when there are no files, we receive an application/json, and the body is the data directly
        # TODO: validate data
        data = request.json
        output_key = generate_key()
        res = tasks.compute_tunnel_meshes.delay(data, output_key)
        return res.id, 202

    elif request.method == 'GET':
        _id = request.args.get('id')
        if _id is None or _id == '':
            return "Missing parameter id", 400
        res = celery.AsyncResult(_id)
        if res.state != 'SUCCESS':
            return res.state
        # TODO: catch errors
        output_key = res.get()
        meshes = r.hgetall(output_key)
        r.delete(output_key)
        if not meshes:
            return '', 204

        output = filemap_to_tar(meshes)
        return send_file(output, mimetype="application/x-tar", as_attachment=True, download_name="tunnel_meshes.tar")


@app.route("/compute/meshes", methods=['POST', 'GET'])
def compute_meshes():
    return compute_meshes_or_faults(True)


@app.route("/compute/intersections", methods=['POST', 'GET'])
def compute_intersections():
    return compute_intersections_or_faults_intersections(True)


@app.route("/compute/faults", methods=['POST', 'GET'])
def compute_faults():
    return compute_meshes_or_faults(False)


@app.route("/compute/faults_intersections", methods=['POST', 'GET'])
def compute_faults_intersections():
    return compute_intersections_or_faults_intersections(False)


@app.route("/compute/voxels", methods=['POST', 'GET'])
def compute_voxels():
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
        gwb_meshes_key = generate_key()
        for key, value in request.files.items():
            # consider every other uploaded file as a groundwater body mesh
            if key in ['xml', 'dem']:
                continue
            r.hset(gwb_meshes_key, key, value.read())
        output_key = generate_key()
        res = tasks.compute_voxels.delay(
            data, xml_key, dem_key, gwb_meshes_key, output_key)
        return res.id, 202

    elif request.method == 'GET':
        _id = request.args.get('id')
        if _id is None or _id == '':
            return "Missing parameter id", 400
        res = celery.AsyncResult(_id)
        if res.state != 'SUCCESS':
            return res.state
        # TODO: catch errors
        output_key = res.get()
        mesh = r.get(output_key)
        r.delete(output_key)
        if not mesh:
            return '', 204

        return mesh.decode('utf-8')

def main():
    app.run()


if __name__ == '__main__':
    main()
