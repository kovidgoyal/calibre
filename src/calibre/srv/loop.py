#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import socket, os, errno, ssl, time, sys
from operator import and_
from Queue import Queue, Full
from threading import Thread, current_thread
from io import DEFAULT_BUFFER_SIZE, BytesIO

from calibre.srv.errors import NonHTTPConnRequest
from calibre.utils.socket_inheritance import set_socket_inherit
from calibre.utils.logging import ThreadSafeLog

def error_codes(*errnames):
    ''' Return error numbers for error names, ignoring non-existent names '''
    ans = {getattr(errno, x, None) for x in errnames}
    ans.discard(None)
    return ans

socket_error_eintr = error_codes("EINTR", "WSAEINTR")

socket_errors_to_ignore = error_codes(
    "EPIPE",
    "EBADF", "WSAEBADF",
    "ENOTSOCK", "WSAENOTSOCK",
    "ETIMEDOUT", "WSAETIMEDOUT",
    "ECONNREFUSED", "WSAECONNREFUSED",
    "ECONNRESET", "WSAECONNRESET",
    "ECONNABORTED", "WSAECONNABORTED",
    "ENETRESET", "WSAENETRESET",
    "EHOSTDOWN", "EHOSTUNREACH",
)
socket_errors_to_ignore.add("timed out")
socket_errors_to_ignore.add("The read operation timed out")
socket_errors_nonblocking = error_codes(
    'EAGAIN', 'EWOULDBLOCK', 'WSAEWOULDBLOCK')

