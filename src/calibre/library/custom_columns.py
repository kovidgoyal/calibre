#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class CustomColumns(object):

    CUSTOM_DATA_TYPES = frozenset(['rating', 'text', 'comments', 'datetime',
        'int', 'float', 'bool'])


    def __init__(self):
        return
        # Delete marked custom columns
        for num in self.conn.get(
                'SELECT id FROM custom_columns WHERE mark_for_delete=1'):
            dt, lt = self.custom_table_names(num)
            self.conn.executescript('''\
                    DROP TABLE IF EXISTS %s;
                    DROP TABLE IF EXISTS %s;
                    '''%(dt, lt)
            )
        self.conn.execute('DELETE FROM custom_columns WHERE mark_for_delete=1')
        self.conn.commit()



    def custom_table_names(self, num):
        return 'custom_column_%d'%num, 'books_custom_column_%d_link'%num

    @property
    def custom_tables(self):
        return set([x[0] for x in self.conn.get(
            'SELECT name FROM sqlite_master WHERE type="table" AND '
            '(name GLOB "custom_column_*" OR name GLOB books_customcolumn_*)')])

    def create_custom_table(self, label, name, datatype, is_multiple,
            sort_alpha):
        if datatype not in self.CUSTOM_DATA_TYPES:
            raise ValueError('%r is not a supported data type'%datatype)


