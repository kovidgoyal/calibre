#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType


def module_for_cmd(cmd: str) -> ModuleType:
    return importlib.import_module('calibre.db.cli.cmd_' + cmd)


def integers_from_string(arg: str, include_last_inrange: bool = False) -> Iterator[int]:
    for x in arg.split(','):
        y = tuple(map(int, x.split('-')))
        if len(y) > 1:
            yield from range(y[0], y[1] + int(bool(include_last_inrange)))
        else:
            yield y[0]
