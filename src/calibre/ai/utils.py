#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from typing import Any

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse


class StreamedResponseAccumulator:

    def __init__(self):
        self.in_reasoning = False
        self.in_role = ChatMessageType.assistant

        self.all_reasoning = ''
        self.all_content = ''
        self.metadata = ChatResponse()
        self.messages: list[ChatMessage] = []

        self.current_reasoning_details: list[dict[str, Any]] = []
        self.current_content = ''

    def commit_content(self) -> None:
        if self.current_content:
            self.all_content += self.current_content
            self.messages.append(ChatMessage(type=self.in_role, query=self.current_content))
            self.current_content = ''

    def commit_reasoning(self) -> None:
        if self.current_reasoning_details:
            self.messages.append(ChatMessage(type=self.in_role, reasoning_details=tuple(self.current_reasoning_details)))
            self.current_reasoning_details = []

    def commit_current(self):
        if self.in_reasoning:
            self.commit_reasoning()
            self.in_reasoning = False
        else:
            self.commit_content()

    def accumulate(self, m: ChatResponse) -> None:
        if self.in_role != m.type:
            self.commit_current()
            self.in_role = m.type
        if m.has_metadata:
            self.commit_current()
            self.metadata = m
        if m.reasoning:
            self.all_reasoning += m.reasoning
        if self.in_reasoning:
            if m.response_details:
                self.current_reasoning_details.extend(m.reasoning_details)
            else:
                self.commit_reasoning()
                self.in_reasoning = False
                if m.content:
                    self.current_content += m.content
        else:
            if m.content:
                self.current_content += m.content
            else:
                self.commit_content()
                if m.reasoning_details:
                    self.in_reasoning = True
                    self.current_reasoning_details.extend(m.reasoning_details)

    def finalize(self) -> None:
        self.commit_current()
