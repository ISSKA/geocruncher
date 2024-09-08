# Exemples for querying the API using CURL

## Tunnel Meshes

### Create a Tunnel Meshes computation

Will return the computation ID

```bash
curl --header "Content-Type: application/json" --request POST --data '{"tunnels":[{"name":"circle_tunnel","shape":"Circle","radius":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]},{"name":"rectangle_tunnel","shape":"Rectangle","width":20,"height":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]},{"name":"elliptic_tunnel","shape":"Elliptic","width":20,"height":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]}],"step":0.1,"nb_vertices":200,"idxStart":-1,"idxEnd":-1,"tStart":0,"tEnd":1}' http://127.0.0.1:5000/compute/tunnel_meshes
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
curl -F data='{"resolution":{"x":5,"y":5,"z":5}}' -F xml=@tests/dummy_project/geocruncher_project.xml -F dem=@tests/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/meshes
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
curl -F data='{"toCompute":{"1":{"lowerLeft":{"x":543440,"y":199630,"z":-2500},"upperRight":{"x":546260,"y":196090,"z":1500}},"2":{"lowerLeft":{"x":541440,"y":198460,"z":-2500},"upperRight":{"x":544660,"y":194390,"z":1500}},"3":{"lowerLeft":{"x":539680,"y":197970,"z":-2500},"upperRight":{"x":543470,"y":193420,"z":1500}}},"resolution":150,"computeMap":true}' -F xml=@tests/dummy_project/geocruncher_project.xml -F dem=@tests/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/intersections
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
curl -F data='{"resolution":{"x":5,"y":5,"z":5}}' -F xml=@tests/dummy_project/geocruncher_project.xml -F dem=@tests/dummy_project/geocruncher_dem.asc http://127.0.0.1:5000/compute/voxels
```

### Poll a Voxels computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output vox file

```bash
curl http://127.0.0.1:5000/compute/voxels?id=xxyy
```
