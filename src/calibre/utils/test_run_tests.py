#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os
import subprocess
import sys
import tempfile
import unittest

from calibre.utils.serialize import msgpack_dumps
from polyglot.binary import as_hex_unicode


def sample_suite(outcome):
    class SampleTest(unittest.TestCase):
        def success(self):
            pass

        def failure(self):
            self.fail('ordinary failure')

        @unittest.expectedFailure
        def expected_failure(self):
            self.fail('expected failure')

        @unittest.expectedFailure
        def unexpected_success(self):
            pass

    # Reach the normal parallel-runner threshold, with distinct test IDs.
    for i in range(32):
        method = outcome if i == 0 and outcome != 'crash' else 'success'
        setattr(SampleTest, f'test_{i:02}', getattr(SampleTest, method))
    return unittest.defaultTestLoader.loadTestsFromTestCase(SampleTest)


def sample_worker():
    from calibre.utils import run_tests

    outcome = sys.argv[-2]
    run_tests.find_tests = lambda: sample_suite(outcome)
    exec(sys.argv[-1])
    if outcome == 'crash':
        # All results have been flushed and the result pipe is closed.
        os._exit(7)


def sample_main(outcome):
    from calibre.utils.ipc.launch import Worker
    from calibre.utils.run_tests import run_parallel

    os.environ['CALIBRE_SIMPLE_WORKER'] = __name__ + ':sample_worker'
    exe = Worker().executable
    cmd = [exe] if isinstance(exe, str) else exe
    raise SystemExit(run_parallel(sample_suite(outcome), num_workers=2, worker_cmd=cmd + [outcome]))


class TestParallelRunner(unittest.TestCase):
    def run_sample(self, outcome, expected_status):
        from calibre.utils.ipc.simple_worker import start_pipe_worker

        with tempfile.TemporaryDirectory() as tdir:
            env = {'CALIBRE_WORKER_TEMP_DIR': as_hex_unicode(msgpack_dumps(tdir))}
            proc = start_pipe_worker(
                f'from calibre.utils.test_run_tests import sample_main; sample_main({outcome!r})',
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
            self.assertIn('Ran 32 tests', output)
            self.assertNotIn('LOST', output)
            return output

    def test_parallel_worker_exit_status(self):
        self.assertIn('OK: 32', self.run_sample('success', 0))
        output = self.run_sample('crash', 1)
        self.assertIn('Worker process crashed (exit code 7)', output)
        self.assertIn('OK: 32', output)

    def test_parallel_expected_failures(self):
        self.run_sample('expected_failure', 0)
        output = self.run_sample('unexpected_success', 1)
        self.assertIn('Unexpected success', output)
        self.assertIn('FAIL: 1', output)

    def test_parallel_ordinary_failure(self):
        self.assertIn('FAIL: 1', self.run_sample('failure', 1))


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestParallelRunner)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests

    run_tests(find_tests)
