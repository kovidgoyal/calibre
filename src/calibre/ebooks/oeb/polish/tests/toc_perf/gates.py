#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Call-count / expectedFailure helpers for TOC perf gates.'''

from __future__ import annotations

import os
import unittest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def gates_forced() -> bool:
    return os.environ.get('CALIBRE_TOC_PERF_GATES', '').strip() in {'1', 'true', 'yes'}


def gates_enabled(feature: str) -> bool:
    '''Return True when hard call-count asserts for *feature* should run.

    Features: ``a1``, ``b1``, ``b2``, ``a2``.
    Default: a1 enabled (product lands with corpus PR); b1/b2/a2 off unless
    CALIBRE_TOC_PERF_GATES=1 or the feature-specific env is set.
    '''
    if gates_forced():
        return True
    specific = os.environ.get(f'CALIBRE_TOC_PERF_GATE_{feature.upper()}', '').strip()
    if specific in {'1', 'true', 'yes'}:
        return True
    if specific in {'0', 'false', 'no'}:
        return False
    # Defaults after product PRs land in-tree; corpus-only red path uses xfail when False
    return feature == 'a1'


def maybe_expected_failure(feature: str) -> Callable[[Callable], Callable]:
    '''Decorator: expectedFailure when the feature gate is not yet enabled.'''

    def deco(fn: Callable) -> Callable:
        if gates_enabled(feature):
            return fn
        return unittest.expectedFailure(fn)

    return deco


def case_sensitive_fs(path: str) -> bool:
    '''True if the filesystem containing *path* is case-sensitive.'''
    base = os.path.abspath(path)
    os.makedirs(base, exist_ok=True)
    probe = os.path.join(base, 'TocPerfCaseProbe')
    other = os.path.join(base, 'tocperfcaseprobe')
    try:
        with open(probe, 'w') as f:
            f.write('x')
        return not os.path.exists(other)
    finally:
        try:
            os.remove(probe)
        except OSError:
            pass
