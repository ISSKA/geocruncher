# Geocruncher

Geocruncher is a standalone application for Geological Computations. It is a dependency of the [VisualKarsys webservice](https://visualkarsys.com) developped by [ISSKA/SISKA](https://www.isska.ch/en/).

It implements certain types of computations in Python and C++, and also acts as a link to libraries such as gmlib, develop by the [BRGM](https://www.brgm.fr/en).

It has the following architecture, handled by docker compose:

- A JSON API written in Flask, taking in computation requests, polls for statuses and returning results
- A Worker system using Celery, to handle computations in different work queues
- A message broker & temporary file storage & result backend using redis

Please check out the [documentation](./doc/api-examples.md) to see example API calls.

Documentation for each existing computation, their parameters and returned values will be added in the future. For now, please get in touch with [ISSKA/SISKA](https://www.isska.ch/en/) if you're interrested in learning more about the project.

Alternatively, a command line interface can be used to launch computations (**DEPRECATED**). See [documentation](./doc/command-line.md).

It posesses an optional integrated Profiler (currently only working in the command line version), used in production by the VisualKarsys team to estimate computation times and identify key areas where speed should be improved. 

## Installation

Please check the [documentation](./doc/dependencies.md) for additional dependencies.

We recommand using the latest version of Docker. Tested on Docker 24 to 27.
No other steps are requiered after cloning the repository. We recommand using the master branch.

```bash
git clone https://github.com/ISSKA/geocruncher
cd geocruncher
git checkout master
git submodule update --init # For VISKAR team, pre-built dependencies are available as a private submodule
```

## Development

To run Geocruncher in local development mode with Hot Reloading, run the script `./scripts/run.sh`

We recommand creating a python environment and installing the dependencies as done in the [Dockerfile.common](./docker/Dockerfile.common) in order to have correct syntax highlighting / autocompletion.

If using Visual Studio Code, the last step is to tell it which Python version to use. With a Python file open, at the bottom right, click on the Python version. In the dropdown, choose the Python version from the conda environment.

Autocompletion will now work as expected.
Recommanded extensions: `ms-python.python`, `ms-python.pylint` and `ms-python.autopep8`

## Deployment

Inside the Docker folder you will find the deployment files for the [VisualKarsys webservice](https://visualkarsys.com)'s infrastructure. We have a dev and prod environment, and use systemd services and journalctl for logging.

Please adapt to your needs.

The API exposes an HTTP server with no compression. We strongly recommand putting a proxy in front that handles HTTPS and GZIP compression to greatly improve security and performance.

Depending on your needs, we also recommand implementing basic authentification to prevent unwanted users from starting computations on your instance, if it is exposed to the internet.
