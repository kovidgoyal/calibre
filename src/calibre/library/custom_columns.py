#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, re
from functools import partial

from calibre import prints
from calibre.constants import preferred_encoding
from calibre.library.field_metadata import FieldMetadata
from calibre.utils.date import parse_date
from calibre.utils.config import tweaks

class CustomColumns(object):

    CUSTOM_DATA_TYPES = frozenset(['rating', 'text', 'comments', 'datetime',
        'int', 'float', 'bool', 'series', 'composite', 'enumeration'])

    def custom_table_names(self, num):
        return 'custom_column_%d'%num, 'books_custom_column_%d_link'%num

    @property
    def custom_tables(self):
        return set([x[0] for x in self.conn.get(
            'SELECT name FROM sqlite_master WHERE type="table" AND '
            '(name GLOB "custom_column_*" OR name GLOB "books_custom_column_*")')])


    def __init__(self):
        # Verify that CUSTOM_DATA_TYPES is a (possibly improper) subset of
        # VALID_DATA_TYPES
        if len(self.CUSTOM_DATA_TYPES - FieldMetadata.VALID_DATA_TYPES) > 0:
            raise ValueError('Unknown custom column type in set')
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
                    DROP VIEW    IF EXISTS tag_browser_filtered_{table};
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
            if data['display'] is None:
                data['display'] = {}
            # set up the is_multiple separator dict
            if data['is_multiple']:
                if data['display'].get('is_names', False):
                    seps = {'cache_to_list': '|', 'ui_to_list': '&', 'list_to_ui': ' & '}
                elif data['datatype'] == 'composite':
                    seps = {'cache_to_list': ',', 'ui_to_list': ',', 'list_to_ui': ', '}
                else:
                    seps = {'cache_to_list': '|', 'ui_to_list': ',', 'list_to_ui': ', '}
            else:
                seps = {}
            data['multiple_seps'] = seps

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
                    x = x.split(d['multiple_seps']['ui_to_list'])
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
                x = x.lower()
                if x == 'true':
                    x = True
                elif x == 'false':
                    x = False
                elif x == 'none':
                    x = None
                else:
                    x = bool(int(x))
            return x

        def adapt_enum(x, d):
            v = adapt_text(x, d)
            if not v:
                v = None
            return v

        def adapt_number(x, d):
            if x is None:
                return None
            if isinstance(x, (str, unicode, bytes)):
                if x.lower() == 'none':
                    return None
            if d['datatype'] == 'int':
                return int(x)
            return float(x)

        self.custom_data_adapters = {
                'float': adapt_number,
                'int':   adapt_number,
                'rating':lambda x,d : x if x is None else min(10., max(0., float(x))),
                'bool':  adapt_bool,
                'comments': lambda x,d: adapt_text(x, {'is_multiple':False}),
                'datetime' : adapt_datetime,
                'text':adapt_text,
                'series':adapt_text,
                'enumeration': adapt_enum
        }

        # Create Tag Browser categories for custom columns
        for k in sorted(self.custom_column_label_map.keys()):
            v = self.custom_column_label_map[k]
            if v['normalized']:
                is_category = True
            else:
                is_category = False
            is_m = v['multiple_seps']
            tn = 'custom_column_{0}'.format(v['num'])
            self.field_metadata.add_custom_field(label=v['label'],
                    table=tn, column='value', datatype=v['datatype'],
                    colnum=v['num'], name=v['name'], display=v['display'],
                    is_multiple=is_m, is_category=is_category,
                    is_editable=v['editable'], is_csp=False)

    def get_custom(self, idx, label=None, num=None, index_is_id=False):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        row = self.data._data[idx] if index_is_id else self.data[idx]
        ans = row[self.FIELD_MAP[data['num']]]
        if data['is_multiple'] and data['datatype'] == 'text':
            ans = ans.split(data['multiple_seps']['cache_to_list']) if ans else []
            if data['display'].get('sort_alpha', False):
                ans.sort(cmp=lambda x,y:cmp(x.lower(), y.lower()))
        return ans

    def get_custom_extra(self, idx, label=None, num=None, index_is_id=False):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        # add future datatypes with an extra column here
        if data['datatype'] not in ['series']:
            return None
        ign,lt = self.custom_table_names(data['num'])
        idx = idx if index_is_id else self.id(idx)
        return self.conn.get('''SELECT extra FROM %s
                                WHERE book=?'''%lt, (idx,), all=False)

    def get_custom_and_extra(self, idx, label=None, num=None, index_is_id=False):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        idx = idx if index_is_id else self.id(idx)
        row = self.data._data[idx]
        ans = row[self.FIELD_MAP[data['num']]]
        if data['is_multiple'] and data['datatype'] == 'text':
            ans = ans.split(data['multiple_seps']['cache_to_list']) if ans else []
            if data['display'].get('sort_alpha', False):
                ans.sort(cmp=lambda x,y:cmp(x.lower(), y.lower()))
        if data['datatype'] != 'series':
            return (ans, None)
        ign,lt = self.custom_table_names(data['num'])
        extra = self.conn.get('''SELECT extra FROM %s
                                 WHERE book=?'''%lt, (idx,), all=False)
        return (ans, extra)

    # convenience methods for tag editing
    def get_custom_items_with_ids(self, label=None, num=None):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        table,lt = self.custom_table_names(data['num'])
        if not data['normalized']:
            return []
        ans = self.conn.get('SELECT id, value FROM %s'%table)
        return ans

    def rename_custom_item(self, old_id, new_name, label=None, num=None):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        table,lt = self.custom_table_names(data['num'])
        # check if item exists
        new_id = self.conn.get(
            'SELECT id FROM %s WHERE value=?'%table, (new_name,), all=False)
        if new_id is None or old_id == new_id:
            self.conn.execute('UPDATE %s SET value=? WHERE id=?'%table, (new_name, old_id))
            new_id = old_id
        else:
            # New id exists. If the column is_multiple, then process like
            # tags, otherwise process like publishers (see database2)
            if data['is_multiple']:
                books = self.conn.get('''SELECT book from %s
                                         WHERE value=?'''%lt, (old_id,))
                for (book_id,) in books:
                    self.conn.execute('''DELETE FROM %s
                            WHERE book=? and value=?'''%lt, (book_id, new_id))
            self.conn.execute('''UPDATE %s SET value=?
                                 WHERE value=?'''%lt, (new_id, old_id,))
            self.conn.execute('DELETE FROM %s WHERE id=?'%table, (old_id,))
        self.dirty_books_referencing('#'+data['label'], new_id, commit=False)
        self.conn.commit()

    def delete_custom_item_using_id(self, id, label=None, num=None):
        if id:
            if label is not None:
                data = self.custom_column_label_map[label]
            if num is not None:
                data = self.custom_column_num_map[num]
            table,lt = self.custom_table_names(data['num'])
            self.dirty_books_referencing('#'+data['label'], id, commit=False)
            self.conn.execute('DELETE FROM %s WHERE value=?'%lt, (id,))
            self.conn.execute('DELETE FROM %s WHERE id=?'%table, (id,))
            self.conn.commit()

    def is_item_used_in_multiple(self, item, label=None, num=None):
        existing_tags = self.all_custom(label=label, num=num)
        return item.lower() in {t.lower() for t in existing_tags}

    def delete_item_from_multiple(self, item, label=None, num=None):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if data['datatype'] != 'text' or not data['is_multiple']:
            raise ValueError('Column %r is not text/multiple'%data['label'])
        existing_tags = list(self.all_custom(label=label, num=num))
        lt = [t.lower() for t in existing_tags]
        try:
            idx = lt.index(item.lower())
        except ValueError:
            idx = -1
        books_affected = []
        if idx > -1:
            table, lt = self.custom_table_names(data['num'])
            id_ = self.conn.get('SELECT id FROM %s WHERE value = ?'%table,
                                (existing_tags[idx],), all=False)
            if id_:
                books = self.conn.get('SELECT book FROM %s WHERE value = ?'%lt, (id_,))
                if books:
                    books_affected = [b[0] for b in books]
                self.conn.execute('DELETE FROM %s WHERE value=?'%lt, (id_,))
                self.conn.execute('DELETE FROM %s WHERE id=?'%table, (id_,))
                self.conn.commit()
        return books_affected
    # end convenience methods

    def get_next_cc_series_num_for(self, series, label=None, num=None):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if data['datatype'] != 'series':
            return None
        table, lt = self.custom_table_names(data['num'])
        # get the id of the row containing the series string
        series_id = self.conn.get('SELECT id from %s WHERE value=?'%table,
                                                        (series,), all=False)
        if series_id is None:
            if isinstance(tweaks['series_index_auto_increment'], (int, float)):
                return float(tweaks['series_index_auto_increment'])
            return 1.0
        series_indices = self.conn.get('''
                SELECT {lt}.extra FROM {lt}
                WHERE {lt}.book IN (SELECT book FROM {lt} where value=?)
                ORDER BY {lt}.extra
                '''.format(lt=lt), (series_id,))
        return self._get_next_series_num_for_list(series_indices)

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

    def set_custom_column_metadata(self, num, name=None, label=None,
            is_editable=None, display=None, notify=True):
        changed = False
        if name is not None:
            self.conn.execute('UPDATE custom_columns SET name=? WHERE id=?',
                    (name, num))
            changed = True
        if label is not None:
            self.conn.execute('UPDATE custom_columns SET label=? WHERE id=?',
                    (label, num))
            changed = True
        if is_editable is not None:
            self.conn.execute('UPDATE custom_columns SET editable=? WHERE id=?',
                    (bool(is_editable), num))
            self.custom_column_num_map[num]['is_editable'] = bool(is_editable)
            changed = True
        if display is not None:
            self.conn.execute('UPDATE custom_columns SET display=? WHERE id=?',
                    (json.dumps(display), num))
            changed = True

        if changed:
            self.conn.commit()
        if notify:
            self.notify('metadata', [])

        return changed

    def set_custom_bulk_multiple(self, ids, add=[], remove=[],
                        label=None, num=None, notify=False):
        '''
        Fast algorithm for updating custom column is_multiple datatypes.
        Do not use with other custom column datatypes.
        '''
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])
        if data['datatype'] != 'text' or not data['is_multiple']:
            raise ValueError('Column %r is not text/multiple'%data['label'])

        add = self.cleanup_tags(add)
        remove = self.cleanup_tags(remove)
        remove = set(remove) - set(add)
        if not ids or (not add and not remove):
            return
        # get custom table names
        cust_table, link_table = self.custom_table_names(data['num'])

        # Add tags that do not already exist into the custom cust_table
        all_tags = self.all_custom(num=data['num'])
        lt = [t.lower() for t in all_tags]
        new_tags = [t for t in add if t.lower() not in lt]
        if new_tags:
            self.conn.executemany('INSERT INTO %s(value) VALUES (?)'%cust_table,
                                  [(x,) for x in new_tags])

        # Create the temporary temp_tables to store the ids for books and tags
        # to be operated on
        temp_tables = ('temp_bulk_tag_edit_books', 'temp_bulk_tag_edit_add',
                    'temp_bulk_tag_edit_remove')
        drops = '\n'.join(['DROP TABLE IF EXISTS %s;'%t for t in temp_tables])
        creates = '\n'.join(['CREATE TEMP TABLE %s(id INTEGER PRIMARY KEY);'%t
                for t in temp_tables])
        self.conn.executescript(drops + creates)

        # Populate the books temp cust_table
        self.conn.executemany(
            'INSERT INTO temp_bulk_tag_edit_books VALUES (?)',
                [(x,) for x in ids])

        # Populate the add/remove tags temp temp_tables
        for table, tags in enumerate([add, remove]):
            if not tags:
                continue
            table = temp_tables[table+1]
            insert = ('INSERT INTO {tt}(id) SELECT {ct}.id FROM {ct} WHERE value=?'
                     ' COLLATE PYNOCASE LIMIT 1').format(tt=table, ct=cust_table)
            self.conn.executemany(insert, [(x,) for x in tags])

        # now do the real work -- removing and adding the tags
        if remove:
            self.conn.execute(
              '''DELETE FROM %s WHERE
                    book IN (SELECT id FROM %s) AND
                    value IN (SELECT id FROM %s)'''
              % (link_table, temp_tables[0], temp_tables[2]))
        if add:
            self.conn.execute(
            '''
            INSERT OR REPLACE INTO {0}(book, value) SELECT {1}.id, {2}.id FROM {1}, {2}
            '''.format(link_table, temp_tables[0], temp_tables[1])
            )
        # get rid of the temp tables
        self.conn.executescript(drops)
        self.dirtied(ids, commit=False)
        self.conn.commit()

        # set the in-memory copies of the tags
        for x in ids:
            tags = self.conn.get(
                    'SELECT custom_%s FROM meta2 WHERE id=?'%data['num'],
                    (x,), all=False)
            self.data.set(x, self.FIELD_MAP[data['num']], tags, row_is_id=True)

        if notify:
            self.notify('metadata', ids)

    def set_custom_bulk(self, ids, val, label=None, num=None,
                   append=False, notify=True, extras=None):
        '''
        Change the value of a column for a set of books. The ids parameter is a
        list of book ids to change. The extra field must be None or a list the
        same length as ids.
        '''
        if extras is not None and len(extras) != len(ids):
            raise ValueError('Length of ids and extras is not the same')
        ev = None
        for idx,id in enumerate(ids):
            if extras is not None:
                ev = extras[idx]
            self._set_custom(id, val, label=label, num=num, append=append,
                             notify=notify, extra=ev)
        self.dirtied(ids, commit=False)
        self.conn.commit()

    def set_custom(self, id, val, label=None, num=None, append=False,
                   notify=True, extra=None, commit=True, allow_case_change=False):
        rv = self._set_custom(id, val, label=label, num=num, append=append,
                         notify=notify, extra=extra,
                         allow_case_change=allow_case_change)
        self.dirtied(set([id])|rv, commit=False)
        if commit:
            self.conn.commit()
        return rv

    def _set_custom(self, id_, val, label=None, num=None, append=False,
                    notify=True, extra=None, allow_case_change=False):
        if label is not None:
            data = self.custom_column_label_map[label]
        if num is not None:
            data = self.custom_column_num_map[num]
        if data['datatype'] == 'composite':
            return set([])
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])
        table, lt = self.custom_table_names(data['num'])
        getter = partial(self.get_custom, id_, num=data['num'],
                index_is_id=True)
        val = self.custom_data_adapters[data['datatype']](val, data)

        if data['datatype'] == 'series' and extra is None:
            (val, extra) = self._get_series_values(val)
            if extra is None:
                extra = 1.0

        books_to_refresh = set([])
        if data['normalized']:
            if data['datatype'] == 'enumeration' and (
                    val and val not in data['display']['enum_values']):
                return books_to_refresh
            if not append or not data['is_multiple']:
                self.conn.execute('DELETE FROM %s WHERE book=?'%lt, (id_,))
                self.conn.execute(
                '''DELETE FROM %s WHERE (SELECT COUNT(id) FROM %s WHERE
                    value=%s.id) < 1''' % (table, lt, table))
                self.data._data[id_][self.FIELD_MAP[data['num']]] = None
            set_val = val if data['is_multiple'] else [val]
            existing = getter()
            if not existing:
                existing = set([])
            else:
                existing = set(existing)
            # preserve the order in set_val
            for x in [v for v in set_val if v not in existing]:
                # normalized types are text and ratings, so we can do this check
                # to see if we need to re-add the value
                if not x:
                    continue
                case_change = False
                existing = list(self.all_custom(num=data['num']))
                lx = [t.lower() if hasattr(t, 'lower') else t for t in existing]
                try:
                    idx = lx.index(x.lower() if hasattr(x, 'lower') else x)
                except ValueError:
                    idx = -1
                if idx > -1:
                    ex = existing[idx]
                    xid = self.conn.get(
                        'SELECT id FROM %s WHERE value=?'%table, (ex,), all=False)
                    if allow_case_change and ex != x:
                        case_change = True
                        self.conn.execute(
                            'UPDATE %s SET value=? WHERE id=?'%table, (x, xid))
                else:
                    xid = self.conn.execute(
                        'INSERT INTO %s(value) VALUES(?)'%table, (x,)).lastrowid
                if not self.conn.get(
                    'SELECT book FROM %s WHERE book=? AND value=?'%lt,
                                                        (id_, xid), all=False):
                    if data['datatype'] == 'series':
                        self.conn.execute(
                            '''INSERT INTO %s(book, value, extra)
                               VALUES (?,?,?)'''%lt, (id_, xid, extra))
                        self.data.set(id_, self.FIELD_MAP[data['num']]+1,
                                      extra, row_is_id=True)
                    else:
                        self.conn.execute(
                            '''INSERT INTO %s(book, value)
                                VALUES (?,?)'''%lt, (id_, xid))
                if case_change:
                    bks = self.conn.get('SELECT book FROM %s WHERE value=?'%lt,
                                        (xid,))
                    books_to_refresh |= set([bk[0] for bk in bks])
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
            nval = self.conn.get(
                    'SELECT custom_%s FROM meta2 WHERE id=?'%data['num'],
                    (id_,), all=False)
            self.data.set(id_, self.FIELD_MAP[data['num']], nval,
                    row_is_id=True)
        if notify:
            self.notify('metadata', [id_])
        return books_to_refresh

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
            table, lt = self.custom_table_names(data['num'])
            if data['normalized']:
                query = '%s.value'
                if data['is_multiple']:
