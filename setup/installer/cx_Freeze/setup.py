"""
Distutils script for cx_Freeze.
"""

import distutils.command.bdist_rpm
import distutils.command.build_ext
import distutils.command.build_scripts
import distutils.command.install
import distutils.command.install_data
import distutils.sysconfig
import os
import sys

from distutils.core import setup
from distutils.extension import Extension

class bdist_rpm(distutils.command.bdist_rpm.bdist_rpm):

    # rpm automatically byte compiles all Python files in a package but we
    # don't want that to happen for initscripts and samples so we tell it to
    # ignore those files
    def _make_spec_file(self):
        specFile = distutils.command.bdist_rpm.bdist_rpm._make_spec_file(self)
        specFile.insert(0, "%define _unpackaged_files_terminate_build 0%{nil}")
        return specFile

    def run(self):
        distutils.command.bdist_rpm.bdist_rpm.run(self)
        specFile = os.path.join(self.rpm_base, "SPECS",
                "%s.spec" % self.distribution.get_name())
        queryFormat = "%{name}-%{version}-%{release}.%{arch}.rpm"
        command = "rpm -q --qf '%s' --specfile %s" % (queryFormat, specFile)
        origFileName = os.popen(command).read()
        parts = origFileName.split("-")
        parts.insert(2, "py%s%s" % sys.version_info[:2])
        newFileName = "-".join(parts)
        self.move_file(os.path.join("dist", origFileName),
                os.path.join("dist", newFileName))


class build_ext(distutils.command.build_ext.build_ext):

    def build_extension(self, ext):
        if ext.name.find("bases") < 0:
            distutils.command.build_ext.build_ext.build_extension(self, ext)
            return
        os.environ["LD_RUN_PATH"] = "${ORIGIN}:${ORIGIN}/../lib"
        objects = self.compiler.compile(ext.sources,
                output_dir = self.build_temp,
                include_dirs = ext.include_dirs,
                debug = self.debug,
                depends = ext.depends)
        fileName = os.path.splitext(self.get_ext_filename(ext.name))[0]
        fullName = os.path.join(self.build_lib, fileName)
        libraryDirs = ext.library_dirs or []
        libraries = self.get_libraries(ext)
        extraArgs = ext.extra_link_args or []
        if sys.platform != "win32":
            vars = distutils.sysconfig.get_config_vars()
            libraryDirs.append(vars["LIBPL"])
            libraries.append("python%s.%s" % sys.version_info[:2])
            if vars["LINKFORSHARED"]:
                extraArgs.extend(vars["LINKFORSHARED"].split())
            if vars["LIBS"]:
                extraArgs.extend(vars["LIBS"].split())
            if vars["LIBM"]:
                extraArgs.append(vars["LIBM"])
            if vars["BASEMODLIBS"]:
                extraArgs.extend(vars["BASEMODLIBS"].split())
            if vars["LOCALMODLIBS"]:
                extraArgs.extend(vars["LOCALMODLIBS"].split())
            extraArgs.append("-s")
        self.compiler.link_executable(objects, fullName,
                libraries = libraries,
                library_dirs = libraryDirs,
                runtime_library_dirs = ext.runtime_library_dirs,
                extra_postargs = extraArgs,
                debug = self.debug)

    def get_ext_filename(self, name):
        fileName = distutils.command.build_ext.build_ext.get_ext_filename(self,
                name)
        if name.find("bases") < 0:
            return fileName
        ext = self.compiler.exe_extension or ""
        return os.path.splitext(fileName)[0] + ext


class build_scripts(distutils.command.build_scripts.build_scripts):

    def copy_scripts(self):
        distutils.command.build_scripts.build_scripts.copy_scripts(self)
        if sys.platform == "win32":
            for script in self.scripts:
                batFileName = os.path.join(self.build_dir, script + ".bat")
                fullScriptName = r"%s\Scripts\%s" % \
                        (os.path.dirname(sys.executable), script)
                command = "%s %s %%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9" % \
                        (sys.executable, fullScriptName)
                file(batFileName, "w").write("@echo off\n\n%s" % command)


class install(distutils.command.install.install):

    def get_sub_commands(self):
        subCommands = distutils.command.install.install.get_sub_commands(self)
        subCommands.append("install_packagedata")
        return subCommands


class install_packagedata(distutils.command.install_data.install_data):

    def run(self):
        installCommand = self.get_finalized_command("install")
        installDir = getattr(installCommand, "install_lib")
        sourceDirs = ["samples", "initscripts"]
        while sourceDirs:
            sourceDir = sourceDirs.pop(0)
            targetDir = os.path.join(installDir, "cx_Freeze", sourceDir)
            self.mkpath(targetDir)
            for name in os.listdir(sourceDir):
                if name == "build" or name.startswith("."):
                    continue
                fullSourceName = os.path.join(sourceDir, name)
                if os.path.isdir(fullSourceName):
                    sourceDirs.append(fullSourceName)
                else:
                    fullTargetName = os.path.join(targetDir, name)
                    self.copy_file(fullSourceName, fullTargetName)
                    self.outfiles.append(fullTargetName)


commandClasses = dict(
        build_ext = build_ext,
        build_scripts = build_scripts,
        bdist_rpm = bdist_rpm,
        install = install,
        install_packagedata = install_packagedata)

if sys.platform == "win32":
    libraries = ["imagehlp"]
else:
    libraries = []
utilModule = Extension("cx_Freeze.util", ["source/util.c"],
        libraries = libraries)
depends = ["source/bases/Common.c"]
if sys.platform == "win32":
    if sys.version_info[:2] >= (2, 6):
        extraSources = ["source/bases/manifest.rc"]
    else:
        extraSources = ["source/bases/dummy.rc"]
else:
    extraSources = []
console = Extension("cx_Freeze.bases.Console",
        ["source/bases/Console.c"] + extraSources, depends = depends)
consoleKeepPath = Extension("cx_Freeze.bases.ConsoleKeepPath",
        ["source/bases/ConsoleKeepPath.c"] + extraSources, depends = depends)
extensions = [utilModule, console, consoleKeepPath]
if sys.platform == "win32":
    gui = Extension("cx_Freeze.bases.Win32GUI",
            ["source/bases/Win32GUI.c"] + extraSources,
            depends = depends, extra_link_args = ["-mwindows"])
    extensions.append(gui)

docFiles = "LICENSE.txt README.txt HISTORY.txt doc/cx_Freeze.html"

classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Python Software Foundation License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: C",
        "Programming Language :: Python",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Software Distribution",
        "Topic :: Utilities"
]

setup(name = "cx_Freeze",
        description = "create standalone executables from Python scripts",
        long_description = "create standalone executables from Python scripts",
        version = "4.0.1",
        cmdclass = commandClasses,
        options = dict(bdist_rpm = dict(doc_files = docFiles),
                install = dict(optimize = 1)),
        ext_modules = extensions,
        packages = ['cx_Freeze'],
        maintainer="Anthony Tuininga",
        maintainer_email="anthony.tuininga@gmail.com",
        url = "http://cx-freeze.sourceforge.net",
        scripts = ["cxfreeze"],
        classifiers = classifiers,
        keywords = "freeze",
        license = "Python Software Foundation License")

