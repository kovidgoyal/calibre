"""Request body processing for CherryPy.

.. versionadded:: 3.2

Application authors have complete control over the parsing of HTTP request
entities. In short, :attr:`cherrypy.request.body<cherrypy._cprequest.Request.body>`
is now always set to an instance of :class:`RequestBody<cherrypy._cpreqbody.RequestBody>`,
and *that* class is a subclass of :class:`Entity<cherrypy._cpreqbody.Entity>`.

When an HTTP request includes an entity body, it is often desirable to
provide that information to applications in a form other than the raw bytes.
Different content types demand different approaches. Examples:

 * For a GIF file, we want the raw bytes in a stream.
 * An HTML form is better parsed into its component fields, and each text field
   decoded from bytes to unicode.
 * A JSON body should be deserialized into a Python dict or list.

When the request contains a Content-Type header, the media type is used as a
key to look up a value in the
:attr:`request.body.processors<cherrypy._cpreqbody.Entity.processors>` dict.
If the full media
type is not found, then the major type is tried; for example, if no processor
is found for the 'image/jpeg' type, then we look for a processor for the 'image'
types altogether. If neither the full type nor the major type has a matching
processor, then a default processor is used
(:func:`default_proc<cherrypy._cpreqbody.Entity.default_proc>`). For most
types, this means no processing is done, and the body is left unread as a
raw byte stream. Processors are configurable in an 'on_start_resource' hook.

Some processors, especially those for the 'text' types, attempt to decode bytes
to unicode. If the Content-Type request header includes a 'charset' parameter,
this is used to decode the entity. Otherwise, one or more default charsets may
be attempted, although this decision is up to each processor. If a processor
successfully decodes an Entity or Part, it should set the
:attr:`charset<cherrypy._cpreqbody.Entity.charset>` attribute
on the Entity or Part to the name of the successful charset, so that
applications can easily re-encode or transcode the value if they wish.

If the Content-Type of the request entity is of major type 'multipart', then
the above parsing process, and possibly a decoding process, is performed for
each part.

For both the full entity and multipart parts, a Content-Disposition header may
be used to fill :attr:`name<cherrypy._cpreqbody.Entity.name>` and
:attr:`filename<cherrypy._cpreqbody.Entity.filename>` attributes on the
request.body or the Part.

.. _custombodyprocessors:

Custom Processors
=================

You can add your own processors for any specific or major MIME type. Simply add
it to the :attr:`processors<cherrypy._cprequest.Entity.processors>` dict in a
hook/tool that runs at ``on_start_resource`` or ``before_request_body``. 
Here's the built-in JSON tool for an example::

    def json_in(force=True, debug=False):
        request = cherrypy.serving.request
        def json_processor(entity):
            \"""Read application/json data into request.json.\"""
            if not entity.headers.get("Content-Length", ""):
                raise cherrypy.HTTPError(411)
            
            body = entity.fp.read()
            try:
                request.json = json_decode(body)
            except ValueError:
                raise cherrypy.HTTPError(400, 'Invalid JSON document')
        if force:
            request.body.processors.clear()
            request.body.default_proc = cherrypy.HTTPError(
                415, 'Expected an application/json content type')
        request.body.processors['application/json'] = json_processor

We begin by defining a new ``json_processor`` function to stick in the ``processors``
dictionary. All processor functions take a single argument, the ``Entity`` instance
they are to process. It will be called whenever a request is received (for those
URI's where the tool is turned on) which has a ``Content-Type`` of
"application/json".

First, it checks for a valid ``Content-Length`` (raising 411 if not valid), then
reads the remaining bytes on the socket. The ``fp`` object knows its own length, so
it won't hang waiting for data that never arrives. It will return when all data
has been read. Then, we decode those bytes using Python's built-in ``json`` module,
and stick the decoded result onto ``request.json`` . If it cannot be decoded, we
raise 400.

If the "force" argument is True (the default), the ``Tool`` clears the ``processors``
dict so that request entities of other ``Content-Types`` aren't parsed at all. Since
there's no entry for those invalid MIME types, the ``default_proc`` method of ``cherrypy.request.body``
is called. But this does nothing by default (usually to provide the page handler an opportunity to handle it.)
But in our case, we want to raise 415, so we replace ``request.body.default_proc``
with the error (``HTTPError`` instances, when called, raise themselves).

If we were defining a custom processor, we can do so without making a ``Tool``. Just add the config entry::

    request.body.processors = {'application/json': json_processor}

Note that you can only replace the ``processors`` dict wholesale this way, not update the existing one.
"""

