#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import numbers
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable

from calibre.ebooks.metadata import author_to_author_sort
from calibre.utils.date import UNDEFINED_DATE, parse_date, utc_tz
from calibre.utils.icu import lower as icu_lower
from calibre_extensions.speedup import parse_date as _c_speedup
from polyglot.builtins import iteritems, itervalues


def identity(x):
    return x

def c_parse(val):
    try:
        year, month, day, hour, minutes, seconds, tzsecs = _c_speedup(val)
    except (AttributeError, TypeError):
        # If a value like 2001 is stored in the column, apsw will return it as
        # an int
        if isinstance(val, numbers.Number):
            return datetime(int(val), 1, 3, tzinfo=utc_tz)
        if val is None:
            return UNDEFINED_DATE
    except:
        pass
    else:
        try:
            ans = datetime(year, month, day, hour, minutes, seconds, tzinfo=utc_tz)
            if tzsecs != 0:
                ans -= timedelta(seconds=tzsecs)
        except OverflowError:
            ans = UNDEFINED_DATE
        return ans
    try:
        return parse_date(val, as_utc=True, assume_utc=True)
    except (ValueError, TypeError):
        return UNDEFINED_DATE


ONE_ONE, MANY_ONE, MANY_MANY = range(3)

null = object()


class Table:

    supports_notes = False

    def __init__(self, name, metadata, link_table=None):
        self.name, self.metadata = name, metadata
        self.sort_alpha = metadata.get('is_multiple', False) and metadata.get('display', {}).get('sort_alpha', False)
        dt = metadata['datatype']

        # self.unserialize() maps values from the db to python objects
        self.unserialize = {
            'datetime': c_parse,
            'bool': bool
        }.get(dt)
        self.serialize = None
        if name == 'authors':
            # Legacy
            self.unserialize = lambda x: x.replace('|', ',') if x else ''
            self.serialize = lambda x: x.replace(',', '|')
        self.link_table = (link_table if link_table else
                'books_%s_link'%self.metadata['table'])
        if self.supports_notes and dt == 'rating':  # custom ratings table
            self.supports_notes = False

    def remove_books(self, book_ids, db):
        return set()

    def fix_link_table(self, db):
        pass

    def fix_case_duplicates(self, db):
        ''' If this table contains entries that differ only by case, then merge
        those entries. This can happen in databases created with old versions
        of calibre and non-ascii values, since sqlite's NOCASE only works with
        ascii text. '''
        pass


class VirtualTable(Table):

    '''
    A dummy table used for fields that only exist in memory like ondevice
    '''

    def __init__(self, name, table_type=ONE_ONE, datatype='text'):
        metadata = {'datatype':datatype, 'table':name}
        self.table_type = table_type
        Table.__init__(self, name, metadata)


class OneToOneTable(Table):

    '''
    Represents data that is unique per book (it may not actually be unique) but
    each item is assigned to a book in a one-to-one mapping. For example: uuid,
    timestamp, size, etc.
    '''

    table_type = ONE_ONE

    def read(self, db):
        idcol = 'id' if self.metadata['table'] == 'books' else 'book'
        query = db.execute('SELECT {}, {} FROM {}'.format(idcol,
            self.metadata['column'], self.metadata['table']))
        if self.unserialize is None:
            try:
                self.book_col_map = dict(query)
            except UnicodeDecodeError:
                # The db is damaged, try to work around it by ignoring
                # failures to decode utf-8
                query = db.execute('SELECT {}, cast({} as blob) FROM {}'.format(idcol,
                    self.metadata['column'], self.metadata['table']))
                self.book_col_map = {k:bytes(val).decode('utf-8', 'replace') for k, val in query}
        else:
            us = self.unserialize
            self.book_col_map = {book_id:us(val) for book_id, val in query}

    def remove_books(self, book_ids, db):
        clean = set()
        for book_id in book_ids:
            val = self.book_col_map.pop(book_id, null)
            if val is not null:
                clean.add(val)
        return clean


