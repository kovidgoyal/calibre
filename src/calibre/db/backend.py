#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

# Imports {{{
import os, shutil, uuid, json, glob, time, cPickle, hashlib, errno, sys
from functools import partial

import apsw

from calibre import isbytestring, force_unicode, prints, as_unicode
from calibre.constants import (iswindows, filesystem_encoding,
        preferred_encoding)
from calibre.ptempfile import PersistentTemporaryFile, TemporaryFile
from calibre.db import SPOOL_SIZE
from calibre.db.schema_upgrades import SchemaUpgrade
from calibre.db.delete_service import delete_service
from calibre.db.errors import NoSuchFormat
from calibre.library.field_metadata import FieldMetadata
from calibre.ebooks.metadata import title_sort, author_to_author_sort
from calibre.utils.icu import sort_key
from calibre.utils.config import to_json, from_json, prefs, tweaks
from calibre.utils.date import utcfromtimestamp, parse_date
from calibre.utils.filenames import (
    is_case_sensitive, samefile, hardlink_file, ascii_filename,
    WindowsAtomicFolderMove, atomic_rename, remove_dir_if_empty,
    copytree_using_links, copyfile_using_links)
from calibre.utils.img import save_cover_data_to
from calibre.utils.formatter_functions import (load_user_template_functions,
            unload_user_template_functions,
            compile_user_template_functions,
            formatter_functions)
import calibre.utils.safe_pickle as safe_pickle
from calibre.db.tables import (OneToOneTable, ManyToOneTable, ManyToManyTable,
        SizeTable, FormatsTable, AuthorsTable, IdentifiersTable, PathTable,
        CompositeTable, UUIDTable, RatingTable)
# }}}

'''
Differences in semantics from pysqlite:

    1. execute/executemany operate in autocommit mode
    2. There is no fetchone() method on cursor objects, instead use next()
    3. There is no executescript

'''
CUSTOM_DATA_TYPES = frozenset(['rating', 'text', 'comments', 'datetime',
    'int', 'float', 'bool', 'series', 'composite', 'enumeration'])
WINDOWS_RESERVED_NAMES = frozenset('CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9'.split())


class DynamicFilter(object):  # {{{

    'No longer used, present for legacy compatibility'

    def __init__(self, name):
        self.name = name
        self.ids = frozenset([])

    def __call__(self, id_):
        return int(id_ in self.ids)

    def change(self, ids):
        self.ids = frozenset(ids)
# }}}


class DBPrefs(dict):  # {{{

    'Store preferences as key:value pairs in the db'

    def __init__(self, db):
        dict.__init__(self)
        self.db = db
        self.defaults = {}
        self.disable_setting = False
        self.load_from_db()

    def load_from_db(self):
        self.clear()
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
        # sort_keys=True is required so that the serialization of dictionaries is
        # not random, which is needed for the changed check in __setitem__
        return json.dumps(val, indent=2, default=to_json, sort_keys=True)

    def has_setting(self, key):
        return key in self

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.db.execute('DELETE FROM preferences WHERE key=?', (key,))

    def __setitem__(self, key, val):
        if not self.disable_setting:
            raw = self.to_raw(val)
            with self.db.conn:
                try:
                    dbraw = self.db.execute('SELECT id,val FROM preferences WHERE key=?', (key,)).next()
                except StopIteration:
                    dbraw = None
                if dbraw is None or dbraw[1] != raw:
                    if dbraw is None:
                        self.db.execute('INSERT INTO preferences (key,val) VALUES (?,?)', (key, raw))
                    else:
                        self.db.execute('UPDATE preferences SET val=? WHERE id=?', (raw, dbraw[0]))
                    dict.__setitem__(self, key, val)

    def set(self, key, val):
        self.__setitem__(key, val)

    def get_namespaced(self, namespace, key, default=None):
        key = u'namespaced:%s:%s'%(namespace, key)
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return default

    def set_namespaced(self, namespace, key, val):
        if u':' in key:
            raise KeyError('Colons are not allowed in keys')
        if u':' in namespace:
            raise KeyError('Colons are not allowed in the namespace')
        key = u'namespaced:%s:%s'%(namespace, key)
        self[key] = val

    def write_serialized(self, library_path):
        try:
            to_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
            with open(to_filename, "wb") as f:
                f.write(json.dumps(self, indent=2, default=to_json))
        except:
            import traceback
            traceback.print_exc()

    @classmethod
    def read_serialized(cls, library_path, recreate_prefs=False):
        from_filename = os.path.join(library_path,
                'metadata_db_prefs_backup.json')
        with open(from_filename, "rb") as f:
            return json.load(f, object_hook=from_json)
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
    if not x:
        return ''
    return author_to_author_sort(x.replace('|', ','))


def icu_collator(s1, s2):
    return cmp(sort_key(force_unicode(s1, 'utf-8')),
               sort_key(force_unicode(s2, 'utf-8')))

# }}}

# Unused aggregators {{{


def Concatenate(sep=','):
    '''String concatenation aggregator for sqlite'''

    def step(ctxt, value):
        if value is not None:
            ctxt.append(value)

    def finalize(ctxt):
        if not ctxt:
            return None
        return sep.join(ctxt)

    return ([], step, finalize)


def SortedConcatenate(sep=','):
    '''String concatenation aggregator for sqlite, sorted by supplied index'''

    def step(ctxt, ndx, value):
        if value is not None:
            ctxt[ndx] = value

    def finalize(ctxt):
        if len(ctxt) == 0:
            return None
        return sep.join(map(ctxt.get, sorted(ctxt.iterkeys())))

    return ({}, step, finalize)


def IdentifiersConcat():
    '''String concatenation aggregator for the identifiers map'''

    def step(ctxt, key, val):
        ctxt.append(u'%s:%s'%(key, val))

    def finalize(ctxt):
        return ','.join(ctxt)

    return ([], step, finalize)


def AumSortedConcatenate():
    '''String concatenation aggregator for the author sort map'''

    def step(ctxt, ndx, author, sort, link):
        if author is not None:
            ctxt[ndx] = ':::'.join((author, sort, link))

    def finalize(ctxt):
        keys = list(ctxt.iterkeys())
        l = len(keys)
        if l == 0:
            return None
        if l == 1:
            return ctxt[keys[0]]
        return ':#:'.join([ctxt[v] for v in sorted(keys)])

    return ({}, step, finalize)

