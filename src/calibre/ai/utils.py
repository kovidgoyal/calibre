#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import os
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from threading import Thread
from typing import Any
from urllib.request import ProxyHandler, build_opener

from calibre import get_proxies
from calibre.ai import ChatMessage, ChatMessageType, ChatResponse
from calibre.constants import __version__


def atomic_write(path, data):
    mode = 'w' if isinstance(data, str) else 'wb'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(mode, delete=False, dir=os.path.dirname(path)) as f:
        f.write(data)
    os.replace(f.name, path)


def opener(user_agent=f'calibre {__version__}'):
    proxies = get_proxies(debug=False)
    proxy_handler = ProxyHandler(proxies)
    ans = build_opener(proxy_handler)
    ans.addheaders = [('User-agent', user_agent)]
    return ans


def download_data(url: str) -> bytes:
    with opener().open(url) as f:
        return f.read()


def update_cached_data(path: str, url: str) -> None:
    raw = download_data(url)
    atomic_write(path, raw)


def schedule_update_of_cached_data(path: str, url: str) -> None:
    mtime = 0
    with suppress(OSError):
        mtime = os.path.getmtime(path)
    modtime = datetime.datetime.fromtimestamp(mtime)
    current_time = datetime.datetime.now()
    if current_time - modtime < datetime.timedelta(days=1):
        return
    Thread(daemon=True, name='AIDataDownload', target=update_cached_data, args=(path, url)).start()


def get_cached_resource(path: str, url: str) -> bytes:
    with suppress(OSError):
        with open(path, 'rb') as f:
            data = f.read()
        schedule_update_of_cached_data(path, url)
        return data
    data = download_data(url)
    atomic_write(path, data)
    return data


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

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self.messages)

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
