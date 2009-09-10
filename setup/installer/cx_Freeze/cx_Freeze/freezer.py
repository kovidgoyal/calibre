"""
Base class for freezing scripts into executables.
"""

import datetime
import distutils.sysconfig
import imp
import marshal
import os
import shutil
import socket
import stat
import struct
import sys
import time
import zipfile

import cx_Freeze
import cx_Freeze.util

__all__ = [ "ConfigError", "ConstantsModule", "Executable", "Freezer" ]

if sys.platform == "win32":
    pythonDll = "python%s%s.dll" % sys.version_info[:2]
    GLOBAL_BIN_PATH_EXCLUDES = [cx_Freeze.util.GetSystemDir()]
    GLOBAL_BIN_INCLUDES = [
            pythonDll,
            "gdiplus.dll",
            "mfc71.dll",
            "msvcp71.dll",
            "msvcr71.dll"
    ]
    GLOBAL_BIN_EXCLUDES = [
            "comctl32.dll",
            "oci.dll",
            "cx_Logging.pyd"
    ]
else:
    extension = distutils.sysconfig.get_config_var("SO")
    pythonSharedLib = "libpython%s.%s%s" % \
            (sys.version_info[:2] + (extension,))
    GLOBAL_BIN_INCLUDES = [pythonSharedLib]
    GLOBAL_BIN_EXCLUDES = [
            "libclntsh.so",
            "libwtc9.so"
    ]
    GLOBAL_BIN_PATH_EXCLUDES = ["/lib", "/lib32", "/lib64", "/usr/lib",
            "/usr/lib32", "/usr/lib64"]


# NOTE: the try: except: block in this code is not necessary under Python 2.4
# and higher and can be removed once support for Python 2.3 is no longer needed
EXTENSION_LOADER_SOURCE = \
"""
import imp, os, sys

found = False
for p in sys.path:
    if not os.path.isdir(p):
        continue
    f = os.path.join(p, "%s")
    if not os.path.exists(f):
        continue
    try:
        m = imp.load_dynamic(__name__, f)
    except ImportError:
        del sys.modules[__name__]
        raise
    sys.modules[__name__] = m
    found = True
    break
if not found:
    del sys.modules[__name__]
    raise ImportError, "No module named %%s" %% __name__
"""


