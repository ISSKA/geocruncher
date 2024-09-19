# Geocruncher

Python 3.9 computation package capable of:
- Tunnel mesh computation
- Geological unit / fault mesh computation
- Geological unit / fault intersection computation
- Geological mesh to voxel computation

Most computations use the BRGM's technologies under the hood. This package is intended as a bridge between GMLIB (and other libraries) and the [VisualKarsys webservice](https://visualkarsys.com).

It can be used both as a standalone executable reading inputs from files and writing outputs to files, or as a python module (Work In Progress).

It posesses an optional integrated Profiler, used in production by the VisualKarsys team to estimate computation times and identify key areas where speed should be improved. 

## Installation

Follow these steps to run Geocruncher

**1) Install a python environment manager like [Miniconda](https://docs.anaconda.com/miniconda/)**

```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
```

**2) Create an environment for Geocruncher**

```bash
conda create -n viskar39 python=3.9
conda activate viskar39
```

**2) Install Geocruncher dependencies**

If you are part of the VisualKarsys team, please refer to the [build.Dockerfile](https://github.com/ISSKA/VISKAR/blob/develop/src/docker/build.Dockerfile) to see the required packages, and follow the [VisualKarsys Geocruncher Documentation](https://github.com/ISSKA/VISKAR/blob/develop/doc/backend/geocruncher.md) to understand how to build the libraries.

Geocruncher requires gmlib >=0.3.22, MeshTools main@5a02671, pycgal >=0.3.14 and vtkwriters >=0.0.10.

vtkwriters is publicly available [here](https://github.com/BRGM/vtkwriters), however, the other 3 libraries are private. Please inquire with [BRGM](https://gitlab.brgm.fr) for access.

The rest of the dependencies are standard python modules, and can be installed with pip.
```bash
pip install lxml scipy sympy pybind11 pyyaml meshio pyvista scikit-image verstr numpy pillow
pip install dist/vtkwriters*.whl
pip install dist/gmlib*.whl
pip install dist/MeshTools*.whl
pip install dist/pycgal*.whl
```

## Dummy Project

A dummy project is provided in order to test the installation. For example, to run the dummy computation of intersections, execute the following:
```bash
python -m geocruncher intersections tests/dummy_project/sections.json tests/dummy_project/geocruncher_project.xml tests/dummy_project/geocruncher_dem.asc tests/dummy_project out.json
```

A more helpful command line argument validation system is being worked on. You can already run geocruncher with `-h` or `--help` to get basic help. Note that:
- validation of parameters specific to each computation doesn't exist for now
- additional flags (such as for profiling) must always come last

In the meantime, you can find out what arguments are requiered and in which order by looking at the `main.run_geocruncher` function. Below each computation type, a comment indicates the list of parameters requiered.

## Development

If using Visual Studio Code, the last step is to tell it which Python version to use. With a Python file open, at the bottom right, click on the Python version. In the dropdown, choose the Python version from the conda environment.

Autocompletion will now work as expected.
Recommanded extensions: `ms-python.python`, `ms-python.pylint` and `ms-python.autopep8`
