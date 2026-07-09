#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
from collections.abc import Iterable, Iterator
from contextlib import suppress
from functools import lru_cache
from typing import Any, NamedTuple
from urllib.error import HTTPError
from urllib.request import Request

from calibre.ai import AICapabilities, ChatMessage, ChatMessageType, ChatResponse, NoAPIKey, ResultBlocked
from calibre.ai.github import GitHubAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir

module_version = 2  # needed for live updates
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


def resolve_model(model_ref: str) -> Model | None:
    text = str(model_ref or '').strip()
    if not text:
        return None
    models = get_available_models()
    if m := models.get(text):
        return m
    lower_text = text.lower()
    for model_id, model in models.items():
        if model_id.lower() == lower_text or model.name.strip().lower() == lower_text:
            return model
    if '/' not in text:
        if m := models.get('openai/' + text):
            return m
    for match in find_models_matching_name(text):
        if m := models.get(match):
            return m
    return None


def configured_text_model() -> Model | None:
    raw = pref('text_model')
    candidates: tuple[str, ...]
    if isinstance(raw, dict):
        candidates = (str(raw.get('id') or ''), str(raw.get('name') or ''))
    elif isinstance(raw, (list, tuple)):
        candidates = tuple(str(x or '') for x in raw)
    elif isinstance(raw, str):
        candidates = (raw,)
    else:
        candidates = ()
    for candidate in candidates:
        if m := resolve_model(candidate):
            return m
    return None


def model_choice_strategy() -> str:
    strategy = str(pref('model_choice_strategy', pref('model_strategy', 'medium')) or 'medium').strip().lower()
    return strategy if strategy in {'high', 'medium', 'low'} else 'medium'


def preferred_text_model_ids(strategy: str) -> tuple[str, ...]:
    match strategy:
        case 'low':
            return ('openai/gpt-4.1-mini', 'openai/gpt-4o-mini', 'openai/gpt-4.1', 'openai/gpt-4o')
        case 'high':
            return ('openai/gpt-4o', 'openai/gpt-4.1', 'openai/gpt-4o-mini', 'openai/gpt-4.1-mini')
        case _:
            return ('openai/gpt-4.1', 'openai/gpt-4.1-mini', 'openai/gpt-4o-mini', 'openai/gpt-4o')


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


def model_choice_for_text() -> tuple[Model, ...]:
    seen: set[str] = set()
    ans: list[Model] = []

    def add(model: Model | None):
        if model is None or model.id in seen:
            return
        seen.add(model.id)
        ans.append(model)

    add(configured_text_model())
    for model_id in preferred_text_model_ids(model_choice_strategy()):
        add(resolve_model(model_id))
    with suppress(Exception):
        legacy = newest_gpt_models()
        add(legacy.get(model_choice_strategy()))
        add(legacy.get('medium'))
        add(legacy.get('high'))
        add(legacy.get('low'))
    return tuple(ans)


def unavailable_model_error_message(err: HTTPError) -> str:
    details = ''
    with suppress(Exception):
        details = err.fp.read().decode('utf-8', 'replace')
    with suppress(Exception):
        error_json = json.loads(details)
        details = error_json.get('error', {}).get('message', details)
    return details


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
        model = resolve_model(use_model)
        if model is None:
            raise KeyError(f'No GitHub AI model matching: {use_model}')
        models = (model,)
    else:
        models = model_choice_for_text()
        if not models:
            raise KeyError('No usable GitHub AI text model could be determined')
    messages = tuple(messages)
    last_error = None
    for i, model in enumerate(models):
        data = {
            'model': model.id,
            'messages': [for_assistant(m) for m in messages],
        }
        rq = chat_request(data, model)
        try:
            for datum in read_streaming_response(rq, GitHubAI.name):
                for res in as_chat_responses(datum, model):
                    yield res
                    if res.exception:
                        break
            return
        except HTTPError as err:
            details = unavailable_model_error_message(err)
            last_error = err
            if err.code == 400 and 'unavailable model' in details.lower() and i + 1 < len(models):
                continue
            raise
    if last_error is not None:
        raise last_error


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.github.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


if __name__ == '__main__':
    develop()
