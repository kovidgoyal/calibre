#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import socket, os, struct
from base64 import standard_b64encode
from collections import deque, namedtuple
from functools import partial
from hashlib import sha1

from calibre.srv.tests.base import BaseTest, TestServer
from calibre.srv.web_socket import (
    GUID_STR, BINARY, TEXT, MessageWriter, create_frame, CLOSE, NORMAL_CLOSE,
    PING, PONG, PROTOCOL_ERROR)
from calibre.utils.monotonic import monotonic
from calibre.utils.socket_inheritance import set_socket_inherit

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
        self.key = standard_b64encode(os.urandom(8))
        self.socket.sendall(HANDSHAKE_STR.format(self.key).encode('ascii'))
        self.read_buf = deque()
        self.read_upgrade_response()
        self.mask = os.urandom(4)
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
        key = standard_b64encode(sha1(self.key + GUID_STR).digest())
        if headers.get('Sec-WebSocket-Accept') != key:
            raise ValueError('Server did not respond with correct key in Sec-WebSocket-Accept')

    def recv(self, max_amt):
        if self.read_buf:
            data = self.read_buf.popleft()
            if len(data) <= max_amt:
                return data
            self.read_buf.appendleft(data[max_amt+1:])
            return data[:max_amt + 1]
        return self.socket.recv(max_amt)

    def read_size(self, size):
        ans = b''
        while len(ans) < size:
            d = self.recv(size - len(ans))
            if not d:
                raise ValueError('Connection to server closed, no data received')
            ans += d
        return ans

    def read_frame(self):
        b1, b2 = bytearray(self.read_size(2))
        fin = b1 & 0b10000000
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

    def read_message(self):
        frames = []
        while True:
            frame = self.read_frame()
            frames.append(frame)
            if frame.fin:
                break
        ans, opcode = [], None
        for frame in frames:
            if frame is frames[0]:
                opcode = frame.opcode
                if frame.fin == 0 and frame.opcode not in (BINARY, TEXT):
                    raise ValueError('Server sent a start frame with fin=0 and bad opcode')
            ans.append(frame.payload)
        ans = b''.join(ans)
        if opcode == TEXT:
            ans = ans.decode('utf-8')
        return opcode, ans

    def write_message(self, msg, chunk_size=None):
        if isinstance(msg, tuple):
            opcode, msg = msg
            if isinstance(msg, type('')):
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
        if isinstance(reason, type('')):
            reason = reason.encode('utf-8')
        self.write_frame(1, CLOSE, struct.pack(b'!H', code) + reason)


class TestHandler(object):

    def __init__(self):
        self.connections = {}
        self.connection_state = {}

    def conn(self, cid):
        ans = self.connections.get(cid)
        if ans is not None:
            ans = ans()
        return ans

    def handle_websocket_upgrade(self, connection_id, connection_ref, inheaders):
        self.connections[connection_id] = connection_ref

    def handle_websocket_data(self, data, message_starting, message_finished, connection_id):
        pass

    def handle_websocket_close(self, connection_id):
        self.connections.pop(connection_id, None)

class EchoHandler(TestHandler):

    def __init__(self):
        TestHandler.__init__(self)
        self.msg_buf = []

    def handle_websocket_data(self, data, message_starting, message_finished, connection_id):
        if message_starting:
            self.msg_buf = []
        self.msg_buf.append(data)
        if message_finished:
            j = '' if isinstance(self.msg_buf[0], type('')) else b''
            msg = j.join(self.msg_buf)
            self.msg_buf = []
            self.conn(connection_id).send_websocket_message(msg, wakeup=False)


class WSTestServer(TestServer):

    def __init__(self, handler=TestHandler):
        TestServer.__init__(self, None)
        from calibre.srv.http_response import create_http_handler
        self.loop.handler = create_http_handler(websocket_handler=handler())

    @property
    def ws_handler(self):
        return self.loop.handler.websocket_handler

    def connect(self):
        return WSClient(self.address[1])

class WebSocketTest(BaseTest):

    def simple_test(self, client, msgs, expected=(), close_code=NORMAL_CLOSE, send_close=True, close_reason=b'NORMAL CLOSE'):
        for msg in msgs:
            if isinstance(msg, dict):
                client.write_frame(**msg)
            else:
                client.write_message(msg)
        for ex in expected:
            if isinstance(ex, type('')):
                ex = TEXT, ex
            elif isinstance(ex, bytes):
                ex = BINARY, ex
            elif isinstance(ex, int):
                ex = ex, b''
            self.ae(ex, client.read_message())
        if send_close:
            client.write_close(close_code, close_reason)
        opcode, data = client.read_message()
        self.ae(opcode, CLOSE)
        self.ae(close_code, struct.unpack_from(b'!H', data, 0)[0])

    def test_websocket_basic(self):
        'Test basic interaction with the websocket server'

        with WSTestServer(EchoHandler) as server:
            for q in ('', '*' * 125, '*' * 126, '*' * 127, '*' * 128, '*' * 65535, '*' * 65536):
                client = server.connect()
                self.simple_test(client, [q], [q])
            for q in (b'', b'\xfe' * 125, b'\xfe' * 126, b'\xfe' * 127, b'\xfe' * 128, b'\xfe' * 65535, b'\xfe' * 65536):
                client = server.connect()
                self.simple_test(client, [q], [q])

            for payload in ['', 'ping', b'\x00\xff\xfe\xfd\xfc\xfb\x00\xff', b"\xfe" * 125]:
                client = server.connect()
                self.simple_test(client, [(PING, payload)], [(PONG, payload)])

            client = server.connect()
            with server.silence_log:
                self.simple_test(client, [(PING, 'a'*126)], close_code=PROTOCOL_ERROR, send_close=False)

            for payload in (b'', b'pong'):
                client = server.connect()
                self.simple_test(client, [(PONG, payload)], [])

            with server.silence_log:
                for rsv in xrange(1, 7):
                    client = server.connect()
                    self.simple_test(client, [{'rsv':rsv, 'opcode':BINARY}], [], close_code=PROTOCOL_ERROR, send_close=False)
                for opcode in (3, 4, 5, 6, 7, 11, 12, 13, 14, 15):
                    client = server.connect()
                    self.simple_test(client, [{'opcode':opcode}], [], close_code=PROTOCOL_ERROR, send_close=False)
