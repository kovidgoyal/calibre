#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Sequence
from enum import Enum, Flag, auto
from typing import Any, NamedTuple


class ChatMessageType(Enum):
    system = 'system'
    user = 'user'
    assistant = 'assistant'
    tool = 'tool'
    developer = 'developer'


class ChatMessage(NamedTuple):
    query: str
    type: ChatMessageType = ChatMessageType.user
    extra_data: Any = None
    reasoning_details: Sequence[dict[str, Any]] = ()
    reasoning: str = ''
    id: int | None = None

    @property
    def from_assistant(self) -> bool:
        return self.type is ChatMessageType.assistant


class WebLink(NamedTuple):
    title: str = ''
    uri: str = ''

    def __bool__(self) -> bool:
        return bool(self.title and self.uri)


class Citation(NamedTuple):
    links: Sequence[int]
    start_offset: int
    end_offset: int
    text: str = ''


class ChatResponse(NamedTuple):
    content: str = ''
    reasoning: str = ''
    reasoning_details: Sequence[dict[str, Any]] = ()
    type: ChatMessageType = ChatMessageType.assistant

    exception: Exception | None = None
    error_details: str = ''  # can be traceback or error message from HTTP response

    # This metadata will typically be present in the last response from a
    # streaming chat session.
    has_metadata: bool = False
    cost: float = 0
    currency: str = ''  # no currency means unknown
    provider: str = ''
    model: str = ''
    plugin_name: str = ''
    citations: Sequence[Citation] = ()
    web_links: Sequence[WebLink] = ()


class NoFreeModels(Exception):
    pass


class NoAPIKey(Exception):
    pass


class PromptBlockReason(Enum):
    unknown = auto()
    safety = auto()
    blocklist = auto()
    prohibited_content = auto()
    unsafe_image_generated = auto()

    @property
    def for_human(self) -> str:
        match self:
            case PromptBlockReason.safety:
                return _('Prompt would cause dangerous content to be generated')
            case PromptBlockReason.blocklist:
                return _('Prompt contains terms from a blocklist')
            case PromptBlockReason.prohibited_content:
                return _('Prompt would cause prohibited content to be generated')
            case PromptBlockReason.unsafe_image_generated:
                return _('Prompt would cause unsafe image content to be generated')
        return _('Prompt was blocked for an unknown reason')


class ResultBlockReason(Enum):
    unknown = auto()
    max_tokens = auto()
    safety = auto()
    recitation = auto()
    unsupported_language = auto()
    blocklist = auto()
    prohibited_content = auto()
    personally_identifiable_info = auto()
    malformed_function_call = auto()
    unsafe_image_generated = auto()
    unexpected_tool_call = auto()
    too_many_tool_calls = auto()

    @property
    def for_human(self) -> str:
        match self:
            case ResultBlockReason.max_tokens:
                return _('Result would contain too many tokens')
            case ResultBlockReason.safety:
                return _('Result would contain dangerous content')
            case ResultBlockReason.recitation:
                return _('Result would contain copyrighted content')
            case ResultBlockReason.unsupported_language:
                return _('Result would contain an unsupported language')
            case ResultBlockReason.personally_identifiable_info:
                return _('Result would contain personally identifiable information')
            case ResultBlockReason.blocklist:
                return _('Result contains terms from a blocklist')
            case ResultBlockReason.prohibited_content:
                return _('Result would contain prohibited content')
            case ResultBlockReason.unsafe_image_generated:
                return _('Result would contain unsafe image content')
            case ResultBlockReason.malformed_function_call:
                return _('Result would contain a malformed function call/tool invocation')
            case ResultBlockReason.unexpected_tool_call:
                return _('Model tried to use a tool with no tools configured')
            case ResultBlockReason.too_many_tool_calls:
                return _('Model tried to use too many tools')
        return _('Result was blocked for an unknown reason')


class PromptBlocked(ValueError):

    def __init__(self, reason: PromptBlockReason):
        super().__init__(reason.for_human)
        self.reason = reason


class ResultBlocked(ValueError):

    def __init__(self, reason: ResultBlockReason):
        super().__init__(reason.for_human)
        self.reason = reason


class AICapabilities(Flag):
    none = auto()
    text_to_text = auto()
    text_to_image = auto()
    text_and_image_to_image = auto()
    tts = auto()
    embedding = auto()

    @property
    def supports_text_to_text(self) -> bool:
        return AICapabilities.text_to_text in self

    @property
    def supports_text_to_image(self) -> bool:
        return AICapabilities.text_to_image in self

    @property
    def purpose(self) -> str:
        return 'AICapabilities.'+'|'.join(sorted(x.name for x in self))
