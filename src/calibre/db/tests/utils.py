#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil

from calibre import walk
from calibre.db.tests.base import BaseTest
from calibre.db.utils import ThumbnailCache


class UtilsTest(BaseTest):

    def setUp(self):
        self.tdir = self.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tdir)

    def init_tc(self, name='1', max_size=1):
        return ThumbnailCache(name=name, location=self.tdir, max_size=max_size, test_mode=True)

    def basic_fill(self, c, num=5):
        total = 0
        for i in range(1, num+1):
            sz = i * 1000
            c.insert(i, i, (('%d'%i) * sz).encode('ascii'))
            total += sz
        return total

    def test_thumbnail_cache(self):  # {{{
        ' Test the operation of the thumbnail cache '
        c = self.init_tc()
        self.assertFalse(hasattr(c, 'total_size'), 'index read on initialization')
        c.invalidate(666)
        self.assertFalse(hasattr(c, 'total_size'), 'index read on invalidate')

        self.assertEqual(self.basic_fill(c), c.total_size)
        self.assertEqual(5, len(c))

        for i in (3, 4, 2, 5, 1):
            data, ts = c[i]
            self.assertEqual(i, ts, 'timestamp not correct')
            self.assertEqual((('%d'%i) * (i*1000)).encode('ascii'), data)
        c.set_group_id('a')
        self.basic_fill(c)
        order = tuple(c.items)
        ts = c.current_size
        c.shutdown()
        c = self.init_tc()
        self.assertEqual(c.current_size, ts, 'size not preserved after restart')
        self.assertEqual(order, tuple(c.items), 'order not preserved after restart')
        c.shutdown()
        c = self.init_tc()
        c.invalidate((1,))
        self.assertIsNone(c[1][1], 'invalidate before load_index() failed')
        c.invalidate((2,))
        self.assertIsNone(c[2][1], 'invalidate after load_index() failed')
        c.set_group_id('a')
        c[1]
        c.set_size(0.001)
        self.assertLessEqual(c.current_size, 1024, 'set_size() failed')
        self.assertEqual(len(c), 1)
        self.assertIn(1, c)
        c.insert(9, 9, b'x' * (c.max_size-1))
        self.assertEqual(len(c), 1)
        self.assertLessEqual(c.current_size, c.max_size, 'insert() did not prune')
        self.assertIn(9, c)
        c.empty()
        self.assertEqual(c.total_size, 0)
        self.assertEqual(len(c), 0)
        self.assertEqual(tuple(walk(c.location)), ())
        c = self.init_tc()
        self.basic_fill(c)
        self.assertEqual(len(c), 5)
        c.set_thumbnail_size(200, 201)
        self.assertIsNone(c[1][0])
        self.assertEqual(len(c), 0)
        self.assertEqual(tuple(walk(c.location)), ())
    # }}}
