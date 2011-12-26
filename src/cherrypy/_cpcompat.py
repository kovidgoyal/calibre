"""Compatibility code for using CherryPy with various versions of Python.

CherryPy 3.2 is compatible with Python versions 2.3+. This module provides a
useful abstraction over the differences between Python versions, sometimes by
preferring a newer idiom, sometimes an older one, and sometimes a custom one.

In particular, Python 2 uses str and '' for byte strings, while Python 3
uses str and '' for unicode strings. We will call each of these the 'native
string' type for each version. Because of this major difference, this module
provides new 'bytestr', 'unicodestr', and 'nativestr' attributes, as well as
two functions: 'ntob', which translates native strings (of type 'str') into
byte strings regardless of Python version, and 'ntou', which translates native
strings to unicode strings. This also provides a 'BytesIO' name for dealing
specifically with bytes, and a 'StringIO' name for dealing with native strings.
It also provides a 'base64_decode' function with native strings as input and
output.
"""
import os
import re
import sys

if sys.version_info >= (3, 0):
    py3k = True
    bytestr = bytes
    unicodestr = str
    nativestr = unicodestr
    basestring = (bytes, str)
    def ntob(n, encoding='ISO-8859-1'):
        """Return the given native string as a byte string in the given encoding."""
        # In Python 3, the native string type is unicode
        return n.encode(encoding)
    def ntou(n, encoding='ISO-8859-1'):
        """Return the given native string as a unicode string with the given encoding."""
        # In Python 3, the native string type is unicode
        return n
    def tonative(n, encoding='ISO-8859-1'):
        """Return the given string as a native string in the given encoding."""
        # In Python 3, the native string type is unicode
        if isinstance(n, bytes):
            return n.decode(encoding)
        return n
    # type("")
    from io import StringIO
    # bytes:
    from io import BytesIO as BytesIO
else:
    # Python 2
    py3k = False
    bytestr = str
    unicodestr = unicode
    nativestr = bytestr
    basestring = basestring
    def ntob(n, encoding='ISO-8859-1'):
        """Return the given native string as a byte string in the given encoding."""
        # In Python 2, the native string type is bytes. Assume it's already
        # in the given encoding, which for ISO-8859-1 is almost always what
        # was intended.
        return n
    def ntou(n, encoding='ISO-8859-1'):
        """Return the given native string as a unicode string with the given encoding."""
        # In Python 2, the native string type is bytes.
        # First, check for the special encoding 'escape'. The test suite uses this
        # to signal that it wants to pass a string with embedded \uXXXX escapes,
        # but without having to prefix it with u'' for Python 2, but no prefix
        # for Python 3.
        if encoding == 'escape':
            return unicode(
                re.sub(r'\\u([0-9a-zA-Z]{4})',
                       lambda m: unichr(int(m.group(1), 16)),
                       n.decode('ISO-8859-1')))
        # Assume it's already in the given encoding, which for ISO-8859-1 is almost
        # always what was intended.
        return n.decode(encoding)
    def tonative(n, encoding='ISO-8859-1'):
        """Return the given string as a native string in the given encoding."""
        # In Python 2, the native string type is bytes.
        if isinstance(n, unicode):
            return n.encode(encoding)
        return n
    try:
        # type("")
        from cStringIO import StringIO
    except ImportError:
        # type("")
        from StringIO import StringIO
    # bytes:
    BytesIO = StringIO

try:
    set = set
except NameError:
    from sets import Set as set

try:
    # Python 3.1+
    from base64 import decodebytes as _base64_decodebytes
except ImportError:
    # Python 3.0-
    # since CherryPy claims compability with Python 2.3, we must use
    # the legacy API of base64
    from base64 import decodestring as _base64_decodebytes

def base64_decode(n, encoding='ISO-8859-1'):
    """Return the native string base64-decoded (as a native string)."""
    if isinstance(n, unicodestr):
        b = n.encode(encoding)
    else:
        b = n
    b = _base64_decodebytes(b)
    if nativestr is unicodestr:
        return b.decode(encoding)
    else:
        return b

try:
    # Python 2.5+
    from hashlib import md5
except ImportError:
    from md5 import new as md5

try:
    # Python 2.5+
    from hashlib import sha1 as sha
except ImportError:
    from sha import new as sha

try:
    sorted = sorted
except NameError:
    def sorted(i):
        i = i[:]
        i.sort()
        return i

try:
    reversed = reversed
except NameError:
    def reversed(x):
        i = len(x)
        while i > 0:
            i -= 1
            yield x[i]

try:
    # Python 3
    from urllib.parse import urljoin, urlencode
    from urllib.parse import quote, quote_plus
    from urllib.request import unquote, urlopen
    from urllib.request import parse_http_list, parse_keqv_list
