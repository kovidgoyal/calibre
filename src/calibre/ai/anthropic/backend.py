#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Anthropic account management: https://console.anthropic.com

# Docs:
# Messages API: https://docs.anthropic.com/en/api/messages
# Streaming: https://docs.anthropic.com/en/docs/build-with-claude/streaming
# Models list API: https://docs.anthropic.com/en/api/models-list
# Extended thinking: https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
# Pricing (no API for this): https://docs.anthropic.com/en/docs/about-claude/pricing

import json
import os
import sys
from collections.abc import Iterable, Iterator
from contextlib import suppress
from enum import Enum, auto
from functools import lru_cache
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.request import Request

if TYPE_CHECKING:
    from calibre.ai.anthropic.config import ConfigWidget
else:
    ConfigWidget = object

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, Citation, NoAPIKey, ResultBlocked, ResultBlockReason, StructuredOutputResult, WebLink
from calibre.ai.anthropic import AnthropicAI
from calibre.ai.prefs import decode_secret, pref_for_provider
from calibre.ai.structured import (
    develop_structured_output,
    messages_for_structured_output,
    strict_json_schema,
    structured_output_from_chat,
    structured_output_via_prompt,
    structured_output_with_error_handler,
)
from calibre.ai.utils import chat_with_error_handler, develop_text_chat, get_cached_resource, read_streaming_response
from calibre.constants import cache_dir
from calibre.utils.localization import _

module_version = 2  # needed for live updates
API_VERSION = '2023-06-01'
API_BASE_URL = 'https://api.anthropic.com/v1'
MODELS_URL = f'{API_BASE_URL}/models?limit=1000'
CHAT_URL = f'{API_BASE_URL}/messages'


def pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
    return pref_for_provider(AnthropicAI.name, key, defval)


def api_key() -> str:
    return pref('api_key')


def is_ready_for_use() -> bool:
    return bool(api_key())


def decoded_api_key() -> str:
    ans = api_key()
    if not ans:
        raise NoAPIKey('API key required for Anthropic')
    return decode_secret(ans)


class ThinkingMode(Enum):
    none = auto()  # model does not support extended thinking
    budget = auto()  # older models that need an explicit token budget for thinking
    adaptive = auto()  # newer models where the model itself decides how much to think


def base_model_id(model_id: str) -> str:
    # strip a trailing date or "latest" qualifier, e.g. claude-3-7-sonnet-20250219
    prefix, sep, last = model_id.rpartition('-')
    if sep and (last == 'latest' or (len(last) == 8 and last.isdigit())):
        return prefix
    return model_id


def parse_model_id(model_id: str) -> tuple[str, float]:
    # Extract the model family and version from ids such as claude-opus-4-8,
    # claude-sonnet-5, claude-3-5-haiku-20241022
    parts = base_model_id(model_id).split('-')
    if parts and parts[0] == 'claude':
        parts = parts[1:]
    family = ''
    version_parts: list[str] = []
    for p in parts:
        if p.isdigit():
            if len(version_parts) < 2:
                version_parts.append(p)
        elif not family and p.isalpha():
            family = p
    version = 0.0
    if version_parts:
        with suppress(ValueError):
            version = float('.'.join(version_parts))
    return family, version


def thinking_mode_for(family: str, version: float) -> tuple[ThinkingMode, bool]:
    # Returns the thinking mode and whether thinking can be explicitly
    # disabled. Assume future model families and versions keep the semantics
    # of the newest current models: adaptive thinking controlled by an effort
    # level.
    if family in ('fable', 'mythos'):
        return ThinkingMode.adaptive, False  # thinking is always on for these models
    if version >= 4.6 or version == 0:
        return ThinkingMode.adaptive, True
    if version >= 3.7:
        return ThinkingMode.budget, True
    return ThinkingMode.none, True


class Pricing(NamedTuple):
    # Values are USD per token/request
    input_token: float
    output_token: float
    cache_read: float
    cache_write: float
    web_search: float = 10 / 1e3  # USD per web search request

    @classmethod
    def per_million(cls, input_price: float, output_price: float) -> Pricing:
        # Cache writes cost 1.25x and cache reads 0.1x the input token price
        return Pricing(
            input_token=input_price / 1e6,
            output_token=output_price / 1e6,
            cache_read=0.1 * input_price / 1e6,
            cache_write=1.25 * input_price / 1e6,
        )

    def get_cost(self, usage: dict[str, Any]) -> tuple[float, str]:
        cost = (
            usage.get('input_tokens', 0) * self.input_token
            + usage.get('output_tokens', 0) * self.output_token
            + usage.get('cache_read_input_tokens', 0) * self.cache_read
            + usage.get('cache_creation_input_tokens', 0) * self.cache_write
        )
        server_tool_use = usage.get('server_tool_use') or {}
        cost += server_tool_use.get('web_search_requests', 0) * self.web_search
        return cost, 'USD'


