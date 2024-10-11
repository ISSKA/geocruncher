# Command Line Interface (DEPRECATED)

A dummy project is provided in order to test the installation. For example, to run the dummy computation of intersections, execute the following:
```bash
python -m geocruncher intersections tests/dummy_project/sections.json tests/dummy_project/geocruncher_project.xml tests/dummy_project/geocruncher_dem.asc tests/dummy_project out.json
```

A more helpful command line argument validation system is being worked on (DEPRECATED). You can already run geocruncher with `-h` or `--help` to get basic help. Note that:
- validation of parameters specific to each computation doesn't exist for now
- additional flags (such as for profiling) must always come last

In the meantime, you can find out what arguments are requiered and in which order by looking at the `main.run_geocruncher` function. Below each computation type, a comment indicates the list of parameters requiered.