# }}}


class Connection(apsw.Connection):  # {{{

    BUSY_TIMEOUT = 10000  # milliseconds

    def __init__(self, path):
        apsw.Connection.__init__(self, path)

        self.setbusytimeout(self.BUSY_TIMEOUT)
        self.execute('pragma cache_size=-5000')
        self.execute('pragma temp_store=2')

        encoding = self.execute('pragma encoding').next()[0]
        self.createcollation('PYNOCASE', partial(pynocase,
            encoding=encoding))

        self.createscalarfunction('title_sort', title_sort, 1)
        self.createscalarfunction('author_to_author_sort',
                _author_to_author_sort, 1)
        self.createscalarfunction('uuid4', lambda: str(uuid.uuid4()),
                0)

        # Dummy functions for dynamically created filters
        self.createscalarfunction('books_list_filter', lambda x: 1, 1)
        self.createcollation('icucollate', icu_collator)

        # Legacy aggregators (never used) but present for backwards compat
        self.createaggregatefunction('sortconcat', SortedConcatenate, 2)
        self.createaggregatefunction('sortconcat_bar',
                partial(SortedConcatenate, sep='|'), 2)
        self.createaggregatefunction('sortconcat_amper',
                partial(SortedConcatenate, sep='&'), 2)
        self.createaggregatefunction('identifiers_concat',
                IdentifiersConcat, 2)
        self.createaggregatefunction('concat', Concatenate, 1)
        self.createaggregatefunction('aum_sortconcat',
                AumSortedConcatenate, 4)

    def create_dynamic_filter(self, name):
        f = DynamicFilter(name)
        self.createscalarfunction(name, f, 1)

    def get(self, *args, **kw):
        ans = self.cursor().execute(*args)
        if kw.get('all', True):
            return ans.fetchall()
        try:
            return ans.next()[0]
        except (StopIteration, IndexError):
            return None

    def execute(self, sql, bindings=None):
        cursor = self.cursor()
        return cursor.execute(sql, bindings)

    def executemany(self, sql, sequence_of_bindings):
        with self:  # Disable autocommit mode, for performance
            return self.cursor().executemany(sql, sequence_of_bindings)

# }}}


def set_global_state(backend):
    load_user_template_functions(
        backend.library_id, (), precompiled_user_functions=backend.get_user_template_functions())


