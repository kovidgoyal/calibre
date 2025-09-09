#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Google studio account management: https://aistudio.google.com/usage

# Docs:
# Text generation: https://ai.google.dev/gemini-api/docs/text-generation#rest
# Image generation with gemini: https://ai.google.dev/gemini-api/docs/image-generation#rest
# Image generation with imagen: https://ai.google.dev/gemini-api/docs/imagen#rest
# TTS: https://ai.google.dev/gemini-api/docs/speech-generation#rest

import json
import os
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Any, NamedTuple
from urllib.request import Request

from calibre.ai import (
    AICapabilities,
    ChatMessage,
    ChatMessageType,
    ChatResponse,
    Citation,
    NoAPIKey,
    PromptBlocked,
    PromptBlockReason,
    ResultBlocked,
    ResultBlockReason,
    WebLink,
)
from calibre.ai.google import GoogleAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir

module_version = 1  # needed for live updates
API_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
MODELS_URL = f'{API_BASE_URL}/models?pageSize=500'


def pref(key: str, defval: Any = None) -> Any:
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
    google_search: Price = Price(35/1e3, 1500)
    input_audio: Price | None = None

    def get_cost_for_input_token_modality(self, mtc: dict[str, int]) -> float:
        cost = self.input
        if mtc['modality'] == 'AUDIO' and self.input_audio:
            cost = self.input_audio
        return cost.get_cost(mtc['tokenCount'])

    def get_cost(self, usage_metadata: dict[str, int]) -> tuple[float, str]:
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
            input=Price(2.5/1e6, 200_000, 1.5/1e6),
            output=Price(15/1e6, 200_000, 10/1e6),
            caching=Price(0.625/1e6, 200_000, 0.31/1e6),
            caching_storage=Price(4.5/1e6),
        ),
        'models/gemini-2.5-flash': Pricing(
            input=Price(0.3/1e6),
            output=Price(2.5/1e6),
            caching=Price(0.075/1e6),
            caching_storage=Price(1/1e6),
            input_audio=Price(1/1e6),
        ),
        'models/gemini-2.5-flash-lite': Pricing(
            input=Price(0.1/1e6),
            input_audio=Price(0.3/1e6),
            output=Price(0.4/1e6),
            caching=Price(0.025/1e6),
            caching_storage=Price(1/1e6),
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
    def from_dict(cls, x: dict[str, object]) -> 'Model':
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
                caps |= AICapabilities.text_to_image
            case 'gemini':
                if family_version >= 2.5:
                    caps |= AICapabilities.text_and_image_to_image
                if 'tts' in name_parts:
                    caps |= AICapabilities.tts
        pmap = get_model_costs()
        return Model(
            name=x['displayName'], id=mid, description=x.get('description', ''), version=x['version'],
            context_length=int(x['inputTokenLimit']), output_token_limit=int(x['outputTokenLimit']),
            capabilities=caps, family=family, family_version=family_version, name_parts=tuple(name_parts),
            slug=mid, thinking=x.get('thinking', False), pricing=pmap.get(mid),
        )

    def get_cost(self, usage_metadata: dict[str, int]) -> tuple[float, str]:
        if self.pricing is None:
            return 0, ''
        return self.pricing.get_cost(usage_metadata)


def parse_models_list(entries: list[dict[str, Any]]) -> dict[str, Model]:
    ans = {}
    for entry in entries['models']:
        e = Model.from_dict(entry)
        ans[e.id] = e
    return ans


@lru_cache(2)
def get_available_models() -> dict[str, 'Model']:
    api_key = decoded_api_key()
    cache_loc = os.path.join(cache_dir(), 'ai', f'{GoogleAI.name}-models-v1.json')
    data = get_cached_resource(cache_loc, MODELS_URL, headers=(('X-goog-api-key', api_key),))
    return parse_models_list(json.loads(data))


def config_widget():
    from calibre.ai.google.config import ConfigWidget
    return ConfigWidget()


def save_settings(config_widget):
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
    return m.get(pref('model_strategy', 'medium')) or m['medium']


def chat_request(data: dict[str, Any], model: Model, streaming: bool = True) -> Request:
    headers = {
        'X-goog-api-key': decoded_api_key(),
        'Content-Type': 'application/json',
    }
    url = f'{API_BASE_URL}/{model.slug}'
    if streaming:
        url += ':streamGenerateContent?alt=sse'
    else:
        url += ':generateContent'
    return Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


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
        'IMAGE_SAFETY': PromptBlockReason.unsafe_image_generated
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
                    citations.append(Citation(
                        links, start_offset=seg.get('startIndex', 0), end_offset=seg.get('endIndex', 0), text=seg.get('text', '')))
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
            type=role, content=''.join(content_parts), reasoning=''.join(reasoning_parts),
            reasoning_details=tuple(reasoning_details), has_metadata=has_metadata, model=model.id,
            cost=cost, plugin_name=GoogleAI.name, currency=currency, citations=citations, web_links=web_links,
        )


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # See https://ai.google.dev/gemini-api/docs/text-generation
    if use_model:
        model = get_available_models()[use_model]
    else:
        model = model_choice_for_text()
    contents = []
    system_instructions = []
    for m in messages:
        d = system_instructions if m.type is ChatMessageType.system else contents
        d.append(for_assistant(m))
    data = {
        # See https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
        'generationConfig': {
            'thinkingConfig': {
                'includeThoughts': True,
            },
        },
    }
    if (tb := thinking_budget(model)) is not None:
        data['generationConfig']['thinkingConfig']['thinkingBudget'] = tb
    if system_instructions:
        data['system_instruction'] = {'parts': system_instructions}
    if contents:
        data['contents'] = [{'parts': contents}]
    if pref('allow_web_searches', True):
        data['tools'] = [{'google_search': {}}]
    rq = chat_request(data, model)

    for datum in read_streaming_response(rq, GoogleAI.name):
        for res in as_chat_responses(datum, model):
            yield res
            if res.exception:
                break


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.google.backend import develop; develop()'
    print('\n'.join(f'{k}:{m.id}' for k, m in gemini_models().items()))
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, ('models/' + use_model) if use_model else '', messages=m)


if __name__ == '__main__':
    develop()
