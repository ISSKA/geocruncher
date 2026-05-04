# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

WORKDIR /home/build

# Install runtime deps from the locked manifest + the server-only group.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group server --no-install-project

COPY celeryconfig.py /

# Jenkins build artifacts
COPY geo-algo/VK-Aquifers/PyGeoAlgo.*.so \
     /opt/venv/lib/python3.12/site-packages/
COPY dist/geocruncher-*.whl dist/
RUN uv pip install dist/geocruncher-*.whl

# use non-root user on dev/prod
# RUN useradd -ms /bin/bash geocruncher
# USER geocruncher