class SocketFile(object):  # {{{
    """Faux file object attached to a socket object. Works with non-blocking
    sockets, unlike the fileobject created by socket.makefile() """

    name = "<socket>"

    __slots__ = (
        "mode", "bufsize", "softspace", "_sock", "_rbufsize", "_wbufsize", "_rbuf", "_wbuf", "_wbuf_len", "_close", 'bytes_read', 'bytes_written',
    )

    def __init__(self, sock, bufsize=-1, close=False):
        self._sock = sock
        self.bytes_read = self.bytes_written = 0
        self.mode = 'r+b'
        self.bufsize = DEFAULT_BUFFER_SIZE if bufsize < 0 else bufsize
        self.softspace = False
        # _rbufsize is the suggested recv buffer size.  It is *strictly*
        # obeyed within readline() for recv calls.  If it is larger than
        # default_bufsize it will be used for recv calls within read().
        if self.bufsize == 0:
            self._rbufsize = 1
        elif bufsize == 1:
            self._rbufsize = DEFAULT_BUFFER_SIZE
        else:
            self._rbufsize = bufsize
        self._wbufsize = bufsize
        # We use BytesIO for the read buffer to avoid holding a list
        # of variously sized string objects which have been known to
        # fragment the heap due to how they are malloc()ed and often
        # realloc()ed down much smaller than their original allocation.
        self._rbuf = BytesIO()
        self._wbuf = []  # A list of strings
        self._wbuf_len = 0
        self._close = close

    @property
    def closed(self):
        return self._sock is None

    def close(self):
        try:
            if self._sock is not None:
                self.flush()
        finally:
            if self._close and self._sock is not None:
                self._sock.close()
            self._sock = None

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    def fileno(self):
        return self._sock.fileno()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def flush(self):
        if self._wbuf_len:
            data = b''.join(self._wbuf)
            self._wbuf = []
            self._wbuf_len = 0
            data_size = len(data)
            view = memoryview(data)
            write_offset = 0
            buffer_size = max(self._rbufsize, DEFAULT_BUFFER_SIZE)
            try:
                while write_offset < data_size:
                    try:
                        bytes_sent = self._sock.send(view[write_offset:write_offset+buffer_size])
                        write_offset += bytes_sent
                        self.bytes_written += bytes_sent
                    except socket.error as e:
                        if e.args[0] not in socket_errors_nonblocking:
                            raise
            finally:
                if write_offset < data_size:
                    remainder = data[write_offset:]
                    self._wbuf.append(remainder)
                    self._wbuf_len = len(remainder)
                del view, data  # explicit free

    def write(self, data):
        if not isinstance(data, bytes):
            raise TypeError('Cannot write data of type: %s to a socket' % type(data))
        if not data:
            return
        self._wbuf.append(data)
        self._wbuf_len += len(data)
        if self._wbufsize == 0 or (self._wbufsize == 1 and b'\n' in data) or (self._wbufsize > 1 and self._wbuf_len >= self._wbufsize):
            self.flush()

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def recv(self, size):
        while True:
            try:
                data = self._sock.recv(size)
                self.bytes_read += len(data)
                return data
            except socket.error, e:
                if e.args[0] not in socket_errors_nonblocking and e.args[0] not in socket_error_eintr:
                    raise

    def read(self, size=-1):
        # Use max, disallow tiny reads in a loop as they are very inefficient.
        # We never leave read() with any leftover data from a new recv() call
        # in our internal buffer.
        rbufsize = max(self._rbufsize, DEFAULT_BUFFER_SIZE)
        buf = self._rbuf
        buf.seek(0, os.SEEK_END)
        if size < 0:
            # Read until EOF
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.recv(rbufsize)
                if not data:
                    break
                buf.write(data)
            return buf.getvalue()
        else:
            # Read until size bytes or EOF seen, whichever comes first
            buf_len = buf.tell()
            if buf_len >= size:
                # Already have size bytes in our buffer?  Extract and return.
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return rv

            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                left = size - buf_len
                # recv() will malloc the amount of memory given as its
                # parameter even though it often returns much less data
                # than that.  The returned data string is short lived
                # as we copy it into a StringIO and free it.  This avoids
                # fragmentation issues on many platforms.
                data = self.recv(left)
                if not data:
                    break
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid buffer data copies when:
                    # - We have no data in our buffer.
                    # AND
                    # - Our call to recv returned exactly the
                    #   number of bytes we were asked to read.
                    return data
                if n == left:
                    buf.write(data)
                    del data  # explicit free
                    break
                assert n <= left, "recv(%d) returned %d bytes" % (left, n)
                buf.write(data)  # noqa
                buf_len += n
                del data  # noqa explicit free
            return buf.getvalue()

    def readline(self, size=-1):
        buf = self._rbuf
        buf.seek(0, 2)  # seek end
        if buf.tell() > 0:
            # check if we already have it in our buffer
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith(b'\n') or len(bline) == size:
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return bline
            del bline
        if size < 0:
            # Read until \n or EOF, whichever comes first
            if self._rbufsize <= 1:
                # Speed up unbuffered case
                buf.seek(0)
                buffers = [buf.read()]
                self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
                data = None
                recv = self.recv
                while data != b'\n':
                    data = recv(1)
                    if not data:
                        break
                    buffers.append(data)
                return b''.join(buffers)

            buf.seek(0, 2)  # seek end
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.recv(self._rbufsize)
                if not data:
                    break
                nl = data.find(b'\n')
                if nl >= 0:
                    nl += 1
                    buf.write(data[:nl])
                    self._rbuf.write(data[nl:])
                    del data
                    break
                buf.write(data)  # noqa
            return buf.getvalue()
        else:
            # Read until size bytes or \n or EOF seen, whichever comes first
            buf.seek(0, os.SEEK_END)
            buf_len = buf.tell()
            if buf_len >= size:
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return rv
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.recv(self._rbufsize)
                if not data:
                    break
                left = size - buf_len
                # did we just receive a newline?
                nl = data.find(b'\n', 0, left)
                if nl >= 0:
                    nl += 1
                    # save the excess data to _rbuf
                    self._rbuf.write(data[nl:])
                    if buf_len:
                        buf.write(data[:nl])
                        break
                    else:
                        # Shortcut.  Avoid data copy through buf when returning
                        # a substring of our first recv().
                        return data[:nl]
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid data copy through buf when
                    # returning exactly all of our first recv().
                    return data
                if n >= left:
                    buf.write(data[:left])
                    self._rbuf.write(data[left:])
                    break
                buf.write(data)
                buf_len += n
            return buf.getvalue()

    def readlines(self, sizehint=0):
        total = 0
        ans = []
        while True:
            line = self.readline()
            if not line:
                break
            ans.append(line)
            total += len(line)
            if sizehint and total >= sizehint:
                break
        return ans

    # Iterator protocols

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line
# }}}

