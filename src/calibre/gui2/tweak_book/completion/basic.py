#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Event
from collections import namedtuple, OrderedDict

from PyQt5.Qt import QObject, pyqtSignal, Qt

from calibre.ebooks.oeb.polish.container import OEB_STYLES, OEB_FONTS, name_to_href
from calibre.gui2 import is_gui_thread
from calibre.gui2.tweak_book import current_container
from calibre.gui2.tweak_book.completion.utils import control, data, DataError
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.matcher import Matcher

Request = namedtuple('Request', 'id type data query')

names_cache = {}

@control
def clear_caches(cache_type, data_conn):
    global names_cache
    if cache_type is None or cache_type == 'names':
        names_cache.clear()

@data
def names_data(request_data):
    c = current_container()
    return c.mime_map, {n for n, is_linear in c.spine_names}

def get_data(data_conn, data_type, data=None):
    eintr_retry_call(data_conn.send, Request(None, data_type, data, None))
    result, tb = eintr_retry_call(data_conn.recv)
    if tb:
        raise DataError(tb)
    return result

class Name(unicode):

    def __new__(self, name, mime_type, spine_names):
        ans = unicode.__new__(self, name)
        ans.mime_type = mime_type
        ans.in_spine = name in spine_names
        return ans

@control
def complete_names(names_data, data_conn):
    if not names_cache:
        mime_map, spine_names = get_data(data_conn, 'names_data')
        names_cache[None] = all_names = frozenset(Name(name, mt, spine_names) for name, mt in mime_map.iteritems())
        names_cache['text_link'] = frozenset(n for n in all_names if n.in_spine)
        names_cache['stylesheet'] = frozenset(n for n in all_names if n.mime_type in OEB_STYLES)
        names_cache['image'] = frozenset(n for n in all_names if n.mime_type.startswith('image/'))
        names_cache['font'] = frozenset(n for n in all_names if n.mime_type in OEB_FONTS)
        names_cache['descriptions'] = d = {}
        for x, desc in {'text_link':_('Text'), 'stylesheet':_('Stylesheet'), 'image':_('Image'), 'font':_('Font')}.iteritems():
            for n in names_cache[x]:
                d[n] = desc
    names_type, base, root = names_data
    names = names_cache.get(names_type, names_cache[None])
    nmap = {name:name_to_href(name, root, base) for name in names}
    items = frozenset(nmap.itervalues())
    descriptions = {href:names_cache.get(name) for name, href in nmap.iteritems()}
    return items, descriptions, {}

_current_matcher = (None, None, None)

def handle_control_request(request, data_conn):
    global _current_matcher
    ans = control_funcs[request.type](request.data, data_conn)
    if ans is not None:
        items, descriptions, matcher_kwargs = ans
        fingerprint = hash(items)
        if fingerprint != _current_matcher[0] or matcher_kwargs != _current_matcher[1]:
            _current_matcher = (fingerprint, matcher_kwargs, Matcher(items, **matcher_kwargs))
        if request.query:
            items = _current_matcher[-1](request.query, limit=50)
        else:
            items = OrderedDict((i, ()) for i in _current_matcher[-1].items)
        ans = items, descriptions
    return ans

class HandleDataRequest(QObject):

    # Ensure data is obtained in the GUI thread

    call = pyqtSignal(object, object)

    def __init__(self):
        QObject.__init__(self)
        self.called = Event()
        self.call.connect(self.run_func, Qt.QueuedConnection)

    def run_func(self, func, data):
        try:
            self.result, self.tb = func(data), None
        except Exception:
            import traceback
            self.result, self.tb = None, traceback.format_exc()
        finally:
            self.called.set()

    def __call__(self, request):
        func = data_funcs[request.type]
        if is_gui_thread():
            try:
                return func(request.data), None
            except Exception:
                import traceback
                return None, traceback.format_exc()
        self.called.clear()
        self.call.emit(func, request.data)
        self.called.wait()
        try:
            return self.result, self.tb
        finally:
            del self.result, self.tb
handle_data_request = HandleDataRequest()

control_funcs = {name:func for name, func in globals().iteritems() if getattr(func, 'function_type', None) == 'control'}
data_funcs = {name:func for name, func in globals().iteritems() if getattr(func, 'function_type', None) == 'data'}
