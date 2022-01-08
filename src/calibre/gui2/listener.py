#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import os
import socket
from contextlib import closing
from functools import partial
from itertools import count
from qt.core import (
    QAbstractSocket, QByteArray, QLocalServer, QLocalSocket, pyqtSignal
)

from calibre.utils.ipc import gui_socket_address


def unix_socket(timeout=10):
    ans = socket.socket(socket.AF_UNIX)
    ans.settimeout(timeout)
    return ans


class Listener(QLocalServer):

    message_received = pyqtSignal(object)

    def __init__(self, address=None, parent=None):
        QLocalServer.__init__(self, parent)
        self.address = address or gui_socket_address()
        self.uses_filesystem = self.address[0] not in '\0\\'
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.newConnection.connect(self.on_new_connection)
        self.connection_id = count()
        self.pending_messages = {}

    def start_listening(self):
        if self.address.startswith('\0'):
            s = unix_socket()
            s.bind(self.address)
            s.listen(16)
            if not self.listen(s.detach()):
                raise OSError(f'Could not start Listener for IPC at address @{self.address[1:]} with error: {self.errorString()}')
        else:
            if not self.listen(self.address):
                if self.serverError() == QAbstractSocket.SocketError.AddressInUseError and self.uses_filesystem:
                    self.removeServer(self.address)
                    if self.listen(self.address):
                        return
                code = self.serverError()
                if code == QAbstractSocket.SocketError.AddressInUseError:
                    raise OSError(errno.EADDRINUSE, os.strerror(errno.EADDRINUSE), self.address)
                raise OSError(f'Could not start Listener for IPC at address {self.address} with error: {self.errorString()}')

    def on_new_connection(self):
        while True:
            s = self.nextPendingConnection()
            if s is None:
                break
            cid = next(self.connection_id)
            self.pending_messages[cid] = b''
            s.readyRead.connect(partial(self.on_ready_read, cid, s))
            s.disconnected.connect(partial(self.on_disconnect, cid, s))

    def on_ready_read(self, connection_id, q_local_socket):
        num = q_local_socket.bytesAvailable()
        if num > 0:
            self.pending_messages[connection_id] += bytes(q_local_socket.readAll())

    def on_disconnect(self, connection_id, q_local_socket):
        self.on_ready_read(connection_id, q_local_socket)
        q_local_socket.close()
        q_local_socket.readyRead.disconnect()
        q_local_socket.disconnected.disconnect()
        q_local_socket.deleteLater()
        self.message_received.emit(self.pending_messages.pop(connection_id, b''))


def send_message_in_process(msg, address=None, timeout=5):
    address = address or gui_socket_address()
    if isinstance(msg, str):
        msg = msg.encode('utf-8')
    s = QLocalSocket()
    qt_timeout = int(timeout * 1000)
    if address.startswith('\0'):
        ps = unix_socket(timeout)
        ps.connect(address)
        s.setSocketDescriptor(ps.detach())
    else:
        s.connectToServer(address)
        if not s.waitForConnected(qt_timeout):
            raise OSError(f'Failed to connect to Listener at: {address} with error: {s.errorString()}')
    data = QByteArray(msg)
    while True:
        written = s.write(data)
        if not s.waitForBytesWritten(qt_timeout):
            raise OSError(f'Failed to write data to address: {s.serverName()} with error: {s.errorString()}')
        if written >= len(data):
            break
        data = data.right(len(data) - written)


def send_message_via_worker(msg, address=None, timeout=5, wait_till_sent=False):
    # On Windows sending a message in a process that also is listening on the
    # same named pipe in a different thread deadlocks, so we do the actual sending in
    # a simple worker process
    import json
    import subprocess

    from calibre.startup import get_debug_executable
    cmd = get_debug_executable() + [
        '-c', 'from calibre.gui2.listener import *; import sys, json;'
        'send_message_implementation(sys.stdin.buffer.read(), address=json.loads(sys.argv[-2]), timeout=int(sys.argv[-1]))',
        json.dumps(address), str(timeout)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if isinstance(msg, str):
        msg = msg.encode('utf-8')
    with closing(p.stdin):
        p.stdin.write(msg)
    if wait_till_sent:
        return p.wait(timeout=timeout) == 0


def test():
    from qt.core import QApplication, QLabel, QTimer
    app = QApplication([])
    l = QLabel()
    l.setText('Waiting for message...')

    def show_message(msg):
        print(msg)
        l.setText(msg.decode('utf-8'))

    def send():
        send_message_via_worker('hello!', wait_till_sent=False)

    QTimer.singleShot(1000, send)
    s = Listener(parent=l)
    s.start_listening()
    print('Listening at:', s.serverName(), s.isListening())
    s.message_received.connect(show_message)

    l.show()
    app.exec()
    del app


if __name__ == '__main__':
    test()
