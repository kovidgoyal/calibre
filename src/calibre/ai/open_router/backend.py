#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import json
import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.request import Request

if TYPE_CHECKING:
    from calibre.ai.open_router.config import ConfigWidget
else:
    ConfigWidget = object

from calibre.ai import (
    AICapabilities,
    ChatMessage,
    ChatMessageType,
    ChatResponse,
    ImageData,
    ImageGenerationOptions,
    ImageGenerationResult,
    NoAPIKey,
    NoFreeModels,
    StructuredOutputResult,
)
from calibre.ai.open_router import OpenRouterAI
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
    image_as_data_url,
    image_data_from_file_path,
    image_from_data_url,
    image_generation_with_error_handler,
    read_json_response,
    read_streaming_response,
)
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 4  # needed for live updates
MODELS_URL = 'https://openrouter.ai/api/v1/models'


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(OpenRouterAI.name, key, defval)


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    cache_loc = os.path.join(cache_dir(), 'ai', f'{OpenRouterAI.name}-models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL)
    return parse_models_list(json.loads(data))


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name_without_creator_preserving_case
    return model_id


class Pricing(NamedTuple):
    # Values are in credits per token/request/unit
    input_token: float = 0  # cost per input token
    output_token: float = 0  # cost per output token
    request: float = 0  # per API request
    image: float = 0  # per image
    web_search: float = 0  # per web search
    internal_reasoning: float = 0  # cost per internal reasoning token
    input_cache_read: float = 0  # cost per cached input token read
    input_cache_write: float = 0  # cost per cached input token write

    @classmethod
    def from_dict(cls, x: dict[str, str]) -> Pricing:
        return Pricing(
            input_token=float(x['prompt']),
            output_token=float(x['completion']),
            request=float(x.get('request', 0)),
            image=float(x.get('image', 0)),
            web_search=float(x.get('web_search', 0)),
            internal_reasoning=float(x.get('internal_reasoning', 0)),
            input_cache_read=float(x.get('input_cache_read', 0)),
            input_cache_write=float(x.get('input_cache_write', 0)),
        )

    @property
    def is_free(self) -> bool:
        return max(self) == 0


class Model(NamedTuple):
    name: str
    id: str
    slug: str
    created: datetime.datetime
    description: str
    context_length: int
    pricing: Pricing
    parameters: tuple[str, ...]
    is_moderated: bool
    capabilities: AICapabilities
    tokenizer: str

    @property
    def creator(self) -> str:
        return self.name.partition(':')[0].lower()

    @property
    def family(self) -> str:
        parts = self.name.split(':')
        if len(parts) > 1:
            return parts[1].strip().partition(' ')[0].lower()
        return ''

    @property
    def name_without_creator(self) -> str:
        return self.name_without_creator_preserving_case.lower()

    @property
    def name_without_creator_preserving_case(self) -> str:
        return re.sub(r' \(free\)$', '', self.name.partition(':')[-1].strip()).strip()

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> Model:
        arch = x['architecture']
        capabilities = AICapabilities.none
        if 'text' in arch['input_modalities']:
            if 'text' in arch['output_modalities']:
                capabilities |= AICapabilities.text_to_text
            if 'image' in arch['output_modalities']:
                capabilities |= AICapabilities.text_to_image
                if 'image' in arch['input_modalities']:
                    capabilities |= AICapabilities.text_and_image_to_image

        return Model(
            name=x['name'],
            id=x['id'],
            created=datetime.datetime.fromtimestamp(x['created'], datetime.UTC),
            description=x['description'],
            context_length=x['context_length'],
            slug=x['canonical_slug'],
            parameters=tuple(x['supported_parameters']),
            pricing=Pricing.from_dict(x['pricing']),
            is_moderated=x['top_provider']['is_moderated'],
            tokenizer=arch['tokenizer'],
            capabilities=capabilities,
        )


def parse_models_list(entries: dict[str, Any]) -> dict[str, Model]:
    ans = {}
    for entry in entries['data']:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


def config_widget() -> ConfigWidget:
    from calibre.ai.open_router.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


@lru_cache(64)
def free_model_choice(capabilities: AICapabilities = AICapabilities.text_to_text, allow_paid: bool = False) -> tuple[Model, ...]:
    gemini_free, gemini_paid = [], []
    deep_seek_free, deep_seek_paid = [], []
    grok_free, grok_paid = [], []
    gpt5_free, gpt5_paid = [], []
    gpt_oss_free, gpt_oss_paid = [], []
    claude_free, claude_paid = [], []

    def only(*model_groups: list[Model], sort_key: Callable[[Model], Any] = lambda m: m.created, reverse: bool = True) -> Iterator[Model]:  # noqa: ANN401
        for models in model_groups:
            if models:
                models.sort(key=sort_key, reverse=reverse)
                yield models[0]

    for model in get_available_models().values():
        if AICapabilities.text_to_text & capabilities != capabilities:
            continue
        match model.creator:
            case 'google':
                if model.family == 'gemini':
                    gemini_free.append(model) if model.pricing.is_free else gemini_paid.append(model)
            case 'deepseek':
                deep_seek_free.append(model) if model.pricing.is_free else deep_seek_paid.append(model)
            case 'openai':
                n = model.name_without_creator
                if n.startswith('gpt-5'):
                    gpt5_free.append(model) if model.pricing.is_free else gpt5_paid.append(model)
                elif n.startswith('gpt-oss'):
                    gpt_oss_free.append(model) if model.pricing.is_free else gpt_oss_paid.append(model)
            case 'anthropic':
                if model.family == 'claude':
                    claude_free.append(model) if model.pricing.is_free else claude_paid.append(model)
            case 'xai':
                if model.family == 'grok' and 'code fast' not in model.name_without_creator:
                    grok_free.append(model) if model.pricing.is_free else grok_paid.append(model)
    free = tuple(only(gemini_free, gpt5_free, grok_free, gpt_oss_free, claude_free, deep_seek_free))
    if free:
        return free
    if not allow_paid:
        raise NoFreeModels(_('No free models were found for text to text generation'))
    return tuple(sorted(only(gemini_paid, gpt5_paid, grok_paid, claude_paid, deep_seek_paid), key=lambda m: m.pricing.output_token))


def model_choice_for_text() -> Iterator[Model]:
    model_id, model_name = pref('text_model', ('', ''))
    if m := get_available_models().get(model_id):
        yield m
        return
    match pref('model_choice_strategy', 'free-or-paid'):
        case 'free-or-paid':
            yield from free_model_choice(allow_paid=True)
        case 'free-only':
            yield from free_model_choice(allow_paid=False)
        case _:
            yield get_available_models()['openrouter/auto']


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for OpenRouter')
    return decode_secret(ans)


def chat_request(data: dict[str, Any], url: str = 'https://openrouter.ai/api/v1/chat/completions') -> Request:
    headers = {
        'Authorization': f'Bearer {decoded_api_key()}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://calibre-ebook.com',
        'X-Title': 'calibre',
    }
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    ans = {'role': self.type.value, 'content': self.query}
    if self.reasoning_details:
        ans['reasoning_details'] = self.reasoning_details
    return ans


def add_websearch_if_desired(data: dict[str, Any], models: Sequence[Model]) -> None:
    # https://openrouter.ai/docs/features/web-search
    if pref('allow_web_searches', False):
        data['plugins'].append({'id': 'web'})


def models_for_chat(use_model: str) -> tuple[tuple[Model, ...], str]:
    if use_model:
        return (), use_model
    models = tuple(model_choice_for_text())
    if not models:
        models = (get_available_models()['openrouter/auto'],)
    return models, models[0].id


def chat_data(messages: Iterable[ChatMessage], models: Sequence[Model], model_id: str, use_web_search: bool = True) -> dict[str, Any]:
    data_collection = pref('data_collection', 'deny')
    if data_collection not in ('allow', 'deny'):
        data_collection = 'deny'
    data: dict[str, Any] = {
        'model': model_id,
        'plugins': [],
        'messages': [for_assistant(m) for m in messages],
        'usage': {'include': True},
        'stream': True,
        'reasoning': {'enabled': True},
        'provider': {'data_collection': data_collection},
    }
    if len(models) > 1:
        data['models'] = [m.id for m in models[1:]]
    s = pref('reasoning_strategy')
    match s:
        case 'low' | 'medium' | 'high':
            data['reasoning']['effort'] = s
        case 'auto':
            pass
        case _:
            data['reasoning']['enabled'] = False
    if use_web_search:
        add_websearch_if_desired(data, models)
    return data


def responses_from_stream(rq: Request) -> Iterator[ChatResponse]:
    for data in read_streaming_response(rq, OpenRouterAI.name):
        for choice in data['choices']:
            d = choice['delta']
            c = d.get('content') or ''
            r = d.get('reasoning') or ''
            rd = d.get('reasoning_details') or ()
            role = d.get('role') or 'assistant'
            if c or r or rd:
                yield ChatResponse(
                    content=c,
                    reasoning=r,
                    reasoning_details=rd,
                    type=ChatMessageType(role),
                    plugin_name=OpenRouterAI.name,
                )
        if u := data.get('usage'):
            yield ChatResponse(
                cost=float(u['cost'] or 0),
                currency=_('credits'),
                provider=data.get('provider') or '',
                model=data.get('model') or '',
                has_metadata=True,
                plugin_name=OpenRouterAI.name,
            )


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    models, model_id = models_for_chat(use_model)
    data = chat_data(messages, models, model_id)
    yield from responses_from_stream(chat_request(data))


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def supports_structured_output(m: Model) -> bool:
    return 'structured_outputs' in m.parameters or 'response_format' in m.parameters


def structured_output_data(messages: Iterable[ChatMessage], models: Sequence[Model], model_id: str, schema: type) -> dict[str, Any]:
    # See https://openrouter.ai/docs/features/structured-outputs
    # web search is disabled as its results are not JSON
    data = chat_data(messages, models, model_id, use_web_search=False)
    data['response_format'] = {'type': 'json_schema', 'json_schema': {'name': schema.__name__, 'strict': True, 'schema': strict_json_schema(schema)}}
    if 'models' in data:
        # only fall back to models that also support structured output
        fallbacks = [m.id for m in models[1:] if supports_structured_output(m)]
        if fallbacks:
            data['models'] = fallbacks
        else:
            del data['models']
    return data


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    models, model_id = models_for_chat(use_model)
    if use_model:
        m = get_available_models().get(use_model)
        # models not in the catalog are assumed to support structured output,
        # the server rejects the request cleanly if not
        native = m is None or supports_structured_output(m)
    else:
        native = supports_structured_output(models[0])
    if not native:
        return structured_output_via_prompt(text_chat_implementation, prompt, schema, instructions, use_model, OpenRouterAI.name)
    data = structured_output_data(messages_for_structured_output(prompt, instructions), models, model_id, schema)
    return structured_output_from_chat(responses_from_stream(chat_request(data)), schema, OpenRouterAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def model_choice_for_images(need_editing: bool) -> Model:
    model_id, model_name = pref('text_to_image_model', ('', ''))
    if m := get_available_models().get(model_id):
        return m
    caps = AICapabilities.text_to_image
    if need_editing:
        caps |= AICapabilities.text_and_image_to_image
    # Exclude the openrouter/auto meta models as they have no pricing data, so
    # appear to be free, and route to arbitrary underlying models
    candidates = [m for m in get_available_models().values() if caps & m.capabilities == caps and not m.id.startswith('openrouter/')]
    if not candidates:
        raise ValueError(_('No models capable of image generation found on OpenRouter'))
    if free := [m for m in candidates if m.pricing.is_free]:
        return max(free, key=lambda m: m.created)
    return min(candidates, key=lambda m: (m.pricing.image or m.pricing.output_token, m.pricing.output_token))


def parse_image_chat_response(d: dict[str, Any], model_id: str) -> ImageGenerationResult:
    # See https://openrouter.ai/docs/features/multimodal/image-generation
    image = None
    text = ''
    for choice in d.get('choices') or ():
        msg = choice.get('message') or {}
        text += msg.get('content') or ''
        for img in msg.get('images') or ():
            if url := (img.get('image_url') or {}).get('url', ''):
                image = image_from_data_url(url)
    if image is None:
        raise ValueError(_('No image was returned by the model: {}').format(model_id))
    cost = float((d.get('usage') or {}).get('cost') or 0)
    return ImageGenerationResult(
        image=image,
        text=text,
        cost=cost,
        currency=_('credits') if cost else '',
        provider=d.get('provider') or '',
        model=d.get('model') or model_id,
        plugin_name=OpenRouterAI.name,
    )


def generate_image_implementation(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    # Note that the OpenRouter API has no standardized way to specify image
    # parameters such as aspect ratio, so options is currently unused.
    model_id = use_model or model_choice_for_images(bool(source_images)).id
    data_collection = pref('data_collection', 'deny')
    if data_collection not in ('allow', 'deny'):
        data_collection = 'deny'
    content: str | list[dict[str, Any]] = prompt
    if source_images:
        content = [{'type': 'text', 'text': prompt}]
        for img in source_images:
            content.append({'type': 'image_url', 'image_url': {'url': image_as_data_url(img)}})
    data = {
        'model': model_id,
        'messages': [{'role': 'user', 'content': content}],
        'modalities': ['image', 'text'],
        'usage': {'include': True},
        'provider': {'data_collection': data_collection},
    }
    rq = chat_request(data)
    return parse_image_chat_response(read_json_response(rq, OpenRouterAI.name), model_id)


def generate_image(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    return image_generation_with_error_handler(lambda: generate_image_implementation(prompt, source_images, options, use_model))


def develop_image(prompt: str = '', source_image_path: str = '', use_model: str = '', aspect_ratio: str = 'auto', output_path: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.open_router.backend import develop_image; develop_image()'
    source_images = (image_data_from_file_path(source_image_path),) if source_image_path else ()
    develop_image_generation(generate_image, prompt, source_images, ImageGenerationOptions(aspect_ratio=aspect_ratio), use_model, output_path)


def develop(msg: str = '', use_model: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.open_router.backend import *; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.open_router.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
