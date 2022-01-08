#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import ssl, os, socket, time
from collections import namedtuple
from unittest import skipIf
from glob import glob
from threading import Event

from calibre.srv.pre_activated import has_preactivated_support
from calibre.srv.tests.base import BaseTest, TestServer
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.certgen import create_server_cert
from calibre.utils.monotonic import monotonic
from polyglot import http_client
is_ci = os.environ.get('CI', '').lower() == 'true'


class LoopTest(BaseTest):

    def test_log_rotation(self):
        'Test log rotation'
        from calibre.srv.utils import RotatingLog
        from calibre.ptempfile import TemporaryDirectory
        with TemporaryDirectory() as tdir:
            fname = os.path.join(tdir, 'log')
            l = RotatingLog(fname, max_size=100)

            def history():
                return {int(x.rpartition('.')[-1]) for x in glob(fname + '.*')}

            def log_size():
                ssize = l.outputs[0].stream.tell()
                self.ae(ssize, os.path.getsize(fname))
                return ssize

            self.ae(log_size(), 0)
            l('a' * 99)
            self.ae(log_size(), 100)
            l('b'), l('c')
            self.ae(log_size(), 2)
            self.ae(history(), {1})
            for i in 'abcdefg':
                l(i * 101)
            self.assertLessEqual(log_size(), 100)
            self.ae(history(), {1,2,3,4,5})

    def test_plugins(self):
        'Test plugin semantics'
        class Plugin:

            def __init__(self):
                self.running = Event()
                self.event = Event()
                self.port = None

            def start(self, loop):
                self.running.set()
                self.port = loop.bound_address[1]
                self.event.wait()
                self.running.clear()

            def stop(self):
                self.event.set()

        plugin = Plugin()
        with TestServer(lambda data:'xxx', plugins=(plugin,)) as server:
            self.assertTrue(plugin.running.wait(0.2))
            self.ae(plugin.port, server.address[1])
        self.assertTrue(plugin.event.wait(5))
        self.assertFalse(plugin.running.is_set())

    def test_workers(self):
        ' Test worker semantics '
        with TestServer(lambda data:(data.path[0] + data.read()), worker_count=3) as server:
            self.ae(3, sum(int(w.is_alive()) for w in server.loop.pool.workers))
        self.ae(0, sum(int(w.is_alive()) for w in server.loop.pool.workers))
        # Test shutdown with hung worker
        block = Event()
        with TestServer(lambda data:block.wait(), worker_count=3, shutdown_timeout=0.1, timeout=0.1) as server:
            pool = server.loop.pool
            self.ae(3, sum(int(w.is_alive()) for w in pool.workers))
            conn = server.connect()
            conn.request('GET', '/')
            with self.assertRaises(socket.timeout):
                res = conn.getresponse()
                if int(res.status) == int(http_client.REQUEST_TIMEOUT):
                    raise socket.timeout('Timeout')
                raise Exception('Got unexpected response: code: {} {} headers: {!r} data: {!r}'.format(
                    res.status, res.reason, res.getheaders(), res.read()))
            self.ae(pool.busy, 1)
        self.ae(1, sum(int(w.is_alive()) for w in pool.workers))
        block.set()
        for w in pool.workers:
            w.join()
        self.ae(0, sum(int(w.is_alive()) for w in server.loop.pool.workers))

    def test_fallback_interface(self):
        'Test falling back to default interface'
        with TestServer(lambda data:(data.path[0] + data.read()), listen_on='1.1.1.1', fallback_to_detected_interface=True) as server:
            self.assertNotEqual('1.1.1.1', server.address[0])

    @skipIf(True, 'Disabled as it is failing on the build server, need to investigate')
    def test_bonjour(self):
        'Test advertising via BonJour'
        from calibre.srv.bonjour import BonJour
        from zeroconf import Zeroconf
        b = BonJour(wait_for_stop=False)
        with TestServer(lambda data:(data.path[0] + data.read()), plugins=(b,), shutdown_timeout=5) as server:
            self.assertTrue(b.started.wait(5), 'BonJour not started')
            self.ae(b.advertised_port, server.address[1])
            service = b.services[0]
            self.ae(service.type, '_calibre._tcp.local.')
            r = Zeroconf()
            info = r.get_service_info(service.type, service.name)
            self.assertIsNotNone(info)
            self.ae(info.text, b'\npath=/opds')

        self.assertTrue(b.stopped.wait(5), 'BonJour not stopped')

    def test_dual_stack(self):
        from calibre.srv.loop import IPPROTO_IPV6
        with TestServer(lambda data:(data.path[0] + data.read().decode('utf-8')), listen_on='::') as server:
            self.ae(server.address[0], '::')
            self.ae(server.loop.socket.getsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY), 0)
            conn = server.connect(interface='127.0.0.1')
            conn.request('GET', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, http_client.OK)
            self.ae(r.read(), b'testbody')

    def test_ring_buffer(self):
        'Test the ring buffer used for reads'
        class FakeSocket:

            def __init__(self, data):
                self.data = data

            def recv_into(self, mv):
                sz = min(len(mv), len(self.data))
                mv[:sz] = self.data[:sz]
                return sz
        from calibre.srv.loop import ReadBuffer, READ, WRITE
        buf = ReadBuffer(100)

        def write(data):
            return buf.recv_from(FakeSocket(data))

        def set(data, rpos, wpos, state):
            buf.ba = bytearray(data)
            buf.buf = memoryview(buf.ba)
            buf.read_pos, buf.write_pos, buf.full_state = rpos, wpos, state

        self.ae(b'', buf.read(10))
        self.assertTrue(buf.has_space), self.assertFalse(buf.has_data)
        self.ae(write(b'a'*50), 50)
        self.ae(write(b'a'*50), 50)
        self.ae(write(b'a'*50), 0)
        self.ae(buf.read(1000), bytes(buf.ba))
        self.ae(b'', buf.read(10))
        self.ae(write(b'a'*10), 10)
        numbers = bytes(bytearray(range(10)))
        set(numbers, 1, 3, READ)
        self.ae(buf.read(1), b'\x01')
        self.ae(buf.read(10), b'\x02')
        self.ae(buf.full_state, WRITE)
        set(numbers, 3, 1, READ)
        self.ae(buf.read(1), b'\x03')
        self.ae(buf.read(10), b'\x04\x05\x06\x07\x08\x09\x00')
        set(numbers, 1, 3, READ)
        self.ae(buf.readline(), b'\x01\x02')
        set(b'123\n', 0, 3, READ)
        self.ae(buf.readline(), b'123')
        set(b'123\n', 0, 0, READ)
        self.ae(buf.readline(), b'123\n')
        self.ae(buf.full_state, WRITE)
        set(b'1\n2345', 2, 2, READ)
        self.ae(buf.readline(), b'23451\n')
        self.ae(buf.full_state, WRITE)
        set(b'1\n2345', 1, 1, READ)
        self.ae(buf.readline(), b'\n')
        set(b'1\n2345', 4, 1, READ)
        self.ae(buf.readline(), b'451')
        set(b'1\n2345', 4, 2, READ)
        self.ae(buf.readline(), b'451\n')
        set(b'123456\n7', 4, 2, READ)
        self.ae(buf.readline(), b'56\n')

    def test_ssl(self):
        'Test serving over SSL'
        address = '127.0.0.1'
        with TemporaryDirectory('srv-test-ssl') as tdir:
            cert_file, key_file, ca_file = map(lambda x:os.path.join(tdir, x), 'cka')
            create_server_cert(address, ca_file, cert_file, key_file, key_size=2048)
            ctx = ssl.create_default_context(cafile=ca_file)
            with TestServer(
                    lambda data:(data.path[0] + data.read().decode('utf-8')),
                    ssl_certfile=cert_file, ssl_keyfile=key_file, listen_on=address, port=0) as server:
                conn = http_client.HTTPSConnection(address, server.address[1], context=ctx)
                conn.request('GET', '/test', 'body')
                r = conn.getresponse()
                self.ae(r.status, http_client.OK)
                self.ae(r.read(), b'testbody')
                cert = conn.sock.getpeercert()
                subject = dict(x[0] for x in cert['subject'])
                self.ae(subject['commonName'], address)

    @skipIf(not has_preactivated_support, 'pre_activated_socket not available')
    def test_socket_activation(self):
        'Test socket activation'
        os.closerange(3, 4)  # Ensure the socket gets fileno == 3
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
        self.ae(s.fileno(), 3)
        os.environ['LISTEN_PID'] = str(os.getpid())
        os.environ['LISTEN_FDS'] = '1'
        with TestServer(lambda data:(data.path[0].encode('utf-8') + data.read()), allow_socket_preallocation=True) as server:
            conn = server.connect()
            conn.request('GET', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, http_client.OK)
            self.ae(r.read(), b'testbody')
            self.ae(server.loop.bound_address[1], port)

    def test_monotonic(self):
        'Test the monotonic() clock'
        a = monotonic()
        b = monotonic()
        self.assertGreaterEqual(b, a)
        a = monotonic()
        time.sleep(0.1)
        b = monotonic()
        self.assertGreaterEqual(b, a)
        self.assertGreaterEqual(b - a, 0.09)
        self.assertLessEqual(b - a, 0.4)

    def test_jobs_manager(self):
        'Test the jobs manager'
        from calibre.srv.jobs import JobsManager
        O = namedtuple('O', 'max_jobs max_job_time')

        class FakeLog(list):

            def error(self, *args):
                self.append(' '.join(args))
        s = ('waiting', 'running')
        jm = JobsManager(O(1, 5), FakeLog())

        def job_status(jid):
            return jm.job_status(jid)[0]

        # Start jobs
        job_id1 = jm.start_job('simple test', 'calibre.srv.jobs', 'sleep_test', args=(1.0,))
        job_id2 = jm.start_job('t2', 'calibre.srv.jobs', 'sleep_test', args=(3,))
        job_id3 = jm.start_job('err test', 'calibre.srv.jobs', 'error_test')

        # Job 1
        job_id = job_id1
        status = jm.job_status(job_id)[0]
        self.assertIn(status, s)
        for jid in (job_id2, job_id3):
            self.assertEqual(job_status(jid), 'waiting')
        while job_status(job_id) in s:
            time.sleep(0.01)
        status, result, tb, was_aborted = jm.job_status(job_id)
        self.assertEqual(status, 'finished')
        self.assertFalse(was_aborted)
        self.assertFalse(tb)
        self.assertEqual(result, 1.0)

        # Job 2
        job_id = job_id2
        while job_status(job_id) == 'waiting':
            time.sleep(0.01)
        self.assertEqual('running', job_status(job_id))
        jm.abort_job(job_id)
        self.assertIn(jm.wait_for_running_job(job_id), (True, None))
        status, result, tb, was_aborted = jm.job_status(job_id)
        self.assertEqual('finished', status)
        self.assertTrue(was_aborted)

        # Job 3
        job_id = job_id3
        while job_status(job_id) == 'waiting':
            time.sleep(0.01)
        self.assertIn(jm.wait_for_running_job(job_id), (True, None))
        status, result, tb, was_aborted = jm.job_status(job_id)
        self.assertEqual(status, 'finished')
        self.assertFalse(was_aborted)
        self.assertTrue(tb)
        self.assertIn('a testing error', tb)
        jm.start_job('simple test', 'calibre.srv.jobs', 'sleep_test', args=(1.0,))
        jm.shutdown(), jm.wait_for_shutdown(monotonic() + 1)


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(LoopTest)
