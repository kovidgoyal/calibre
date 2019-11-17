#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>



from polyglot.builtins import is_py3

if is_py3:
    from http.server import HTTPServer, SimpleHTTPRequestHandler
else:
    from BaseHTTPServer import HTTPServer  # noqa
    from SimpleHTTPServer import SimpleHTTPRequestHandler  # noqa
