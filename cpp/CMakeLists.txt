cmake_minimum_required(VERSION 3.20)
project(package_name LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

option(BUILD_TESTS "Build test suite" ON)

# ---- Warnings ----
add_library(project_warnings INTERFACE)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(project_warnings INTERFACE
    -Wall -Wextra -Wpedantic -Wshadow -Wconversion
  )
endif()

# ---- Library ----
add_library(package_name_lib
  src/example.cpp
)
target_include_directories(package_name_lib PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(package_name_lib PRIVATE project_warnings)

# ---- Executable ----
add_executable(package_name src/main.cpp)
target_link_libraries(package_name PRIVATE package_name_lib project_warnings)

# ---- Tests ----
if(BUILD_TESTS)
  include(FetchContent)
  FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
  )
  # Windows: force shared CRT to match GTest defaults
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)

  enable_testing()
  add_executable(unit_tests tests/test_example.cpp)
  target_link_libraries(unit_tests PRIVATE
    package_name_lib
    GTest::gtest_main
    project_warnings
  )

  include(GoogleTest)
  gtest_discover_tests(unit_tests)
endif()
