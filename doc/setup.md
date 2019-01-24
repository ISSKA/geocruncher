GeoCruncher developement setup
===============================
This section describes the setup necessary to get started with using geoCruncher.

## Version control

The source code for GeoCruncher is managed in a Git repository. To access the repository, you can use the Git command line, or alternatively a UI such as [SourceTree](http://sourcetreeapp.com).
* Repository URL: https://github.com/ISSKA/geocruncher
* Check out the **develop** branch before continuing.

## Requirements

To run geoCruncher need other libraries to be installed. The followings needs to be installed before running the python scripts:

* GmLib by brgm (Commit 2c7736a57906c48a8edfbc6348f0477512debbd6 or later)
* MeshTools by brgm (Commit 20e68f3bcc0581cbc79affb6abc7b470fe0243fb or later)
* scikit-image >= 0.14.0
* CGAL >= 4.13
* numpy
 
### On Linux

### numpy

1. run the following key:
	
        pip install numpy

Or for python3

	pip3 install numpy

### GmLib

1. run the following key to clone the gmlib repository:

	git clone https://gitlab.inria.fr/gmlib/gmlib.git

2. You will need to enter your Gitlab INRIA username and password.

3. Within your git repository run the following key:

	pip install -e .

Or for python3

	pip3 install -e .

### CGAL

### On Windows

1.  Install PostgreSQL 9 (x64) version >= 9.6.8 (see
    <https://www.enterprisedb.com/downloads/postgres-postgresql-downloads>
    )

2.  A psql prompt should have been installed as well as PostgreSQL, this prompt should be used used for all database related command. The windows original prompt does not understand psql requests

3.  Within the psql prompt, as an admin user, execute the following
    command:

        CREATE ROLE viskar WITH LOGIN PASSWORD 'isska' SUPERUSER;

4.  Install PostGIS  (Choose the version corresponding to your PostgreSQL version and windows (64 or 32)
    <https://download.osgeo.org/postgis/windows/>
    )

### On Linux

1.  Install PostgreSQL 9 version >= 9.6.8 & PostGIS 2.3. You can use your favorite package manager.
    On Ubuntu 16.04, however, the 9.6 version isn't avaiable by default but you can add the following key:

        sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt xenial-pgdg main" >> /etc/apt/sources.list'
        wget --quiet -O - http://apt.postgresql.org/pub/repos/apt/ACCC4CF8.asc | sudo apt-key add -
        sudo apt-get update

        sudo apt-get install postgresql-9.6
        sudo apt-get install postgresql-9.6-postgis-2.3

    (commands taken from [here](https://trac.osgeo.org/postgis/wiki/UsersWikiPostGIS23UbuntuPGSQL96Apt))

2.  There are many mysteries in the universe, and the default logging behavior of PostgreSQL is one of them.
    For some reasons, one cannot directly log in with the default user `postgres`. For that, we should alter
    the configuration file `pg_hfa.conf`:

        cd /etc/postgresql/9.6/main/
        sudo cp pg_hba.conf pg_hba.conf.bkp    # backup

    Then open the file `pg_hba.conf` with super user rights and find the following line

        local   all             postgres                                <whatever value>

    Change `<whatever value>` to `trust` and save the file (with nano: Ctrl-O then Ctrl-X).
    Note that this isn't secure as no password will be prompted when logging with the user postgres,
    but this should be sufficient in our case.

    Now restart the server:

        sudo service postgresql restart

    Et voilà ! Now we should be able to log-in with the (only) user, namely postgres

        psql -U postgres

3.  In psql, create the user viskar:

        CREATE ROLE viskar WITH LOGIN PASSWORD 'isska' SUPERUSER;

    However, we should repeat almost the same operations as before, i.e. edit `pg_hba.conf` to be able to connect
    as the user viskar:

        cd /etc/postgresql/9.6/main/

    Then open again the file `pg_hba.conf` find the following line

        local   all             viskar                                <whatever value>

    Change `<whatever value>` to `md5` and save the file. We also should restart the server:

        sudo service postgresql restart

    Currently, viskar doesn't have any DB; the creation of the developpment DB and
    the test DB will be discussed in [“DB Initialization”](#db-init)
    After that, you can directly log into the DB of your choice with viskar:

        psql -U viskar viskar # developpment DB, used by the local webserver

    Or

        psql -U viskar viskar_test # DB only used for the tests

### Useful commands in psql
* Connect to a different database: `\c <database name>`
* Execute a SQL script: `\i <script name>`
* Show information about a table: `\d <table name>`

## Frontend Setup
**Recommended IDE: Visual Studio Code**

**Debugging:** In VS Code, install the Debugger for Chrome to enable debugging the TypeScript code. Alternatively, the browser's developer tools may be used, but may not support source maps (mapping the JavaScript at runtime to the TypeScript source).

We use Yarn for package management. The packages must be installed before running the front-end.

1.  Install yarn from <https://yarnpkg.com/en/docs/install>

2.  Select the “<REPO>/src/client” folder

3.  In the command line, run `yarn install`. This installs the required node packages.

4.  In the command line, run `yarn start` to run the development server

## Backend Setup
**Recommended IDE: IntelliJ IDEA**

1.  Install the Java Development Kit (JDK) 8 or newer

2.  Install an integrated development environment (IDE). IntelliJ IDEA
    by Jet Brains is recommended. The Community Edition should suffice.
    All further steps assume IntelliJ IDEA.

    1.  Install the Scala plugin for IntelliJ. This can be done on first
        startup or from the splash window, clicking on “configuration”,
        then “plugins”.

3.  Click on “Import project”

4.  Select the “&lt;REPO&gt;/src/server” folder

5.  Select “Import project from external model” - “SBT”

6.  Click on “Finish”

7.  Click on “Ok” in the “SBT Project Data To Import” dialog

### Database Initialization<a name="db-init"></a>

All database setup actions are performed through the `viskar-admin` utility in the backend.
This includes database migrations and creating test users. To setup the backend development environment,
carry out the following steps in IntelliJ IDEA:

1.  Go to the menu “Run” - “Edit configurations”

2.  In the “Run/Debug Configurations” window, press the plus button and
    select “Application”.

3.  Optionally, give a name to the task to remember what it is

4.  Set “Main class” to “ch.isska.viskar.admin.Main”

5.  Set "Use classpath of module" to "admin"

6.  Set "Program arguments" to `setup-dev-env`

7.  Press “Ok” to save the configuration

8.  Run the task. This can be done from the “Run” menu.

### Running the REST API

1.  Go to the menu “Run” - “Edit configurations”

2.  In the “Run/Debug Configurations” window, press the plus button and
    select “Application”.

3.  Optionally, give a name to the task to remember what it is

4.  Set “Main class” to “ch.isska.viskar.restAPI.Main”

5.  Set "Use classpath of module" to "restAPI"

6.  Set no "Program arguments"

7.  Press “Ok” to save the configuration

8.  At the beginning of each session you need to run this application to start the server.

9. To test if it worked, navigate to “localhost:3145/v1.0/public/swagger.json” in a
    web browser. You should see the swagger API docs.

### Updating the data-base

1.  After each update of the database schema, and on the first start, the database migration job
    needs to be run. To achieve this, run the `viskar-admin` task with the argument `migrate-db`.

2.  On the first start, and after each time the translation files have been updated, you
    need to execute the `sbt compile` task to compile the translations to scala. Do this
    by opening the "SBT projects" pane in IntelliJ Idea, select the
    task "VisKar > root > SBT Tasks > compile" and double click on it.

3.  By default, you can log in with the test user: `test@visualkarsys.isska.ch` and password `test`.
    You can also create an account by executing `viskar-admin` with the arguments `create-user --email test@test.ch --user-name test --password MyPassword`.

4.  If you wish, you can load the pilot project by executing `viskar-admin` with the arguments
    `load-sample-project --owner-email test@test.ch`.

## Application Config
A number of properties must be defined for your development environment. A configuration file is used for the backend properties: `src/server/logic/src/main/resources/application.conf`

To begin, make a copy of the template file `application.conf.dev_example`, named `application.conf`, and make your changes there. The config file must be edited for the algorithm utilities, detailed below.

## Algorithm utilities

### GeoCruncher
GeoCruncher is a Python package required for computing geological meshes and interfaces.

1. Downloaded the source from the repository: https://github.com/ISSKA/geocruncher

2. Follow the installation guide for GeoCruncher and its dependencies

3. Update the backend application config

3.1 Add `python-path` to the file and make it point to the python.exe location

3.2 Set `geocruncher-script-path` to point to GeoCruncher's main.py file

### GeoAlgo
The geo-algo directory contains C++ applications for running algorithms on geological meshes. Currently, this is limited to the VK-Aquifers application.

1. Use CMake to generate an IDE project. Set the source code directory to `src/geo-algo/VK-Aquifers`

2. Build the project using your IDE/compiler of choice

3. Update the backend application config. Set `geo-algo-path` to point to the executable file you built (build mode: release, not debug)

### Sec Export

The sec-export utility is required when exporting a project to GeoModeller. This step is therefore optional. The application must only be built once, unless its source code is modified.

These instructions are specific to Linux.

1.  To build, you will need a C++ compiler (which is usually shipped with your distribution) and CMake.
    You can install CMake by typing the following command to the terminal:

        sudo apt-get install cmake

2.  You'll also need the OpenCascade library.

        sudo apt-get install liboce-*

    (Note that this is the community edition; if you want the official one, you'll have to download the
    sources and compile them by yourself, but this shouldn't be a problem)

2.  Navigate to the `src/sec-export` folder.

3.  Execute the following commands:

        cmake .
        make

    This will create an executable named `viskar-sec-export`.

 4. Path configuration

    Edit the application config, as described above, and set the property `geomodeller-sec-export-helper` to the
    absolute path to the sec-export executable you just created (including the filename).

## Integration Tests

The integration tests require a fully setup Visual Karsys database to run. On the continous
integration server, this is handled automatically and fresh database is created from scratch
for each build.

If you want to run the integration tests locally, execute "sbt it:test". You may need to re-run
the ``viskar-admin setup-dev-env`` command beforehand if the db schema has changed.