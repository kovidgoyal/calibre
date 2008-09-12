"""Response classes.

The seek_wrapper code is not used if you're using UserAgent with
.set_seekable_responses(False), or if you're using the urllib2-level interface
without SeekableProcessor or HTTPEquivProcessor.  Class closeable_response is
instantiated by some handlers (AbstractHTTPHandler), but the closeable_response
interface is only depended upon by Browser-level code.  Function
upgrade_response is only used if you're using Browser or
ResponseUpgradeProcessor.


Copyright 2006 John J. Lee <jjl@pobox.com>

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses (see the file COPYING.txt
included with the distribution).

"""

import copy, mimetools
from cStringIO import StringIO
import urllib2

# XXX Andrew Dalke kindly sent me a similar class in response to my request on
# comp.lang.python, which I then proceeded to lose.  I wrote this class
# instead, but I think he's released his code publicly since, could pinch the
# tests from it, at least...

# For testing seek_wrapper invariant (note that
# test_urllib2.HandlerTest.test_seekable is expected to fail when this
# invariant checking is turned on).  The invariant checking is done by module
# ipdc, which is available here:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/436834
## from ipdbc import ContractBase
## class seek_wrapper(ContractBase):
class seek_wrapper:
    """Adds a seek method to a file object.

    This is only designed for seeking on readonly file-like objects.

    Wrapped file-like object must have a read method.  The readline method is
    only supported if that method is present on the wrapped object.  The
    readlines method is always supported.  xreadlines and iteration are
    supported only for Python 2.2 and above.

    Public attributes:

    wrapped: the wrapped file object
    is_closed: true iff .close() has been called

    WARNING: All other attributes of the wrapped object (ie. those that are not
    one of wrapped, read, readline, readlines, xreadlines, __iter__ and next)
    are passed through unaltered, which may or may not make sense for your
    particular file object.

    """
    # General strategy is to check that cache is full enough, then delegate to
    # the cache (self.__cache, which is a cStringIO.StringIO instance).  A seek
    # position (self.__pos) is maintained independently of the cache, in order
    # that a single cache may be shared between multiple seek_wrapper objects.
    # Copying using module copy shares the cache in this way.

    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.__read_complete_state = [False]
        self.__is_closed_state = [False]
        self.__have_readline = hasattr(self.wrapped, "readline")
        self.__cache = StringIO()
        self.__pos = 0  # seek position

    def invariant(self):
        # The end of the cache is always at the same place as the end of the
        # wrapped file.
        return self.wrapped.tell() == len(self.__cache.getvalue())

    def close(self):
        self.wrapped.close()
        self.is_closed = True

    def __getattr__(self, name):
        if name == "is_closed":
            return self.__is_closed_state[0]
        elif name == "read_complete":
            return self.__read_complete_state[0]

        wrapped = self.__dict__.get("wrapped")
        if wrapped:
            return getattr(wrapped, name)

        return getattr(self.__class__, name)

    def __setattr__(self, name, value):
        if name == "is_closed":
            self.__is_closed_state[0] = bool(value)
        elif name == "read_complete":
            if not self.is_closed:
                self.__read_complete_state[0] = bool(value)
        else:
            self.__dict__[name] = value

    def seek(self, offset, whence=0):
        assert whence in [0,1,2]

        # how much data, if any, do we need to read?
        if whence == 2:  # 2: relative to end of *wrapped* file
            if offset < 0: raise ValueError("negative seek offset")
            # since we don't know yet where the end of that file is, we must
            # read everything
            to_read = None
        else:
            if whence == 0:  # 0: absolute
                if offset < 0: raise ValueError("negative seek offset")
                dest = offset
            else:  # 1: relative to current position
                pos = self.__pos
                if pos < offset:
                    raise ValueError("seek to before start of file")
                dest = pos + offset
            end = len(self.__cache.getvalue())
            to_read = dest - end
            if to_read < 0:
                to_read = 0

        if to_read != 0:
            self.__cache.seek(0, 2)
            if to_read is None:
                assert whence == 2
                self.__cache.write(self.wrapped.read())
                self.read_complete = True
                self.__pos = self.__cache.tell() - offset
            else:
                data = self.wrapped.read(to_read)
                if not data:
                    self.read_complete = True
                else:
                    self.__cache.write(data)
                # Don't raise an exception even if we've seek()ed past the end
                # of .wrapped, since fseek() doesn't complain in that case.
                # Also like fseek(), pretend we have seek()ed past the end,
                # i.e. not:
                #self.__pos = self.__cache.tell()
                # but rather:
                self.__pos = dest
        else:
            self.__pos = dest

    def tell(self):
        return self.__pos

    def __copy__(self):
        cpy = self.__class__(self.wrapped)
        cpy.__cache = self.__cache
        cpy.__read_complete_state = self.__read_complete_state
        cpy.__is_closed_state = self.__is_closed_state
        return cpy

    def get_data(self):
        pos = self.__pos
        try:
            self.seek(0)
            return self.read(-1)
        finally:
            self.__pos = pos

    def read(self, size=-1):
        pos = self.__pos
        end = len(self.__cache.getvalue())
        available = end - pos

        # enough data already cached?
        if size <= available and size != -1:
            self.__cache.seek(pos)
            self.__pos = pos+size
            return self.__cache.read(size)

        # no, so read sufficient data from wrapped file and cache it
        self.__cache.seek(0, 2)
        if size == -1:
            self.__cache.write(self.wrapped.read())
            self.read_complete = True
        else:
            to_read = size - available
            assert to_read > 0
            data = self.wrapped.read(to_read)
            if not data:
                self.read_complete = True
            else:
                self.__cache.write(data)
        self.__cache.seek(pos)

        data = self.__cache.read(size)
        self.__pos = self.__cache.tell()
        assert self.__pos == pos + len(data)
        return data

    def readline(self, size=-1):
        if not self.__have_readline:
            raise NotImplementedError("no readline method on wrapped object")

        # line we're about to read might not be complete in the cache, so
        # read another line first
        pos = self.__pos
        self.__cache.seek(0, 2)
        data = self.wrapped.readline()
        if not data:
            self.read_complete = True
        else:
            self.__cache.write(data)
        self.__cache.seek(pos)

        data = self.__cache.readline()
        if size != -1:
            r = data[:size]
            self.__pos = pos+size
        else:
            r = data
            self.__pos = pos+len(data)
        return r

    def readlines(self, sizehint=-1):
        pos = self.__pos
        self.__cache.seek(0, 2)
        self.__cache.write(self.wrapped.read())
        self.read_complete = True
        self.__cache.seek(pos)
        data = self.__cache.readlines(sizehint)
        self.__pos = self.__cache.tell()
        return data

    def __iter__(self): return self
    def next(self):
        line = self.readline()
        if line == "": raise StopIteration
        return line

    xreadlines = __iter__

    def __repr__(self):
        return ("<%s at %s whose wrapped object = %r>" %
                (self.__class__.__name__, hex(abs(id(self))), self.wrapped))


