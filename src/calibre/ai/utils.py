#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
import http
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import suppress
from enum import Enum, auto
from functools import lru_cache
from threading import Thread
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from calibre import get_proxies
from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, Citation, WebLink
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


def download_data(url: str, headers: Sequence[tuple[str, str]] = ()) -> bytes:
    o = opener()
    o.addheaders.extend(headers)
    with o.open(url) as f:
        return f.read()


def update_cached_data(path: str, url: str, headers: Sequence[tuple[str, str]] = ()) -> None:
    raw = download_data(url, headers)
    atomic_write(path, raw)


def schedule_update_of_cached_data(path: str, url: str, headers: Sequence[tuple[str, str]] = ()) -> None:
    mtime = 0
    with suppress(OSError):
        mtime = os.path.getmtime(path)
    modtime = datetime.datetime.fromtimestamp(mtime)
    current_time = datetime.datetime.now()
    if current_time - modtime < datetime.timedelta(days=1):
        return
    Thread(daemon=True, name='AIDataDownload', target=update_cached_data, args=(path, url, headers)).start()


def get_cached_resource(path: str, url: str, headers: Sequence[tuple[str, str]] = ()) -> bytes:
    with suppress(OSError):
        with open(path, 'rb') as f:
            data = f.read()
        schedule_update_of_cached_data(path, url, headers)
        return data
    data = download_data(url, headers)
    atomic_write(path, data)
    return data


def _read_response(buffer: str) -> Iterator[dict[str, Any]]:
    if not buffer.startswith('data: '):
        return
    buffer = buffer[6:].rstrip()
    if buffer == '[DONE]':
        return
    yield json.loads(buffer)


def read_streaming_response(rq: Request, provider_name: str = 'AI provider') -> Iterator[dict[str, Any]]:
    with opener().open(rq) as response:
        if response.status != http.HTTPStatus.OK:
            details = ''
            with suppress(Exception):
                details = response.read().decode('utf-8', 'replace')
            raise Exception(f'Reading from {provider_name} failed with HTTP response status: {response.status} and body: {details}')
        buffer = ''
        for raw_line in response:
            line = raw_line.decode('utf-8')
            if line.strip() == '':
                if buffer:
                    yield from _read_response(buffer)
                    buffer = ''
            else:
                buffer += line
        yield from _read_response(buffer)


def chat_with_error_handler(it: Iterable[ChatResponse]) -> Iterator[ChatResponse]:
    try:
        yield from it
    except HTTPError as e:
        try:
            details = e.fp.read().decode('utf-8', 'replace')
        except Exception:
            details = ''
        try:
            error_json = json.loads(details)
            details = error_json.get('error', {}).get('message', details)
        except Exception:
            pass
        yield ChatResponse(exception=e, error_details=details)
    except URLError as e:
        yield ChatResponse(exception=e, error_details=f'Network error: {e.reason}')
    except Exception as e:
        import traceback
        yield ChatResponse(exception=e, error_details=traceback.format_exc())


class ContentType(Enum):
    unknown = auto()
    markdown = auto()


ref_link_prefix = 'calibre-link-'


def add_citation(text: str, citation: Citation, web_links: Sequence[WebLink], escaped_titles: Sequence[str]) -> str:
    if len(citation.links) == 1:
        wl = web_links[citation.links[0]]
        escaped_title = escaped_titles[citation.links[0]]
        return (
            text[:citation.start_offset] +
            f'[{text[citation.start_offset:citation.end_offset]}]({wl.uri} "{escaped_title}")' +
            text[citation.end_offset:])
    citation_links = []
    for i, link_num in enumerate(citation.links):
        wl = web_links[link_num]
        title = escaped_titles[link_num]
        citation_links.append(f'[{i+1}]({wl.uri} "{title}")')
    return text[:citation.end_offset] + '<sup>' + ', '.join(citation_links) + '</sup>' + text[citation.end_offset:]


def add_citations(text: str, metadata: ChatMessage) -> str:
    citations, web_links = metadata.citations, metadata.web_links
    if not citations or not web_links:
        return text
    escaped_titles = tuple(wl.title.replace('"', r'\"') for wl in web_links)
    for citation in sorted(citations, key=lambda c: c.end_offset, reverse=True):
        if citation.links:
            text = add_citation(text, citation, web_links, escaped_titles)
    return text


class StreamedResponseAccumulator:

    def __init__(self):
        self.all_reasoning = self.all_content = ''
        self.all_reasoning_details: list[dict[str, Any]] = []
        self.metadata = ChatResponse()
        self.messages: list[ChatMessage] = []

    @property
    def content_type(self) -> ContentType:
        return ContentType.markdown if self.metadata.citations else ContentType.unknown

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self.messages)

    def accumulate(self, m: ChatResponse) -> None:
        if m.has_metadata:
            self.metadata = m
        if m.reasoning:
            self.all_reasoning += m.reasoning
            self.all_reasoning_details.extend(m.reasoning_details)
        if m.content:
            self.all_content += m.content

    def finalize(self) -> None:
        self.messages.append(ChatMessage(
            type=ChatMessageType.assistant, query=add_citations(self.all_content, self.metadata), reasoning=self.all_reasoning,
            reasoning_details=tuple(self.all_reasoning_details)
        ))


