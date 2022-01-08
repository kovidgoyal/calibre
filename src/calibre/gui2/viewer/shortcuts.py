#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QKeySequence, QMainWindow, Qt


key_name_to_qt_name = {
    'ArrowRight': 'Right',
    'ArrowLeft': 'Left',
    'ArrowUp': 'Up',
    'ArrowDown': 'Down',
    'PageUp': 'PgUp',
    'PageDown': 'PgDown',
}


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
    key = idx[4:]
    mods.append(key_name_to_qt_name.get(key, key))
    return QKeySequence('+'.join(mods))


def key_to_text(key):
    return QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText).lower()


def ev_to_index(ev):
    m = ev.modifiers()
    mods = []
    for x in (
            Qt.KeyboardModifier.AltModifier, Qt.KeyboardModifier.ControlModifier,
            Qt.KeyboardModifier.MetaModifier, Qt.KeyboardModifier.ShiftModifier):
        mods.append('y' if m & x else 'n')
    return ''.join(mods) + key_to_text(ev.key())


def get_shortcut_for(widget, ev):
    mw = get_main_window_for(widget)
    if mw is None:
        return
    smap = mw.web_view.shortcut_map
    idx = ev_to_index(ev)
    return smap.get(idx)
