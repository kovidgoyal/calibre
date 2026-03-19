#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import asyncio
import unittest

from calibre.web.automate.worker import start_server


class TestAutomateWorker(unittest.TestCase):

    def test_automate_worker(self):
        asyncio.run(name_collision(self))


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


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAutomateWorker)
