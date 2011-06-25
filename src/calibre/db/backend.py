#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

# Imports {{{
import os, shutil, uuid, json
from functools import partial

import apsw

from calibre import isbytestring, force_unicode, prints
from calibre.constants import (iswindows, filesystem_encoding,
        preferred_encoding)
from calibre.ptempfile import PersistentTemporaryFile
from calibre.library.schema_upgrades import SchemaUpgrade
from calibre.library.field_metadata import FieldMetadata
from calibre.ebooks.metadata import title_sort, author_to_author_sort
from calibre.utils.icu import strcmp
from calibre.utils.config import to_json, from_json, prefs, tweaks
from calibre.utils.date import utcfromtimestamp
from calibre.db.tables import (OneToOneTable, ManyToOneTable, ManyToManyTable,
        SizeTable, FormatsTable, AuthorsTable, IdentifiersTable)
# }}}

'''
Differences in semantics from pysqlite:

    1. execute/executemany/executescript operate in autocommit mode

'''

class DynamicFilter(object): # {{{

    'No longer used, present for legacy compatibility'

    def __init__(self, name):
        self.name = name
        self.ids = frozenset([])

    def __call__(self, id_):
        return int(id_ in self.ids)

    def change(self, ids):
        self.ids = frozenset(ids)
# }}}

class DBPrefs(dict): # {{{

    'Store preferences as key:value pairs in the db'

    def __init__(self, db):
        dict.__init__(self)
        self.db = db
        self.defaults = {}
        self.disable_setting = False
        for key, val in self.db.conn.get('SELECT key,val FROM preferences'):
            try:
                val = self.raw_to_object(val)
            except:
                prints('Failed to read value for:', key, 'from db')
                continue
            dict.__setitem__(self, key, val)

    def raw_to_object(self, raw):
        if not isinstance(raw, unicode):
            raw = raw.decode(preferred_encoding)
        return json.loads(raw, object_hook=from_json)

    def to_raw(self, val):
        return json.dumps(val, indent=2, default=to_json)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.db.conn.execute('DELETE FROM preferences WHERE key=?', (key,))

    def __setitem__(self, key, val):
        if self.disable_setting:
            return
        raw = self.to_raw(val)
        self.db.conn.execute('INSERT OR REPLACE INTO preferences (key,val) VALUES (?,?)', (key,
            raw))
        dict.__setitem__(self, key, val)

    def set(self, key, val):
        self.__setitem__(key, val)

# }}}

# Extra collators {{{
def pynocase(one, two, encoding='utf-8'):
    if isbytestring(one):
        try:
            one = one.decode(encoding, 'replace')
        except:
            pass
    if isbytestring(two):
        try:
            two = two.decode(encoding, 'replace')
        except:
            pass
    return cmp(one.lower(), two.lower())

def _author_to_author_sort(x):
    if not x: return ''
    return author_to_author_sort(x.replace('|', ','))

def icu_collator(s1, s2):
    return strcmp(force_unicode(s1, 'utf-8'), force_unicode(s2, 'utf-8'))
# }}}

class Connection(apsw.Connection): # {{{

    BUSY_TIMEOUT = 2000 # milliseconds

    def __init__(self, path):
        apsw.Connection.__init__(self, path)

        self.setbusytimeout(self.BUSY_TIMEOUT)
        self.execute('pragma cache_size=5000')
        self.conn.execute('pragma temp_store=2')

        encoding = self.execute('pragma encoding').fetchone()[0]
        self.conn.create_collation('PYNOCASE', partial(pynocase,
            encoding=encoding))

        self.conn.create_function('title_sort', 1, title_sort)
        self.conn.create_function('author_to_author_sort', 1,
                _author_to_author_sort)

        self.conn.create_function('uuid4', 0, lambda : str(uuid.uuid4()))

        # Dummy functions for dynamically created filters
        self.conn.create_function('books_list_filter', 1, lambda x: 1)
        self.conn.create_collation('icucollate', icu_collator)

    def create_dynamic_filter(self, name):
        f = DynamicFilter(name)
        self.conn.create_function(name, 1, f)

    def get(self, *args, **kw):
        ans = self.cursor().execute(*args)
        if kw.get('all', True):
            return ans.fetchall()
        for row in ans:
            return ans[0]

    def execute(self, sql, bindings=None):
        cursor = self.cursor()
        return cursor.execute(sql, bindings)

    def executemany(self, sql, sequence_of_bindings):
        return self.cursor().executemany(sql, sequence_of_bindings)

    def executescript(self, sql):
        with self:
            # Use an explicit savepoint so that even if this is called
            # while a transaction is active, it is atomic
            return self.cursor().execute(sql)
