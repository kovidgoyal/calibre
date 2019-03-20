#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import

from polyglot.builtins import is_py3

if is_py3:
    from urllib.request import (build_opener, getproxies, install_opener,  # noqa
            HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPDigestAuthHandler,  # noqa
            url2pathname, urlopen, Request)  # noqa
    from urllib.parse import (parse_qs, quote, unquote, quote_plus, urldefrag,  # noqa
            urlencode, urljoin, urlparse, urlunparse, urlsplit, urlunsplit)  # noqa
    from urllib.error import HTTPError, URLError  # noqa
else:
    from urllib import (getproxies, quote, unquote, quote_plus, url2pathname,  # noqa
            urlencode)  # noqa
    from urllib2 import (build_opener, install_opener, HTTPBasicAuthHandler,  # noqa
            HTTPCookieProcessor, HTTPDigestAuthHandler, HTTPError, URLError,  # noqa
            urlopen, Request)  # noqa
    from urlparse import (parse_qs, urldefrag, urljoin, urlparse, urlunparse,  # noqa
            urlsplit, urlunsplit)  # noqa
