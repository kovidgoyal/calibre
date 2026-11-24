#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from calibre_extensions._patiencediff_c import PatienceSequenceMatcher_c


def load_patience_module() -> ModuleType:
    from calibre_extensions import _patiencediff_c

    return _patiencediff_c


def get_sequence_matcher() -> type[PatienceSequenceMatcher_c]:
    return load_patience_module().PatienceSequenceMatcher_c
