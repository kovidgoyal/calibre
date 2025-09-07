#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
import re
import sys
from collections.abc import Iterable, Iterator
from functools import lru_cache
from pprint import pprint
from typing import Any, NamedTuple
from urllib.request import Request

from calibre.ai import AICapabilities, ChatMessage, ChatMessageType, ChatResponse, NoFreeModels
from calibre.ai.prefs import pref_for_provider
from calibre.ai.utils import StreamedResponseAccumulator, chat_with_error_handler, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir
from polyglot.binary import from_hex_unicode

module_version = 1  # needed for live updates
MODELS_URL = 'https://openrouter.ai/api/v1/models'


def pref(key: str, defval: Any = None) -> Any:
    from calibre.ai.open_router import OpenRouterAI
    return pref_for_provider(OpenRouterAI.name, key, defval)


@lru_cache(2)
def get_available_models() -> dict[str, 'Model']:
    cache_loc = os.path.join(cache_dir(), 'openrouter', 'models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL)
    return parse_models_list(json.loads(data))


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name_without_creator_preserving_case
    return model_id


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
        return self.name_without_creator_preserving_case.lower()

    @property
    def name_without_creator_preserving_case(self) -> str:
        return re.sub(r' \(free\)$', '', self.name.partition(':')[-1].strip()).strip()

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


def parse_models_list(entries: dict[str, Any]) -> dict[str, Model]:
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
    match pref('model_choice_strategy', 'free-or-paid'):
        case 'free-or-paid':
            yield from free_model_choice_for_text(allow_paid=True)
        case 'free-only':
            yield from free_model_choice_for_text(allow_paid=False)
        case _:
            yield get_available_models()['openrouter/auto']


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
    }
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    if use_model:
        models = ()
        model_id = use_model
    else:
        models = tuple(model_choice_for_text())
        if not models:
            models = (get_available_models()['openrouter/auto'],)
        model_id = models[0].id
    data_collection = pref('data_collection', 'deny')
    if data_collection not in ('allow', 'deny'):
        data_collection = 'deny'
    data = {
        'model': model_id,
        'messages': [m.for_assistant() for m in messages],
        'usage': {'include': True},
        'stream': True,
        'reasoning': {'enabled': True},
        'provider': {'data_collection': data_collection},
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

    for data in read_streaming_response(rq):
        for choice in data['choices']:
            d = choice['delta']
            c = d.get('content') or ''
            r = d.get('reasoning') or ''
            rd = d.get('reasoning_details') or ()
            role = d.get('role') or 'assistant'
            if c or r or rd:
                yield ChatResponse(content=c, reasoning=r, reasoning_details=rd, type=ChatMessageType(role))
        if u := data.get('usage'):
            yield ChatResponse(
                cost=float(u['cost'] or 0), currency=_('credits'), provider=data.get('provider') or '',
                model=data.get('model') or '', has_metadata=True,
            )


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = ''):
    # calibre-debug -c 'from calibre.ai.open_router.backend import *; develop()'
    acc = StreamedResponseAccumulator()
    messages = [
        ChatMessage(type=ChatMessageType.system, query='You are William Shakespeare.'),
        ChatMessage('Give me twenty lines on my supremely beautiful wife.')
    ]
    for x in text_chat(messages, use_model):
        if x.exception:
            if x.error_details:
                print(x.error_details, file=sys.stderr)
            raise SystemExit(str(x.exception))
        acc.accumulate(x)
        if x.content:
            print(end=x.content, flush=True)
    acc.finalize()
    print()
    if acc.all_reasoning:
        print('Reasoning:')
        print(acc.all_reasoning)
    print()
    if acc.metadata.has_metadata:
        x = acc.metadata
        print(f'\nCost: {x.cost} {x.currency} Provider: {x.provider!r} Model: {x.model!r}')
    messages.extend(acc.messages)
    print('Messages:')
    for msg in messages:
        pprint(msg.for_assistant())


if __name__ == '__main__':
    develop()