class Freezer(object):

    def __init__(self, executables, constantsModules = [], includes = [],
            excludes = [], packages = [], replacePaths = [], compress = None,
            optimizeFlag = 0, copyDependentFiles = None, initScript = None,
            base = None, path = None, createLibraryZip = None,
            appendScriptToExe = None, appendScriptToLibrary = None,
            targetDir = None, binIncludes = [], binExcludes = [],
            binPathIncludes = [], binPathExcludes = [], icon = None,
            includeFiles = []):
        self.executables = executables
        self.constantsModules = constantsModules
        self.includes = includes
        self.excludes = excludes
        self.packages = packages
        self.replacePaths = replacePaths
        self.compress = compress
        self.optimizeFlag = optimizeFlag
        self.copyDependentFiles = copyDependentFiles
        self.initScript = initScript
        self.base = base
        self.path = path
        self.createLibraryZip = createLibraryZip
        self.appendScriptToExe = appendScriptToExe
        self.appendScriptToLibrary = appendScriptToLibrary
        self.targetDir = targetDir
        self.binIncludes = [os.path.normcase(n) \
                for n in GLOBAL_BIN_INCLUDES + binIncludes]
        self.binExcludes = [os.path.normcase(n) \
                for n in GLOBAL_BIN_EXCLUDES + binExcludes]
        self.binPathIncludes = [os.path.normcase(n) for n in binPathIncludes]
        self.binPathExcludes = [os.path.normcase(n) \
                for n in GLOBAL_BIN_PATH_EXCLUDES + binPathExcludes]
        self.icon = icon
        self.includeFiles = includeFiles
        self._VerifyConfiguration()

    def _CopyFile(self, source, target, copyDependentFiles,
            includeMode = False):
        normalizedSource = os.path.normcase(os.path.normpath(source))
        normalizedTarget = os.path.normcase(os.path.normpath(target))
        if normalizedTarget in self.filesCopied:
            return
        if normalizedSource == normalizedTarget:
            return
        self._RemoveFile(target)
        targetDir = os.path.dirname(target)
        self._CreateDirectory(targetDir)
        print "copying", source, "->", target
        shutil.copyfile(source, target)
        if includeMode:
            shutil.copymode(source, target)
        self.filesCopied[normalizedTarget] = None
        if copyDependentFiles:
            for source in self._GetDependentFiles(source):
                target = os.path.join(targetDir, os.path.basename(source))
                self._CopyFile(source, target, copyDependentFiles)

    def _CreateDirectory(self, path):
        if not os.path.isdir(path):
            print "creating directory", path
            os.makedirs(path)

    def _FreezeExecutable(self, exe):
        if self.createLibraryZip:
            finder = self.finder
        else:
            finder = self._GetModuleFinder(exe)
        if exe.script is None:
            scriptModule = None
        else:
            scriptModule = finder.IncludeFile(exe.script, exe.moduleName)
        self._CopyFile(exe.base, exe.targetName, exe.copyDependentFiles,
                includeMode = True)
        if exe.icon is not None:
            if sys.platform == "win32":
                cx_Freeze.util.AddIcon(exe.targetName, exe.icon)
            else:
                targetName = os.path.join(os.path.dirname(exe.targetName),
                        os.path.basename(exe.icon))
                self._CopyFile(exe.icon, targetName,
                        copyDependentFiles = False)
        if not os.access(exe.targetName, os.W_OK):
            mode = os.stat(exe.targetName).st_mode
            os.chmod(exe.targetName, mode | stat.S_IWUSR)
        if not exe.appendScriptToLibrary:
            if exe.appendScriptToExe:
                fileName = exe.targetName
            else:
                baseFileName, ext = os.path.splitext(exe.targetName)
                fileName = baseFileName + ".zip"
                self._RemoveFile(fileName)
            if not self.createLibraryZip and exe.copyDependentFiles:
                scriptModule = None
            self._WriteModules(fileName, exe.initScript, finder, exe.compress,
                    exe.copyDependentFiles, scriptModule)

    def _GetBaseFileName(self, argsSource = None):
        if argsSource is None:
            argsSource = self
        name = argsSource.base
        if name is None:
            if argsSource.copyDependentFiles:
                name = "Console"
            else:
                name = "ConsoleKeepPath"
        argsSource.base = self._GetFileName("bases", name)
        if argsSource.base is None:
            raise ConfigError("no base named %s", name)

    def _GetDependentFiles(self, path):
        dependentFiles = self.dependentFiles.get(path)
        if dependentFiles is None:
            if sys.platform == "win32":
                origPath = os.environ["PATH"]
                os.environ["PATH"] = origPath + os.pathsep + \
                        os.pathsep.join(sys.path)
                dependentFiles = cx_Freeze.util.GetDependentFiles(path)
                os.environ["PATH"] = origPath
            else:
                dependentFiles = []
                for line in os.popen('ldd "%s"' % path):
                    parts = line.strip().split(" => ")
                    if len(parts) != 2:
                        continue
                    dependentFile = parts[1]
                    if dependentFile == "not found":
                        print "WARNING: cannot find", parts[0]
                        continue
                    pos = dependentFile.find(" (")
                    if pos >= 0:
                        dependentFile = dependentFile[:pos].strip()
                    if dependentFile:
                        dependentFiles.append(dependentFile)
            dependentFiles = self.dependentFiles[path] = \
                    [f for f in dependentFiles if self._ShouldCopyFile(f)]
        return dependentFiles

    def _GetFileName(self, dir, name):
        if os.path.isabs(name):
            return name
        name = os.path.normcase(name)
        fullDir = os.path.join(os.path.dirname(cx_Freeze.__file__), dir)
        if os.path.isdir(fullDir):
            for fileName in os.listdir(fullDir):
                if name == os.path.splitext(os.path.normcase(fileName))[0]:
                    return os.path.join(fullDir, fileName)

    def _GetInitScriptFileName(self, argsSource = None):
        if argsSource is None:
            argsSource = self
        name = argsSource.initScript
        if name is None:
            if argsSource.copyDependentFiles:
                name = "Console"
            else:
                name = "ConsoleKeepPath"
        argsSource.initScript = self._GetFileName("initscripts", name)
        if argsSource.initScript is None:
            raise ConfigError("no initscript named %s", name)

    def _GetModuleFinder(self, argsSource = None):
        if argsSource is None:
            argsSource = self
        finder = cx_Freeze.ModuleFinder(self.includeFiles, argsSource.excludes,
                argsSource.path, argsSource.replacePaths)
        if argsSource.copyDependentFiles:
            finder.IncludeModule("imp")
            finder.IncludeModule("os")
            finder.IncludeModule("sys")
            if argsSource.compress:
                finder.IncludeModule("zlib")
        for name in argsSource.includes:
            finder.IncludeModule(name)
        for name in argsSource.packages:
            finder.IncludePackage(name)
        return finder

    def _PrintReport(self, fileName, modules):
        print "writing zip file", fileName
        print
        print "  %-25s %s" % ("Name", "File")
        print "  %-25s %s" % ("----", "----")
        for module in modules:
            if module.path:
                print "P",
            else:
                print "m",
            print "%-25s" % module.name, module.file or ""
        print

    def _RemoveFile(self, path):
        if os.path.exists(path):
            os.chmod(path, 0777)
            os.remove(path)

    def _ShouldCopyFile(self, path):
        dir, name = os.path.split(os.path.normcase(path))
        parts = name.split(".")
        tweaked = False
        while True:
            if not parts[-1].isdigit():
                break
            parts.pop(-1)
            tweaked = True
        if tweaked:
            name = ".".join(parts)
        if name in self.binIncludes:
            return True
        if name in self.binExcludes:
            return False
        for path in self.binPathIncludes:
            if dir.startswith(path):
                return True
        for path in self.binPathExcludes:
            if dir.startswith(path):
                return False
        return True

    def _VerifyCanAppendToLibrary(self):
        if not self.createLibraryZip:
            raise ConfigError("script cannot be appended to library zip if "
                    "one is not being created")

    def _VerifyConfiguration(self):
        if self.compress is None:
            self.compress = True
        if self.copyDependentFiles is None:
            self.copyDependentFiles = True
        if self.createLibraryZip is None:
            self.createLibraryZip = True
        if self.appendScriptToExe is None:
            self.appendScriptToExe = False
        if self.appendScriptToLibrary is None:
            self.appendScriptToLibrary = \
                    self.createLibraryZip and not self.appendScriptToExe
        if self.targetDir is None:
            self.targetDir = os.path.abspath("dist")
        self._GetInitScriptFileName()
        self._GetBaseFileName()
        if self.path is None:
            self.path = sys.path
        if self.appendScriptToLibrary:
            self._VerifyCanAppendToLibrary()
        for sourceFileName, targetFileName in self.includeFiles:
            if not os.path.exists(sourceFileName):
                raise ConfigError("cannot find file/directory named %s",
                        sourceFileName)
            if os.path.isabs(targetFileName):
                raise ConfigError("target file/directory cannot be absolute")
        for executable in self.executables:
            executable._VerifyConfiguration(self)

    def _WriteModules(self, fileName, initScript, finder, compress,
            copyDependentFiles, scriptModule = None):
        initModule = finder.IncludeFile(initScript, "cx_Freeze__init__")
        if scriptModule is None:
            for module in self.constantsModules:
                module.Create(finder)
            modules = [m for m in finder.modules \
                    if m.name not in self.excludeModules]
        else:
            modules = [initModule, scriptModule]
            self.excludeModules[initModule.name] = None
            self.excludeModules[scriptModule.name] = None
        itemsToSort = [(m.name, m) for m in modules]
        itemsToSort.sort()
        modules = [m for n, m in itemsToSort]
        self._PrintReport(fileName, modules)
        if scriptModule is None:
            finder.ReportMissingModules()
        targetDir = os.path.dirname(fileName)
        self._CreateDirectory(targetDir)
        filesToCopy = []
        if os.path.exists(fileName):
            mode = "a"
        else:
            mode = "w"
        outFile = zipfile.PyZipFile(fileName, mode, zipfile.ZIP_DEFLATED)
        for module in modules:
            if module.code is None and module.file is not None:
                fileName = os.path.basename(module.file)
                baseFileName, ext = os.path.splitext(fileName)
                if baseFileName != module.name and module.name != "zlib":
                    if "." in module.name:
                        fileName = module.name + ext
                    generatedFileName = "ExtensionLoader_%s.py" % \
                            module.name.replace(".", "_")
                    module.code = compile(EXTENSION_LOADER_SOURCE % fileName,
                            generatedFileName, "exec")
                target = os.path.join(targetDir, fileName)
                filesToCopy.append((module, target))
            if module.code is None:
                continue
            fileName = "/".join(module.name.split("."))
            if module.path:
                fileName += "/__init__"
            if module.file is not None and os.path.exists(module.file):
                mtime = os.stat(module.file).st_mtime
            else:
                mtime = time.time()
            zipTime = time.localtime(mtime)[:6]
            data = imp.get_magic() + struct.pack("<i", mtime) + \
                    marshal.dumps(module.code)
            zinfo = zipfile.ZipInfo(fileName + ".pyc", zipTime)
            if compress:
                zinfo.compress_type = zipfile.ZIP_DEFLATED
            outFile.writestr(zinfo, data)
        origPath = os.environ["PATH"]
        for module, target in filesToCopy:
            try:
                if module.parent is not None:
                    path = os.pathsep.join([origPath] + module.parent.path)
                    os.environ["PATH"] = path
                self._CopyFile(module.file, target, copyDependentFiles)
            finally:
                os.environ["PATH"] = origPath

    def Freeze(self):
        self.finder = None
        self.excludeModules = {}
        self.dependentFiles = {}
        self.filesCopied = {}
        cx_Freeze.util.SetOptimizeFlag(self.optimizeFlag)
        if self.createLibraryZip:
            self.finder = self._GetModuleFinder()
        for executable in self.executables:
            self._FreezeExecutable(executable)
        if self.createLibraryZip:
            fileName = os.path.join(self.targetDir, "library.zip")
            self._RemoveFile(fileName)
            self._WriteModules(fileName, self.initScript, self.finder,
                    self.compress, self.copyDependentFiles)
        for sourceFileName, targetFileName in self.includeFiles:
            fullName = os.path.join(self.targetDir, targetFileName)
            if os.path.isdir(sourceFileName):
                for path, dirNames, fileNames in os.walk(sourceFileName):
                    shortPath = path[len(sourceFileName) + 1:]
                    if ".svn" in dirNames:
                        dirNames.remove(".svn")
                    if "CVS" in dirNames:
                        dirNames.remove("CVS")
                    for fileName in fileNames:
                        fullSourceName = os.path.join(path, fileName)
                        fullTargetName = os.path.join(self.targetDir,
                                targetFileName, shortPath, fileName)
                        self._CopyFile(fullSourceName, fullTargetName,
                                copyDependentFiles = False)
            else:
                self._CopyFile(sourceFileName, fullName,
                        copyDependentFiles = False)


