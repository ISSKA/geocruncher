GeoCruncher
===========

A small wrapper for the gmlib library. Intended as a stand-alone executable reading input data from files.

To run the dummy project:

```
python -m geocruncher all tests/dummy_project/sections.json tests/dummy_project/geocruncher_project.xml tests/dummy_project/geocruncher_dem.asc  out.json
```

To run the tests:

```
python setup.py test
```


Development Setup
=================

GeoCruncher developement setup
===============================

## Version control

The source code for GeoCruncher is managed in a Git repository. To access the repository, you can use the Git command line, or alternatively a UI such as [SourceTree](http://sourcetreeapp.com).
* Repository URL: https://github.com/ISSKA/geocruncher
* Check out the **develop** branch before continuing.

## Requirements

To run geoCruncher need other libraries to be installed. The followings needs to be installed before running the python scripts:

* Eigen
* GmLib by brgm (Commit 2c7736a57906c48a8edfbc6348f0477512debbd6 or later)
* MeshTools by brgm (Commit 5923bad641f5fe82622a0b33e73806177a0f4690 or later)
* scikit-image >= 0.14.0
* CGAL >= 4.13
* numpy
 
##  Setup with linux 

### Geocruncher

1. run the following key to clone the geocruncher repository:

        git clone https://github.com/ISSKA/geocruncher.git

2. To be able to run the python script you need to manually change some files within geoCruncher. 


### numpy

1. run the following key:
	
        pip install numpy

2. Or for python3
	
        pip3 install numpy

### Eigen

* INSTALL.md URL: https://github.com/libigl/eigen/blob/master/INSTALL

1. Download the eigen3 library in tar.gz format at their website (http://eigen.tuxfamily.org/index.php?title=Main_Page) or using this link directely:
	
        http://bitbucket.org/eigen/eigen/get/3.3.7.tar.gz

2. Create a folder named eigen-build.

3. Run cmake-gui, select the original eigen folder for the source code and eigen-build to build binaries. Then configure and generate.

4. If the generation have been succesful, go to the eigen-build folder and run:
	
        make install .

### GmLib

* INSTALL.md URL: https://gitlab.inria.fr/gmlib/gmlib/blob/master/INSTALL.md

1. run the following key to clone the gmlib repository:

        git clone https://gitlab.inria.fr/gmlib/gmlib.git

2. You will need to enter your Gitlab INRIA username and password.

3. Within your git repository run the following key:
	
        pip install -e .

Or for python3
	
        pip3 install -e .

From now on you can compute intersections, however to compute meshes you still need two package CGAL and Meshtools

### CGAL

* INSTALL.md URL: https://github.com/CGAL/cgal/blob/master/INSTALL.md

1. run the following key to clone the cgal repository:
	
        git clone https://github.com/CGAL/cgal.git

2. Create a folder named cgal-build.

3. Run cmake-gui, select the original cgal folder for the source code and cgal-build to build binaries. Then configure and generate.

4. Tick yes for CGAL_HEADER_ONLY and CGAL_DEV_MODE options.

5. If the generation have been succesful, go to the cgal-build folder and run:

        make install .

### Meshtools

* INSTALL.md URL: https://gitlab.inria.fr/charms/MeshTools/blob/master/INSTALL.md

1. run the following key to clone the gmlib repository:
	
	git clone https://gitlab.inria.fr/charms/MeshTools.git

2. You will need to enter your Gitlab INRIA username and password.

3. Setup the path to your cgal location usually by runnning:
	
	export CGAL_DIR=/usr/local/lib/cmake/CGAL

4. Within your git repository run the following key:
	
        pip install .

Or for python3
	
        pip3 install .

##  Setup for windows


The steps for windows are the same than for linux but some of the tools used and integrated within linux have to be installed for windows.

### Additional Requirements for windows

* Assure that pip (or pip3) have been installed
* Install a make command for windows
* Install cmake
* Install a c++ compiler for cmake (VisualStudio usually)

### Windows command

To run many of the command lines you will have to use alternative prompts, for example a bash prompt is needed to execute the make command. Moreover you may have to start the prompt as an administrator.
