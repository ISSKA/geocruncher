# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

# Used for hot reloading celery worker
RUN pip install "watchdog[watchmedo]"

# geo-algo
WORKDIR /home/build/
COPY geo-algo/VK-Aquifers geo-algo/VK-Aquifers
RUN cd geo-algo/VK-Aquifers && cmake -DCMAKE_BUILD_TYPE=Release . && make
COPY PyGeoAlgo.* /usr/bin/

# set the workdir so the worker start script finds the mounted python code
WORKDIR /home/build/
