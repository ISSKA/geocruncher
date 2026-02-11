# Dependencies

Every dependency is managed by the Dockerfiles and installed from conda or pip.

## Pip dependencies

Here is the list of uses of each pip dependency

| Depencency   | Use case                             |
| -------------|--------------------------------------|
| celery       | framerowk of worker/queue system     |
| DracoPy      | draco file i/o in python             |
| flask        | framework of the api                 |
| forgeo-gmlib | geological computations              |
| forgeo       | gmlib dependency                     |
| gunicorn     | (production) http server             |
| lxml         | gmlib dependency                     |
| meshio       | types for legacy OFF importer        |
| numpy        | efficient array manipulations        |
| pybind11     | (build/local) build python bindings  |
| pyvista      | extract geometry from meshio object (legacy OFF importer), create PolyData to evaluate GWB layer for intersections & voxels |
| pyyaml       | gmlib dependency                     | 
| redis        | storage for worker/queue system      |
| scikit-image | marching cubes                       |
| scipy        | elliptic tunnel shape                |
| sympy        | parse tunnel functions               |
| verstr       | gmlib dependency                     |
| watchdog     | (local) hot reloading                |

## Conda dependencies

TODO
