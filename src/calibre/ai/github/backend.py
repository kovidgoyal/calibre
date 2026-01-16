#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Any, NamedTuple
from urllib.request import Request

from calibre.ai import AICapabilities, ChatMessage, ChatMessageType, ChatResponse, NoAPIKey, ResultBlocked
from calibre.ai.github import GitHubAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir

module_version = 1  # needed for live updates
MODELS_URL = 'https://models.github.ai/catalog/models'
CHAT_URL = 'https://models.github.ai/inference/chat/completions'
API_VERSION = '2022-11-28'


def pref(key: str, defval: Any = None) -> Any:
    return pref_for_provider(GitHubAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('Personal access token required for GitHub AI')
    return decode_secret(ans)


@lru_cache(2)
def headers() -> tuple[tuple[str, str]]:
    api_key = decoded_api_key()
    return (
        ('Authorization', f'Bearer {api_key}'),
        ('X-GitHub-Api-Version', API_VERSION),
        ('Accept', 'application/vnd.github+json'),
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    # See https://ai.google.dev/api/models#Model
    name: str
    id: str
    url: str
    description: str
    version: str
    context_length: int
    output_token_limit: int
    capabilities: AICapabilities
    thinking: bool
    publisher: str

    @classmethod
    def from_dict(cls, x: dict[str, object]) -> Model:
        mid = x['id']
        caps = AICapabilities.none
        if 'embedding' in x['capabilities'] or 'embeddings' in x['supported_output_modalities']:
            caps |= AICapabilities.embedding
        else:
            input_has_text = x['supported_input_modalities']
            output_has_text = x['supported_output_modalities']
            if input_has_text:
                if output_has_text:
                    caps |= AICapabilities.text_to_text
        return Model(
            name=x['name'], id=mid, description=x.get('summary', ''), version=x['version'],
            context_length=int(x['limits']['max_input_tokens'] or 0), publisher=x['publisher'],
            output_token_limit=int(x['limits']['max_output_tokens'] or 0),
            capabilities=caps, url=x['html_url'], thinking='reasoning' in x['capabilities'],
        )


def parse_models_list(entries: list[dict[str, Any]]) -> dict[str, Model]:
    ans = {}
    for entry in entries:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    cache_loc = os.path.join(cache_dir(), 'ai', f'{GitHubAI.name}-models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL)
    return parse_models_list(json.loads(data))


def find_models_matching_name(name: str) -> Iterator[str]:
    name = name.strip().lower()
    for model in get_available_models().values():
        q = model.name.strip().lower()
        if name in q:
            yield model.id


def config_widget():
    from calibre.ai.github.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name
    return model_id


@lru_cache(2)
def newest_gpt_models() -> dict[str, Model]:
    high, medium, low = [], [], []

    def get_date(model: Model) -> datetime.date:
        try:
            return datetime.date.fromisoformat(model.version)
        except Exception:
            return datetime.date(2000, 1, 1)

    for model in get_available_models().values():
        if model.publisher == 'OpenAI' and '(preview)' not in model.name and (idp := model.id.split('/')[-1].split('-')) and 'gpt' in idp:
            which = high
            if 'mini' in model.id.split('-'):
                which = medium
            elif 'nano' in model.id.split('-'):
                which = low
            which.append(model)
    return {
        'high': sorted(high, key=get_date)[-1],
        'medium': sorted(medium, key=get_date)[-1],
        'low': sorted(low, key=get_date)[-1],
    }


@lru_cache(2)
def model_choice_for_text() -> Model:
    m = newest_gpt_models()
    return m.get(pref('model_strategy', 'medium'), m['medium'])


def chat_request(data: dict[str, Any], model: Model) -> Request:
    data['stream'] = True
    data['stream_options'] = {'include_usage': True}
    return Request(
        CHAT_URL, data=json.dumps(data).encode('utf-8'),
        headers=dict(headers()), method='POST')


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    if self.type not in (ChatMessageType.assistant, ChatMessageType.system, ChatMessageType.user, ChatMessageType.developer):
        raise ValueError(f'Unsupported message type: {self.type}')
    return {'role': self.type.value, 'content': self.query}


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    # See https://docs.github.com/en/rest/models/inference
    content = ''
    for choice in d['choices']:
        content += choice['delta'].get('content', '')
        if (fr := choice['finish_reason']) and fr != 'stop':
            yield ChatResponse(exception=ResultBlocked(custom_message=_('Result was blocked for reason: {}').format(fr)))
            return
    has_metadata = False
    if u := d.get('usage'):
        u  # TODO: implement costing
        has_metadata = True
    if has_metadata or content:
        yield ChatResponse(
            type=ChatMessageType.assistant, content=content, has_metadata=has_metadata, model=model.id, plugin_name=GitHubAI.name)


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # https://docs.github.com/en/rest/models/inference
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    data = {
        'model': model.id,
        'messages': [for_assistant(m) for m in messages],
    }
    rq = chat_request(data, model)
    for datum in read_streaming_response(rq, GitHubAI.name):
        for res in as_chat_responses(datum, model):
            yield res
            if res.exception:
                break


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.github.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


if __name__ == '__main__':
    develop()
