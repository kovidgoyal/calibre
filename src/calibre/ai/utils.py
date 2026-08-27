#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import base64
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
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from calibre import get_proxies
from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, Citation, ImageData, ImageGenerationOptions, ImageGenerationResult, WebLink
from calibre.constants import __version__
from calibre.customize import AIProviderPlugin
from calibre.customize.ui import available_ai_provider_plugins
from calibre.utils.localization import _, pgettext

if TYPE_CHECKING:
    from unittest.suite import TestSuite

    from qt.core import QComboBox, QWidget
else:
    TestSuite = QWidget = QComboBox = object


def atomic_write(path: str, data: str | bytes) -> None:
    mode = 'w' if isinstance(data, str) else 'wb'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(mode, delete=False, dir=os.path.dirname(path)) as f:
        f.write(data)
    os.replace(f.name, path)


def opener(user_agent: str = f'calibre {__version__}') -> OpenerDirector:
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
    # Parse a single Server-sent event. Ignores event: and comment lines and
    # joins together multiple data: lines, as per the SSE specification.
    data_lines = []
    for line in buffer.splitlines():
        if line.startswith('data:'):
            data_lines.append(line[5:].strip())
    data = '\n'.join(data_lines)
    if not data or data == '[DONE]':
        return
    yield json.loads(data)


def read_streaming_response(rq: Request, provider_name: str = 'AI provider', timeout: int = 120) -> Iterator[dict[str, Any]]:
    with opener().open(rq, timeout=timeout) as response:
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


def read_json_response(rq: Request, provider_name: str = 'AI provider', timeout: int = 240) -> dict[str, Any]:
    with opener().open(rq, timeout=timeout) as response:
        raw = response.read()
        if response.status != http.HTTPStatus.OK:
            details = raw.decode('utf-8', 'replace')
            raise Exception(f'Reading from {provider_name} failed with HTTP response status: {response.status} and body: {details}')
        return json.loads(raw)


def encode_multipart_formdata(fields: Sequence[tuple[str, str]] = (), files: Sequence[tuple[str, str, str, bytes]] = ()) -> tuple[bytes, str]:
    # Encode fields (name, value) and files (name, filename, mime_type, data)
    # as multipart/form-data returning the body and the Content-Type header value.
    boundary = '-' * 12 + os.urandom(16).hex()
    lines: list[bytes] = []
    for name, value in fields:
        lines.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, filename, mime_type, data in files:
        lines.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {mime_type}\r\n\r\n'.encode())
        lines.append(data)
        lines.append(b'\r\n')
    lines.append(f'--{boundary}--\r\n'.encode())
    return b''.join(lines), f'multipart/form-data; boundary={boundary}'


def image_as_data_url(img: ImageData) -> str:
    return f'data:{img.mime_type};base64,' + base64.standard_b64encode(img.data).decode('ascii')


def image_from_data_url(url: str) -> ImageData:
    metadata, sep, payload = url.partition(',')
    if not sep or not metadata.startswith('data:'):
        raise ValueError(f'Not a valid data URL: {url[:64]!r}')
    mime_type = metadata[len('data:') :].partition(';')[0] or 'image/png'
    return ImageData(data=base64.standard_b64decode(payload), mime_type=mime_type)


def image_data_from_file_path(path: str) -> ImageData:
    import mimetypes

    mime_type = mimetypes.guess_type(path)[0] or 'image/png'
    with open(path, 'rb') as f:
        return ImageData(data=f.read(), mime_type=mime_type)


def image_generation_with_error_handler(func: Callable[[], ImageGenerationResult]) -> ImageGenerationResult:
    try:
        return func()
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
        return ImageGenerationResult(exception=e, error_details=details)
    except URLError as e:
        return ImageGenerationResult(exception=e, error_details=f'Network error: {e.reason}')
    except Exception as e:
        import traceback

        return ImageGenerationResult(exception=e, error_details=traceback.format_exc())


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
            text[: citation.start_offset] + f'[{text[citation.start_offset : citation.end_offset]}]({wl.uri} "{escaped_title}")' + text[citation.end_offset :]
        )
    citation_links = []
    for i, link_num in enumerate(citation.links):
        wl = web_links[link_num]
        title = escaped_titles[link_num]
        citation_links.append(f'[{i + 1}]({wl.uri} "{title}")')
    return text[: citation.end_offset] + '<sup>' + ', '.join(citation_links) + '</sup>' + text[citation.end_offset :]