try:
    from io import DEFAULT_BUFFER_SIZE
except ImportError:
    DEFAULT_BUFFER_SIZE = 8192
import re
import sys
import tempfile
try:
    from urllib import unquote_plus
except ImportError:
    def unquote_plus(bs):
        """Bytes version of urllib.parse.unquote_plus."""
        bs = bs.replace(ntob('+'), ntob(' '))
        atoms = bs.split(ntob('%'))
        for i in range(1, len(atoms)):
            item = atoms[i]
            try:
                pct = int(item[:2], 16)
                atoms[i] = bytes([pct]) + item[2:]
            except ValueError:
                pass
        return ntob('').join(atoms)

import cherrypy
from cherrypy._cpcompat import basestring, ntob, ntou
from cherrypy.lib import httputil


# -------------------------------- Processors -------------------------------- #

def process_urlencoded(entity):
    """Read application/x-www-form-urlencoded data into entity.params."""
    qs = entity.fp.read()
    for charset in entity.attempt_charsets:
        try:
            params = {}
            for aparam in qs.split(ntob('&')):
                for pair in aparam.split(ntob(';')):
                    if not pair:
                        continue
                    
                    atoms = pair.split(ntob('='), 1)
                    if len(atoms) == 1:
                        atoms.append(ntob(''))
                    
                    key = unquote_plus(atoms[0]).decode(charset)
                    value = unquote_plus(atoms[1]).decode(charset)
                    
                    if key in params:
                        if not isinstance(params[key], list):
                            params[key] = [params[key]]
                        params[key].append(value)
                    else:
                        params[key] = value
        except UnicodeDecodeError:
            pass
        else:
            entity.charset = charset
            break
    else:
        raise cherrypy.HTTPError(
            400, "The request entity could not be decoded. The following "
            "charsets were attempted: %s" % repr(entity.attempt_charsets))
        
    # Now that all values have been successfully parsed and decoded,
    # apply them to the entity.params dict.
    for key, value in params.items():
        if key in entity.params:
            if not isinstance(entity.params[key], list):
                entity.params[key] = [entity.params[key]]
            entity.params[key].append(value)
        else:
            entity.params[key] = value


def process_multipart(entity):
    """Read all multipart parts into entity.parts."""
    ib = ""
    if 'boundary' in entity.content_type.params:
        # http://tools.ietf.org/html/rfc2046#section-5.1.1
        # "The grammar for parameters on the Content-type field is such that it
        # is often necessary to enclose the boundary parameter values in quotes
        # on the Content-type line"
        ib = entity.content_type.params['boundary'].strip('"')
    
    if not re.match("^[ -~]{0,200}[!-~]$", ib):
        raise ValueError('Invalid boundary in multipart form: %r' % (ib,))
    
    ib = ('--' + ib).encode('ascii')
    
    # Find the first marker
    while True:
        b = entity.readline()
        if not b:
            return
        
        b = b.strip()
        if b == ib:
            break
    
    # Read all parts
    while True:
        part = entity.part_class.from_fp(entity.fp, ib)
        entity.parts.append(part)
        part.process()
        if part.fp.done:
            break

