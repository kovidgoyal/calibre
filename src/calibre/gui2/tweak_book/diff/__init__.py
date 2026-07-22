#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>


def load_patience_module():
    from calibre_extensions import _patiencediff_c

    return _patiencediff_c


def get_sequence_matcher():
    return load_patience_module().PatienceSequenceMatcher_c
