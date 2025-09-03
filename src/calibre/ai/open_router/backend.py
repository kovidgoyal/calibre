#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import http
import json
import os
import sys
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import closing, suppress
from functools import lru_cache
from threading import Thread
from typing import Any, NamedTuple
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from calibre import browser, get_proxies
from calibre.ai import AICapabilities, ChatMessage, ChatMessageType, ChatResponse, NoFreeModels
from calibre.ai.open_router import OpenRouterAI
from calibre.ai.prefs import pref_for_provider
from calibre.constants import __version__, cache_dir
from calibre.utils.lock import SingleInstance
from polyglot.binary import from_hex_unicode

module_version = 1  # needed for live updates


def pref(key: str, defval: Any = None) -> Any:
    return pref_for_provider(OpenRouterAI.name, key, defval)


def user_agent() -> str:
    return f'calibre {__version__}'


def get_browser():
    ans = browser(user_agent=user_agent())
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
def get_available_models() -> dict[str, 'Model']:
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

    @property
    def is_free(self) -> bool:
        return max(self) == 0


class Model(NamedTuple):
    name: str
    id: str
    slug: str
    created: int
    description: str
    context_length: int
    pricing: Pricing
    parameters: tuple[str, ...]
    is_moderated: bool
    capabilities: AICapabilities
    tokenizer: str

    @property
    def creator(self) -> str:
        return self.name.partition(':')[0].lower()

    @property
    def family(self) -> str:
        parts = self.name.split(':')
        if len(parts) > 1:
            return parts[1].strip().partition(' ')[0].lower()
        return ''

    @property
    def name_without_creator(self) -> str:
        return self.name.partition(':')[-1].lower().strip()

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
            description=x['description'], context_length=x['context_length'], slug=x['canonical_slug'],
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


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


@lru_cache(2)
def free_model_choice_for_text(allow_paid: bool = False) -> tuple[Model, ...]:
    gemini_free, gemini_paid = [], []
    deep_seek_free, deep_seek_paid = [], []
    gpt5_free, gpt5_paid = [], []
    gpt_oss_free, gpt_oss_paid = [], []
    opus_free, opus_paid = [], []

    def only_newest(models: list[Model]) -> tuple[Model, ...]:
        if models:
            models.sort(key=lambda m: m.created, reverse=True)
            return (models[0],)
        return ()

    def only_cheapest(models: list[Model]) -> tuple[Model, ...]:
        if models:
            models.sort(key=lambda m: m.pricing.output_token)
            return (models[0],)
        return ()

    for model in get_available_models().values():
        if AICapabilities.text_to_text not in model.capabilities:
            continue
        match model.creator:
            case 'google':
                if model.family == 'gemini':
                    gemini_free.append(model) if model.pricing.is_free else gemini_paid.append(model)
            case 'deepseek':
                deep_seek_free.append(model) if model.pricing.is_free else deep_seek_paid.append(model)
            case 'openai':
                n = model.name_without_creator
                if n.startswith('gpt-5'):
                    gpt5_free.append(model) if model.pricing.is_free else gpt5_paid.append(model)
                elif n.startswith('gpt-oss'):
                    gpt_oss_free.append(model) if model.pricing.is_free else gpt_oss_paid.append(model)
            case 'anthropic':
                if model.family == 'opus':
                    opus_free.append(model) if model.pricing.is_free else opus_paid.append(model)
    free = only_newest(gemini_free) + only_newest(gpt5_free) + only_newest(gpt_oss_free) + only_newest(opus_free) + only_newest(deep_seek_free)
    if free:
        return free
    if not allow_paid:
        raise NoFreeModels(_('No free models were found for text to text generation'))
    return only_cheapest(gemini_paid) + only_cheapest(gpt5_paid) + only_cheapest(opus_paid) + only_cheapest(deep_seek_paid)


