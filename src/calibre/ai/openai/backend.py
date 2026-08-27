#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import base64
import datetime
import json
import os
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from operator import attrgetter
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.request import Request

if TYPE_CHECKING:
    from calibre.ai.openai.config import ConfigWidget
else:
    ConfigWidget = object

from calibre.ai import (
    ChatMessage,
    ChatMessageType,
    ChatResponse,
    ImageData,
    ImageGenerationOptions,
    ImageGenerationResult,
    NoAPIKey,
    ResultBlocked,
    ResultBlockReason,
    StructuredOutputResult,
)
from calibre.ai.openai import OpenAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.structured import (
    develop_structured_output,
    messages_for_structured_output,
    strict_json_schema,
    structured_output_from_chat,
    structured_output_with_error_handler,
)
from calibre.ai.utils import (
    chat_with_error_handler,
    develop_image_generation,
    develop_text_chat,
    encode_multipart_formdata,
    get_cached_resource,
    image_data_from_file_path,
    image_generation_with_error_handler,
    read_json_response,
    read_streaming_response,
)
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 3  # needed for live updates
MODELS_URL = 'https://api.openai.com/v1/models'
CHAT_URL = 'https://api.openai.com/v1/responses'
IMAGE_GENERATIONS_URL = 'https://api.openai.com/v1/images/generations'
IMAGE_EDITS_URL = 'https://api.openai.com/v1/images/edits'


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
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
def headers() -> tuple[tuple[str, str], ...]:
    api_key = decoded_api_key()
    return (
        ('Authorization', f'Bearer {api_key}'),
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    # See https://platform.openai.com/docs/api-reference/models/retrieve
    id: str
    id_parts: Sequence[str]
    created: datetime.datetime
    version: float

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> Model:
        id_parts = tuple(x['id'].split('-'))
        try:
            version = float(id_parts[1])
        except Exception:
            version = 0
        return Model(
            id=x['id'],
            created=datetime.datetime.fromtimestamp(x['created'], datetime.UTC),
            id_parts=id_parts,
            version=version,
        )

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
        q = model.id.strip().lower()
        if name in q:
            yield model.id


def config_widget() -> ConfigWidget:
    from calibre.ai.openai.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    return model_id


_NON_CHAT_MODEL_TYPES = frozenset({'realtime', 'audio', 'tts', 'transcribe', 'search', 'image', 'codex', 'live', 'whisper'})


@lru_cache(2)
def newest_gpt_models() -> dict[str, Model]:
    high, medium, low = [], [], []
    for model in get_available_models().values():
        parts = model.id_parts
        if parts[0] == 'gpt' and len(parts) > 1 and not (_NON_CHAT_MODEL_TYPES & set(parts)):
            which = high
            if 'mini' in parts:
                which = medium
            elif 'nano' in parts:
                which = low
            which.append(model)
    return {
        'high': max(high, key=attrgetter('created')),
        'medium': max(medium, key=attrgetter('created')),
        'low': max(low, key=attrgetter('created')),
    }


@lru_cache(2)
def model_choice_for_text() -> Model:
    m = newest_gpt_models()
    return m.get(pref('model_strategy', 'medium'), m['medium'])


def reasoning_effort() -> str:
    return {'none': 'minimal', 'auto': 'medium', 'low': 'low', 'medium': 'medium', 'high': 'high'}.get(pref('reasoning_strategy', 'auto'), 'medium')


def chat_request(data: dict[str, Any], model: Model, use_tools: bool = True) -> Request:
    # See https://platform.openai.com/docs/api-reference/responses/create
    data['model'] = model.id
    data['stream'] = True
    if use_tools and pref('allow_web_searches', True):
        data.setdefault('tools', []).append({'type': 'web_search'})
    data['reasoning'] = {'effort': reasoning_effort(), 'summary': 'auto'}
    return Request(CHAT_URL, data=json.dumps(data).encode('utf-8'), headers=dict(headers()), method='POST')


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    if self.type not in (
        ChatMessageType.assistant,
        ChatMessageType.system,
        ChatMessageType.user,
        ChatMessageType.developer,
    ):
        raise ValueError(f'Unsupported message type: {self.type}')
    return {'role': self.type.value, 'content': self.query}


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    # See https://platform.openai.com/docs/api-reference/responses-streaming
    match d.get('type', ''):
        case 'response.created':
            if rid := (d.get('response') or {}).get('id', ''):
                yield ChatResponse(id=rid, plugin_name=OpenAI.name)
        case 'response.output_text.delta':
            if delta := d.get('delta'):
                yield ChatResponse(type=ChatMessageType.assistant, content=delta, model=model.id, plugin_name=OpenAI.name)
        case 'response.reasoning_summary_text.delta':
            if delta := d.get('delta'):
                yield ChatResponse(type=ChatMessageType.assistant, reasoning=delta, model=model.id, plugin_name=OpenAI.name)
        case 'response.completed':
            r = d.get('response') or {}
            # TODO: costing based on r['usage'] once model pricing data is available
            yield ChatResponse(
                id=r.get('id', ''),
                type=ChatMessageType.assistant,
                has_metadata=True,
                model=r.get('model') or model.id,
                provider='OpenAI',
                plugin_name=OpenAI.name,
            )
        case 'response.incomplete':
            reason = ((d.get('response') or {}).get('incomplete_details') or {}).get('reason', '')
            br = {'max_output_tokens': ResultBlockReason.max_tokens, 'content_filter': ResultBlockReason.safety}.get(reason, ResultBlockReason.unknown)
            yield ChatResponse(exception=ResultBlocked(br))
        case 'response.failed':
            err = (d.get('response') or {}).get('error') or {}
            msg = err.get('message') or _('The response failed for an unknown reason')
            yield ChatResponse(exception=Exception(msg), error_details=json.dumps(err))
        case 'error':
            msg = d.get('message') or _('Unknown error')
            yield ChatResponse(exception=Exception(msg), error_details=json.dumps(d))


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


def structured_output_data(messages: Iterable[ChatMessage], schema: type) -> dict[str, Any]:
    # See https://platform.openai.com/docs/guides/structured-outputs
    return {
        'input': [for_assistant(m) for m in messages],
        'text': {
            'format': {
                'type': 'json_schema',
                'name': schema.__name__,
                'strict': True,
                'schema': strict_json_schema(schema),
            }
        },
    }


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    data = structured_output_data(messages_for_structured_output(prompt, instructions), schema)
    # tools must be disabled as web search results are not JSON
    rq = chat_request(data, model, use_tools=False)

    def responses() -> Iterator[ChatResponse]:
        for datum in read_streaming_response(rq, OpenAI.name):
            yield from as_chat_responses(datum, model)

    return structured_output_from_chat(responses(), schema, OpenAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def size_for_aspect_ratio(aspect_ratio: str) -> str:
    # The gpt-image models only support a few fixed sizes
    return {'1:1': '1024x1024', '16:9': '1536x1024', '4:3': '1536x1024', '9:16': '1024x1536', '3:4': '1024x1536'}.get(aspect_ratio, 'auto')


def model_choice_for_images() -> str:
    want_mini = pref('image_model_strategy', 'high') == 'low'
    candidates = [m for m in get_available_models().values() if m.id_parts[0] == 'gpt' and 'image' in m.id_parts]
    if preferred := [m for m in candidates if ('mini' in m.id_parts) == want_mini]:
        candidates = preferred
    if not candidates:
        return 'gpt-image-1-mini' if want_mini else 'gpt-image-1'
    return max(candidates, key=attrgetter('created')).id


def image_generation_cost(model_id: str, usage: dict[str, Any]) -> tuple[float, str]:
    # See https://platform.openai.com/docs/pricing gpt-image models are priced
    # per million text input, image input and image output tokens.
    if not usage:
        return 0, ''
    is_mini = 'mini' in model_id.split('-')
    text_price, image_price, output_price = (2.0, 2.5, 8.0) if is_mini else (5.0, 10.0, 40.0)
    details = usage.get('input_tokens_details') or {}
    text_tokens = details.get('text_tokens', usage.get('input_tokens', 0))
    image_tokens = details.get('image_tokens', 0)
    cost = (text_tokens * text_price + image_tokens * image_price + usage.get('output_tokens', 0) * output_price) / 1e6
    return cost, 'USD'


def parse_image_response(d: dict[str, Any], model_id: str) -> ImageGenerationResult:
    # See https://platform.openai.com/docs/api-reference/images/object
    for item in d.get('data') or ():
        if b64 := item.get('b64_json'):
            cost, currency = image_generation_cost(model_id, d.get('usage') or {})
            return ImageGenerationResult(
                image=ImageData(data=base64.standard_b64decode(b64)), cost=cost, currency=currency, model=model_id, plugin_name=OpenAI.name
            )
    raise ValueError(_('No image was returned by the model: {}').format(model_id))


def generate_image_implementation(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    # See https://platform.openai.com/docs/api-reference/images
    model_id = use_model or model_choice_for_images()
    quality = pref('image_quality', 'auto')
    size = size_for_aspect_ratio(options.aspect_ratio)
    if source_images:
        fields = (('prompt', prompt), ('model', model_id), ('size', size), ('quality', quality))
        files = tuple(('image[]', f'image-{i}.{img.mime_type.partition("/")[2] or "png"}', img.mime_type, img.data) for i, img in enumerate(source_images))
        body, content_type = encode_multipart_formdata(fields, files)
        rq = Request(IMAGE_EDITS_URL, data=body, headers={'Authorization': f'Bearer {decoded_api_key()}', 'Content-Type': content_type}, method='POST')
    else:
        data = {'prompt': prompt, 'model': model_id, 'size': size, 'quality': quality}
        rq = Request(IMAGE_GENERATIONS_URL, data=json.dumps(data).encode('utf-8'), headers=dict(headers()), method='POST')
    return parse_image_response(read_json_response(rq, OpenAI.name), model_id)


def generate_image(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    return image_generation_with_error_handler(lambda: generate_image_implementation(prompt, source_images, options, use_model))


def develop_image(prompt: str = '', source_image_path: str = '', use_model: str = '', aspect_ratio: str = 'auto', output_path: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.openai.backend import develop_image; develop_image()'
    source_images = (image_data_from_file_path(source_image_path),) if source_image_path else ()
    develop_image_generation(generate_image, prompt, source_images, ImageGenerationOptions(aspect_ratio=aspect_ratio), use_model, output_path)


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.openai.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.openai.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
