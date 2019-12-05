#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import socket, os, struct, errno, numbers
from collections import deque, namedtuple
from functools import partial
from hashlib import sha1

from calibre.srv.tests.base import BaseTest, TestServer
from calibre.srv.web_socket import (
    GUID_STR, BINARY, TEXT, MessageWriter, create_frame, CLOSE, NORMAL_CLOSE,
    PING, PONG, PROTOCOL_ERROR, CONTINUATION, INCONSISTENT_DATA, CONTROL_CODES)
from calibre.utils.monotonic import monotonic
from calibre.utils.socket_inheritance import set_socket_inherit
from polyglot.builtins import range, unicode_type
from polyglot.binary import as_base64_unicode

HANDSHAKE_STR = '''\
GET / HTTP/1.1\r
Upgrade: websocket\r
Connection: Upgrade\r
Sec-WebSocket-Key: {}\r
Sec-WebSocket-Version: 13\r
''' + '\r\n'

Frame = namedtuple('Frame', 'fin opcode payload')


class WSClient(object):

    def __init__(self, port, timeout=5):
        self.timeout = timeout
        self.socket = socket.create_connection(('localhost', port), timeout)
        set_socket_inherit(self.socket, False)
        self.key = as_base64_unicode(os.urandom(8))
        self.socket.sendall(HANDSHAKE_STR.format(self.key).encode('ascii'))
        self.read_buf = deque()
        self.read_upgrade_response()
        self.mask = memoryview(os.urandom(4))
        self.frames = []

    def read_upgrade_response(self):
        from calibre.srv.http_request import read_headers
        st = monotonic()
        buf, idx = b'', -1
        while idx == -1:
            data = self.socket.recv(1024)
            if not data:
                raise ValueError('Server did not respond with a valid HTTP upgrade response')
            buf += data
            if len(buf) > 4096:
                raise ValueError('Server responded with too much data to HTTP upgrade request')
            if monotonic() - st > self.timeout:
                raise ValueError('Timed out while waiting for server response to HTTP upgrade')
            idx = buf.find(b'\r\n\r\n')
        response, rest = buf[:idx+4], buf[idx+4:]
        if rest:
            self.read_buf.append(rest)
        lines = (x + b'\r\n' for x in response.split(b'\r\n')[:-1])
        rl = next(lines)
        if rl != b'HTTP/1.1 101 Switching Protocols\r\n':
            raise ValueError('Server did not respond with correct switching protocols line')
        headers = read_headers(partial(next, lines))
        key = as_base64_unicode(sha1((self.key + GUID_STR).encode('ascii')).digest())
        if headers.get('Sec-WebSocket-Accept') != key:
            raise ValueError('Server did not respond with correct key in Sec-WebSocket-Accept: {} != {}'.format(
                key, headers.get('Sec-WebSocket-Accept')))

    def recv(self, max_amt):
        if self.read_buf:
            data = self.read_buf.popleft()
            if len(data) <= max_amt:
                return data
            self.read_buf.appendleft(data[max_amt+1:])
            return data[:max_amt + 1]
        try:
            return self.socket.recv(max_amt)
        except socket.error as err:
            if err.errno != errno.ECONNRESET:
                raise
            return b''

    def read_size(self, size):
        ans = b''
        while len(ans) < size:
            d = self.recv(size - len(ans))
            if not d:
                return None
            ans += d
        return ans

    def read_frame(self):
        x = self.read_size(2)
        if x is None:
            return None
        b1, b2 = bytearray(x)
        fin = bool(b1 & 0b10000000)
        opcode = b1 & 0b1111
        masked = b2 & 0b10000000
        if masked:
            raise ValueError('Got a frame with mask bit set from the server')
        payload_length = b2 & 0b01111111
        if payload_length == 126:
            payload_length = struct.unpack(b'!H', self.read_size(2))[0]
        elif payload_length == 127:
            payload_length = struct.unpack(b'!Q', self.read_size(8))[0]
        return Frame(fin, opcode, self.read_size(payload_length))

    def read_messages(self):
        messages, control_frames = [], []
        msg_buf, opcode = [], None
        while True:
            frame = self.read_frame()
            if frame is None or frame.payload is None:
                break
            if frame.opcode in CONTROL_CODES:
                control_frames.append((frame.opcode, frame.payload))
            else:
                if opcode is None:
                    opcode = frame.opcode
                msg_buf.append(frame.payload)
                if frame.fin:
                    data = b''.join(msg_buf)
                    if opcode == TEXT:
                        data = data.decode('utf-8', 'replace')
                    messages.append((opcode, data))
                    msg_buf, opcode = [], None
        return messages, control_frames

    def write_message(self, msg, chunk_size=None):
        if isinstance(msg, tuple):
            opcode, msg = msg
            if isinstance(msg, unicode_type):
                msg = msg.encode('utf-8')
            return self.write_frame(1, opcode, msg)
        w = MessageWriter(msg, self.mask, chunk_size)
        while True:
            frame = w.create_frame()
            if frame is None:
                break
            self.socket.sendall(frame.getvalue())

    def write_frame(self, fin=1, opcode=CLOSE, payload=b'', rsv=0, mask=True):
        frame = create_frame(fin, opcode, payload, rsv=(rsv << 4), mask=self.mask if mask else None)
        self.socket.sendall(frame)

    def write_close(self, code, reason=b''):
        if isinstance(reason, unicode_type):
            reason = reason.encode('utf-8')
        self.write_frame(1, CLOSE, struct.pack(b'!H', code) + reason)


