#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Venice AI account management: https://venice.ai/settings/api

# Docs:
# API spec: https://docs.venice.ai/api-reference/api-spec
# Chat API: https://docs.venice.ai/api-reference/endpoint/chat/completions
# Image generation: https://docs.venice.ai/api-reference/endpoint/image/generate
# Models list API: https://docs.venice.ai/api-reference/endpoint/models/list

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
    from calibre.ai.venice.config import ConfigWidget
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
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.structured import (
    develop_structured_output,
    messages_for_structured_output,
    strict_json_schema,
    structured_output_from_chat,
    structured_output_via_prompt,
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
from calibre.ai.venice import VeniceAI
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 1  # needed for live updates
API_BASE_URL = 'https://api.venice.ai/api/v1'
MODELS_URL = f'{API_BASE_URL}/models'
CHAT_URL = f'{API_BASE_URL}/chat/completions'
IMAGE_GENERATION_URL = f'{API_BASE_URL}/image/generate'
# Token prices in the models list API are in USD per million tokens
PRICE_UNIT_TO_USD = 1 / 1e6
# Sizes for image generation models that take explicit pixel dimensions,
# keyed by the aspect ratios used in calibre. Dimensions must be at most
# 1280 pixels and divisible by 8.
PIXEL_SIZES = {
    'auto': (1024, 1024),
    '1:1': (1024, 1024),
    '3:4': (960, 1280),
    '9:16': (720, 1280),
    '4:3': (1280, 960),
    '16:9': (1280, 720),
}


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(VeniceAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for Venice AI')
    return decode_secret(ans)


@lru_cache(2)
def headers() -> tuple[tuple[str, str], ...]:
    return (
        ('Authorization', f'Bearer {decoded_api_key()}'),
        ('Content-Type', 'application/json'),
    )


class Model(NamedTuple):
    id: str
    name: str
    created: datetime.datetime
    context_length: int
    input_price: float  # USD per token
    output_price: float  # USD per token
    image_price: float  # USD per generated image
    traits: frozenset[str]
    supports_reasoning: bool
    supports_reasoning_effort: bool
    supports_response_schema: bool
    generates_images: bool
    aspect_ratios: tuple[str, ...]  # non-empty for image models sized by aspect ratio
    offline: bool

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> Model:
        spec = x.get('model_spec') or {}
        caps = spec.get('capabilities') or {}
        pricing = spec.get('pricing') or {}
        constraints = spec.get('constraints') or {}

        def usd(key: str) -> float:
            p = pricing.get(key)
            return float(p.get('usd') or 0) if isinstance(p, dict) else 0.0

        return cls(
            id=x['id'],
            name=spec.get('name') or x['id'],
            created=datetime.datetime.fromtimestamp(x.get('created') or 0, datetime.UTC),
            context_length=int(spec.get('availableContextTokens') or 0),
            input_price=usd('input') * PRICE_UNIT_TO_USD,
            output_price=usd('output') * PRICE_UNIT_TO_USD,
            image_price=usd('generation'),
            traits=frozenset(spec.get('traits') or ()),
            supports_reasoning=bool(caps.get('supportsReasoning')),
            supports_reasoning_effort=bool(caps.get('supportsReasoningEffort')),
            supports_response_schema=bool(caps.get('supportsResponseSchema')),
            generates_images=x.get('type') == 'image',
            aspect_ratios=tuple(constraints.get('aspectRatios') or ()),
            offline=bool(spec.get('offline')),
        )

    def get_cost(self, usage: dict[str, Any]) -> tuple[float, str]:
        if not usage or not (self.input_price or self.output_price):
            return 0, ''
        cost = usage.get('prompt_tokens', 0) * self.input_price + usage.get('completion_tokens', 0) * self.output_price
        return cost, 'USD'


def parse_models_list(data: dict[str, Any]) -> dict[str, Model]:
    ans = {}
    for entry in data.get('data') or ():
        m = Model.from_dict(entry)
        ans[m.id] = m
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    ans = {}
    for key in ('text', 'image'):
        cache_loc = os.path.join(cache_dir(), 'ai', f'{VeniceAI.name}-{key}-models-v1.json')
        data = json.loads(get_cached_resource(cache_loc, f'{MODELS_URL}?type={key}'))
        ans.update(parse_models_list(data))
    return ans


def config_widget() -> ConfigWidget:
    from calibre.ai.venice.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    try:
        m = get_available_models().get(model_id)
    except Exception:
        return model_id
    return m.name if m is not None else model_id


@lru_cache(2)
def models_by_strategy() -> dict[str, Model]:
    candidates = [m for m in get_available_models().values() if not m.generates_images and not m.offline]
    if not candidates:
        raise ValueError('No Venice AI models found for automatic model choice')

    def by_trait(trait: str) -> Model | None:
        return next((m for m in candidates if trait in m.traits), None)

    high = by_trait('most_intelligent') or max(candidates, key=attrgetter('output_price', 'created'))
    low = by_trait('fastest') or min(candidates, key=lambda m: (m.output_price or float('inf'), m.input_price or float('inf')))
    medium = by_trait('default') or low
    return {'high': high, 'medium': medium, 'low': low}


def model_choice_for_text() -> Model:
    model_id, model_name = pref('text_model', ('', ''))
    if m := get_available_models().get(model_id):
        return m
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
    # Venice injects its own system prompt by default, turn that off as
    # calibre supplies its own system prompts.
    venice_parameters: dict[str, Any] = {'include_venice_system_prompt': False}
    data: dict[str, Any] = {
        'model': model.id,
        'messages': [for_assistant(m) for m in messages],
        'stream': True,
        # usage is null in streamed chunks unless explicitly requested, and
        # without it responses have no cost or model metadata
        'stream_options': {'include_usage': True},
        'venice_parameters': venice_parameters,
    }
    strategy = pref('reasoning_strategy', 'auto')
    if strategy == 'none':
        if model.supports_reasoning:
            venice_parameters['disable_thinking'] = True
    elif strategy != 'auto' and model.supports_reasoning_effort:
        data['reasoning_effort'] = strategy
    if use_tools and pref('allow_web_searches', False):
        venice_parameters['enable_web_search'] = 'auto'
        venice_parameters['enable_web_citations'] = True
    return data


def parse_citations(d: dict[str, Any]) -> Iterator[WebLink]:
    for c in d.get('citations') or ():
        if isinstance(c, str):
            yield WebLink(title=c, uri=c)
    vp = d.get('venice_parameters') or {}
    for c in vp.get('web_search_citations') or ():
        if isinstance(c, dict):
            if url := c.get('url'):
                yield WebLink(title=c.get('title') or url, uri=url)
        elif isinstance(c, str):
            yield WebLink(title=c, uri=c)


def as_chat_responses(d: dict[str, Any], model: Model, web_links: tuple[WebLink, ...] = ()) -> Iterator[ChatResponse]:
    # https://docs.venice.ai/api-reference/endpoint/chat/completions
    rid = d.get('id') or ''
    for choice in d.get('choices') or ():
        delta = choice.get('delta') or {}
        content = delta.get('content') or ''
        reasoning = delta.get('reasoning_content') or ''
        if content or reasoning:
            yield ChatResponse(content=content, reasoning=reasoning, type=ChatMessageType.assistant, id=rid, model=model.id, plugin_name=VeniceAI.name)
        match choice.get('finish_reason'):
            case 'content_filter':
                yield ChatResponse(exception=ResultBlocked(ResultBlockReason.safety), plugin_name=VeniceAI.name)
                return
            case 'length':
                yield ChatResponse(exception=ResultBlocked(ResultBlockReason.max_tokens), plugin_name=VeniceAI.name)
                return
    if usage := d.get('usage'):
        cost, currency = model.get_cost(usage)
        yield ChatResponse(
            id=rid,
            type=ChatMessageType.assistant,
            has_metadata=True,
            cost=cost,
            currency=currency,
            provider=VeniceAI.name,
            model=d.get('model') or model.id,
            plugin_name=VeniceAI.name,
            web_links=web_links,
        )


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    model = model_for_use_model(use_model)
    rq = chat_request(chat_data(messages, model))
    seen_metadata = False
    web_links: list[WebLink] = []
    for datum in read_streaming_response(rq, VeniceAI.name):
        web_links.extend(parse_citations(datum))
        for res in as_chat_responses(datum, model, tuple(web_links)):
            seen_metadata = seen_metadata or res.has_metadata
            yield res
            if res.exception:
                return
    if not seen_metadata:
        yield ChatResponse(has_metadata=True, provider=VeniceAI.name, model=model.id, plugin_name=VeniceAI.name, web_links=tuple(web_links))


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def structured_output_data(messages: Iterable[ChatMessage], model: Model, schema: type) -> dict[str, Any]:
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
    if not model.supports_response_schema:
        return structured_output_via_prompt(text_chat_implementation, prompt, schema, instructions, use_model, VeniceAI.name)
    data = structured_output_data(messages_for_structured_output(prompt, instructions), model, schema)
    rq = chat_request(data)

    def responses() -> Iterator[ChatResponse]:
        seen_metadata = False
        for datum in read_streaming_response(rq, VeniceAI.name):
            for res in as_chat_responses(datum, model):
                seen_metadata = seen_metadata or res.has_metadata
                yield res
        if not seen_metadata:  # at least report the model used
            yield ChatResponse(has_metadata=True, provider=VeniceAI.name, model=model.id, plugin_name=VeniceAI.name)

    return structured_output_from_chat(responses(), schema, VeniceAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def model_choice_for_images() -> Model:
    model_id, model_name = pref('text_to_image_model', ('', ''))
    if m := get_available_models().get(model_id):
        return m
    candidates = [m for m in get_available_models().values() if m.generates_images and not m.offline]
    if not candidates:
        raise ValueError(_('No Venice AI models found for image generation'))
    return next((m for m in candidates if 'default' in m.traits), None) or max(candidates, key=attrgetter('created'))


def image_generation_data(prompt: str, model: Model, options: ImageGenerationOptions) -> dict[str, Any]:
    data: dict[str, Any] = {
        'model': model.id,
        'prompt': prompt,
        'format': 'png',
        # Venice watermarks generated images unless told not to
        'hide_watermark': True,
        # when true Venice blurs adult content in generated images
        'safe_mode': bool(pref('safe_mode', False)),
    }
    if model.aspect_ratios:
        if options.aspect_ratio != 'auto' and options.aspect_ratio in model.aspect_ratios:
            data['aspect_ratio'] = options.aspect_ratio
    else:
        data['width'], data['height'] = PIXEL_SIZES.get(options.aspect_ratio, PIXEL_SIZES['auto'])
    return data


def parse_image_response(d: dict[str, Any], model: Model) -> ImageGenerationResult:
    for b64 in d.get('images') or ():
        cost, currency = (model.image_price, 'USD') if model.image_price else (0, '')
        return ImageGenerationResult(
            image=ImageData(data=base64.standard_b64decode(b64), mime_type='image/png'),
            cost=cost,
            currency=currency,
            model=model.id,
            plugin_name=VeniceAI.name,
        )
    raise ValueError(_('No image was returned by the model: {}').format(model.id))


def generate_image_implementation(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    # https://docs.venice.ai/api-reference/endpoint/image/generate
    if source_images:
        raise ValueError(_('Venice AI models cannot edit existing images'))
    if use_model:
        model = get_available_models().get(use_model) or Model.from_dict({'id': use_model, 'type': 'image'})
    else:
        model = model_choice_for_images()
    data = image_generation_data(prompt, model, options)
    rq = Request(IMAGE_GENERATION_URL, data=json.dumps(data).encode('utf-8'), headers=dict(headers()), method='POST')
    return parse_image_response(read_json_response(rq, VeniceAI.name), model)


def generate_image(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    return image_generation_with_error_handler(lambda: generate_image_implementation(prompt, source_images, options, use_model))


def develop_image(prompt: str = '', use_model: str = '', aspect_ratio: str = 'auto', output_path: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.venice.backend import develop_image; develop_image()'
    develop_image_generation(generate_image, prompt, (), ImageGenerationOptions(aspect_ratio=aspect_ratio), use_model, output_path)


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.venice.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.venice.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
