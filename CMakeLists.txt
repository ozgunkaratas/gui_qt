cmake_minimum_required(VERSION 3.16)
project(SignChecker VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_AUTOMOC ON)   # runs moc on headers with Q_OBJECT  -> moc_*.cpp
set(CMAKE_AUTOUIC ON)   # runs uic on *.ui files             -> ui_*.h

find_package(Qt6 REQUIRED COMPONENTS Widgets)

add_executable(SignChecker
    main.cpp
    model.h  model.cpp
    view.h   view.cpp
    inputdialog.ui
    resultdialog.ui
)

target_link_libraries(SignChecker PRIVATE Qt6::Widgets)

if(WIN32)
    set_target_properties(SignChecker PROPERTIES WIN32_EXECUTABLE ON)  # no console window
endif()

# Visual Studio: start SignChecker on F5 instead of ALL_BUILD.
set_property(DIRECTORY PROPERTY VS_STARTUP_PROJECT SignChecker)

# Visual Studio: let the debugger find the Qt DLLs for every configuration.
set_target_properties(SignChecker PROPERTIES
    VS_DEBUGGER_ENVIRONMENT "PATH=${QT6_INSTALL_PREFIX}/${QT6_INSTALL_BINS};%PATH%")

# Used by `conan create` / the recipe's package() step.
install(TARGETS SignChecker RUNTIME DESTINATION bin)