class Model(NamedTuple):
    id: str
    name: str
    description: str
    family: str
    family_version: float
    thinking: ThinkingMode
    can_disable_thinking: bool
    context_length: int
    output_limit: int
    pricing: Pricing | None

    @property
    def supports_native_structured_output(self) -> bool:
        # See https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
        # Only available on newer models. Assume future model families and
        # versions support it.
        if self.family in ('fable', 'mythos') or self.family_version == 0:
            return True
        if self.family == 'opus':
            return self.family_version >= 4.1
        return self.family_version >= 4.5

    @classmethod
    def create(
        cls,
        model_id: str,
        name: str,
        description: str = '',
        context_length: int = 200_000,
        output_limit: int = 32_000,
        pricing: Pricing | None = None,
    ) -> Model:
        family, version = parse_model_id(model_id)
        mode, can_disable = thinking_mode_for(family, version)
        return Model(
            id=model_id,
            name=name,
            description=description,
            family=family,
            family_version=version,
            thinking=mode,
            can_disable_thinking=can_disable,
            context_length=context_length,
            output_limit=output_limit,
            pricing=pricing,
        )

    @classmethod
    def from_dict(cls, x: dict[str, Any], builtin: Model | None = None) -> Model:
        # See https://docs.anthropic.com/en/api/models-list
        mid = x['id']
        return cls.create(
            model_id=mid,
            name=x.get('display_name') or mid,
            description=builtin.description if builtin else '',
            context_length=int(x.get('max_input_tokens') or (builtin.context_length if builtin else 200_000)),
            output_limit=int(x.get('max_tokens') or (builtin.output_limit if builtin else 32_000)),
            pricing=builtin.pricing if builtin else None,
        )


