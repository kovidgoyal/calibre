import struct
import time

import cherrypy
from cherrypy._cpcompat import basestring, BytesIO, ntob, set, unicodestr
from cherrypy.lib import file_generator
from cherrypy.lib import set_vary_header


def decode(encoding=None, default_encoding='utf-8'):
    """Replace or extend the list of charsets used to decode a request entity.
    
    Either argument may be a single string or a list of strings.
    
    encoding
        If not None, restricts the set of charsets attempted while decoding
        a request entity to the given set (even if a different charset is given in
        the Content-Type request header).
    
    default_encoding
        Only in effect if the 'encoding' argument is not given.
        If given, the set of charsets attempted while decoding a request entity is
        *extended* with the given value(s).
    
    """
    body = cherrypy.request.body
    if encoding is not None:
        if not isinstance(encoding, list):
            encoding = [encoding]
        body.attempt_charsets = encoding
    elif default_encoding:
        if not isinstance(default_encoding, list):
            default_encoding = [default_encoding]
        body.attempt_charsets = body.attempt_charsets + default_encoding


class ResponseEncoder:
    
    default_encoding = 'utf-8'
    failmsg = "Response body could not be encoded with %r."
    encoding = None
    errors = 'strict'
    text_only = True
    add_charset = True
    debug = False
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        
        self.attempted_charsets = set()
        request = cherrypy.serving.request
        if request.handler is not None:
            # Replace request.handler with self
            if self.debug:
                cherrypy.log('Replacing request.handler', 'TOOLS.ENCODE')
            self.oldhandler = request.handler
            request.handler = self
    
    def encode_stream(self, encoding):
        """Encode a streaming response body.
        
        Use a generator wrapper, and just pray it works as the stream is
        being written out.
        """
        if encoding in self.attempted_charsets:
            return False
        self.attempted_charsets.add(encoding)
        
        def encoder(body):
            for chunk in body:
                if isinstance(chunk, unicodestr):
                    chunk = chunk.encode(encoding, self.errors)
                yield chunk
        self.body = encoder(self.body)
        return True
    
    def encode_string(self, encoding):
        """Encode a buffered response body."""
        if encoding in self.attempted_charsets:
            return False
        self.attempted_charsets.add(encoding)
        
        try:
            body = []
            for chunk in self.body:
                if isinstance(chunk, unicodestr):
                    chunk = chunk.encode(encoding, self.errors)
                body.append(chunk)
            self.body = body
        except (LookupError, UnicodeError):
            return False
        else:
            return True
    
    def find_acceptable_charset(self):
        request = cherrypy.serving.request
        response = cherrypy.serving.response
        
        if self.debug:
            cherrypy.log('response.stream %r' % response.stream, 'TOOLS.ENCODE')
        if response.stream:
            encoder = self.encode_stream
        else:
            encoder = self.encode_string
            if "Content-Length" in response.headers:
                # Delete Content-Length header so finalize() recalcs it.
                # Encoded strings may be of different lengths from their
                # unicode equivalents, and even from each other. For example:
                # >>> t = u"\u7007\u3040"
                # >>> len(t)
                # 2
                # >>> len(t.encode("UTF-8"))
                # 6
                # >>> len(t.encode("utf7"))
                # 8
                del response.headers["Content-Length"]
        
        # Parse the Accept-Charset request header, and try to provide one
        # of the requested charsets (in order of user preference).
        encs = request.headers.elements('Accept-Charset')
        charsets = [enc.value.lower() for enc in encs]
        if self.debug:
            cherrypy.log('charsets %s' % repr(charsets), 'TOOLS.ENCODE')
        
        if self.encoding is not None:
            # If specified, force this encoding to be used, or fail.
            encoding = self.encoding.lower()
            if self.debug:
                cherrypy.log('Specified encoding %r' % encoding, 'TOOLS.ENCODE')
            if (not charsets) or "*" in charsets or encoding in charsets:
                if self.debug:
                    cherrypy.log('Attempting encoding %r' % encoding, 'TOOLS.ENCODE')
                if encoder(encoding):
                    return encoding
        else:
            if not encs:
                if self.debug:
                    cherrypy.log('Attempting default encoding %r' %
                                 self.default_encoding, 'TOOLS.ENCODE')
                # Any character-set is acceptable.
                if encoder(self.default_encoding):
                    return self.default_encoding
                else:
                    raise cherrypy.HTTPError(500, self.failmsg % self.default_encoding)
            else:
                for element in encs:
                    if element.qvalue > 0:
                        if element.value == "*":
                            # Matches any charset. Try our default.
                            if self.debug:
                                cherrypy.log('Attempting default encoding due '
                                             'to %r' % element, 'TOOLS.ENCODE')
                            if encoder(self.default_encoding):
                                return self.default_encoding
                        else:
                            encoding = element.value
                            if self.debug:
                                cherrypy.log('Attempting encoding %s (qvalue >'
                                             '0)' % element, 'TOOLS.ENCODE')
                            if encoder(encoding):
                                return encoding
                
                if "*" not in charsets:
                    # If no "*" is present in an Accept-Charset field, then all
                    # character sets not explicitly mentioned get a quality
                    # value of 0, except for ISO-8859-1, which gets a quality
                    # value of 1 if not explicitly mentioned.
                    iso = 'iso-8859-1'
                    if iso not in charsets:
                        if self.debug:
                            cherrypy.log('Attempting ISO-8859-1 encoding',
                                         'TOOLS.ENCODE')
                        if encoder(iso):
                            return iso
        
        # No suitable encoding found.
        ac = request.headers.get('Accept-Charset')
        if ac is None:
            msg = "Your client did not send an Accept-Charset header."
        else:
            msg = "Your client sent this Accept-Charset header: %s." % ac
        msg += " We tried these charsets: %s." % ", ".join(self.attempted_charsets)
        raise cherrypy.HTTPError(406, msg)
    
    def __call__(self, *args, **kwargs):
        response = cherrypy.serving.response
        self.body = self.oldhandler(*args, **kwargs)
        
        if isinstance(self.body, basestring):
            # strings get wrapped in a list because iterating over a single
            # item list is much faster than iterating over every character
            # in a long string.
            if self.body:
                self.body = [self.body]
            else:
                # [''] doesn't evaluate to False, so replace it with [].
                self.body = []
        elif hasattr(self.body, 'read'):
            self.body = file_generator(self.body)
        elif self.body is None:
            self.body = []
        
        ct = response.headers.elements("Content-Type")
        if self.debug:
            cherrypy.log('Content-Type: %r' % [str(h) for h in ct], 'TOOLS.ENCODE')
        if ct:
            ct = ct[0]
            if self.text_only:
                if ct.value.lower().startswith("text/"):
                    if self.debug:
                        cherrypy.log('Content-Type %s starts with "text/"' % ct,
                                     'TOOLS.ENCODE')
                    do_find = True
                else:
                    if self.debug:
                        cherrypy.log('Not finding because Content-Type %s does '
                                     'not start with "text/"' % ct,
                                     'TOOLS.ENCODE')
                    do_find = False
            else:
                if self.debug:
                    cherrypy.log('Finding because not text_only', 'TOOLS.ENCODE')
                do_find = True
            
            if do_find:
                # Set "charset=..." param on response Content-Type header
                ct.params['charset'] = self.find_acceptable_charset()
                if self.add_charset:
                    if self.debug:
                        cherrypy.log('Setting Content-Type %s' % ct,
                                     'TOOLS.ENCODE')
                    response.headers["Content-Type"] = str(ct)
        
        return self.body

