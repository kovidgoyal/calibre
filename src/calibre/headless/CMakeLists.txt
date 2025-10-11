cmake_minimum_required(VERSION 3.21)
project(headless)
set(CMAKE_AUTOMOC ON)
__FIND_GUI__
find_package(Qt6 REQUIRED COMPONENTS Gui GuiPrivate Core CorePrivate)
add_library(headless MODULE main.cpp headless_backingstore.cpp headless_integration.cpp)
set_property(TARGET headless PROPERTY QT_PLUGIN_TYPE "platforms")
set_property(TARGET headless PROPERTY QT_PLUGIN_CLASS_NAME "HeadlessIntegrationPlugin")
__LINK_TARGETS__
