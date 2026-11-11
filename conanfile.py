import os
import re
import shutil
import subprocess
from pathlib import Path

from conan import ConanFile
from conan.errors import ConanException
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout


class SignCheckerRecipe(ConanFile):
    """Build recipe for SignChecker.

    No Conan dependencies: Qt 6 is taken from your local installation and
    found automatically, so plain `conan build .` is enough.

    Lookup order (first hit wins):
      1. option      conan build . -o "&:qt_dir=C:/Qt/6.8.0/msvc2022_64"
      2. env var     QT_DIR=C:/Qt/6.8.0/msvc2022_64
      3. qtpaths6 / qtpaths / qmake6 / qmake found on PATH
      4. scan of Qt installer folders (C:/Qt, ~/Qt, QT_ROOT env var):
         newest Qt 6.x whose kit matches the profile's compiler and arch
    """

    name = "signchecker"
    version = "1.0"
    package_type = "application"

    settings = "os", "compiler", "build_type", "arch"
    options = {"qt_dir": [None, "ANY"]}
    default_options = {"qt_dir": None}

    exports_sources = (
        "CMakeLists.txt",
        "*.h",
        "*.cpp",
        "*.ui",
    )

    def layout(self):
        # build/<BuildType>/... on single-config generators, build/ on Visual Studio
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)

        # Conan sets the MSVC runtime only for the build_type it was invoked with
        # (e.g. "$<$<CONFIG:Release>:MultiThreadedDLL>"). In a Visual Studio
        # solution the other configurations then get *no* runtime flag -> /MT,
        # while Qt's DLLs use /MD(d). Mixing them corrupts std::string & co.
        # Drop Conan's block so CMake's default applies to every configuration:
        #   MultiThreaded$<$<CONFIG:Debug>:Debug>DLL   (= /MDd for Debug, /MD otherwise)
        # which is exactly how the Qt kits are built. Safe here: no Conan deps.
        tc.blocks.remove("vs_runtime")

        qt_dir = self._find_qt()
        if qt_dir:
            tc.cache_variables["CMAKE_PREFIX_PATH"] = qt_dir.as_posix()

        tc.generate()
        # No CMakeDeps: there are no Conan requirements to generate find-modules for.

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        self._deploy_qt_runtime()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    # ------------------------------------------------------------ Qt discovery

    @staticmethod
    def _is_qt6_prefix(path):
        return path is not None and (Path(path) / "lib" / "cmake" / "Qt6" / "Qt6Config.cmake").is_file()

    def _find_qt(self):
        candidates = [
            ("option qt_dir", lambda: self.options.qt_dir and str(self.options.qt_dir)),
            ("environment variable QT_DIR", lambda: os.environ.get("QT_DIR")),
            ("Qt tool on PATH", self._qt_from_path_tools),
            ("Qt installer folder", self._qt_from_install_dirs),
        ]
        for source, lookup in candidates:
            found = lookup()
            if not found:
                continue
            found = Path(found)
            if self._is_qt6_prefix(found):
                self.output.info(f"Using Qt from {found.as_posix()} ({source})")
                return found
            # An explicit setting that is wrong should fail loudly, not be skipped.
            if source.startswith(("option", "environment")):
                raise ConanException(
                    f"{source} points to '{found}', but there is no "
                    f"lib/cmake/Qt6/Qt6Config.cmake below it. It must be a Qt kit folder "
                    f"such as C:/Qt/6.8.0/msvc2022_64."
                )

        if self.settings.os == "Windows":
            raise ConanException(
                "Could not find a Qt 6 kit matching this profile "
                f"(compiler={self.settings.compiler}, arch={self.settings.arch}).\n"
                f"Searched: {', '.join(r.as_posix() for r in self._install_roots())} and PATH.\n"
                "Install a matching kit with the Qt Maintenance Tool, or pass "
                '-o "&:qt_dir=<kit folder>".'
            )
        # Elsewhere, distro packages live in default CMake locations: let CMake search.
        self.output.info("No Qt kit detected; relying on CMake's default search paths")
        return None

    def _qt_from_path_tools(self):
        for tool, args in (
            ("qtpaths6", ["--query", "QT_INSTALL_PREFIX"]),
            ("qtpaths",  ["--query", "QT_INSTALL_PREFIX"]),
            ("qmake6",   ["-query", "QT_INSTALL_PREFIX"]),
            ("qmake",    ["-query", "QT_INSTALL_PREFIX"]),
        ):
            exe = shutil.which(tool)
            if not exe:
                continue
            try:
                out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                continue
            prefix = out.stdout.strip()
            # qmake on PATH may well be Qt 5 or a mismatching kit; only accept a Qt 6 prefix
            # that also fits the compiler/arch of the profile.
            if self._is_qt6_prefix(prefix) and self._kit_matches(Path(prefix).name):
                return prefix
        return None

    def _install_roots(self):
        roots = []
        if os.environ.get("QT_ROOT"):
            roots.append(Path(os.environ["QT_ROOT"]))
        if self.settings.os == "Windows":
            roots.append(Path("C:/Qt"))
        roots.append(Path.home() / "Qt")
        return roots

    def _qt_from_install_dirs(self):
        best = None   # ((version tuple), kit preference, path)
        for root in self._install_roots():
            if not root.is_dir():
                continue
            for version_dir in root.iterdir():
                m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version_dir.name)
                if not m or m.group(1) != "6" or not version_dir.is_dir():
                    continue
                version = tuple(int(x) for x in m.groups())
                for kit in version_dir.iterdir():
                    if not (self._kit_matches(kit.name) and self._is_qt6_prefix(kit)):
                        continue
                    key = (version, self._kit_preference(kit.name), kit)
                    if best is None or key[:2] > best[:2]:
                        best = key
        return best[2] if best else None

    def _arch_suffix(self):
        return {"x86_64": "_64", "armv8": "_arm64", "x86": ""}.get(str(self.settings.arch))

    def _kit_matches(self, kit_name):
        """Does an installer kit folder name fit the profile's compiler and arch?"""
        suffix = self._arch_suffix()
        if suffix is None:
            return False
        compiler = str(self.settings.compiler)
        if self.settings.os == "Windows":
            if compiler == "msvc":
                return re.fullmatch(rf"msvc\d{{4}}{suffix}", kit_name) is not None
            if compiler == "gcc":
                return kit_name == f"mingw{suffix}"
            if compiler == "clang":
                return kit_name in (f"llvm-mingw{suffix}", f"mingw{suffix}")
            return False
        if self.settings.os == "Linux":
            return kit_name in (f"gcc{suffix}", f"linux_gcc{suffix}")
        if self.settings.os == "Macos":
            return kit_name == "macos"
        return False

    @staticmethod
    def _kit_preference(kit_name):
        """Among matching kits of one Qt version, prefer the newest MSVC year."""
        m = re.match(r"msvc(\d{4})", kit_name)
        return int(m.group(1)) if m else 0

    # ------------------------------------------------------- Windows runtime

    def _deploy_qt_runtime(self):
        """Copy the Qt DLLs and plugins next to the .exe so it runs by double-click."""
        if self.settings.os != "Windows":
            return
        qt_dir = self._find_qt()
        windeployqt = qt_dir / "bin" / "windeployqt.exe" if qt_dir else None
        if not windeployqt or not windeployqt.is_file():
            self.output.warning("windeployqt not found; Qt DLLs were not copied next to the .exe")
            return

        build = Path(self.build_folder)
        for exe in (build / str(self.settings.build_type) / "SignChecker.exe",  # Visual Studio
                    build / "SignChecker.exe"):                                 # Ninja / Makefiles
            if exe.is_file():
                mode = "--debug" if self.settings.build_type == "Debug" else "--release"
                self.run(f'"{windeployqt}" {mode} --no-translations "{exe}"')
                return
        self.output.warning("Built SignChecker.exe not found; skipped windeployqt")