# GZIP

def compress(body, compress_level):
    """Compress 'body' at the given compress_level."""
    import zlib
    
    # See http://www.gzip.org/zlib/rfc-gzip.html
    yield ntob('\x1f\x8b')       # ID1 and ID2: gzip marker
    yield ntob('\x08')           # CM: compression method
    yield ntob('\x00')           # FLG: none set
    # MTIME: 4 bytes
    yield struct.pack("<L", int(time.time()) & int('FFFFFFFF', 16))
    yield ntob('\x02')           # XFL: max compression, slowest algo
    yield ntob('\xff')           # OS: unknown
    
    crc = zlib.crc32(ntob(""))
    size = 0
    zobj = zlib.compressobj(compress_level,
                            zlib.DEFLATED, -zlib.MAX_WBITS,
                            zlib.DEF_MEM_LEVEL, 0)
    for line in body:
        size += len(line)
        crc = zlib.crc32(line, crc)
        yield zobj.compress(line)
    yield zobj.flush()
    
    # CRC32: 4 bytes
    yield struct.pack("<L", crc & int('FFFFFFFF', 16))
    # ISIZE: 4 bytes
    yield struct.pack("<L", size & int('FFFFFFFF', 16))

def decompress(body):
    import gzip
    
    zbuf = BytesIO()
    zbuf.write(body)
    zbuf.seek(0)
    zfile = gzip.GzipFile(mode='rb', fileobj=zbuf)
    data = zfile.read()
    zfile.close()
    return data


