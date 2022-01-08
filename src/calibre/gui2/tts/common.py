#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from enum import Enum, auto


class EventType(Enum):
    mark = auto()
    begin = auto()
    end = auto()
    cancel = auto()
    pause = auto()
    resume = auto()


class Event:

    def __init__(self, etype, data=None):
        self.type = etype
        self.data = data

    def __repr__(self):
        return f'Event(type={self.type}, data={self.data})'


def add_markup(text_parts, mark_template, escape_marked_text, chunk_size=0):
    buf = []
    size = 0
    for x in text_parts:
        if isinstance(x, int):
            item = mark_template.format(x)
        else:
            item = escape_marked_text(x)
        sz = len(item)
        if chunk_size and size + sz > chunk_size:
            yield ''.join(buf).strip()
            size = 0
            buf = []
        size += sz
        buf.append(item)
    if size:
        yield ''.join(buf).strip()