@lru_cache(2)
def builtin_models() -> dict[str, Model]:
    # The models API provides no pricing data, so model pricing must be kept
    # up to date manually from https://docs.anthropic.com/en/docs/about-claude/pricing
    models = (
        Model.create(
            'claude-fable-5',
            'Claude Fable 5',
            _('The most capable Claude model, for the most demanding tasks. Note that it is expensive.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(10, 50),
        ),
        Model.create(
            'claude-opus-5',
            'Claude Opus 5',
            _('The flagship Claude model, combining high intelligence with reasonable cost.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(5, 25),
        ),
        Model.create(
            'claude-opus-4-8',
            'Claude Opus 4.8',
            _('An older generation of the flagship Claude Opus series of models.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(5, 25),
        ),
        Model.create(
            'claude-opus-4-7',
            'Claude Opus 4.7',
            _('An older generation of the flagship Claude Opus series of models.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(5, 25),
        ),
        Model.create(
            'claude-opus-4-6',
            'Claude Opus 4.6',
            _('An older generation of the flagship Claude Opus series of models.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(5, 25),
        ),
        Model.create(
            'claude-sonnet-5',
            'Claude Sonnet 5',
            _('A fast and capable model, well suited to most everyday tasks.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(3, 15),
        ),
        Model.create(
            'claude-sonnet-4-6',
            'Claude Sonnet 4.6',
            _('An older generation of the fast and capable Claude Sonnet series of models.'),
            context_length=1_000_000,
            output_limit=128_000,
            pricing=Pricing.per_million(3, 15),
        ),
        Model.create(
            'claude-haiku-4-5',
            'Claude Haiku 4.5',
            _('A small and fast model for simple tasks, the cheapest of the Claude models.'),
            context_length=200_000,
            output_limit=64_000,
            pricing=Pricing.per_million(1, 5),
        ),
    )
    return {m.id: m for m in models}


@lru_cache(2)
def get_available_models() -> dict[str, Model]:
    ans = dict(builtin_models())
    if not is_ready_for_use():
        return ans
    cache_loc = os.path.join(cache_dir(), 'ai', f'{AnthropicAI.name}-models-v1.json')
    headers = (('x-api-key', decoded_api_key()), ('anthropic-version', API_VERSION))
    try:
        entries = json.loads(get_cached_resource(cache_loc, MODELS_URL, headers=headers))
    except Exception as e:
        print(f'Failed to download the list of Anthropic models with error: {e}', file=sys.stderr)
        return ans
    b = builtin_models()
    for entry in entries.get('data', ()):
        if entry.get('type') != 'model' or not entry.get('id'):
            continue
        builtin = b.get(entry['id']) or b.get(base_model_id(entry['id']))
        m = Model.from_dict(entry, builtin)
        ans[m.id] = m
    return ans


def config_widget() -> ConfigWidget:
    from calibre.ai.anthropic.config import ConfigWidget

    return ConfigWidget()


def save_settings(config_widget: ConfigWidget) -> None:
    config_widget.save_settings()


def human_readable_model_name(model_id: str) -> str:
    if m := get_available_models().get(model_id):
        model_id = m.name
    return model_id


@lru_cache(2)
def models_by_strategy() -> dict[str, Model]:
    strategy_for_family = {'opus': 'high', 'sonnet': 'medium', 'haiku': 'low'}
    ans: dict[str, Model] = {}
    for m in get_available_models().values():
        strategy = strategy_for_family.get(m.family)
        if strategy is None:
            continue
        q = ans.get(strategy)
        # prefer the newest model, and among equally new ones those with known pricing
        if q is None or (m.family_version, m.pricing is not None) > (q.family_version, q.pricing is not None):
            ans[strategy] = m
    return ans


def model_choice_for_text() -> Model:
    if model_id := pref('model'):
        if m := get_available_models().get(model_id):
            return m
    m = models_by_strategy()
    ans = m.get(pref('model_choice_strategy', 'medium')) or m.get('medium')
    if ans is None:
        raise ValueError('No Anthropic models found for automatic model choice')
    return ans


def apply_reasoning_settings(data: dict[str, Any], model: Model) -> None:
    # https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    strategy = pref('reasoning_strategy', 'auto')
    match model.thinking:
        case ThinkingMode.adaptive:
            if strategy == 'none' and model.can_disable_thinking:
                data['thinking'] = {'type': 'disabled'}
                return
            # ask for summarized thinking so the reasoning can be shown to the user
            data['thinking'] = {'type': 'adaptive', 'display': 'summarized'}
            if strategy == 'none':
                # thinking cannot be disabled on this model, use lowest effort instead
                data.setdefault('output_config', {})['effort'] = 'low'
            elif strategy in ('low', 'medium', 'high'):
                data.setdefault('output_config', {})['effort'] = strategy
        case ThinkingMode.budget:
            if strategy == 'none':
                return
            fraction = {'low': 0.1, 'medium': 0.25, 'high': 0.5}.get(strategy, 0.25)
            budget = max(1024, int(data['max_tokens'] * fraction))
            data['thinking'] = {'type': 'enabled', 'budget_tokens': min(budget, data['max_tokens'] - 1024)}


def chat_request(data: dict[str, Any]) -> Request:
    headers = {
        'x-api-key': decoded_api_key(),
        'anthropic-version': API_VERSION,
        'Content-Type': 'application/json',
    }
    return Request(CHAT_URL, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')


def for_assistant(m: ChatMessage) -> dict[str, Any]:
    if m.type not in (ChatMessageType.user, ChatMessageType.assistant):
        raise ValueError(f'Unsupported message type: {m.type}')
    return {'role': m.type.value, 'content': m.query}


def exception_for_stop_reason(stop_reason: str, delta: dict[str, Any]) -> ResultBlocked | None:
    match stop_reason:
        case 'end_turn' | 'stop_sequence' | 'pause_turn':
            return None
        case 'max_tokens':
            return ResultBlocked(ResultBlockReason.max_tokens)
        case 'refusal':
            stop_details = delta.get('stop_details') or {}
            return ResultBlocked(ResultBlockReason.safety, custom_message=stop_details.get('explanation') or '')
    return ResultBlocked(custom_message=_('Response stopped for an unknown reason: {}').format(stop_reason))


def response_from_events(events: Iterator[dict[str, Any]], model: Model) -> Iterator[ChatResponse]:
    # https://docs.anthropic.com/en/docs/build-with-claude/streaming
    usage: dict[str, Any] = {}
    response_id = ''
    offset = block_start = 0
    block_links: list[int] = []
    citations: list[Citation] = []
    web_links: list[WebLink] = []
    link_idx_by_url: dict[str, int] = {}
    for event in events:
        match event.get('type'):
            case 'message_start':
                msg = event['message']
                response_id = msg.get('id') or ''
                usage.update(msg.get('usage') or {})
            case 'content_block_start':
                block_start = offset
                block_links = []
            case 'content_block_delta':
                delta = event['delta']
                match delta.get('type'):
                    case 'text_delta':
                        if text := delta.get('text'):
                            offset += len(text)
                            yield ChatResponse(content=text, type=ChatMessageType.assistant, id=response_id, plugin_name=AnthropicAI.name)
                    case 'thinking_delta':
                        if text := delta.get('thinking'):
                            yield ChatResponse(reasoning=text, type=ChatMessageType.assistant, id=response_id, plugin_name=AnthropicAI.name)
                    case 'citations_delta':
                        c = delta.get('citation') or {}
                        if url := c.get('url'):
                            idx = link_idx_by_url.get(url)
                            if idx is None:
                                idx = link_idx_by_url[url] = len(web_links)
                                web_links.append(WebLink(title=c.get('title') or url, uri=url))
                            if idx not in block_links:
                                block_links.append(idx)
            case 'content_block_stop':
                if block_links:
                    citations.append(Citation(tuple(block_links), start_offset=block_start, end_offset=offset))
                    block_links = []
            case 'message_delta':
                delta = event.get('delta') or {}
                usage.update(event.get('usage') or {})
                if (stop_reason := delta.get('stop_reason')) and (exc := exception_for_stop_reason(stop_reason, delta)) is not None:
                    yield ChatResponse(exception=exc)
                    return
            case 'error':
                e = event.get('error') or {}
                raise Exception(f'Error from Anthropic of type: {e.get("type", "unknown")} with message: {e.get("message", "Unknown error")}')
    cost, currency = model.pricing.get_cost(usage) if model.pricing else (0.0, '')
    yield ChatResponse(
        type=ChatMessageType.assistant,
        id=response_id,
        has_metadata=True,
        cost=cost,
        currency=currency,
        provider=AnthropicAI.name,
        model=model.id,
        plugin_name=AnthropicAI.name,
        citations=tuple(citations),
        web_links=tuple(web_links),
    )


def model_for_use_model(use_model: str) -> Model:
    if use_model:
        return get_available_models().get(use_model) or Model.create(use_model, use_model)
    return model_choice_for_text()


def chat_data(messages: Iterable[ChatMessage], model: Model, use_tools: bool = True) -> dict[str, Any]:
    system_prompts, chat = [], []
    for m in messages:
        if m.type in (ChatMessageType.system, ChatMessageType.developer):
            system_prompts.append(m.query)
        else:
            chat.append(for_assistant(m))
    data: dict[str, Any] = {
        'model': model.id,
        'max_tokens': model.output_limit,
        'messages': chat,
        'stream': True,
    }
    if system_prompts:
        data['system'] = '\n\n'.join(system_prompts)
    apply_reasoning_settings(data, model)
    if use_tools and pref('allow_web_searches', False):
        # https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool
        tool_type = 'web_search_20260209' if model.thinking is ThinkingMode.adaptive else 'web_search_20250305'
        data['tools'] = [{'type': tool_type, 'name': 'web_search'}]
    return data


def text_chat_implementation(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    # https://docs.anthropic.com/en/api/messages
    model = model_for_use_model(use_model)
    rq = chat_request(chat_data(messages, model))
    yield from response_from_events(read_streaming_response(rq, AnthropicAI.name), model)


def text_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
    yield from chat_with_error_handler(text_chat_implementation(messages, use_model))


def structured_output_data(messages: Iterable[ChatMessage], model: Model, schema: type) -> dict[str, Any]:
    # https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
    # tools must be disabled as web search results are not JSON
    data = chat_data(messages, model, use_tools=False)
    data.setdefault('output_config', {})['format'] = {'type': 'json_schema', 'schema': strict_json_schema(schema)}
    return data


def generate_structured_output_implementation(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    model = model_for_use_model(use_model)
    if not model.supports_native_structured_output:
        return structured_output_via_prompt(text_chat_implementation, prompt, schema, instructions, use_model, AnthropicAI.name)
    data = structured_output_data(messages_for_structured_output(prompt, instructions), model, schema)
    rq = chat_request(data)
    return structured_output_from_chat(response_from_events(read_streaming_response(rq, AnthropicAI.name), model), schema, AnthropicAI.name)


def generate_structured_output(prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
    return structured_output_with_error_handler(lambda: generate_structured_output_implementation(prompt, schema, instructions, use_model))


def develop(use_model: str = '', msg: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.anthropic.backend import develop; develop()'
    m = (ChatMessage(msg),) if msg else ()
    develop_text_chat(text_chat, use_model, messages=m)


def develop_structured(use_model: str = '', prompt: str = '') -> None:
    # calibre-debug -c 'from calibre.ai.anthropic.backend import develop_structured; develop_structured()'
    develop_structured_output(generate_structured_output, prompt, use_model=use_model)


if __name__ == '__main__':
    develop()
