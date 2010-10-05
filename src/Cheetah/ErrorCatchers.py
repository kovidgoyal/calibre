# $Id: ErrorCatchers.py,v 1.7 2005/01/03 19:59:07 tavis_rudd Exp $
"""ErrorCatcher class for Cheetah Templates

Meta-Data
================================================================================
Author: Tavis Rudd <tavis@damnsimple.com>
Version: $Revision: 1.7 $
Start Date: 2001/08/01
Last Revision Date: $Date: 2005/01/03 19:59:07 $
"""
__author__ = "Tavis Rudd <tavis@damnsimple.com>"
__revision__ = "$Revision: 1.7 $"[11:-2]

import time
from Cheetah.NameMapper import NotFound

class Error(Exception):
    pass

class ErrorCatcher:
    _exceptionsToCatch = (NotFound,)
    
    def __init__(self, templateObj):
        pass
    
    def exceptions(self):
        return self._exceptionsToCatch
    
    def warn(self, exc_val, code, rawCode, lineCol):
        return rawCode
## make an alias
Echo = ErrorCatcher

class BigEcho(ErrorCatcher):
    def warn(self, exc_val, code, rawCode, lineCol):
        return "="*15 + "&lt;" + rawCode + " could not be found&gt;" + "="*15

class KeyError(ErrorCatcher):
    def warn(self, exc_val, code, rawCode, lineCol):
        raise KeyError("no '%s' in this Template Object's Search List" % rawCode) 

class ListErrors(ErrorCatcher):
    """Accumulate a list of errors."""
    _timeFormat = "%c"
    
    def __init__(self, templateObj):
        ErrorCatcher.__init__(self, templateObj)
        self._errors = []

    def warn(self, exc_val, code, rawCode, lineCol):
        dict = locals().copy()
        del dict['self']
        dict['time'] = time.strftime(self._timeFormat,
                                     time.localtime(time.time()))
        self._errors.append(dict)
        return rawCode
    
    def listErrors(self):
        """Return the list of errors."""
        return self._errors


