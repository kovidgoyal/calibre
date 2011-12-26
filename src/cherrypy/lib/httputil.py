"""HTTP library functions.

This module contains functions for building an HTTP application
framework: any one, not just one whose name starts with "Ch". ;) If you
reference any modules from some popular framework inside *this* module,
FuManChu will personally hang you up by your thumbs and submit you
to a public caning.
"""

from binascii import b2a_base64
from cherrypy._cpcompat import BaseHTTPRequestHandler, HTTPDate, ntob, ntou, reversed, sorted
from cherrypy._cpcompat import basestring, bytestr, iteritems, nativestr, unicodestr, unquote_qs
response_codes = BaseHTTPRequestHandler.responses.copy()

# From http://www.cherrypy.org/ticket/361
response_codes[500] = ('Internal Server Error',
                      'The server encountered an unexpected condition '
                      'which prevented it from fulfilling the request.')
response_codes[503] = ('Service Unavailable',
                      'The server is currently unable to handle the '
                      'request due to a temporary overloading or '
                      'maintenance of the server.')

import re
import urllib



def urljoin(*atoms):
    """Return the given path \*atoms, joined into a single URL.
    
    This will correctly join a SCRIPT_NAME and PATH_INFO into the
    original URL, even if either atom is blank.
    """
    url = "/".join([x for x in atoms if x])
    while "//" in url:
        url = url.replace("//", "/")
    # Special-case the final url of "", and return "/" instead.
    return url or "/"

def urljoin_bytes(*atoms):
    """Return the given path *atoms, joined into a single URL.
    
    This will correctly join a SCRIPT_NAME and PATH_INFO into the
    original URL, even if either atom is blank.
    """
    url = ntob("/").join([x for x in atoms if x])
    while ntob("//") in url:
        url = url.replace(ntob("//"), ntob("/"))
    # Special-case the final url of "", and return "/" instead.
    return url or ntob("/")

def protocol_from_http(protocol_str):
    """Return a protocol tuple from the given 'HTTP/x.y' string."""
    return int(protocol_str[5]), int(protocol_str[7])

def get_ranges(headervalue, content_length):
    """Return a list of (start, stop) indices from a Range header, or None.
    
    Each (start, stop) tuple will be composed of two ints, which are suitable
    for use in a slicing operation. That is, the header "Range: bytes=3-6",
    if applied against a Python string, is requesting resource[3:7]. This
    function will return the list [(3, 7)].
    
    If this function returns an empty list, you should return HTTP 416.
    """
    
    if not headervalue:
        return None
    
    result = []
    bytesunit, byteranges = headervalue.split("=", 1)
    for brange in byteranges.split(","):
        start, stop = [x.strip() for x in brange.split("-", 1)]
        if start:
            if not stop:
                stop = content_length - 1
            start, stop = int(start), int(stop)
            if start >= content_length:
                # From rfc 2616 sec 14.16:
                # "If the server receives a request (other than one
                # including an If-Range request-header field) with an
                # unsatisfiable Range request-header field (that is,
                # all of whose byte-range-spec values have a first-byte-pos
                # value greater than the current length of the selected
                # resource), it SHOULD return a response code of 416
                # (Requested range not satisfiable)."
                continue
            if stop < start:
                # From rfc 2616 sec 14.16:
                # "If the server ignores a byte-range-spec because it
                # is syntactically invalid, the server SHOULD treat
                # the request as if the invalid Range header field
                # did not exist. (Normally, this means return a 200
                # response containing the full entity)."
                return None
            result.append((start, stop + 1))
        else:
            if not stop:
                # See rfc quote above.
                return None
            # Negative subscript (last N bytes)
            result.append((content_length - int(stop), content_length))
    
    return result


