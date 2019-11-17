#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>



from polyglot.builtins import is_py3

if is_py3:
    from urllib.request import (build_opener, getproxies, install_opener,  # noqa
            HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPDigestAuthHandler,  # noqa
            url2pathname, urlopen, Request)  # noqa
    from urllib.parse import (parse_qs, quote, unquote as uq, quote_plus, urldefrag,  # noqa
            urlencode, urljoin, urlparse, urlunparse, urlsplit, urlunsplit)  # noqa
    from urllib.error import HTTPError, URLError  # noqa

    def unquote(x, encoding='utf-8', errors='replace'):
        binary = isinstance(x, bytes)
        if binary:
            x = x.decode(encoding, errors)
        ans = uq(x, encoding, errors)
        if binary:
            ans = ans.encode(encoding, errors)
        return ans

else:
    from urllib import (getproxies, quote, unquote as uq, quote_plus, url2pathname,  # noqa
            urlencode)  # noqa
    from urllib2 import (build_opener, install_opener, HTTPBasicAuthHandler,  # noqa
            HTTPCookieProcessor, HTTPDigestAuthHandler, HTTPError, URLError,  # noqa
            urlopen, Request)  # noqa
    from urlparse import (parse_qs, urldefrag, urljoin, urlparse, urlunparse,  # noqa
            urlsplit, urlunsplit)  # noqa

    def unquote(x, encoding='utf-8', errors='replace'):
        # unquote must run on a bytestring and will return a bytestring
        # If it runs on a unicode object, it returns a double encoded unicode
        # string: unquote(u'%C3%A4') != unquote(b'%C3%A4').decode('utf-8')
        # and the latter is correct
        binary = isinstance(x, bytes)
        if not binary:
            x = x.encode(encoding, errors)
        ans = uq(x)
        if not binary:
            ans = ans.decode(encoding, errors)
        return ans


def unquote_plus(x, encoding='utf-8', errors='replace'):
    q, repl = (b'+', b' ') if isinstance(x, bytes) else ('+', ' ')
    x = x.replace(q, repl)
    return unquote(x, encoding=encoding, errors=errors)
