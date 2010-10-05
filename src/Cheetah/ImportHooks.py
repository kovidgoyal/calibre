#!/usr/bin/env python

"""
Provides some import hooks to allow Cheetah's .tmpl files to be imported
directly like Python .py modules.

To use these:
  import Cheetah.ImportHooks
  Cheetah.ImportHooks.install()
"""

import sys
import os.path
import types
import __builtin__
import imp
from threading import RLock
import string
import traceback
import types

from Cheetah import ImportManager
from Cheetah.ImportManager import DirOwner
from Cheetah.Compiler import Compiler
from Cheetah.convertTmplPathToModuleName import convertTmplPathToModuleName

_installed = False

##################################################
## HELPER FUNCS

_cacheDir = []
def setCacheDir(cacheDir):
    global _cacheDir
    _cacheDir.append(cacheDir)
    
##################################################
## CLASSES

class CheetahDirOwner(DirOwner):
    _lock = RLock()
    _acquireLock = _lock.acquire
    _releaseLock = _lock.release

    templateFileExtensions = ('.tmpl',)

    def getmod(self, name):
        self._acquireLock()
        try:        
            mod = DirOwner.getmod(self, name)
            if mod:
                return mod

            for ext in self.templateFileExtensions:
                tmplPath =  os.path.join(self.path, name + ext)
                if os.path.exists(tmplPath):
                    try:
                        return self._compile(name, tmplPath)
                    except:
                        # @@TR: log the error
                        exc_txt = traceback.format_exc()
                        exc_txt ='  '+('  \n'.join(exc_txt.splitlines()))
                        raise ImportError(
                            'Error while compiling Cheetah module'
                        ' %(name)s, original traceback follows:\n%(exc_txt)s'%locals())
            ##
            return None

        finally:
            self._releaseLock()          

    def _compile(self, name, tmplPath):
        ## @@ consider adding an ImportError raiser here
        code = str(Compiler(file=tmplPath, moduleName=name,
                            mainClassName=name))
        if _cacheDir:
            __file__ = os.path.join(_cacheDir[0],
                                    convertTmplPathToModuleName(tmplPath)) + '.py'
            try:
                open(__file__, 'w').write(code)
            except OSError:
                ## @@ TR: need to add some error code here
                traceback.print_exc(file=sys.stderr)
                __file__ = tmplPath
        else:
            __file__ = tmplPath
        co = compile(code+'\n', __file__, 'exec')

        mod = types.ModuleType(name)
        mod.__file__ = co.co_filename
        if _cacheDir:
            mod.__orig_file__ = tmplPath # @@TR: this is used in the WebKit
                                         # filemonitoring code
        mod.__co__ = co
        return mod
        

##################################################
## FUNCTIONS

def install(templateFileExtensions=('.tmpl',)):
    """Install the Cheetah Import Hooks"""

    global _installed
    if not _installed:
        CheetahDirOwner.templateFileExtensions = templateFileExtensions
        import __builtin__
        if isinstance(__builtin__.__import__, types.BuiltinFunctionType):
            global __oldimport__
            __oldimport__ = __builtin__.__import__
            ImportManager._globalOwnerTypes.insert(0, CheetahDirOwner)
            #ImportManager._globalOwnerTypes.append(CheetahDirOwner)            
            global _manager
            _manager=ImportManager.ImportManager()
            _manager.setThreaded()
            _manager.install()
        
def uninstall():
    """Uninstall the Cheetah Import Hooks"""    
    global _installed
    if not _installed:
        import __builtin__
        if isinstance(__builtin__.__import__, types.MethodType):
            __builtin__.__import__ = __oldimport__
            global _manager
            del _manager

if __name__ == '__main__':
    install()
