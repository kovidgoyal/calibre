#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from code import InteractiveInterpreter

from PyQt4.Qt import QObject, pyqtSignal

from calibre import isbytestring
from calibre.constants import preferred_encoding

class Interpreter(QObject, InteractiveInterpreter):

    # show_error(is_syntax_error, traceback)
    show_error = pyqtSignal(object, object)

    def __init__(self, local={}, parent=None):
        QObject.__init__(self, parent)
        if '__name__' not in local:
            local['__name__'] = '__console__'
        if '__doc__' not in local:
            local['__doc__'] = None
        InteractiveInterpreter.__init__(self, locals=local)

    def showtraceback(self, *args, **kwargs):
        self.is_syntax_error = False
        InteractiveInterpreter.showtraceback(self, *args, **kwargs)

    def showsyntaxerror(self, *args, **kwargs):
        self.is_syntax_error = True
        InteractiveInterpreter.showsyntaxerror(self, *args, **kwargs)

    def write(self, tb):
        self.show_error.emit(self.is_syntax_error, tb)

class DummyFile(QObject):

    # write_output(unicode_object)
    write_output = pyqtSignal(object)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.closed = False
        self.name = 'console'
        self.softspace = 0

    def flush(self):
        pass

    def close(self):
        pass

    def write(self, raw):
        #import sys, traceback
        #print >> sys.__stdout__, 'file,write stack:\n', ''.join(traceback.format_stack())
        if isbytestring(raw):
            try:
                raw = raw.decode(preferred_encoding, 'replace')
            except:
                raw = repr(raw)
                if isbytestring(raw):
                    raw = raw.decode(preferred_encoding, 'replace')
        self.write_output.emit(raw)

