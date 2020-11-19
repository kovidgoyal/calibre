#!/usr/bin/env python
# vim:fileencoding=utf-8
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
