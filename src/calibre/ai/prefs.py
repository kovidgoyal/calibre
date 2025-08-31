#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from copy import deepcopy
from functools import lru_cache
from typing import Any

from calibre.utils.config import JSONConfig


@lru_cache(2)
def prefs() -> JSONConfig:
    ans = JSONConfig('ai')
    ans.defaults['providers'] = {}
    ans.defaults['purpose_map'] = {}
    return ans


def pref_for_provider(name: str, key: str, defval: Any = None) -> Any:
    return prefs()['providers'].get(key, defval)


def set_prefs_for_provider(name: str, pref_map: dict[str, Any]) -> None:
    p = prefs()
    p['providers'][name] = deepcopy(pref_map)
    p.set('providers', p['providers'])
