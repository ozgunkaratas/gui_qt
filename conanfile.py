from conan import ConanFile


class SignChecker(ConanFile):
    name = "signchecker"
    version = "1.0"

    # All build logic lives in the shared cmake-base package.
    # QtApp = CMakeAppBase + QtMixin (Qt detection, MSVC runtime fix, windeployqt).
    python_requires = "cmake-base/[>=1.0 <2]"
    python_requires_extend = "cmake-base.QtApp"
