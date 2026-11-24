#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from collections import OrderedDict
from threading import Event
from typing import TYPE_CHECKING, Literal, NamedTuple, Self, overload

from qt.core import QObject, Qt, pyqtSignal

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.polish.container import OEB_STYLES, name_to_href
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.polish.report import description_for_anchor
from calibre.ebooks.oeb.polish.utils import OEB_FONTS
from calibre.gui2 import is_gui_thread
from calibre.gui2.tweak_book import current_container, editors
from calibre.gui2.tweak_book.completion.utils import DataError, control, data
from calibre.utils.icu import numeric_sort_key
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.localization import _
from calibre.utils.matcher import Matcher

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Mapping, Sequence
    from multiprocessing.connection import Connection, PipeConnection

    AnyConnection = Connection | PipeConnection

    from lxml.etree import _Element

    # The candidate items, their descriptions and extra keyword arguments for the Matcher
    CompletionCandidates = tuple[tuple[str, ...], Mapping[str, str | None], dict[str, object]]
    # The matching items with the positions of the matched characters and the item descriptions
    CompletionAnswer = tuple[Mapping[str, Sequence[int]], Mapping[str, str | None]]


class Request(NamedTuple):
    # The request id is a (request number, file name) pair, see Boss.request_completion()
    id: tuple[int, str] | None
    type: str
    data: object
    query: str | None


names_cache = {}
file_cache = {}


@control
def clear_caches(cache_type: str | None, data_conn: AnyConnection) -> None:
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
def names_data(request_data: object) -> tuple[dict[str, str], set[str]]:
    c = current_container()
    return c.mime_map, {n for n, is_linear in c.spine_names}


@data
def file_data(name: str) -> str | bytes:
    "Get the data for name. Returns a unicode string if name is a text document/stylesheet"
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)


@overload
def get_data(data_conn: AnyConnection, data_type: Literal['names_data'], data: object = None) -> tuple[dict[str, str], set[str]]: ...
@overload
def get_data(data_conn: AnyConnection, data_type: Literal['file_data'], data: object = None) -> str | bytes: ...
def get_data(data_conn: AnyConnection, data_type: str, data: object = None) -> object:
    eintr_retry_call(data_conn.send, Request(None, data_type, data, None))
    result, tb = eintr_retry_call(data_conn.recv)
    if tb:
        raise DataError(tb)
    return result


class Name(str):
    mime_type: str
    in_spine: bool

    def __new__(cls, name: str, mime_type: str, spine_names: Container[str]) -> Self:
        ans = str.__new__(cls, name)
        ans.mime_type = mime_type
        ans.in_spine = name in spine_names
        return ans


@control
def complete_names(names_data: tuple[str | None, str, str], data_conn: AnyConnection) -> CompletionCandidates:
    if not names_cache:
        mime_map, spine_names = get_data(data_conn, 'names_data')
        names_cache[None] = all_names = frozenset(Name(name, mt, spine_names) for name, mt in mime_map.items())
        names_cache['text_link'] = frozenset(n for n in all_names if n.in_spine)
        names_cache['stylesheet'] = frozenset(n for n in all_names if n.mime_type in OEB_STYLES)
        names_cache['image'] = frozenset(n for n in all_names if n.mime_type.startswith('image/'))
        names_cache['font'] = frozenset(n for n in all_names if n.mime_type in OEB_FONTS)
        names_cache['css_resource'] = names_cache['image'] | names_cache['font']
        names_cache['descriptions'] = d = {}
        for x, desc in {
            'text_link': _('Text'),
            'stylesheet': _('Stylesheet'),
            'image': _('Image'),
            'font': _('Font'),
        }.items():
            for n in names_cache[x]:
                d[n] = desc
    names_type, base, root = names_data
    quote = (lambda x: x) if base.lower().endswith('.css') else prepare_string_for_xml
    names = names_cache.get(names_type, names_cache[None])
    nmap = {name: name_to_href(name, root, base, quote) for name in names}
    items = tuple(sorted(frozenset(nmap.values()), key=numeric_sort_key))
    d = names_cache['descriptions'].get
    descriptions = {href: d(name) for name, href in nmap.items()}
    return items, descriptions, {}


def create_anchor_map(root: _Element) -> dict[str, str | None]:
    ans = {}
    for elem in root.xpath('//*[@id or @name]'):
        anchor = elem.get('id') or elem.get('name')
        if anchor and anchor not in ans:
            ans[anchor] = description_for_anchor(elem)
    return ans


@control
def complete_anchor(name: str, data_conn: AnyConnection) -> CompletionCandidates | None:
    if name not in file_cache:
        data = raw = get_data(data_conn, 'file_data', name)
        if isinstance(raw, str):
            try:
                root = parse(raw, decoder=lambda x: x.decode('utf-8'))
            except Exception:
                pass
            else:
                data = (root, create_anchor_map(root))
        file_cache[name] = data
    data = file_cache[name]
    if isinstance(data, tuple) and len(data) > 1 and isinstance(data[1], dict):
        return tuple(sorted(frozenset(data[1]), key=numeric_sort_key)), data[1], {}


_current_matcher = (None, None, None)


def handle_control_request(request: Request, data_conn: AnyConnection) -> CompletionAnswer | None:
    global _current_matcher
    ans = control_funcs[request.type](request.data, data_conn)
    if ans is not None:
        items, descriptions, matcher_kwargs = ans
        fingerprint = hash(items)
        if fingerprint != _current_matcher[0] or matcher_kwargs != _current_matcher[1]:
            _current_matcher = (fingerprint, matcher_kwargs, Matcher(items, **matcher_kwargs))
        matcher = _current_matcher[-1]
        assert matcher is not None
        if request.query:
            items = matcher(request.query, limit=50)
        else:
            items = OrderedDict((i, ()) for i in matcher.items)
        ans = items, descriptions
    return ans


class HandleDataRequest(QObject):
    # Ensure data is obtained in the GUI thread

    call = pyqtSignal(object, object)

    def __init__(self) -> None:
        QObject.__init__(self)
        self.called = Event()
        self.call.connect(self.run_func, Qt.ConnectionType.QueuedConnection)

    def run_func(self, func: Callable[[object], object], data: object) -> None:
        try:
            self.result, self.tb = func(data), None
        except Exception:
            import traceback

            self.result, self.tb = None, traceback.format_exc()
        finally:
            self.called.set()

    def __call__(self, request: Request) -> tuple[object, str | None]:
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

control_funcs = {name: func for name, func in globals().items() if getattr(func, 'function_type', None) == 'control'}
data_funcs = {name: func for name, func in globals().items() if getattr(func, 'function_type', None) == 'data'}
