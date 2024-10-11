# Prebuilt libraries

Geocruncher currently requires 4 private dependencies managed by the BRGM. Please Inquire with BRGM to gain access.
For our use case, we use pre built binaries with the following versions:

| Depencency | Version used |
|------------|--------------|
| gmlib      | 0.3.22       |
| MeshTools  | main@5a02671 |
| pycgal     | 0.3.14       |
| vtkwriters | 0.0.10       |

The documentation below explains how to generate each prebuilt binary. This is needed when upgrading dependencies, or when you need to compile them for a different platform.
For each, the resultintg `.whl` file will be created in a `dist` subfolder. You can copy that file to `geocruncher/geocruncher-dist/`, and delete the old one.

Don't forget to update the version you want to install inside `Dockerfile.common`


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
# Choose here the python version that corresponds to the production environment
# Look for the "conda create" command in the Dockerfiles
conda create -n viskar39 python=3.9
conda activate viskar39
```

## gmlib

The source code is available here: https://gitlab.brgm.fr/brgm/geomodelling/internal/gmlib

```bash
sudo apt install cmake libeigen3-dev
pip install build
git clone https://gitlab.brgm.fr/brgm/geomodelling/internal/gmlib
cd gmlib
# Check out specific version you want to build
git checkout v0.3.22
python -m build --wheel
```

## MeshTools

The source code is available here: https://gitlab.brgm.fr/brgm/modelisation-geologique/meshtools

```bash
sudo apt install cmake
pip install scikit-build numpy
git clone https://gitlab.brgm.fr/brgm/modelisation-geologique/meshtools
cd meshtools
# Check out specific version you want to build
git checkout v0.0.8
python setup.py bdist_wheel
```

This package seems to build with version number 0.0.0. Manually correct the .whl file name.
The version number inside is likely irrelevant to us. We just need the Docker build to detect the new version for cache busting.

## pycgal

The source code is available here: https://gitlab.brgm.fr/brgm/geomodelling/internal/pycgal

```bash
sudo apt install cmake libeigen3-dev libcgal-dev libboost-all-dev libgmp-dev libmpfr-dev
pip install scikit-build
git clone https://gitlab.brgm.fr/brgm/geomodelling/internal/pycgal
cd pycgal
# Check out specific version you want to build
git checkout v0.3.14
python setup.py bdist_wheel
```

Beware, this one is particularly slow to compile.

## vtkwriters

The source code is available here: https://github.com/BRGM/vtkwriters

```bash
sudo apt install cmake
pip install scikit-build
git clone https://github.com/BRGM/vtkwriters
cd vtkwriters
# Check out specific version you want to build
git checkout v0.0.10
python setup.py bdist_wheel
```

# Other dependencies

Every other dependency is managed by the Dockerfiles and installed from conda or pip.