def process_multipart_form_data(entity):
    """Read all multipart/form-data parts into entity.parts or entity.params."""
    process_multipart(entity)
    
    kept_parts = []
    for part in entity.parts:
        if part.name is None:
            kept_parts.append(part)
        else:
            if part.filename is None:
                # It's a regular field
                value = part.fullvalue()
            else:
                # It's a file upload. Retain the whole part so consumer code
                # has access to its .file and .filename attributes.
                value = part
            
            if part.name in entity.params:
                if not isinstance(entity.params[part.name], list):
                    entity.params[part.name] = [entity.params[part.name]]
                entity.params[part.name].append(value)
            else:
                entity.params[part.name] = value
    
    entity.parts = kept_parts

def _old_process_multipart(entity):
    """The behavior of 3.2 and lower. Deprecated and will be changed in 3.3."""
    process_multipart(entity)
    
    params = entity.params
    
    for part in entity.parts:
        if part.name is None:
            key = ntou('parts')
        else:
            key = part.name
        
        if part.filename is None:
            # It's a regular field
            value = part.fullvalue()
        else:
            # It's a file upload. Retain the whole part so consumer code
            # has access to its .file and .filename attributes.
            value = part
        
        if key in params:
            if not isinstance(params[key], list):
                params[key] = [params[key]]
            params[key].append(value)
        else:
            params[key] = value



# --------------------------------- Entities --------------------------------- #


