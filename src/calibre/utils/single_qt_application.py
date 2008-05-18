#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Enforces running of only a single application instance and allows for messaging between
applications using a local socket.
'''
import atexit

from PyQt4.QtCore import QByteArray, QDataStream, QIODevice, SIGNAL, QObject, Qt
from PyQt4.QtNetwork import QLocalSocket, QLocalServer

timeout_read    = 5000
timeout_connect = 500

def write_message(socket, message, timeout = 5000):
    block = QByteArray()
    out = QDataStream(block, QIODevice.WriteOnly)

    out.writeInt32(0)
    out.writeString(message)
    out.device().seek(0)
    out.writeInt32(len(message))

    socket.write(block)
    
    return getattr(socket, 'state', lambda : None)() == QLocalSocket.ConnectedState and \
            bool(socket.waitForBytesWritten(timeout))

def read_message(socket):
    if getattr(socket, 'state', lambda : None)() != QLocalSocket.ConnectedState:
        return ''
    
    while socket.bytesAvailable() < 4:
        if not socket.waitForReadyRead(timeout_read):
            return ''

    message = ''
    ins = QDataStream(socket)
    block_size = ins.readInt32()
    while socket.bytesAvailable() < block_size:
        if not socket.waitForReadyRead(timeout_read):
            return message
    return str(ins.readString())

class Connection(QObject):
    
    def __init__(self, socket, name):
        QObject.__init__(self)
        self.socket = socket
        self.name   = name
        self.magic = self.name + ':'
        self.connect(self.socket, SIGNAL('readyRead()'), self.read_msg, Qt.QueuedConnection)
        self.write_succeeded = write_message(self.socket, self.name)
        self.connect(self.socket, SIGNAL('disconnected()'), self.disconnected)
        if not self.write_succeeded:
            self.socket.abort()
            
    def read_msg(self):
        while self.socket.bytesAvailable() > 0:
            msg = read_message(self.socket)
            if msg.startswith(self.magic):
                self.emit(SIGNAL('message_received(PyQt_PyObject)'), msg[len(self.magic):])
        
    def disconnected(self):
        self.emit(SIGNAL('disconnected()'))
        

class LocalServer(QLocalServer):
    
    def __init__(self, server_id, parent=None):
        QLocalServer.__init__(self, parent)
        self.server_id = str(server_id) 
        self.mr = lambda x : self.emit(SIGNAL('message_received(PyQt_PyObject)'), x)
        self.connections = []
        self.connect(self, SIGNAL('newConnection()'), self.new_connection)
        
    def new_connection(self):
        socket = self.nextPendingConnection()
        conn = Connection(socket, self.server_id)
        if conn.socket.state() != QLocalSocket.UnconnectedState:
            self.connect(conn, SIGNAL('message_received(PyQt_PyObject)'), self.mr)
            self.connect(conn, SIGNAL('disconnected()'), self.free)
            self.connections.append(conn)
    
    def free(self):
        pop = []
        for conn in self.connections:
            if conn.socket.state() == QLocalSocket.UnconnectedState:
                pop.append(conn)
                
        for conn in pop:
            self.connections.remove(conn)
                
        
        
class SingleApplication(QObject):
    
    def __init__(self, name, parent=None, server_name='calibre_server'):
        QObject.__init__(self, parent)
        self.name = name
        self.server_name = server_name
        self.running = False
        self.mr = lambda x : self.emit(SIGNAL('message_received(PyQt_PyObject)'), x)
        
        # Check if server is already running
        self.socket = QLocalSocket(self)
        self.socket.connectToServer(self.server_name)
        if self.socket.waitForConnected(timeout_connect):
            msg = read_message(self.socket)
            if msg == self.name:
                self.running = True
        
            
        # Start server
        self.server = None
        if not self.running:
            self.socket.abort()
            self.socket = None
            self.server = LocalServer(self.name, self)
            self.connect(self.server, SIGNAL('message_received(PyQt_PyObject)'), 
                         self.mr, Qt.QueuedConnection)
            
            if not self.server.listen(self.server_name):
                if not self.server.listen(self.server_name):
                    self.server = None
        if self.server is not None:
            atexit.register(self.server.close)
                
                
    def is_running(self, name=None):
        return self.running if name is None else SingleApplication().is_running()
    
    def send_message(self, msg, timeout=3000):
        return self.running and write_message(self.socket, self.name+':'+msg, timeout)
    
if __name__ == '__main__':
    from PyQt4.Qt import QWidget, QApplication
    class Test(QWidget):
        
        def __init__(self, sa):
            QWidget.__init__(self)
            self.sa = sa
            self.connect(sa, SIGNAL('message_received(PyQt_PyObject)'), self.mr)
            
        def mr(self, msg):
            print 'Message received:', msg
            
    app = QApplication([])
    app.connect(app, SIGNAL('lastWindowClosed()'), app.quit)
    sa = SingleApplication('test SA')
    if sa.is_running():
        sa.send_message('test message')
    else:
        widget = Test(sa)
        widget.show()
        app.exec_()
            
    
    