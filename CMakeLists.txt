cmake_minimum_required(VERSION 3.16)

project(tonatiuhpp-rays-selector LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(tonatiuhpp-rays-selector
    src/FileSorting.cpp
    src/ParametersFileReader.cpp
    src/PhotonOutputWriter.cpp
    src/RaySelector.cpp
    src/SurfaceMap.cpp
    src/TonatiuhPhotonReader.cpp
    src/main.cpp
)

target_include_directories(tonatiuhpp-rays-selector PRIVATE include)