class PathTable(OneToOneTable):

    def set_path(self, book_id, path, db):
        self.book_col_map[book_id] = path
        db.execute('UPDATE books SET path=? WHERE id=?',
                        (path, book_id))


class SizeTable(OneToOneTable):

    def read(self, db):
        query = db.execute(
            'SELECT books.id, (SELECT MAX(uncompressed_size) FROM data '
            'WHERE data.book=books.id) FROM books')
        self.book_col_map = dict(query)

    def update_sizes(self, size_map):
        self.book_col_map.update(size_map)


class UUIDTable(OneToOneTable):

    def read(self, db):
        OneToOneTable.read(self, db)
        self.uuid_to_id_map = {v:k for k, v in iteritems(self.book_col_map)}

    def update_uuid_cache(self, book_id_val_map):
        for book_id, uuid in iteritems(book_id_val_map):
            self.uuid_to_id_map.pop(self.book_col_map.get(book_id, None), None)  # discard old uuid
            self.uuid_to_id_map[uuid] = book_id

    def remove_books(self, book_ids, db):
        clean = set()
        for book_id in book_ids:
            val = self.book_col_map.pop(book_id, null)
            if val is not null:
                self.uuid_to_id_map.pop(val, None)
                clean.add(val)
        return clean

    def lookup_by_uuid(self, uuid):
        return self.uuid_to_id_map.get(uuid, None)


class CompositeTable(OneToOneTable):

    def read(self, db):
        self.book_col_map = {}
        d = self.metadata['display']
        self.composite_template = ['composite_template']
        self.contains_html = d.get('contains_html', False)
        self.make_category = d.get('make_category', False)
        self.composite_sort = d.get('composite_sort', False)
        self.use_decorations = d.get('use_decorations', False)

    def remove_books(self, book_ids, db):
        return set()


