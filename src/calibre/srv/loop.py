#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import ssl, socket, select, os, traceback
from io import BytesIO
from Queue import Empty, Full
from functools import partial

from calibre import as_unicode
from calibre.ptempfile import TemporaryDirectory
from calibre.srv.errors import JobQueueFull
from calibre.srv.pool import ThreadPool, PluginPool
from calibre.srv.opts import Options
from calibre.srv.jobs import JobsManager
from calibre.srv.utils import (
    socket_errors_socket_closed, socket_errors_nonblocking, HandleInterrupt,
    socket_errors_eintr, start_cork, stop_cork, DESIRED_SEND_BUFFER_SIZE,
    create_sock_pair)
from calibre.utils.socket_inheritance import set_socket_inherit
from calibre.utils.logging import ThreadSafeLog
from calibre.utils.monotonic import monotonic
from calibre.utils.mdns import get_external_ip

READ, WRITE, RDWR, WAIT = 'READ', 'WRITE', 'RDWR', 'WAIT'
WAKEUP, JOB_DONE = bytes(bytearray(xrange(2)))


class ReadBuffer(object):  # {{{

    ' A ring buffer used to speed up the readline() implementation by minimizing recv() calls '

    __slots__ = ('ba', 'buf', 'read_pos', 'write_pos', 'full_state')

    def __init__(self, size=4096):
        self.ba = bytearray(size)
        self.buf = memoryview(self.ba)
        self.read_pos = 0
        self.write_pos = 0
        self.full_state = WRITE

    @property
    def has_data(self):
        return self.read_pos != self.write_pos or self.full_state is READ

    @property
    def has_space(self):
        return self.read_pos != self.write_pos or self.full_state is WRITE

    def read(self, size):
        # Read from this buffer, retuning the read bytes as a bytestring
        if self.read_pos == self.write_pos and self.full_state is WRITE:
            return b''
        if self.read_pos < self.write_pos:
            sz = min(self.write_pos - self.read_pos, size)
            npos = self.read_pos + sz
            ans = self.buf[self.read_pos:npos].tobytes()
            self.read_pos = npos
            if self.read_pos == self.write_pos:
                self.full_state = WRITE
        else:
            sz = min(size, len(self.buf) - self.read_pos)
            ans = self.buf[self.read_pos:self.read_pos + sz].tobytes()
            self.read_pos = (self.read_pos + sz) % len(self.buf)
            if self.read_pos == self.write_pos:
                self.full_state = WRITE
            if size > sz and self.read_pos < self.write_pos:
                ans += self.read(size - len(ans))
        return ans

    def recv_from(self, socket):
        # Write into this buffer from socket, return number of bytes written
        if self.read_pos == self.write_pos and self.full_state is READ:
            return 0
        if self.write_pos < self.read_pos:
            num = socket.recv_into(self.buf[self.write_pos:self.read_pos])
            self.write_pos += num
        else:
            num = socket.recv_into(self.buf[self.write_pos:])
            self.write_pos = (self.write_pos + num) % len(self.buf)
        if self.write_pos == self.read_pos:
            self.full_state = READ
        return num

    def readline(self):
        # Return whatever is in the buffer up to (and including) the first \n
        # If no \n is present, returns everything
        if self.read_pos == self.write_pos and self.full_state is WRITE:
            return b''
        if self.read_pos < self.write_pos:
            pos = self.ba.find(b'\n', self.read_pos, self.write_pos)
            if pos < 0:
                pos = self.write_pos - 1
            ans = self.buf[self.read_pos:pos + 1].tobytes()
            self.read_pos = (pos + 1) % len(self.buf)
            if self.read_pos == self.write_pos:
                self.full_state = WRITE
        else:
            pos = self.ba.find(b'\n', self.read_pos)
            if pos < 0:
                pos = self.ba.find(b'\n', 0, self.write_pos)
                if pos < 0:
                    pos = self.write_pos - 1
                ans = self.buf[self.read_pos:].tobytes() + self.buf[:pos+1].tobytes()
                self.read_pos = (pos + 1) % len(self.buf)
                if self.read_pos == self.write_pos:
                    self.full_state = WRITE
            else:
                ans = self.buf[self.read_pos:pos + 1].tobytes()
                self.read_pos = (pos + 1) % len(self.buf)
                if self.read_pos == self.write_pos:
                    self.full_state = WRITE
        return ans
    # }}}


