#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.db.tests.base import BaseTest

class LegacyTest(BaseTest):

    ''' Test the emulation of the legacy interface. '''

    def test_library_wide_properties(self):  # {{{
        'Test library wide properties'
        old = self.init_old()
        props = ('user_version', 'is_second_db', 'library_id', 'field_metadata',
                 'custom_column_label_map', 'custom_column_num_map')
        oldvals = {x:getattr(old, x) for x in props}
        oldvals['last_modified'] = old.last_modified()
        old.close()
        old = None
        db = self.init_legacy()
        newvals = {x:getattr(db, x) for x in props}
        newvals['last_modified'] = db.last_modified()
        self.assertEqual(oldvals, newvals)
        db.close()
    # }}}

    def test_get_property(self):  # {{{
        'Test the get_property interface for reading data'
        def get_values(db):
            ans = {}
            for label, loc in db.FIELD_MAP.iteritems():
                if isinstance(label, int):
                    label = '#'+db.custom_column_num_map[label]['label']
                label = type('')(label)
                ans[label] = tuple(db.get_property(i, index_is_id=True, loc=loc)
                                   for i in db.all_ids())
            return ans

        old = self.init_old()
        old_vals = get_values(old)
        old.close()
        old = None
        db = self.init_legacy()
        new_vals = get_values(db)
        db.close()
        self.assertEqual(old_vals, new_vals)

    # }}}

