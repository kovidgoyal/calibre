#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from operator import attrgetter
from typing import Any, NamedTuple
from urllib.request import Request

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, NoAPIKey, PromptBlocked
from calibre.ai.openai import OpenAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir

module_version = 1  # needed for live updates
MODELS_URL = 'https://api.openai.com/v1/models'
CHAT_URL = 'https://api.openai.com/v1/responses'


def pref(key: str, defval: Any = None) -> Any:
    return pref_for_provider(OpenAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for OpenAI')
    return decode_secret(ans)


@lru_cache(2)
def headers() -> tuple[tuple[str, str]]:
    api_key = decoded_api_key()
    return (
        ('Authorization', f'Bearer {api_key}'),
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    # See https://platform.openai.com/docs/api-reference/models/retrieve
    id: str
    id_parts: Sequence[str, ...]
    created: datetime.datetime
    version: float

    @classmethod
    def from_dict(cls, x: dict[str, object]) -> 'Model':
        id_parts = tuple(x['id'].split('-'))
        try:
            version = float(id_parts[1])
        except Exception:
            version = 0
        return Model(id=x['id'], created=datetime.datetime.fromtimestamp(x['created'], datetime.timezone.utc), id_parts=id_parts, version=version)

    @property
    def is_preview(self) -> bool:
        return 'preview' in self.id_parts


def parse_models_list(entries: list[dict[str, Any]]) -> dict[str, Model]:
    ans = {}
    for entry in entries:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    api_key = decoded_api_key()
    cache_loc = os.path.join(cache_dir(), 'ai', f'{OpenAI.name}-models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL, headers=(('Authorization', f'Bearer {api_key}'),))
    return parse_models_list(json.loads(data)['data'])


def find_models_matching_name(name: str) -> Iterator[str]:
    name = name.strip().lower()
    for model in get_available_models().values():
        q = model.name.strip().lower()
        if name in q:
            yield model.id


def config_widget():
    from calibre.ai.openai.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    return model_id


@lru_cache(2)
def newest_gpt_models() -> dict[str, Model]:
    high, medium, low = [], [], []
    for model in get_available_models().values():
        if model.id_parts[0] == 'gpt' and len(model.id_parts) > 1:
            which = high
            if 'mini' in model.id.split('-'):
                which = medium
            elif 'nano' in model.id.split('-'):
                which = low
            elif len(model.id_parts) == 2:
                which = high
            which.append(model)
    return {
        'high': sorted(high, key=attrgetter('created'))[-1],
        'medium': sorted(medium, key=attrgetter('created'))[-1],
        'low': sorted(low, key=attrgetter('created'))[-1],
    }


@lru_cache(2)
def model_choice_for_text() -> Model:
    m = newest_gpt_models()
    return m.get(pref('model_strategy', 'medium'), m['medium'])


def reasoning_effort():
    return {
            'none': 'minimal', 'auto': 'medium', 'low': 'low', 'medium': 'medium', 'high': 'high'
    }.get(pref('reasoning_strategy', 'auto'), 'medium')


def chat_request(data: dict[str, Any], model: Model) -> Request:
    # See https://platform.openai.com/docs/api-reference/responses/create
    data['model'] = model.id
    data['stream'] = True
    if pref('allow_web_searches', True):
        data.setdefault('tools', []).append({'type': 'web_search'})
    data['reasoning'] = {
        'effort': reasoning_effort(),
        'summary': 'auto'
    }
    return Request(
        CHAT_URL, data=json.dumps(data).encode('utf-8'),
        headers=dict(headers()), method='POST')


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    if self.type not in (ChatMessageType.assistant, ChatMessageType.system, ChatMessageType.user, ChatMessageType.developer):
        raise ValueError(f'Unsupported message type: {self.type}')
    return {'role': self.type.value, 'content': self.query}


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    # See https://platform.openai.com/docs/api-reference/responses/object
    print(1111111111, d)
    if True:
        return
    content = ''
    for choice in d['choices']:
        content += choice['delta'].get('content', '')
        if (fr := choice['finish_reason']) and fr != 'stop':
            yield ChatResponse(exception=PromptBlocked(custom_message=_('Result was blocked for reason: {}').format(fr)))
            return
    has_metadata = False
    if u := d.get('usage'):
        u  # TODO: implement costing
        has_metadata = True
    if has_metadata or content:
        yield ChatResponse(
            id=d['id'],
            type=ChatMessageType.assistant, content=content, has_metadata=has_metadata, model=model.id, plugin_name=OpenAI.name)


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # See https://platform.openai.com/docs/guides/text?api-mode=responses
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    previous_response_id = ''
    messages = mcon = tuple(messages)
    for i, m in enumerate(reversed(messages)):
        if m.response_id:
            previous_response_id = m.response_id
            idx = len(mcon) - 1 - i
            messages = mcon[idx:]
            break
    data = {
        'input': [for_assistant(m) for m in messages],
    }
    if previous_response_id:
        data['previous_response_id'] = previous_response_id
    rq = chat_request(data, model)
    for datum in read_streaming_response(rq, OpenAI.name):
        for res in as_chat_responses(datum, model):
            yield res
            if res.exception:
                break


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.openai.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


if __name__ == '__main__':
    develop()