class ConfigError(Exception):

    def __init__(self, format, *args):
        self.what = format % args

    def __str__(self):
        return self.what


class Executable(object):

    def __init__(self, script, initScript = None, base = None, path = None,
            targetDir = None, targetName = None, includes = None,
            excludes = None, packages = None, replacePaths = None,
            compress = None, copyDependentFiles = None,
            appendScriptToExe = None, appendScriptToLibrary = None,
            icon = None):
        self.script = script
        self.initScript = initScript
        self.base = base
        self.path = path
        self.targetDir = targetDir
        self.targetName = targetName
        self.includes = includes
        self.excludes = excludes
        self.packages = packages
        self.replacePaths = replacePaths
        self.compress = compress
        self.copyDependentFiles = copyDependentFiles
        self.appendScriptToExe = appendScriptToExe
        self.appendScriptToLibrary = appendScriptToLibrary
        self.icon = icon

    def __repr__(self):
        return "<Executable script=%s>" % self.script

    def _VerifyConfiguration(self, freezer):
        if self.path is None:
            self.path = freezer.path
        if self.targetDir is None:
            self.targetDir = freezer.targetDir
        if self.includes is None:
            self.includes = freezer.includes
        if self.excludes is None:
            self.excludes = freezer.excludes
        if self.packages is None:
            self.packages = freezer.packages
        if self.replacePaths is None:
            self.replacePaths = freezer.replacePaths
        if self.compress is None:
            self.compress = freezer.compress
        if self.copyDependentFiles is None:
            self.copyDependentFiles = freezer.copyDependentFiles
        if self.appendScriptToExe is None:
            self.appendScriptToExe = freezer.appendScriptToExe
        if self.appendScriptToLibrary is None:
            self.appendScriptToLibrary = freezer.appendScriptToLibrary
        if self.initScript is None:
            self.initScript = freezer.initScript
        else:
            freezer._GetInitScriptFileName(self)
        if self.base is None:
            self.base = freezer.base
        else:
            freezer._GetBaseFileName(self)
        if self.appendScriptToLibrary:
            freezer._VerifyCanAppendToLibrary()
        if self.icon is None:
            self.icon = freezer.icon
        if self.script is not None:
            name, ext = os.path.splitext(os.path.basename(self.script))
            if self.appendScriptToLibrary:
                self.moduleName = "%s__main__" % os.path.normcase(name)
            else:
                self.moduleName = "__main__"
        if self.targetName is None:
            baseName, ext = os.path.splitext(self.base)
            self.targetName = name + ext
        self.targetName = os.path.join(self.targetDir, self.targetName)


