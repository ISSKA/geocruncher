#!/usr/bin/env bash
# Set up a local development venv that mirrors docker/Dockerfile's local stage.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

USER_SET_BOOST_PREFIX=0
USER_SET_CGAL_DIR=0
USER_SET_DRACO_PREFIX=0
USER_SET_DRACO_BUILD_DIR=0
[[ -v BOOST_PREFIX ]] && USER_SET_BOOST_PREFIX=1
[[ -v CGAL_DIR ]] && USER_SET_CGAL_DIR=1
[[ -v DRACO_PREFIX ]] && USER_SET_DRACO_PREFIX=1
[[ -v DRACO_BUILD_DIR ]] && USER_SET_DRACO_BUILD_DIR=1

DEPS_DIR="${DEPS_DIR:-"$ROOT_DIR/.cache/local-dev"}"
BUILD_JOBS="${BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)}"
FORGEO_GMLIB_MIN_GLIBC_VERSION="2.39"

BOOST_VERSION="${BOOST_VERSION:-1.90.0}"
BOOST_ARCHIVE_VERSION="${BOOST_VERSION//./_}"
BOOST_PREFIX="${BOOST_PREFIX:-"$DEPS_DIR/boost-$BOOST_VERSION"}"
BUILD_BOOST="${BUILD_BOOST:-auto}"

CGAL_VERSION="${CGAL_VERSION:-6.1.1}"
CGAL_DIR="${CGAL_DIR:-"$DEPS_DIR/CGAL-$CGAL_VERSION-library"}"

DRACO_PREFIX="${DRACO_PREFIX:-"$DEPS_DIR/draco"}"
DRACO_BUILD_DIR="${DRACO_BUILD_DIR:-"$DEPS_DIR/draco-build"}"

GEO_ALGO_DIR="$ROOT_DIR/geo-algo/VK-Aquifers"
GEO_ALGO_BUILD_DIR="${GEO_ALGO_BUILD_DIR:-"$GEO_ALGO_DIR/build"}"

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --deps-dir PATH        Local native dependency cache. Default: $DEPS_DIR
  --skip-boost-build     Use system Boost instead of building Boost $BOOST_VERSION locally.
  --help                Show this help message.

Environment overrides:
  DEPS_DIR, BUILD_JOBS, BOOST_VERSION, BUILD_BOOST,
  BOOST_PREFIX, CGAL_VERSION, CGAL_DIR, DRACO_PREFIX, DRACO_BUILD_DIR,
  GEO_ALGO_BUILD_DIR
EOF
}