class HeaderElement(object):
    """An element (with parameters) from an HTTP header's element list."""
    
    def __init__(self, value, params=None):
        self.value = value
        if params is None:
            params = {}
        self.params = params
    
    def __cmp__(self, other):
        return cmp(self.value, other.value)
    
    def __lt__(self, other):
        return self.value < other.value
    
    def __str__(self):
        p = [";%s=%s" % (k, v) for k, v in iteritems(self.params)]
        return "%s%s" % (self.value, "".join(p))
    
    def __bytes__(self):
        return ntob(self.__str__())

    def __unicode__(self):
        return ntou(self.__str__())
    
    def parse(elementstr):
        """Transform 'token;key=val' to ('token', {'key': 'val'})."""
        # Split the element into a value and parameters. The 'value' may
        # be of the form, "token=token", but we don't split that here.
        atoms = [x.strip() for x in elementstr.split(";") if x.strip()]
        if not atoms:
            initial_value = ''
        else:
            initial_value = atoms.pop(0).strip()
        params = {}
        for atom in atoms:
            atom = [x.strip() for x in atom.split("=", 1) if x.strip()]
            key = atom.pop(0)
            if atom:
                val = atom[0]
            else:
                val = ""
            params[key] = val
        return initial_value, params
    parse = staticmethod(parse)
    
    def from_str(cls, elementstr):
        """Construct an instance from a string of the form 'token;key=val'."""
        ival, params = cls.parse(elementstr)
        return cls(ival, params)
    from_str = classmethod(from_str)


q_separator = re.compile(r'; *q *=')

class AcceptElement(HeaderElement):
    """An element (with parameters) from an Accept* header's element list.
    
    AcceptElement objects are comparable; the more-preferred object will be
    "less than" the less-preferred object. They are also therefore sortable;
    if you sort a list of AcceptElement objects, they will be listed in
    priority order; the most preferred value will be first. Yes, it should
    have been the other way around, but it's too late to fix now.
    """
    
    def from_str(cls, elementstr):
        qvalue = None
        # The first "q" parameter (if any) separates the initial
        # media-range parameter(s) (if any) from the accept-params.
        atoms = q_separator.split(elementstr, 1)
        media_range = atoms.pop(0).strip()
        if atoms:
            # The qvalue for an Accept header can have extensions. The other
            # headers cannot, but it's easier to parse them as if they did.
            qvalue = HeaderElement.from_str(atoms[0].strip())
        
        media_type, params = cls.parse(media_range)
        if qvalue is not None:
            params["q"] = qvalue
        return cls(media_type, params)
    from_str = classmethod(from_str)
    
    def qvalue(self):
        val = self.params.get("q", "1")
        if isinstance(val, HeaderElement):
            val = val.value
        return float(val)
    qvalue = property(qvalue, doc="The qvalue, or priority, of this value.")
    
    def __cmp__(self, other):
        diff = cmp(self.qvalue, other.qvalue)
        if diff == 0:
            diff = cmp(str(self), str(other))
        return diff
    
    def __lt__(self, other):
        if self.qvalue == other.qvalue:
            return str(self) < str(other)
        else:
            return self.qvalue < other.qvalue


def header_elements(fieldname, fieldvalue):
    """Return a sorted HeaderElement list from a comma-separated header string."""
    if not fieldvalue:
        return []
    
    result = []
    for element in fieldvalue.split(","):
        if fieldname.startswith("Accept") or fieldname == 'TE':
            hv = AcceptElement.from_str(element)
        else:
            hv = HeaderElement.from_str(element)
        result.append(hv)
    
    return list(reversed(sorted(result)))

def decode_TEXT(value):
    r"""Decode :rfc:`2047` TEXT (e.g. "=?utf-8?q?f=C3=BCr?=" -> "f\xfcr")."""
    try:
        # Python 3
        from email.header import decode_header
    except ImportError:
        from email.Header import decode_header
    atoms = decode_header(value)
    decodedvalue = ""
    for atom, charset in atoms:
        if charset is not None:
            atom = atom.decode(charset)
        decodedvalue += atom
    return decodedvalue