class Connection(object):  # {{{

    def __init__(self, socket, opts, ssl_context, tdir, addr, pool, log, access_log, wakeup):
        self.opts, self.pool, self.log, self.wakeup, self.access_log = opts, pool, log, wakeup, access_log
        try:
            self.remote_addr = addr[0]
            self.remote_port = addr[1]
        except Exception:
            # In case addr is None, which can occassionally happen
            self.remote_addr = self.remote_port = None
        self.is_local_connection = self.remote_addr in ('127.0.0.1', '::1')
        self.orig_send_bufsize = self.send_bufsize = 4096
        self.tdir = tdir
        self.ssl_context = ssl_context
        self.wait_for = READ
        self.response_started = False
        self.read_buffer = ReadBuffer()
        self.handle_event = None
        if self.ssl_context is not None:
            self.ready = False
            self.socket = self.ssl_context.wrap_socket(socket, server_side=True, do_handshake_on_connect=False)
            self.set_state(RDWR, self.do_ssl_handshake)
        else:
            self.socket = socket
            self.connection_ready()
        self.last_activity = monotonic()
        self.ready = True

    def optimize_for_sending_packet(self):
        start_cork(self.socket)
        self.orig_send_bufsize = self.send_bufsize = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        if self.send_bufsize < DESIRED_SEND_BUFFER_SIZE:
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, DESIRED_SEND_BUFFER_SIZE)
            except socket.error:
                pass
            else:
                self.send_bufsize = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)

    def end_send_optimization(self):
        stop_cork(self.socket)
        if self.send_bufsize != self.orig_send_bufsize:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.orig_send_bufsize)

    def set_state(self, wait_for, func, *args, **kwargs):
        self.wait_for = wait_for
        if args or kwargs:
            pfunc = partial(func, *args, **kwargs)
            pfunc.__name__ = func.__name__
            func = pfunc
        self.handle_event = func

    def do_ssl_handshake(self, event):
        try:
            self.socket._sslobj.do_handshake()
        except ssl.SSLWantReadError:
            self.set_state(READ, self.do_ssl_handshake)
        except ssl.SSLWantWriteError:
            self.set_state(WRITE, self.do_ssl_handshake)
        else:
            self.connection_ready()

    def send(self, data):
        try:
            ret = self.socket.send(data)
            self.last_activity = monotonic()
            return ret
        except socket.error as e:
            if e.errno in socket_errors_nonblocking or e.errno in socket_errors_eintr:
                return 0
            elif e.errno in socket_errors_socket_closed:
                self.ready = False
                return 0
            raise

    def recv(self, amt):
        # If there is data in the read buffer we have to return only that,
        # since we dont know if the socket has signalled it is ready for
        # reading
        if self.read_buffer.has_data:
            return self.read_buffer.read(amt)
        # read buffer is empty, so read directly from socket
        try:
            data = self.socket.recv(amt)
            self.last_activity = monotonic()
            if not data:
                # a closed connection is indicated by signaling
                # a read condition, and having recv() return 0.
                self.ready = False
                return b''
            return data
        except socket.error as e:
            if e.errno in socket_errors_nonblocking or e.errno in socket_errors_eintr:
                return b''
            if e.errno in socket_errors_socket_closed:
                self.ready = False
                return b''
            raise

    def recv_into(self, buf, amt=0):
        amt = amt or len(buf)
        if self.read_buffer.has_data:
            data = self.read_buffer.read(amt)
            buf[0:len(data)] = data
            return len(data)
        try:
            bytes_read = self.socket.recv_into(buf, amt)
            self.last_activity = monotonic()
            if bytes_read == 0:
                # a closed connection is indicated by signaling
                # a read condition, and having recv() return 0.
                self.ready = False
                return 0
            return bytes_read
        except socket.error as e:
            if e.errno in socket_errors_nonblocking or e.errno in socket_errors_eintr:
                return 0
            if e.errno in socket_errors_socket_closed:
                self.ready = False
                return 0
            raise
        except ssl.SSLWantReadError:
            return 0

    def fill_read_buffer(self):
        try:
            num = self.read_buffer.recv_from(self.socket)
            self.last_activity = monotonic()
            if not num:
                # a closed connection is indicated by signaling
                # a read condition, and having recv() return 0.
                self.ready = False
        except socket.error as e:
            if e.errno in socket_errors_nonblocking or e.errno in socket_errors_eintr:
                return
            if e.errno in socket_errors_socket_closed:
                self.ready = False
                return
            raise
        except ssl.SSLWantReadError:
            return

    def close(self):
        self.ready = False
        self.handle_event = None  # prevent reference cycles
        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass

    def queue_job(self, func, *args):
        if args:
            func = partial(func, *args)
        try:
            self.pool.put_nowait(self.socket.fileno(), func)
        except Full:
            raise JobQueueFull()
        self.set_state(WAIT, self._job_done)

    def _job_done(self, event):
        self.job_done(*event)

    def job_done(self, ok, result):
        raise NotImplementedError()

    @property
    def state_description(self):
        return ''

    def report_unhandled_exception(self, e, formatted_traceback):
        pass

    def report_busy(self):
        pass

    def connection_ready(self):
        raise NotImplementedError()

    def handle_timeout(self):
        return False
