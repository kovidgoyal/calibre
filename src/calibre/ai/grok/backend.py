#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# xAI account management: https://console.x.ai

# Docs:
# Chat API: https://docs.x.ai/developers/rest-api-reference/inference/chat
# Structured outputs: https://docs.x.ai/docs/guides/structured-outputs
# Image generation: https://docs.x.ai/developers/rest-api-reference/inference/images
# Models list APIs: https://docs.x.ai/developers/rest-api-reference/inference/models

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
    from calibre.ai.grok.config import ConfigWidget
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
    WebLink,
)
from calibre.ai.grok import GrokAI
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
    get_cached_resource,
    image_generation_with_error_handler,
    read_json_response,
    read_streaming_response,
)
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 1  # needed for live updates
API_BASE_URL = 'https://api.x.ai/v1'
TEXT_MODELS_URL = f'{API_BASE_URL}/language-models'
IMAGE_MODELS_URL = f'{API_BASE_URL}/image-generation-models'
CHAT_URL = f'{API_BASE_URL}/chat/completions'
IMAGE_GENERATIONS_URL = f'{API_BASE_URL}/images/generations'
DEFAULT_IMAGE_MODEL = 'grok-imagine-image-2.0'
# Token prices in the models list APIs are in USD cents per hundred million tokens
PRICE_UNIT_TO_USD_PER_TOKEN = 1 / (100 * 1e8)


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(GrokAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for Grok')
    return decode_secret(ans)


@lru_cache(2)
def headers() -> tuple[tuple[str, str], ...]:
    return (
        ('Authorization', f'Bearer {decoded_api_key()}'),
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    id: str
    id_parts: Sequence[str]
    created: datetime.datetime
    family_version: float
    context_length: int
    input_price: float  # USD per token
    output_price: float  # USD per token
    image_price: float  # USD per generated image
    generates_images: bool

    @classmethod
    def from_dict(cls, x: dict[str, Any], generates_images: bool = False) -> Model:
        id_parts = tuple(x['id'].split('-'))
        try:
            version = float(id_parts[1])
        except Exception:
            version = 0.0
        return cls(
            id=x['id'],
            id_parts=id_parts,
            created=datetime.datetime.fromtimestamp(x.get('created') or 0, datetime.UTC),
            family_version=version,
            context_length=int(x.get('context_length') or 0),
            input_price=(x.get('prompt_text_token_price') or 0) * PRICE_UNIT_TO_USD_PER_TOKEN,
            output_price=(x.get('completion_text_token_price') or 0) * PRICE_UNIT_TO_USD_PER_TOKEN,
            image_price=(x.get('image_price') or 0) / 100,  # USD cents per image
            generates_images=generates_images or 'image' in (x.get('output_modalities') or ()),
        )

    @property
    def supports_reasoning_effort(self) -> bool:
        # Only some Grok models accept the reasoning_effort parameter, the
        # request fails when it is sent to models that do not support it.
        return 'mini' in self.id_parts or ('reasoning' in self.id_parts and 'non' not in self.id_parts)

    def get_cost(self, usage: dict[str, Any]) -> tuple[float, str]:
        if not usage or not (self.input_price or self.output_price):
            return 0, ''
        cost = usage.get('prompt_tokens', 0) * self.input_price + usage.get('completion_tokens', 0) * self.output_price
        return cost, 'USD'


def parse_models_list(data: dict[str, Any], generates_images: bool = False) -> dict[str, Model]:
    ans = {}
    for entry in data.get('models') or ():
        m = Model.from_dict(entry, generates_images)
        ans[m.id] = m
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    auth_headers = (('Authorization', f'Bearer {decoded_api_key()}'),)
    ans = {}
    for url, key, generates_images in ((TEXT_MODELS_URL, 'text', False), (IMAGE_MODELS_URL, 'image', True)):
        cache_loc = os.path.join(cache_dir(), 'ai', f'{GrokAI.name}-{key}-models-v1.json')
        data = json.loads(get_cached_resource(cache_loc, url, headers=auth_headers))
        ans.update(parse_models_list(data, generates_images))
    return ans


def config_widget() -> ConfigWidget:
    from calibre.ai.grok.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    return model_id


_SPECIALIZED_MODEL_TYPES = frozenset({'image', 'video', 'voice', 'imagine', 'code', 'build', 'embedding'})


@lru_cache(2)
def models_by_strategy() -> dict[str, Model]:
    candidates = [
        m
        for m in get_available_models().values()
        if m.id_parts[0] == 'grok' and m.family_version > 0 and not (_SPECIALIZED_MODEL_TYPES & set(m.id_parts)) and not m.generates_images
    ]
    if not candidates:
        raise ValueError('No Grok models found for automatic model choice')
    candidates.sort(key=attrgetter('family_version', 'created'), reverse=True)
    high = candidates[0]
    # among equally cheap models prefer non-reasoning variants as they are
    # faster, and then newer ones
    low = min(candidates, key=lambda m: (m.output_price or float('inf'), m.input_price or float('inf'), 'non' not in m.id_parts, -m.family_version))
    medium = next((m for m in candidates if m.output_price and m.output_price < high.output_price), None) or low
    return {'high': high, 'medium': medium, 'low': low}


def model_choice_for_text() -> Model:
    m = models_by_strategy()
    return m.get(pref('model_choice_strategy', 'medium')) or m['medium']


def model_for_use_model(use_model: str) -> Model:
    if use_model:
        return get_available_models().get(use_model) or Model.from_dict({'id': use_model})
    return model_choice_for_text()


def chat_request(data: dict[str, Any]) -> Request:
    return Request(CHAT_URL, data=json.dumps(data).encode('utf-8'), headers=dict(headers()), method='POST')


def for_assistant(m: ChatMessage) -> dict[str, Any]:
    role = ChatMessageType.system if m.type is ChatMessageType.developer else m.type
    if role not in (ChatMessageType.assistant, ChatMessageType.system, ChatMessageType.user):
        raise ValueError(f'Unsupported message type: {m.type}')
    return {'role': role.value, 'content': m.query}


def chat_data(messages: Iterable[ChatMessage], model: Model, use_tools: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        'model': model.id,
        'messages': [for_assistant(m) for m in messages],
        'stream': True,
    }
    strategy = pref('reasoning_strategy', 'auto')
    if strategy != 'auto' and model.supports_reasoning_effort:
        # reasoning cannot be turned off, use the lowest available effort instead
        data['reasoning_effort'] = {'none': 'low'}.get(strategy, strategy)
    if use_tools and pref('allow_web_searches', False):
        # https://docs.x.ai/docs/guides/live-search
        data['search_parameters'] = {'mode': 'auto', 'return_citations': True}
    return data


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    # https://docs.x.ai/developers/rest-api-reference/inference/chat
    rid = d.get('id') or ''
    for choice in d.get('choices') or ():
        delta = choice.get('delta') or {}
        content = delta.get('content') or ''
        reasoning = delta.get('reasoning_content') or ''
        if content or reasoning:
            yield ChatResponse(content=content, reasoning=reasoning, type=ChatMessageType.assistant, id=rid, model=model.id, plugin_name=GrokAI.name)
        match choice.get('finish_reason'):
            case 'content_filter':
                yield ChatResponse(exception=ResultBlocked(ResultBlockReason.safety), plugin_name=GrokAI.name)
                return
            case 'length':
                yield ChatResponse(exception=ResultBlocked(ResultBlockReason.max_tokens), plugin_name=GrokAI.name)
                return
    if usage := d.get('usage'):
        cost, currency = model.get_cost(usage)
        web_links = tuple(WebLink(title=url, uri=url) for url in (d.get('citations') or ()))
        yield ChatResponse(
            id=rid,
            type=ChatMessageType.assistant,
            has_metadata=True,
            cost=cost,
            currency=currency,
            provider=GrokAI.name,
            model=d.get('model') or model.id,
            plugin_name=GrokAI.name,
            web_links=web_links,
        )


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    model = model_for_use_model(use_model)
    rq = chat_request(chat_data(messages, model))
    seen_metadata = False
    for datum in read_streaming_response(rq, GrokAI.name):
        for res in as_chat_responses(datum, model):
            seen_metadata = seen_metadata or res.has_metadata
            yield res
            if res.exception:
                return
    if not seen_metadata:
        yield ChatResponse(has_metadata=True, provider=GrokAI.name, model=model.id, plugin_name=GrokAI.name)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def structured_output_data(messages: Iterable[ChatMessage], model: Model, schema: type) -> dict[str, Any]:
    # https://docs.x.ai/docs/guides/structured-outputs
    # web searches must be disabled as search results are not JSON
    data = chat_data(messages, model, use_tools=False)
    data['response_format'] = {
        'type': 'json_schema',
        'json_schema': {
            'name': schema.__name__,
            'strict': True,
            'schema': strict_json_schema(schema),
        },
    }
    return data


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    model = model_for_use_model(use_model)
    data = structured_output_data(messages_for_structured_output(prompt, instructions), model, schema)
    rq = chat_request(data)

    def responses() -> Iterator[ChatResponse]:
        for datum in read_streaming_response(rq, GrokAI.name):
            yield from as_chat_responses(datum, model)

    return structured_output_from_chat(responses(), schema, GrokAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def model_choice_for_images() -> Model:
    candidates = [m for m in get_available_models().values() if m.generates_images]
    if not candidates:
        return Model.from_dict({'id': DEFAULT_IMAGE_MODEL}, generates_images=True)
    return max(candidates, key=attrgetter('created'))


def parse_image_response(d: dict[str, Any], model: Model) -> ImageGenerationResult:
    for item in d.get('data') or ():
        if b64 := item.get('b64_json'):
            cost, currency = (model.image_price, 'USD') if model.image_price else (0, '')
            return ImageGenerationResult(
                image=ImageData(data=base64.standard_b64decode(b64), mime_type=item.get('mime_type') or 'image/png'),
                cost=cost,
                currency=currency,
                model=model.id,
                plugin_name=GrokAI.name,
            )
    raise ValueError(_('No image was returned by the model: {}').format(model.id))


def generate_image_implementation(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    # https://docs.x.ai/developers/rest-api-reference/inference/images
    if source_images:
        raise ValueError(_('Grok models cannot edit existing images'))
    if use_model:
        model = get_available_models().get(use_model) or Model.from_dict({'id': use_model}, generates_images=True)
    else:
        model = model_choice_for_images()
    data = {
        'prompt': prompt,
        'model': model.id,
        'response_format': 'b64_json',
        'resolution': pref('image_resolution', '1k'),
    }
    if options.aspect_ratio != 'auto':
        data['aspect_ratio'] = options.aspect_ratio
    rq = Request(IMAGE_GENERATIONS_URL, data=json.dumps(data).encode('utf-8'), headers=dict(headers()), method='POST')
    return parse_image_response(read_json_response(rq, GrokAI.name), model)


def generate_image(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    return image_generation_with_error_handler(lambda: generate_image_implementation(prompt, source_images, options, use_model))


def develop_image(prompt: str = '', use_model: str = '', aspect_ratio: str = 'auto', output_path: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.grok.backend import develop_image; develop_image()'
    develop_image_generation(generate_image, prompt, (), ImageGenerationOptions(aspect_ratio=aspect_ratio), use_model, output_path)


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.grok.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.grok.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
