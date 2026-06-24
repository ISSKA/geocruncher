FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS base

ENV TZ=Europe/Zurich
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Build toolchain + system C/C++ libraries.
# - build-essential, cmake: compiling Boost / CGAL / Draco / PyGeoAlgo.
# - libgmp-dev, libmpfr-dev, libeigen3-dev: required by CGAL.
# - The matching runtime libs (libgmp10, libmpfr6) come in as deps of *-dev,
#   so PyGeoAlgo.so loads at runtime without further installs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake wget ca-certificates xz-utils git \
        libgmp-dev libmpfr-dev libeigen3-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN wget -q https://archives.boost.io/release/1.90.0/source/boost_1_90_0.tar.gz \
 && tar -xzf boost_1_90_0.tar.gz \
 && rm boost_1_90_0.tar.gz \
 && cd boost_1_90_0 \
 && ./bootstrap.sh --prefix=/usr/local \
 && ./b2 -j"$(nproc)" install \
 && cd /opt && rm -rf boost_1_90_0

RUN wget -q https://github.com/CGAL/cgal/releases/download/v6.1.1/CGAL-6.1.1-library.tar.xz \
 && tar -xf CGAL-6.1.1-library.tar.xz \
 && rm CGAL-6.1.1-library.tar.xz

WORKDIR /

# uv project venv. Sync happens in downstream stages.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH

COPY /scripts/* /home/build/scripts/


# Jenkins build agent: bare venv with pybind11 for compiling native modules.
FROM base AS build

RUN uv venv /opt/venv \
 && uv pip install "pybind11[global]"


# Local dev image: full dev deps + in-image Draco / PyGeoAlgo build.
# Source is mounted over /home/build at runtime.
FROM base AS local

WORKDIR /home/build

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


# Server image (dev/prod): consumes Jenkins-built artifacts.
FROM base AS server

WORKDIR /home/build

# Install runtime deps from the locked manifest + the server-only group.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group server --no-install-project

COPY celeryconfig.py ./

# Jenkins build artifacts
COPY geo-algo/VK-Aquifers/PyGeoAlgo.*.so \
     /opt/venv/lib/python3.12/site-packages/
COPY dist/geocruncher-*.whl dist/
RUN uv pip install dist/geocruncher-*.whl

# use non-root user on dev/prod
# RUN useradd -ms /bin/bash geocruncher
# USER geocruncher
