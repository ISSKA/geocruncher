# Run Geocruncher locally and call the API

## Run Geocruncher locally

Install Docker with the Compose plugin, then run this command from the repository root (if you do not want to use Docker follow the [local Python venv setup](../README.md#Development)):

```bash
./scripts/run.sh
```

This starts the API, worker, and Redis containers. It builds the local image on the first run and exposes the API at `http://127.0.0.1:5000`. Keep this terminal open while using Geocruncher. Press `Ctrl+C` to stop the stack.

Use a second terminal for the API calls below.

## Migrate from the removed CLI

The HTTP API replaces the old `geocruncher` command and `python -m geocruncher`. Each computation now has two steps:

1. Send a `POST` request. The response body is a computation ID.
2. Wait for the computation to reach `SUCCESS`, then send a `GET` request with that ID to download the result.

The old positional arguments map to multipart form fields as follows:

| Old CLI input | HTTP API field |
| --- | --- |
| Computation name | Endpoint path, such as `/compute/meshes` |
| JSON configuration file | `data` |
| Geological model | `model` |
| Digital elevation model | `dem` |
| Groundwater body mesh files | Additional, uniquely named file fields |
| Output file or directory | The response from the result request |

The API accepts a binary `isska.geocruncher.v1.GeologicalModel` protobuf in the `model` field, not the GeoModeller XML file used by older CLI examples. See the [`model` field reference](./api.md#model) for the input contract.

For example, submit a tunnel mesh computation and store its ID:

```bash
computation_id=$(curl --fail --silent --show-error \
  -F "data=<tests/fixtures/dummy_project/tunnel.json" \
  http://127.0.0.1:5000/compute/tunnel_meshes)
```

Check its state. Repeat this request until the returned state is `SUCCESS`:

```bash
curl --fail --silent --show-error \
  --json "[\"${computation_id}\"]" \
  http://127.0.0.1:5000/poll
```

Then download and extract the result:

```bash
curl --fail --silent --show-error \
  "http://127.0.0.1:5000/compute/tunnel_meshes?id=${computation_id}" \
  --output tunnel_meshes.tar
tar -xf tunnel_meshes.tar
```

The sections below show the request fields and result format for each computation. The [HTTP API reference](./api.md) documents validation, status codes, and every endpoint.

## Tunnel meshes

### Create a tunnel meshes computation

The response body is the computation ID.

```bash
curl -F "data=<tests/fixtures/dummy_project/tunnel.json" http://127.0.0.1:5000/compute/tunnel_meshes
```

### Get tunnel meshes results

Replace `xxyy` with the computation ID. When the computation succeeds, the response is a tar archive.

```bash
curl --fail --output tunnel_meshes.tar \
  "http://127.0.0.1:5000/compute/tunnel_meshes?id=xxyy"
tar -xf tunnel_meshes.tar
```

## Meshes and faults

### Create a meshes or faults computation

The response body is the computation ID. Replace `meshes` with `faults` in the URL to compute faults.

```bash
curl --fail \
  -F "data=<tests/fixtures/dummy_project/mesh.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/meshes
```

### Get meshes or faults results

Replace `xxyy` with the computation ID. Replace `meshes` with `faults` in the URL for a faults computation. When the computation succeeds, the response is a tar archive.

```bash
curl --fail --output meshes.tar \
  "http://127.0.0.1:5000/compute/meshes?id=xxyy"
tar -xf meshes.tar
```

## Intersections

### Create an intersections computation

The response body is the computation ID. The API treats each additional file field as a groundwater body mesh. Name these fields `<groundwater-body-id>_<part>` so it can group mesh parts by ID.

```bash
curl --fail \
  -F "data=<tests/fixtures/dummy_project/sections.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/intersections
```

### Get intersections results

Replace `xxyy` with the computation ID. When the computation succeeds, the response is JSON.

```bash
curl --fail --output intersections.json \
  "http://127.0.0.1:5000/compute/intersections?id=xxyy"
```

## Voxels

### Create a voxels computation

The response body is the computation ID. As with intersections, the API treats each additional file field as a groundwater body mesh.

```bash
curl --fail \
  -F "data=<tests/fixtures/dummy_project/mesh.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/voxels
```

### Get voxels results

Replace `xxyy` with the computation ID. When the computation succeeds, the response is the voxel file.

```bash
curl --fail --output voxels.vox \
  "http://127.0.0.1:5000/compute/voxels?id=xxyy"
```
