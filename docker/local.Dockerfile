# syntax = edrevo/dockerfile-plus
INCLUDE+ docker/Dockerfile.common

WORKDIR /home/build

# Install runtime + dev deps. Source is mounted over /home/build at runtime.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group dev --no-install-project

# Build Draco
COPY third_party/draco draco_src
RUN mkdir draco_build && cd draco_build && \
    cmake -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX=/opt/draco \
          -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
          ../draco_src && \
    make -j"$(nproc)" install

# Build geo-algo (PyGeoAlgo pybind11 module). Force CMake to use the venv's
# Python so the .so ABI matches what we'll import at runtime.
COPY geo-algo/VK-Aquifers geo-algo/VK-Aquifers
RUN cd geo-algo/VK-Aquifers && \
    cmake -B build \
          -DCMAKE_BUILD_TYPE=Release \
          -DPython_EXECUTABLE=/opt/venv/bin/python \
          -Dpybind11_DIR="$(/opt/venv/bin/python -m pybind11 --cmakedir)" \
          . && \
    cmake --build build --target PyGeoAlgo -j"$(nproc)"

# Place PyGeoAlgo into the venv's site-packages so `import PyGeoAlgo` works.
RUN cp geo-algo/VK-Aquifers/build/PyGeoAlgo.*.so \
       /opt/venv/lib/python3.12/site-packages/

WORKDIR /home/build/
