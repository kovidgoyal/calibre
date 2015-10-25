#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from calibre.srv.tests.base import BaseTest, TestServer

class TestHandler(object):

    def __init__(self):
        self.connections = {}
        self.connection_state = {}

    def conn(self, cid):
        ans = self.ws_connections.get(cid)
        if ans is not None:
            ans = ans()
        return ans

    def handle_websocket_upgrade(self, connection_id, connection_ref, inheaders):
        self.ws_connections[connection_id] = connection_ref

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
            self.conn(connection_id).send_websocket_message(msg)


class WSTestServer(TestServer):

    def __init__(self, handler=TestHandler):
        TestServer.__init__(self, None)
        from calibre.srv.http_response import create_http_handler
        self.loop.handler = create_http_handler(websocket_handler=handler())

    @property
    def ws_handler(self):
        return self.loop.handler.websocket_handler

class WebSocketTest(BaseTest):

    def test_websocket_basic(self):
        'Test basic interaction with the websocket server'

        with WSTestServer(EchoHandler):
            pass
