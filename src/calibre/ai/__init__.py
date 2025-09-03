#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from enum import Enum, Flag, auto
from typing import Any, NamedTuple


class ChatMessageType(Enum):
    system = auto()
    user = auto()
    assistant = auto()
    tool = auto()
    developer = auto()


class ChatMessage(NamedTuple):
    id: int
    query: str
    type: ChatMessageType = ChatMessageType.user
    extra_data: Any = None

    @property
    def from_assistant(self) -> bool:
        return self.type is ChatMessageType.assistant

    def for_assistant(self) -> dict[str, str]:
        return {'role': self.type.value, 'content': self.query}

    def for_display_to_human(self) -> str:
        if self.type is ChatMessageType.system:
            return ''
        from html import escape
        return escape(self.query).replace('\n', '<br>')


class ChatResponse(NamedTuple):
    content: str = ''
    cost: float = 0
    currency: str = 'USD'
    exception: Exception | None = None
    traceback: str = ''


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
