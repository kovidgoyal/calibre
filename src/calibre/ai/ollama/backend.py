#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import http
import json
import posixpath
from collections.abc import Iterable, Iterator, Sequence
from contextlib import suppress
from functools import lru_cache
from typing import Any, NamedTuple
from urllib.parse import urlparse, urlunparse
from urllib.request import Request

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, ResultBlocked
from calibre.ai.ollama import OllamaAI
from calibre.ai.prefs import pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, download_data, opener

module_version = 1  # needed for live updates


def pref(key: str, defval: Any = None) -> Any:
    return pref_for_provider(OllamaAI.name, key, defval)


def is_ready_for_use() -> bool:
    return bool(pref('text_model'))


def headers() -> tuple[tuple[str, str]]:
    return (
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    # See https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
    name: str
    id: str
    family: str
    families: Sequence[str]
    modified_at: datetime.datetime
    can_think: bool

    @classmethod
    def from_dict(cls, x: dict[str, Any], details: dict[str, Any]) -> 'Model':
        d = x.get('details', {})
        return Model(
            name=x['name'], id=x['model'], family=d.get('family', ''), families=d.get('families', ()),
            modified_at=datetime.datetime.fromisoformat(x['modified_at']), can_think='thinking' in details['capabilities'],
        )


def api_url(path: str = '', use_api_url: str = '') -> str:
    ans = use_api_url or pref('api_url') or OllamaAI.DEFAULT_URL
    purl = urlparse(ans)
    base_path = purl.path or '/'
    if path:
        path = posixpath.join(base_path, path)
        purl = purl._replace(path=path)
    return urlunparse(purl)


@lru_cache(8)
def get_available_models(use_api_url: str = '') -> dict[str, Model]:
    ans = {}
    o = opener()
    for model in json.loads(download_data(api_url('api/tags', use_api_url)))['models']:
        rq = Request(api_url('api/show', use_api_url), data=json.dumps({'model': model['model']}).encode(), method='POST')
        with o.open(rq) as f:
            details = json.loads(f.read())
        e = Model.from_dict(model, details)
        ans[e.id] = e
    return ans


def does_model_exist_locally(model_id: str, use_api_url: str = '') -> bool:
    try:
        return model_id in get_available_models(use_api_url)
    except Exception:
        return False


def config_widget():
    from calibre.ai.ollama.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name
    return model_id


@lru_cache(2)
def model_choice_for_text() -> Model:
    return get_available_models()[pref('text_model')]


def chat_request(data: dict[str, Any], model: Model) -> Request:
    data['stream'] = True
    if model.can_think:
        data['think'] = True
    return Request(
        api_url('api/chat'), data=json.dumps(data).encode('utf-8'),
        headers=dict(headers()), method='POST')


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    if self.type not in (ChatMessageType.assistant, ChatMessageType.system, ChatMessageType.user, ChatMessageType.developer):
        raise ValueError(f'Unsupported message type: {self.type}')
    return {'role': self.type.value, 'content': self.query}


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    msg = d['message']
    content = msg['content']
    has_metadata = d['done']
    if has_metadata and (dr := d['done_reason']) != 'stop':
        yield ChatResponse(exception=ResultBlocked(custom_message=_('Result was blocked for reason: {}').format(dr)))
        return
    reasoning = msg.get('thinking') or ''
    if has_metadata or content or reasoning:
        yield ChatResponse(
            type=ChatMessageType.assistant, reasoning=reasoning, content=content, has_metadata=has_metadata, model=model.id, plugin_name=OllamaAI.name)


def read_streaming_response(rq: Request) -> Iterator[dict[str, Any]]:
    with opener().open(rq, timeout=pref('timeout', 120)) as response:
        if response.status != http.HTTPStatus.OK:
            details = ''
            with suppress(Exception):
                details = response.read().decode('utf-8', 'replace')
            raise Exception(f'Reading from {OllamaAI.name} failed with HTTP response status: {response.status} and body: {details}')
        for raw_line in response:
            yield json.loads(raw_line)


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
    # Doesnt use SSE
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    data = {
        'model': model.id,
        'messages': [for_assistant(m) for m in messages],
    }
    rq = chat_request(data, model)
    for datum in read_streaming_response(rq):
        for res in as_chat_responses(datum, model):
            yield res
            if res.exception:
                break


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.ollama.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


if __name__ == '__main__':
    develop()