def valid_status(status):
    """Return legal HTTP status Code, Reason-phrase and Message.
    
    The status arg must be an int, or a str that begins with an int.
    
    If status is an int, or a str and no reason-phrase is supplied,
    a default reason-phrase will be provided.
    """
    
    if not status:
        status = 200
    
    status = str(status)
    parts = status.split(" ", 1)
    if len(parts) == 1:
        # No reason supplied.
        code, = parts
        reason = None
    else:
        code, reason = parts
        reason = reason.strip()
    
    try:
        code = int(code)
    except ValueError:
        raise ValueError("Illegal response status from server "
                         "(%s is non-numeric)." % repr(code))
    
    if code < 100 or code > 599:
        raise ValueError("Illegal response status from server "
                         "(%s is out of range)." % repr(code))
    
    if code not in response_codes:
        # code is unknown but not illegal
        default_reason, message = "", ""
    else:
        default_reason, message = response_codes[code]
    
    if reason is None:
        reason = default_reason
    
    return code, reason, message


# NOTE: the parse_qs functions that follow are modified version of those
# in the python3.0 source - we need to pass through an encoding to the unquote
# method, but the default parse_qs function doesn't allow us to.  These do.

def _parse_qs(qs, keep_blank_values=0, strict_parsing=0, encoding='utf-8'):
    """Parse a query given as a string argument.
    
    Arguments:
    
    qs: URL-encoded query string to be parsed
    
    keep_blank_values: flag indicating whether blank values in
        URL encoded queries should be treated as blank strings.  A
        true value indicates that blanks should be retained as blank
        strings.  The default false value indicates that blank values
        are to be ignored and treated as if they were  not included.
    
    strict_parsing: flag indicating what to do with parsing errors. If
        false (the default), errors are silently ignored. If true,
        errors raise a ValueError exception.
    
    Returns a dict, as G-d intended.
    """
    pairs = [s2 for s1 in qs.split('&') for s2 in s1.split(';')]
    d = {}
    for name_value in pairs:
        if not name_value and not strict_parsing:
            continue
        nv = name_value.split('=', 1)
        if len(nv) != 2:
            if strict_parsing:
                raise ValueError("bad query field: %r" % (name_value,))
            # Handle case of a control-name with no equal sign
            if keep_blank_values:
                nv.append('')
            else:
                continue
        if len(nv[1]) or keep_blank_values:
            name = unquote_qs(nv[0], encoding)
            value = unquote_qs(nv[1], encoding)
            if name in d:
                if not isinstance(d[name], list):
                    d[name] = [d[name]]
                d[name].append(value)
            else:
                d[name] = value
    return d


image_map_pattern = re.compile(r"[0-9]+,[0-9]+")

def parse_query_string(query_string, keep_blank_values=True, encoding='utf-8'):
    """Build a params dictionary from a query_string.
    
    Duplicate key/value pairs in the provided query_string will be
    returned as {'key': [val1, val2, ...]}. Single key/values will
    be returned as strings: {'key': 'value'}.
    """
    if image_map_pattern.match(query_string):
        # Server-side image map. Map the coords to 'x' and 'y'
        # (like CGI::Request does).
        pm = query_string.split(",")
        pm = {'x': int(pm[0]), 'y': int(pm[1])}
    else:
        pm = _parse_qs(query_string, keep_blank_values, encoding=encoding)
    return pm


class CaseInsensitiveDict(dict):
    """A case-insensitive dict subclass.
    
    Each key is changed on entry to str(key).title().
    """
    
    def __getitem__(self, key):
        return dict.__getitem__(self, str(key).title())
    
    def __setitem__(self, key, value):
        dict.__setitem__(self, str(key).title(), value)
    
    def __delitem__(self, key):
        dict.__delitem__(self, str(key).title())
    
    def __contains__(self, key):
        return dict.__contains__(self, str(key).title())
    
    def get(self, key, default=None):
        return dict.get(self, str(key).title(), default)
    
    if hasattr({}, 'has_key'):
        def has_key(self, key):
            return dict.has_key(self, str(key).title())
    
    def update(self, E):
        for k in E.keys():
            self[str(k).title()] = E[k]
    
    def fromkeys(cls, seq, value=None):
        newdict = cls()
        for k in seq:
            newdict[str(k).title()] = value
        return newdict
    fromkeys = classmethod(fromkeys)
    
    def setdefault(self, key, x=None):
        key = str(key).title()
        try:
            return self[key]
        except KeyError:
            self[key] = x
            return x
    
    def pop(self, key, default):
        return dict.pop(self, str(key).title(), default)