class Entity(object):
    """An HTTP request body, or MIME multipart body.
    
    This class collects information about the HTTP request entity. When a
    given entity is of MIME type "multipart", each part is parsed into its own
    Entity instance, and the set of parts stored in
    :attr:`entity.parts<cherrypy._cpreqbody.Entity.parts>`.
    
    Between the ``before_request_body`` and ``before_handler`` tools, CherryPy
    tries to process the request body (if any) by calling
    :func:`request.body.process<cherrypy._cpreqbody.RequestBody.process`.
    This uses the ``content_type`` of the Entity to look up a suitable processor
    in :attr:`Entity.processors<cherrypy._cpreqbody.Entity.processors>`, a dict.
    If a matching processor cannot be found for the complete Content-Type,
    it tries again using the major type. For example, if a request with an
    entity of type "image/jpeg" arrives, but no processor can be found for
    that complete type, then one is sought for the major type "image". If a
    processor is still not found, then the
    :func:`default_proc<cherrypy._cpreqbody.Entity.default_proc>` method of the
    Entity is called (which does nothing by default; you can override this too).
    
    CherryPy includes processors for the "application/x-www-form-urlencoded"
    type, the "multipart/form-data" type, and the "multipart" major type.
    CherryPy 3.2 processes these types almost exactly as older versions.
    Parts are passed as arguments to the page handler using their
    ``Content-Disposition.name`` if given, otherwise in a generic "parts"
    argument. Each such part is either a string, or the
    :class:`Part<cherrypy._cpreqbody.Part>` itself if it's a file. (In this
    case it will have ``file`` and ``filename`` attributes, or possibly a
    ``value`` attribute). Each Part is itself a subclass of
    Entity, and has its own ``process`` method and ``processors`` dict.
    
    There is a separate processor for the "multipart" major type which is more
    flexible, and simply stores all multipart parts in
    :attr:`request.body.parts<cherrypy._cpreqbody.Entity.parts>`. You can
    enable it with::
    
        cherrypy.request.body.processors['multipart'] = _cpreqbody.process_multipart
    
    in an ``on_start_resource`` tool.
    """
    
    # http://tools.ietf.org/html/rfc2046#section-4.1.2:
    # "The default character set, which must be assumed in the
    # absence of a charset parameter, is US-ASCII."
    # However, many browsers send data in utf-8 with no charset.
    attempt_charsets = ['utf-8']
    """A list of strings, each of which should be a known encoding.
    
    When the Content-Type of the request body warrants it, each of the given
    encodings will be tried in order. The first one to successfully decode the
    entity without raising an error is stored as
    :attr:`entity.charset<cherrypy._cpreqbody.Entity.charset>`. This defaults
    to ``['utf-8']`` (plus 'ISO-8859-1' for "text/\*" types, as required by 
    `HTTP/1.1 <http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1>`_), 
    but ``['us-ascii', 'utf-8']`` for multipart parts.
    """
    
    charset = None
    """The successful decoding; see "attempt_charsets" above."""
    
    content_type = None
    """The value of the Content-Type request header.
    
    If the Entity is part of a multipart payload, this will be the Content-Type
    given in the MIME headers for this part.
    """
    
    default_content_type = 'application/x-www-form-urlencoded'
    """This defines a default ``Content-Type`` to use if no Content-Type header
    is given. The empty string is used for RequestBody, which results in the
    request body not being read or parsed at all. This is by design; a missing
    ``Content-Type`` header in the HTTP request entity is an error at best,
    and a security hole at worst. For multipart parts, however, the MIME spec
    declares that a part with no Content-Type defaults to "text/plain"
    (see :class:`Part<cherrypy._cpreqbody.Part>`).
    """
    
    filename = None
    """The ``Content-Disposition.filename`` header, if available."""
    
    fp = None
    """The readable socket file object."""
    
    headers = None
    """A dict of request/multipart header names and values.
    
    This is a copy of the ``request.headers`` for the ``request.body``;
    for multipart parts, it is the set of headers for that part.
    """
    
    length = None
    """The value of the ``Content-Length`` header, if provided."""
    
    name = None
    """The "name" parameter of the ``Content-Disposition`` header, if any."""
    
    params = None
    """
    If the request Content-Type is 'application/x-www-form-urlencoded' or
    multipart, this will be a dict of the params pulled from the entity
    body; that is, it will be the portion of request.params that come
    from the message body (sometimes called "POST params", although they
    can be sent with various HTTP method verbs). This value is set between
    the 'before_request_body' and 'before_handler' hooks (assuming that
    process_request_body is True)."""
    
    processors = {'application/x-www-form-urlencoded': process_urlencoded,
                  'multipart/form-data': process_multipart_form_data,
                  'multipart': process_multipart,
                  }
    """A dict of Content-Type names to processor methods."""
    
    parts = None
    """A list of Part instances if ``Content-Type`` is of major type "multipart"."""
    
    part_class = None
    """The class used for multipart parts.
    
    You can replace this with custom subclasses to alter the processing of
    multipart parts.
    """
    
    def __init__(self, fp, headers, params=None, parts=None):
        # Make an instance-specific copy of the class processors
        # so Tools, etc. can replace them per-request.
        self.processors = self.processors.copy()
        
        self.fp = fp
        self.headers = headers
        
        if params is None:
            params = {}
        self.params = params
        
        if parts is None:
            parts = []
        self.parts = parts
        
        # Content-Type
        self.content_type = headers.elements('Content-Type')
        if self.content_type:
            self.content_type = self.content_type[0]
        else:
            self.content_type = httputil.HeaderElement.from_str(
                self.default_content_type)
        
        # Copy the class 'attempt_charsets', prepending any Content-Type charset
        dec = self.content_type.params.get("charset", None)
        if dec:
            self.attempt_charsets = [dec] + [c for c in self.attempt_charsets
                                             if c != dec]
        else:
            self.attempt_charsets = self.attempt_charsets[:]
        
        # Length
        self.length = None
        clen = headers.get('Content-Length', None)
        # If Transfer-Encoding is 'chunked', ignore any Content-Length.
        if clen is not None and 'chunked' not in headers.get('Transfer-Encoding', ''):
            try:
                self.length = int(clen)
            except ValueError:
                pass
        
        # Content-Disposition
        self.name = None
        self.filename = None
        disp = headers.elements('Content-Disposition')
        if disp:
            disp = disp[0]
            if 'name' in disp.params:
                self.name = disp.params['name']
                if self.name.startswith('"') and self.name.endswith('"'):
                    self.name = self.name[1:-1]
            if 'filename' in disp.params:
                self.filename = disp.params['filename']
                if self.filename.startswith('"') and self.filename.endswith('"'):
                    self.filename = self.filename[1:-1]
    
    # The 'type' attribute is deprecated in 3.2; remove it in 3.3.
    type = property(lambda self: self.content_type,
        doc="""A deprecated alias for :attr:`content_type<cherrypy._cpreqbody.Entity.content_type>`.""")
    
    def read(self, size=None, fp_out=None):
        return self.fp.read(size, fp_out)
    
    def readline(self, size=None):
        return self.fp.readline(size)
    
    def readlines(self, sizehint=None):
        return self.fp.readlines(sizehint)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def next(self):
        return self.__next__()
    
    def read_into_file(self, fp_out=None):
        """Read the request body into fp_out (or make_file() if None). Return fp_out."""
        if fp_out is None:
            fp_out = self.make_file()
        self.read(fp_out=fp_out)
        return fp_out
    
    def make_file(self):
        """Return a file-like object into which the request body will be read.
        
        By default, this will return a TemporaryFile. Override as needed.
        See also :attr:`cherrypy._cpreqbody.Part.maxrambytes`."""
        return tempfile.TemporaryFile()
    
    def fullvalue(self):
        """Return this entity as a string, whether stored in a file or not."""
        if self.file:
            # It was stored in a tempfile. Read it.
            self.file.seek(0)
            value = self.file.read()
            self.file.seek(0)
        else:
            value = self.value
        return value
    
    def process(self):
        """Execute the best-match processor for the given media type."""
        proc = None
        ct = self.content_type.value
        try:
            proc = self.processors[ct]
        except KeyError:
            toptype = ct.split('/', 1)[0]
            try:
                proc = self.processors[toptype]
            except KeyError:
                pass
        if proc is None:
            self.default_proc()
        else:
            proc(self)
    
    def default_proc(self):
        """Called if a more-specific processor is not found for the ``Content-Type``."""
        # Leave the fp alone for someone else to read. This works fine
        # for request.body, but the Part subclasses need to override this
        # so they can move on to the next part.
        pass


