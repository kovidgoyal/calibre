##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Thin ctypes based wrapper around libtidy. Example usage:
>>> from libtidy import parseString
>>> print parseString('<h1>fowehfow</h2>', \
                       output_xhtml=1, add_xml_decl=1, indent=1, tidy_mark=0)
<?xml version="1.0" encoding="us-ascii"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title></title>
  </head>
  <body>
    <h1>
      fowehfow
    </h1>
  </body>
</html>
"""

import ctypes
from cStringIO import StringIO
import weakref

class TidyLibError(Exception):
    def __init__(self, arg):
        self.arg=arg

class InvalidOptionError(TidyLibError):
    def __str__(self):
        return "%s was not a valid Tidy option." % (self.arg)
    __repr__=__str__

class OptionArgError(TidyLibError):
    def __init__(self, arg):
        self.arg=arg
    def __str__(self):
        return self.arg

# search the path for libtidy using the known names; 
thelib=None
for libname in ('cygtidy-0-99-0', 'libtidy', 'libtidy.so', 'tidylib'):
    try:
        thelib = getattr(ctypes.cdll, libname)
        break
    except OSError:
        pass
if not thelib:
    raise OSError("Couldn't find libtidy, please make sure it is installed.")

class Loader:
    """
    I am a trivial wrapper that eliminates the need for tidy.tidyFoo, 
    so you can just access tidy.Foo
    """
    def __init__(self):
        self.lib = thelib
    def __getattr__(self, name):
        try:
            return getattr(self.lib, "tidy%s" % name)
        # current ctypes uses ValueError, future will use AttributeError
        except (ValueError, AttributeError):
            return getattr(self.lib, name)

_tidy=Loader()

# define a callback to pass to Tidylib
def _putByte(handle, c):
    """Lookup sink by handle and call its putByte method"""
    sinkfactory[handle].putByte(c)
    return 0

PUTBYTEFUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_char)    
putByte = PUTBYTEFUNC(_putByte)

class _OutputSink(ctypes.Structure):
    _fields_ = [("sinkData", ctypes.c_int),
              ("putByte", PUTBYTEFUNC),
              ]

class _Sink:
    def __init__(self):
        self._data = StringIO()
        self.struct = _OutputSink()
        self.struct.putByte = putByte
        
    def putByte(self, c):
        self._data.write(c)
        
    def __str__(self):
        return self._data.getvalue()

class ReportItem:
    def __init__(self, err):
        self.err = err
        if err.startswith('line'):
            tokens = err.split(' ',6)
            self.severity = tokens[5][0] # W or E
            self.line = int(tokens[1])
            self.col = int(tokens[3])
            self.message = tokens[6]
        else:
            tokens = err.split(' ',1)
            self.severity = tokens[0][0]
            self.message = tokens[1]
            self.line = None
            self.col = None
        # TODO - parse emacs mode
    
    def __str__(self):
        severities = dict(W='Warning', E='Error', C='Config')
        try:
            if self.line:
                return "line %d col %d - %s: %s" % (self.line, self.col,
                                                    severities[self.severity],
                                                    self.message)
            
            else:
                return "%s: %s" % (severities[self.severity], self.message)
        except KeyError:
            return self.err

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__,
                             str(self).replace("'", "\\'"))
        
class FactoryDict(dict):
    """I am a dict with a create method and no __setitem__.  This allows
    me to control my own keys.
    """
    def create(self):
        """Subclasses should implement me to generate a new item"""
    
    def _setitem(self, name, value):
        dict.__setitem__(self, name, value)
    
    def __setitem__(self, name, value):
        raise TypeError, "Use create() to get a new object"
        

class SinkFactory(FactoryDict):
    """Mapping for lookup of sinks by handle"""
    def __init__(self):
        FactoryDict.__init__(self)
        self.lastsink = 0
    
    def create(self):
        sink = _Sink()
        sink.struct.sinkData = self.lastsink
        FactoryDict._setitem(self, self.lastsink, sink)
        self.lastsink = self.lastsink+1
        return sink

sinkfactory = SinkFactory()

class _Document(object):
    def __init__(self):
        self.cdoc = _tidy.Create()
        self.errsink = sinkfactory.create()
        _tidy.SetErrorSink(self.cdoc, ctypes.byref(self.errsink.struct))
    
    def write(self, stream):
        stream.write(str(self))
    
    def get_errors(self):
        ret = []
        for line in str(self.errsink).split('\n'):
            line = line.strip(' \n\r')
            if line: ret.append(ReportItem(line))
        return ret
    
    errors=property(get_errors)
    
    def __str__(self):
        stlen = ctypes.c_int(8192)
        st = ctypes.c_buffer(stlen.value)
        rc = _tidy.SaveString(self.cdoc, st, ctypes.byref(stlen))
        if rc==-12: # buffer too small
            st = ctypes.c_buffer(stlen.value)
            _tidy.SaveString(self.cdoc, st, ctypes.byref(stlen))
        return st.value

errors = {'missing or malformed argument for option: ': OptionArgError,
          'unknown option: ': InvalidOptionError,
          }


class DocumentFactory(FactoryDict):
    def _setOptions(self, doc, **options):
        for k in options.keys():
            
            # this will flush out most argument type errors...
            if options[k] is None: options[k] = ''
            
            _tidy.OptParseValue(doc.cdoc, 
                                k.replace('_', '-'), 
                                str(options[k]))
            if doc.errors:
                match=filter(doc.errors[-1].message.startswith, errors.keys())
                if match:
                    raise errors[match[0]](doc.errors[-1].message)
    
    def load(self, doc, arg, loader):
        loader(doc.cdoc, arg)
        _tidy.CleanAndRepair(doc.cdoc)
    
    def loadFile(self, doc, filename):
        self.load(doc, filename, _tidy.ParseFile)
    
    def loadString(self, doc, st):
        self.load(doc, st, _tidy.ParseString)
    
    def _create(self, *args, **kwargs):
        doc = _Document()
        self._setOptions(doc, **kwargs)
        ref = weakref.ref(doc, self.releaseDoc)
        FactoryDict._setitem(self, ref, doc.cdoc)
        return doc
    
    def parse(self, filename, *args, **kwargs):
        """
        Open and process filename as an HTML file, returning a
        processed document object.
        @param kwargs: named options to pass to TidyLib for processing
        the input file.
        @param filename: the name of a file to process
        @return: a document object
        """
        doc = self._create(**kwargs)
        self.loadFile(doc, filename)
        return doc
    
    def parseString(self, st, *args, **kwargs):
        """
        Use st as an HTML file, and process it, returning a
        document object.
        @param kwargs: named options to pass to TidyLib for processing
        the input file.
        @param st: the string to parse
        @return: a document object
        """
        doc = self._create(**kwargs)
        self.loadString(doc, st)
        return doc
    
    def releaseDoc(self, ref):
        _tidy.Release(self[ref])
    
docfactory = DocumentFactory()
parse = docfactory.parse
parseString = docfactory.parseString