class Connection(object):

    ' A thin wrapper around an active socket '

    remote_addr = None
    remote_port = None
    linger = False

    def __init__(self, server_loop, socket):
        self.server_loop = server_loop
        self.socket = socket
        self.socket_file = SocketFile(socket)

    def http_communicate(self):
        """Read each request and respond appropriately."""
        request_seen = False
        try:
            while True:
                # (re)set req to None so that if something goes wrong in
                # the RequestHandlerClass constructor, the error doesn't
                # get written to the previous request.
                req = None
                req = self.server_loop.http_handler(self)

                # This order of operations should guarantee correct pipelining.
                req.parse_request()
                if not req.ready:
                    # Something went wrong in the parsing (and the server has
                    # probably already made a simple_response). Return and
                    # let the conn close.
                    return

                request_seen = True
                req.respond()
                if req.close_connection:
                    return
        except socket.error as e:
            errnum = e.args[0]
            if errnum.endswith('timed out'):
                # Don't error if we're between requests; only error
                # if 1) no request has been started at all, or 2) we're
                # in the middle of a request.
                if (not request_seen) or (req and req.started_request):
                    # Don't bother writing the 408 if the response
                    # has already started being written.
                    if req and not req.sent_headers:
                        req.simple_response("408 Request Timeout")
            elif errnum not in socket_errors_to_ignore:
                self.server_loop.log.exception("socket.error %s" % repr(errnum))
                if req and not req.sent_headers:
                    req.simple_response("500 Internal Server Error")
            return
        except NonHTTPConnRequest:
            raise
        except Exception:
            self.server_loop.log.exception()
            if req and not req.sent_headers:
                req.simple_response("500 Internal Server Error")

    def nonhttp_communicate(self, data):
        try:
            self.server_loop.nonhttp_handler(self, data)
        except Exception:
            self.server_loop.log.exception()
            return

    def close(self):
        """Close the socket underlying this connection."""
        self.socket_file.close()

        if not self.linger:
            # Python's socket module does NOT call close on the kernel
            # socket when you call socket.close(). We do so manually here
            # because we want this server to send a FIN TCP segment
            # immediately. Note this must be called *before* calling
            # socket.close(), because the latter drops its reference to
            # the kernel socket.
            if hasattr(self.socket, '_sock'):
                self.socket._sock.close()
            self.socket.close()
        else:
            # On the other hand, sometimes we want to hang around for a bit
            # to make sure the client has a chance to read our entire
            # response. Skipping the close() calls here delays the FIN
            # packet until the socket object is garbage-collected later.
            # Someday, perhaps, we'll do the full lingering_close that
            # Apache does, but not today.
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class WorkerThread(Thread):

    daemon = True

    def __init__(self, server_loop):
        self.ready = False
        self.serving = False
        self.server_loop = server_loop
        Thread.__init__(self, name='ServerWorker')

    def run(self):
        try:
            self.ready = True
            while True:
                self.serving = False
                conn = self.server_loop.requests.get()
                if conn is None:
                    return  # Clean exit
                with conn, self:
                    try:
                        conn.http_communicate()
                    except NonHTTPConnRequest as e:
                        conn.nonhttp_communicate(e.data)
        except (KeyboardInterrupt, SystemExit):
            self.server_loop.stop()

    def __enter__(self):
        self.serving = True
        return self

    def __exit__(self, *args):
        self.serving = False


class ThreadPool(object):

    def __init__(self, server_loop, min_threads=10, max_threads=-1, accepted_queue_size=-1, accepted_queue_timeout=10):
        self.server_loop = server_loop
        self.min_threads = max(1, min_threads)
        self.max_threads = max_threads
        self._threads = []
        self._queue = Queue(maxsize=accepted_queue_size)
        self._queue_put_timeout = accepted_queue_timeout
        self.get = self._queue.get

    def start(self):
        """Start the pool of threads."""
        self._threads = [self._spawn_worker() for i in xrange(self.min_threads)]

    @property
    def idle(self):
        return sum(int(not w.serving) for w in self._threads)

    def put(self, obj):
        self._queue.put(obj, block=True, timeout=self._queue_put_timeout)

    def grow(self, amount):
        """Spawn new worker threads (not above self.max_threads)."""
        budget = max(self.max_threads - len(self._threads), 0) if self.max_threads > 0 else sys.maxsize
        n_new = min(amount, budget)
        self._threads.extend([self._spawn_worker() for i in xrange(n_new)])

    def _spawn_worker(self):
        worker = WorkerThread(self.server_loop)
        worker.start()
        return worker

    @staticmethod
    def _all(func, items):
        results = [func(item) for item in items]
        return reduce(and_, results, True)

    def shrink(self, amount):
        """Kill off worker threads (not below self.min_threads)."""
        # Grow/shrink the pool if necessary.
        # Remove any dead threads from our list
        orig = len(self._threads)
        self._threads = [t for t in self._threads if t.is_alive()]
        amount -= orig - len(self._threads)

        # calculate the number of threads above the minimum
        n_extra = max(len(self._threads) - self.min_threads, 0)

        # don't remove more than amount
        n_to_remove = min(amount, n_extra)

        # put shutdown requests on the queue equal to the number of threads
        # to remove. As each request is processed by a worker, that worker
        # will terminate and be culled from the list.
        for n in xrange(n_to_remove):
            self._queue.put(None)

    def stop(self, timeout=5):
        # Must shut down threads here so the code that calls
        # this method can know when all threads are stopped.
        for worker in self._threads:
            self._queue.put(None)

        # Don't join currentThread (when stop is called inside a request).
        current = current_thread()
        if timeout and timeout >= 0:
            endtime = time.time() + timeout
        while self._threads:
            worker = self._threads.pop()
            if worker is not current and worker.isAlive():
                try:
                    if timeout is None or timeout < 0:
                        worker.join()
                    else:
                        remaining_time = endtime - time.time()
                        if remaining_time > 0:
                            worker.join(remaining_time)
                        if worker.is_alive():
                            # We exhausted the timeout.
                            # Forcibly shut down the socket.
                            c = worker.conn
                            if c and not c.socket_file.closed:
                                c.socket.shutdown(socket.SHUT_RDWR)
                            worker.join()
                except (AssertionError,
                        # Ignore repeated Ctrl-C.
                        KeyboardInterrupt):
                    pass

    @property
    def qsize(self):
        return self._queue.qsize()


