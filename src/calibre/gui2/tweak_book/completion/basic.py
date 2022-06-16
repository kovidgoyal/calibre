#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Event
from collections import namedtuple, OrderedDict

from qt.core import QObject, pyqtSignal, Qt

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.polish.container import OEB_STYLES, name_to_href
from calibre.ebooks.oeb.polish.utils import OEB_FONTS
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.report import description_for_anchor
from calibre.gui2 import is_gui_thread
from calibre.gui2.tweak_book import current_container, editors
from calibre.gui2.tweak_book.completion.utils import control, data, DataError
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.matcher import Matcher
from calibre.utils.icu import numeric_sort_key
from polyglot.builtins import iteritems, itervalues

Request = namedtuple('Request', 'id type data query')

names_cache = {}
file_cache = {}


@control
def clear_caches(cache_type, data_conn):
    global names_cache, file_cache
    if cache_type is None:
        names_cache.clear()
        file_cache.clear()
        return
    if cache_type == 'names':
        names_cache.clear()
    elif cache_type.startswith('file:'):
        name = cache_type.partition(':')[2]
        file_cache.pop(name, None)
        if name.lower().endswith('.opf'):
            names_cache.clear()


@data
def names_data(request_data):
    c = current_container()
    return c.mime_map, {n for n, is_linear in c.spine_names}


@data
def file_data(name):
    'Get the data for name. Returns a unicode string if name is a text document/stylesheet'
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)


def get_data(data_conn, data_type, data=None):
    eintr_retry_call(data_conn.send, Request(None, data_type, data, None))
    result, tb = eintr_retry_call(data_conn.recv)
    if tb:
        raise DataError(tb)
    return result


class Name(str):

    def __new__(self, name, mime_type, spine_names):
        ans = str.__new__(self, name)
        ans.mime_type = mime_type
        ans.in_spine = name in spine_names
        return ans


@control
def complete_names(names_data, data_conn):
    if not names_cache:
        mime_map, spine_names = get_data(data_conn, 'names_data')
        names_cache[None] = all_names = frozenset(Name(name, mt, spine_names) for name, mt in iteritems(mime_map))
        names_cache['text_link'] = frozenset(n for n in all_names if n.in_spine)
        names_cache['stylesheet'] = frozenset(n for n in all_names if n.mime_type in OEB_STYLES)
        names_cache['image'] = frozenset(n for n in all_names if n.mime_type.startswith('image/'))
        names_cache['font'] = frozenset(n for n in all_names if n.mime_type in OEB_FONTS)
        names_cache['css_resource'] = names_cache['image'] | names_cache['font']
        names_cache['descriptions'] = d = {}
        for x, desc in iteritems({'text_link':_('Text'), 'stylesheet':_('Stylesheet'), 'image':_('Image'), 'font':_('Font')}):
            for n in names_cache[x]:
                d[n] = desc
    names_type, base, root = names_data
    quote = (lambda x:x) if base.lower().endswith('.css') else prepare_string_for_xml
    names = names_cache.get(names_type, names_cache[None])
    nmap = {name:name_to_href(name, root, base, quote) for name in names}
    items = tuple(sorted(frozenset(itervalues(nmap)), key=numeric_sort_key))
    d = names_cache['descriptions'].get
    descriptions = {href:d(name) for name, href in iteritems(nmap)}
    return items, descriptions, {}


def create_anchor_map(root):
    ans = {}
    for elem in root.xpath('//*[@id or @name]'):
        anchor = elem.get('id') or elem.get('name')
        if anchor and anchor not in ans:
            ans[anchor] = description_for_anchor(elem)
    return ans


@control
def complete_anchor(name, data_conn):
    if name not in file_cache:
        data = raw = get_data(data_conn, 'file_data', name)
        if isinstance(raw, str):
            try:
                root = parse(raw, decoder=lambda x:x.decode('utf-8'))
            except Exception:
                pass
            else:
                data = (root, create_anchor_map(root))
        file_cache[name] = data
    data = file_cache[name]
    if isinstance(data, tuple) and len(data) > 1 and isinstance(data[1], dict):
        return tuple(sorted(frozenset(data[1]), key=numeric_sort_key)), data[1], {}


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
        self.call.connect(self.run_func, Qt.ConnectionType.QueuedConnection)

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

control_funcs = {name:func for name, func in iteritems(globals()) if getattr(func, 'function_type', None) == 'control'}
data_funcs = {name:func for name, func in iteritems(globals()) if getattr(func, 'function_type', None) == 'data'}