except ImportError:
    # Python 2
    from urlparse import urljoin
    from urllib import urlencode, urlopen
    from urllib import quote, quote_plus
    from urllib import unquote
    from urllib2 import parse_http_list, parse_keqv_list

try:
    from threading import local as threadlocal
except ImportError:
    from cherrypy._cpthreadinglocal import local as threadlocal

try:
    dict.iteritems
    # Python 2
    iteritems = lambda d: d.iteritems()
    copyitems = lambda d: d.items()
except AttributeError:
    # Python 3
    iteritems = lambda d: d.items()
    copyitems = lambda d: list(d.items())

try:
    dict.iterkeys
    # Python 2
    iterkeys = lambda d: d.iterkeys()
    copykeys = lambda d: d.keys()
except AttributeError:
    # Python 3
    iterkeys = lambda d: d.keys()
    copykeys = lambda d: list(d.keys())

try:
    dict.itervalues
    # Python 2
    itervalues = lambda d: d.itervalues()
    copyvalues = lambda d: d.values()
except AttributeError:
    # Python 3
    itervalues = lambda d: d.values()
    copyvalues = lambda d: list(d.values())

try:
    # Python 3
    import builtins
except ImportError:
    # Python 2
    import __builtin__ as builtins

try:
    # Python 2. We have to do it in this order so Python 2 builds
    # don't try to import the 'http' module from cherrypy.lib
    from Cookie import SimpleCookie, CookieError
    from httplib import BadStatusLine, HTTPConnection, HTTPSConnection, IncompleteRead, NotConnected
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    # Python 3
    from http.cookies import SimpleCookie, CookieError
    from http.client import BadStatusLine, HTTPConnection, HTTPSConnection, IncompleteRead, NotConnected
    from http.server import BaseHTTPRequestHandler

try:
    # Python 2. We have to do it in this order so Python 2 builds
    # don't try to import the 'http' module from cherrypy.lib
    from httplib import HTTPSConnection
except ImportError:
    try:
        # Python 3
        from http.client import HTTPSConnection
    except ImportError:
        # Some platforms which don't have SSL don't expose HTTPSConnection
        HTTPSConnection = None

try:
    # Python 2
    xrange = xrange
except NameError:
    # Python 3
    xrange = range

import threading
if hasattr(threading.Thread, "daemon"):
    # Python 2.6+
    def get_daemon(t):
        return t.daemon
    def set_daemon(t, val):
        t.daemon = val
else:
    def get_daemon(t):
        return t.isDaemon()
    def set_daemon(t, val):
        t.setDaemon(val)

try:
    from email.utils import formatdate
    def HTTPDate(timeval=None):
        return formatdate(timeval, usegmt=True)
except ImportError:
    from rfc822 import formatdate as HTTPDate

try:
    # Python 3
    from urllib.parse import unquote as parse_unquote
    def unquote_qs(atom, encoding, errors='strict'):
        return parse_unquote(atom.replace('+', ' '), encoding=encoding, errors=errors)
except ImportError:
    # Python 2
    from urllib import unquote as parse_unquote
    def unquote_qs(atom, encoding, errors='strict'):
        return parse_unquote(atom.replace('+', ' ')).decode(encoding, errors)

try:
    # Prefer simplejson, which is usually more advanced than the builtin module.
    import simplejson as json
    json_decode = json.JSONDecoder().decode
    json_encode = json.JSONEncoder().iterencode
except ImportError:
    if py3k:
        # Python 3.0: json is part of the standard library,
        # but outputs unicode. We need bytes.
        import json
        json_decode = json.JSONDecoder().decode
        _json_encode = json.JSONEncoder().iterencode
        def json_encode(value):
            for chunk in _json_encode(value):
                yield chunk.encode('utf8')
    elif sys.version_info >= (2, 6):
        # Python 2.6: json is part of the standard library
        import json
        json_decode = json.JSONDecoder().decode
        json_encode = json.JSONEncoder().iterencode
    else:
        json = None
        def json_decode(s):
            raise ValueError('No JSON library is available')
        def json_encode(s):
            raise ValueError('No JSON library is available')

try:
    import cPickle as pickle
except ImportError:
    # In Python 2, pickle is a Python version.
    # In Python 3, pickle is the sped-up C version.
    import pickle

try:
    os.urandom(20)
    import binascii
    def random20():
        return binascii.hexlify(os.urandom(20)).decode('ascii')
except (AttributeError, NotImplementedError):
    import random
    # os.urandom not available until Python 2.4. Fall back to random.random.
    def random20():
        return sha('%s' % random.random()).hexdigest()

try:
    from _thread import get_ident as get_thread_ident
except ImportError:
    from thread import get_ident as get_thread_ident

try:
    # Python 3
    next = next
except NameError:
    # Python 2
    def next(i):
        return i.next()