#                    query = 'group_concat(%s.value, "{0}")'.format(
#                                        data['multiple_seps']['cache_to_list'])
#                    if not display.get('sort_alpha', False):
                    if data['multiple_seps']['cache_to_list'] == '|':
                        query = 'sortconcat_bar(link.id, %s.value)'
                    elif data['multiple_seps']['cache_to_list'] == '&':
                        query = 'sortconcat_amper(link.id, %s.value)'
                    else:
                        prints('WARNING: unknown value in multiple_seps',
                               data['multiple_seps']['cache_to_list'])
                        query = 'sortconcat_bar(link.id, %s.value)'
                line = '''(SELECT {query} FROM {lt} AS link INNER JOIN
                    {table} ON(link.value={table}.id) WHERE link.book=books.id)
                    custom_{num}
                '''.format(query=query%table, lt=lt, table=table, num=data['num'])
                if data['datatype'] == 'series':
                    line += ''',(SELECT extra FROM {lt} WHERE {lt}.book=books.id)
                        custom_index_{num}'''.format(lt=lt, num=data['num'])
            else:
                line = '''
                (SELECT value FROM {table} WHERE book=books.id) custom_{num}
                '''.format(table=table, num=data['num'])
            lines[data['num']] = line
        return lines

    def create_custom_column(self, label, name, datatype, is_multiple,
            editable=True, display={}):
        if not label:
            raise ValueError(_('No label was provided'))
        if re.match('^\w*$', label) is None or not label[0].isalpha() or label.lower() != label:
            raise ValueError(_('The label must contain only lower case letters, digits and underscores, and start with a letter'))
        if datatype not in self.CUSTOM_DATA_TYPES:
            raise ValueError('%r is not a supported data type'%datatype)
        normalized  = datatype not in ('datetime', 'comments', 'int', 'bool',
                'float', 'composite')
        is_multiple = is_multiple and datatype in ('text', 'composite')
        num = self.conn.execute(
                ('INSERT INTO '
                'custom_columns(label,name,datatype,is_multiple,editable,display,normalized)'
                'VALUES (?,?,?,?,?,?,?)'),
                (label, name, datatype, is_multiple, editable,
                    json.dumps(display), normalized)).lastrowid

        if datatype in ('rating', 'int'):
            dt = 'INT'
        elif datatype in ('text', 'comments', 'series', 'composite', 'enumeration'):
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
            if datatype == 'series':
                s_index = 'extra REAL,'
            else:
                s_index = ''
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
                    %s
                    UNIQUE(book, value)
                    );'''%(lt, s_index),

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
                    (SELECT COUNT(id) FROM {lt} WHERE value={table}.id) count,
                    (SELECT AVG(r.rating)
                     FROM {lt},
                          books_ratings_link as bl,
                          ratings as r
                     WHERE {lt}.value={table}.id and bl.book={lt}.book and
                           r.id = bl.rating and r.rating <> 0) avg_rating,
                    value AS sort
                FROM {table};

                CREATE VIEW tag_browser_filtered_{table} AS SELECT
                    id,
                    value,
                    (SELECT COUNT({lt}.id) FROM {lt} WHERE value={table}.id AND
                    books_list_filter(book)) count,
                    (SELECT AVG(r.rating)
                     FROM {lt},
                          books_ratings_link as bl,
                          ratings as r
                     WHERE {lt}.value={table}.id AND bl.book={lt}.book AND
                           r.id = bl.rating AND r.rating <> 0 AND
                           books_list_filter(bl.book)) avg_rating,
                    value AS sort
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


