# Geocruncher

A small wrapper for the gmlib library. Can be used both as a stand-alone executable reading input data from files, or as a python module.

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

If you are part of the VISKAR development team, please refer to the [build.Dockerfile](https://github.com/ISSKA/VISKAR/blob/develop/src/docker/build.Dockerfile) to see the required packages, and follow the [Geocruncher Documentation](https://github.com/ISSKA/VISKAR/blob/develop/doc/backend/geocruncher.md) to understand how to build the libraries.

Geocruncher requires gmlib >=0.3.17, MeshTools main@5a02671, pycgal >=0.3.14 and vtkwriters >=0.0.10.
vtkwriters is publicly available [here](https://github.com/BRGM/vtkwriters), however, the other 3 libraries are private. Please inquire with [BRGM](https://gitlab.brgm.fr) for access.

```bash
pip install lxml scipy sympy pybind11 pyyaml meshio pyvista scikit-image verstr numpy pillow
pip install dist/vtkwriters*.whl
pip install dist/gmlib*.whl
pip install dist/MeshTools*.whl
pip install dist/pycgal*.whl
```

## Development

If using Visual Studio Code, the last step is to tell it which Python version to use. With a Python file open, at the bottom right, click on the Python version. In the dropdown, choose the Python version from the conda environment.

Autocompletion will now work as expected.
Recommanded extensions: `ms-python.python`, `ms-python.pylint` and `ms-python.autopep8`
