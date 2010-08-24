"""
Base class for finding modules.
"""

import dis
import imp
import marshal
import new
import opcode
import os
import sys
import zipfile

import cx_Freeze.hooks

BUILD_LIST = opcode.opmap["BUILD_LIST"]
INPLACE_ADD = opcode.opmap["INPLACE_ADD"]
LOAD_CONST = opcode.opmap["LOAD_CONST"]
IMPORT_NAME = opcode.opmap["IMPORT_NAME"]
IMPORT_FROM = opcode.opmap["IMPORT_FROM"]
STORE_NAME = opcode.opmap["STORE_NAME"]
STORE_GLOBAL = opcode.opmap["STORE_GLOBAL"]
STORE_OPS = (STORE_NAME, STORE_GLOBAL)

__all__ = [ "Module", "ModuleFinder" ]

class ModuleFinder(object):

    def __init__(self, includeFiles, excludes, path, replacePaths):
        self.includeFiles = includeFiles
        self.excludes = dict.fromkeys(excludes)
        self.replacePaths = replacePaths
        self.path = path or sys.path
        self.modules = []
        self.aliases = {}
        self._modules = dict.fromkeys(excludes)
        self._builtinModules = dict.fromkeys(sys.builtin_module_names)
        self._badModules = {}
        self._zipFileEntries = {}
        self._zipFiles = {}
        cx_Freeze.hooks.initialize(self)

    def _AddModule(self, name):
        """Add a module to the list of modules but if one is already found,
           then return it instead; this is done so that packages can be
           handled properly."""
        module = self._modules.get(name)
        if module is None:
            module = self._modules[name] = Module(name)
            self.modules.append(module)
            if name in self._badModules:
                del self._badModules[name]
        return module

    def _DetermineParent(self, caller):
        """Determine the parent to use when searching packages."""
        if caller is not None:
            if caller.path is not None:
                return caller
            return self._GetParentByName(caller.name)

    def _EnsureFromList(self, caller, packageModule, fromList,
            deferredImports):
        """Ensure that the from list is satisfied. This is only necessary for
           package modules. If the caller is the package itself, actually
           attempt to import right then since it must be a submodule; otherwise
           defer until after all global names are defined in order to avoid
           spurious complaints about missing modules."""
        if caller is not packageModule:
            deferredImports.append((packageModule, fromList))
        else:
            if fromList == ("*",):
                fromList = packageModule.allNames
            for name in fromList:
                if name in packageModule.globalNames:
                    continue
                subModuleName = "%s.%s" % (packageModule.name, name)
                self._ImportModule(subModuleName, deferredImports, caller)

    def _FindModule(self, name, path):
        try:
            return imp.find_module(name, path)
        except ImportError:
            if not path:
                path = []
            for location in path:
                if name in self._zipFileEntries:
                    break
                if location in self._zipFiles:
                    continue
                if os.path.isdir(location) or not zipfile.is_zipfile(location):
                    self._zipFiles[location] = None
                    continue
                zip = zipfile.ZipFile(location)
                for archiveName in zip.namelist():
                    baseName, ext = os.path.splitext(archiveName)
                    if ext not in ('.pyc', '.pyo'):
                        continue
                    moduleName = ".".join(baseName.split("/"))
                    if moduleName in self._zipFileEntries:
                        continue
                    self._zipFileEntries[moduleName] = (zip, archiveName)
                self._zipFiles[location] = None
            info = self._zipFileEntries.get(name)
            if info is not None:
                zip, archiveName = info
                fp = zip.read(archiveName)
                info = (".pyc", "rb", imp.PY_COMPILED)
                return fp, os.path.join(zip.filename, archiveName), info
            raise

    def _GetParentByName(self, name):
        """Return the parent module given the name of a module."""
        pos = name.rfind(".")
        if pos > 0:
            parentName = name[:pos]
            return self._modules[parentName]

    def _ImportAllSubModules(self, module, deferredImports, recursive = True):
        """Import all sub modules to the given package."""
        suffixes = dict.fromkeys([s[0] for s in imp.get_suffixes()])
        for dir in module.path:
            try:
                fileNames = os.listdir(dir)
            except os.error:
                continue
            for fileName in fileNames:
                name, ext = os.path.splitext(fileName)
                if ext not in suffixes:
                    continue
                if name == "__init__":
                    continue
                subModuleName = "%s.%s" % (module.name, name)
                subModule, returnError = \
                        self._InternalImportModule(subModuleName,
                                deferredImports)
                if returnError and subModule is None:
                    raise ImportError, "No module named %s" % subModuleName
                module.globalNames[name] = None
                if subModule.path and recursive:
                    self._ImportAllSubModules(subModule, deferredImports,
                            recursive)

    def _ImportDeferredImports(self, deferredImports):
        """Import any sub modules that were deferred, if applicable."""
        while deferredImports:
            newDeferredImports = []
            for packageModule, subModuleNames in deferredImports:
                self._EnsureFromList(packageModule, packageModule,
                        subModuleNames, newDeferredImports)
            deferredImports = newDeferredImports

    def _ImportModule(self, name, deferredImports, caller = None,
            relativeImportIndex = 0):
        """Attempt to find the named module and return it or None if no module
           by that name could be found."""

        # absolute import (available in Python 2.5 and up)
        # the name given is the only name that will be searched
        if relativeImportIndex == 0:
            module, returnError = self._InternalImportModule(name,
                    deferredImports)

        # old style relative import (only possibility in Python 2.4 and prior)
        # the name given is tried in all parents until a match is found and if
        # no match is found, the global namespace is searched
        elif relativeImportIndex < 0:
            parent = self._DetermineParent(caller)
            while parent is not None:
                fullName = "%s.%s" % (parent.name, name)
                module, returnError = self._InternalImportModule(fullName,
                        deferredImports)
                if module is not None:
                    parent.globalNames[name] = None
                    return module
                parent = self._GetParentByName(parent.name)
            module, returnError = self._InternalImportModule(name,
                    deferredImports)

        # new style relative import (available in Python 2.5 and up)
        # the index indicates how many levels to traverse and only that level
        # is searched for the named module
        elif relativeImportIndex > 0:
            parent = caller
            if parent.path is not None:
                relativeImportIndex -= 1
            while parent is not None and relativeImportIndex > 0:
                parent = self._GetParentByName(parent.name)
                relativeImportIndex -= 1
            if parent is None:
                module = None
                returnError = True
            elif not name:
                module = parent
            else:
                name = "%s.%s" % (parent.name, name)
                module, returnError = self._InternalImportModule(name,
                        deferredImports)

        # if module not found, track that fact
        if module is None:
            if caller is None:
                raise ImportError, "No module named %s" % name
            self._RunHook("missing", name, caller)
            if returnError and name not in caller.ignoreNames:
                callers = self._badModules.setdefault(name, {})
                callers[caller.name] = None

        return module

    def _InternalImportModule(self, name, deferredImports):
        """Internal method used for importing a module which assumes that the
           name given is an absolute name. None is returned if the module
           cannot be found."""
        try:
            return self._modules[name], False
        except KeyError:
            pass
        if name in self._builtinModules:
            module = self._AddModule(name)
            self._RunHook("load", module.name, module)
            return module, False
        pos = name.rfind(".")
        if pos < 0:
            path = self.path
            searchName = name
            parentModule = None
        else:
            parentName = name[:pos]
            parentModule, returnError = \
                    self._InternalImportModule(parentName, deferredImports)
            if parentModule is None:
                return None, returnError
            path = parentModule.path
            searchName = name[pos + 1:]
        if name in self.aliases:
            actualName = self.aliases[name]
            module, returnError = \
                    self._InternalImportModule(actualName, deferredImports)
            self._modules[name] = module
            return module, returnError
        try:
            fp, path, info = self._FindModule(searchName, path)
        except ImportError:
            self._modules[name] = None
            return None, True
        module = self._LoadModule(name, fp, path, info, deferredImports,
                parentModule)
        return module, False

    def _LoadModule(self, name, fp, path, info, deferredImports,
            parent = None):
        """Load the module, given the information acquired by the finder."""
        suffix, mode, type = info
        if type == imp.PKG_DIRECTORY:
            return self._LoadPackage(name, path, parent, deferredImports)
        module = self._AddModule(name)
        module.file = path
        module.parent = parent
        if type == imp.PY_SOURCE:
            module.code = compile(fp.read() + "\n", path, "exec")
        elif type == imp.PY_COMPILED:
            if isinstance(fp, str):
                magic = fp[:4]
            else:
                magic = fp.read(4)
            if magic != imp.get_magic():
                raise ImportError, "Bad magic number in %s" % path
            if isinstance(fp, str):
                module.code = marshal.loads(fp[8:])
                module.inZipFile = True
            else:
                fp.read(4)
                module.code = marshal.load(fp)
        self._RunHook("load", module.name, module)
        if module.code is not None:
            if self.replacePaths:
                topLevelModule = module
                while topLevelModule.parent is not None:
                    topLevelModule = topLevelModule.parent
                module.code = self._ReplacePathsInCode(topLevelModule,
                        module.code)
            self._ScanCode(module.code, module, deferredImports)
        return module

    def _LoadPackage(self, name, path, parent, deferredImports):
        """Load the package, given its name and path."""
        module = self._AddModule(name)
        module.path = [path]
        fp, path, info = imp.find_module("__init__", module.path)
        self._LoadModule(name, fp, path, info, deferredImports, parent)
        return module

    def _ReplacePathsInCode(self, topLevelModule, co):
        """Replace paths in the code as directed, returning a new code object
           with the modified paths in place."""
        origFileName = newFileName = os.path.normpath(co.co_filename)
        for searchValue, replaceValue in self.replacePaths:
            if searchValue == "*":
                searchValue = os.path.dirname(topLevelModule.file)
                if topLevelModule.path:
                    searchValue = os.path.dirname(searchValue)
                if searchValue:
                    searchValue = searchValue + os.pathsep
            elif not origFileName.startswith(searchValue):
                continue
            newFileName = replaceValue + origFileName[len(searchValue):]
            break
        constants = list(co.co_consts)
        for i, value in enumerate(constants):
            if isinstance(value, type(co)):
                constants[i] = self._ReplacePathsInCode(topLevelModule, value)
        return new.code(co.co_argcount, co.co_nlocals, co.co_stacksize,
                co.co_flags, co.co_code, tuple(constants), co.co_names,
                co.co_varnames, newFileName, co.co_name, co.co_firstlineno,
                co.co_lnotab, co.co_freevars, co.co_cellvars)

    def _RunHook(self, hookName, moduleName, *args):
        """Run hook for the given module if one is present."""
        name = "%s_%s" % (hookName, moduleName.replace(".", "_"))
        method = getattr(cx_Freeze.hooks, name, None)
        if method is not None:
            method(self, *args)

    def _ScanCode(self, co, module, deferredImports):
        """Scan code, looking for imported modules and keeping track of the
           constants that have been created in order to better tell which
           modules are truly missing."""
        opIndex = 0
        arguments = []
        code = co.co_code
        numOps = len(code)
        while opIndex < numOps:
            op = ord(code[opIndex])
            opIndex += 1
            if op >= dis.HAVE_ARGUMENT:
                opArg = ord(code[opIndex]) + ord(code[opIndex + 1]) * 256
                opIndex += 2
            if op == LOAD_CONST:
                arguments.append(co.co_consts[opArg])
            elif op == IMPORT_NAME:
                name = co.co_names[opArg]
                if len(arguments) == 2:
                    relativeImportIndex, fromList = arguments
                else:
                    relativeImportIndex = -1
                    fromList, = arguments
                if name not in module.excludeNames:
                    subModule = self._ImportModule(name, deferredImports,
                            module, relativeImportIndex)
                    if subModule is not None:
                        module.globalNames.update(subModule.globalNames)
                        if fromList and subModule.path is not None:
                            self._EnsureFromList(module, subModule, fromList,
                                    deferredImports)
            elif op == IMPORT_FROM:
                opIndex += 3
            elif op not in (BUILD_LIST, INPLACE_ADD):
                if op in STORE_OPS:
                    name = co.co_names[opArg]
                    if name == "__all__":
                        module.allNames.extend(arguments)
                    module.globalNames[name] = None
                arguments = []
        for constant in co.co_consts:
            if isinstance(constant, type(co)):
                self._ScanCode(constant, module, deferredImports)

    def AddAlias(self, name, aliasFor):
        """Add an alias for a particular module; when an attempt is made to
           import a module using the alias name, import the actual name
           instead."""
        self.aliases[name] = aliasFor

    def ExcludeModule(self, name):
        """Exclude the named module from the resulting frozen executable."""
        self.excludes[name] = None
        self._modules[name] = None

    def IncludeFile(self, path, moduleName = None):
        """Include the named file as a module in the frozen executable."""
        name, ext = os.path.splitext(os.path.basename(path))
        if moduleName is None:
            moduleName = name
        info = (ext, "r", imp.PY_SOURCE)
        deferredImports = []
        module = self._LoadModule(moduleName, file(path, "U"), path, info,
                deferredImports)
        self._ImportDeferredImports(deferredImports)
        return module

    def IncludeFiles(self, sourcePath, targetPath):
        """Include the files in the given directory in the target build."""
        self.includeFiles.append((sourcePath, targetPath))

    def IncludeModule(self, name):
        """Include the named module in the frozen executable."""
        deferredImports = []
        module = self._ImportModule(name, deferredImports)
        self._ImportDeferredImports(deferredImports)
        return module

    def IncludePackage(self, name):
        """Include the named package and any submodules in the frozen
           executable."""
        deferredImports = []
        module = self._ImportModule(name, deferredImports)
        if module.path:
            self._ImportAllSubModules(module, deferredImports)
        self._ImportDeferredImports(deferredImports)
        return module

    def ReportMissingModules(self):
        if self._badModules:
            print "Missing modules:"
            names = self._badModules.keys()
            names.sort()
            for name in names:
                callers = self._badModules[name].keys()
                callers.sort()
                print "?", name, "imported from", ", ".join(callers)
            print


class Module(object):

    def __init__(self, name):
        self.name = name
        self.file = None
        self.path = None
        self.code = None
        self.parent = None
        self.globalNames = {}
        self.excludeNames = {}
        self.ignoreNames = {}
        self.allNames = []
        self.inZipFile = False

    def __repr__(self):
        parts = ["name=%s" % repr(self.name)]
        if self.file is not None:
            parts.append("file=%s" % repr(self.file))
        if self.path is not None:
            parts.append("path=%s" % repr(self.path))
        return "<Module %s>" % ", ".join(parts)

    def AddGlobalName(self, name):
        self.globalNames[name] = None

    def ExcludeName(self, name):
        self.excludeNames[name] = None

    def IgnoreName(self, name):
        self.ignoreNames[name] = None

