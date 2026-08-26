#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Google studio account management: https://aistudio.google.com/usage

# Docs:
# Text generation: https://ai.google.dev/gemini-api/docs/text-generation#rest
# Image generation with gemini: https://ai.google.dev/gemini-api/docs/image-generation#rest
# Image generation with imagen: https://ai.google.dev/gemini-api/docs/imagen#rest
# TTS: https://ai.google.dev/gemini-api/docs/speech-generation#rest

import base64
import http
import json
import os
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.error import HTTPError
from urllib.request import Request

if TYPE_CHECKING:
    from calibre.ai.google.config import ConfigWidget
else:
    ConfigWidget = object

from calibre.ai import (
    AICapabilities,
    ChatMessage,
    ChatMessageType,
    ChatResponse,
    Citation,
    ImageData,
    ImageGenerationOptions,
    ImageGenerationResult,
    NoAPIKey,
    PromptBlocked,
    PromptBlockReason,
    ResultBlocked,
    ResultBlockReason,
    StructuredOutputResult,
    WebLink,
)
from calibre.ai.google import GoogleAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.structured import (
    develop_structured_output,
    gemini_response_schema,
    messages_for_structured_output,
    structured_output_from_chat,
    structured_output_with_error_handler,
)
from calibre.ai.utils import (
    chat_with_error_handler,
    develop_image_generation,
    develop_text_chat,
    get_cached_resource,
    image_data_from_file_path,
    image_generation_with_error_handler,
    read_json_response,
    read_streaming_response,
)
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 3  # needed for live updates
API_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
MODELS_URL = f'{API_BASE_URL}/models?pageSize=500'


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(GoogleAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for Google AI')
    return decode_secret(ans)


class Price(NamedTuple):
    above: float
    threshold: int = 0
    below: float = 0

    def get_cost(self, num_tokens: int) -> float:
        return (self.below if num_tokens <= self.threshold else self.above) * num_tokens


class Pricing(NamedTuple):
    input: Price
    output: Price
    caching: Price
    caching_storage: Price
    google_search: Price = Price(35 / 1e3, 1500)
    input_audio: Price | None = None

    def get_cost_for_input_token_modality(self, mtc: dict[str, int]) -> float:
        cost = self.input
        if mtc['modality'] == 'AUDIO' and self.input_audio:
            cost = self.input_audio
        return cost.get_cost(mtc['tokenCount'])

    def get_cost(self, usage_metadata: dict[str, Any]) -> tuple[float, str]:
        prompt_tokens = usage_metadata['promptTokenCount']
        cached_tokens = usage_metadata.get('cachedContentTokenCount', 0)
        input_tokens = prompt_tokens - cached_tokens
        output_tokens = usage_metadata['totalTokenCount'] - prompt_tokens
        if ptd := usage_metadata.get('promptTokenDetails', ()):
            input_cost = 0
            for mtc in ptd:
                input_cost += self.get_cost_for_input_token_modality(mtc)
        else:
            input_cost = self.input.get_cost(input_tokens)
        return input_cost + self.caching.get_cost(cached_tokens) + self.output.get_cost(output_tokens), 'USD'


@lru_cache(2)
def get_model_costs() -> dict[str, Pricing]:
    # https://ai.google.dev/gemini-api/docs/pricing
    return {
        'models/gemini-2.5-pro': Pricing(
            input=Price(2.5 / 1e6, 200_000, 1.25 / 1e6),
            output=Price(15 / 1e6, 200_000, 10 / 1e6),
            caching=Price(0.25 / 1e6, 200_000, 0.125 / 1e6),
            caching_storage=Price(4.5 / 1e6),
        ),
        'models/gemini-2.5-flash': Pricing(
            input=Price(0.3 / 1e6),
            output=Price(2.5 / 1e6),
            caching=Price(0.03 / 1e6),
            caching_storage=Price(1 / 1e6),
            input_audio=Price(1 / 1e6),
        ),
        'models/gemini-2.5-flash-lite': Pricing(
            input=Price(0.1 / 1e6),
            input_audio=Price(0.3 / 1e6),
            output=Price(0.4 / 1e6),
            caching=Price(0.01 / 1e6),
            caching_storage=Price(1 / 1e6),
        ),
        'models/gemini-2.5-flash-image': Pricing(
            input=Price(0.3 / 1e6),
            output=Price(30 / 1e6),  # roughly $0.039 per image at 1290 tokens per image
            caching=Price(0),
            caching_storage=Price(0),
        ),
    }


class Model(NamedTuple):
    # See https://ai.google.dev/api/models#Model
    name: str
    id: str
    slug: str
    description: str
    version: str
    context_length: int
    output_token_limit: int
    capabilities: AICapabilities
    family: str
    family_version: float
    name_parts: tuple[str, ...]
    thinking: bool
    pricing: Pricing | None

    @classmethod
    def from_dict(cls, x: dict[str, Any]) -> Model:
        caps = AICapabilities.text_to_text
        mid = x['name']
        if 'embedContent' in x['supportedGenerationMethods']:
            caps |= AICapabilities.embedding
        family, family_version = '', 0
        name_parts = mid.rpartition('/')[-1].split('-')
        if len(name_parts) > 1:
            family, fv = name_parts[:2]
            try:
                family_version = float(fv)
            except Exception:
                family = ''
        match family:
            case 'imagen':
                if 'generate' in name_parts:
                    caps |= AICapabilities.text_to_image
            case 'gemini':
                if 'image' in name_parts:
                    caps |= AICapabilities.text_to_image | AICapabilities.text_and_image_to_image
                if 'tts' in name_parts:
                    caps |= AICapabilities.tts
        pmap = get_model_costs()
        return Model(
            name=x['displayName'],
            id=mid,
            description=x.get('description', ''),
            version=x['version'],
            context_length=int(x['inputTokenLimit']),
            output_token_limit=int(x['outputTokenLimit']),
            capabilities=caps,
            family=family,
            family_version=family_version,
            name_parts=tuple(name_parts),
            slug=mid,
            thinking=x.get('thinking', False),
            pricing=pmap.get(mid),
        )

    def get_cost(self, usage_metadata: dict[str, int]) -> tuple[float, str]:
        if self.pricing is None:
            return 0, ''
        return self.pricing.get_cost(usage_metadata)


def parse_models_list(entries: dict[str, Any]) -> dict[str, Model]:
    ans = {}
    for entry in entries['models']:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    api_key = decoded_api_key()
    cache_loc = os.path.join(cache_dir(), 'ai', f'{GoogleAI.name}-models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL, headers=(('X-goog-api-key', api_key),))
    return parse_models_list(json.loads(data))


def config_widget() -> ConfigWidget:
    from calibre.ai.google.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name
    return model_id


@lru_cache(8)
def gemini_models(version: float = 0) -> dict[str, Model]:
    models = {}
    for m in get_available_models().values():
        if m.family and 'preview' not in m.name_parts:
            fm = models.setdefault(m.family, {})
            fm.setdefault(m.family_version, []).append(m)

    gemini = models['gemini']
    version = version or max(gemini)
    ans = {}
    for m in gemini[version]:
        if m.name_parts[-1] == 'pro':
            ans['high'] = m
        elif m.name_parts[-1] == 'flash':
            ans['medium'] = m
        elif m.name_parts[-2:] == ('flash', 'lite'):
            ans['low'] = m
    return ans


def model_choice_for_text() -> Model:
    m = gemini_models()
    return m.get(pref('model_choice_strategy', 'medium')) or m['medium']


def model_choices_for_images(need_editing: bool) -> tuple[Model, ...]:
    gemini, imagen = [], []
    for m in get_available_models().values():
        if m.family == 'gemini' and m.capabilities.supports_text_to_image:
            gemini.append(m)
        elif m.family == 'imagen' and m.capabilities.supports_text_to_image:
            imagen.append(m)
    if pref('image_model', 'auto') == 'imagen' and not need_editing and imagen:
        # Prefer the newest standard generation model over fast/ultra variants
        return (max(imagen, key=lambda m: (m.family_version, ('fast' not in m.name_parts) + ('ultra' not in m.name_parts))),)
    if not gemini:
        raise ValueError(_('No Gemini models capable of image generation found'))
    # Prefer stable flash models with the highest version. Newer models are
    # tried first, falling back to older ones when quota is exceeded, as
    # typically only older models are available on the free tier.
    gemini.sort(
        key=lambda m: ('preview' not in m.name_parts and 'exp' not in m.name_parts, 'flash' in m.name_parts, 'lite' not in m.name_parts, m.family_version),
        reverse=True,
    )
    return tuple(gemini)


def api_request(data: dict[str, Any], model: Model, action: str) -> Request:
    headers = {
        'X-goog-api-key': decoded_api_key(),
        'Content-Type': 'application/json',
    }
    url = f'{API_BASE_URL}/{model.slug}:{action}'
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def chat_request(data: dict[str, Any], model: Model, streaming: bool = True) -> Request:
    return api_request(data, model, 'streamGenerateContent?alt=sse' if streaming else 'generateContent')


def thinking_budget(m: Model) -> int | None:
    # https://ai.google.dev/gemini-api/docs/thinking#set-budget
    if not m.thinking:
        return None
    limits = 0, 24576
    if 'pro' in m.name_parts:
        limits = 128, 32768
    elif 'lite' in m.name_parts:
        limits = 512, 24576
    match pref('reasoning_strategy', 'auto'):
        case 'auto':
            return -1
        case 'none':
            return limits[0] if 'pro' in m.name_parts else 0
        case 'low':
            return max(limits[0], int(0.2 * limits[1]))
        case 'medium':
            return max(limits[0], int(0.5 * limits[1]))
        case 'high':
            return max(limits[0], int(0.8 * limits[1]))
    return None


def for_assistant(self: ChatMessage) -> dict[str, Any]:
    return {'text': self.query}


def block_reason(block_reason: str) -> PromptBlockReason:
    return {
        'SAFETY': PromptBlockReason.safety,
        'BLOCKLIST': PromptBlockReason.blocklist,
        'PROHIBITED_CONTENT': PromptBlockReason.prohibited_content,
        'IMAGE_SAFETY': PromptBlockReason.unsafe_image_generated,
    }.get(block_reason.upper(), PromptBlockReason.unknown)


def result_block_reason(block_reason: str) -> ResultBlockReason:
    # See https://ai.google.dev/api/generate-content#FinishReason
    return {
        'MAX_TOKENS': ResultBlockReason.max_tokens,
        'SAFETY': ResultBlockReason.safety,
        'RECITATION': ResultBlockReason.recitation,
        'LANGUAGE': ResultBlockReason.unsupported_language,
        'BLOCKLIST': ResultBlockReason.blocklist,
        'PROHIBITED_CONTENT': ResultBlockReason.prohibited_content,
        'SPII': ResultBlockReason.personally_identifiable_info,
        'MALFORMED_FUNCTION_CALL': ResultBlockReason.malformed_function_call,
        'IMAGE_SAFETY': ResultBlockReason.unsafe_image_generated,
        'UNEXPECTED_TOOL_CALL': ResultBlockReason.unexpected_tool_call,
        'TOO_MANY_TOOL_CALLS': ResultBlockReason.too_many_tool_calls,
    }.get(block_reason.upper(), ResultBlockReason.unknown)


def as_chat_responses(d: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    # See https://ai.google.dev/api/generate-content#generatecontentresponse
    if pf := d.get('promptFeedback'):
        if br := pf.get('blockReason'):
            yield ChatResponse(exception=PromptBlocked(block_reason(br)))
            return
    grounding_chunks, grounding_supports = [], []
    for c in d['candidates']:
        has_metadata = False
        cost, currency = 0, ''
        if fr := c.get('finishReason'):
            if fr == 'STOP':
                has_metadata = True
                cost, currency = model.get_cost(d['usageMetadata'])
            else:
                yield ChatResponse(exception=ResultBlocked(result_block_reason(fr)))
                return
        content = c['content']
        if gm := c.get('groundingMetadata'):
            grounding_chunks.extend(gm['groundingChunks'])
            grounding_supports.extend(gm['groundingSupports'])
        citations, web_links = [], []
        if has_metadata:
            for x in grounding_chunks:
                if w := x.get('web'):
                    web_links.append(WebLink(**w))
                else:
                    web_links.append(WebLink())

            for s in grounding_supports:
                if links := tuple(i for i in s['groundingChunkIndices'] if web_links[i]):
                    seg = s['segment']
                    citations.append(
                        Citation(
                            links,
                            start_offset=seg.get('startIndex', 0),
                            end_offset=seg.get('endIndex', 0),
                            text=seg.get('text', ''),
                        )
                    )
        role = ChatMessageType.user if 'user' == content.get('role') else ChatMessageType.assistant
        content_parts = []
        reasoning_parts = []
        reasoning_details = []
        for part in content['parts']:
            if text := part.get('text'):
                (reasoning_parts if part.get('thought') else content_parts).append(text)
            if ts := part.get('thoughtSignature'):
                reasoning_details.append({'signature': ts})
        yield ChatResponse(
            type=role,
            content=''.join(content_parts),
            reasoning=''.join(reasoning_parts),
            reasoning_details=tuple(reasoning_details),
            has_metadata=has_metadata,
            model=model.id,
            cost=cost,
            plugin_name=GoogleAI.name,
            currency=currency,
            citations=citations,
            web_links=web_links,
        )


def chat_data(messages: Iterable[ChatMessage], model: Model, allow_web_searches: bool = True) -> dict[str, Any]:
    contents = []
    system_instructions = []
    for m in messages:
        d = system_instructions if m.type is ChatMessageType.system else contents
        d.append(for_assistant(m))
    data: dict[str, Any] = {
        # See https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
        'generationConfig': {
            'thinkingConfig': {
                'includeThoughts': True,
            },
        },
    }
    if (tb := thinking_budget(model)) is not None:
        thinking_config: dict[str, Any] = data['generationConfig']['thinkingConfig']
        thinking_config['thinkingBudget'] = tb
    if system_instructions:
        data['system_instruction'] = {'parts': system_instructions}
    if contents:
        data['contents'] = [{'parts': contents}]
    if allow_web_searches and pref('allow_web_searches', False):
        data['tools'] = [{'google_search': {}}]
    return data


def responses_for_data(data: dict[str, Any], model: Model) -> Iterator[ChatResponse]:
    rq = chat_request(data, model)
    for datum in read_streaming_response(rq, GoogleAI.name):
        for res in as_chat_responses(datum, model):
            yield res
            if res.exception:
                break


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # See https://ai.google.dev/gemini-api/docs/text-generation
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    yield from responses_for_data(chat_data(messages, model), model)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def structured_output_data(messages: Iterable[ChatMessage], model: Model, schema: type) -> dict[str, Any]:
    # See https://ai.google.dev/gemini-api/docs/structured-output
    # responseSchema is incompatible with the google_search tool
    data = chat_data(messages, model, allow_web_searches=False)
    gc = data['generationConfig']
    gc['responseMimeType'] = 'application/json'
    gc['responseSchema'] = gemini_response_schema(schema)
    return data


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    data = structured_output_data(messages_for_structured_output(prompt, instructions), model, schema)
    return structured_output_from_chat(responses_for_data(data, model), schema, GoogleAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def parse_gemini_image_response(d: dict[str, Any], model: Model) -> ImageGenerationResult:
    # See https://ai.google.dev/gemini-api/docs/image-generation
    if pf := d.get('promptFeedback'):
        if br := pf.get('blockReason'):
            raise PromptBlocked(block_reason(br))
    image = None
    text_parts: list[str] = []
    for c in d.get('candidates') or ():
        if (fr := c.get('finishReason')) and fr != 'STOP':
            raise ResultBlocked(result_block_reason(fr))
        for part in c.get('content', {}).get('parts', ()):
            if (text := part.get('text')) and not part.get('thought'):
                text_parts.append(text)
            if idata := part.get('inlineData'):
                image = ImageData(data=base64.standard_b64decode(idata['data']), mime_type=idata.get('mimeType') or 'image/png')
    if image is None:
        raise ValueError(_('No image was returned by the model: {}').format(model.name))
    cost, currency = 0.0, ''
    if um := d.get('usageMetadata'):
        cost, currency = model.get_cost(um)
    return ImageGenerationResult(image=image, text=''.join(text_parts), cost=cost, currency=currency, model=model.id, plugin_name=GoogleAI.name)


def gemini_generate_image(prompt: str, source_images: Sequence[ImageData], options: ImageGenerationOptions, model: Model) -> ImageGenerationResult:
    parts: list[dict[str, Any]] = [{'text': prompt}]
    for img in source_images:
        parts.append({'inline_data': {'mime_type': img.mime_type, 'data': base64.standard_b64encode(img.data).decode('ascii')}})
    generation_config: dict[str, Any] = {'responseModalities': ['TEXT', 'IMAGE']}
    if options.aspect_ratio != 'auto':
        generation_config['imageConfig'] = {'aspectRatio': options.aspect_ratio}
    data = {'contents': [{'parts': parts}], 'generationConfig': generation_config}
    rq = chat_request(data, model, streaming=False)
    return parse_gemini_image_response(read_json_response(rq, GoogleAI.name), model)


def parse_imagen_response(d: dict[str, Any], model: Model) -> ImageGenerationResult:
    # See https://ai.google.dev/gemini-api/docs/imagen
    for p in d.get('predictions') or ():
        if b64 := p.get('bytesBase64Encoded'):
            # Per image pricing, see https://ai.google.dev/gemini-api/docs/pricing
            cost = 0.06 if 'ultra' in model.name_parts else (0.02 if 'fast' in model.name_parts else 0.04)
            return ImageGenerationResult(
                image=ImageData(data=base64.standard_b64decode(b64), mime_type=p.get('mimeType') or 'image/png'),
                cost=cost,
                currency='USD',
                model=model.id,
                plugin_name=GoogleAI.name,
            )
        if reason := p.get('raiFilteredReason'):
            raise ResultBlocked(ResultBlockReason.unsafe_image_generated, custom_message=reason)
    raise ValueError(_('No image was returned by the model: {}').format(model.name))


def imagen_generate_image(prompt: str, options: ImageGenerationOptions, model: Model) -> ImageGenerationResult:
    parameters: dict[str, Any] = {'sampleCount': 1}
    if options.aspect_ratio != 'auto':
        parameters['aspectRatio'] = options.aspect_ratio
    data = {'instances': [{'prompt': prompt}], 'parameters': parameters}
    rq = api_request(data, model, 'predict')
    return parse_imagen_response(read_json_response(rq, GoogleAI.name), model)


def generate_image_implementation(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    if use_model:
        models = (get_available_models()[use_model],)
    else:
        models = model_choices_for_images(bool(source_images))
    for i, model in enumerate(models):
        try:
            if model.family == 'imagen':
                if source_images:
                    raise ValueError(_('The model {} cannot edit existing images').format(model.name))
                return imagen_generate_image(prompt, options, model)
            return gemini_generate_image(prompt, source_images, options, model)
        except HTTPError as e:
            # Fallback to older models when quota is exceeded, as typically
            # only older models are available on the free tier
            if e.code != http.HTTPStatus.TOO_MANY_REQUESTS or i == len(models) - 1:
                raise
    raise ValueError(_('No Gemini models capable of image generation found'))


def generate_image(
    prompt: str,
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
) -> ImageGenerationResult:
    return image_generation_with_error_handler(lambda: generate_image_implementation(prompt, source_images, options, use_model))


def develop_image(prompt: str = '', source_image_path: str = '', use_model: str = '', aspect_ratio: str = 'auto', output_path: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.google.backend import develop_image; develop_image()'
    source_images = (image_data_from_file_path(source_image_path),) if source_image_path else ()
    develop_image_generation(
        generate_image, prompt, source_images, ImageGenerationOptions(aspect_ratio=aspect_ratio), ('models/' + use_model) if use_model else '', output_path
    )


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.google.backend import develop; develop()'
    print('\n'.join(f'{k}:{m.id}' for k, m in gemini_models().items()))
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, ('models/' + use_model) if use_model else '', messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.google.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=('models/' + use_model) if use_model else '')


if __name__ == '__main__':
    develop()
