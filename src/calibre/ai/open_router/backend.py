#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
import tempfile
from contextlib import closing, suppress
from functools import lru_cache
from threading import Thread
from typing import NamedTuple

from calibre import browser
from calibre.ai import AICapabilities
from calibre.constants import __version__, cache_dir
from calibre.utils.lock import SingleInstance

module_version = 1  # needed for live updates


def get_browser():
    ans = browser(user_agent=f'calibre {__version__}')
    return ans


def singleinstance():
    return SingleInstance('calibre-open-router')


def atomic_write(path, data):
    mode = 'w' if isinstance(data, str) else 'wb'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(mode, delete=False, dir=os.path.dirname(path)) as f:
        f.write(data)
    with singleinstance():
        os.replace(f.name, path)


def atomic_read(path):
    with singleinstance(), open(path, 'rb') as f:
        return f.read()


def download_models_list():
    url = 'https://openrouter.ai/api/v1/models'
    br = get_browser()
    with closing(br.open(url)) as src:
        return src.read()


def update_cached_models_data(cache_loc):
    raw = download_models_list()
    atomic_write(cache_loc, raw)


def schedule_update_of_cached_models_data(cache_loc):
    mtime = 0
    with suppress(OSError):
        mtime = os.path.getmtime(cache_loc)
    modtime = datetime.datetime.fromtimestamp(mtime)
    current_time = datetime.datetime.now()
    if current_time - modtime < datetime.timedelta(days=1):
        return

    Thread(daemon=True, target=update_cached_models_data, args=(cache_loc,)).start()


@lru_cache(2)
def get_available_models():
    cache_loc = os.path.join(cache_dir(), 'openrouter', 'models-v1.json')
    with suppress(OSError):
        data = json.loads(atomic_read(cache_loc))
        schedule_update_of_cached_models_data(cache_loc)
        return parse_models_list(data)
    raw = download_models_list()
    atomic_write(cache_loc, raw)
    return parse_models_list(json.loads(raw))


class Pricing(NamedTuple):
    # Values are in USD per token/request/unit
    input_token: float  # cost per input token
    output_token: float  # cost per output token
    request: float  # per API request
    image: float  # per image
    web_search: float  # per web search
    internal_reasoning: float  # cost per internal reasoning token
    input_cache_read: float  # cost per cached input token read
    input_cache_write: float  # cost per cached input token write

    @classmethod
    def from_dict(cls, x: dict[str, str]) -> 'Pricing':
        return Pricing(
            input_token=float(x['prompt']), output_token=float(x['completion']), request=float(x.get('request', 0)),
            image=float(x.get('image', 0)), web_search=float(x.get('web_search', 0)),
            internal_reasoning=float(x.get('internal_reasoning', 0)),
            input_cache_read=float(x.get('input_cache_read', 0)), input_cache_write=float(x.get('input_cache_write', 0)),
        )


class Model(NamedTuple):
    name: str
    id: str
    created: int
    description: str
    context_length: int
    pricing: Pricing
    parameters: tuple[str, ...]
    is_moderated: bool
    capabilities: AICapabilities
    tokenizer: str

    @classmethod
    def from_dict(cls, x: dict[str, object]) -> 'Model':
        arch = x['architecture']
        capabilities = AICapabilities.none
        if 'text' in arch['input_modalities']:
            if 'text' in arch['output_modalities']:
                capabilities |= AICapabilities.text_to_text
            if 'image' in arch['output_modalities']:
                capabilities |= AICapabilities.text_to_image

        return Model(
            name=x['name'], id=x['id'], created=datetime.datetime.fromtimestamp(x['created'], datetime.timezone.utc),
            description=x['description'], context_length=x['context_length'],
            parameters=tuple(x['supported_parameters']), pricing=Pricing.from_dict(x['pricing']),
            is_moderated=x['top_provider']['is_moderated'], tokenizer=arch['tokenizer'],
            capabilities=capabilities,
        )


def parse_models_list(entries) -> dict[str, Model]:
    ans = {}
    for entry in entries['data']:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


def config_widget():
    from calibre.ai.open_router.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


if __name__ == '__main__':
    from pprint import pprint
    for m in get_available_models().values():
        pprint(m)
