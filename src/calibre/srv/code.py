#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import re
from functools import partial
from threading import Lock

from calibre.srv.routes import endpoint

html_cache = {}
cache_lock = Lock()
autoreload_js = None

def get_html(name, auto_reload_port, **replacements):
    global autoreload_js
    key = (name, auto_reload_port, tuple(replacements.iteritems()))
    with cache_lock:
        try:
            return html_cache[key]
        except KeyError:
            with lopen(P(name), 'rb') as f:
                raw = f.read()
            for k, val in key[-1]:
                if isinstance(val, type('')):
                    val = val.encode('utf-8')
                if isinstance(k, type('')):
                    k = k.encode('utf-8')
                raw = raw.replace(k, val)
            if auto_reload_port > 0:
                if autoreload_js is None:
                    autoreload_js = P('content-server/autoreload.js', data=True, allow_user_override=False).replace(
                        b'AUTORELOAD_PORT', bytes(str(auto_reload_port)))
                raw = re.sub(
                    br'(<\s*/\s*head\s*>)', br'<script type="text/javascript">%s</script>\1' % autoreload_js,
                    raw, flags=re.IGNORECASE)
            html_cache[key] = raw
            return raw

@endpoint('', auth_required=False)
def index(ctx, rd):
    return rd.generate_static_output('/', partial(
        get_html, 'content-server/index.html', getattr(rd.opts, 'auto_reload_port', 0),
        ENTRY_POINT='book list', LOADING_MSG=_('Loading library, please wait')))
