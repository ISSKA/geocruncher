# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

# Used for hot reloading celery worker
RUN pip install "watchdog[watchmedo]"

# Build Draco first
WORKDIR /home/build/
COPY third_party/draco draco_src
RUN mkdir draco_build && cd draco_build && \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/draco ../draco_src && \
    make -j$(nproc) install

# Build geo-algo
COPY geo-algo/VK-Aquifers geo-algo/VK-Aquifers
RUN cd geo-algo/VK-Aquifers && \
    cmake -B build \
          -DCMAKE_BUILD_TYPE=Release \
          . && \
    cmake --build build --target PyGeoAlgo

RUN cp geo-algo/VK-Aquifers/build/PyGeoAlgo.* /usr/bin/

# set the workdir so the worker start script finds the mounted python code
WORKDIR /home/build/
