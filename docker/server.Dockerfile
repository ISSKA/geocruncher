# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

# Gunicorn is only used as the dev/prod server
RUN pip install gunicorn

COPY celeryconfig.py /

# Jenkins build artifacts
# TODO
# COPY src/geo-algo/VK-Aquifers/viskar-geo-algo /usr/bin/viskar-geo-algo
COPY \
  dist/geocruncher-*.whl \
  dist/api-*.whl dist/
RUN pip install dist/geocruncher-*.whl dist/api-*.whl

# use non-root user on dev/prod
RUN useradd -ms /bin/bash geocruncher
USER geocruncher
