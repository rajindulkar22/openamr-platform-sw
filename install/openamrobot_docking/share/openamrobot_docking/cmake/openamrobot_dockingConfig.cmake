# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_openamrobot_docking_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED openamrobot_docking_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(openamrobot_docking_FOUND FALSE)
  elseif(NOT openamrobot_docking_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(openamrobot_docking_FOUND FALSE)
  endif()
  return()
endif()
set(_openamrobot_docking_CONFIG_INCLUDED TRUE)

# output package information
if(NOT openamrobot_docking_FIND_QUIETLY)
  message(STATUS "Found openamrobot_docking: 0.0.1 (${openamrobot_docking_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'openamrobot_docking' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT openamrobot_docking_DEPRECATED_QUIET)
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(openamrobot_docking_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${openamrobot_docking_DIR}/${_extra}")
endforeach()