def gzip(compress_level=5, mime_types=['text/html', 'text/plain'], debug=False):
    """Try to gzip the response body if Content-Type in mime_types.
    
    cherrypy.response.headers['Content-Type'] must be set to one of the
    values in the mime_types arg before calling this function.

    The provided list of mime-types must be of one of the following form:
        * type/subtype
        * type/*
        * type/*+subtype
    
    No compression is performed if any of the following hold:
        * The client sends no Accept-Encoding request header
        * No 'gzip' or 'x-gzip' is present in the Accept-Encoding header
        * No 'gzip' or 'x-gzip' with a qvalue > 0 is present
        * The 'identity' value is given with a qvalue > 0.
    
    """
    request = cherrypy.serving.request
    response = cherrypy.serving.response
    
    set_vary_header(response, "Accept-Encoding")
    
    if not response.body:
        # Response body is empty (might be a 304 for instance)
        if debug:
            cherrypy.log('No response body', context='TOOLS.GZIP')
        return
    
    # If returning cached content (which should already have been gzipped),
    # don't re-zip.
    if getattr(request, "cached", False):
        if debug:
            cherrypy.log('Not gzipping cached response', context='TOOLS.GZIP')
        return
    
    acceptable = request.headers.elements('Accept-Encoding')
    if not acceptable:
        # If no Accept-Encoding field is present in a request,
        # the server MAY assume that the client will accept any
        # content coding. In this case, if "identity" is one of
        # the available content-codings, then the server SHOULD use
        # the "identity" content-coding, unless it has additional
        # information that a different content-coding is meaningful
        # to the client.
        if debug:
            cherrypy.log('No Accept-Encoding', context='TOOLS.GZIP')
        return
    
    ct = response.headers.get('Content-Type', '').split(';')[0]
    for coding in acceptable:
        if coding.value == 'identity' and coding.qvalue != 0:
            if debug:
                cherrypy.log('Non-zero identity qvalue: %s' % coding,
                             context='TOOLS.GZIP')
            return
        if coding.value in ('gzip', 'x-gzip'):
            if coding.qvalue == 0:
                if debug:
                    cherrypy.log('Zero gzip qvalue: %s' % coding,
                                 context='TOOLS.GZIP')
                return
            
            if ct not in mime_types:
                # If the list of provided mime-types contains tokens
                # such as 'text/*' or 'application/*+xml',
                # we go through them and find the most appropriate one
                # based on the given content-type.
                # The pattern matching is only caring about the most
                # common cases, as stated above, and doesn't support
                # for extra parameters.
                found = False
                if '/' in ct:
                    ct_media_type, ct_sub_type = ct.split('/')
                    for mime_type in mime_types:
                        if '/' in mime_type:
                            media_type, sub_type = mime_type.split('/')
                            if ct_media_type == media_type:
                                if sub_type == '*':
                                    found = True
                                    break
                                elif '+' in sub_type and '+' in ct_sub_type:
                                    ct_left, ct_right = ct_sub_type.split('+')
                                    left, right = sub_type.split('+')
                                    if left == '*' and ct_right == right:
                                        found = True
                                        break

                if not found:
                    if debug:
                        cherrypy.log('Content-Type %s not in mime_types %r' %
                                     (ct, mime_types), context='TOOLS.GZIP')
                    return
            
            if debug:
                cherrypy.log('Gzipping', context='TOOLS.GZIP')
            # Return a generator that compresses the page
            response.headers['Content-Encoding'] = 'gzip'
            response.body = compress(response.body, compress_level)
            if "Content-Length" in response.headers:
                # Delete Content-Length header so finalize() recalcs it.
                del response.headers["Content-Length"]
            
            return
    
    if debug:
        cherrypy.log('No acceptable encoding found.', context='GZIP')
    cherrypy.HTTPError(406, "identity, gzip").set_response()

