#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import asyncio
import builtins
import os
import sys
import tempfile
import unittest

from calibre.web.automate.worker import make_request, start_server, start_worker


def print(*a, **kw):
    kw['file'] = sys.stderr
    builtins.print(*a, **kw)


class TestAutomateWorker(unittest.TestCase):

    def test_automate_worker(self):
        asyncio.run(name_collision(self))
        worker(self)


async def name_collision(self: TestAutomateWorker):
    path1, srv1 = await start_server(random_suffix='test')
    self.assertEndsWith(path1, '-test')
    path2, srv2 = await start_server(random_suffix='test')
    self.assertNotEqual(path1, path2)
    srv1.close()
    await srv1.wait_closed()
    path3, srv3 = await start_server(random_suffix='test')
    self.assertEndsWith(path3, '-test')
    srv2.close()
    await srv2.wait_closed()
    srv3.close()
    await srv3.wait_closed()


delayed_setup_items = []
handler_items = []


async def delayed_setup_for_test(x=None):
    delayed_setup_items.append(x)


async def handler_for_test(*args):
    if len(args) == 1:
        x, input_data = args[0], None
    else:
        input_data, x = args
    if x == 'raise-exception':
        raise Exception(x)
    handler_items.append((input_data, x))
    return {'arg': x, 'delayed_setup_items': delayed_setup_items}


def finalize(x=None):
    if x:
        os.remove(x[0])


def worker(self: TestAutomateWorker):
    tf = tempfile.NamedTemporaryFile(delete=False)
    tf.close()
    for input_data in (None, [tf.name]):
        path, close = start_worker(
            'calibre.web.automate.test_worker:handler_for_test',
            'calibre.web.automate.test_worker:delayed_setup_for_test',
            'calibre.web.automate.test_worker:finalize',
        input_data=input_data)
        try:
            self.assertTrue(path)
            r = make_request(path, 'some-test-input')
            self.assertFalse(r.exception)
            self.assertEqual({'arg': 'some-test-input', 'delayed_setup_items': [input_data]}, r.response)
            r = make_request(path, 'some-test-input2')
            self.assertEqual({'arg': 'some-test-input2', 'delayed_setup_items': [input_data]}, r.response)
            r = make_request(path, 'raise-exception')
            self.assertIn('raise-exception', r.exception)
        finally:
            close()
        if input_data:
            self.assertFalse(os.path.exists(tf.name))
        else:
            self.assertTrue(os.path.exists(tf.name))


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAutomateWorker)
