# HTTP API reference

Geocruncher exposes an HTTP API for starting geological computations and retrieving their results. Computations run asynchronously in Celery workers, so every computation uses the same two-step process:

1. Send a `POST` request to a `/compute/...` endpoint. The response contains a task ID.
2. Poll the task. Once it succeeds, send a `GET` request to the same computation endpoint to retrieve the result.

The API has no built-in authentication and its paths are not versioned. Do not expose it directly to the internet. Put an authenticated HTTPS proxy in front of it when access is not limited to a trusted network.

The examples below use the development server at `http://127.0.0.1:5000`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/compute/tunnel_meshes` | Start tunnel mesh generation |
| `GET` | `/compute/tunnel_meshes?id=...` | Read tunnel meshes or the current task state |
| `POST` | `/compute/meshes` | Start geological unit and fault mesh generation |
| `GET` | `/compute/meshes?id=...` | Read unit and fault meshes or the current task state |
| `POST` | `/compute/faults` | Start fault-only mesh generation |
| `GET` | `/compute/faults?id=...` | Read fault meshes or the current task state |
| `POST` | `/compute/intersections` | Start cross-section and map intersection computation |
| `GET` | `/compute/intersections?id=...` | Read intersection data or the current task state |
| `POST` | `/compute/voxels` | Start voxel computation |
| `GET` | `/compute/voxels?id=...` | Read voxel data or the current task state |
| `POST` | `/compute/gwb_meshes` | Start groundwater body mesh generation |
| `GET` | `/compute/gwb_meshes?id=...` | Read groundwater body meshes or the current task state |
| `POST` | `/poll` | Read the state and progress of several tasks |
| `POST` | `/revoke?id=...` | Stop a task |

## Asynchronous workflow

### Starting a computation

All computation requests use `multipart/form-data`. The `data` form field contains JSON, not an uploaded JSON file. Most endpoints also accept uploaded model, elevation, or mesh files.

A valid request returns:

```http
HTTP/1.1 202 ACCEPTED
Content-Type: text/plain

6b17af3038d34cbf932815a7d1775377
```

The response body is the Celery task ID. Treat it as an opaque string.

### Checking progress

Use `POST /poll` to check one or more tasks without consuming their results:

```bash
curl \
  -H "Content-Type: application/json" \
  -d '["6b17af3038d34cbf932815a7d1775377"]' \
  http://127.0.0.1:5000/poll
```

The response maps each requested task ID to its state and optional progress data:

```json
{
  "6b17af3038d34cbf932815a7d1775377": {
    "state": "STARTED",
    "progress": {
      "currentStep": "ranks",
      "startTime": 1788182950123,
      "totalTime": 240
    }
  }
}
```

`progress` is `null` when the task has not reported a progress object. Its fields are:

| Field | Type | Meaning |
| --- | --- | --- |
| `currentStep` | string | Name of the computation step currently starting |
| `startTime` | integer | Step start time as Unix epoch milliseconds |
| `totalTime` | integer | Time already recorded for this step, in milliseconds |

Celery states normally include `PENDING`, `STARTED`, `RETRY`, `SUCCESS`, `FAILURE`, and `REVOKED`.

### Retrieving a result

After `/poll` reports `SUCCESS`, send a `GET` request to the same computation endpoint used to start the task:

```bash
curl \
  -o meshes.tar \
  "http://127.0.0.1:5000/compute/meshes?id=6b17af3038d34cbf932815a7d1775377"
```

Result retrieval is destructive. The API deletes a successful result from Redis while handling the first `GET`, including when it returns `204 No Content`. Do not retry a successful download unless the client failed before sending the request. Store the response before processing it.

If the task has not succeeded, the `GET` response is `200 OK` with the current Celery state as plain text instead of a result. For example:

```text
PENDING
```

Use the response `Content-Type` or check `/poll` first. Do not pipe an unchecked response directly into an archive extractor.

## Common request fields

### `data`

Every computation request requires a `data` form field containing a JSON value. Its structure depends on the endpoint.

With curl, `-F "data=<path.json"` reads the file contents into the form field:

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/tunnel.json" \
  http://127.0.0.1:5000/compute/tunnel_meshes
```

### `metadata`