class ServerLoop(object):

    def __init__(self,
                 bind_address=('localhost', 8080),

                 http_handler=None,
                 nonhttp_handler=None,

                 ssl_certfile=None,
                 ssl_keyfile=None,

                 # Max. queued connections for socket.accept()
                 request_queue_size=5,

                 # Timeout in seconds for accepted connections
                 timeout=10,

                 # Total time in seconds to wait for worker threads to cleanly
                 # exit
                 shutdown_timeout=5,

                 # Minimum number of connection handling threads
                 min_threads=10,
                 # Maximum number of connection handling threads (beyond this
                 # number of connections will be dropped)
                 max_threads=500,

                 # Allow socket pre-allocation, for example, with systemd
                 # socket activation
                 allow_socket_preallocation=True,

                 # no_delay turns on TCP_NODELAY which decreases latency at the cost of
                 # worse overall performance when sending multiple small packets. It
                 # prevents the TCP stack from aggregating multiple small TCP packets.
                 no_delay=True,

                 # A calibre logging object. If None a default log that logs to
                 # stdout is used
                 log=None
    ):
        if http_handler is None:
            def aborth(*args, **kwargs):
                raise NonHTTPConnRequest()
            http_handler = aborth
        self.http_handler = http_handler
        self.nonhttp_handler = nonhttp_handler
        if http_handler is None and nonhttp_handler is None:
            raise ValueError('You must specify at least one protocol handler')
        self.log = log or ThreadSafeLog(level=ThreadSafeLog.DEBUG)
        self.allow_socket_preallocation = allow_socket_preallocation
        self.no_delay = no_delay
        self.request_queue_size = request_queue_size
        self.timeout = timeout
        self.shutdown_timeout = shutdown_timeout
        ba = bind_address
        if not isinstance(ba, basestring):
            ba = tuple(ba)
            if not ba[0]:
                # AI_PASSIVE does not work with host of '' or None
                ba = ('0.0.0.0', ba[1])
        self.bind_address = ba
        self.ssl_context = None
        if ssl_certfile is not None and ssl_keyfile is not None:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile=ssl_certfile, keyfile=ssl_keyfile)

        self.pre_activated_socket = None
        if self.allow_socket_preallocation:
            from calibre.srv.pre_activated import pre_activated_socket
            self.pre_activated_socket = pre_activated_socket()
            if self.pre_activated_socket is not None:
                set_socket_inherit(self.pre_activated_socket, False)
                self.bind_address = self.pre_activated_socket.getsockname()

        self.ready = False
        self.requests = ThreadPool(self, min_threads=min_threads, max_threads=max_threads)

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__, self.bind_address)
    __repr__ = __str__

    def serve_forever(self):
        """ Listen for incoming connections. """

        if self.pre_activated_socket is None:
            # Select the appropriate socket
            if isinstance(self.bind_address, basestring):
                # AF_UNIX socket

                # So we can reuse the socket...
                try:
                    os.unlink(self.bind_address)
                except EnvironmentError:
                    pass

                # So everyone can access the socket...
                try:
                    os.chmod(self.bind_address, 0777)
                except EnvironmentError:
                    pass

                info = [
                    (socket.AF_UNIX, socket.SOCK_STREAM, 0, "", self.bind_address)]
            else:
                # AF_INET or AF_INET6 socket
                # Get the correct address family for our host (allows IPv6
                # addresses)
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
                except socket.error, serr:
                    msg = "%s -- (%s: %s)" % (msg, sa, serr)
                    if self.socket:
                        self.socket.close()
                    self.socket = None
                    continue
                break
            if not self.socket:
                raise socket.error(msg)
        else:
            self.socket = self.pre_activated_socket
            self.pre_activated_socket = None
            self.setup_socket()

        # Timeout so KeyboardInterrupt can be caught on Win32
        self.socket.settimeout(1)
        self.socket.listen(self.request_queue_size)
        ba = self.bind_address
        if isinstance(ba, tuple):
            ba = ':'.join(map(type(''), ba))
        self.log('calibre server listening on', ba)

        # Create worker threads
        self.requests.start()
        self.ready = True

        while self.ready:
            try:
                self.tick()
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                self.log.exception('Error in ServerLoop.tick')

    def setup_socket(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.no_delay and not isinstance(self.bind_address, basestring):
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

    def bind(self, family, atype, proto=0):
        """Create (or recreate) the actual socket object."""
        self.socket = socket.socket(family, atype, proto)
        set_socket_inherit(self.socket, False)
        self.setup_socket()
        self.socket.bind(self.bind_address)

    def tick(self):
        """Accept a new connection and put it on the Queue."""
        try:
            s, addr = self.socket.accept()
            if not self.ready:
                return

            set_socket_inherit(s, False)
            if hasattr(s, 'settimeout'):
                s.settimeout(self.timeout)

            if self.ssl_context is not None:
                try:
                    s = self.ssl_context.wrap_socket(s, server_side=True)
                except ssl.SSLEOFError:
                    return  # Ignore, client closed connection
                except ssl.SSLError as e:
                    if e.args[1].endswith('http request'):
                        msg = (b"The client sent a plain HTTP request, but "
                            b"this server only speaks HTTPS on this port.")
                        response = [
                            b"HTTP/1.1 400 Bad Request\r\n",
                            str("Content-Length: %s\r\n" % len(msg)),
                            b"Content-Type: text/plain\r\n\r\n",
                            msg
                        ]
                        with SocketFile(s._sock) as f:
                            f.write(response)
                        return
                    elif e.args[1].endswith('unknown protocol'):
                        return  # Drop connection
                    raise
                if hasattr(s, 'settimeout'):
                    s.settimeout(self.timeout)

            conn = Connection(self, s)

            if not isinstance(self.bind_address, basestring):
                # optional values
                # Until we do DNS lookups, omit REMOTE_HOST
                if addr is None:  # sometimes this can happen
                    # figure out if AF_INET or AF_INET6.
                    if len(s.getsockname()) == 2:
                        # AF_INET
                        addr = ('0.0.0.0', 0)
                    else:
                        # AF_INET6
                        addr = ('::', 0)
                conn.remote_addr = addr[0]
                conn.remote_port = addr[1]

            try:
                self.requests.put(conn)
            except Full:
                self.log.warn('Server overloaded, dropping connection')
                conn.close()
                return
        except socket.timeout:
            # The only reason for the timeout in start() is so we can
            # notice keyboard interrupts on Win32, which don't interrupt
            # accept() by default
            return
        except socket.error as e:
            if e.args[0] in socket_error_eintr | socket_errors_nonblocking | socket_errors_to_ignore:
                return
            raise

    def stop(self):
        """ Gracefully shutdown the server loop. """
        if not self.ready:
            return
        self.ready = False

        sock = getattr(self, "socket", None)
        if sock is not None:
            if not isinstance(self.bind_address, basestring):
                # Touch our own socket to make accept() return immediately.
                try:
                    host, port = sock.getsockname()[:2]
                except socket.error as e:
                    if e.args[0] not in socket_errors_to_ignore:
                        raise
                else:
                    # Ensure tick() returns by opening a transient connection
                    # to our own listening socket
                    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                                  socket.SOCK_STREAM):
                        af, socktype, proto, canonname, sa = res
                        s = None
                        try:
                            s = socket.socket(af, socktype, proto)
                            s.settimeout(1.0)
                            s.connect((host, port))
                            s.close()
                        except socket.error:
                            if s is not None:
                                s.close()
            if hasattr(sock, "close"):
                sock.close()
            self.socket = None

        self.requests.stop(self.shutdown_timeout)

def echo_handler(conn, data):
    keep_going = True
    while keep_going:
        line = conn.socket_file.readline()
        if not line.rstrip():
            keep_going = False
            line = b'bye\r\n'
        conn.socket_file.write(line)
        conn.socket_file.flush()

if __name__ == '__main__':
    s = ServerLoop(nonhttp_handler=echo_handler)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
