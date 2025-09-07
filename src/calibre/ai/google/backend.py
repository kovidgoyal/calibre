#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
from functools import lru_cache
from typing import Any, NamedTuple

from calibre.ai import NoAPIKey
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import get_cached_resource
from calibre.constants import cache_dir

module_version = 1  # needed for live updates
MODELS_URL = 'https://generativelanguage.googleapis.com/v1beta/models'


def pref(key: str, defval: Any = None) -> Any:
    from calibre.ai.google import GoogleAI
    return pref_for_provider(GoogleAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for Google AI')
    return decode_secret(ans)


@lru_cache(2)
def get_available_models() -> dict[str, 'Model']:
    api_key = decoded_api_key()
    cache_loc = os.path.join(cache_dir(), 'google-ai', 'models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL, headers=(('X-goog-api-key', api_key),))
    return parse_models_list(json.loads(data)['models'])


class Model(NamedTuple):
    pass


def parse_models_list(models: list[dict[str, Any]]) -> dict[str, Model]:
    pass


def config_widget():
    from calibre.ai.google.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()
