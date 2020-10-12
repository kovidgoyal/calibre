#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import QKeySequence, QMainWindow, Qt


def get_main_window_for(widget):
    p = widget
    while p is not None:
        if isinstance(p, QMainWindow):
            return p
        p = p.parent()


def index_to_key_sequence(idx):
    mods = []
    for i, x in enumerate(('ALT', 'CTRL', 'META', 'SHIFT')):
        if idx[i] == 'y':
            mods.append(x.capitalize())
    mods.append(idx[4:])
    return QKeySequence('+'.join(mods))


def key_to_text(key):
    return QKeySequence(key).toString(QKeySequence.PortableText).lower()


def ev_to_index(ev):
    m = ev.modifiers()
    mods = []
    for x in ('ALT', 'CTRL', 'META', 'SHIFT'):
        mods.append('y' if m & getattr(Qt, x) else 'n')
    return ''.join(mods) + key_to_text(ev.key())


def get_shortcut_for(widget, ev):
    mw = get_main_window_for(widget)
    if mw is None:
        return
    smap = mw.web_view.shortcut_map
    idx = ev_to_index(ev)
    return smap.get(idx)