class Part(Entity):
    """A MIME part entity, part of a multipart entity."""
    
    # "The default character set, which must be assumed in the absence of a
    # charset parameter, is US-ASCII."
    attempt_charsets = ['us-ascii', 'utf-8']
    """A list of strings, each of which should be a known encoding.
    
    When the Content-Type of the request body warrants it, each of the given
    encodings will be tried in order. The first one to successfully decode the
    entity without raising an error is stored as
    :attr:`entity.charset<cherrypy._cpreqbody.Entity.charset>`. This defaults
    to ``['utf-8']`` (plus 'ISO-8859-1' for "text/\*" types, as required by 
    `HTTP/1.1 <http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1>`_), 
    but ``['us-ascii', 'utf-8']`` for multipart parts.
    """
    
    boundary = None
    """The MIME multipart boundary."""
    
    default_content_type = 'text/plain'
    """This defines a default ``Content-Type`` to use if no Content-Type header
    is given. The empty string is used for RequestBody, which results in the
    request body not being read or parsed at all. This is by design; a missing
    ``Content-Type`` header in the HTTP request entity is an error at best,
    and a security hole at worst. For multipart parts, however (this class),
    the MIME spec declares that a part with no Content-Type defaults to
    "text/plain".
    """
    
    # This is the default in stdlib cgi. We may want to increase it.
    maxrambytes = 1000
    """The threshold of bytes after which point the ``Part`` will store its data
    in a file (generated by :func:`make_file<cherrypy._cprequest.Entity.make_file>`)
    instead of a string. Defaults to 1000, just like the :mod:`cgi` module in
    Python's standard library.
    """
    
    def __init__(self, fp, headers, boundary):
        Entity.__init__(self, fp, headers)
        self.boundary = boundary
        self.file = None
        self.value = None
    
    def from_fp(cls, fp, boundary):
        headers = cls.read_headers(fp)
        return cls(fp, headers, boundary)
    from_fp = classmethod(from_fp)
    
    def read_headers(cls, fp):
        headers = httputil.HeaderMap()
        while True:
            line = fp.readline()
            if not line:
                # No more data--illegal end of headers
                raise EOFError("Illegal end of headers.")
            
            if line == ntob('\r\n'):
                # Normal end of headers
                break
            if not line.endswith(ntob('\r\n')):
                raise ValueError("MIME requires CRLF terminators: %r" % line)
            
            if line[0] in ntob(' \t'):
                # It's a continuation line.
                v = line.strip().decode('ISO-8859-1')
            else:
                k, v = line.split(ntob(":"), 1)
                k = k.strip().decode('ISO-8859-1')
                v = v.strip().decode('ISO-8859-1')
            
            existing = headers.get(k)
            if existing:
                v = ", ".join((existing, v))
            headers[k] = v
        
        return headers
    read_headers = classmethod(read_headers)
    
    def read_lines_to_boundary(self, fp_out=None):
        """Read bytes from self.fp and return or write them to a file.
        
        If the 'fp_out' argument is None (the default), all bytes read are
        returned in a single byte string.
        
        If the 'fp_out' argument is not None, it must be a file-like object that
        supports the 'write' method; all bytes read will be written to the fp,
        and that fp is returned.
        """
        endmarker = self.boundary + ntob("--")
        delim = ntob("")
        prev_lf = True
        lines = []
        seen = 0
        while True:
            line = self.fp.readline(1<<16)
            if not line:
                raise EOFError("Illegal end of multipart body.")
            if line.startswith(ntob("--")) and prev_lf:
                strippedline = line.strip()
                if strippedline == self.boundary:
                    break
                if strippedline == endmarker:
                    self.fp.finish()
                    break
            
            line = delim + line
            
            if line.endswith(ntob("\r\n")):
                delim = ntob("\r\n")
                line = line[:-2]
                prev_lf = True
            elif line.endswith(ntob("\n")):
                delim = ntob("\n")
                line = line[:-1]
                prev_lf = True
            else:
                delim = ntob("")
                prev_lf = False
            
            if fp_out is None:
                lines.append(line)
                seen += len(line)
                if seen > self.maxrambytes:
                    fp_out = self.make_file()
                    for line in lines:
                        fp_out.write(line)
            else:
                fp_out.write(line)
        
        if fp_out is None:
            result = ntob('').join(lines)
            for charset in self.attempt_charsets:
                try:
                    result = result.decode(charset)
                except UnicodeDecodeError:
                    pass
                else:
                    self.charset = charset
                    return result
            else:
                raise cherrypy.HTTPError(
                    400, "The request entity could not be decoded. The following "
                    "charsets were attempted: %s" % repr(self.attempt_charsets))
        else:
            fp_out.seek(0)
            return fp_out
    
    def default_proc(self):
        """Called if a more-specific processor is not found for the ``Content-Type``."""
        if self.filename:
            # Always read into a file if a .filename was given.
            self.file = self.read_into_file()
        else:
            result = self.read_lines_to_boundary()
            if isinstance(result, basestring):
                self.value = result
            else:
                self.file = result
    
    def read_into_file(self, fp_out=None):
        """Read the request body into fp_out (or make_file() if None). Return fp_out."""
        if fp_out is None:
            fp_out = self.make_file()
        self.read_lines_to_boundary(fp_out=fp_out)
        return fp_out

