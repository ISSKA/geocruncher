# Examples for querying the API using CURL

## Tunnel Meshes

### Create a Tunnel Meshes computation

Will return the computation ID

```bash
curl -F "data=<tests/fixtures/dummy_project/tunnel.json" http://127.0.0.1:5000/compute/tunnel_meshes
```

### Poll a Tunnel Meshes computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output tar file

```bash
curl http://127.0.0.1:5000/compute/tunnel_meshes?id=xxyy | tar -xf -
```

## Meshes / Faults

### Create a Meshes / Faults computation

Will return the computation ID

Replace `meshes` with `faults` in the URL for a faults computation

```bash
curl -F "data=<tests/fixtures/dummy_project/mesh.json" -F model=@tests/fixtures/dummy_project/geocruncher_project.pb -F dem=@tests/fixtures/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/meshes
```

### Poll a Meshes / Faults computation for results

Use the previously returned ID as parameter

Replace `meshes` with `faults` in the URL for a faults computation

Will return either the state of the computation, or the output tar file

```bash
curl http://127.0.0.1:5000/compute/meshes?id=xxyy | tar -xf -
```

## Intersections

### Create an Intersections computation

Will return the computation ID

Not included in this exemple: every additional file given is considered as a groundwater body mesh

```bash
curl -F "data=<tests/fixtures/dummy_project/sections.json" -F model=@tests/fixtures/dummy_project/geocruncher_project.pb -F dem=@tests/fixtures/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/intersections
```

### Poll an Intersections computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output json

```bash
curl http://127.0.0.1:5000/compute/intersections?id=xxyy
```

## Voxels

### Create a Voxels computation

Will return the computation ID

Not included in this exemple: every additional file given is considered as a groundwater body mesh

```bash
curl -F "data=<tests/fixtures/dummy_project/mesh.json" -F model=@tests/fixtures/dummy_project/geocruncher_project.pb -F dem=@tests/fixtures/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/voxels
```

### Poll a Voxels computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output vox file

```bash
curl http://127.0.0.1:5000/compute/voxels?id=xxyy
```