@lru_cache(2)
def markdown_patterns(detect_code: bool = False) -> dict[re.Pattern[str], float]:
    ans = {re.compile(pat): score for pat, score in {
        # Check for Markdown headers (# Header, ## Subheader, etc.)
        r'(?m)^#{1,6}\s+.+$': 0.15,

        # Check for Markdown two part links and footnotes [..]:
        r'(?m)^\[\.+?\]: ': 0.15,

        # Check for bold (**text**)
        r'\*\*.+?\*\*': 0.05,

        # Check for italics (*text*)
        r'\*[^*\n]+\*': 0.05,

        # Check for unordered lists
        r'(?m)^[\s]*[-*+][\s]+.+$': 0.1,

        # Check for ordered lists
        r'(?m)^[\s]*\d+\.[\s]+.+$': 0.1,

        # Check for blockquotes
        r'(?m)^[\s]*>[\s]*.+$': 0.1,

        # Check for links ([text](url))
        r'\[.+?\]\(.+?\)': 0.15,

        # Check for tables
        r'\|.+\|[\s]*\n\|[\s]*[-:]+[-|\s:]+[\s]*\n': 0.1,

    }.items()}
    if detect_code:
        # Check for inline code (`code`)
        ans[re.compile(r'`[^`\n]+`')] = 0.1
        # Check for code blocks (```code```)
        ans[re.compile(r'```[\s\S]*?```')] = 0.2  # very markdown specific
    return ans


def is_probably_markdown(text: str, threshold: float = -1, detect_code: bool = False) -> bool:
    if threshold < 0:
        threshold = 0.4 if detect_code else 0.2
    if not text:
        return False
    score = 0
    for pattern, pscore in markdown_patterns().items():
        if pattern.search(text) is not None:
            score += pscore
            if score >= threshold:
                return True
    return False


@lru_cache(64)
def response_to_html(text: str, content_type: ContentType = ContentType.unknown, detect_code: bool = False) -> str:
    is_markdown = is_probably_markdown(text, detect_code=detect_code) if ContentType is ContentType.unknown else True
    if is_markdown:
        from calibre.ebooks.txt.processor import create_markdown_object
        md = create_markdown_object(('tables', 'footnotes'))
        return md.convert(text)
    from html import escape
    return escape(text).replace('\n', '<br>')


def develop_text_chat(
    text_chat: Callable[[Iterable[ChatMessage], str], Iterator[ChatResponse]], use_model: str = '',
    messages: Sequence[ChatMessage] = (),
):
    acc = StreamedResponseAccumulator()
    messages = messages or (
        ChatMessage(type=ChatMessageType.system, query='You are William Shakespeare.'),
        ChatMessage('Give me twenty lines on my supremely beautiful wife.')
    )
    for x in text_chat(messages, use_model):
        if x.exception:
            raise SystemExit(str(x.exception) + (': ' + x.error_details) if x.error_details else '')
        acc.accumulate(x)
        if x.content:
            print(end=x.content, flush=True)
    acc.finalize()
    print()
    if acc.all_reasoning:
        print('Reasoning:')
        print(acc.all_reasoning.strip())
    print()
    if acc.metadata.citations:
        print('Response with citations inline:')
        print(acc.messages[-1].query.strip())
    if acc.metadata.has_metadata:
        x = acc.metadata
        print(f'\nCost: {x.cost} {x.currency} Provider: {x.provider!r} Model: {x.model!r}')
    messages = list(messages)
    messages.extend(acc.messages)
    print('Messages:')
    from pprint import pprint
    for msg in messages:
        pprint(msg)


def find_tests() -> None:
    import unittest
    class TestAIUtils(unittest.TestCase):

        def test_ai_response_accumulator(self):
            a = StreamedResponseAccumulator()
            a.accumulate(ChatResponse('an initial msg'))
            a.accumulate(ChatResponse('. more text.'))
            a.accumulate(ChatResponse(has_metadata=True, citations=[
                Citation([0], 3, 3 + len('initial')),
                Citation([0, 1], 3 + len('initial '), 3 + len('initial msg'))
            ], web_links=[WebLink('link1', 'dest1'), WebLink('link2', 'dest2')]
            ))
            a.finalize()
            self.assertEqual(a.messages[-1].query, 'an [initial](dest1 "link1") msg<sup>[1](dest1 "link1"), [2](dest2 "link2")</sup>. more text.')

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAIUtils)
