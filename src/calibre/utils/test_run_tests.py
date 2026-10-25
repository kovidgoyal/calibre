#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from calibre.utils.serialize import msgpack_dumps
from polyglot.binary import as_hex_unicode


def sample_suite(outcome, size=32):
    class SampleTest(unittest.TestCase):
        def success(self):
            pass

        def failure(self):
            self.fail('ordinary failure')

        def error(self):
            raise ValueError('ordinary error')

        @unittest.skip('skip control')
        def skipped(self):
            pass

        @unittest.expectedFailure
        def expected_failure(self):
            self.fail('expected failure')

        @unittest.expectedFailure
        def unexpected_success(self):
            pass

    methods = {
        'success': (),
        'xfail': ('expected_failure',),
        'xpass': ('unexpected_success',),
        'multiple_xpass': ('unexpected_success', 'unexpected_success'),
        'mixed': ('unexpected_success', 'unexpected_success', 'expected_failure', 'failure', 'error', 'skipped'),
    }[outcome]
    # Unique IDs keep the runner from deduplicating the successful controls.
    for i in range(size):
        method = methods[i] if i < len(methods) else 'success'
        setattr(SampleTest, f'test_{i:02}', getattr(SampleTest, method))
    return unittest.defaultTestLoader.loadTestsFromTestCase(SampleTest)


def sample_worker():
    from calibre.utils import run_tests

    outcome, size = sys.argv[-3:-1]
    run_tests.find_tests = lambda: sample_suite(outcome, int(size))
    exec(sys.argv[-1])


def sample_main(outcome, size, buffer):
    from calibre.utils.ipc.launch import Worker
    from calibre.utils.run_tests import run_cli

    os.environ['CALIBRE_SIMPLE_WORKER'] = __name__ + ':sample_worker'
    exe = Worker().executable
    cmd = [exe] if isinstance(exe, str) else exe
    # Exercise real workers without spawning one for every CPU on CI runners.
    with patch('os.cpu_count', return_value=2):
        run_cli(sample_suite(outcome, size), buffer=buffer, worker_cmd=cmd + [outcome, str(size)])


class TestXPASS(unittest.TestCase):
    def run_sample(self, outcome, expected_status, size=32, buffer=True):
        from calibre.utils.ipc.simple_worker import start_pipe_worker

        with tempfile.TemporaryDirectory() as tdir:
            # Each nested runner needs its own w0/w1 temporary directories.
            env = {'CALIBRE_WORKER_TEMP_DIR': as_hex_unicode(msgpack_dumps(tdir))}
            proc = start_pipe_worker(
                f'from calibre.utils.test_run_tests import sample_main; sample_main({outcome!r}, {size}, {buffer!r})',
                env=env,
                stderr=subprocess.STDOUT,
            )
            try:
                output = proc.communicate(timeout=60)[0].decode('utf-8', errors='replace')
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
            self.assertEqual(proc.returncode, expected_status, output)
            self.assertNotIn('LOST', output)
            return output

    def check_summary(self, output, **expected):
        summary = next((line for line in output.splitlines() if line.startswith('OK: ')), '')
        self.assertTrue(summary, output)
        counts = dict(re.findall(r'([A-Z]+): (\d+)', summary))
        for key, value in expected.items():
            self.assertEqual(int(counts.get(key, 0)), value, output)

    def check_xpass_diagnostics(self, output, outcome, count):
        diagnostics = [line for line in output.splitlines() if line.startswith('UNEXPECTED SUCCESS: ')]
        self.assertEqual(len(diagnostics), count, output)
        tests = list(sample_suite(outcome))
        for test in tests[:count]:
            self.assertIn('UNEXPECTED SUCCESS: ' + test.id(), diagnostics, output)

    def test_parallel_xpass(self):
        output = self.run_sample('xpass', 1)
        self.check_summary(output, OK=31, FAIL=0, ERROR=0, XFAIL=0, XPASS=1)
        self.check_xpass_diagnostics(output, 'xpass', 1)
        self.check_summary(self.run_sample('success', 0), OK=32, FAIL=0, ERROR=0, XPASS=0)
        self.check_summary(self.run_sample('xfail', 0), OK=31, FAIL=0, ERROR=0, XFAIL=1, XPASS=0)

    def test_parallel_xpass_aggregation(self):
        # test_00 and test_01 go to different workers in the round-robin split.
        output = self.run_sample('multiple_xpass', 1)
        self.check_summary(output, OK=30, FAIL=0, ERROR=0, XFAIL=0, XPASS=2)
        self.check_xpass_diagnostics(output, 'multiple_xpass', 2)
        output = self.run_sample('mixed', 1)
        self.check_summary(output, OK=26, FAIL=1, ERROR=1, SKIP=1, XFAIL=1, XPASS=2)
        self.check_xpass_diagnostics(output, 'mixed', 2)

    def test_xpass_cli_fallback(self):
        self.run_sample('xpass', 1, size=1)
        self.run_sample('xfail', 0, size=1)

    def test_xpass_serial_cli(self):
        self.run_sample('xpass', 1, buffer=False)
        self.run_sample('xfail', 0, buffer=False)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestXPASS)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests

    run_tests(find_tests)
