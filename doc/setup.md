GeoCruncher developement setup
===============================
This section describes the setup necessary to get started with using geoCruncher.

## Version control

The source code for GeoCruncher is managed in a Git repository. To access the repository, you can use the Git command line, or alternatively a UI such as [SourceTree](http://sourcetreeapp.com).
* Repository URL: https://github.com/ISSKA/geocruncher
* Check out the **develop** branch before continuing.

## Requirements

To run geoCruncher need other libraries to be installed. The followings needs to be installed before running the python scripts:

* Eigen
* GmLib by brgm (Commit 2c7736a57906c48a8edfbc6348f0477512debbd6 or later)
* MeshTools by brgm (Commit 20e68f3bcc0581cbc79affb6abc7b470fe0243fb or later)
* scikit-image >= 0.14.0
* CGAL >= 4.13
* numpy
 
### On Linux

### numpy

1. run the following key:
	
        pip install numpy

2. Or for python3
	
        pip3 install numpy

### Eigen

1. Download the eigen3 library in tar.gz format at their website (http://eigen.tuxfamily.org/index.php?title=Main_Page) or using this link directely:
	
        http://bitbucket.org/eigen/eigen/get/3.3.7.tar.gz

2. Create a folder named eigen-build.

3. Run cmake-gui, select the original eigen folder for the source code and eigen-build to build binaries. Then configure and generate.

4. If the generation have been succesful, go to the eigen-build folder and run:
	
        make install .

### GmLib

1. run the following key to clone the gmlib repository:

        git clone https://gitlab.inria.fr/gmlib/gmlib.git

2. You will need to enter your Gitlab INRIA username and password.

3. Within your git repository run the following key:
	
        pip install -e .

Or for python3
	
        pip3 install -e .

From now on you can compute intersections, however to compute meshes you still need two package CGAL and Meshtools

### CGAL

1. run the following key to clone the cgal repository:
	
        git clone https://github.com/CGAL/cgal.git

2. Create a folder named cgal-build.

3. Run cmake-gui, select the original cgal folder for the source code and cgal-build to build binaries. Then configure and generate.

4. Tick yes for CGAL_HEADER_ONLY and CGAL_DEV_MODE options.

5. If the generation have been succesful, go to the cgal-build folder and run:

        make install .

### Meshtools

1. run the following key to clone the gmlib repository:
	
	git clone https://gitlab.inria.fr/charms/MeshTools.git

2. You will need to enter your Gitlab INRIA username and password.

3. Setup the path to your cgal location usually by runnning:
	
	export CGAL_DIR=/usr/local/lib/cmake/CGAL

	
4. Within your git repository run the following key:
	
        pip install .

Or for python3
	
        pip3 install .
