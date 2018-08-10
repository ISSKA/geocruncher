GeoCruncher protocol
====================

GeoCruncher accepts commands on its standard input stream in a line based format. Standard error is used for logging.

Example session:

    python main.py
    $> SetProjectData project.xml
    $> SetProjectDEM test.dem
    $> ComputeImplicitModel
    $> QueryBoundariesCrossSection (10,20,30) (40,50,60) out.png
    $> QueryMeshes outdir/

Commands
--------

| Command                                 | Inputs                  | Outputs       | Description |
|-----------------------------------------|-------------------------|---------------|-------------|
| ``SetProjectData PROJECTFILE``          | Project XML File Path   | -             | Set project settings (location, size) and geological data. Only contains small data which is fast to transfer. |
| ``SetProjectDEM DEMFILE``               | DEM File Path           | -             | Set project DEM. |
| ``ComputeImplicitModel``                | -                       | -             | Computes the implicit model/the rank function. |
| ``QueryBoundariesCrossSection (X1,Y1,Z1) (X2,Y2,Z2) OUTFILE`` | lower left, upper right, output file name | PNG picture with boundaries | Draw boundaries between units on a virtual cross section. |
| ``QueryMeshes OUTDIR``                  | Output directory        | Meshes        | Build full meshes from an implicit model. |
| ``Shutdown``                            | -                       | -             | Shutdown geocruncher |


Testing
-------

You may collect the commands into a file and pipe them into geocruncher for testing:

    my_example_commands.txt > python main.py
