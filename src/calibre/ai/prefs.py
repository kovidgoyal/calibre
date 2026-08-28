#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from calibre.ai import AICapabilities
from calibre.customize import AIProviderPlugin
from calibre.customize.ui import available_ai_provider_plugins
from calibre.utils.config import JSONConfig
from calibre.utils.icu import primary_sort_key
from polyglot.binary import as_hex_unicode, from_hex_unicode

if TYPE_CHECKING:
    from unittest.suite import TestSuite
else:
    TestSuite = object


@lru_cache(2)
def prefs() -> JSONConfig:
    ans = JSONConfig('ai', permissions=0o600)  # make readable only by user as it stores secrets
    ans.defaults['providers'] = {}
    ans.defaults['purpose_map'] = {}
    ans.defaults['llm_localized_results'] = 'never'
    return ans


_overrides = threading.local()


@contextmanager
def override_prefs_for_providers(overrides: dict[str, dict[str, Any]]) -> Iterator[None]:
    # Temporarily shadow stored provider preferences with the specified
    # per-provider values, in the calling thread only. Keys absent from the
    # override map fall through to the stored preferences, so that secrets
    # such as api_key can be shared while model choice, reasoning effort,
    # etc. are scoped to a particular feature. Must be entered in every
    # thread that reads preferences, in particular worker threads that make
    # AI requests.
    prev = getattr(_overrides, 'map', None)
    _overrides.map = overrides
    try:
        yield
    finally:
        _overrides.map = prev


def pref_for_provider(name: str, key: str, defval: Any = None) -> Any:  # noqa: ANN401
    overrides = getattr(_overrides, 'map', None)
    if overrides is not None:
        try:
            return overrides[name][key]
        except KeyError:
            pass
    try:
        return prefs()['providers'][name][key]
    except Exception:
        return defval


def set_prefs_for_provider(name: str, pref_map: dict[str, Any]) -> None:
    p = prefs()
    p['providers'][name] = deepcopy(pref_map)
    p.set('providers', p['providers'])


def update_prefs_for_provider(name: str, pref_map: dict[str, Any]) -> None:
    # Merge the specified preferences into those stored for the provider,
    # leaving other stored preferences untouched.
    p = prefs()
    providers = p['providers']
    providers.setdefault(name, {}).update(deepcopy(pref_map))
    p.set('providers', providers)


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


def find_tests() -> TestSuite:  # {{{
    import tempfile
    import unittest
    from unittest.mock import patch

    class TestAIPrefs(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def test_ai_prefs_overrides(self) -> None:
            name = 'TestOnlyFakeProvider'
            with tempfile.TemporaryDirectory() as tdir:
                p = JSONConfig('ai-test', base_path=tdir)
                p.defaults['providers'] = {}
                with patch('calibre.ai.prefs.prefs', return_value=p):
                    set_prefs_for_provider(name, {'api_key': 'k', 'model': 'm'})
                    self.ae(pref_for_provider(name, 'model'), 'm')
                    with override_prefs_for_providers({name: {'model': 'q'}}):
                        self.ae(pref_for_provider(name, 'model'), 'q')
                        self.ae(pref_for_provider(name, 'api_key'), 'k', 'keys absent from the overrides must fall through to stored prefs')
                        self.ae(pref_for_provider(name, 'missing', 7), 7)
                        self.ae(pref_for_provider('OtherProvider', 'model', 'd'), 'd')
                        seen = {}

                        def worker() -> None:
                            seen['model'] = pref_for_provider(name, 'model')

                        t = threading.Thread(target=worker)
                        t.start()
                        t.join()
                        self.ae(seen['model'], 'm', 'the overrides must apply only in the thread that set them')
                    self.ae(pref_for_provider(name, 'model'), 'm')
                    with self.assertRaises(RuntimeError), override_prefs_for_providers({name: {'model': 'q'}}):
                        raise RuntimeError('boom')
                    self.ae(pref_for_provider(name, 'model'), 'm', 'the overrides must be removed even when an exception is raised')

                    update_prefs_for_provider(name, {'api_key': 'k2'})
                    self.ae(pref_for_provider(name, 'api_key'), 'k2')
                    self.ae(pref_for_provider(name, 'model'), 'm', 'updating prefs must not clobber other stored prefs')
                    update_prefs_for_provider('NewProvider', {'api_key': 'nk'})
                    self.ae(pref_for_provider('NewProvider', 'api_key'), 'nk')

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAIPrefs)


# }}}