def model_choice_for_text() -> Iterator[Model, ...]:
    model_id, model_name = pref('text_model', ('', ''))
    if m := get_available_models().get(model_id):
        yield m
        return
    match pref('model_choice_strategy', 'free'):
        case 'free-or-paid':
            yield from free_model_choice_for_text(allow_paid=True)
        case 'free-only':
            yield from free_model_choice_for_text(allow_paid=False)
        case _:
            yield get_available_models()['openrouter/auto']


def opener():
    proxies = get_proxies(debug=False)
    proxy_handler = ProxyHandler(proxies)
    return build_opener(proxy_handler)


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise ValueError('API key required for OpenRouter')
    return from_hex_unicode(ans)


def chat_request(data: dict[str, Any], url='https://openrouter.ai/api/v1/chat/completions') -> Request:
    headers = {
        'Authorization': f'Bearer {decoded_api_key()}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://calibre-ebook.com',
        'X-Title': 'calibre',
        'User-agent': user_agent(),
    }
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def text_chat_implementation(messages: Iterable[ChatMessage]) -> Iterator[ChatResponse]:
    models = tuple(model_choice_for_text())
    if not models:
        models = (get_available_models()['openrouter/auto'],)
    data = {
        'model': models[0].id,
        'messages': [m.for_assistant() for m in messages],
        'usage': {'include': True},
        'stream': True,
        'reasoning': {'enabled': True},
    }
    if len(models) > 1:
        data['models'] = [m.id for m in models[1:]]
    s = pref('reasoning_strategy')
    match s:
        case 'low' | 'medium' | 'high':
            data['reasoning']['effort'] = s
        case _:
            data['reasoning']['enabled'] = False
    rq = chat_request(data)

    def read_response(buffer: str) -> Iterator[ChatResponse]:
        if not buffer.startswith('data: '):
            return
        buffer = buffer[6:].rstrip()
        if buffer == '[DONE]':
            return
        data = json.loads(buffer)
        for choice in data['choices']:
            d = choice['delta']
            c = d.get('content') or ''
            r = d.get('reasoning') or ''
            role = d.get('role') or 'assistant'
            if c or r:
                yield ChatResponse(content=c, reasoning=r, type=ChatMessageType(role))
        if u := data.get('usage'):
            yield ChatResponse(
                cost=float(u['cost'] or 0), currency=_('credits'), provider=data.get('provider') or '',
                model=data.get('model') or '', has_metadata=True,
            )

    with opener().open(rq) as response:
        if response.status != http.HTTPStatus.OK:
            raise Exception(f'OpenRouter API failed with status code: {response.status} and body: {response.read().decode("utf-8", "replace")}')
        buffer = ''
        for raw_line in response:
            line = raw_line.decode('utf-8')
            if line.strip() == '':
                if buffer:
                    yield from read_response(buffer)
                    buffer = ''
            else:
                buffer += line
        yield from read_response(buffer)


def text_chat(messages: Iterable[ChatMessage]) -> Iterator[ChatResponse]:
    try:
        yield from text_chat_implementation(messages)
    except HTTPError as e:
        try:
            details = e.fp.read().decode()
        except Exception:
            details = ''
        yield ChatResponse(exception=e, error_details=details)
    except Exception as e:
        import traceback
        yield ChatResponse(exception=e, error_details=traceback.format_exc())


def develop():
    for x in text_chat((ChatMessage(type=ChatMessageType.system, query='You are William Shakespeare.'),
                        ChatMessage('Give me twenty lines on my supremely beautiful wife.'))):
        if x.exception:
            if x.error_details:
                print(x.error_details, file=sys.stderr)
            raise SystemExit(str(x.exception))
        if x.content:
            print(end=x.content, flush=True)
        if x.has_metadata:
            print(f'\nCost: {x.cost} {x.currency} Provider: {x.provider} Model: {x.model}')


if __name__ == '__main__':
    from pprint import pprint
    for m in get_available_models().values():
        pprint(m)