#   TEXT = <any OCTET except CTLs, but including LWS>
#
# A CRLF is allowed in the definition of TEXT only as part of a header
# field continuation. It is expected that the folding LWS will be
# replaced with a single SP before interpretation of the TEXT value."
if nativestr == bytestr:
    header_translate_table = ''.join([chr(i) for i in xrange(256)])
    header_translate_deletechars = ''.join([chr(i) for i in xrange(32)]) + chr(127)
else:
    header_translate_table = None
    header_translate_deletechars = bytes(range(32)) + bytes([127])


class HeaderMap(CaseInsensitiveDict):
    """A dict subclass for HTTP request and response headers.
    
    Each key is changed on entry to str(key).title(). This allows headers
    to be case-insensitive and avoid duplicates.
    
    Values are header values (decoded according to :rfc:`2047` if necessary).
    """
    
    protocol=(1, 1)
    encodings = ["ISO-8859-1"]
    
    # Someday, when http-bis is done, this will probably get dropped
    # since few servers, clients, or intermediaries do it. But until then,
    # we're going to obey the spec as is.
    # "Words of *TEXT MAY contain characters from character sets other than
    # ISO-8859-1 only when encoded according to the rules of RFC 2047."
    use_rfc_2047 = True
    
    def elements(self, key):
        """Return a sorted list of HeaderElements for the given header."""
        key = str(key).title()
        value = self.get(key)
        return header_elements(key, value)
    
    def values(self, key):
        """Return a sorted list of HeaderElement.value for the given header."""
        return [e.value for e in self.elements(key)]
    
    def output(self):
        """Transform self into a list of (name, value) tuples."""
        header_list = []
        for k, v in self.items():
            if isinstance(k, unicodestr):
                k = self.encode(k)
            
            if not isinstance(v, basestring):
                v = str(v)
            
            if isinstance(v, unicodestr):
                v = self.encode(v)
            
            # See header_translate_* constants above.
            # Replace only if you really know what you're doing.
            k = k.translate(header_translate_table, header_translate_deletechars)
            v = v.translate(header_translate_table, header_translate_deletechars)
            
            header_list.append((k, v))
        return header_list
    
    def encode(self, v):
        """Return the given header name or value, encoded for HTTP output."""
        for enc in self.encodings:
            try:
                return v.encode(enc)
            except UnicodeEncodeError:
                continue
        
        if self.protocol == (1, 1) and self.use_rfc_2047:
            # Encode RFC-2047 TEXT 
            # (e.g. u"\u8200" -> "=?utf-8?b?6IiA?="). 
            # We do our own here instead of using the email module
            # because we never want to fold lines--folding has
            # been deprecated by the HTTP working group.
            v = b2a_base64(v.encode('utf-8'))
            return (ntob('=?utf-8?b?') + v.strip(ntob('\n')) + ntob('?='))
        
        raise ValueError("Could not encode header part %r using "
                         "any of the encodings %r." %
                         (v, self.encodings))


class Host(object):
    """An internet address.
    
    name
        Should be the client's host name. If not available (because no DNS
        lookup is performed), the IP address should be used instead.
    
    """
    
    ip = "0.0.0.0"
    port = 80
    name = "unknown.tld"
    
    def __init__(self, ip, port, name=None):
        self.ip = ip
        self.port = port
        if name is None:
            name = ip
        self.name = name
    
    def __repr__(self):
        return "httputil.Host(%r, %r, %r)" % (self.ip, self.port, self.name)