Every computation request accepts an optional `metadata` form field. Its value must be a JSON object with string keys. The worker adds these values to profiler records when profiling is enabled.

```bash
-F 'metadata={"project_id":"project-a","request_id":"request-42"}'
```

Invalid metadata is ignored and does not reject the computation. Do not use this field for computation parameters.

### `model`

The `/compute/meshes`, `/compute/faults`, `/compute/intersections`, and `/compute/voxels` endpoints require a `model` file. It must contain a binary `isska.geocruncher.v1.GeologicalModel` protobuf. The schema is defined in [`proto/isska/geocruncher/v1/project.proto`](../proto/isska/geocruncher/v1/project.proto).

### `dem`

The same four endpoints require a `dem` file containing elevation data in ASCII Grid format.

### Mesh uploads

Mesh upload fields accept triangular meshes encoded as OFF or Draco data. The API recognizes an OFF file by its `OFF` prefix and otherwise attempts to decode it as Draco.

For `/compute/intersections` and `/compute/voxels`, every uploaded file other than `model` and `dem` is a groundwater body mesh. Name each form field as `<gwb-id>_<part-id>`, for example `7_0` and `7_1`. The groundwater body ID before the first underscore must be an integer. Multiple fields may supply separate mesh parts for the same groundwater body.

For `/compute/gwb_meshes`, every uploaded file is a geological unit mesh. The form field name must be the integer unit ID, for example `1` or `12`.

## Shared JSON types

Field names are case-sensitive.

### Evaluation extent

An evaluation extent describes a box in project coordinates:

```json
{
  "xmin": 534000.0,
  "ymin": 191000.0,
  "zmin": -2500.0,
  "xmax": 549000.0,
  "ymax": 201000.0,
  "zmax": 5000.0
}
```

All six fields are required numbers. For the top-level `box` sent to a project computation, every value must be finite and each minimum must be less than its corresponding maximum.

Extents inside `toCompute` describe oriented vertical sections. Their x or y coordinates may run in either direction, as shown in the examples below.

### Integer resolution

Mesh and voxel computations use a resolution with one positive integer per axis:

```json
{
  "x": 50,
  "y": 50,
  "z": 25
}
```

Larger values use more memory and computation time.

### 3D point

A 3D point has three required numeric coordinates:

```json
{
  "x": 541266.25,
  "y": 195845.42,
  "z": 500.0
}
```

## Tunnel meshes

### Start a computation

```http
POST /compute/tunnel_meshes
Content-Type: multipart/form-data
```

This endpoint does not need a geological model or DEM.

The `data` field contains:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `tunnels` | array of tunnel objects | yes | Tunnels to generate |
| `nb_vertices` | integer | yes | Number of vertices around each cross section |
| `step` | number | yes | Increment of the function parameter `t` |
| `idxStart` | integer | yes | First function index for a partial tunnel, or `-1` for the start |
| `idxEnd` | integer | yes | Last function index for a partial tunnel, or `-1` for the end |
| `tStart` | number | yes | Starting `t` value when `idxStart` selects a function |
| `tEnd` | number | yes | Ending `t` value when `idxEnd` selects a function |

Each tunnel object contains:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `name` | string | yes | Tunnel name and result archive entry name |
| `shape` | string | yes | `Circle`, `Rectangle`, or `Elliptic` |
| `functions` | array | yes | Parametric path segments |
| `radius` | number | for `Circle` | Circle radius |
| `width` | number | for `Rectangle` and `Elliptic` | Cross-section width |
| `height` | number | for `Rectangle` and `Elliptic` | Cross-section height |

Each item in `functions` has string fields named `x`, `y`, and `z`. The expressions use `t` as their variable. The API accepts `^` for exponentiation and converts it to `**` before parsing.

Example data:

```json
{
  "tunnels": [
    {
      "name": "main_tunnel",
      "shape": "Circle",
      "radius": 10,
      "functions": [
        {
          "x": "10 * t",
          "y": "(t - 0.5)^2 + 120 * t",
          "z": "40"
        }
      ]
    }
  ],
  "nb_vertices": 12,
  "step": 0.25,
  "idxStart": -1,
  "idxEnd": -1,
  "tStart": 0,
  "tEnd": 1
}
```

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/tunnel.json" \
  http://127.0.0.1:5000/compute/tunnel_meshes
