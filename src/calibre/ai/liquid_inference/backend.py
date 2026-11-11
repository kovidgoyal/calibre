#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Loc Nguyen

import json
import math
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from urllib.request import Request

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, NoAPIKey, ResultBlocked, ResultBlockReason, StructuredOutputResult
from calibre.ai.liquid_inference import LiquidInference
from calibre.ai.openai_compatible.backend import coerce_text, for_assistant
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.structured import OnText, structured_output_via_prompt, structured_output_with_error_handler
from calibre.ai.utils import chat_with_error_handler, download_data, read_streaming_response
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from calibre.ai.liquid_inference.config import ConfigWidget
else:
    ConfigWidget = object

module_version = 1
API_URL = 'https://router.inference.ai.exchange/v1'
DEFAULT_MODEL = 'liquid.auto'
DEFAULT_CAP_USD = 1.0


def pref(key: str, defval: Any = None) -> Any:  # ruff: ignore[any-type]
    return pref_for_provider(LiquidInference.name, key, defval)


def is_ready_for_use() -> bool:
    return bool(pref('api_key'))


def headers(use_api_key: str | None = None) -> tuple[tuple[str, str], ...]:
    key = pref('api_key') if use_api_key is None else use_api_key
    if not key:
        raise NoAPIKey(_('An API key is required for Liquid Inference'))
    return (
        ('Authorization', f'Bearer {decode_secret(key)}'),
        ('Content-Type', 'application/json'),
        ('X-Title', 'Calibre'),
    )


@lru_cache(8)
def get_available_models(use_api_key: str | None = None) -> dict[str, str]:
    data = json.loads(download_data(API_URL + '/models', headers(use_api_key)))
    return {m['id']: m['id'] for m in data['data'] if m.get('modality') == 'text'}


def configured_model_name(for_image: bool = False) -> str:
    return '' if for_image else (pref('text_model') or DEFAULT_MODEL)


def human_readable_model_name(model_id: str) -> str:
    return model_id


def config_widget() -> ConfigWidget:
    from calibre.ai.liquid_inference.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()
    get_available_models.cache_clear()


def chat_request(data: dict[str, Any]) -> Request:
    cap = float(pref('cap_usd', DEFAULT_CAP_USD))
    if not math.isfinite(cap) or cap < 0.01:
        raise ValueError(_('The request cap must be at least 0.01 USD'))
    request_headers = dict(headers())
    request_headers['x-liquid-cap-usd'] = f'{cap:.2f}'
    return Request(API_URL + '/chat/completions', data=json.dumps(data).encode('utf-8'), headers=request_headers, method='POST')


def as_chat_responses(data: dict[str, Any], model_id: str) -> Iterator[ChatResponse]:
    if error := data.get('error'):
        message = error.get('message') if isinstance(error, dict) else str(error)
        yield ChatResponse(exception=ValueError(message or _('The provider returned an error')), plugin_name=LiquidInference.name)
        return
    for choice in data.get('choices') or ():
        delta = choice.get('delta') or {}
        content = coerce_text(delta.get('content'))
        reasoning = coerce_text(delta.get('reasoning_content')) or coerce_text(delta.get('reasoning'))
        if content or reasoning:
            yield ChatResponse(content=content, reasoning=reasoning, type=ChatMessageType.assistant, plugin_name=LiquidInference.name)
        reason = {'content_filter': ResultBlockReason.safety, 'length': ResultBlockReason.max_tokens}.get(choice.get('finish_reason'))
        if reason is not None:
            yield ChatResponse(exception=ResultBlocked(reason), plugin_name=LiquidInference.name)
            return
    if data.get('usage'):
        # The catalogue price is not the settled charge. The Liquid receipt holds the charge.
        yield ChatResponse(has_metadata=True, provider=LiquidInference.name, model=data.get('model') or model_id, plugin_name=LiquidInference.name)


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    model_id = use_model or configured_model_name()
    data = {
        'model': model_id,
        'messages': [for_assistant(m) for m in messages],
        'stream': True,
        'stream_options': {'include_usage': True},
    }
    seen_metadata = False
    finished = False
    for datum in read_streaming_response(chat_request(data), LiquidInference.name):
        finished = finished or any(c.get('finish_reason') is not None for c in datum.get('choices') or ())
        for response in as_chat_responses(datum, model_id):
            seen_metadata = seen_metadata or response.has_metadata
            yield response
            if response.exception:
                return
    if not finished:
        raise ValueError(_('The provider closed the stream before the answer was complete'))
    if not seen_metadata:
        yield ChatResponse(has_metadata=True, provider=LiquidInference.name, model=model_id, plugin_name=LiquidInference.name)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '', on_text: OnText | None = None) -> StructuredOutputResult:
    # Text models do not all support a native JSON schema.
    return structured_output_with_error_handler(
        lambda: structured_output_via_prompt(text_chat_implementation, prompt, schema, instructions, use_model, LiquidInference.name, on_text)
    )
