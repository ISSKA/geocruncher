# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

# Used for hot reloading celery worker
RUN pip install "watchdog[watchmedo]"

# TODO
# geo-algo
# WORKDIR /home/build/
# COPY src/geo-algo/VK-Aquifers src/geo-algo/VK-Aquifers
# RUN cd src/geo-algo/VK-Aquifers && cmake -DCMAKE_BUILD_TYPE=Release . && make
# COPY src/dist src/dist

# set the workdir so the worker start script finds the mounted python code
WORKDIR /home/build/src
