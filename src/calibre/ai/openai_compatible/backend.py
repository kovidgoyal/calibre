#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, OpenAI

import json
import posixpath
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from typing import Any, NamedTuple
from urllib.parse import urlparse, urlunparse
from urllib.request import Request

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, ResultBlocked, ResultBlockReason
from calibre.ai.openai_compatible import OpenAICompatible
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, download_data, read_streaming_response

module_version = 1


def pref(key: str, defval: Any = None) -> Any:
    return pref_for_provider(OpenAICompatible.name, key, defval)


def is_ready_for_use() -> bool:
    return bool(pref('api_url') and pref('text_model'))


class Model(NamedTuple):
    id: str
    owner: str

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> 'Model':
        return cls(id=x['id'], owner=x.get('owned_by', 'remote'))


def api_url(path: str = '', use_api_url: str | None = None) -> str:
    base = (pref('api_url') if use_api_url is None else use_api_url) or ''
    purl = urlparse(base)
    base_path = (purl.path or '').rstrip('/')
    if not base_path:
        base_path = '/v1'
    elif base_path.endswith('/chat/completions'):
        base_path = base_path[:-len('/chat/completions')]
    elif base_path.endswith('/models'):
        base_path = base_path[:-len('/models')]
    if path:
        base_path = posixpath.join(base_path, path)
    purl = purl._replace(path=base_path)
    return urlunparse(purl)


def raw_api_key(use_api_key: str | None = None) -> str:
    key = pref('api_key') if use_api_key is None else use_api_key
    return decode_secret(key) if key else ''


@lru_cache(32)
def request_headers(
    use_api_key: str | None = None, use_headers: Sequence[tuple[str, str]] | None = None
) -> tuple[tuple[str, str], ...]:
    ans = [('Content-Type', 'application/json')]
    extra_headers = pref('headers', ()) if use_headers is None else use_headers
    extra_headers = tuple(extra_headers or ())
    has_auth = False
    for key, val in extra_headers:
        if key.lower() == 'authorization':
            has_auth = True
        ans.append((key, val))
    if api_key := raw_api_key(use_api_key):
        if not has_auth:
            ans.insert(0, ('Authorization', f'Bearer {api_key}'))
    return tuple(ans)


@lru_cache(8)
def get_available_models(
    use_api_url: str | None = None, use_api_key: str | None = None, use_headers: Sequence[tuple[str, str]] | None = None
) -> dict[str, Model]:
    url = api_url('models', use_api_url)
    data = json.loads(download_data(url, request_headers(use_api_key, use_headers)))
    ans = {}
    if 'data' in data:
        for model_data in data['data']:
            model = Model.from_dict(model_data)
            ans[model.id] = model
    return ans


def human_readable_model_name(model_id: str) -> str:
    return model_id


def config_widget():
    from calibre.ai.openai_compatible.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    if self.type not in (ChatMessageType.assistant, ChatMessageType.system, ChatMessageType.user, ChatMessageType.developer):
        raise ValueError(f'Unsupported message type: {self.type}')
    return {'role': self.type.value, 'content': self.query}


def coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get('text')
        return text if isinstance(text, str) else ''
    if isinstance(value, list):
        return ''.join(filter(None, map(coerce_text, value)))
    return ''


def chat_request(
    data: dict[str, Any], url_override: str | None = None, use_api_key: str | None = None,
    use_headers: Sequence[tuple[str, str]] | None = None
) -> Request:
    url = api_url('chat/completions', url_override)
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=dict(request_headers(use_api_key, use_headers)), method='POST')


def as_chat_responses(d: dict[str, Any], model_id: str) -> Iterator[ChatResponse]:
    blocked = False
    for choice in d.get('choices', ()):
        delta = choice.get('delta') or {}
        content = coerce_text(delta.get('content'))
        reasoning = coerce_text(delta.get('reasoning_content'))
        role = delta.get('role') or 'assistant'
        if content or reasoning:
            yield ChatResponse(
                content=content, reasoning=reasoning, type=ChatMessageType(role), plugin_name=OpenAICompatible.name
            )
        if choice.get('finish_reason') == 'content_filter':
            blocked = True
    if blocked:
        yield ChatResponse(exception=ResultBlocked(ResultBlockReason.safety), plugin_name=OpenAICompatible.name)
        return
    if usage := d.get('usage'):
        yield ChatResponse(
            has_metadata=True, provider=OpenAICompatible.name, model=d.get('model') or model_id,
            plugin_name=OpenAICompatible.name
        )


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    model_id = use_model or pref('text_model')
    temperature = pref('temperature', 0.7)
    data = {
        'model': model_id,
        'messages': [for_assistant(m) for m in messages],
        'stream': True,
        'temperature': temperature,
    }
    rq = chat_request(data)
    seen_metadata = False
    for data in read_streaming_response(rq, OpenAICompatible.name, timeout=pref('timeout', 120)):
        for response in as_chat_responses(data, model_id):
            if response.has_metadata:
                seen_metadata = True
            yield response
            if response.exception:
                return
    if not seen_metadata:
        yield ChatResponse(has_metadata=True, provider=OpenAICompatible.name, model=model_id, plugin_name=OpenAICompatible.name)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def find_tests():
    import unittest

    class TestOpenAICompatibleBackend(unittest.TestCase):

        def test_api_url_normalization(self):
            self.assertEqual(api_url('models', 'http://localhost:1234'), 'http://localhost:1234/v1/models')
            self.assertEqual(api_url('models', 'http://localhost:1234/v1'), 'http://localhost:1234/v1/models')
            self.assertEqual(api_url('models', 'https://example.com/custom/api'), 'https://example.com/custom/api/models')
            self.assertEqual(api_url('chat/completions', 'https://ark.cn-beijing.volces.com/api/v3'), 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
            self.assertEqual(api_url('chat/completions', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'), 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')

        def test_request_headers_allows_missing_headers_pref(self):
            headers = request_headers()
            self.assertEqual(headers, (('Content-Type', 'application/json'),))

        def test_parsing_stream_deltas(self):
            responses = tuple(as_chat_responses({
                'model': 'demo-model',
                'choices': [
                    {'delta': {'role': 'assistant', 'content': 'Hello', 'reasoning_content': 'Think'}, 'finish_reason': None}
                ],
                'usage': {'total_tokens': 42},
            }, 'demo-model'))
            self.assertEqual(responses[0].content, 'Hello')
            self.assertEqual(responses[0].reasoning, 'Think')
            self.assertTrue(responses[-1].has_metadata)
            self.assertEqual(responses[-1].model, 'demo-model')

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestOpenAICompatibleBackend)


if __name__ == '__main__':
    develop()
