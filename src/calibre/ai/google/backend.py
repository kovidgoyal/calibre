#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Google studio account management: https://aistudio.google.com/usage

# Docs:
# Text generation: https://ai.google.dev/gemini-api/docs/text-generation#rest
# Image generation with gemini: https://ai.google.dev/gemini-api/docs/image-generation#rest
# Image generation with imagen: https://ai.google.dev/gemini-api/docs/imagen#rest
# TTS: https://ai.google.dev/gemini-api/docs/speech-generation#rest

import json
import os
from functools import lru_cache
from typing import Any, NamedTuple

from calibre.ai import AICapabilities, NoAPIKey
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
    return parse_models_list(json.loads(data))


class Model(NamedTuple):
    name: str
    id: str
    description: str
    version: str
    context_length: int
    output_token_limit: int
    capabilities: AICapabilities
    family: str
    family_version: float

    @classmethod
    def from_dict(cls, x: dict[str, object]) -> 'Model':
        caps = AICapabilities.text_to_text
        mid = x['name']
        if 'embedContent' in x['supportedGenerationMethods']:
            caps |= AICapabilities.embedding
        family, family_version = '', 0
        name_parts = mid.split('-')
        if len(name_parts) > 1:
            family, fv = name_parts[:2]
            try:
                family_version = float(fv)
            except Exception:
                family = ''
        match family:
            case 'imagen':
                caps |= AICapabilities.text_to_image
            case 'gemini':
                if family_version >= 2.5:
                    caps |= AICapabilities.text_and_image_to_image
                if 'tts' in name_parts:
                    caps |= AICapabilities.tts
        return Model(
            name=x['displayName'], id=mid, description=x.get('description', ''), version=x['version'],
            context_length=int(x['inputTokenLimit']), output_token_limit=int(x['outputTokenLimit']),
            capabilities=caps, family=family, family_version=family_version,
        )


def parse_models_list(entries: list[dict[str, Any]]) -> dict[str, Model]:
    ans = {}
    for entry in entries['models']:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


def config_widget():
    from calibre.ai.google.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


def develop():
    from pprint import pprint
    # calibre-debug -c 'from calibre.ai.google.backend import develop; develop()'
    for model in get_available_models().values():
        pprint(model)


if __name__ == '__main__':
    develop()
