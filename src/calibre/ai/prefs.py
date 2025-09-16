#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Iterator
from copy import deepcopy
from functools import lru_cache
from typing import Any

from calibre.ai import AICapabilities
from calibre.customize import AIProviderPlugin
from calibre.customize.ui import available_ai_provider_plugins
from calibre.utils.config import JSONConfig
from calibre.utils.icu import primary_sort_key
from polyglot.binary import as_hex_unicode, from_hex_unicode


@lru_cache(2)
def prefs() -> JSONConfig:
    ans = JSONConfig('ai', permissions=0o600)  # make readable only by user as it stores secrets
    ans.defaults['providers'] = {}
    ans.defaults['purpose_map'] = {}
    return ans


def pref_for_provider(name: str, key: str, defval: Any = None) -> Any:
    try:
        return prefs()['providers'][name][key]
    except Exception:
        return defval


def set_prefs_for_provider(name: str, pref_map: dict[str, Any]) -> None:
    p = prefs()
    p['providers'][name] = deepcopy(pref_map)
    p.set('providers', p['providers'])


def plugins_for_purpose(purpose: AICapabilities) -> Iterator[AIProviderPlugin]:
    for p in sorted(available_ai_provider_plugins(), key=lambda p: primary_sort_key(p.name)):
        if p.capabilities & purpose == purpose:
            yield p


def plugin_for_purpose(purpose: AICapabilities) -> AIProviderPlugin | None:
    compatible_plugins = {p.name: p for p in plugins_for_purpose(purpose)}
    q = prefs()['purpose_map'].get(purpose.purpose, '')
    if ans := compatible_plugins.get(q):
        return ans
    if compatible_plugins:
        from calibre.ai.google import GoogleAI
        # Prefer Google for text to text as it give us 1500 free web searches per day
        if purpose == AICapabilities.text_to_text:
            for name, p in compatible_plugins.items():
                if name == GoogleAI.name:
                    return p
        return next(iter(compatible_plugins.values()))
    return None


def encode_secret(text: str) -> str:
    return as_hex_unicode(text)


def decode_secret(text: str) -> str:
    return from_hex_unicode(text)