```

### Result

`GET /compute/tunnel_meshes?id=...` returns `application/x-tar`. The suggested download name is `tunnel_meshes.tar`. The archive has one entry per tunnel, named exactly after the tunnel's `name`. Entry names have no file extension. Their contents are Draco-encoded triangular meshes.

## Geological unit and fault meshes

### Start a computation

```http
POST /compute/meshes
Content-Type: multipart/form-data
```

The request requires `data`, `model`, and `dem`.

The `data` object contains:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `resolution` | integer resolution | yes | Number of grid samples on each axis |
| `box` | evaluation extent | yes | Bounds of the generated model |

Example:

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/mesh.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/meshes
```

### Result

`GET /compute/meshes?id=...` returns `application/x-tar` with the suggested download name `meshes.tar`.

The archive may contain:

| Entry name | Contents |
| --- | --- |
| `rank_<rank>` | Draco mesh for a geological unit rank |
| `fault_<fault-name>` | Draco mesh for a fault |

Archive entry names have no file extension.

## Fault meshes

### Start a computation

```http
POST /compute/faults
Content-Type: multipart/form-data
```

The request has the same `data`, `model`, and `dem` fields as `/compute/meshes`.

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/mesh.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/faults
```

### Result

`GET /compute/faults?id=...` returns `application/x-tar`. The archive contains `fault_<fault-name>` entries with Draco mesh data. The suggested download name is currently `meshes.tar`.

## Intersections

### Start a computation

```http
POST /compute/intersections
Content-Type: multipart/form-data
```

The request requires `data`, `model`, and `dem`. It may also contain groundwater body mesh fields.

The `data` object contains:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `resolution` | integer | yes | Target resolution of the longer side of each output grid |
| `box` | evaluation extent | yes | Bounds used to load the geological model |
| `toCompute` | object | yes | Map from section ID to an array of section extents |
| `computeMap` | boolean | yes | Whether to calculate top-down map results |
| `springs` | object or `null` | no | Map from spring ID to a 3D point |
| `drillholes` | object or `null` | no | Map from drillhole ID to an evaluation extent |

Example data:

```json
{
  "box": {
    "xmin": 534000.0,
    "ymin": 191000.0,
    "zmin": -2500.0,
    "xmax": 549000.0,
    "ymax": 201000.0,
    "zmax": 5000.0
  },
  "toCompute": {
    "section-1": [
      {
        "xmin": 543440.0,
        "ymin": 199630.0,
        "zmin": -2500.0,
        "xmax": 546260.0,
        "ymax": 196090.0,
        "zmax": 1500.0
      }
    ]
  },
  "resolution": 150,
  "computeMap": true
}
```

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/sections.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  http://127.0.0.1:5000/compute/intersections
```

To include a groundwater body with ID `7` split into two meshes:

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/intersection_hydro.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  -F "7_0=@path/to/gwb-part-0.drc" \
  -F "7_1=@path/to/gwb-part-1.drc" \
  http://127.0.0.1:5000/compute/intersections
```

### Result

`GET /compute/intersections?id=...` returns `application/json` with top-level `mesh` and `fault` objects.

The `mesh` object contains:

| Field | Meaning |
| --- | --- |
| `forCrossSections` | Map from section ID to one geological rank matrix per requested extent |
| `drillholes` | Map from section ID to projected drillhole coordinates for each extent |
| `springs` | Map from section ID to projected spring coordinates for each extent |
| `matrixGwb` | Map from section ID to flattened groundwater body ID values for each extent |
| `forMaps` | Top-down geological rank matrix, present when `computeMap` is `true` |

Projected spring coordinates are `[distanceAlongSection, elevation]`. A projected drillhole contains two such coordinate pairs. The API rounds projected coordinates to two decimal places.

The `fault` object contains:

| Field | Meaning |
| --- | --- |
| `forCrossSections` | Map from section ID to fault intersections for each requested extent |
| `forMaps` | Map from fault name to its top-down intersection data, empty when `computeMap` is `false` |

When the request has no springs, drillholes, or groundwater meshes, `drillholes`, `springs`, and `matrixGwb` contain an empty array for each section ID.

## Voxels

### Start a computation

```http
POST /compute/voxels
Content-Type: multipart/form-data
```

The request requires the same `data`, `model`, and `dem` fields as `/compute/meshes`. It may also include groundwater body meshes named with the `<gwb-id>_<part-id>` convention.

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/mesh.json" \
  -F "model=@tests/fixtures/dummy_project/geocruncher_project.pb" \
  -F "dem=@tests/fixtures/dummy_project/geocruncher_dem.asc" \
  -F "7_0=@path/to/gwb-part-0.off" \
  http://127.0.0.1:5000/compute/voxels
```

