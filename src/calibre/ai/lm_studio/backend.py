#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Ali Sheikhizadeh (Al00X) <al00x@outlook.com> <https://al00x.com>
# Based on code Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import json
import posixpath
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.parse import urlparse, urlunparse
from urllib.request import Request

if TYPE_CHECKING:
    from calibre.ai.lm_studio.config import ConfigWidget
else:
    ConfigWidget = object

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, StructuredOutputResult
from calibre.ai.lm_studio import LMStudioAI
from calibre.ai.prefs import pref_for_provider
from calibre.ai.structured import (
    develop_structured_output,
    messages_for_structured_output,
    strict_json_schema,
    structured_output_from_chat,
    structured_output_with_error_handler,
)
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, download_data, read_streaming_response

module_version = 2


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(LMStudioAI.name, key, defval)


def is_ready_for_use() -> bool:
    return bool(pref('text_model'))


class Model(NamedTuple):
    id: str
    owner: str

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> Model:
        return Model(id=x['id'], owner=x.get('owned_by', 'local'))


def api_url(path: str = '', use_api_url: str | None = None) -> str:
    base = (pref('api_url') if use_api_url is None else use_api_url) or LMStudioAI.DEFAULT_URL
    purl = urlparse(base)
    # LM Studio typically mounts endpoints under /v1
    base_path = purl.path or '/v1'
    if not base_path.endswith('/v1'):
        base_path = posixpath.join(base_path, 'v1')

    if path:
        path = posixpath.join(base_path, path)
    else:
        path = base_path

    purl = purl._replace(path=path)
    return urlunparse(purl)


@lru_cache(8)
def get_available_models(use_api_url: str | None = None) -> dict[str, Model]:
    # LM Studio mimics OpenAI: GET /v1/models
    url = api_url('models', use_api_url)
    ans = {}
    try:
        data = json.loads(download_data(url))
        if 'data' in data:
            for m in data['data']:
                model = Model.from_dict(m)
                ans[model.id] = model
    except Exception:
        pass
    return ans


def does_model_exist_locally(model_id: str, use_api_url: str | None = None) -> bool:
    try:
        return model_id in get_available_models(use_api_url)
    except Exception:
        return False


def human_readable_model_name(model_id: str) -> str:
    return model_id


def config_widget() -> ConfigWidget:
    from calibre.ai.lm_studio.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    return {'role': self.type.value, 'content': self.query}


def chat_request(data: dict[str, Any], url_override: str | None = None) -> Request:
    url = api_url('chat/completions', url_override)
    headers = {
        'Content-Type': 'application/json',
    }
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def chat_data(messages: Iterable[ChatMessage], model_id: str) -> dict[str, Any]:
    return {
        'model': model_id,
        'messages': [for_assistant(m) for m in messages],
        'stream': True,
        'temperature': pref('temperature', 0.7),
    }


def responses_for_data(data: dict[str, Any], model_id: str) -> Iterator[ChatResponse]:
    rq = chat_request(data)
    for data in read_streaming_response(rq, LMStudioAI.name):
        for choice in data.get('choices', []):
            d = choice.get('delta', {})
            content = d.get('content')
            role = d.get('role')
            if content:
                yield ChatResponse(content=content, type=ChatMessageType(role or 'assistant'), plugin_name=LMStudioAI.name)

        if 'usage' in data:
            yield ChatResponse(has_metadata=True, provider='LM Studio', model=data.get('model', model_id), plugin_name=LMStudioAI.name)


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    model_id = use_model or pref('text_model')
    yield from responses_for_data(chat_data(messages, model_id), model_id)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def structured_output_data(messages: Iterable[ChatMessage], model_id: str, schema: type) -> dict[str, Any]:
    # See https://lmstudio.ai/docs/app/api/structured-output
    data = chat_data(messages, model_id)
    data['response_format'] = {'type': 'json_schema', 'json_schema': {'name': schema.__name__, 'strict': True, 'schema': strict_json_schema(schema)}}
    return data


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    model_id = use_model or pref('text_model')
    data = structured_output_data(messages_for_structured_output(prompt, instructions), model_id, schema)
    return structured_output_from_chat(responses_for_data(data, model_id), schema, LMStudioAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.lm_studio.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