log() {
    printf '\n==> %s\n' "$*"
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

version_at_least() {
    local actual="$1"
    local required="$2"
    local actual_major="${actual%%.*}"
    local actual_minor="${actual#*.}"
    local required_major="${required%%.*}"
    local required_minor="${required#*.}"

    actual_minor="${actual_minor%%.*}"
    required_minor="${required_minor%%.*}"

    if (( actual_major > required_major )); then
        return 0
    fi
    if (( actual_major == required_major && actual_minor >= required_minor )); then
        return 0
    fi
    return 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --deps-dir)
            [[ $# -ge 2 ]] || die "$1 requires a value"
            DEPS_DIR="$2"
            [[ "$USER_SET_BOOST_PREFIX" -eq 0 ]] && BOOST_PREFIX="$DEPS_DIR/boost-$BOOST_VERSION"
            [[ "$USER_SET_CGAL_DIR" -eq 0 ]] && CGAL_DIR="$DEPS_DIR/CGAL-$CGAL_VERSION-library"
            [[ "$USER_SET_DRACO_PREFIX" -eq 0 ]] && DRACO_PREFIX="$DEPS_DIR/draco"
            [[ "$USER_SET_DRACO_BUILD_DIR" -eq 0 ]] && DRACO_BUILD_DIR="$DEPS_DIR/draco-build"
            shift 2
            ;;
        --skip-boost-build)
            BUILD_BOOST=skip
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

download() {
    local url="$1"
    local dest="$2"

    if [[ -f "$dest" ]]; then
        return
    fi

    log "Downloading $(basename "$dest")"
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$dest" "$url"
    elif command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$dest" "$url"
    else
        die "Install wget or curl so native dependencies can be downloaded."
    fi
}

check_system_dependencies() {
    local missing=()

    need_cmd uv
    need_cmd cmake
    need_cmd make
    need_cmd tar

    if ! command -v c++ >/dev/null 2>&1 && ! command -v g++ >/dev/null 2>&1; then
        missing+=("build-essential")
    fi

    if ! command -v xz >/dev/null 2>&1; then
        missing+=("xz-utils")
    fi

    if [[ ! -d /usr/include/eigen3/Eigen ]]; then
        missing+=("libeigen3-dev")
    fi

    if [[ ! -f /usr/include/gmp.h && ! -f /usr/include/x86_64-linux-gnu/gmp.h ]]; then
        missing+=("libgmp-dev")
    fi

    if [[ ! -f /usr/include/mpfr.h && ! -f /usr/include/x86_64-linux-gnu/mpfr.h ]]; then
        missing+=("libmpfr-dev")
    fi

    if [[ "$BUILD_BOOST" == "skip" && ! -d /usr/include/boost ]]; then
        missing+=("libboost-dev")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        local apt_packages=(
            build-essential
            cmake
            wget
            ca-certificates
            xz-utils
            libgmp-dev
            libmpfr-dev
            libeigen3-dev
        )
        if [[ "$BUILD_BOOST" == "skip" ]]; then
            apt_packages+=(libboost-dev)
        fi

        printf 'Missing system packages needed by CGAL/PyGeoAlgo:\n' >&2
        printf '  %s\n' "${missing[@]}" >&2
        printf '\nOn Debian/Ubuntu, install them with:\n' >&2
        printf '  sudo apt-get install %s\n' "${apt_packages[*]}" >&2
        exit 1
    fi
}

check_python_wheel_platform() {
    if [[ "$(uname -s)" != "Linux" ]]; then
        return
    fi

    local libc_info
    local glibc_version
    libc_info="$(getconf GNU_LIBC_VERSION 2>/dev/null || true)"

    if [[ "$libc_info" != glibc\ * ]]; then
        return
    fi

    glibc_version="${libc_info#glibc }"
    if version_at_least "$glibc_version" "$FORGEO_GMLIB_MIN_GLIBC_VERSION"; then
        return
    fi

    cat >&2 <<EOF
This checkout cannot be synced into a local venv on this Linux host.

forgeo-gmlib is currently only published for manylinux_2_39_x86_64 on Linux,
which requires glibc $FORGEO_GMLIB_MIN_GLIBC_VERSION or newer. This host reports
glibc $glibc_version.

Use a newer Linux distribution for the local venv, such as Debian Trixie or
Ubuntu 24.04, or use the Docker local-dev setup from ./scripts/run.sh.
EOF
    exit 1
}

ensure_venv() {
    log "Creating/syncing Python venv"
    export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

    uv sync --managed-python --frozen --group dev --no-install-project
}

ensure_boost() {
    if [[ "$BUILD_BOOST" == "skip" ]]; then
        log "Skipping local Boost build; CMake will use system Boost"
        return
    fi

    if [[ -f "$BOOST_PREFIX/include/boost/version.hpp" ]]; then
        log "Using cached Boost at $BOOST_PREFIX"
        return
    fi

    local src_dir="$DEPS_DIR/src"
    local archive="$src_dir/boost_$BOOST_ARCHIVE_VERSION.tar.gz"
    local extracted="$src_dir/boost_$BOOST_ARCHIVE_VERSION"

    mkdir -p "$src_dir"
    download "https://archives.boost.io/release/$BOOST_VERSION/source/boost_$BOOST_ARCHIVE_VERSION.tar.gz" "$archive"

    if [[ ! -d "$extracted" ]]; then
        log "Extracting Boost"
        tar -xzf "$archive" -C "$src_dir"
    fi

    log "Building Boost $BOOST_VERSION"
    (
        cd "$extracted"
        ./bootstrap.sh --prefix="$BOOST_PREFIX"
        ./b2 -j"$BUILD_JOBS" install
    )
}

ensure_cgal() {
    if [[ -d "$CGAL_DIR" ]]; then
        log "Using cached CGAL at $CGAL_DIR"
        return
    fi

    local src_dir="$DEPS_DIR/src"
    local archive="$src_dir/CGAL-$CGAL_VERSION-library.tar.xz"
    local extracted="$src_dir/CGAL-$CGAL_VERSION-library"

    mkdir -p "$src_dir"
    download "https://github.com/CGAL/cgal/releases/download/v$CGAL_VERSION/CGAL-$CGAL_VERSION-library.tar.xz" "$archive"

    log "Extracting CGAL"
    tar -xf "$archive" -C "$src_dir"

    if [[ -d "$extracted" ]]; then
        mkdir -p "$(dirname "$CGAL_DIR")"
        mv "$extracted" "$CGAL_DIR"
    elif [[ -d "$src_dir/CGAL-$CGAL_VERSION" ]]; then
        mkdir -p "$(dirname "$CGAL_DIR")"
        mv "$src_dir/CGAL-$CGAL_VERSION" "$CGAL_DIR"
    else
        die "Could not find extracted CGAL directory in $src_dir"
    fi
}

ensure_draco() {
    if [[ -f "$DRACO_PREFIX/include/draco/compression/decode.h" ]]; then
        log "Using cached Draco at $DRACO_PREFIX"
        return
    fi

    log "Building Draco"
    cmake -S "$ROOT_DIR/third_party/draco" -B "$DRACO_BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$DRACO_PREFIX" \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    cmake --build "$DRACO_BUILD_DIR" --target install -j"$BUILD_JOBS"
}

build_pygeoalgo() {
    log "Building PyGeoAlgo"

    local python
    local pybind11_dir
    local site_packages
    python="$(uv run --no-sync python -c 'import sys; print(sys.executable)')"
    pybind11_dir="$(uv run --no-sync python -m pybind11 --cmakedir)"
    site_packages="$(uv run --no-sync python -c 'import sysconfig; print(sysconfig.get_paths()["platlib"])')"

    local cmake_args=(
        -S "$GEO_ALGO_DIR"
        -B "$GEO_ALGO_BUILD_DIR"
        -DCMAKE_BUILD_TYPE=Release
        -DPython_EXECUTABLE="$python"
        -Dpybind11_DIR="$pybind11_dir"
        -DDRACO_INSTALL_DIR="$DRACO_PREFIX"
        -DCGAL_DIR="$CGAL_DIR"
    )

    if [[ "$BUILD_BOOST" != "skip" ]]; then
        cmake_args+=(
            -DBoost_ROOT="$BOOST_PREFIX"
            -DBOOST_ROOT="$BOOST_PREFIX"
        )
    fi

    cmake "${cmake_args[@]}"
    cmake --build "$GEO_ALGO_BUILD_DIR" --target PyGeoAlgo -j"$BUILD_JOBS"
    cp "$GEO_ALGO_BUILD_DIR"/PyGeoAlgo.*.so "$site_packages"/
}

verify_setup() {
    log "Verifying imports"
    uv run --no-sync python -c 'import PyGeoAlgo; import geocruncher.geo_algo; print("PyGeoAlgo import OK")'
}

main() {
    cd "$ROOT_DIR"
    mkdir -p "$DEPS_DIR"

    check_python_wheel_platform
    check_system_dependencies
    ensure_venv
    ensure_boost
    ensure_cgal
    ensure_draco
    build_pygeoalgo
    verify_setup

    cat <<EOF

Local development venv is ready.

Activate it with:
  source .venv/bin/activate

For API/worker runs outside Docker, use a Redis reachable from the host:
  export REDIS_HOST=localhost
  ./scripts/api-local.sh
  ./scripts/worker-local.sh
EOF
}

main "$@"
