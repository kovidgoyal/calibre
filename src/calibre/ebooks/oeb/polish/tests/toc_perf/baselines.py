#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Wall-time baseline recorder for L-scale TOC perf (no ratio asserts).'''

from __future__ import annotations

import json
import os
import time
from typing import Any

from calibre.ebooks.oeb.polish.tests.base import get_cache

BASELINE_NAME = 'toc_perf_baselines.json'


def baselines_path() -> str:
    # Prefer package-local file when writable; else cache artifact
    pkg = os.path.join(os.path.dirname(__file__), 'baselines.json')
    if os.access(os.path.dirname(pkg), os.W_OK):
        return pkg
    return os.path.join(get_cache(), 'toc_perf', BASELINE_NAME)


def load_baselines() -> dict[str, Any]:
    path = baselines_path()
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def record_baseline(key: str, seconds: float, meta: dict[str, Any] | None = None) -> str:
    data = load_baselines()
    entry: dict[str, Any] = {'seconds': seconds, 'recorded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if meta:
        entry['meta'] = meta
    data[key] = entry
    path = baselines_path()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')
    return path
