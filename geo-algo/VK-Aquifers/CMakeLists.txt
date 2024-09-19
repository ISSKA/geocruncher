cmake_minimum_required(VERSION 3.16)
project( VK-Aquifers )

set (CMAKE_CXX_STANDARD 11)

# CGAL and its components
find_package( CGAL QUIET COMPONENTS Core )

if ( NOT CGAL_FOUND )
  message(STATUS "This project requires the CGAL library, and will not be compiled.")
  return()
endif()

# include helper file
include( ${CGAL_USE_FILE} )

# Boost and its components
find_package( Boost REQUIRED )

if ( NOT Boost_FOUND )
  message(STATUS "This project requires the Boost library, and will not be compiled.")
  return()
endif()


# Geo-algo
# ############################

add_executable( viskar-geo-algo  AquiferCalc.cpp FileIO.cpp TestSuite.cpp Main.cpp )

add_to_cached_list( CGAL_EXECUTABLE_TARGETS viskar-geo-algo )

file(COPY res DESTINATION ${CMAKE_BINARY_DIR})

# Link the executable to CGAL and third-party libraries
target_link_libraries(viskar-geo-algo   ${CGAL_LIBRARIES} ${CGAL_3RD_PARTY_LIBRARIES} )


# Python Bindings
# ############################

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(PyGeoAlgo AquiferCalc.cpp FileIO.cpp Bindings.cpp)