class WSTestServer(TestServer):

    def __init__(self, handler):
        TestServer.__init__(self, None, shutdown_timeout=5)
        from calibre.srv.http_response import create_http_handler
        self.loop.handler = create_http_handler(websocket_handler=handler())

    @property
    def ws_handler(self):
        return self.loop.handler.websocket_handler

    def connect(self):
        return WSClient(self.address[1])


class WebSocketTest(BaseTest):

    def simple_test(self, server, msgs, expected=(), close_code=NORMAL_CLOSE, send_close=True, close_reason=b'NORMAL CLOSE', ignore_send_failures=False):
        client = server.connect()
        for msg in msgs:
            try:
                if isinstance(msg, dict):
                    client.write_frame(**msg)
                else:
                    client.write_message(msg)
            except Exception:
                if not ignore_send_failures:
                    raise

        expected_messages, expected_controls = [], []
        for ex in expected:
            if isinstance(ex, unicode_type):
                ex = TEXT, ex
            elif isinstance(ex, bytes):
                ex = BINARY, ex
            elif isinstance(ex, numbers.Integral):
                ex = ex, b''
            if ex[0] in CONTROL_CODES:
                expected_controls.append(ex)
            else:
                expected_messages.append(ex)
        if send_close:
            client.write_close(close_code, close_reason)
        try:
            messages, control_frames = client.read_messages()
        except ConnectionAbortedError:
            if expected_messages or expected_controls or send_close:
                raise
            return
        self.ae(expected_messages, messages)
        self.assertGreaterEqual(len(control_frames), 1)
        self.ae(expected_controls, control_frames[:-1])
        self.ae(control_frames[-1][0], CLOSE)
        self.ae(close_code, struct.unpack_from(b'!H', control_frames[-1][1], 0)[0])

    def test_websocket_basic(self):
        'Test basic interaction with the websocket server'
        from calibre.srv.web_socket import EchoHandler

        with WSTestServer(EchoHandler) as server:
            simple_test = partial(self.simple_test, server)

            for q in ('', '*' * 125, '*' * 126, '*' * 127, '*' * 128, '*' * 65535, '*' * 65536, "Hello-µ@ßöäüàá-UTF-8!!"):
                simple_test([q], [q])
            for q in (b'', b'\xfe' * 125, b'\xfe' * 126, b'\xfe' * 127, b'\xfe' * 128, b'\xfe' * 65535, b'\xfe' * 65536):
                simple_test([q], [q])

            for payload in [b'', b'ping', b'\x00\xff\xfe\xfd\xfc\xfb\x00\xff', b"\xfe" * 125]:
                simple_test([(PING, payload)], [(PONG, payload)])

            with server.silence_log:
                simple_test([(PING, 'a'*126)], close_code=PROTOCOL_ERROR, send_close=False)

            for payload in (b'', b'pong'):
                simple_test([(PONG, payload)], [])

            fragments = 'Hello-µ@ßöä üàá-UTF-8!!'.split()
            nc = struct.pack(b'!H', NORMAL_CLOSE)

            with server.silence_log:
                # It can happen that the server detects bad data and closes the
                # connection before the client has finished sending all
                # messages, so ignore failures to send packets.
                isf_test = partial(simple_test, ignore_send_failures=True)
                for rsv in range(1, 7):
                    isf_test([{'rsv':rsv, 'opcode':BINARY}], [], close_code=PROTOCOL_ERROR, send_close=False)
                for opcode in (3, 4, 5, 6, 7, 11, 12, 13, 14, 15):
                    isf_test([{'opcode':opcode}], [], close_code=PROTOCOL_ERROR, send_close=False)

                for opcode in (PING, PONG):
                    isf_test([
                        {'opcode':opcode, 'payload':'f1', 'fin':0}, {'opcode':opcode, 'payload':'f2'}
                    ], close_code=PROTOCOL_ERROR, send_close=False)
                isf_test([(CLOSE, nc + b'x'*124)], send_close=False, close_code=PROTOCOL_ERROR)

                for fin in (0, 1):
                    isf_test([{'opcode':0, 'fin': fin, 'payload':b'non-continuation frame'}, 'some text'], close_code=PROTOCOL_ERROR, send_close=False)

                isf_test([
                    {'opcode':TEXT, 'payload':fragments[0], 'fin':0}, {'opcode':CONTINUATION, 'payload':fragments[1]}, {'opcode':0, 'fin':0}
                ], [''.join(fragments)], close_code=PROTOCOL_ERROR, send_close=False)

                isf_test([
                    {'opcode':TEXT, 'payload':fragments[0], 'fin':0}, {'opcode':TEXT, 'payload':fragments[1]},
                ], close_code=PROTOCOL_ERROR, send_close=False)

                frags = []
                for payload in (b'\xce\xba\xe1\xbd\xb9\xcf\x83\xce\xbc\xce\xb5', b'\xed\xa0\x80', b'\x80\x65\x64\x69\x74\x65\x64'):
                    frags.append({'opcode':(CONTINUATION if frags else TEXT), 'fin':1 if len(frags) == 2 else 0, 'payload':payload})
                isf_test(frags, close_code=INCONSISTENT_DATA, send_close=False)

                frags, q = [], b'\xce\xba\xe1\xbd\xb9\xcf\x83\xce\xbc\xce\xb5\xed\xa0\x80\x80\x65\x64\x69\x74\x65\x64'
                for i in range(len(q)):
                    b = q[i:i+1]
                    frags.append({'opcode':(TEXT if i == 0 else CONTINUATION), 'fin':1 if i == len(q)-1 else 0, 'payload':b})
                isf_test(frags, close_code=INCONSISTENT_DATA, send_close=False, ignore_send_failures=True)

                for q in (b'\xce', b'\xce\xba\xe1'):
                    isf_test([{'opcode':TEXT, 'payload':q}], close_code=INCONSISTENT_DATA, send_close=False)

            simple_test([
                {'opcode':TEXT, 'payload':fragments[0], 'fin':0}, {'opcode':CONTINUATION, 'payload':fragments[1]}
            ], [''.join(fragments)])

            simple_test([
                {'opcode':TEXT, 'payload':fragments[0], 'fin':0}, (PING, b'pong'), {'opcode':CONTINUATION, 'payload':fragments[1]}
            ], [(PONG, b'pong'), ''.join(fragments)])

            fragments = '12345'
            simple_test([
                {'opcode':TEXT, 'payload':fragments[0], 'fin':0}, {'opcode':CONTINUATION, 'payload':fragments[1], 'fin':0},
                (PING, b'1'),
                {'opcode':CONTINUATION, 'payload':fragments[2], 'fin':0}, {'opcode':CONTINUATION, 'payload':fragments[3], 'fin':0},
                (PING, b'2'),
                {'opcode':CONTINUATION, 'payload':fragments[4]}
            ], [(PONG, b'1'), (PONG, b'2'), fragments])

            simple_test([
                {'opcode':TEXT, 'fin':0}, {'opcode':CONTINUATION, 'fin':0}, {'opcode':CONTINUATION},], [''])
            simple_test([
                {'opcode':TEXT, 'fin':0}, {'opcode':CONTINUATION, 'fin':0, 'payload':'x'}, {'opcode':CONTINUATION},], ['x'])

            for q in (b'\xc2\xb5', b'\xce\xba\xe1\xbd\xb9\xcf\x83\xce\xbc\xce\xb5', "Hello-µ@ßöäüàá-UTF-8!!".encode('utf-8')):
                frags = []
                for i in range(len(q)):
                    b = q[i:i+1]
                    frags.append({'opcode':(TEXT if i == 0 else CONTINUATION), 'fin':1 if i == len(q)-1 else 0, 'payload':b})
                simple_test(frags, [q.decode('utf-8')])

            simple_test([(CLOSE, nc), (CLOSE, b'\x01\x01')], send_close=False)
            simple_test([(CLOSE, nc), (PING, b'ping')], send_close=False)
            simple_test([(CLOSE, nc), 'xxx'], send_close=False)
            simple_test([{'opcode':TEXT, 'payload':'xxx', 'fin':0}, (CLOSE, nc), {'opcode':CONTINUATION, 'payload':'yyy'}], send_close=False)
            simple_test([(CLOSE, b'')], send_close=False)
            simple_test([(CLOSE, b'\x01')], send_close=False, close_code=PROTOCOL_ERROR)
            simple_test([(CLOSE, nc + b'x'*123)], send_close=False)
            simple_test([(CLOSE, nc + b'a\x80\x80')], send_close=False, close_code=PROTOCOL_ERROR)
            for code in (1000,1001,1002,1003,1007,1008,1009,1010,1011,3000,3999,4000,4999):
                simple_test([(CLOSE, struct.pack(b'!H', code))], send_close=False, close_code=code)
            for code in (0,999,1004,1005,1006,1012,1013,1014,1015,1016,1100,2000,2999):
                simple_test([(CLOSE, struct.pack(b'!H', code))], send_close=False, close_code=PROTOCOL_ERROR)

    def test_websocket_perf(self):
        from calibre.srv.web_socket import EchoHandler
        with WSTestServer(EchoHandler) as server:
            simple_test = partial(self.simple_test, server)
            for sz in (64, 256, 1024, 4096, 8192, 16384):
                sz *= 1024
                t, b = 'a'*sz, b'a'*sz
                simple_test([t, b], [t, b])


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(WebSocketTest)
