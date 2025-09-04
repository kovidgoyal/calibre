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
    id: int | None = None

    @property
    def from_assistant(self) -> bool:
        return self.type is ChatMessageType.assistant

    def for_assistant(self) -> dict[str, Any]:
        ans = {'role': self.type.value}
        if self.reasoning_details:
            ans['reasoning_details'] = self.reasoning_details
            ans['content'] = ''
        else:
            ans['content'] = self.query
        return ans


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
    currency: str = 'USD'
    provider: str = ''
    model: str = ''


class NoFreeModels(Exception):
    pass


class AICapabilities(Flag):
    none = auto()
    text_to_text = auto()
    text_to_image = auto()

    @property
    def supports_text_to_text(self) -> bool:
        return AICapabilities.text_to_text in self

    @property
    def supports_text_to_image(self) -> bool:
        return AICapabilities.text_to_image in self
