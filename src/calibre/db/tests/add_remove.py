#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from io import BytesIO
from tempfile import NamedTemporaryFile

from calibre.db.tests.base import BaseTest
from calibre.ptempfile import PersistentTemporaryFile

def import_test(replacement_data, replacement_fmt=None):
    def func(path, fmt):
        if not path.endswith('.'+fmt.lower()):
            raise AssertionError('path extension does not match format')
        ext = (replacement_fmt or fmt).lower()
        with PersistentTemporaryFile('.'+ext) as f:
            f.write(replacement_data)
        return f.name
    return func

class AddRemoveTest(BaseTest):

    def test_add_format(self):  # {{{
        'Test adding formats to an existing book record'
        af, ae, at = self.assertFalse, self.assertEqual, self.assertTrue

        cache = self.init_cache()
        table = cache.fields['formats'].table
        NF = b'test_add_formatxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

        # Test that replace=False works
        previous = cache.format(1, 'FMT1')
        af(cache.add_format(1, 'FMT1', BytesIO(NF), replace=False))
        ae(previous, cache.format(1, 'FMT1'))

        # Test that replace=True works
        lm = cache.field_for('last_modified', 1)
        at(cache.add_format(1, 'FMT1', BytesIO(NF), replace=True))
        ae(NF, cache.format(1, 'FMT1'))
        ae(cache.format_metadata(1, 'FMT1')['size'], len(NF))
        at(cache.field_for('size', 1) >= len(NF))
        at(cache.field_for('last_modified', 1) > lm)
        ae(('FMT2','FMT1'), cache.formats(1))
        at(1 in table.col_book_map['FMT1'])

        # Test adding a format to a record with no formats
        at(cache.add_format(3, 'FMT1', BytesIO(NF), replace=True))
        ae(NF, cache.format(3, 'FMT1'))
        ae(cache.format_metadata(3, 'FMT1')['size'], len(NF))
        ae(('FMT1',), cache.formats(3))
        at(3 in table.col_book_map['FMT1'])
        at(cache.add_format(3, 'FMTX', BytesIO(NF), replace=True))
        at(3 in table.col_book_map['FMTX'])
        ae(('FMT1','FMTX'), cache.formats(3))

        # Test running on import plugins
        import calibre.db.cache as c
        orig = c.run_plugins_on_import
        try:
            c.run_plugins_on_import = import_test(b'replacement data')
            at(cache.add_format(3, 'REPL', BytesIO(NF)))
            ae(b'replacement data', cache.format(3, 'REPL'))
            c.run_plugins_on_import = import_test(b'replacement data2', 'REPL2')
            with NamedTemporaryFile(suffix='_test_add_format.repl') as f:
                f.write(NF)
                f.seek(0)
                at(cache.add_format(3, 'REPL', BytesIO(NF)))
                ae(b'replacement data', cache.format(3, 'REPL'))
                ae(b'replacement data2', cache.format(3, 'REPL2'))

        finally:
            c.run_plugins_on_import = orig

        # Test adding FMT with path
        with NamedTemporaryFile(suffix='_test_add_format.fmt9') as f:
            f.write(NF)
            f.seek(0)
            at(cache.add_format(2, 'FMT9', f))
            ae(NF, cache.format(2, 'FMT9'))
            ae(cache.format_metadata(2, 'FMT9')['size'], len(NF))
            at(cache.field_for('size', 2) >= len(NF))
            at(2 in table.col_book_map['FMT9'])

        del cache
        # Test that the old interface also shows correct format data
        db = self.init_old()
        ae(db.formats(3, index_is_id=True), ','.join(['FMT1', 'FMTX', 'REPL', 'REPL2']))
        ae(db.format(3, 'FMT1', index_is_id=True), NF)
        ae(db.format(1, 'FMT1', index_is_id=True), NF)

        db.close()
        del db

    # }}}


