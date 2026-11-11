#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Loc Nguyen

import json
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from calibre.ai import AICapabilities, ChatMessage, NoAPIKey, ResultBlockReason
from calibre.ai.liquid_inference import LiquidInference, backend
from calibre.ai.prefs import encode_secret, override_prefs_for_providers

if TYPE_CHECKING:
    from collections.abc import Iterator
    from http.client import HTTPMessage


class TestLiquidInference(unittest.TestCase):
    def setUp(self) -> None:
        self.prefs = override_prefs_for_providers({LiquidInference.name: {'api_key': encode_secret('test-key'), 'text_model': 'liquid.auto', 'cap_usd': 1.0}})
        self.prefs.__enter__()
        self.addCleanup(self.prefs.__exit__, None, None, None)
        backend.get_available_models.cache_clear()
        self.addCleanup(backend.get_available_models.cache_clear)

    @contextmanager
    def server(self, status: int = 200, events: list[dict[str, Any]] | None = None) -> Iterator[list[tuple[str, HTTPMessage, Any]]]:
        calls = []
        models = {
            'data': [
                {'id': 'liquid.auto', 'modality': 'text'},
                {'id': 'text-model', 'modality': 'text'},
                {'id': 'image-model', 'modality': 'image'},
                {'id': 'embedding-model', 'modality': 'embedding'},
            ]
        }

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                calls.append((self.path, self.headers, None))
                body = json.dumps(models).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, self.headers, body))
                if status != 200:
                    payload = json.dumps({'error': {'message': 'Request refused'}}).encode()
                else:
                    payload = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events or ()).encode() + b'data: [DONE]\n\n'
                self.send_response(status)
                self.send_header('Content-Type', 'text/event-stream' if status == 200 else 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.object(backend, 'API_URL', f'http://127.0.0.1:{server.server_port}/v1'):
                yield calls
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_registered_text_provider(self) -> None:
        from calibre.customize.ui import available_ai_provider_plugins

        plugin = next(p for p in available_ai_provider_plugins() if p.name == LiquidInference.name)
        self.assertEqual(plugin.capabilities, AICapabilities.text_to_text)
        self.assertEqual(plugin.builtin_live_module_name, 'calibre.ai.liquid_inference.backend')

    def test_models_use_unsaved_key_and_exclude_other_modalities(self) -> None:
        with self.server() as calls:
            models = backend.get_available_models(encode_secret('new-key'))
        self.assertEqual(set(models), {'liquid.auto', 'text-model'})
        self.assertEqual(calls[0][0], '/v1/models')
        self.assertEqual(calls[0][1]['Authorization'], 'Bearer new-key')
        self.assertEqual(calls[0][1]['X-Title'], 'Calibre')

    def test_stream_request_and_metadata(self) -> None:
        events = [
            {'choices': [{'delta': {'role': 'assistant'}}]},
            {'choices': [{'delta': {'reasoning_content': 'Consider'}}]},
            {'choices': [{'delta': {'content': 'Hello'}}]},
            {'choices': [{'delta': {}, 'finish_reason': 'stop'}]},
            {'choices': [], 'model': 'actual-model', 'usage': {'total_tokens': 8}},
        ]
        with self.server(events=events) as calls:
            responses = tuple(backend.text_chat([ChatMessage('Explain this passage')], 'text-model'))
        self.assertFalse(any(r.exception for r in responses))
        self.assertEqual(''.join(r.content for r in responses), 'Hello')
        self.assertEqual(''.join(r.reasoning for r in responses), 'Consider')
        self.assertTrue(responses[-1].has_metadata)
        self.assertEqual(responses[-1].model, 'actual-model')
        path, headers, data = calls[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(headers['Authorization'], 'Bearer test-key')
        self.assertEqual(headers['X-Title'], 'Calibre')
        self.assertEqual(headers['x-liquid-cap-usd'], '1.00')
        self.assertEqual(data['model'], 'text-model')
        self.assertEqual(data['messages'], [{'role': 'user', 'content': 'Explain this passage'}])
        self.assertTrue(data['stream'])
        self.assertEqual(data['stream_options'], {'include_usage': True})
        self.assertNotIn('temperature', data)
        self.assertEqual(len(calls), 1)

    def test_metadata_without_usage(self) -> None:
        with self.server(events=[{'choices': [{'delta': {'content': 'Answer'}, 'finish_reason': 'stop'}]}]):
            responses = tuple(backend.text_chat([ChatMessage('Question')]))
        self.assertTrue(responses[-1].has_metadata)
        self.assertEqual(responses[-1].model, 'liquid.auto')
        self.assertEqual(responses[-1].currency, '')

    def test_http_errors_do_not_retry(self) -> None:
        for status in (401, 402, 429, 503):
            with self.subTest(status=status), self.server(status=status) as calls:
                responses = tuple(backend.text_chat([ChatMessage('Question')]))
            self.assertTrue(responses[-1].exception)
            self.assertEqual(len(calls), 1)

    def test_stream_error_stops_after_partial_answer(self) -> None:
        with self.server(events=[{'choices': [{'delta': {'content': 'Partial'}}]}, {'error': {'message': 'Provider disconnected'}}]):
            responses = tuple(backend.text_chat([ChatMessage('Question')]))
        self.assertEqual(responses[0].content, 'Partial')
        self.assertIn('Provider disconnected', str(responses[-1].exception))
        self.assertFalse(responses[-1].has_metadata)

    def test_incomplete_stream_is_not_a_complete_answer(self) -> None:
        with self.server(events=[{'choices': [{'delta': {'content': 'Partial'}}]}]) as calls:
            responses = tuple(backend.text_chat([ChatMessage('Question')]))
        self.assertEqual(responses[0].content, 'Partial')
        self.assertTrue(responses[-1].exception)
        self.assertFalse(responses[-1].has_metadata)
        self.assertEqual(len(calls), 1)

    def test_structured_output_and_invalid_json_do_not_retry(self) -> None:
        from typing import NamedTuple

        class Answer(NamedTuple):
            explanation: str

        for content, valid in (('{"explanation": "A book"}', True), ('not json', False)):
            with self.subTest(content=content), self.server(events=[{'choices': [{'delta': {'content': content}, 'finish_reason': 'stop'}]}]) as calls:
                result = backend.generate_structured_output('Describe it', Answer, 'Use plain words')
            self.assertEqual(len(calls), 1)
            if valid:
                self.assertIsNone(result.exception)
                self.assertEqual(result.data.explanation, 'A book')
            else:
                self.assertTrue(result.exception)

    def test_finish_reasons(self) -> None:
        for reason, expected in (('length', ResultBlockReason.max_tokens), ('content_filter', ResultBlockReason.safety)):
            with self.subTest(reason=reason):
                responses = tuple(backend.as_chat_responses({'choices': [{'delta': {}, 'finish_reason': reason}]}, 'model'))
                self.assertEqual(responses[-1].exception.reason, expected)

    def test_config_settings_and_refresh_preserve_the_selected_model(self) -> None:
        from calibre.ai.liquid_inference.config import ConfigWidget
        from calibre.ai.prefs import decode_secret
        from calibre.gui2 import Application

        app = Application.instance() or Application([])
        widget = ConfigWidget()
        self.assertTrue(widget.is_ready_for_use)
        widget.api_key_edit.setText('unsaved-key')
        widget.model_combo.setCurrentText('chosen-model')
        widget.cap_sb.setValue(0.25)
        settings = widget.settings
        self.assertEqual(decode_secret(settings['api_key']), 'unsaved-key')
        self.assertEqual(settings['cap_usd'], 0.25)
        self.assertEqual(settings['text_model'], 'chosen-model')
        with patch('calibre.ai.liquid_inference.config.set_prefs_for_provider') as save:
            widget.save_settings()
            save.assert_called_once_with(LiquidInference.name, settings)
        with patch('calibre.ai.liquid_inference.config.plugin_for_name') as plugin:
            plugin.return_value.builtin_live_module = backend
            with self.server() as calls:
                widget.refresh_models()
            self.assertEqual(calls[0][1]['Authorization'], 'Bearer unsaved-key')
            self.assertEqual(widget.text_model, 'chosen-model')
            self.assertEqual(widget.model_combo.count(), 2)
        widget.deleteLater()
        app.processEvents()

    def test_missing_key_fails_before_network(self) -> None:
        with override_prefs_for_providers({LiquidInference.name: {'api_key': ''}}):
            self.assertFalse(backend.is_ready_for_use())
            with self.assertRaises(NoAPIKey):
                backend.headers()

    def test_invalid_caps_fail_before_network(self) -> None:
        for cap in (0, -1, float('nan'), float('inf')):
            with self.subTest(cap=cap), override_prefs_for_providers({LiquidInference.name: {'cap_usd': cap}}):
                with self.assertRaises(ValueError):
                    backend.chat_request({})


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestLiquidInference)