# }}}


class ServerLoop(object):

    LISTENING_MSG = 'calibre server listening on'

    def __init__(
        self,
        handler,
        opts=None,
        plugins=(),
        # A calibre logging object. If None, a default log that logs to
        # stdout is used
        log=None,
        # A calibre logging object for access logging, by default no access
        # logging is performed
        access_log=None
    ):
        self.ready = False
        self.handler = handler
        self.opts = opts or Options()
        self.log = log or ThreadSafeLog(level=ThreadSafeLog.DEBUG)
        self.jobs_manager = JobsManager(self.opts, self.log)
        self.access_log = access_log

        ba = (self.opts.listen_on, int(self.opts.port))
        if not ba[0]:
            # AI_PASSIVE does not work with host of '' or None
            ba = ('0.0.0.0', ba[1])
        self.bind_address = ba
        self.bound_address = None
        self.connection_map = {}

        self.ssl_context = None
        if self.opts.ssl_certfile is not None and self.opts.ssl_keyfile is not None:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile=self.opts.ssl_certfile, keyfile=self.opts.ssl_keyfile)

        self.pre_activated_socket = None
        if self.opts.allow_socket_preallocation:
            from calibre.srv.pre_activated import pre_activated_socket
            self.pre_activated_socket = pre_activated_socket()
            if self.pre_activated_socket is not None:
                set_socket_inherit(self.pre_activated_socket, False)
                self.bind_address = self.pre_activated_socket.getsockname()

        self.create_control_connection()
        self.pool = ThreadPool(self.log, self.job_completed, count=self.opts.worker_count)
        self.plugin_pool = PluginPool(self, plugins)

    def create_control_connection(self):
        self.control_in, self.control_out = create_sock_pair()

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__, self.bind_address)
    __repr__ = __str__

    @property
    def num_active_connections(self):
        return len(self.connection_map)

    def do_bind(self):
        # Get the correct address family for our host (allows IPv6 addresses)
        host, port = self.bind_address
        try:
            info = socket.getaddrinfo(
                host, port, socket.AF_UNSPEC,
                socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
        except socket.gaierror:
            if ':' in host:
                info = [(socket.AF_INET6, socket.SOCK_STREAM,
                        0, "", self.bind_address + (0, 0))]
            else:
                info = [(socket.AF_INET, socket.SOCK_STREAM,
                        0, "", self.bind_address)]

        self.socket = None
        msg = "No socket could be created"
        for res in info:
            af, socktype, proto, canonname, sa = res
            try:
                self.bind(af, socktype, proto)
            except socket.error as serr:
                msg = "%s -- (%s: %s)" % (msg, sa, as_unicode(serr))
                if self.socket:
                    self.socket.close()
                self.socket = None
                continue
            break
        if not self.socket:
            raise socket.error(msg)

    def initialize_socket(self):
        if self.pre_activated_socket is None:
            try:
                self.do_bind()
            except socket.error as err:
                if not self.opts.fallback_to_detected_interface:
                    raise
                ip = get_external_ip()
                if ip == self.bind_address[0]:
                    raise
                self.log.warn('Failed to bind to %s with error: %s. Trying to bind to the default interface: %s instead' % (
                    self.bind_address[0], as_unicode(err), ip))
                self.bind_address = (ip, self.bind_address[1])
                self.do_bind()
        else:
            self.socket = self.pre_activated_socket
            self.pre_activated_socket = None
            self.setup_socket()

    def serve(self):
        self.connection_map = {}
        self.socket.listen(min(socket.SOMAXCONN, 128))
        self.bound_address = ba = self.socket.getsockname()
        if isinstance(ba, tuple):
            ba = ':'.join(map(type(''), ba))
        self.pool.start()
        with TemporaryDirectory(prefix='srv-') as tdir:
            self.tdir = tdir
            self.ready = True
            if self.LISTENING_MSG:
                self.log(self.LISTENING_MSG, ba)
            self.plugin_pool.start()

            while self.ready:
                try:
                    self.tick()
                except SystemExit:
                    self.shutdown()
                    raise
                except KeyboardInterrupt:
                    break
                except:
                    self.log.exception('Error in ServerLoop.tick')
            self.shutdown()

    def serve_forever(self):
        """ Listen for incoming connections. """
        self.initialize_socket()
        self.serve()

    def setup_socket(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # If listening on the IPV6 any address ('::' = IN6ADDR_ANY),
        # activate dual-stack.
        if (hasattr(socket, 'AF_INET6') and self.socket.family == socket.AF_INET6 and
                self.bind_address[0] in ('::', '::0', '::0.0.0.0')):
            try:
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, socket.error):
                # Apparently, the socket option is not available in
                # this machine's TCP stack
                pass
        self.socket.setblocking(0)

    def bind(self, family, atype, proto=0):
        '''Create (or recreate) the actual socket object.'''
        self.socket = socket.socket(family, atype, proto)
        set_socket_inherit(self.socket, False)
        self.setup_socket()
        self.socket.bind(self.bind_address)

    def tick(self):
        now = monotonic()
        read_needed, write_needed, readable, remove = [], [], [], []
        for s, conn in self.connection_map.iteritems():
            if now - conn.last_activity > self.opts.timeout:
                if conn.handle_timeout():
                    conn.last_activity = now
                else:
                    remove.append((s, conn))
                    continue
            wf = conn.wait_for
            if wf is READ:
                (readable if conn.read_buffer.has_data else read_needed).append(s)
            elif wf is WRITE:
                write_needed.append(s)
            elif wf is RDWR:
                write_needed.append(s)
                (readable if conn.read_buffer.has_data else read_needed).append(s)

        for s, conn in remove:
            self.log('Closing connection because of extended inactivity: %s' % conn.state_description)
            self.close(s, conn)

        if readable:
            writable = []
        else:
            try:
                readable, writable, _ = select.select([self.socket.fileno(), self.control_out.fileno()] + read_needed, write_needed, [], self.opts.timeout)
            except ValueError:  # self.socket.fileno() == -1
                self.ready = False
                self.log.error('Listening socket was unexpectedly terminated')
                return
            except (select.error, socket.error) as e:
                # select.error has no errno attribute. errno is instead
                # e.args[0]
                if getattr(e, 'errno', e.args[0]) in socket_errors_eintr:
                    return
                for s, conn in tuple(self.connection_map.iteritems()):
                    try:
                        select.select([s], [], [], 0)
                    except (select.error, socket.error) as e:
                        if getattr(e, 'errno', e.args[0]) not in socket_errors_eintr:
                            self.close(s, conn)  # Bad socket, discard
                return

        if not self.ready:
            return

        ignore = set()
        for s, conn, event in self.get_actions(readable, writable):
            if s in ignore:
                continue
            try:
                conn.handle_event(event)
                if not conn.ready:
                    self.close(s, conn)
            except JobQueueFull:
                self.log.exception('Server busy handling request: %s' % conn.state_description)
                if conn.ready:
                    if conn.response_started:
                        self.close(s, conn)
                    else:
                        try:
                            conn.report_busy()
                        except Exception:
                            self.close(s, conn)
            except Exception as e:
                ignore.add(s)
                self.log.exception('Unhandled exception in state: %s' % conn.state_description)
                if conn.ready:
                    if conn.response_started:
                        self.close(s, conn)
                    else:
                        try:
                            conn.report_unhandled_exception(e, traceback.format_exc())
                        except Exception:
                            self.close(s, conn)
                else:
                    self.log.error('Error in SSL handshake, terminating connection: %s' % as_unicode(e))
                    self.close(s, conn)

    def wakeup(self):
        self.control_in.sendall(WAKEUP)

    def job_completed(self):
        self.control_in.sendall(JOB_DONE)

    def dispatch_job_results(self):
        while True:
            try:
                s, ok, result = self.pool.get_nowait()
            except Empty:
                break
            conn = self.connection_map.get(s)
            if conn is not None:
                yield s, conn, (ok, result)

    def close(self, s, conn):
        self.connection_map.pop(s, None)
        conn.close()

    def get_actions(self, readable, writable):
        listener = self.socket.fileno()
        control = self.control_out.fileno()
        for s in readable:
            if s == listener:
                sock, addr = self.accept()
                if sock is not None:
                    s = sock.fileno()
                    if s > -1:
                        self.connection_map[s] = conn = self.handler(
                            sock, self.opts, self.ssl_context, self.tdir, addr, self.pool, self.log, self.access_log, self.wakeup)
                        if self.ssl_context is not None:
                            yield s, conn, RDWR
            elif s == control:
                try:
                    c = self.control_out.recv(1)
                except socket.error:
                    if not self.ready:
                        return
                    self.log.error('Control socket raised an error, resetting')
                    self.create_control_connection()
                    continue
                if c == JOB_DONE:
                    for s, conn, event in self.dispatch_job_results():
                        yield s, conn, event
                elif c == WAKEUP:
                    pass
                elif not c:
                    if not self.ready:
                        return
                    self.log.error('Control socket failed to recv(), resetting')
                    self.create_control_connection()
            else:
                yield s, self.connection_map[s], READ
        for s in writable:
            try:
                conn = self.connection_map[s]
            except KeyError:
                continue  # Happens if connection was closed during read phase
            yield s, conn, WRITE

    def accept(self):
        try:
            sock, addr = self.socket.accept()
            set_socket_inherit(sock, False), sock.setblocking(False)
            return sock, addr
        except socket.error:
            return None, None

    def stop(self):
        self.ready = False
        self.wakeup()

    def shutdown(self):
        self.jobs_manager.shutdown()
        try:
            if getattr(self, 'socket', None):
                self.socket.close()
                self.socket = None
        except socket.error:
            pass
        for s, conn in tuple(self.connection_map.iteritems()):
            self.close(s, conn)
        wait_till = monotonic() + self.opts.shutdown_timeout
        for pool in (self.plugin_pool, self.pool):
            pool.stop(wait_till)
            if pool.workers:
                self.log.warn('Failed to shutdown %d workers in %s cleanly' % (len(pool.workers), pool.__class__.__name__))
        self.jobs_manager.wait_for_shutdown(wait_till)


class EchoLine(Connection):  # {{{

    bye_after_echo = False

    def connection_ready(self):
        self.rbuf = BytesIO()
        self.set_state(READ, self.read_line)

    def read_line(self, event):
        data = self.recv(1)
        if data:
            self.rbuf.write(data)
            if b'\n' == data:
                if self.rbuf.tell() < 3:
                    # Empty line
                    self.rbuf = BytesIO(b'bye' + self.rbuf.getvalue())
                    self.bye_after_echo = True
                self.set_state(WRITE, self.echo)
                self.rbuf.seek(0)

    def echo(self, event):
        pos = self.rbuf.tell()
        self.rbuf.seek(0, os.SEEK_END)
        left = self.rbuf.tell() - pos
        self.rbuf.seek(pos)
        sent = self.send(self.rbuf.read(512))
        if sent == left:
            self.rbuf = BytesIO()
            self.set_state(READ, self.read_line)
            if self.bye_after_echo:
                self.ready = False
        else:
            self.rbuf.seek(pos + sent)
# }}}


if __name__ == '__main__':
    s = ServerLoop(EchoLine)
    with HandleInterrupt(s.wakeup):
        s.serve_forever()