Entity.part_class = Part

try:
    inf = float('inf')
except ValueError:
    # Python 2.4 and lower
    class Infinity(object):
        def __cmp__(self, other):
            return 1
        def __sub__(self, other):
            return self
    inf = Infinity()


comma_separated_headers = ['Accept', 'Accept-Charset', 'Accept-Encoding',
    'Accept-Language', 'Accept-Ranges', 'Allow', 'Cache-Control', 'Connection',
    'Content-Encoding', 'Content-Language', 'Expect', 'If-Match',
    'If-None-Match', 'Pragma', 'Proxy-Authenticate', 'Te', 'Trailer',
    'Transfer-Encoding', 'Upgrade', 'Vary', 'Via', 'Warning', 'Www-Authenticate']


class SizedReader:
    
    def __init__(self, fp, length, maxbytes, bufsize=DEFAULT_BUFFER_SIZE, has_trailers=False):
        # Wrap our fp in a buffer so peek() works
        self.fp = fp
        self.length = length
        self.maxbytes = maxbytes
        self.buffer = ntob('')
        self.bufsize = bufsize
        self.bytes_read = 0
        self.done = False
        self.has_trailers = has_trailers
    
    def read(self, size=None, fp_out=None):
        """Read bytes from the request body and return or write them to a file.
        
        A number of bytes less than or equal to the 'size' argument are read
        off the socket. The actual number of bytes read are tracked in
        self.bytes_read. The number may be smaller than 'size' when 1) the
        client sends fewer bytes, 2) the 'Content-Length' request header
        specifies fewer bytes than requested, or 3) the number of bytes read
        exceeds self.maxbytes (in which case, 413 is raised).
        
        If the 'fp_out' argument is None (the default), all bytes read are
        returned in a single byte string.
        
        If the 'fp_out' argument is not None, it must be a file-like object that
        supports the 'write' method; all bytes read will be written to the fp,
        and None is returned.
        """
        
        if self.length is None:
            if size is None:
                remaining = inf
            else:
                remaining = size
        else:
            remaining = self.length - self.bytes_read
            if size and size < remaining:
                remaining = size
        if remaining == 0:
            self.finish()
            if fp_out is None:
                return ntob('')
            else:
                return None
        
        chunks = []
        
        # Read bytes from the buffer.
        if self.buffer:
            if remaining is inf:
                data = self.buffer
                self.buffer = ntob('')
            else:
                data = self.buffer[:remaining]
                self.buffer = self.buffer[remaining:]
            datalen = len(data)
            remaining -= datalen
            
            # Check lengths.
            self.bytes_read += datalen
            if self.maxbytes and self.bytes_read > self.maxbytes:
                raise cherrypy.HTTPError(413)
            
            # Store the data.
            if fp_out is None:
                chunks.append(data)
            else:
                fp_out.write(data)
        
        # Read bytes from the socket.
        while remaining > 0:
            chunksize = min(remaining, self.bufsize)
            try:
                data = self.fp.read(chunksize)
            except Exception:
                e = sys.exc_info()[1]
                if e.__class__.__name__ == 'MaxSizeExceeded':
                    # Post data is too big
                    raise cherrypy.HTTPError(
                        413, "Maximum request length: %r" % e.args[1])
                else:
                    raise
            if not data:
                self.finish()
                break
            datalen = len(data)
            remaining -= datalen
            
            # Check lengths.
            self.bytes_read += datalen
            if self.maxbytes and self.bytes_read > self.maxbytes:
                raise cherrypy.HTTPError(413)
            
            # Store the data.
            if fp_out is None:
                chunks.append(data)
            else:
                fp_out.write(data)
        
        if fp_out is None:
            return ntob('').join(chunks)
    
    def readline(self, size=None):
        """Read a line from the request body and return it."""
        chunks = []
        while size is None or size > 0:
            chunksize = self.bufsize
            if size is not None and size < self.bufsize:
                chunksize = size
            data = self.read(chunksize)
            if not data:
                break
            pos = data.find(ntob('\n')) + 1
            if pos:
                chunks.append(data[:pos])
                remainder = data[pos:]
                self.buffer += remainder
                self.bytes_read -= len(remainder)
                break
            else:
                chunks.append(data)
        return ntob('').join(chunks)
    
    def readlines(self, sizehint=None):
        """Read lines from the request body and return them."""
        if self.length is not None:
            if sizehint is None:
                sizehint = self.length - self.bytes_read
            else:
                sizehint = min(sizehint, self.length - self.bytes_read)
        
        lines = []
        seen = 0
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
            seen += len(line)
            if seen >= sizehint:
                break
        return lines
    
    def finish(self):
        self.done = True
        if self.has_trailers and hasattr(self.fp, 'read_trailer_lines'):
            self.trailers = {}
            
            try:
                for line in self.fp.read_trailer_lines():
                    if line[0] in ntob(' \t'):
                        # It's a continuation line.
                        v = line.strip()
                    else:
                        try:
                            k, v = line.split(ntob(":"), 1)
                        except ValueError:
                            raise ValueError("Illegal header line.")
                        k = k.strip().title()
                        v = v.strip()
                    
                    if k in comma_separated_headers:
                        existing = self.trailers.get(envname)
                        if existing:
                            v = ntob(", ").join((existing, v))
                    self.trailers[k] = v
            except Exception:
                e = sys.exc_info()[1]
                if e.__class__.__name__ == 'MaxSizeExceeded':
                    # Post data is too big
                    raise cherrypy.HTTPError(
                        413, "Maximum request length: %r" % e.args[1])
                else:
                    raise