class response_seek_wrapper(seek_wrapper):

    """
    Supports copying response objects and setting response body data.

    """

    def __init__(self, wrapped):
        seek_wrapper.__init__(self, wrapped)
        self._headers = self.wrapped.info()

    def __copy__(self):
        cpy = seek_wrapper.__copy__(self)
        # copy headers from delegate
        cpy._headers = copy.copy(self.info())
        return cpy

    # Note that .info() and .geturl() (the only two urllib2 response methods
    # that are not implemented by seek_wrapper) must be here explicitly rather
    # than by seek_wrapper's __getattr__ delegation) so that the nasty
    # dynamically-created HTTPError classes in get_seek_wrapper_class() get the
    # wrapped object's implementation, and not HTTPError's.

    def info(self):
        return self._headers

    def geturl(self):
        return self.wrapped.geturl()

    def set_data(self, data):
        self.seek(0)
        self.read()
        self.close()
        cache = self._seek_wrapper__cache = StringIO()
        cache.write(data)
        self.seek(0)


class eoffile:
    # file-like object that always claims to be at end-of-file...
    def read(self, size=-1): return ""
    def readline(self, size=-1): return ""
    def __iter__(self): return self
    def next(self): return ""
    def close(self): pass

class eofresponse(eoffile):
    def __init__(self, url, headers, code, msg):
        self._url = url
        self._headers = headers
        self.code = code
        self.msg = msg
    def geturl(self): return self._url
    def info(self): return self._headers


class closeable_response:
    """Avoids unnecessarily clobbering urllib.addinfourl methods on .close().

    Only supports responses returned by mechanize.HTTPHandler.

    After .close(), the following methods are supported:

    .read()
    .readline()
    .info()
    .geturl()
    .__iter__()
    .next()
    .close()

    and the following attributes are supported:

    .code
    .msg

    Also supports pickling (but the stdlib currently does something to prevent
    it: http://python.org/sf/1144636).

    """
    # presence of this attr indicates is useable after .close()
    closeable_response = None

    def __init__(self, fp, headers, url, code, msg):
        self._set_fp(fp)
        self._headers = headers
        self._url = url
        self.code = code
        self.msg = msg

    def _set_fp(self, fp):
        self.fp = fp
        self.read = self.fp.read
        self.readline = self.fp.readline
        if hasattr(self.fp, "readlines"): self.readlines = self.fp.readlines
        if hasattr(self.fp, "fileno"):
            self.fileno = self.fp.fileno
        else:
            self.fileno = lambda: None
        self.__iter__ = self.fp.__iter__
        self.next = self.fp.next

    def __repr__(self):
        return '<%s at %s whose fp = %r>' % (
            self.__class__.__name__, hex(abs(id(self))), self.fp)

    def info(self):
        return self._headers

    def geturl(self):
        return self._url

    def close(self):
        self.fp._close = True
        wrapped = self.fp
        wrapped.close()
        new_wrapped = eofresponse(
            self._url, self._headers, self.code, self.msg)
        self._set_fp(new_wrapped)

    def __getstate__(self):
        # There are three obvious options here:
        # 1. truncate
        # 2. read to end
        # 3. close socket, pickle state including read position, then open
        #    again on unpickle and use Range header
        # XXXX um, 4. refuse to pickle unless .close()d.  This is better,
        #  actually ("errors should never pass silently").  Pickling doesn't
        #  work anyway ATM, because of http://python.org/sf/1144636 so fix
        #  this later

        # 2 breaks pickle protocol, because one expects the original object
        # to be left unscathed by pickling.  3 is too complicated and
        # surprising (and too much work ;-) to happen in a sane __getstate__.
        # So we do 1.

        state = self.__dict__.copy()
        new_wrapped = eofresponse(
            self._url, self._headers, self.code, self.msg)
        state["wrapped"] = new_wrapped
        return state

