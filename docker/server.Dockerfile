# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

# Gunicorn is only used as the dev/prod server
RUN pip install gunicorn

COPY celeryconfig.py /

# Jenkins build artifacts
COPY geo-algo/VK-Aquifers/PyGeoAlgo.* /usr/bin/
COPY \
  dist/geocruncher-*.whl \
  dist/api-*.whl dist/
RUN pip install dist/geocruncher-*.whl dist/api-*.whl

# use non-root user on dev/prod
RUN useradd -ms /bin/bash geocruncher
USER geocruncher
# use the correct conda environment with this user
RUN echo "conda activate geocruncher" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]