class DB(object):

    PATH_LIMIT = 40 if iswindows else 100
    WINDOWS_LIBRARY_PATH_LIMIT = 75

    # Initialize database {{{

    def __init__(self, library_path, default_prefs=None, read_only=False,
                 restore_all_prefs=False, progress_callback=lambda x, y:True,
                 load_user_formatter_functions=True):
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
                'Path to library ({0}) too long. Must be less than'
                ' {1} characters.').format(self.library_path, 259-4*self.PATH_LIMIT-10))
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

        if not os.path.exists(os.path.dirname(self.dbpath)):
            os.makedirs(os.path.dirname(self.dbpath))

        self._conn = None
        if self.user_version == 0:
            self.initialize_database()

        if not os.path.exists(self.library_path):
            os.makedirs(self.library_path)
        self.is_case_sensitive = is_case_sensitive(self.library_path)

        SchemaUpgrade(self, self.library_path, self.field_metadata)

        # Guarantee that the library_id is set
        self.library_id

        # Fix legacy triggers and columns
        self.execute('''
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

        # Initialize_prefs must be called before initialize_custom_columns because
        # icc can set a pref.
        self.initialize_prefs(default_prefs, restore_all_prefs, progress_callback)
        self.initialize_custom_columns()
        self.initialize_tables()
        self.set_user_template_functions(compile_user_template_functions(
                                 self.prefs.get('user_template_functions', [])))
        if load_user_formatter_functions:
            set_global_state(self)

    def get_template_functions(self):
        return self._template_functions

    def get_user_template_functions(self):
        return self._user_template_functions

    def set_user_template_functions(self, user_formatter_functions):
        self._user_template_functions = user_formatter_functions
        self._template_functions = formatter_functions().get_builtins().copy()
        self._template_functions.update(user_formatter_functions)

    def initialize_prefs(self, default_prefs, restore_all_prefs, progress_callback):  # {{{
        self.prefs = DBPrefs(self)

        if default_prefs is not None and not self._exists:
            progress_callback(None, len(default_prefs))
            # Only apply default prefs to a new database
            for i, key in enumerate(default_prefs):
                # be sure that prefs not to be copied are listed below
                if restore_all_prefs or key not in frozenset(['news_to_be_synced']):
                    self.prefs[key] = default_prefs[key]
                    progress_callback(_('restored preference ') + key, i+1)
            if 'field_metadata' in default_prefs:
                fmvals = [f for f in default_prefs['field_metadata'].values()
                                if f['is_custom']]
                progress_callback(None, len(fmvals))
                for i, f in enumerate(fmvals):
                    progress_callback(_('creating custom column ') + f['label'], i)
                    self.create_custom_column(f['label'], f['name'],
                            f['datatype'],
                            (f['is_multiple'] is not None and
                                len(f['is_multiple']) > 0),
                            f['is_editable'], f['display'])

        defs = self.prefs.defaults
        defs['gui_restriction'] = defs['cs_restriction'] = ''
        defs['categories_using_hierarchy'] = []
        defs['column_color_rules'] = []
        defs['column_icon_rules'] = []
        defs['cover_grid_icon_rules'] = []
        defs['grouped_search_make_user_categories'] = []
        defs['similar_authors_search_key'] = 'authors'
        defs['similar_authors_match_kind'] = 'match_any'
        defs['similar_publisher_search_key'] = 'publisher'
        defs['similar_publisher_match_kind'] = 'match_any'
        defs['similar_tags_search_key'] = 'tags'
        defs['similar_tags_match_kind'] = 'match_all'
        defs['similar_series_search_key'] = 'series'
        defs['similar_series_match_kind'] = 'match_any'
        defs['book_display_fields'] = [
        ('title', False), ('authors', True), ('series', True),
        ('identifiers', True), ('tags', True), ('formats', True),
        ('path', True), ('publisher', False), ('rating', False),
        ('author_sort', False), ('sort', False), ('timestamp', False),
        ('uuid', False), ('comments', True), ('id', False), ('pubdate', False),
        ('last_modified', False), ('size', False), ('languages', False),
        ]
        defs['popup_book_display_fields'] = [('title', True)] + [(f[0], True) for f in defs['book_display_fields'] if f[0] != 'title']
        defs['qv_display_fields'] = [('title', True), ('authors', True), ('series', True)]
        defs['virtual_libraries'] = {}
        defs['virtual_lib_on_startup'] = defs['cs_virtual_lib_on_startup'] = ''
        defs['virt_libs_hidden'] = defs['virt_libs_order'] = ()
        defs['update_all_last_mod_dates_on_start'] = False
        defs['field_under_covers_in_grid'] = 'title'
        defs['cover_browser_title_template'] = '{title}'
        defs['cover_browser_subtitle_field'] = 'rating'

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

        # migrate the gui_restriction preference to a virtual library
        gr_pref = self.prefs.get('gui_restriction', None)
        if gr_pref:
            virt_libs = self.prefs.get('virtual_libraries', {})
            virt_libs[gr_pref] = 'search:"' + gr_pref + '"'
            self.prefs['virtual_libraries'] = virt_libs
            self.prefs['gui_restriction'] = ''
            self.prefs['virtual_lib_on_startup'] = gr_pref

        # migrate the cs_restriction preference to a virtual library
        gr_pref = self.prefs.get('cs_restriction', None)
        if gr_pref:
            virt_libs = self.prefs.get('virtual_libraries', {})
            virt_libs[gr_pref] = 'search:"' + gr_pref + '"'
            self.prefs['virtual_libraries'] = virt_libs
            self.prefs['cs_restriction'] = ''
            self.prefs['cs_virtual_lib_on_startup'] = gr_pref

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
    # }}}

    def initialize_custom_columns(self):  # {{{
        self.custom_columns_deleted = False
        with self.conn:
            # Delete previously marked custom columns
            for record in self.conn.get(
                    'SELECT id FROM custom_columns WHERE mark_for_delete=1'):
                num = record[0]
                table, lt = self.custom_table_names(num)
                self.execute('''\
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
                self.prefs.set('update_all_last_mod_dates_on_start', True)
            self.execute('DELETE FROM custom_columns WHERE mark_for_delete=1')

        # Load metadata for custom columns
        self.custom_column_label_map, self.custom_column_num_map = {}, {}
        self.custom_column_num_to_label_map = {}
        triggers = []
        remove = []
        custom_tables = self.custom_tables
        for record in self.conn.get(
                'SELECT label,name,datatype,editable,display,normalized,id,is_multiple FROM custom_columns'):
            data = {
                    'label':record[0],
                    'name':record[1],
                    'datatype':record[2],
                    'editable':bool(record[3]),
                    'display':json.loads(record[4]),
                    'normalized':bool(record[5]),
                    'num':record[6],
                    'is_multiple':bool(record[7]),
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

            self.custom_column_num_map[data['num']] = \
                self.custom_column_label_map[data['label']] = data
            self.custom_column_num_to_label_map[data['num']] = data['label']

            # Create Foreign Key triggers
            if data['normalized']:
                trigger = 'DELETE FROM %s WHERE book=OLD.id;'%lt
            else:
                trigger = 'DELETE FROM %s WHERE book=OLD.id;'%table
            triggers.append(trigger)

        if remove:
            with self.conn:
                for data in remove:
                    prints('WARNING: Custom column %r not found, removing.' %
                            data['label'])
                    self.execute('DELETE FROM custom_columns WHERE id=?',
                            (data['num'],))

        if triggers:
            with self.conn:
                self.execute('''\
                    CREATE TEMP TRIGGER custom_books_delete_trg
                        AFTER DELETE ON books
                        BEGIN
                        %s
                    END;
                    '''%(' \n'.join(triggers)))

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
                'int': adapt_number,
                'rating':lambda x,d: x if x is None else min(10., max(0., float(x))),
                'bool': adapt_bool,
                'comments': lambda x,d: adapt_text(x, {'is_multiple':False}),
                'datetime': adapt_datetime,
                'text':adapt_text,
                'series':adapt_text,
                'enumeration': adapt_enum
        }

        # Create Tag Browser categories for custom columns
        for k in sorted(self.custom_column_label_map.iterkeys()):
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

    # }}}

    def initialize_tables(self):  # {{{
        tables = self.tables = {}
        for col in ('title', 'sort', 'author_sort', 'series_index', 'comments',
                'timestamp', 'pubdate', 'uuid', 'path', 'cover',
                'last_modified'):
            metadata = self.field_metadata[col].copy()
            if col == 'comments':
                metadata['table'], metadata['column'] = 'comments', 'text'
            if not metadata['table']:
                metadata['table'], metadata['column'] = 'books', ('has_cover'
                        if col == 'cover' else col)
            if not metadata['column']:
                metadata['column'] = col
            tables[col] = (PathTable if col == 'path' else UUIDTable if col == 'uuid' else OneToOneTable)(col, metadata)

        for col in ('series', 'publisher'):
            tables[col] = ManyToOneTable(col, self.field_metadata[col].copy())

        for col in ('authors', 'tags', 'formats', 'identifiers', 'languages', 'rating'):
            cls = {
                    'authors':AuthorsTable,
                    'formats':FormatsTable,
                    'identifiers':IdentifiersTable,
                    'rating':RatingTable,
                  }.get(col, ManyToManyTable)
            tables[col] = cls(col, self.field_metadata[col].copy())

        tables['size'] = SizeTable('size', self.field_metadata['size'].copy())

        self.FIELD_MAP = {
            'id':0, 'title':1, 'authors':2, 'timestamp':3, 'size':4,
            'rating':5, 'tags':6, 'comments':7, 'series':8, 'publisher':9,
            'series_index':10, 'sort':11, 'author_sort':12, 'formats':13,
            'path':14, 'pubdate':15, 'uuid':16, 'cover':17, 'au_map':18,
            'last_modified':19, 'identifiers':20, 'languages':21,
        }

        for k,v in self.FIELD_MAP.iteritems():
            self.field_metadata.set_field_record_index(k, v, prefer_custom=False)

        base = max(self.FIELD_MAP.itervalues())

        for label_ in sorted(self.custom_column_label_map):
            data = self.custom_column_label_map[label_]
            label = self.field_metadata.custom_field_prefix + label_
            metadata = self.field_metadata[label].copy()
            link_table = self.custom_table_names(data['num'])[1]
            self.FIELD_MAP[data['num']] = base = base+1
            self.field_metadata.set_field_record_index(label_, base,
                    prefer_custom=True)
            if data['datatype'] == 'series':
                # account for the series index column. Field_metadata knows that
                # the series index is one larger than the series. If you change
                # it here, be sure to change it there as well.
                self.FIELD_MAP[str(data['num'])+'_index'] = base = base+1
                self.field_metadata.set_field_record_index(label_+'_index', base,
                            prefer_custom=True)

            if data['normalized']:
                if metadata['is_multiple']:
                    tables[label] = ManyToManyTable(label, metadata,
                            link_table=link_table)
                else:
                    tables[label] = ManyToOneTable(label, metadata,
                            link_table=link_table)
                    if metadata['datatype'] == 'series':
                        # Create series index table
                        label += '_index'
                        metadata = self.field_metadata[label].copy()
                        metadata['column'] = 'extra'
                        metadata['table'] = link_table
                        tables[label] = OneToOneTable(label, metadata)
            else:
                if data['datatype'] == 'composite':
                    tables[label] = CompositeTable(label, metadata)
                else:
                    tables[label] = OneToOneTable(label, metadata)

        self.FIELD_MAP['ondevice'] = base = base+1
        self.field_metadata.set_field_record_index('ondevice', base, prefer_custom=False)
        self.FIELD_MAP['marked'] = base = base+1
        self.field_metadata.set_field_record_index('marked', base, prefer_custom=False)
        self.FIELD_MAP['series_sort'] = base = base+1
        self.field_metadata.set_field_record_index('series_sort', base, prefer_custom=False)

    # }}}

    @property
    def conn(self):
        if self._conn is None:
            self._conn = Connection(self.dbpath)
            if self._exists and self.user_version == 0:
                self._conn.close()
                os.remove(self.dbpath)
                self._conn = Connection(self.dbpath)
        return self._conn

    def execute(self, sql, bindings=None):
        try:
            return self.conn.cursor().execute(sql, bindings)
        except apsw.IOError:
            # This can happen if the computer was suspended see for example:
            # https://bugs.launchpad.net/bugs/1286522. Try to reopen the db
            if not self.conn.getautocommit():
                raise  # We are in a transaction, re-opening the db will fail anyway
            self.reopen(force=True)
            return self.conn.cursor().execute(sql, bindings)

    def executemany(self, sql, sequence_of_bindings):
        try:
            with self.conn:  # Disable autocommit mode, for performance
                return self.conn.cursor().executemany(sql, sequence_of_bindings)
        except apsw.IOError:
            # This can happen if the computer was suspended see for example:
            # https://bugs.launchpad.net/bugs/1286522. Try to reopen the db
            if not self.conn.getautocommit():
                raise  # We are in a transaction, re-opening the db will fail anyway
            self.reopen(force=True)
            with self.conn:  # Disable autocommit mode, for performance
                return self.conn.cursor().executemany(sql, sequence_of_bindings)

    def get(self, *args, **kw):
        ans = self.execute(*args)
        if kw.get('all', True):
            return ans.fetchall()
        try:
            return ans.next()[0]
        except (StopIteration, IndexError):
            return None

    def last_insert_rowid(self):
        return self.conn.last_insert_rowid()

    def custom_field_name(self, label=None, num=None):
        if label is not None:
            return self.field_metadata.custom_field_prefix + label
        return self.field_metadata.custom_field_prefix + self.custom_column_num_to_label_map[num]

    def custom_field_metadata(self, label=None, num=None):
        if label is not None:
            return self.custom_column_label_map[label]
        return self.custom_column_num_map[num]

    def set_custom_column_metadata(self, num, name=None, label=None, is_editable=None, display=None):
        changed = False
        if name is not None:
            self.execute('UPDATE custom_columns SET name=? WHERE id=?', (name, num))
            changed = True
        if label is not None:
            self.execute('UPDATE custom_columns SET label=? WHERE id=?', (label, num))
            changed = True
        if is_editable is not None:
            self.execute('UPDATE custom_columns SET editable=? WHERE id=?', (bool(is_editable), num))
            self.custom_column_num_map[num]['is_editable'] = bool(is_editable)
            changed = True
        if display is not None:
            self.execute('UPDATE custom_columns SET display=? WHERE id=?', (json.dumps(display), num))
            changed = True
        # Note: the caller is responsible for scheduling a metadata backup if necessary
        return changed

    def create_custom_column(self, label, name, datatype, is_multiple, editable=True, display={}):  # {{{
        import re
        if not label:
            raise ValueError(_('No label was provided'))
        if re.match('^\w*$', label) is None or not label[0].isalpha() or label.lower() != label:
            raise ValueError(_('The label must contain only lower case letters, digits and underscores, and start with a letter'))
        if datatype not in CUSTOM_DATA_TYPES:
            raise ValueError('%r is not a supported data type'%datatype)
        normalized  = datatype not in ('datetime', 'comments', 'int', 'bool',
                'float', 'composite')
        is_multiple = is_multiple and datatype in ('text', 'composite')
        self.execute(
                ('INSERT INTO '
                'custom_columns(label,name,datatype,is_multiple,editable,display,normalized)'
                'VALUES (?,?,?,?,?,?,?)'),
                (label, name, datatype, is_multiple, editable, json.dumps(display), normalized))
        num = self.conn.last_insert_rowid()

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
        self.execute(script)
        self.prefs.set('update_all_last_mod_dates_on_start', True)
        return num
    # }}}

    def delete_custom_column(self, label=None, num=None):
        data = self.custom_field_metadata(label, num)
        self.execute('UPDATE custom_columns SET mark_for_delete=1 WHERE id=?', (data['num'],))

    def close(self, force=False, unload_formatter_functions=True):
        if getattr(self, '_conn', None) is not None:
            if unload_formatter_functions:
                try:
                    unload_user_template_functions(self.library_id)
                except Exception:
                    pass
            self._conn.close(force)
            del self._conn

    def reopen(self, force=False):
        self.close(force=force, unload_formatter_functions=False)
        self._conn = None
        self.conn

    def dump_and_restore(self, callback=None, sql=None):
        import codecs
        from calibre.utils.apsw_shell import Shell
        from contextlib import closing
        if callback is None:
            callback = lambda x: x
        uv = int(self.user_version)

        with TemporaryFile(suffix='.sql') as fname:
            if sql is None:
                callback(_('Dumping database to SQL') + '...')
                with codecs.open(fname, 'wb', encoding='utf-8') as buf:
                    shell = Shell(db=self.conn, stdout=buf)
                    shell.process_command('.dump')
            else:
                with open(fname, 'wb') as buf:
                    buf.write(sql if isinstance(sql, bytes) else sql.encode('utf-8'))

            with TemporaryFile(suffix='_tmpdb.db', dir=os.path.dirname(self.dbpath)) as tmpdb:
                callback(_('Restoring database from SQL') + '...')
                with closing(Connection(tmpdb)) as conn:
                    shell = Shell(db=conn, encoding='utf-8')
                    shell.process_command('.read ' + fname.replace(os.sep, '/'))
                    conn.execute('PRAGMA user_version=%d;'%uv)

                self.close(unload_formatter_functions=False)
                try:
                    atomic_rename(tmpdb, self.dbpath)
                finally:
                    self.reopen()

    def vacuum(self):
        self.execute('VACUUM')

    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'

        def fget(self):
            return self.conn.get('pragma user_version;', all=False)

        def fset(self, val):
            self.execute('pragma user_version=%d'%int(val))

        return property(doc=doc, fget=fget, fset=fset)

    def initialize_database(self):
        metadata_sqlite = P('metadata_sqlite.sql', data=True,
                allow_user_override=False).decode('utf-8')
        cur = self.conn.cursor()
        cur.execute('BEGIN EXCLUSIVE TRANSACTION')
        try:
            cur.execute(metadata_sqlite)
        except:
            cur.execute('ROLLBACK')
        else:
            cur.execute('COMMIT')
        if self.user_version == 0:
            self.user_version = 1
    # }}}

    def normpath(self, path):
        path = os.path.abspath(os.path.realpath(path))
        if not self.is_case_sensitive:
            path = os.path.normcase(path).lower()
        return path

    def is_deletable(self, path):
        return path and not self.normpath(self.library_path).startswith(self.normpath(path))

    def rmtree(self, path):
        if self.is_deletable(path):
            try:
                shutil.rmtree(path)
            except EnvironmentError as e:
                if e.errno == errno.ENOENT and not os.path.exists(path):
                    return
                import traceback
                traceback.print_exc()
                time.sleep(1)  # In case something has temporarily locked a file
                shutil.rmtree(path)

    def construct_path_name(self, book_id, title, author):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        book_id = ' (%d)' % book_id
        l = self.PATH_LIMIT - (len(book_id) // 2) - 2
        author = ascii_filename(author)[:l].decode('ascii', 'replace')
        title  = ascii_filename(title.lstrip())[:l].decode('ascii', 'replace').rstrip()
        if not title:
            title = 'Unknown'[:l]
        try:
            while author[-1] in (' ', '.'):
                author = author[:-1]
        except IndexError:
            author = ''
        if not author:
            author = ascii_filename(_('Unknown')).decode(
                    'ascii', 'replace')
        if author.upper() in WINDOWS_RESERVED_NAMES:
            author += 'w'
        return '%s/%s%s' % (author, title, book_id)

    def construct_file_name(self, book_id, title, author, extlen):
        '''
        Construct the file name for this book based on its metadata.
        '''
        extlen = max(extlen, 14)  # 14 accounts for ORIGINAL_EPUB
        # The PATH_LIMIT on windows already takes into account the doubling
        # (it is used to enforce the total path length limit, individual path
        # components can be much longer than the total path length would allow on
        # windows).
        l = (self.PATH_LIMIT - (extlen // 2) - 2) if iswindows else ((self.PATH_LIMIT - extlen - 2) // 2)
        if l < 5:
            raise ValueError('Extension length too long: %d' % extlen)
        author = ascii_filename(author)[:l].decode('ascii', 'replace')
        title  = ascii_filename(title.lstrip())[:l].decode('ascii', 'replace').rstrip()
        if not title:
            title = 'Unknown'[:l]
        name   = title + ' - ' + author
        while name.endswith('.'):
            name = name[:-1]
        if not name:
            name = ascii_filename(_('Unknown')).decode('ascii', 'replace')
        return name

    # Database layer API {{{

    def custom_table_names(self, num):
        return 'custom_column_%d'%num, 'books_custom_column_%d_link'%num

    @property
    def custom_tables(self):
        return set([x[0] for x in self.conn.get(
            'SELECT name FROM sqlite_master WHERE type="table" AND '
            '(name GLOB "custom_column_*" OR name GLOB "books_custom_column_*")')])

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
            self.execute('''
                    DELETE FROM library_id;
                    INSERT INTO library_id (uuid) VALUES (?);
                    ''', (self._library_id_,))

        return property(doc=doc, fget=fget, fset=fset)

    def last_modified(self):
        ''' Return last modified time as a UTC datetime object '''
        return utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def read_tables(self):
        '''
        Read all data from the db into the python in-memory tables
        '''

        with self.conn:  # Use a single transaction, to ensure nothing modifies the db while we are reading
            for table in self.tables.itervalues():
                try:
                    table.read(self)
                except:
                    prints('Failed to read table:', table.name)
                    import pprint
                    pprint.pprint(table.metadata)
                    raise

    def format_abspath(self, book_id, fmt, fname, path):
        path = os.path.join(self.library_path, path)
        fmt = ('.' + fmt.lower()) if fmt else ''
        fmt_path = os.path.join(path, fname+fmt)
        if os.path.exists(fmt_path):
            return fmt_path
        try:
            candidates = glob.glob(os.path.join(path, '*'+fmt))
        except:  # If path contains strange characters this throws an exc
            candidates = []
        if fmt and candidates and os.path.exists(candidates[0]):
            shutil.copyfile(candidates[0], fmt_path)
            return fmt_path

    def cover_abspath(self, book_id, path):
        path = os.path.join(self.library_path, path)
        fmt_path = os.path.join(path, 'cover.jpg')
        if os.path.exists(fmt_path):
            return fmt_path

    def apply_to_format(self, book_id, path, fname, fmt, func, missing_value=None):
        path = self.format_abspath(book_id, fmt, fname, path)
        if path is None:
            return missing_value
        with lopen(path, 'r+b') as f:
            return func(f)

    def format_hash(self, book_id, fmt, fname, path):
        path = self.format_abspath(book_id, fmt, fname, path)
        if path is None:
            raise NoSuchFormat('Record %d has no fmt: %s'%(book_id, fmt))
        sha = hashlib.sha256()
        with lopen(path, 'rb') as f:
            while True:
                raw = f.read(SPOOL_SIZE)
                sha.update(raw)
                if len(raw) < SPOOL_SIZE:
                    break
        return sha.hexdigest()

    def format_metadata(self, book_id, fmt, fname, path):
        path = self.format_abspath(book_id, fmt, fname, path)
        ans = {}
        if path is not None:
            stat = os.stat(path)
            ans['path'] = path
            ans['size'] = stat.st_size
            ans['mtime'] = utcfromtimestamp(stat.st_mtime)
        return ans

    def has_format(self, book_id, fmt, fname, path):
        return self.format_abspath(book_id, fmt, fname, path) is not None

    def remove_formats(self, remove_map):
        paths = []
        for book_id, removals in remove_map.iteritems():
            for fmt, fname, path in removals:
                path = self.format_abspath(book_id, fmt, fname, path)
                if path is not None:
                    paths.append(path)
        try:
            delete_service().delete_files(paths, self.library_path)
        except:
            import traceback
            traceback.print_exc()

    def cover_last_modified(self, path):
        path = os.path.abspath(os.path.join(self.library_path, path, 'cover.jpg'))
        try:
            return utcfromtimestamp(os.stat(path).st_mtime)
        except EnvironmentError:
            pass  # Cover doesn't exist

    def copy_cover_to(self, path, dest, windows_atomic_move=None, use_hardlink=False, report_file_size=None):
        path = os.path.abspath(os.path.join(self.library_path, path, 'cover.jpg'))
        if windows_atomic_move is not None:
            if not isinstance(dest, basestring):
                raise Exception("Error, you must pass the dest as a path when"
                        " using windows_atomic_move")
            if os.access(path, os.R_OK) and dest and not samefile(dest, path):
                windows_atomic_move.copy_path_to(path, dest)
                return True
        else:
            if os.access(path, os.R_OK):
                try:
                    f = lopen(path, 'rb')
                except (IOError, OSError):
                    time.sleep(0.2)
                    try:
                        f = lopen(path, 'rb')
                    except (IOError, OSError) as e:
                        # Ensure the path that caused this error is reported
                        raise Exception('Failed to open %r with error: %s' % (path, e))

                with f:
                    if hasattr(dest, 'write'):
                        if report_file_size is not None:
                            f.seek(0, os.SEEK_END)
                            report_file_size(f.tell())
                            f.seek(0)
                        shutil.copyfileobj(f, dest)
                        if hasattr(dest, 'flush'):
                            dest.flush()
                        return True
                    elif dest and not samefile(dest, path):
                        if use_hardlink:
                            try:
                                hardlink_file(path, dest)
                                return True
                            except:
                                pass
                        with lopen(dest, 'wb') as d:
                            shutil.copyfileobj(f, d)
                        return True
        return False

    def cover_or_cache(self, path, timestamp):
        path = os.path.abspath(os.path.join(self.library_path, path, 'cover.jpg'))
        try:
            stat = os.stat(path)
        except EnvironmentError:
            return False, None, None
        if abs(timestamp - stat.st_mtime) < 0.1:
            return True, None, None
        try:
            f = lopen(path, 'rb')
        except (IOError, OSError):
            time.sleep(0.2)
        f = lopen(path, 'rb')
        with f:
            return True, f.read(), stat.st_mtime

    def set_cover(self, book_id, path, data, no_processing=False):
        path = os.path.abspath(os.path.join(self.library_path, path))
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            from calibre.gui2 import pixmap_to_data
            data = pixmap_to_data(data)
        elif callable(getattr(data, 'read', None)):
            data = data.read()
        if data is None:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except (IOError, OSError):
                    time.sleep(0.2)
                    os.remove(path)
        else:
            if no_processing:
                with lopen(path, 'wb') as f:
                    f.write(data)
            else:
                try:
                    save_cover_data_to(data, path)
                except (IOError, OSError):
                    time.sleep(0.2)
                    save_cover_data_to(data, path)

    def copy_format_to(self, book_id, fmt, fname, path, dest,
                       windows_atomic_move=None, use_hardlink=False, report_file_size=None):
        path = self.format_abspath(book_id, fmt, fname, path)
        if path is None:
            return False
        if windows_atomic_move is not None:
            if not isinstance(dest, basestring):
                raise Exception("Error, you must pass the dest as a path when"
                        " using windows_atomic_move")
            if dest:
                if samefile(dest, path):
                    # Ensure that the file has the same case as dest
                    try:
                        if path != dest:
                            os.rename(path, dest)
                    except:
                        pass  # Nothing too catastrophic happened, the cases mismatch, that's all
                else:
                    windows_atomic_move.copy_path_to(path, dest)
        else:
            if hasattr(dest, 'write'):
                with lopen(path, 'rb') as f:
                    if report_file_size is not None:
                        f.seek(0, os.SEEK_END)
                        report_file_size(f.tell())
                        f.seek(0)
                    shutil.copyfileobj(f, dest)
                if hasattr(dest, 'flush'):
                    dest.flush()
            elif dest:
                if samefile(dest, path):
                    if not self.is_case_sensitive and path != dest:
                        # Ensure that the file has the same case as dest
                        try:
                            os.rename(path, dest)
                        except:
                            pass  # Nothing too catastrophic happened, the cases mismatch, that's all
                else:
                    if use_hardlink:
                        try:
                            hardlink_file(path, dest)
                            return True
                        except:
                            pass
                    with lopen(path, 'rb') as f, lopen(dest, 'wb') as d:
                        shutil.copyfileobj(f, d)
        return True

    def windows_check_if_files_in_use(self, paths):
        '''
        Raises an EACCES IOError if any of the files in the folder of book_id
        are opened in another program on windows.
        '''
        if iswindows:
            for path in paths:
                spath = os.path.join(self.library_path, *path.split('/'))
                wam = None
                if os.path.exists(spath):
                    try:
                        wam = WindowsAtomicFolderMove(spath)
                    finally:
                        if wam is not None:
                            wam.close_handles()

    def add_format(self, book_id, fmt, stream, title, author, path, current_name, mtime=None):
        fmt = ('.' + fmt.lower()) if fmt else ''
        fname = self.construct_file_name(book_id, title, author, len(fmt))
        path = os.path.join(self.library_path, path)
        dest = os.path.join(path, fname + fmt)
        if not os.path.exists(path):
            os.makedirs(path)
        size = 0
        if current_name is not None:
            old_path = os.path.join(path, current_name + fmt)
            if old_path != dest:
                # Ensure that the old format file is not orphaned, this can
                # happen if the algorithm in construct_file_name is changed.
                try:
                    # rename rather than remove, so that if something goes
                    # wrong in the rest of this function, at least the file is
                    # not deleted
                    os.rename(old_path, dest)
                except EnvironmentError as e:
                    if getattr(e, 'errno', None) != errno.ENOENT:
                        # Failing to rename the old format will at worst leave a
                        # harmless orphan, so log and ignore the error
                        import traceback
                        traceback.print_exc()

        if (not getattr(stream, 'name', False) or not samefile(dest, stream.name)):
            with lopen(dest, 'wb') as f:
                shutil.copyfileobj(stream, f)
                size = f.tell()
            if mtime is not None:
                os.utime(dest, (mtime, mtime))
        elif os.path.exists(dest):
            size = os.path.getsize(dest)
            if mtime is not None:
                os.utime(dest, (mtime, mtime))

        return size, fname

    def update_path(self, book_id, title, author, path_field, formats_field):
        path = self.construct_path_name(book_id, title, author)
        current_path = path_field.for_book(book_id, default_value='')
        formats = formats_field.for_book(book_id, default_value=())
        try:
            extlen = max(len(fmt) for fmt in formats) + 1
        except ValueError:
            extlen = 10
        fname = self.construct_file_name(book_id, title, author, extlen)
        # Check if the metadata used to construct paths has changed
        changed = False
        for fmt in formats:
            name = formats_field.format_fname(book_id, fmt)
            if name and name != fname:
                changed = True
                break
        if path == current_path and not changed:
            return
        spath = os.path.join(self.library_path, *current_path.split('/'))
        tpath = os.path.join(self.library_path, *path.split('/'))

        source_ok = current_path and os.path.exists(spath)
        wam = WindowsAtomicFolderMove(spath) if iswindows and source_ok else None
        format_map = {}
        original_format_map = {}
        try:
            if not os.path.exists(tpath):
                os.makedirs(tpath)

            if source_ok:  # Migrate existing files
                dest = os.path.join(tpath, 'cover.jpg')
                self.copy_cover_to(current_path, dest,
                        windows_atomic_move=wam, use_hardlink=True)
                for fmt in formats:
                    dest = os.path.join(tpath, fname+'.'+fmt.lower())
                    format_map[fmt] = dest
                    ofmt_fname = formats_field.format_fname(book_id, fmt)
                    original_format_map[fmt] = os.path.join(spath, ofmt_fname+'.'+fmt.lower())
                    self.copy_format_to(book_id, fmt, ofmt_fname, current_path,
                                        dest, windows_atomic_move=wam, use_hardlink=True)
            # Update db to reflect new file locations
            for fmt in formats:
                formats_field.table.set_fname(book_id, fmt, fname, self)
            path_field.table.set_path(book_id, path, self)

            # Delete not needed files and directories
            if source_ok:
                if os.path.exists(spath):
                    if samefile(spath, tpath):
                        # The format filenames may have changed while the folder
                        # name remains the same
                        for fmt, opath in original_format_map.iteritems():
                            npath = format_map.get(fmt, None)
                            if npath and os.path.abspath(npath.lower()) != os.path.abspath(opath.lower()) and samefile(opath, npath):
                                # opath and npath are different hard links to the same file
                                os.unlink(opath)
                    else:
                        if wam is not None:
                            wam.delete_originals()
                        self.rmtree(spath)
                        parent = os.path.dirname(spath)
                        if len(os.listdir(parent)) == 0:
                            self.rmtree(parent)
        finally:
            if wam is not None:
                wam.close_handles()

        curpath = self.library_path
        c1, c2 = current_path.split('/'), path.split('/')
        if not self.is_case_sensitive and len(c1) == len(c2):
            # On case-insensitive systems, title and author renames that only
            # change case don't cause any changes to the directories in the file
            # system. This can lead to having the directory names not match the
            # title/author, which leads to trouble when libraries are copied to
            # a case-sensitive system. The following code attempts to fix this
            # by checking each segment. If they are different because of case,
            # then rename the segment. Note that the code above correctly
            # handles files in the directories, so no need to do them here.
            for oldseg, newseg in zip(c1, c2):
                if oldseg.lower() == newseg.lower() and oldseg != newseg:
                    try:
                        os.rename(os.path.join(curpath, oldseg),
                                os.path.join(curpath, newseg))
                    except:
                        break  # Fail silently since nothing catastrophic has happened
                curpath = os.path.join(curpath, newseg)

    def write_backup(self, path, raw):
        path = os.path.abspath(os.path.join(self.library_path, path, 'metadata.opf'))
        try:
            with lopen(path, 'wb') as f:
                f.write(raw)
        except EnvironmentError:
            exc_info = sys.exc_info()
            try:
                os.makedirs(os.path.dirname(path))
            except EnvironmentError as err:
                if err.errno == errno.EEXIST:
                    # Parent directory already exists, re-raise original exception
                    raise exc_info[0], exc_info[1], exc_info[2]
                raise
            finally:
                del exc_info
            with lopen(path, 'wb') as f:
                f.write(raw)

    def read_backup(self, path):
        path = os.path.abspath(os.path.join(self.library_path, path, 'metadata.opf'))
        with lopen(path, 'rb') as f:
            return f.read()

    def remove_books(self, path_map, permanent=False):
        self.executemany(
            'DELETE FROM books WHERE id=?', [(x,) for x in path_map])
        paths = {os.path.join(self.library_path, x) for x in path_map.itervalues() if x}
        paths = {x for x in paths if os.path.exists(x) and self.is_deletable(x)}
        if permanent:
            for path in paths:
                self.rmtree(path)
                remove_dir_if_empty(os.path.dirname(path), ignore_metadata_caches=True)
        else:
            delete_service().delete_books(paths, self.library_path)

    def add_custom_data(self, name, val_map, delete_first):
        if delete_first:
            self.execute('DELETE FROM books_plugin_data WHERE name=?', (name, ))
        self.executemany(
            'INSERT OR REPLACE INTO books_plugin_data (book, name, val) VALUES (?, ?, ?)',
            [(book_id, name, json.dumps(val, default=to_json))
                    for book_id, val in val_map.iteritems()])

    def get_custom_book_data(self, name, book_ids, default=None):
        book_ids = frozenset(book_ids)

        def safe_load(val):
            try:
                return json.loads(val, object_hook=from_json)
            except:
                return default

        if len(book_ids) == 1:
            bid = next(iter(book_ids))
            ans = {book_id:safe_load(val) for book_id, val in
                   self.execute('SELECT book, val FROM books_plugin_data WHERE book=? AND name=?', (bid, name))}
            return ans or {bid:default}

        ans = {}
        for book_id, val in self.execute(
            'SELECT book, val FROM books_plugin_data WHERE name=?', (name,)):
            if not book_ids or book_id in book_ids:
                val = safe_load(val)
                ans[book_id] = val
        return ans

    def delete_custom_book_data(self, name, book_ids):
        if book_ids:
            self.executemany('DELETE FROM books_plugin_data WHERE book=? AND name=?',
                                  [(book_id, name) for book_id in book_ids])
        else:
            self.execute('DELETE FROM books_plugin_data WHERE name=?', (name,))

    def get_ids_for_custom_book_data(self, name):
        return frozenset(r[0] for r in self.execute('SELECT book FROM books_plugin_data WHERE name=?', (name,)))

    def conversion_options(self, book_id, fmt):
        for (data,) in self.conn.get('SELECT data FROM conversion_options WHERE book=? AND format=?', (book_id, fmt.upper())):
            if data:
                return safe_pickle.loads(bytes(data))

    def has_conversion_options(self, ids, fmt='PIPE'):
        ids = frozenset(ids)
        with self.conn:
            self.execute('DROP TABLE IF EXISTS conversion_options_temp; CREATE TEMP TABLE conversion_options_temp (id INTEGER PRIMARY KEY);')
            self.executemany('INSERT INTO conversion_options_temp VALUES (?)', [(x,) for x in ids])
            for (book_id,) in self.conn.get(
                'SELECT book FROM conversion_options WHERE format=? AND book IN (SELECT id FROM conversion_options_temp)', (fmt.upper(),)):
                return True
            return False

    def delete_conversion_options(self, book_ids, fmt):
        self.executemany('DELETE FROM conversion_options WHERE book=? AND format=?',
            [(book_id, fmt.upper()) for book_id in book_ids])

    def set_conversion_options(self, options, fmt):
        options = [(book_id, fmt.upper(), buffer(cPickle.dumps(data, -1))) for book_id, data in options.iteritems()]
        self.executemany('INSERT OR REPLACE INTO conversion_options(book,format,data) VALUES (?,?,?)', options)

    def get_top_level_move_items(self, all_paths):
        items = set(os.listdir(self.library_path))
        paths = set(all_paths)
        paths.update({'metadata.db', 'metadata_db_prefs_backup.json'})
        path_map = {x:x for x in paths}
        if not self.is_case_sensitive:
            for x in items:
                path_map[x.lower()] = x
            items = {x.lower() for x in items}
            paths = {x.lower() for x in paths}
        items = items.intersection(paths)
        return items, path_map

    def move_library_to(self, all_paths, newloc, progress=(lambda item_name, item_count, total: None), abort=None):
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs, old_files = set(), set()
        items, path_map = self.get_top_level_move_items(all_paths)
        total = len(items) + 1
        for i, x in enumerate(items):
            if abort is not None and abort.is_set():
                return
            src = os.path.join(self.library_path, x)
            dest = os.path.join(newloc, path_map[x])
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                copytree_using_links(src, dest, dest_is_parent=False)
                old_dirs.add(src)
            else:
                if os.path.exists(dest):
                    os.remove(dest)
                copyfile_using_links(src, dest, dest_is_dir=False)
                old_files.add(src)
            x = path_map[x]
            if not isinstance(x, unicode):
                x = x.decode(filesystem_encoding, 'replace')
            progress(x, i+1, total)

        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        odir = self.library_path
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        for loc in old_dirs:
            try:
                shutil.rmtree(loc)
            except EnvironmentError as e:
                if os.path.exists(loc):
                    prints('Failed to delete:', loc, 'with error:', as_unicode(e))
        for loc in old_files:
            try:
                os.remove(loc)
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    prints('Failed to delete:', loc, 'with error:', as_unicode(e))
        try:
            os.rmdir(odir)
        except EnvironmentError:
            pass
        self.conn  # Connect to the moved metadata.db
        progress(_('Completed'), total, total)

    def restore_book(self, book_id, path, formats):
        self.execute('UPDATE books SET path=? WHERE id=?', (path.replace(os.sep, '/'), book_id))
        vals = [(book_id, fmt, size, name) for fmt, size, name in formats]
        self.executemany('INSERT INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)', vals)

    def backup_database(self, path):
        # We have to open a new connection to self.dbpath, until this issue is fixed:
        # https://github.com/rogerbinns/apsw/issues/199
        dest_db = apsw.Connection(path)
        source = apsw.Connection(self.dbpath)
        with dest_db.backup('main', source, 'main') as b:
            while not b.done:
                b.step(100)
        source.close()
        dest_db.cursor().execute('DELETE FROM metadata_dirtied; VACUUM;')
        dest_db.close()

    # }}}