### Result

`GET /compute/voxels?id=...` returns `text/plain`. The first line describes the bounds and grid dimensions. The second line names the columns. The remaining lines contain one geological rank and groundwater body ID per voxel.

```text
XMIN=0 XMAX=10 YMIN=0 YMAX=10 ZMIN=-5 ZMAX=5 NUMBERX=2 NUMBERY=2 NUMBERZ=2 NOVALUE=0
rank gwb_id
1 0
1 0
2 7
2 7
```

Voxel rows use x as the innermost loop, y as the middle loop, and z as the outer loop. Groundwater body ID `0` means that the voxel is not inside an uploaded groundwater body mesh.

## Groundwater body meshes

### Start a computation

```http
POST /compute/gwb_meshes
Content-Type: multipart/form-data
```

The request requires `data` and one or more geological unit meshes. It does not use the geological model protobuf or DEM.

The `data` field contains an array of springs:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | integer | yes | Spring ID |
| `unit_id` | integer | yes | ID of the geological unit containing the spring |
| `location` | 3D point | yes | Spring coordinates |

Example data:

```json
[
  {
    "id": 1,
    "unit_id": 1,
    "location": {
      "x": 550875.0,
      "y": 202250.0,
      "z": -1500.0
    }
  }
]
```

Each mesh form field is named after its unit ID:

```bash
curl \
  -F "data=<tests/fixtures/dummy_project/gwb_spring.json" \
  -F "1=@path/to/unit-1.drc" \
  -F "2=@path/to/unit-2.off" \
  http://127.0.0.1:5000/compute/gwb_meshes
```

### Result

`GET /compute/gwb_meshes?id=...` returns `application/x-tar` with the suggested download name `gwb_meshes.tar`.

The archive contains:

| Entry name | Contents |
| --- | --- |
| `mesh_0`, `mesh_1`, ... | One Draco-encoded groundwater body mesh per result |
| `metadata` | JSON array describing the generated meshes in the same order |

Each item in `metadata` has this structure:

```json
{
  "unit_id": 1,
  "spring_id": 1,
  "volume": 12345.67
}
```

## Revoking a task

Send the task ID as the `id` query parameter:

```bash
curl \
  -X POST \
  "http://127.0.0.1:5000/revoke?id=6b17af3038d34cbf932815a7d1775377"
```

A successful request returns `200 OK` and plain text:

```text
Task 6b17af3038d34cbf932815a7d1775377 revoked
```

The server waits up to two seconds for Celery to report the `REVOKED` state. It returns `500 Internal Server Error` if that does not happen.

## Status codes and errors

| Status | When it is returned | Body |
| --- | --- | --- |
| `200 OK` | A task state, completed JSON or text result, poll response, or successful revoke | Depends on the endpoint |
| `202 Accepted` | A computation was queued | Plain-text task ID |
| `204 No Content` | The task succeeded but its stored output was empty or unavailable | Empty |
| `400 Bad Request` | A required parameter or file is missing, JSON validation fails, the model protobuf is invalid, or the top-level box is invalid | JSON validation details or plain text |
| `500 Internal Server Error` | A revoke request did not reach the `REVOKED` state | Plain text |

Pydantic validation errors use `application/json`. Missing files and semantic model or box errors use `text/plain`.

An invalid `model` upload returns a message beginning with `invalid GeologicalModel protobuf`. A missing `model` or `dem` returns:

```text
Missing model or dem file
```

A missing `id` query parameter returns:

```text
Missing parameter id
```

Worker failures do not return a structured error document. `/poll` reports the `FAILURE` state with `progress` set to `null`. A `GET` request to the computation endpoint returns `FAILURE` as plain text and forgets the failed Celery result.
