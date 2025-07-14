cmake_minimum_required(VERSION 3.16)
project(VK-Aquifers)

set(CMAKE_CXX_STANDARD 17) # Draco requires C++14+

# Explicit Draco configuration
set(DRACO_INSTALL_DIR "/opt/draco")
set(DRACO_INCLUDE_DIR "${DRACO_INSTALL_DIR}/include")
set(DRACO_LIB_DIR "${DRACO_INSTALL_DIR}/lib")

# Verify Draco headers
if(NOT EXISTS "${DRACO_INCLUDE_DIR}/draco/compression/decode.h")
    message(FATAL_ERROR "Draco headers not found at ${DRACO_INCLUDE_DIR}/draco")
endif()

# Find Draco library
find_library(DRACO_LIBRARY
    NAMES draco
    PATHS ${DRACO_LIB_DIR}
    NO_DEFAULT_PATH
    REQUIRED
)

# Add Draco include directory to all targets
include_directories(${DRACO_INCLUDE_DIR})

# CGAL
find_package(CGAL QUIET COMPONENTS Core)

if(NOT CGAL_FOUND)
    message(STATUS "This project requires the CGAL library, and will not be compiled.")
    return()
endif()

# include helper file
include(${CGAL_USE_FILE})

# Boost
find_package(Boost REQUIRED)

if(NOT Boost_FOUND)
    message(STATUS "This project requires the Boost library, and will not be compiled.")
    return()
endif()

# Main executable
add_executable(viskar-geo-algo
    AquiferCalc.cpp
    FileIO.cpp
    TestSuite.cpp
    Main.cpp
)

target_link_libraries(viskar-geo-algo
    PRIVATE
    ${CGAL_LIBRARIES}
    ${CGAL_3RD_PARTY_LIBRARIES}
    ${DRACO_LIBRARY} # Link the Draco library
)

add_to_cached_list(CGAL_EXECUTABLE_TARGETS viskar-geo-algo)
file(COPY res DESTINATION ${CMAKE_BINARY_DIR})

# Python bindings
set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(PyGeoAlgo
    AquiferCalc.cpp
    FileIO.cpp
    Bindings.cpp
)

# Add Draco library to Python bindings
target_link_libraries(PyGeoAlgo PRIVATE
    ${DRACO_LIBRARY}
    ${CGAL_LIBRARIES}
    ${CGAL_3RD_PARTY_LIBRARIES}
)
