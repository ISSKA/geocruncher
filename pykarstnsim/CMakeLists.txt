cmake_minimum_required(VERSION 3.15)
project(KarstNSim VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17 CACHE STRING "The C++ standard to use")
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
include(ProcessorCount)
ProcessorCount(NPROC)
set(CMAKE_BUILD_PARALLEL_LEVEL ${NPROC})

find_package(pybind11 CONFIG REQUIRED)

# Fetch library
include(FetchContent)
FetchContent_Declare(
    karstnsim_repo
    GIT_REPOSITORY https://github.com/ISSKA/KarstNSim_Public.git
    GIT_TAG c1c0b6cd463acd493813381d27a44335b480dbe4
)
FetchContent_GetProperties(karstnsim_repo)
if (NOT karstnsim_repo_POPULATED)
    FetchContent_Populate(karstnsim_repo)
endif()

set(KARSTNSIM_PATH ${karstnsim_repo_SOURCE_DIR})

#add_compile_options(-Wall -Wextra -pedantic)

# Library source (exclude main.cpp)
set(KARSTNSIM_LIB_SOURCES 
    ${KARSTNSIM_PATH}/KarstNSim/src/karstic_network.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/surface_sampling.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/cost_graph.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/geostats.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/ghost_rocks.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/randomgenerator.cpp  
    ${KARSTNSIM_PATH}/KarstNSim/src/write_files.cpp 
    ${KARSTNSIM_PATH}/KarstNSim/src/simplex_noise.cpp
    ${KARSTNSIM_PATH}/KarstNSim/src/graph_operations.cpp  
    ${KARSTNSIM_PATH}/KarstNSim/src/read_files.cpp
    ${KARSTNSIM_PATH}/KarstNSim/src/karstic_skeleton.cpp  
    ${KARSTNSIM_PATH}/KarstNSim/src/run_code.cpp
    ${KARSTNSIM_PATH}/KarstNSim/src/parse_inputs.cpp
)

# Create library
add_library(karstnsim_objs OBJECT ${KARSTNSIM_LIB_SOURCES})
target_include_directories(karstnsim_objs PUBLIC ${KARSTNSIM_PATH}/KarstNSim/include)
set_property(TARGET karstnsim_objs PROPERTY POSITION_INDEPENDENT_CODE ON)

# Create the Python extension
pybind11_add_module(pykarstnsim_core karstnsim_bindings.cpp $<TARGET_OBJECTS:karstnsim_objs>)
target_include_directories(pykarstnsim_core PRIVATE ${KARSTNSIM_PATH}/KarstNSim/include)

# Find a Python interpreter to run stub generation
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# Generate .pyi stubs for the built extension and install them into the wheel
set(PYKARSTNSIM_STUB_OUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/stubs)
set(PYKARSTNSIM_STUB_PYI ${PYKARSTNSIM_STUB_OUT_DIR}/pykarstnsim_core.pyi)

add_custom_command(TARGET pykarstnsim_core POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory ${PYKARSTNSIM_STUB_OUT_DIR}
    COMMAND ${CMAKE_COMMAND} -E env
            PYTHONPATH=$<TARGET_FILE_DIR:pykarstnsim_core>
            ${Python3_EXECUTABLE} -m pybind11_stubgen pykarstnsim_core -o ${PYKARSTNSIM_STUB_OUT_DIR}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/fix_typings.py ${PYKARSTNSIM_STUB_PYI}
    BYPRODUCTS ${PYKARSTNSIM_STUB_PYI}
    COMMENT "Generating .pyi stubs for pykarstnsim_core"
)

# Install the Python extension and stubs
install(TARGETS pykarstnsim_core DESTINATION .)
install(FILES ${PYKARSTNSIM_STUB_PYI} DESTINATION .)