class RequestBody(Entity):
    """The entity of the HTTP request."""
    
    bufsize = 8 * 1024
    """The buffer size used when reading the socket."""
    
    # Don't parse the request body at all if the client didn't provide
    # a Content-Type header. See http://www.cherrypy.org/ticket/790
    default_content_type = ''
    """This defines a default ``Content-Type`` to use if no Content-Type header
    is given. The empty string is used for RequestBody, which results in the
    request body not being read or parsed at all. This is by design; a missing
    ``Content-Type`` header in the HTTP request entity is an error at best,
    and a security hole at worst. For multipart parts, however, the MIME spec
    declares that a part with no Content-Type defaults to "text/plain"
    (see :class:`Part<cherrypy._cpreqbody.Part>`).
    """
    
    maxbytes = None
    """Raise ``MaxSizeExceeded`` if more bytes than this are read from the socket."""
    
    def __init__(self, fp, headers, params=None, request_params=None):
        Entity.__init__(self, fp, headers, params)
        
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
        # When no explicit charset parameter is provided by the
        # sender, media subtypes of the "text" type are defined
        # to have a default charset value of "ISO-8859-1" when
        # received via HTTP.
        if self.content_type.value.startswith('text/'):
            for c in ('ISO-8859-1', 'iso-8859-1', 'Latin-1', 'latin-1'):
                if c in self.attempt_charsets:
                    break
            else:
                self.attempt_charsets.append('ISO-8859-1')
        
        # Temporary fix while deprecating passing .parts as .params.
        self.processors['multipart'] = _old_process_multipart
        
        if request_params is None:
            request_params = {}
        self.request_params = request_params
    
    def process(self):
        """Process the request entity based on its Content-Type."""
        # "The presence of a message-body in a request is signaled by the
        # inclusion of a Content-Length or Transfer-Encoding header field in
        # the request's message-headers."
        # It is possible to send a POST request with no body, for example;
        # however, app developers are responsible in that case to set
        # cherrypy.request.process_body to False so this method isn't called.
        h = cherrypy.serving.request.headers
        if 'Content-Length' not in h and 'Transfer-Encoding' not in h:
            raise cherrypy.HTTPError(411)
        
        self.fp = SizedReader(self.fp, self.length,
                              self.maxbytes, bufsize=self.bufsize,
                              has_trailers='Trailer' in h)
        super(RequestBody, self).process()
        
        # Body params should also be a part of the request_params
        # add them in here.
        request_params = self.request_params
        for key, value in self.params.items():
            # Python 2 only: keyword arguments must be byte strings (type 'str').
            if sys.version_info < (3, 0):
                if isinstance(key, unicode):
                    key = key.encode('ISO-8859-1')
            
            if key in request_params:
                if not isinstance(request_params[key], list):
                    request_params[key] = [request_params[key]]
                request_params[key].append(value)
            else:
                request_params[key] = value
