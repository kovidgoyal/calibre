#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
from functools import partial

from calibre import prints
from calibre.constants import preferred_encoding
from calibre.utils.date import parse_date

class CustomColumns(object):

    CUSTOM_DATA_TYPES = frozenset(['rating', 'text', 'comments', 'datetime',
        'int', 'float', 'bool'])

    def custom_table_names(self, num):
        return 'custom_column_%d'%num, 'books_custom_column_%d_link'%num

    @property
    def custom_tables(self):
        return set([x[0] for x in self.conn.get(
            'SELECT name FROM sqlite_master WHERE type="table" AND '
            '(name GLOB "custom_column_*" OR name GLOB "books_custom_column_*")')])


    def __init__(self):
        # Delete marked custom columns
        for record in self.conn.get(
                'SELECT id FROM custom_columns WHERE mark_for_delete=1'):
            num = record[0]
            table, lt = self.custom_table_names(num)
            self.conn.executescript('''\
                    DROP INDEX   IF EXISTS {table}_idx;
                    DROP INDEX   IF EXISTS {lt}_aidx;
                    DROP INDEX   IF EXISTS {lt}_bidx;
                    DROP TRIGGER IF EXISTS fkc_update_{lt}_a;
                    DROP TRIGGER IF EXISTS fkc_update_{lt}_b;
                    DROP TRIGGER IF EXISTS fkc_insert_{lt};
                    DROP TRIGGER IF EXISTS fkc_delete_{lt};
                    DROP TRIGGER IF EXISTS fkc_insert_{table};
                    DROP TRIGGER IF EXISTS fkc_delete_{table};
                    DROP VIEW    IF EXISTS tag_browser_{table};
                    DROP TABLE   IF EXISTS {table};
                    DROP TABLE   IF EXISTS {lt};
                    '''.format(table=table, lt=lt)
            )
        self.conn.execute('DELETE FROM custom_columns WHERE mark_for_delete=1')
        self.conn.commit()

        # Load metadata for custom columns
        self.custom_column_label_map, self.custom_column_num_map = {}, {}
        triggers = []
        remove = []
        custom_tables = self.custom_tables
        for record in self.conn.get(
                'SELECT label,name,datatype,editable,display,normalized,id,is_multiple FROM custom_columns'):
            data = {
                    'label':record[0],
                    'name':record[1],
                    'datatype':record[2],
                    'editable':record[3],
                    'display':json.loads(record[4]),
                    'normalized':record[5],
                    'num':record[6],
                    'is_multiple':record[7],
                    }
            table, lt = self.custom_table_names(data['num'])
            if table not in custom_tables or (data['normalized'] and lt not in
                    custom_tables):
                remove.append(data)
                continue

            self.custom_column_label_map[data['label']] = data['num']
            self.custom_column_num_map[data['num']] = \
                self.custom_column_label_map[data['label']] = data

            # Create Foreign Key triggers
            if data['normalized']:
                trigger = 'DELETE FROM %s WHERE book=OLD.id;'%lt
            else:
                trigger = 'DELETE FROM %s WHERE book=OLD.id;'%table
            triggers.append(trigger)

        if remove:
            for data in remove:
                prints('WARNING: Custom column %r not found, removing.' %
                        data['label'])
                self.conn.execute('DELETE FROM custom_columns WHERE id=?',
                        (data['num'],))
            self.conn.commit()

        if triggers:
            self.conn.execute('''\
                CREATE TEMP TRIGGER custom_books_delete_trg
                    AFTER DELETE ON books
                    BEGIN
                    %s
                    END;
                '''%(' \n'.join(triggers)))
            self.conn.commit()

        # Setup data adapters
        def adapt_text(x, d):
            if d['is_multiple']:
                if x is None:
                    return []
                if isinstance(x, (str, unicode, bytes)):
                    x = x.split(',')
                x = [y.strip() for y in x if y.strip()]
                x = [y.decode(preferred_encoding, 'replace') if not isinstance(y,
                    unicode) else y for y in x]
                return [u' '.join(y.split()) for y in x]
            else:
                return x if x is None or isinstance(x, unicode) else \
                        x.decode(preferred_encoding, 'replace')

        def adapt_datetime(x, d):
            if isinstance(x, (str, unicode, bytes)):
                x = parse_date(x, assume_utc=False, as_utc=False)
            return x

        def adapt_bool(x, d):
            if isinstance(x, (str, unicode, bytes)):
                x = bool(int(x))
            return x

        self.custom_data_adapters = {
                'float': lambda x,d : x if x is None else float(x),
                'int':   lambda x,d : x if x is None else int(x),
                'rating':lambda x,d : x if x is None else min(10., max(0., float(x))),
                'bool':  adapt_bool,
                'comments': lambda x,d: adapt_text(x, {'is_multiple':False}),
                'datetime' : adapt_datetime,
                'text':adapt_text
                }

    def get_custom(self, idx, label=None, num=None, index_is_id=False):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        row = self.data._data[idx] if index_is_id else self.data[idx]
        ans = row[self.FIELD_MAP[data['num']]]
        if data['is_multiple'] and data['datatype'] == 'text':
            ans = ans.split('|') if ans else []
            if data['display'].get('sort_alpha', False):
                ans.sort(cmp=lambda x,y:cmp(x.lower(), y.lower()))
        return ans

    def all_custom(self, label=None, num=None):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        table, lt = self.custom_table_names(data['num'])
        if data['normalized']:
            ans = self.conn.get('SELECT value FROM %s'%table)
        else:
            ans = self.conn.get('SELECT DISTINCT value FROM %s'%table)
        ans = set([x[0] for x in ans])
        return ans

    def delete_custom_column(self, label=None, num=None):
        data = None
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if data is None:
            raise ValueError('No such column')
        self.conn.execute(
                'UPDATE custom_columns SET mark_for_delete=1 WHERE id=?',
                (data['num'],))
        self.conn.commit()

    def set_custom(self, id_, val, label=None, num=None, append=False, notify=True):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])
        table, lt = self.custom_table_names(data['num'])
        getter = partial(self.get_custom, id_, num=data['num'],
                index_is_id=True)
        val = self.custom_data_adapters[data['datatype']](val, data)

        if data['normalized']:
            if not append or not data['is_multiple']:
                self.conn.execute('DELETE FROM %s WHERE book=?'%lt, (id_,))
                self.conn.execute(
                '''DELETE FROM %s WHERE (SELECT COUNT(id) FROM %s WHERE
                    value=%s.id) < 1''' % (table, lt, table))
                self.data._data[id_][self.FIELD_MAP[data['num']]] = None
            set_val = val if data['is_multiple'] else [val]
            existing = getter()
            if not existing:
                existing = []
            for x in set(set_val) - set(existing):
                if x is None:
                    continue
                existing = self.all_custom(num=data['num'])
                lx = [t.lower() if hasattr(t, 'lower') else t for t in existing]
                try:
                    idx = lx.index(x.lower() if hasattr(x, 'lower') else x)
                except ValueError:
                    idx = -1
                if idx > -1:
                    ex = existing[idx]
                    xid = self.conn.get(
                            'SELECT id FROM %s WHERE value=?'%table, (ex,), all=False)
                    if ex != x:
                        self.conn.execute(
                                'UPDATE %s SET value=? WHERE id=?', (x, xid))
                else:
                    xid = self.conn.execute(
                            'INSERT INTO %s(value) VALUES(?)'%table, (x,)).lastrowid
                if not self.conn.get(
                    'SELECT book FROM %s WHERE book=? AND value=?'%lt,
                    (id_, xid), all=False):
                    self.conn.execute(
                        'INSERT INTO %s(book, value) VALUES (?,?)'%lt,
                            (id_, xid))
            self.conn.commit()
            nval = self.conn.get(
                    'SELECT custom_%s FROM meta2 WHERE id=?'%data['num'],
                    (id_,), all=False)
            self.data.set(id_, self.FIELD_MAP[data['num']], nval,
                    row_is_id=True)
        else:
            self.conn.execute('DELETE FROM %s WHERE book=?'%table, (id_,))
            if val is not None:
                self.conn.execute(
                        'INSERT INTO %s(book,value) VALUES (?,?)'%table,
                    (id_, val))
            self.conn.commit()
            nval = self.conn.get(
                    'SELECT custom_%s FROM meta2 WHERE id=?'%data['num'],
                    (id_,), all=False)
            self.data.set(id_, self.FIELD_MAP[data['num']], nval,
                    row_is_id=True)
        if notify:
            self.notify('metadata', [id_])
        return nval

    def clean_custom(self):
        st = ('DELETE FROM {table} WHERE (SELECT COUNT(id) FROM {lt} WHERE'
           ' {lt}.value={table}.id) < 1;')
        statements = []
        for data in self.custom_column_num_map.values():
            if data['normalized']:
                table, lt = self.custom_table_names(data['num'])
                statements.append(st.format(lt=lt, table=table))
        if statements:
            self.conn.executescript(' \n'.join(statements))
            self.conn.commit()

    def custom_columns_in_meta(self):
        lines = {}
        for data in self.custom_column_label_map.values():
            display = data['display']
            table, lt = self.custom_table_names(data['num'])
            if data['normalized']:
                query = '%s.value'
                if data['is_multiple']:
                    query = 'group_concat(%s.value, "|")'
                    if not display.get('sort_alpha', False):
                        query = 'sort_concat(link.id, %s.value)'
                line = '''(SELECT {query} FROM {lt} AS link INNER JOIN
                    {table} ON(link.value={table}.id) WHERE link.book=books.id)
                    custom_{num}
                '''.format(query=query%table, lt=lt, table=table, num=data['num'])
            else:
                line = '''
                (SELECT value FROM {table} WHERE book=books.id) custom_{num}
                '''.format(table=table, num=data['num'])
            lines[data['num']] = line
        return lines

    def create_custom_column(self, label, name, datatype, is_multiple,
            editable=True, display={}):
        if datatype not in self.CUSTOM_DATA_TYPES:
            raise ValueError('%r is not a supported data type'%datatype)
        normalized  = datatype not in ('datetime', 'comments', 'int', 'bool')
        is_multiple = is_multiple and datatype in ('text',)
        num = self.conn.execute(
                ('INSERT INTO '
                'custom_columns(label,name,datatype,is_multiple,editable,display,normalized)'
                'VALUES (?,?,?,?,?,?,?)'),
                (label, name, datatype, is_multiple, editable,
                    json.dumps(display), normalized)).lastrowid

        if datatype in ('rating', 'int'):
            dt = 'INT'
        elif datatype in ('text', 'comments'):
            dt = 'TEXT'
        elif datatype in ('float',):
            dt = 'REAL'
        elif datatype == 'datetime':
            dt = 'timestamp'
        elif datatype == 'bool':
            dt = 'BOOL'
        collate = 'COLLATE NOCASE' if dt == 'TEXT' else ''
        table, lt = self.custom_table_names(num)
        if normalized:
            lines = [
                '''\
                CREATE TABLE %s(
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    value %s NOT NULL %s,
                    UNIQUE(value));
                '''%(table, dt, collate),

                'CREATE INDEX %s_idx ON %s (value %s);'%(table, table, collate),

                '''\
                CREATE TABLE %s(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book INTEGER NOT NULL,
                    value INTEGER NOT NULL,
                    UNIQUE(book, value)
                    );'''%lt,

                'CREATE INDEX %s_aidx ON %s (value);'%(lt,lt),
                'CREATE INDEX %s_bidx ON %s (book);'%(lt,lt),

                '''\
                CREATE TRIGGER fkc_update_{lt}_a
                        BEFORE UPDATE OF book ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                CREATE TRIGGER fkc_update_{lt}_b
                        BEFORE UPDATE OF author ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from {table} WHERE id=NEW.value) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: value not in {table}')
                            END;
                        END;
                CREATE TRIGGER fkc_insert_{lt}
                        BEFORE INSERT ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                                WHEN (SELECT id from {table} WHERE id=NEW.value) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: value not in {table}')
                            END;
                        END;
                CREATE TRIGGER fkc_delete_{lt}
                        AFTER DELETE ON {table}
                        BEGIN
                            DELETE FROM {lt} WHERE value=OLD.id;
                        END;

                CREATE VIEW tag_browser_{table} AS SELECT
                    id,
                    value,
                    (SELECT COUNT(id) FROM {lt} WHERE value={table}.id) count
                FROM {table};

                '''.format(lt=lt, table=table),

            ]
        else:
            lines = [
                '''\
                CREATE TABLE %s(
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    book  INTEGER,
                    value %s NOT NULL %s,
                    UNIQUE(book));
                '''%(table, dt, collate),

                'CREATE INDEX %s_idx ON %s (book);'%(table, table),

                '''\
                CREATE TRIGGER fkc_insert_{table}
                        BEFORE INSERT ON {table}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                CREATE TRIGGER fkc_update_{table}
                        BEFORE UPDATE OF book ON {table}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                '''.format(table=table),
            ]

        script = ' \n'.join(lines)
        self.conn.executescript(script)
        self.conn.commit()
        return num