class ManyToOneTable(Table):

    '''
    Represents data where one data item can map to many books, for example:
    series or publisher.

    Each book however has only one value for data of this type.
    '''

    table_type = MANY_ONE
    supports_notes = True

    def read(self, db):
        self.id_map = {}
        self.link_map = {}
        self.col_book_map = defaultdict(set)
        self.book_col_map = {}
        self.read_id_maps(db)
        self.read_maps(db)

    def read_id_maps(self, db):
        query = db.execute('SELECT id, {}, link FROM {}'.format(
            self.metadata['column'], self.metadata['table']))
        us = identity if self.unserialize is None else self.unserialize
        for id_, val, link in query:
            self.id_map[id_] = us(val)
            self.link_map[id_] = link

    def read_maps(self, db):
        cbm = self.col_book_map
        bcm = self.book_col_map
        for book, item_id in db.execute(
                'SELECT book, {} FROM {}'.format(
                    self.metadata['link_column'], self.link_table)):
            cbm[item_id].add(book)
            bcm[book] = item_id

    def fix_link_table(self, db):
        linked_item_ids = {item_id for item_id in itervalues(self.book_col_map)}
        extra_item_ids = linked_item_ids - set(self.id_map)
        if extra_item_ids:
            for item_id in extra_item_ids:
                book_ids = self.col_book_map.pop(item_id, ())
                for book_id in book_ids:
                    self.book_col_map.pop(book_id, None)
            db.executemany('DELETE FROM {} WHERE {}=?'.format(
                self.link_table, self.metadata['link_column']), tuple((x,) for x in extra_item_ids))

    def fix_case_duplicates(self, db):
        case_map = defaultdict(set)
        for item_id, val in iteritems(self.id_map):
            case_map[icu_lower(val)].add(item_id)

        for v in itervalues(case_map):
            if len(v) > 1:
                main_id = min(v)
                v.discard(main_id)
                item_map = {}
                for item_id in v:
                    val = self.id_map.pop(item_id, null)
                    if val is not null:
                        item_map[item_id] = val
                    books = self.col_book_map.pop(item_id, set())
                    for book_id in books:
                        self.book_col_map[book_id] = main_id
                db.executemany('UPDATE {0} SET {1}=? WHERE {1}=?'.format(
                    self.link_table, self.metadata['link_column']),
                    tuple((main_id, x) for x in v))
                db.delete_category_items(self.name, self.metadata['table'], item_map)

    def item_ids_for_names(self, db, item_names: Iterable[str], case_sensitive: bool = False) -> dict[str, int]:
        item_names = tuple(item_names)
        if case_sensitive:
            colname = self.metadata['column']
            serialized_names = tuple(map(self.serialize, item_names)) if self.serialize else item_names
            if len(item_names) == 1:
                iid = db.get(f'SELECT id FROM {self.metadata["table"]} WHERE {colname} = ?', ((serialized_names[0],)), all=False)
                return {item_names[0]: iid}
            inq = ('?,' * len(item_names))[:-1]
            ans = dict.fromkeys(item_names)
            res = db.get(f'SELECT {colname}, id FROM {self.metadata["table"]} WHERE {colname} IN ({inq})', serialized_names)
            if self.unserialize:
                res = ((self.unserialize(name), iid) for name, iid in res)
            ans.update(res)
            return ans
        if len(item_names) == 1:
            q = icu_lower(item_names[0])
            for iid, name in self.id_map.items():
                if icu_lower(name) == q:
                    return {item_names[0]: iid}
            return {item_names[0]: None}
        rmap = {icu_lower(v) if isinstance(v, str) else v:k for k, v in self.id_map.items()}
        return {name: rmap.get(icu_lower(name) if isinstance(name, str) else name, None) for name in item_names}

    def remove_books(self, book_ids, db):
        clean = set()
        for book_id in book_ids:
            item_id = self.book_col_map.pop(book_id, None)
            if item_id is not None:
                try:
                    self.col_book_map[item_id].discard(book_id)
                except KeyError:
                    if self.id_map.pop(item_id, null) is not null:
                        clean.add(item_id)
                else:
                    if not self.col_book_map[item_id]:
                        del self.col_book_map[item_id]
                        if self.id_map.pop(item_id, null) is not null:
                            clean.add(item_id)
        if clean:
            db.executemany(
                'DELETE FROM {} WHERE id=?'.format(self.metadata['table']),
                [(x,) for x in clean])
        return clean

    def remove_items(self, item_ids, db, restrict_to_book_ids=None):
        affected_books = set()

        if restrict_to_book_ids is not None:
            items_to_process_normally = set()
            # Check if all the books with the item are in the restriction. If
            # so, process them normally
            for item_id in item_ids:
                books_to_process = self.col_book_map.get(item_id, set())
                books_not_to_delete = books_to_process - restrict_to_book_ids
                if books_not_to_delete:
                    # Some books not in restriction. Must do special processing
                    books_to_delete = books_to_process & restrict_to_book_ids
                    # remove the books from the old id maps
                    self.col_book_map[item_id] = books_not_to_delete
                    for book_id in books_to_delete:
                        self.book_col_map.pop(book_id, None)
                    if books_to_delete:
                        # Delete links to the affected books from the link table. As
                        # this is a many-to-one mapping we know that we can delete
                        # links without checking the item ID
                        db.executemany(
                            f'DELETE FROM {self.link_table} WHERE book=?', tuple((x,) for x in books_to_delete))
                        affected_books |= books_to_delete
                else:
                    # Process normally any items where the VL was not significant
                    items_to_process_normally.add(item_id)
            if items_to_process_normally:
                affected_books |= self.remove_items(items_to_process_normally, db)
            return affected_books

        item_map = {}
        for item_id in item_ids:
            val = self.id_map.pop(item_id, null)
            if val is null:
                continue
            item_map[item_id] = val
            book_ids = self.col_book_map.pop(item_id, set())
            for book_id in book_ids:
                self.book_col_map.pop(book_id, None)
            affected_books.update(book_ids)
        db.delete_category_items(self.name, self.metadata['table'], item_map, self.link_table, self.metadata['link_column'])
        return affected_books

    def rename_item(self, item_id, new_name, db):
        existing_item = None
        q = icu_lower(new_name)
        for q_id, q_val in self.id_map.items():
            if icu_lower(q_val) == q:
                existing_item = q_id
                break
        table, col, lcol = self.metadata['table'], self.metadata['column'], self.metadata['link_column']
        affected_books = self.col_book_map.get(item_id, set())
        new_id = item_id
        if existing_item is None or existing_item == item_id:
            # A simple rename will do the trick
            self.id_map[item_id] = new_name
            db.execute(f'UPDATE {table} SET {col}=? WHERE id=?', (new_name, item_id))
        else:
            # We have to replace
            new_id = existing_item
            self.id_map.pop(item_id, None)
            books = self.col_book_map.pop(item_id, set())
            for book_id in books:
                self.book_col_map[book_id] = existing_item
            self.col_book_map[existing_item].update(books)
            db.rename_category_item(self.name, table, self.link_table, lcol, item_id, existing_item, self.id_map[new_id])
        return affected_books, new_id

    def set_links(self, link_map, db):
        link_map = {id_:(l or '').strip() for id_, l in link_map.items()}
        link_map = {id_:l for id_, l in link_map.items() if l != self.link_map.get(id_)}
        if link_map:
            self.link_map.update(link_map)
            db.executemany(f'UPDATE {self.metadata["table"]} SET link=? WHERE id=?',
                tuple((v, k) for k, v in link_map.items()))
        return link_map