class ConstantsModule(object):

    def __init__(self, releaseString = None, copyright = None,
            moduleName = "BUILD_CONSTANTS", timeFormat = "%B %d, %Y %H:%M:%S"):
        self.moduleName = moduleName
        self.timeFormat = timeFormat
        self.values = {}
        self.values["BUILD_RELEASE_STRING"] = releaseString
        self.values["BUILD_COPYRIGHT"] = copyright

    def Create(self, finder):
        """Create the module which consists of declaration statements for each
           of the values."""
        today = datetime.datetime.today()
        sourceTimestamp = 0
        for module in finder.modules:
            if module.file is None:
                continue
            if module.inZipFile:
                continue
            if not os.path.exists(module.file):
                raise ConfigError("no file named %s", module.file)
            timestamp = os.stat(module.file).st_mtime
            sourceTimestamp = max(sourceTimestamp, timestamp)
        sourceTimestamp = datetime.datetime.fromtimestamp(sourceTimestamp)
        self.values["BUILD_TIMESTAMP"] = today.strftime(self.timeFormat)
        self.values["BUILD_HOST"] = socket.gethostname().split(".")[0]
        self.values["SOURCE_TIMESTAMP"] = \
                sourceTimestamp.strftime(self.timeFormat)
        module = finder._AddModule(self.moduleName)
        sourceParts = []
        names = self.values.keys()
        names.sort()
        for name in names:
            value = self.values[name]
            sourceParts.append("%s = %r" % (name, value))
        source = "\n".join(sourceParts)
        module.code = compile(source, "%s.py" % self.moduleName, "exec")

