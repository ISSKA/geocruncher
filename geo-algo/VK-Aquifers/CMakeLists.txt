cmake_minimum_required(VERSION 3.16)
project(VK-Aquifers)

set(CMAKE_CXX_STANDARD 17) # Draco requires C++14+

# Add Draco library
include(FetchContent)
FetchContent_Declare(
    draco
    GIT_REPOSITORY https://github.com/google/draco
    GIT_TAG 4e12ab27d0fe690cf98e96dc33c2bd52e1485163
)
FetchContent_MakeAvailable(draco)

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
    draco
)
set_property(TARGET viskar-geo-algo PROPERTY POSITION_INDEPENDENT_CODE ON)

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
    draco
    ${CGAL_LIBRARIES}
    ${CGAL_3RD_PARTY_LIBRARIES}
)

# Install the Python extension
install(TARGETS PyGeoAlgo DESTINATION .)