class RatingTable(ManyToOneTable):

    supports_notes = False

    def read_id_maps(self, db):
        ManyToOneTable.read_id_maps(self, db)
        # Ensure there are no records with rating=0 in the table. These should
        # be represented as rating:None instead.
        bad_ids = {item_id for item_id, rating in iteritems(self.id_map) if rating == 0}
        if bad_ids:
            self.id_map = {item_id:rating for item_id, rating in iteritems(self.id_map) if rating != 0}
            db.executemany('DELETE FROM {} WHERE {}=?'.format(self.link_table, self.metadata['link_column']),
                                tuple((x,) for x in bad_ids))
            db.execute('DELETE FROM {} WHERE {}=0'.format(
                self.metadata['table'], self.metadata['column']))


class ManyToManyTable(ManyToOneTable):

    '''
    Represents data that has a many-to-many mapping with books. i.e. each book
    can have more than one value and each value can be mapped to more than one
    book. For example: tags or authors.
    '''

    table_type = MANY_MANY
    selectq = 'SELECT book, {0} FROM {1} ORDER BY id'
    do_clean_on_remove = True

    def read_maps(self, db):
        bcm = defaultdict(list)
        cbm = self.col_book_map
        for book, item_id in db.execute(
                self.selectq.format(self.metadata['link_column'], self.link_table)):
            cbm[item_id].add(book)
            bcm[book].append(item_id)

        self.book_col_map = {k:tuple(v) for k, v in iteritems(bcm)}

    def fix_link_table(self, db):
        linked_item_ids = {item_id for item_ids in itervalues(self.book_col_map) for item_id in item_ids}
        extra_item_ids = linked_item_ids - set(self.id_map)
        if extra_item_ids:
            for item_id in extra_item_ids:
                book_ids = self.col_book_map.pop(item_id, ())
                for book_id in book_ids:
                    self.book_col_map[book_id] = tuple(iid for iid in self.book_col_map.pop(book_id, ()) if iid not in extra_item_ids)
            db.executemany('DELETE FROM {} WHERE {}=?'.format(
                self.link_table, self.metadata['link_column']), tuple((x,) for x in extra_item_ids))

    def remove_books(self, book_ids, db):
        clean = {}
        for book_id in book_ids:
            item_ids = self.book_col_map.pop(book_id, ())
            for item_id in item_ids:
                try:
                    self.col_book_map[item_id].discard(book_id)
                except KeyError:
                    if self.id_map.pop(item_id, null) is not null:
                        clean.add(item_id)
                else:
                    if not self.col_book_map[item_id]:
                        del self.col_book_map[item_id]
                        val = self.id_map.pop(item_id, null)
                        if val is not null:
                            clean[item_id] = val
        if clean and self.do_clean_on_remove:
            db.delete_category_items(self.name, self.metadata['table'], clean)
        return set(clean)

    def remove_items(self, item_ids, db, restrict_to_book_ids=None):
        affected_books = set()
        if restrict_to_book_ids is not None:
            items_to_process_normally = set()
            # Check if all the books with the item are in the restriction. If
            # so, process them normally
            for item_id in item_ids:
                books_to_process = self.col_book_map.get(item_id, set())
                books_not_to_delete = books_to_process - restrict_to_book_ids
                if books_not_to_delete:
                    # Some books not in restriction. Must do special processing
                    books_to_delete = books_to_process & restrict_to_book_ids
                    # remove the books from the old id maps
                    self.col_book_map[item_id] = books_not_to_delete
                    for book_id in books_to_delete:
                        self.book_col_map[book_id] = tuple(
                           x for x in self.book_col_map.get(book_id, ()) if x != item_id)
                    affected_books |= books_to_delete
                else:
                    items_to_process_normally.add(item_id)
            # Delete book/item pairs from the link table. We don't need to do
            # anything with the main table because books with the old ID are
            # still in the library.
            db.executemany('DELETE FROM {} WHERE {}=? and {}=?'.format(
                    self.link_table, 'book', self.metadata['link_column']),
                           [(b, i) for b in affected_books for i in item_ids])
            # Take care of any items where the VL was not significant
            if items_to_process_normally:
                affected_books |= self.remove_items(items_to_process_normally, db)
            return affected_books

        item_map = {}
        for item_id in item_ids:
            val = self.id_map.pop(item_id, null)
            if val is null:
                continue
            item_map[item_id] = val
            book_ids = self.col_book_map.pop(item_id, set())
            for book_id in book_ids:
                self.book_col_map[book_id] = tuple(x for x in self.book_col_map.get(book_id, ()) if x != item_id)
            affected_books.update(book_ids)
        db.delete_category_items(self.name, self.metadata['table'], item_map, self.link_table, self.metadata['link_column'])
        return affected_books

    def rename_item(self, item_id, new_name, db):
        existing_item = None
        q = icu_lower(new_name)
        for q_id, q_val in self.id_map.items():
            if icu_lower(q_val) == q:
                existing_item = q_id
                break
        table, col, lcol = self.metadata['table'], self.metadata['column'], self.metadata['link_column']
        affected_books = self.col_book_map.get(item_id, set())
        new_id = item_id
        if existing_item is None or existing_item == item_id:
            # A simple rename will do the trick
            self.id_map[item_id] = new_name
            db.execute(f'UPDATE {table} SET {col}=? WHERE id=?', (new_name, item_id))
        else:
            # We have to replace
            new_id = existing_item
            self.id_map.pop(item_id, None)
            books = self.col_book_map.pop(item_id, set())
            # Replacing item_id with existing_item could cause the same id to
            # appear twice in the book list. Handle that by removing existing
            # item from the book list before replacing.
            for book_id in books:
                self.book_col_map[book_id] = tuple((existing_item if x == item_id else x) for x in self.book_col_map.get(book_id, ()) if x != existing_item)
            self.col_book_map[existing_item].update(books)
            db.executemany(f'DELETE FROM {self.link_table} WHERE book=? AND {lcol}=?', [
                (book_id, existing_item) for book_id in books])
            db.rename_category_item(self.name, table, self.link_table, lcol, item_id, existing_item, self.id_map[new_id])
        return affected_books, new_id

    def fix_case_duplicates(self, db):
        from calibre.db.write import uniq
        case_map = defaultdict(set)
        for item_id, val in iteritems(self.id_map):
            case_map[icu_lower(val)].add(item_id)

        for v in itervalues(case_map):
            if len(v) > 1:
                done_books = set()
                main_id = min(v)
                v.discard(main_id)
                item_map = {}
                for item_id in v:
                    val = self.id_map.pop(item_id, null)
                    if val is not null:
                        item_map[item_id] = val
                    books = self.col_book_map.pop(item_id, set())
                    for book_id in books:
                        if book_id in done_books:
                            continue
                        done_books.add(book_id)
                        orig = self.book_col_map.get(book_id, ())
                        if not orig:
                            continue
                        vals = uniq(tuple(main_id if x in v else x for x in orig))
                        self.book_col_map[book_id] = vals
                        if len(orig) == len(vals):
                            # We have a simple replacement
                            db.executemany(
                                'UPDATE {0} SET {1}=? WHERE {1}=? AND book=?'.format(
                                self.link_table, self.metadata['link_column']),
                                tuple((main_id, x, book_id) for x in v))
                        else:
                            # duplicates
                            db.execute(f'DELETE FROM {self.link_table} WHERE book=?', (book_id,))
                            db.executemany(
                                'INSERT INTO {} (book,{}) VALUES (?,?)'.format(self.link_table, self.metadata['link_column']),
                                tuple((book_id, x) for x in vals))
                db.delete_category_items(self.name, self.metadata['table'], item_map)