def test_response(data='test data', headers=[],
                  url="http://example.com/", code=200, msg="OK"):
    return make_response(data, headers, url, code, msg)

def test_html_response(data='test data', headers=[],
                       url="http://example.com/", code=200, msg="OK"):
    headers += [("Content-type", "text/html")]
    return make_response(data, headers, url, code, msg)

def make_response(data, headers, url, code, msg):
    """Convenient factory for objects implementing response interface.

    data: string containing response body data
    headers: sequence of (name, value) pairs
    url: URL of response
    code: integer response code (e.g. 200)
    msg: string response code message (e.g. "OK")

    """
    mime_headers = make_headers(headers)
    r = closeable_response(StringIO(data), mime_headers, url, code, msg)
    return response_seek_wrapper(r)


def make_headers(headers):
    """
    headers: sequence of (name, value) pairs
    """
    hdr_text = []
    for name_value in headers:
        hdr_text.append("%s: %s" % name_value)
    return mimetools.Message(StringIO("\n".join(hdr_text)))


# Rest of this module is especially horrible, but needed, at least until fork
# urllib2.  Even then, may want to preseve urllib2 compatibility.

def get_seek_wrapper_class(response):
    # in order to wrap response objects that are also exceptions, we must
    # dynamically subclass the exception :-(((
    if (isinstance(response, urllib2.HTTPError) and
        not hasattr(response, "seek")):
        if response.__class__.__module__ == "__builtin__":
            exc_class_name = response.__class__.__name__
        else:
            exc_class_name = "%s.%s" % (
                response.__class__.__module__, response.__class__.__name__)

        class httperror_seek_wrapper(response_seek_wrapper, response.__class__):
            # this only derives from HTTPError in order to be a subclass --
            # the HTTPError behaviour comes from delegation

            _exc_class_name = exc_class_name

            def __init__(self, wrapped):
                response_seek_wrapper.__init__(self, wrapped)
                # be compatible with undocumented HTTPError attributes :-(
                self.hdrs = wrapped.info()
                self.filename = wrapped.geturl()

            def __repr__(self):
                return (
                    "<%s (%s instance) at %s "
                    "whose wrapped object = %r>" % (
                    self.__class__.__name__, self._exc_class_name,
                    hex(abs(id(self))), self.wrapped)
                    )
        wrapper_class = httperror_seek_wrapper
    else:
        wrapper_class = response_seek_wrapper
    return wrapper_class

def seek_wrapped_response(response):
    """Return a copy of response that supports seekable response interface.

    Accepts responses from both mechanize and urllib2 handlers.

    Copes with both oridinary response instances and HTTPError instances (which
    can't be simply wrapped due to the requirement of preserving the exception
    base class).
    """
    if not hasattr(response, "seek"):
        wrapper_class = get_seek_wrapper_class(response)
        response = wrapper_class(response)
    assert hasattr(response, "get_data")
    return response

def upgrade_response(response):
    """Return a copy of response that supports Browser response interface.

    Browser response interface is that of "seekable responses"
    (response_seek_wrapper), plus the requirement that responses must be
    useable after .close() (closeable_response).

    Accepts responses from both mechanize and urllib2 handlers.

    Copes with both ordinary response instances and HTTPError instances (which
    can't be simply wrapped due to the requirement of preserving the exception
    base class).
    """
    wrapper_class = get_seek_wrapper_class(response)
    if hasattr(response, "closeable_response"):
        if not hasattr(response, "seek"):
            response = wrapper_class(response)
        assert hasattr(response, "get_data")
        return copy.copy(response)

    # a urllib2 handler constructed the response, i.e. the response is an
    # urllib.addinfourl or a urllib2.HTTPError, instead of a
    # _Util.closeable_response as returned by e.g. mechanize.HTTPHandler
    try:
        code = response.code
    except AttributeError:
        code = None
    try:
        msg = response.msg
    except AttributeError:
        msg = None

    # may have already-.read() data from .seek() cache
    data = None
    get_data = getattr(response, "get_data", None)
    if get_data:
        data = get_data()

    response = closeable_response(
        response.fp, response.info(), response.geturl(), code, msg)
    response = wrapper_class(response)
    if data:
        response.set_data(data)
    return response