def add_citations(text: str, metadata: ChatResponse) -> str:
    citations, web_links = metadata.citations, metadata.web_links
    if not citations or not web_links:
        return text
    escaped_titles = tuple(wl.title.replace('"', r'\"') for wl in web_links)
    for citation in sorted(citations, key=lambda c: c.end_offset, reverse=True):
        if citation.links:
            text = add_citation(text, citation, web_links, escaped_titles)
    return text


class StreamedResponseAccumulator:
    def __init__(self) -> None:
        self.all_reasoning = self.all_content = ''
        self.all_reasoning_details: list[dict[str, Any]] = []
        self.metadata = ChatResponse()
        self.messages: list[ChatMessage] = []
        self.response_id: str = ''

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
        if m.id:
            self.response_id = m.id

    def finalize(self) -> None:
        self.messages.append(
            ChatMessage(
                type=ChatMessageType.assistant,
                query=add_citations(self.all_content, self.metadata),
                reasoning=self.all_reasoning,
                reasoning_details=tuple(self.all_reasoning_details),
                response_id=self.response_id,
            )
        )


@lru_cache(2)
def markdown_patterns(detect_code: bool = False) -> dict[re.Pattern[str], float]:
    ans = {
        re.compile(pat): score
        for pat, score in {
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
        }.items()
    }
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
    text_chat: Callable[[Iterable[ChatMessage], str], Iterator[ChatResponse]],
    use_model: str = '',
    messages: Sequence[ChatMessage] = (),
) -> None:
    acc = StreamedResponseAccumulator()
    messages = messages or (
        ChatMessage(type=ChatMessageType.system, query='You are William Shakespeare.'),
        ChatMessage('Write twenty lines on my supremely beautiful wife. Assume she has honey gold skin and a brilliant smile.'),
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


def develop_image_generation(
    generate_image: Callable[..., ImageGenerationResult],
    prompt: str = '',
    source_images: Sequence[ImageData] = (),
    options: ImageGenerationOptions = ImageGenerationOptions(),
    use_model: str = '',
    output_path: str = '',
) -> str:
    prompt = prompt or 'A minimalist line drawing of a cat sitting on a pile of books'
    res = generate_image(prompt, source_images, options, use_model)
    if res.exception is not None:
        raise SystemExit(str(res.exception) + (': ' + res.error_details if res.error_details else ''))
    if res.text:
        print(res.text)
    if res.image is None:
        raise SystemExit('No image was generated')
    if not output_path:
        # Note: not the temporary directory as calibre removes that on exit
        ext = res.image.mime_type.partition('/')[-1] or 'png'
        output_path = os.path.abspath(f'calibre-ai-develop-image.{ext}')
    with open(output_path, 'wb') as f:
        f.write(res.image.data)
    print(f'Image ({res.image.mime_type}) of size {len(res.image.data)} bytes written to:', output_path)
    print(f'Cost: {res.cost} {res.currency} Provider: {res.provider!r} Model: {res.model!r}')
    return output_path


def plugin_for_name(plugin_name: str) -> AIProviderPlugin:
    for plugin in available_ai_provider_plugins():
        if plugin.name == plugin_name:
            return plugin
    raise KeyError(f'No plugin named {plugin_name} is available')


def configure(plugin_name: str, parent: QWidget | None = None) -> None:
    from qt.core import QDialog, QDialogButtonBox, QVBoxLayout

    from calibre.gui2 import ensure_app

    ensure_app(headless=False)
    plugin = plugin_for_name(plugin_name)
    cw = plugin.config_widget()

    class D(QDialog):
        def accept(self) -> None:
            if not cw.validate():
                return
            super().accept()

    d = D(parent=parent)
    l = QVBoxLayout(d)
    l.addWidget(cw)
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    l.addWidget(bb)
    d.resize(d.sizeHint())
    if d.exec() == QDialog.DialogCode.Accepted:
        plugin.save_settings(cw)


def reasoning_strategy_config_widget(current_val: str = 'auto', parent: QWidget | None = None) -> QComboBox:
    from qt.core import QComboBox

    rs = QComboBox(parent)
    rs.addItem(_('Automatic'), 'auto')
    rs.addItem(pgettext('reasoning effort', 'Medium'), 'medium')
    rs.addItem(pgettext('reasoning effort', 'High'), 'high')
    rs.addItem(pgettext('reasoning effort', 'Low'), 'low')
    rs.addItem(_('No reasoning'), 'none')
    rs.setCurrentIndex(max(0, rs.findData(current_val)))
    rs.setToolTip(
        '<p>'
        + _(
            'Select how much "reasoning" AI does when answering queries. More reasoning leads to'
            ' better quality responses at the cost of increased cost and reduced speed.'
        )
    )
    return rs


def model_choice_strategy_config_widget(current_val: str = 'medium', parent: QWidget | None = None) -> QComboBox:
    from qt.core import QComboBox

    ms = QComboBox(parent)
    ms.addItem(_('Cheap and fastest'), 'low')
    ms.addItem(pgettext('model choice', 'Medium'), 'medium')
    ms.addItem(_('High quality, expensive and slower'), 'high')
    ms.setCurrentIndex(max(0, ms.findData(current_val)))
    ms.setToolTip('<p>' + _('The model choice strategy controls how a model to query is chosen. Cheaper and faster models give lower quality results.'))
    return ms


def image_quality_config_widget(current_val: str = 'auto', parent: QWidget | None = None) -> QComboBox:
    from qt.core import QComboBox

    q = QComboBox(parent)
    q.addItem(pgettext('image quality', 'Automatic'), 'auto')
    q.addItem(pgettext('image quality', 'Low'), 'low')
    q.addItem(pgettext('image quality', 'Medium'), 'medium')
    q.addItem(pgettext('image quality', 'High'), 'high')
    q.setCurrentIndex(max(0, q.findData(current_val)))
    q.setToolTip('<p>' + _('The quality of generated images. Higher quality images cost more and take longer to generate.'))
    return q


def find_tests() -> TestSuite:
    import unittest

    class TestAIUtils(unittest.TestCase):
        def test_ai_sse_event_parsing(self) -> None:
            def p(buffer: str) -> list[dict[str, Any]]:
                return list(_read_response(buffer))

            self.assertEqual(p('data: {"a": 1}\n'), [{'a': 1}])
            self.assertEqual(p('event: content_block_delta\ndata: {"a": 1}\n'), [{'a': 1}])
            self.assertEqual(p('data: {"a":\ndata: 1}\n'), [{'a': 1}])
            self.assertEqual(p(': comment\n'), [])
            self.assertEqual(p('data: [DONE]\n'), [])
            self.assertEqual(p('event: ping\n'), [])

        def test_ai_multipart_formdata_encoding(self) -> None:
            from email import message_from_bytes
            from email.message import Message

            body, content_type = encode_multipart_formdata(
                fields=(('prompt', 'a cat'), ('model', 'test-model')),
                files=(('image[]', 'image-0.png', 'image/png', b'\x89PNG\r\n\x1a\nfake'),),
            )
            msg = message_from_bytes(f'Content-Type: {content_type}\r\n\r\n'.encode() + body)
            self.assertTrue(msg.is_multipart())
            parts = msg.get_payload()
            assert isinstance(parts, list)
            self.assertEqual(len(parts), 3)
            prompt_part, model_part, image_part = parts
            assert isinstance(prompt_part, Message)
            assert isinstance(model_part, Message)
            assert isinstance(image_part, Message)
            self.assertEqual(prompt_part.get_payload(decode=True), b'a cat')
            self.assertEqual(model_part.get_payload(decode=True), b'test-model')
            self.assertEqual(image_part.get_payload(decode=True), b'\x89PNG\r\n\x1a\nfake')
            self.assertEqual(image_part.get_content_type(), 'image/png')
            self.assertEqual(image_part.get_filename(), 'image-0.png')

        def test_ai_image_data_url(self) -> None:
            img = ImageData(data=b'some image data', mime_type='image/jpeg')
            self.assertEqual(image_from_data_url(image_as_data_url(img)), img)
            self.assertRaises(ValueError, image_from_data_url, 'https://example.com/image.png')

        def test_ai_openai_chat_response_parsing(self) -> None:
            from calibre.ai.openai.backend import Model, as_chat_responses

            model = Model(id='gpt-5', id_parts=('gpt', '5'), created=datetime.datetime.now(datetime.UTC), version=5.0)

            def p(d: dict[str, Any]) -> list[ChatResponse]:
                return list(as_chat_responses(d, model))

            self.assertEqual(p({'type': 'response.created', 'response': {'id': 'resp_1'}})[0].id, 'resp_1')
            r = p({'type': 'response.output_text.delta', 'delta': 'hello'})[0]
            self.assertEqual(r.content, 'hello')
            self.assertEqual(r.type, ChatMessageType.assistant)
            self.assertEqual(p({'type': 'response.reasoning_summary_text.delta', 'delta': 'hmm'})[0].reasoning, 'hmm')
            r = p({'type': 'response.completed', 'response': {'id': 'resp_1', 'model': 'gpt-5.2', 'usage': {}}})[0]
            self.assertTrue(r.has_metadata)
            self.assertEqual(r.model, 'gpt-5.2')
            r = p({'type': 'response.incomplete', 'response': {'incomplete_details': {'reason': 'max_output_tokens'}}})[0]
            self.assertIsNotNone(r.exception)
            r = p({'type': 'error', 'code': 'ERR', 'message': 'something failed'})[0]
            self.assertIn('something failed', str(r.exception))
            self.assertEqual(p({'type': 'response.output_item.added'}), [])

        def test_ai_openai_image_response_parsing(self) -> None:
            from calibre.ai.openai.backend import image_generation_cost, parse_image_response, size_for_aspect_ratio

            self.assertEqual(size_for_aspect_ratio('auto'), 'auto')
            self.assertEqual(size_for_aspect_ratio('1:1'), '1024x1024')
            self.assertEqual(size_for_aspect_ratio('16:9'), '1536x1024')
            self.assertEqual(size_for_aspect_ratio('3:4'), '1024x1536')

            usage = {'input_tokens': 30, 'output_tokens': 1000, 'input_tokens_details': {'text_tokens': 10, 'image_tokens': 20}}
            cost, currency = image_generation_cost('gpt-image-1', usage)
            self.assertEqual(currency, 'USD')
            self.assertAlmostEqual(cost, (10 * 5 + 20 * 10 + 1000 * 40) / 1e6)
            cost, currency = image_generation_cost('gpt-image-1-mini', usage)
            self.assertAlmostEqual(cost, (10 * 2 + 20 * 2.5 + 1000 * 8) / 1e6)

            d = {'data': [{'b64_json': base64.standard_b64encode(b'image bytes').decode()}], 'usage': usage}
            res = parse_image_response(d, 'gpt-image-1')
            self.assertEqual(res.image, ImageData(data=b'image bytes'))
            self.assertEqual(res.model, 'gpt-image-1')
            self.assertRaises(ValueError, parse_image_response, {'data': []}, 'gpt-image-1')

        def test_ai_grok_chat_response_parsing(self) -> None:
            from calibre.ai.grok.backend import Model, as_chat_responses

            model = Model.from_dict({'id': 'grok-4.6', 'created': 0, 'prompt_text_token_price': 20000, 'completion_text_token_price': 100000})
            self.assertEqual(model.family_version, 4.6)
            self.assertFalse(model.supports_reasoning_effort)
            self.assertTrue(Model.from_dict({'id': 'grok-4.20-0309-reasoning'}).supports_reasoning_effort)
            self.assertFalse(Model.from_dict({'id': 'grok-4.20-0309-non-reasoning'}).supports_reasoning_effort)

            def p(d: dict[str, Any]) -> list[ChatResponse]:
                return list(as_chat_responses(d, model))

            r = p({'id': 'c1', 'choices': [{'delta': {'role': 'assistant', 'content': 'Hello', 'reasoning_content': 'Think'}, 'finish_reason': None}]})[0]
            self.assertEqual(r.content, 'Hello')
            self.assertEqual(r.reasoning, 'Think')
            self.assertEqual(r.id, 'c1')
            self.assertEqual(r.type, ChatMessageType.assistant)
            r = p({
                'id': 'c1',
                'model': 'grok-4.6',
                'choices': [{'delta': {}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 1_000_000, 'completion_tokens': 1_000_000},
                'citations': ['https://example.com'],
            })[-1]
            self.assertTrue(r.has_metadata)
            self.assertEqual((r.model, r.currency), ('grok-4.6', 'USD'))
            self.assertAlmostEqual(r.cost, 2 + 10)  # $2/M input and $10/M output tokens
            self.assertEqual(r.web_links, (WebLink(title='https://example.com', uri='https://example.com'),))
            r = p({'choices': [{'delta': {}, 'finish_reason': 'content_filter'}]})[0]
            self.assertIsNotNone(r.exception)

            from calibre.ai.grok.backend import for_assistant

            self.assertEqual(for_assistant(ChatMessage(type=ChatMessageType.developer, query='q')), {'role': 'system', 'content': 'q'})
            self.assertRaises(ValueError, for_assistant, ChatMessage(type=ChatMessageType.tool, query='q'))

        def test_ai_grok_image_response_parsing(self) -> None:
            from calibre.ai.grok.backend import Model, parse_image_response

            model = Model.from_dict({'id': 'grok-imagine-image-2.0', 'image_price': 4}, generates_images=True)
            self.assertTrue(model.generates_images)
            d = {'data': [{'b64_json': base64.standard_b64encode(b'image bytes').decode(), 'mime_type': 'image/jpeg'}]}
            res = parse_image_response(d, model)
            self.assertEqual(res.image, ImageData(data=b'image bytes', mime_type='image/jpeg'))
            self.assertEqual((res.cost, res.currency), (0.04, 'USD'))
            self.assertEqual(res.model, 'grok-imagine-image-2.0')
            self.assertRaises(ValueError, parse_image_response, {'data': []}, model)

            # Grok cannot edit images, check the error is reported via the
            # result so that the cover dialog can show it, rather than raised
            from calibre.ai.grok.backend import generate_image

            res = generate_image('a prompt', source_images=(ImageData(data=b'image bytes'),))
            self.assertIsInstance(res.exception, ValueError)

        def test_ai_google_image_response_parsing(self) -> None:
            from calibre.ai import AICapabilities, PromptBlocked, ResultBlocked
            from calibre.ai.google.backend import Model, parse_gemini_image_response, parse_imagen_response

            def m(mid: str) -> Model:
                name_parts = tuple(mid.split('-'))
                return Model(
                    name=mid,
                    id=f'models/{mid}',
                    slug=f'models/{mid}',
                    description='',
                    version='1',
                    context_length=1000,
                    output_token_limit=1000,
                    capabilities=AICapabilities.text_to_image,
                    family=name_parts[0],
                    family_version=0,
                    name_parts=name_parts,
                    thinking=False,
                    pricing=None,
                )

            img_b64 = base64.standard_b64encode(b'image bytes').decode()
            d = {
                'candidates': [
                    {
                        'finishReason': 'STOP',
                        'content': {
                            'parts': [
                                {'text': 'here you go'},
                                {'inlineData': {'mimeType': 'image/webp', 'data': img_b64}},
                            ]
                        },
                    }
                ],
                'usageMetadata': {'promptTokenCount': 10, 'totalTokenCount': 20},
            }
            res = parse_gemini_image_response(d, m('gemini-2.5-flash-image'))
            self.assertEqual(res.image, ImageData(data=b'image bytes', mime_type='image/webp'))
            self.assertEqual(res.text, 'here you go')
            self.assertRaises(PromptBlocked, parse_gemini_image_response, {'promptFeedback': {'blockReason': 'SAFETY'}}, m('gemini-2.5-flash-image'))
            self.assertRaises(
                ResultBlocked,
                parse_gemini_image_response,
                {'candidates': [{'finishReason': 'IMAGE_SAFETY', 'content': {'parts': []}}]},
                m('gemini-2.5-flash-image'),
            )

            res = parse_imagen_response({'predictions': [{'bytesBase64Encoded': img_b64, 'mimeType': 'image/png'}]}, m('imagen-4.0-generate-001'))
            self.assertEqual(res.image, ImageData(data=b'image bytes', mime_type='image/png'))
            self.assertEqual((res.cost, res.currency), (0.04, 'USD'))
            self.assertRaises(ResultBlocked, parse_imagen_response, {'predictions': [{'raiFilteredReason': 'unsafe'}]}, m('imagen-4.0-generate-001'))

        def test_ai_open_router_image_response_parsing(self) -> None:
            from calibre.ai.open_router.backend import parse_image_chat_response

            d = {
                'model': 'test/model',
                'provider': 'test-provider',
                'choices': [{'message': {'content': 'done', 'images': [{'image_url': {'url': image_as_data_url(ImageData(b'image bytes'))}}]}}],
                'usage': {'cost': 0.5},
            }
            res = parse_image_chat_response(d, 'test/model')
            self.assertEqual(res.image, ImageData(data=b'image bytes', mime_type='image/png'))
            self.assertEqual(res.text, 'done')
            self.assertEqual(res.cost, 0.5)
            self.assertEqual(res.provider, 'test-provider')
            self.assertRaises(ValueError, parse_image_chat_response, {'choices': [{'message': {'content': 'no image'}}]}, 'test/model')

        def test_ai_response_accumulator(self) -> None:
            a = StreamedResponseAccumulator()
            a.accumulate(ChatResponse('an initial msg'))
            a.accumulate(ChatResponse('. more text.'))
            a.accumulate(
                ChatResponse(
                    has_metadata=True,
                    citations=[
                        Citation([0], 3, 3 + len('initial')),
                        Citation([0, 1], 3 + len('initial '), 3 + len('initial msg')),
                    ],
                    web_links=[WebLink('link1', 'dest1'), WebLink('link2', 'dest2')],
                )
            )
            a.finalize()
            self.assertEqual(
                a.messages[-1].query,
                'an [initial](dest1 "link1") msg<sup>[1](dest1 "link1"), [2](dest2 "link2")</sup>. more text.',
            )

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAIUtils)