class AuthorsTable(ManyToManyTable):

    def read_id_maps(self, db):
        self.link_map = lm = {}
        self.asort_map = sm = {}
        self.id_map = im = {}
        us = self.unserialize
        for aid, name, sort, link in db.execute(
                'SELECT id, name, sort, link FROM authors'):
            name = us(name)
            im[aid] = name
            sm[aid] = (sort or author_to_author_sort(name))
            lm[aid] = link

    def set_sort_names(self, aus_map, db):
        aus_map = {aid:(a or '').strip() for aid, a in iteritems(aus_map)}
        aus_map = {aid:a for aid, a in iteritems(aus_map) if a != self.asort_map.get(aid, None)}
        self.asort_map.update(aus_map)
        db.executemany('UPDATE authors SET sort=? WHERE id=?',
            [(v, k) for k, v in iteritems(aus_map)])
        return aus_map

    def set_links(self, link_map, db):
        link_map = {aid:(l or '').strip() for aid, l in iteritems(link_map)}
        link_map = {aid:l for aid, l in iteritems(link_map) if l != self.link_map.get(aid, None)}
        self.link_map.update(link_map)
        db.executemany('UPDATE authors SET link=? WHERE id=?',
            [(v, k) for k, v in iteritems(link_map)])
        return link_map

    def remove_books(self, book_ids, db):
        clean = ManyToManyTable.remove_books(self, book_ids, db)
        for item_id in clean:
            self.link_map.pop(item_id, None)
            self.asort_map.pop(item_id, None)
        return clean

    def rename_item(self, item_id, new_name, db):
        ret = ManyToManyTable.rename_item(self, item_id, new_name, db)
        if item_id not in self.id_map:
            self.link_map.pop(item_id, None)
            self.asort_map.pop(item_id, None)
        else:
            # Was a simple rename, update the author sort value
            self.set_sort_names({item_id:author_to_author_sort(new_name)}, db)

        return ret

    def remove_items(self, item_ids, db, restrict_to_book_ids=None):
        raise NotImplementedError('Direct removal of authors is not allowed')


