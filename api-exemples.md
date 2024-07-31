# Exemples for querying the API using CURL

## Tunnel Meshes

### Create a Tunnel Meshes computation

Will return the computation ID

```bash
curl --header "Content-Type: application/json" --request POST --data '{"tunnels":[{"name":"circle_tunnel","shape":"Circle","radius":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]},{"name":"rectangle_tunnel","shape":"Rectangle","width":20,"height":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]},{"name":"elliptic_tunnel","shape":"Elliptic","width":20,"height":10,"functions":[{"x":"10 * t","y":"(t - 0.5)^2 + 120 * t","z":"40"}]}],"step":0.1,"nb_vertices":200,"idxStart":-1,"idxEnd":-1,"tStart":0,"tEnd":1}' http://127.0.0.1:8000/compute/tunnel_meshes
```

### Poll a Tunnel Meshes computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output tar file

```bash
curl http://127.0.0.1:8000/compute/tunnel_meshes?id=xxyy | tar -xf -
```

## Meshes

### Create a Meshes computation

Will return the computation ID

```bash
curl -F data='{"resolution":{"x":5,"y":5,"z":5}}' -F xml=@/path/to/xml.xml -F dem=@/path/to/dem.asc http://127.0.0.1:5000/compute/meshes
```

### Poll a Meshes computation for results

Use the previously returned ID as parameter

Will return either the state of the computation, or the output tar file

```bash
curl http://127.0.0.1:8000/compute/meshes?id=xxyy | tar -xf -
```