# }}}

class DB(object, SchemaUpgrade):

    PATH_LIMIT = 40 if iswindows else 100
    WINDOWS_LIBRARY_PATH_LIMIT = 75

    # Initialize database {{{

    def __init__(self, library_path, default_prefs=None, read_only=False):
        try:
            if isbytestring(library_path):
                library_path = library_path.decode(filesystem_encoding)
        except:
            import traceback
            traceback.print_exc()

        self.field_metadata = FieldMetadata()

        self.library_path = os.path.abspath(library_path)
        self.dbpath = os.path.join(library_path, 'metadata.db')
        self.dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH',
                self.dbpath)

        if iswindows and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError(_(
                'Path to library too long. Must be less than'
                ' %d characters.')%(259-4*self.PATH_LIMIT-10))
        exists = self._exists = os.path.exists(self.dbpath)
        if not exists:
            # Be more strict when creating new libraries as the old calculation
            # allowed for max path lengths of 265 chars.
            if (iswindows and len(self.library_path) >
                    self.WINDOWS_LIBRARY_PATH_LIMIT):
                raise ValueError(_(
                    'Path to library too long. Must be less than'
                    ' %d characters.')%self.WINDOWS_LIBRARY_PATH_LIMIT)

        if read_only and os.path.exists(self.dbpath):
            # Work on only a copy of metadata.db to ensure that
            # metadata.db is not changed
            pt = PersistentTemporaryFile('_metadata_ro.db')
            pt.close()
            shutil.copyfile(self.dbpath, pt.name)
            self.dbpath = pt.name

        self.is_case_sensitive = (not iswindows and
            not os.path.exists(self.dbpath.replace('metadata.db',
                'MeTAdAtA.dB')))

        self._conn = None

        if self.user_version == 0:
            self.initialize_database()

        with self.conn:
            SchemaUpgrade.__init__(self)

        # Guarantee that the library_id is set
        self.library_id

        self.initialize_prefs(default_prefs)

        # Fix legacy triggers and columns
        self.conn.executescript('''
        DROP TRIGGER IF EXISTS author_insert_trg;
        CREATE TEMP TRIGGER author_insert_trg
            AFTER INSERT ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name) WHERE id=NEW.id;
        END;
        DROP TRIGGER IF EXISTS author_update_trg;
        CREATE TEMP TRIGGER author_update_trg
            BEFORE UPDATE ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name)
            WHERE id=NEW.id AND name <> NEW.name;
        END;
        UPDATE authors SET sort=author_to_author_sort(name) WHERE sort IS NULL;
        ''')

    def initialize_prefs(self, default_prefs):
        self.prefs = DBPrefs(self)

        if default_prefs is not None and not self._exists:
            # Only apply default prefs to a new database
            for key in default_prefs:
                # be sure that prefs not to be copied are listed below
                if key not in frozenset(['news_to_be_synced']):
                    self.prefs[key] = default_prefs[key]
            if 'field_metadata' in default_prefs:
                fmvals = [f for f in default_prefs['field_metadata'].values()
                                if f['is_custom']]
                for f in fmvals:
                    self.create_custom_column(f['label'], f['name'],
                            f['datatype'], f['is_multiple'] is not None,
                            f['is_editable'], f['display'])

        defs = self.prefs.defaults
        defs['gui_restriction'] = defs['cs_restriction'] = ''
        defs['categories_using_hierarchy'] = []
        defs['column_color_rules'] = []

        # Migrate the bool tristate tweak
        defs['bools_are_tristate'] = \
                tweaks.get('bool_custom_columns_are_tristate', 'yes') == 'yes'
        if self.prefs.get('bools_are_tristate') is None:
            self.prefs.set('bools_are_tristate', defs['bools_are_tristate'])

        # Migrate column coloring rules
        if self.prefs.get('column_color_name_1', None) is not None:
            from calibre.library.coloring import migrate_old_rule
            old_rules = []
            for i in range(1, 6):
                col = self.prefs.get('column_color_name_'+str(i), None)
                templ = self.prefs.get('column_color_template_'+str(i), None)
                if col and templ:
                    try:
                        del self.prefs['column_color_name_'+str(i)]
                        rules = migrate_old_rule(self.field_metadata, templ)
                        for templ in rules:
                            old_rules.append((col, templ))
                    except:
                        pass
            if old_rules:
                self.prefs['column_color_rules'] += old_rules

        # Migrate saved search and user categories to db preference scheme
        def migrate_preference(key, default):
            oldval = prefs[key]
            if oldval != default:
                self.prefs[key] = oldval
                prefs[key] = default
            if key not in self.prefs:
                self.prefs[key] = default

        migrate_preference('user_categories', {})
        migrate_preference('saved_searches', {})

        # migrate grouped_search_terms
        if self.prefs.get('grouped_search_terms', None) is None:
            try:
                ogst = tweaks.get('grouped_search_terms', {})
                ngst = {}
                for t in ogst:
                    ngst[icu_lower(t)] = ogst[t]
                self.prefs.set('grouped_search_terms', ngst)
            except:
                pass

        # Rename any user categories with names that differ only in case
        user_cats = self.prefs.get('user_categories', [])
        catmap = {}
        for uc in user_cats:
            ucl = icu_lower(uc)
            if ucl not in catmap:
                catmap[ucl] = []
            catmap[ucl].append(uc)
        cats_changed = False
        for uc in catmap:
            if len(catmap[uc]) > 1:
                prints('found user category case overlap', catmap[uc])
                cat = catmap[uc][0]
                suffix = 1
                while icu_lower((cat + unicode(suffix))) in catmap:
                    suffix += 1
                prints('Renaming user category %s to %s'%(cat, cat+unicode(suffix)))
                user_cats[cat + unicode(suffix)] = user_cats[cat]
                del user_cats[cat]
                cats_changed = True
        if cats_changed:
            self.prefs.set('user_categories', user_cats)

    @property
    def conn(self):
        if self._conn is None:
            self._conn = apsw.Connection(self.dbpath)
            if self._exists and self.user_version == 0:
                self._conn.close()
                os.remove(self.dbpath)
                self._conn = apsw.Connection(self.dbpath)
        return self._conn

    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'

        def fget(self):
            return self.conn.get('pragma user_version;', all=False)

        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))

        return property(doc=doc, fget=fget, fset=fset)

    def initialize_database(self):
        metadata_sqlite = P('metadata_sqlite.sql', data=True,
                allow_user_override=False).decode('utf-8')
        self.conn.executescript(metadata_sqlite)
        if self.user_version == 0:
            self.user_version = 1
    # }}}

    # Database layer API {{{

    @classmethod
    def exists_at(cls, path):
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    @dynamic_property
    def library_id(self):
        doc = ('The UUID for this library. As long as the user only operates'
                ' on libraries with calibre, it will be unique')

        def fget(self):
            if getattr(self, '_library_id_', None) is None:
                ans = self.conn.get('SELECT uuid FROM library_id', all=False)
                if ans is None:
                    ans = str(uuid.uuid4())
                    self.library_id = ans
                else:
                    self._library_id_ = ans
            return self._library_id_

        def fset(self, val):
            self._library_id_ = unicode(val)
            self.conn.execute('''
                    DELETE FROM library_id;
                    INSERT INTO library_id (uuid) VALUES (?);
                    ''', self._library_id_)

        return property(doc=doc, fget=fget, fset=fset)

    def last_modified(self):
        ''' Return last modified time as a UTC datetime object '''
        return utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def read_tables(self):
        tables = {}
        for col in ('title', 'sort', 'author_sort', 'series_index', 'comments',
                'timestamp', 'published', 'uuid', 'path', 'cover',
                'last_modified'):
            metadata = self.field_metadata[col].copy()
            if metadata['table'] is None:
                metadata['table'], metadata['column'] == 'books', ('has_cover'
                        if col == 'cover' else col)
            tables[col] = OneToOneTable(col, metadata)

        for col in ('series', 'publisher', 'rating'):
            tables[col] = ManyToOneTable(col, self.field_metadata[col].copy())

        for col in ('authors', 'tags', 'formats', 'identifiers'):
            cls = {
                    'authors':AuthorsTable,
                    'formats':FormatsTable,
                    'identifiers':IdentifiersTable,
                  }.get(col, ManyToManyTable)
            tables[col] = cls(col, self.field_metadata[col].copy())

        tables['size'] = SizeTable('size', self.field_metadata['size'].copy())

        with self.conn: # Use a single transaction, to ensure nothing modifies
                        # the db while we are reading
            for table in tables.itervalues():
                try:
                    table.read()
                except:
                    prints('Failed to read table:', table.name)
                    raise

        return tables

   # }}}