class FormatsTable(ManyToManyTable):

    do_clean_on_remove = False
    supports_notes = False

    def read_id_maps(self, db):
        pass

    def fix_case_duplicates(self, db):
        pass

    def read_maps(self, db):
        self.fname_map = fnm = defaultdict(dict)
        self.size_map = sm = defaultdict(dict)
        self.col_book_map = cbm = defaultdict(set)
        bcm = defaultdict(list)

        for book, fmt, name, sz in db.execute('SELECT book, format, name, uncompressed_size FROM data'):
            if fmt is not None:
                fmt = fmt.upper()
                cbm[fmt].add(book)
                bcm[book].append(fmt)
                fnm[book][fmt] = name
                sm[book][fmt] = sz

        self.book_col_map = {k:tuple(sorted(v)) for k, v in iteritems(bcm)}

    def remove_books(self, book_ids, db):
        clean = ManyToManyTable.remove_books(self, book_ids, db)
        for book_id in book_ids:
            self.fname_map.pop(book_id, None)
            self.size_map.pop(book_id, None)
        return clean

    def set_fname(self, book_id, fmt, fname, db):
        self.fname_map[book_id][fmt] = fname
        db.execute('UPDATE data SET name=? WHERE book=? AND format=?',
                        (fname, book_id, fmt))

    def remove_formats(self, formats_map, db):
        for book_id, fmts in iteritems(formats_map):
            self.book_col_map[book_id] = [fmt for fmt in self.book_col_map.get(book_id, []) if fmt not in fmts]
            for m in (self.fname_map, self.size_map):
                m[book_id] = {k:v for k, v in iteritems(m[book_id]) if k not in fmts}
            for fmt in fmts:
                try:
                    self.col_book_map[fmt].discard(book_id)
                except KeyError:
                    pass
        db.executemany('DELETE FROM data WHERE book=? AND format=?',
            [(book_id, fmt) for book_id, fmts in iteritems(formats_map) for fmt in fmts])

        def zero_max(book_id):
            try:
                return max(itervalues(self.size_map[book_id]))
            except ValueError:
                return 0

        return {book_id:zero_max(book_id) for book_id in formats_map}

    def remove_items(self, item_ids, db):
        raise NotImplementedError('Cannot delete a format directly')

    def rename_item(self, item_id, new_name, db):
        raise NotImplementedError('Cannot rename formats')

    def update_fmt(self, book_id, fmt, fname, size, db):
        fmts = list(self.book_col_map.get(book_id, []))
        try:
            fmts.remove(fmt)
        except ValueError:
            pass
        fmts.append(fmt)
        self.book_col_map[book_id] = tuple(fmts)

        try:
            self.col_book_map[fmt].add(book_id)
        except KeyError:
            self.col_book_map[fmt] = {book_id}

        self.fname_map[book_id][fmt] = fname
        self.size_map[book_id][fmt] = size
        db.execute('INSERT OR REPLACE INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                        (book_id, fmt, size, fname))
        return max(itervalues(self.size_map[book_id]))


class IdentifiersTable(ManyToManyTable):

    supports_notes = False

    def read_id_maps(self, db):
        pass

    def fix_case_duplicates(self, db):
        pass

    def read_maps(self, db):
        self.book_col_map = defaultdict(dict)
        self.col_book_map = defaultdict(set)
        for book, typ, val in db.execute('SELECT book, type, val FROM identifiers'):
            if typ is not None and val is not None:
                self.col_book_map[typ].add(book)
                self.book_col_map[book][typ] = val

    def remove_books(self, book_ids, db):
        clean = set()
        for book_id in book_ids:
            item_map = self.book_col_map.pop(book_id, {})
            for item_id in item_map:
                try:
                    self.col_book_map[item_id].discard(book_id)
                except KeyError:
                    clean.add(item_id)
                else:
                    if not self.col_book_map[item_id]:
                        del self.col_book_map[item_id]
                        clean.add(item_id)
        return clean

    def remove_items(self, item_ids, db):
        raise NotImplementedError('Direct deletion of identifiers is not implemented')

    def rename_item(self, item_id, new_name, db):
        raise NotImplementedError('Cannot rename identifiers')

    def all_identifier_types(self):
        return frozenset(k for k, v in iteritems(self.col_book_map) if v)
