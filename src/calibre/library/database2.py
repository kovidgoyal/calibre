from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The database used to store ebook metadata
'''
import os, sys, shutil, cStringIO, glob, time, functools, traceback, re, \
        json, uuid, hashlib, copy
from collections import defaultdict
import threading, random
from itertools import repeat
from math import ceil

from calibre import prints, force_unicode
from calibre.ebooks.metadata import (title_sort, author_to_author_sort,
        string_to_authors, authors_to_string, get_title_sort_pat)
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.library.database import LibraryDatabase
from calibre.library.field_metadata import FieldMetadata, TagsIcons
from calibre.library.schema_upgrades import SchemaUpgrade
from calibre.library.caches import ResultCache
from calibre.library.custom_columns import CustomColumns
from calibre.library.sqlite import connect, IntegrityError
from calibre.library.prefs import DBPrefs
from calibre.ebooks.metadata.book.base import Metadata
from calibre.constants import preferred_encoding, iswindows, filesystem_encoding
from calibre.ptempfile import (PersistentTemporaryFile,
        base_dir, SpooledTemporaryFile)
from calibre.customize.ui import run_plugins_on_import
from calibre import isbytestring
from calibre.utils.filenames import ascii_filename
from calibre.utils.date import utcnow, now as nowf, utcfromtimestamp
from calibre.utils.config import prefs, tweaks, from_json, to_json
from calibre.utils.icu import sort_key, strcmp, lower
from calibre.utils.search_query_parser import saved_searches, set_saved_searches
from calibre.ebooks import BOOK_EXTENSIONS, check_ebook_format
from calibre.utils.magick.draw import save_cover_data_to
from calibre.utils.recycle_bin import delete_file, delete_tree
from calibre.utils.formatter_functions import load_user_template_functions
from calibre.db.errors import NoSuchFormat
from calibre.db.lazy import FormatMetadata, FormatsList
from calibre.utils.localization import (canonicalize_lang,
        calibre_langcode_to_name)

copyfile = os.link if hasattr(os, 'link') else shutil.copyfile
SPOOL_SIZE = 30*1024*1024

class Tag(object):

    def __init__(self, name, id=None, count=0, state=0, avg=0, sort=None,
                 tooltip=None, icon=None, category=None, id_set=None,
                 is_editable = True, is_searchable=True, use_sort_as_name=False):
        self.name = self.original_name = name
        self.id = id
        self.count = count
        self.state = state
        self.is_hierarchical = ''
        self.is_editable = is_editable
        self.is_searchable = is_searchable
        self.id_set = id_set if id_set is not None else set([])
        self.avg_rating = avg/2.0 if avg is not None else 0
        self.sort = sort
        self.use_sort_as_name = use_sort_as_name
        if self.avg_rating > 0:
            if tooltip:
                tooltip = tooltip + ': '
            tooltip = _('%(tt)sAverage rating is %(rating)3.1f')%dict(
                    tt=tooltip, rating=self.avg_rating)
        self.tooltip = tooltip
        self.icon = icon
        self.category = category

    def __unicode__(self):
        return u'%s:%s:%s:%s:%s:%s'%(self.name, self.count, self.id, self.state,
                                  self.category, self.tooltip)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        return str(self)

class LibraryDatabase2(LibraryDatabase, SchemaUpgrade, CustomColumns):
    '''
    An ebook metadata database that stores references to ebook files on disk.
    '''
    PATH_LIMIT = 40 if 'win32' in sys.platform else 100
    WINDOWS_LIBRARY_PATH_LIMIT = 75

    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'

        def fget(self):
            return self.conn.get('pragma user_version;', all=False)

        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))
            self.conn.commit()

        return property(doc=doc, fget=fget, fset=fset)

    @dynamic_property
    def library_id(self):
        doc = ('The UUID for this library. As long as the user only operates'
                ' on libraries with calibre, it will be unique')

        def fget(self):
            if self._library_id_ is None:
                ans = self.conn.get('SELECT uuid FROM library_id', all=False)
                if ans is None:
                    ans = str(uuid.uuid4())
                    self.library_id = ans
                else:
                    self._library_id_ = ans
            return self._library_id_

        def fset(self, val):
            self._library_id_ = unicode(val)
            self.conn.executescript('''
                    DELETE FROM library_id;
                    INSERT INTO library_id (uuid) VALUES ("%s");
                    '''%self._library_id_)
            self.conn.commit()

        return property(doc=doc, fget=fget, fset=fset)

    def connect(self):
        if iswindows and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError(_(
                'Path to library too long. Must be less than'
                ' %d characters.')%(259-4*self.PATH_LIMIT-10))
        exists = os.path.exists(self.dbpath)
        if not exists:
            # Be more strict when creating new libraries as the old calculation
            # allowed for max path lengths of 265 chars.
            if (iswindows and len(self.library_path) >
                    self.WINDOWS_LIBRARY_PATH_LIMIT):
                raise ValueError(_(
                    'Path to library too long. Must be less than'
                    ' %d characters.')%self.WINDOWS_LIBRARY_PATH_LIMIT)

        self.conn = connect(self.dbpath, self.row_factory)
        if exists and self.user_version == 0:
            self.conn.close()
            os.remove(self.dbpath)
            self.conn = connect(self.dbpath, self.row_factory)
        if self.user_version == 0:
            self.initialize_database()
        # remember to add any filter to the connect method in sqlite.py as well
        # so that various code that connects directly will not complain about
        # missing functions
        self.books_list_filter = self.conn.create_dynamic_filter('books_list_filter')
        # Store temporary tables in memory
        self.conn.execute('pragma temp_store=2')
        self.conn.commit()

    @classmethod
    def exists_at(cls, path):
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    def __init__(self, library_path, row_factory=False, default_prefs=None,
            read_only=False, is_second_db=False, progress_callback=None,
            restore_all_prefs=False):
        self.is_second_db = is_second_db
        try:
            if isbytestring(library_path):
                library_path = library_path.decode(filesystem_encoding)
        except:
            traceback.print_exc()
        self.field_metadata = FieldMetadata()
        self.format_filename_cache = defaultdict(dict)
        self._library_id_ = None
        # Create the lock to be used to guard access to the metadata writer
        # queues. This must be an RLock, not a Lock
        self.dirtied_lock = threading.RLock()
        if not os.path.exists(library_path):
            os.makedirs(library_path)
        self.listeners = set([])
        self.library_path = os.path.abspath(library_path)
        self.row_factory = row_factory
        self.dbpath = os.path.join(library_path, 'metadata.db')
        self.dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH',
                self.dbpath)

        if read_only and os.path.exists(self.dbpath):
            # Work on only a copy of metadata.db to ensure that
            # metadata.db is not changed
            pt = PersistentTemporaryFile('_metadata_ro.db')
            pt.close()
            shutil.copyfile(self.dbpath, pt.name)
            self.dbpath = pt.name

        apply_default_prefs = not os.path.exists(self.dbpath)
        self.connect()

        self.is_case_sensitive = (not iswindows and
            not os.path.exists(self.dbpath.replace('metadata.db',
                'MeTAdAtA.dB')))
        SchemaUpgrade.__init__(self)
        # Guarantee that the library_id is set
        self.library_id

        # if we are to copy the prefs and structure from some other DB, then
        # we need to do it before we call initialize_dynamic
        if apply_default_prefs and default_prefs is not None:
            if progress_callback is None:
                progress_callback = lambda x, y: True
            dbprefs = DBPrefs(self)
            progress_callback(None, len(default_prefs))
            for i, key in enumerate(default_prefs):
                # be sure that prefs not to be copied are listed below
                if not restore_all_prefs and key in frozenset(['news_to_be_synced']):
                    continue
                dbprefs[key] = default_prefs[key]
                progress_callback(_('restored preference ') + key, i+1)
            if 'field_metadata' in default_prefs:
                fmvals = [f for f in default_prefs['field_metadata'].values() if f['is_custom']]
                progress_callback(None, len(fmvals))
                for i, f in enumerate(fmvals):
                    progress_callback(_('creating custom column ') + f['label'], i)
                    self.create_custom_column(f['label'], f['name'], f['datatype'],
                            f['is_multiple'] is not None and len(f['is_multiple']) > 0,
                            f['is_editable'], f['display'])
        self.initialize_template_cache()
        self.initialize_dynamic()

    def initialize_template_cache(self):
        self.formatter_template_cache = {}

    def get_property(self, idx, index_is_id=False, loc=-1):
        row = self.data._data[idx] if index_is_id else self.data[idx]
        if row is not None:
            return row[loc]

    def initialize_dynamic(self):
        self.field_metadata = FieldMetadata() #Ensure we start with a clean copy
        self.prefs = DBPrefs(self)
        defs = self.prefs.defaults
        defs['gui_restriction'] = defs['cs_restriction'] = ''
        defs['categories_using_hierarchy'] = []
        defs['column_color_rules'] = []
        defs['grouped_search_make_user_categories'] = []
        defs['similar_authors_search_key'] = 'authors'
        defs['similar_authors_match_kind'] = 'match_any'
        defs['similar_publisher_search_key'] = 'publisher'
        defs['similar_publisher_match_kind'] = 'match_any'
        defs['similar_tags_search_key'] = 'tags'
        defs['similar_tags_match_kind'] = 'match_all'
        defs['similar_series_search_key'] = 'series'
        defs['similar_series_match_kind'] = 'match_any'

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
        if not self.is_second_db:
            set_saved_searches(self, 'saved_searches')

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

        if not self.is_second_db:
            load_user_template_functions(self.prefs.get('user_template_functions', []))

        # Load the format filename cache
        self.refresh_format_cache()

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
        ''')
        self.conn.execute(
            'UPDATE authors SET sort=author_to_author_sort(name) WHERE sort IS NULL')
        self.conn.executescript(u'''
            CREATE TEMP VIEW IF NOT EXISTS tag_browser_news AS SELECT DISTINCT
                id,
                name,
                (SELECT COUNT(books_tags_link.id) FROM books_tags_link WHERE tag=x.id) count,
                (0) as avg_rating,
                name as sort
            FROM tags as x WHERE name!="{0}" AND id IN
                (SELECT DISTINCT tag FROM books_tags_link WHERE book IN
                    (SELECT DISTINCT book FROM books_tags_link WHERE tag IN
                        (SELECT id FROM tags WHERE name="{0}")));
            '''.format(_('News')))

        self.conn.executescript(u'''
            CREATE TEMP VIEW IF NOT EXISTS tag_browser_filtered_news AS SELECT DISTINCT
                id,
                name,
                (SELECT COUNT(books_tags_link.id) FROM books_tags_link WHERE tag=x.id and books_list_filter(book)) count,
                (0) as avg_rating,
                name as sort
            FROM tags as x WHERE name!="{0}" AND id IN
                (SELECT DISTINCT tag FROM books_tags_link WHERE book IN
                    (SELECT DISTINCT book FROM books_tags_link WHERE tag IN
                        (SELECT id FROM tags WHERE name="{0}")));
            '''.format(_('News')))
        self.conn.commit()


        CustomColumns.__init__(self)
        template = '''\
                (SELECT {query} FROM books_{table}_link AS link INNER JOIN
                    {table} ON(link.{link_col}={table}.id) WHERE link.book=books.id)
                    {col}
                '''
        columns = ['id', 'title',
            # col         table     link_col          query
            ('authors', 'authors', 'author', 'sortconcat(link.id, name)'),
             'timestamp',
             '(SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size',
            ('rating', 'ratings', 'rating', 'ratings.rating'),
            ('tags', 'tags', 'tag', 'group_concat(name)'),
             '(SELECT text FROM comments WHERE book=books.id) comments',
            ('series', 'series', 'series', 'name'),
            ('publisher', 'publishers', 'publisher', 'name'),
             'series_index',
             'sort',
             'author_sort',
             '(SELECT group_concat(format) FROM data WHERE data.book=books.id) formats',
             'path',
             'pubdate',
             'uuid',
             'has_cover',
            ('au_map', 'authors', 'author',
                'aum_sortconcat(link.id, authors.name, authors.sort, authors.link)'),
            'last_modified',
            '(SELECT identifiers_concat(type, val) FROM identifiers WHERE identifiers.book=books.id) identifiers',
            ('languages', 'languages', 'lang_code',
                'sortconcat(link.id, languages.lang_code)'),
            ]
        lines = []
        for col in columns:
            line = col
            if isinstance(col, tuple):
                line = template.format(col=col[0], table=col[1],
                        link_col=col[2], query=col[3])
            lines.append(line)

        custom_map = self.custom_columns_in_meta()
        # custom col labels are numbers (the id in the custom_columns table)
        custom_cols = list(sorted(custom_map.keys()))
        lines.extend([custom_map[x] for x in custom_cols])

        self.FIELD_MAP = {'id':0, 'title':1, 'authors':2, 'timestamp':3,
             'size':4, 'rating':5, 'tags':6, 'comments':7, 'series':8,
             'publisher':9, 'series_index':10, 'sort':11, 'author_sort':12,
             'formats':13, 'path':14, 'pubdate':15, 'uuid':16, 'cover':17,
             'au_map':18, 'last_modified':19, 'identifiers':20, 'languages':21}

        for k,v in self.FIELD_MAP.iteritems():
            self.field_metadata.set_field_record_index(k, v, prefer_custom=False)

        base = max(self.FIELD_MAP.values())
        for col in custom_cols:
            self.FIELD_MAP[col] = base = base+1
            self.field_metadata.set_field_record_index(
                                        self.custom_column_num_map[col]['label'],
                                        base,
                                        prefer_custom=True)
            if self.custom_column_num_map[col]['datatype'] == 'series':
                # account for the series index column. Field_metadata knows that
                # the series index is one larger than the series. If you change
                # it here, be sure to change it there as well.
                self.FIELD_MAP[str(col)+'_index'] = base = base+1
                self.field_metadata.set_field_record_index(
                            self.custom_column_num_map[col]['label']+'_index',
                            base,
                            prefer_custom=True)

        self.FIELD_MAP['ondevice'] = base = base+1
        self.field_metadata.set_field_record_index('ondevice', base, prefer_custom=False)
        self.FIELD_MAP['marked'] = base = base+1
        self.field_metadata.set_field_record_index('marked', base, prefer_custom=False)
        self.FIELD_MAP['series_sort'] = base = base+1
        self.field_metadata.set_field_record_index('series_sort', base, prefer_custom=False)

        script = '''
        DROP VIEW IF EXISTS meta2;
        CREATE TEMP VIEW meta2 AS
        SELECT
        {0}
        FROM books;
        '''.format(', \n'.join(lines))
        self.conn.executescript(script)
        self.conn.commit()

        # Reconstruct the user categories, putting them into field_metadata
        # Assumption is that someone else will fix them if they change.
        self.field_metadata.remove_dynamic_categories()
        for user_cat in sorted(self.prefs.get('user_categories', {}).keys(), key=sort_key):
            cat_name = '@' + user_cat # add the '@' to avoid name collision
            self.field_metadata.add_user_category(label=cat_name, name=user_cat)

        # add grouped search term user categories
        muc = self.prefs.get('grouped_search_make_user_categories', [])
        for cat in sorted(self.prefs.get('grouped_search_terms', {}).keys(), key=sort_key):
            if cat in muc:
                # There is a chance that these can be duplicates of an existing
                # user category. Print the exception and continue.
                try:
                    self.field_metadata.add_user_category(label=u'@' + cat, name=cat)
                except:
                    traceback.print_exc()

        if len(saved_searches().names()):
            self.field_metadata.add_search_category(label='search', name=_('Searches'))

        self.field_metadata.add_grouped_search_terms(
                                    self.prefs.get('grouped_search_terms', {}))

        self.book_on_device_func = None
        self.data    = ResultCache(self.FIELD_MAP, self.field_metadata, db_prefs=self.prefs)
        self.search  = self.data.search
        self.search_getting_ids  = self.data.search_getting_ids
        self.refresh = functools.partial(self.data.refresh, self)
        self.sort    = self.data.sort
        self.multisort = self.data.multisort
        self.index   = self.data.index
        self.refresh_ids = functools.partial(self.data.refresh_ids, self)
        self.row     = self.data.row
        self.has_id  = self.data.has_id
        self.count   = self.data.count
        self.set_marked_ids = self.data.set_marked_ids

        for prop in (
                'author_sort', 'authors', 'comment', 'comments',
                'publisher', 'rating', 'series', 'series_index', 'tags',
                'title', 'timestamp', 'uuid', 'pubdate', 'ondevice',
                'metadata_last_modified', 'languages',
                ):
            fm = {'comment':'comments', 'metadata_last_modified':
                    'last_modified'}.get(prop, prop)
            setattr(self, prop, functools.partial(self.get_property,
                    loc=self.FIELD_MAP[fm]))
        setattr(self, 'title_sort', functools.partial(self.get_property,
                loc=self.FIELD_MAP['sort']))

        d = self.conn.get('SELECT book FROM metadata_dirtied', all=True)
        with self.dirtied_lock:
            self.dirtied_sequence = 0
            self.dirtied_cache = {}
            for x in d:
                self.dirtied_cache[x[0]] = self.dirtied_sequence
                self.dirtied_sequence += 1

        self.refresh_ondevice = functools.partial(self.data.refresh_ondevice, self)
        self.refresh()
        self.last_update_check = self.last_modified()

    def break_cycles(self):
        self.data.break_cycles()
        self.data = self.field_metadata = self.prefs = self.listeners = \
            self.refresh_ondevice = None

    def initialize_database(self):
        metadata_sqlite = P('metadata_sqlite.sql', data=True,
                allow_user_override=False).decode('utf-8')
        self.conn.executescript(metadata_sqlite)
        self.conn.commit()
        if self.user_version == 0:
            self.user_version = 1

    def last_modified(self):
        ''' Return last modified time as a UTC datetime object'''
        return utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def refresh_format_cache(self):
        self.format_filename_cache = defaultdict(dict)
        for book_id, fmt, name in self.conn.get(
                'SELECT book,format,name FROM data'):
            self.format_filename_cache[book_id][fmt.upper() if fmt else ''] = name
        self.format_metadata_cache = defaultdict(dict)

    def check_if_modified(self):
        if self.last_modified() > self.last_update_check:
            self.refresh()
            self.refresh_format_cache()
        self.last_update_check = utcnow()

    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        row = self.data._data[index] if index_is_id else self.data[index]
        return row[self.FIELD_MAP['path']].replace('/', os.sep)

    def abspath(self, index, index_is_id=False, create_dirs=True):
        'Return the absolute path to the directory containing this books files as a unicode string.'
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if create_dirs and not os.path.exists(path):
            os.makedirs(path)
        return path

    def construct_path_name(self, id):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0].replace('|', ',')
                    )[:self.PATH_LIMIT].decode('ascii', 'replace')
        title  = ascii_filename(self.title(id, index_is_id=True)
                    )[:self.PATH_LIMIT].decode('ascii', 'replace')
        while author[-1] in (' ', '.'):
            author = author[:-1]
        if not author:
            author = ascii_filename(_('Unknown')).decode(
                    'ascii', 'replace')
        path = author + '/' + title + ' (%d)'%id
        return path

    def construct_file_name(self, id):
        '''
        Construct the file name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0].replace('|', ',')
                    )[:self.PATH_LIMIT].decode('ascii', 'replace')
        title  = ascii_filename(self.title(id, index_is_id=True)
                    )[:self.PATH_LIMIT].decode('ascii', 'replace')
        name   = title + ' - ' + author
        while name.endswith('.'):
            name = name[:-1]
        return name

    def rmtree(self, path, permanent=False):
        if not self.normpath(self.library_path).startswith(self.normpath(path)):
            delete_tree(path, permanent=permanent)

    def normpath(self, path):
        path = os.path.abspath(os.path.realpath(path))
        if not self.is_case_sensitive:
            path = path.lower()
        return path

    def set_path(self, index, index_is_id=False):
        '''
        Set the path to the directory containing this books files based on its
        current title and author. If there was a previous directory, its contents
        are copied and it is deleted.
        '''
        id = index if  index_is_id else self.id(index)
        path = self.construct_path_name(id)
        current_path = self.path(id, index_is_id=True).replace(os.sep, '/')
        formats = self.formats(id, index_is_id=True)
        formats = formats.split(',') if formats else []
        # Check if the metadata used to construct paths has changed
        fname = self.construct_file_name(id)
        changed = False
        for format in formats:
            name = self.format_filename_cache[id].get(format.upper(), None)
            if name and name != fname:
                changed = True
                break
        if path == current_path and not changed:
            return

        tpath = os.path.join(self.library_path, *path.split('/'))
        if not os.path.exists(tpath):
            os.makedirs(tpath)
        spath = os.path.join(self.library_path, *current_path.split('/'))

        if current_path and os.path.exists(spath): # Migrate existing files
            cdata = self.cover(id, index_is_id=True)
            if cdata is not None:
                with lopen(os.path.join(tpath, 'cover.jpg'), 'wb') as f:
                    f.write(cdata)
            for format in formats:
                with SpooledTemporaryFile(SPOOL_SIZE) as stream:
                    try:
                        self.copy_format_to(id, format, stream, index_is_id=True)
                        stream.seek(0)
                    except NoSuchFormat:
                        continue
                    self.add_format(id, format, stream, index_is_id=True,
                        path=tpath, notify=False)
        self.conn.execute('UPDATE books SET path=? WHERE id=?', (path, id))
        self.dirtied([id], commit=False)
        self.conn.commit()
        self.data.set(id, self.FIELD_MAP['path'], path, row_is_id=True)
        # Delete not needed directories
        if current_path and os.path.exists(spath):
            if self.normpath(spath) != self.normpath(tpath):
                self.rmtree(spath, permanent=True)
                parent = os.path.dirname(spath)
                if len(os.listdir(parent)) == 0:
                    self.rmtree(parent, permanent=True)

        curpath = self.library_path
        c1, c2 = current_path.split('/'), path.split('/')
        if not self.is_case_sensitive and len(c1) == len(c2):
            # On case-insensitive systems, title and author renames that only
            # change case don't cause any changes to the directories in the file
            # system. This can lead to having the directory names not match the
            # title/author, which leads to trouble when libraries are copied to
            # a case-sensitive system. The following code attempts to fix this
            # by checking each segment. If they are different because of case,
            # then rename the segment to some temp file name, then rename it
            # back to the correct name. Note that the code above correctly
            # handles files in the directories, so no need to do them here.
            for oldseg, newseg in zip(c1, c2):
                if oldseg.lower() == newseg.lower() and oldseg != newseg:
                    try:
                        os.rename(os.path.join(curpath, oldseg),
                                os.path.join(curpath, newseg))
                    except:
                        break # Fail silently since nothing catastrophic has happened
                curpath = os.path.join(curpath, newseg)

    def add_listener(self, listener):
        '''
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        '''
        self.listeners.add(listener)

    def notify(self, event, ids=[]):
        'Notify all listeners'
        for listener in self.listeners:
            try:
                listener(event, ids)
            except:
                traceback.print_exc()
                continue

    def cover(self, index, index_is_id=False, as_file=False, as_image=False,
            as_path=False):
        '''
        Return the cover image as a bytestring (in JPEG format) or None.

        WARNING: Using as_path will copy the cover to a temp file and return
        the path to the temp file. You should delete the temp file when you are
        done with it.

        :param as_file: If True return the image as an open file object (a SpooledTemporaryFile)
        :param as_image: If True return the image as a QImage object
        '''
        id = index if index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.access(path, os.R_OK):
            try:
                f = lopen(path, 'rb')
            except (IOError, OSError):
                time.sleep(0.2)
                f = lopen(path, 'rb')
            with f:
                if as_path:
                    pt = PersistentTemporaryFile('_dbcover.jpg')
                    with pt:
                        shutil.copyfileobj(f, pt)
                    return pt.name
                if as_file:
                    ret = SpooledTemporaryFile(SPOOL_SIZE)
                    shutil.copyfileobj(f, ret)
                    ret.seek(0)
                else:
                    ret = f.read()
                    if as_image:
                        from PyQt4.Qt import QImage
                        i = QImage()
                        i.loadFromData(ret)
                        ret = i
            return ret

    def cover_last_modified(self, index, index_is_id=False):
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        try:
            return utcfromtimestamp(os.stat(path).st_mtime)
        except:
            # Cover doesn't exist
            pass
        return self.last_modified()

    ### The field-style interface. These use field keys.

    def get_field(self, idx, key, default=None, index_is_id=False):
        mi = self.get_metadata(idx, index_is_id=index_is_id,
                               get_cover=key == 'cover')
        return mi.get(key, default)

    def standard_field_keys(self):
        return self.field_metadata.standard_field_keys()

    def custom_field_keys(self, include_composites=True):
        return self.field_metadata.custom_field_keys(include_composites)

    def all_field_keys(self):
        return self.field_metadata.all_field_keys()

    def sortable_field_keys(self):
        return self.field_metadata.sortable_field_keys()

    def searchable_fields(self):
        return self.field_metadata.searchable_field_keys()

    def search_term_to_field_key(self, term):
        return self.field_metadata.search_term_to_key(term)

    def custom_field_metadata(self, include_composites=True):
        return self.field_metadata.custom_field_metadata(include_composites)

    def all_metadata(self):
        return self.field_metadata.all_metadata()

    def metadata_for_field(self, key):
        return self.field_metadata[key]

    def clear_dirtied(self, book_id, sequence):
        '''
        Clear the dirtied indicator for the books. This is used when fetching
        metadata, creating an OPF, and writing a file are separated into steps.
        The last step is clearing the indicator
        '''
        with self.dirtied_lock:
            dc_sequence = self.dirtied_cache.get(book_id, None)
            # print 'clear_dirty: check book', book_id, dc_sequence
            if dc_sequence is None or sequence is None or dc_sequence == sequence:
                # print 'needs to be cleaned'
                self.conn.execute('DELETE FROM metadata_dirtied WHERE book=?',
                        (book_id,))
                self.conn.commit()
                try:
                    del self.dirtied_cache[book_id]
                except:
                    pass
            elif dc_sequence is not None:
                # print 'book needs to be done again'
                pass

    def dump_metadata(self, book_ids=None, remove_from_dirtied=True,
            commit=True, callback=None):
        '''
        Write metadata for each record to an individual OPF file. If callback
        is not None, it is called once at the start with the number of book_ids
        being processed. And once for every book_id, with arguments (book_id,
        mi, ok).
        '''
        if book_ids is None:
            book_ids = [x[0] for x in self.conn.get(
                'SELECT book FROM metadata_dirtied', all=True)]

        if callback is not None:
            book_ids = tuple(book_ids)
            callback(len(book_ids), True, False)

        for book_id in book_ids:
            if not self.data.has_id(book_id):
                if callback is not None:
                    callback(book_id, None, False)
                continue
            path, mi, sequence = self.get_metadata_for_dump(book_id)
            if path is None:
                if callback is not None:
                    callback(book_id, mi, False)
                continue
            try:
                raw = metadata_to_opf(mi)
                with lopen(path, 'wb') as f:
                    f.write(raw)
                if remove_from_dirtied:
                    self.clear_dirtied(book_id, sequence)
            except:
                pass
            if callback is not None:
                callback(book_id, mi, True)
        if commit:
            self.conn.commit()

    def update_last_modified(self, book_ids, commit=False, now=None):
        if now is None:
            now = nowf()
        if book_ids:
            self.conn.executemany(
                'UPDATE books SET last_modified=? WHERE id=?',
                [(now, book) for book in book_ids])
            for book_id in book_ids:
                self.data.set(book_id, self.FIELD_MAP['last_modified'], now, row_is_id=True)
            if commit:
                self.conn.commit()

    def dirtied(self, book_ids, commit=True):
        self.update_last_modified(book_ids)
        for book in book_ids:
            with self.dirtied_lock:
                # print 'dirtied: check id', book
                if book in self.dirtied_cache:
                    self.dirtied_cache[book] = self.dirtied_sequence
                    self.dirtied_sequence += 1
                    continue
                # print 'book not already dirty'

                self.conn.execute(
                    'INSERT OR IGNORE INTO metadata_dirtied (book) VALUES (?)',
                    (book,))
                self.dirtied_cache[book] = self.dirtied_sequence
                self.dirtied_sequence += 1

        # If the commit doesn't happen, then the DB table will be wrong. This
        # could lead to a problem because on restart, we won't put the book back
        # into the dirtied_cache. We deal with this by writing the dirtied_cache
        # back to the table on GUI exit. Not perfect, but probably OK
        if book_ids and commit:
            self.conn.commit()

    def get_a_dirtied_book(self):
        with self.dirtied_lock:
            l = len(self.dirtied_cache)
            if l > 0:
                # The random stuff is here to prevent a single book from
                # blocking progress if its metadata cannot be written for some
                # reason.
                id_ = self.dirtied_cache.keys()[random.randint(0, l-1)]
                sequence = self.dirtied_cache[id_]
                return (id_, sequence)
            return (None, None)

    def dirty_queue_length(self):
        return len(self.dirtied_cache)

    def commit_dirty_cache(self):
        '''
        Set the dirty indication for every book in the cache. The vast majority
        of the time, the indication will already be set. However, sometimes
        exceptions may have prevented a commit, which may remove some dirty
        indications from the DB. This call will put them back. Note that there
        is no problem with setting a dirty indication for a book that isn't in
        fact dirty. Just wastes a few cycles.
        '''
        with self.dirtied_lock:
            book_ids = list(self.dirtied_cache.keys())
            self.dirtied_cache = {}
            self.dirtied(book_ids)

    def get_metadata_for_dump(self, idx):
        path, mi = (None, None)
        # get the current sequence number for this book to pass back to the
        # backup thread. This will avoid double calls in the case where the
        # thread has not done the work between the put and the get_metadata
        with self.dirtied_lock:
            sequence = self.dirtied_cache.get(idx, None)
        # print 'get_md_for_dump', idx, sequence
        try:
            # While a book is being created, the path is empty. Don't bother to
            # try to write the opf, because it will go to the wrong folder.
            if self.path(idx, index_is_id=True):
                path = os.path.join(self.abspath(idx, index_is_id=True), 'metadata.opf')
                mi = self.get_metadata(idx, index_is_id=True)
                # Always set cover to cover.jpg. Even if cover doesn't exist,
                # no harm done. This way no need to call dirtied when
                # cover is set/removed
                mi.cover = 'cover.jpg'
        except:
            # This almost certainly means that the book has been deleted while
            # the backup operation sat in the queue.
            pass
        return (path, mi, sequence)

    def get_metadata(self, idx, index_is_id=False, get_cover=False,
                     get_user_categories=True, cover_as_data=False):
        '''
        Convenience method to return metadata as a :class:`Metadata` object.
        Note that the list of formats is not verified.
        '''
        idx = idx if index_is_id else self.id(idx)
        try:
            row = self.data._data[idx]
        except:
            row = None

        if row is None:
            raise ValueError('No book with id: %d'%idx)

        fm = self.FIELD_MAP
        mi = Metadata(None, template_cache=self.formatter_template_cache)

        aut_list = row[fm['au_map']]
        if aut_list:
            aut_list = [p.split(':::') for p in aut_list.split(':#:') if p]
        else:
            aut_list = []
        aum = []
        aus = {}
        aul = {}
        try:
            for (author, author_sort, link) in aut_list:
                aut = author.replace('|', ',')
                aum.append(aut)
                aus[aut] = author_sort.replace('|', ',')
                aul[aut] = link
        except ValueError:
            # Author has either ::: or :#: in it
            for x in row[fm['authors']].split(','):
                aum.append(x.replace('|', ','))
                aul[aum[-1]] = ''
                aus[aum[-1]] = aum[-1]
        mi.title       = row[fm['title']]
        mi.authors     = aum
        mi.author_sort = row[fm['author_sort']]
        mi.author_sort_map = aus
        mi.author_link_map = aul
        mi.comments    = row[fm['comments']]
        mi.publisher   = row[fm['publisher']]
        mi.timestamp   = row[fm['timestamp']]
        mi.pubdate     = row[fm['pubdate']]
        mi.uuid        = row[fm['uuid']]
        mi.title_sort  = row[fm['sort']]
        mi.book_size   = row[fm['size']]
        mi.ondevice_col= row[fm['ondevice']]
        mi.last_modified = row[fm['last_modified']]
        formats = row[fm['formats']]
        mi.format_metadata = {}
        if not formats:
            good_formats = None
        else:
            formats = sorted(formats.split(','))
            mi.format_metadata = FormatMetadata(self, idx, formats)
            good_formats = FormatsList(formats, mi.format_metadata)
        mi.formats = good_formats
        tags = row[fm['tags']]
        if tags:
            mi.tags = [i.strip() for i in tags.split(',')]
        languages = row[fm['languages']]
        if languages:
            mi.languages = [i.strip() for i in languages.split(',')]
        mi.series = row[fm['series']]
        if mi.series:
            mi.series_index = row[fm['series_index']]
        mi.rating = row[fm['rating']]
        mi.set_identifiers(self.get_identifiers(idx, index_is_id=True))
        mi.application_id = idx
        mi.id = idx

        mi.set_all_user_metadata(self.field_metadata.custom_field_metadata())
        for key, meta in self.field_metadata.custom_iteritems():
            if meta['datatype'] == 'composite':
                mi.set(key, val=row[meta['rec_index']])
            else:
                val, extra = self.get_custom_and_extra(idx, label=meta['label'],
                                                       index_is_id=True)
                mi.set(key, val=val, extra=extra)

        user_cats = self.prefs['user_categories']
        user_cat_vals = {}
        if get_user_categories:
            for ucat in user_cats:
                res = []
                for name,cat,ign in user_cats[ucat]:
                    v = mi.get(cat, None)
                    if isinstance(v, list):
                        if name in v:
                            res.append([name,cat])
                    elif name == v:
                        res.append([name,cat])
                user_cat_vals[ucat] = res
        mi.user_categories = user_cat_vals

        if get_cover:
            if cover_as_data:
                cdata = self.cover(idx, index_is_id=True)
                if cdata:
                    mi.cover_data = ('jpeg', cdata)
            else:
                mi.cover = self.cover(idx, index_is_id=True, as_path=True)
        mi.has_cover = _('Yes') if self.has_cover(idx) else ''
        return mi

    def has_book(self, mi):
        title = mi.title
        if title:
            if not isinstance(title, unicode):
                title = title.decode(preferred_encoding, 'replace')
            return bool(self.conn.get('SELECT id FROM books where title=?', (title,), all=False))
        return False

    def has_id(self, id_):
        return self.data._data[id_] is not None

    def books_with_same_title(self, mi, all_matches=True):
        title = mi.title
        ans = set()
        if title:
            title = lower(force_unicode(title))
            for book_id in self.all_ids():
                x = self.title(book_id, index_is_id=True)
                if lower(x) == title:
                    ans.add(book_id)
                    if not all_matches:
                        break
        return ans

    def find_identical_books(self, mi):
        fuzzy_title_patterns = [(re.compile(pat, re.IGNORECASE) if
            isinstance(pat, basestring) else pat, repl) for pat, repl in
                [
                    (r'[\[\](){}<>\'";,:#]', ''),
                    (get_title_sort_pat(), ''),
                    (r'[-._]', ' '),
                    (r'\s+', ' ')
                ]
        ]

        def fuzzy_title(title):
            title = title.strip().lower()
            for pat, repl in fuzzy_title_patterns:
                title = pat.sub(repl, title)
            return title

        identical_book_ids = set([])
        if mi.authors:
            try:
                query = u' and '.join([u'author:"=%s"'%(a.replace('"', '')) for a in
                    mi.authors])
            except ValueError:
                return identical_book_ids
            try:
                book_ids = self.data.parse(query)
            except:
                traceback.print_exc()
                return identical_book_ids
            for book_id in book_ids:
                fbook_title = self.title(book_id, index_is_id=True)
                fbook_title = fuzzy_title(fbook_title)
                mbook_title = fuzzy_title(mi.title)
                if fbook_title == mbook_title:
                    identical_book_ids.add(book_id)
        return identical_book_ids

    def remove_cover(self, id, notify=True, commit=True):
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.path.exists(path):
            try:
                os.remove(path)
            except (IOError, OSError):
                time.sleep(0.2)
                os.remove(path)
        self.conn.execute('UPDATE books SET has_cover=0 WHERE id=?', (id,))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['cover'], False, row_is_id=True)
        if notify:
            self.notify('cover', [id])

    def set_cover(self, id, data, notify=True, commit=True):
        '''
        Set the cover for this book.

        `data`: Can be either a QImage, QPixmap, file object or bytestring
        '''
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            data.save(path)
        else:
            if callable(getattr(data, 'read', None)):
                data = data.read()
            try:
                save_cover_data_to(data, path)
            except (IOError, OSError):
                time.sleep(0.2)
                save_cover_data_to(data, path)
        now = nowf()
        self.conn.execute(
            'UPDATE books SET has_cover=1,last_modified=? WHERE id=?',
              (now, id))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['cover'], True, row_is_id=True)
        self.data.set(id, self.FIELD_MAP['last_modified'], now, row_is_id=True)
        if notify:
            self.notify('cover', [id])

    def has_cover(self, id):
        return self.data.get(id, self.FIELD_MAP['cover'], row_is_id=True)

    def set_has_cover(self, id, val):
        dval = 1 if val else 0
        now = nowf()
        self.conn.execute(
                'UPDATE books SET has_cover=?,last_modified=? WHERE id=?',
                (dval, now, id))
        self.data.set(id, self.FIELD_MAP['cover'], val, row_is_id=True)
        self.data.set(id, self.FIELD_MAP['last_modified'], now, row_is_id=True)

    def book_on_device(self, id):
        if callable(self.book_on_device_func):
            return self.book_on_device_func(id)
        return None

    def book_on_device_string(self, id):
        loc = []
        count = 0
        on = self.book_on_device(id)
        if on is not None:
            m, a, b, count = on[:4]
            if m is not None:
                loc.append(_('Main'))
            if a is not None:
                loc.append(_('Card A'))
            if b is not None:
                loc.append(_('Card B'))
        return ', '.join(loc) + ((' (%s books)'%count) if count > 1 else '')

    def set_book_on_device_func(self, func):
        self.book_on_device_func = func

    def all_formats(self):
        formats = self.conn.get('SELECT DISTINCT format from data')
        if not formats:
            return set([])
        return set([f[0] for f in formats])

    def format_files(self, index, index_is_id=False):
        id = index if index_is_id else self.id(index)
        return [(v, k) for k, v in self.format_filename_cache[id].iteritems()]

    def formats(self, index, index_is_id=False, verify_formats=True):
        ''' Return available formats as a comma separated list or None if there are no available formats '''
        id_ = index if index_is_id else self.id(index)
        formats = self.data.get(id_, self.FIELD_MAP['formats'], row_is_id=True)
        if not formats:
            return None
        if not verify_formats:
            return formats
        formats = formats.split(',')
        ans = []
        for fmt in formats:
            if self.format_abspath(id_, fmt, index_is_id=True) is not None:
                ans.append(fmt)
        if not ans:
            return None
        return ','.join(ans)

    def has_format(self, index, format, index_is_id=False):
        return self.format_abspath(index, format, index_is_id) is not None

    def format_last_modified(self, id_, fmt):
        m = self.format_metadata(id_, fmt)
        if m:
            return m['mtime']

    def format_metadata(self, id_, fmt, allow_cache=True, update_db=False,
            commit=False):
        if not fmt:
            return {}
        fmt = fmt.upper()
        if allow_cache:
            x = self.format_metadata_cache[id_].get(fmt, None)
            if x is not None:
                return x
        path = self.format_abspath(id_, fmt, index_is_id=True)
        ans = {}
        if path is not None:
            stat = os.stat(path)
            ans['size'] = stat.st_size
            ans['mtime'] = utcfromtimestamp(stat.st_mtime)
            self.format_metadata_cache[id_][fmt] = ans
            if update_db:
                self.conn.execute(
                    'UPDATE data SET uncompressed_size=? WHERE format=? AND'
                    ' book=?', (stat.st_size, fmt, id_))
                if commit:
                    self.conn.commit()
        return ans

    def format_hash(self, id_, fmt):
        path = self.format_abspath(id_, fmt, index_is_id=True)
        if path is None:
            raise NoSuchFormat('Record %d has no fmt: %s'%(id_, fmt))
        sha = hashlib.sha256()
        with lopen(path, 'rb') as f:
            while True:
                raw = f.read(SPOOL_SIZE)
                sha.update(raw)
                if len(raw) < SPOOL_SIZE:
                    break
        return sha.hexdigest()

    def format_path(self, index, fmt, index_is_id=False):
        '''
        This method is intended to be used only in those rare situations, like
        Drag'n Drop, when you absolutely need the path to the original file.
        Otherwise, use format(..., as_path=True).

        Note that a networked backend will always return None.
        '''
        path = self.format_abspath(index, fmt, index_is_id=index_is_id)
        if path is None:
            id_ = index if index_is_id else self.id(index)
            raise NoSuchFormat('Record %d has no format: %s'%(id_, fmt))
        return path

    def format_abspath(self, index, format, index_is_id=False):
        '''
        Return absolute path to the ebook file of format `format`

        WARNING: This method will return a dummy path for a network backend DB,
        so do not rely on it, use format(..., as_path=True) instead.

        Currently used only in calibredb list, the viewer and the catalogs (via
        get_data_as_dict()).

        Apart from the viewer, I don't believe any of the others do any file
        I/O with the results of this call.
        '''
        id = index if index_is_id else self.id(index)
        try:
            name = self.format_filename_cache[id][format.upper()]
        except:
            return None
        if name:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
            format = ('.' + format.lower()) if format else ''
            fmt_path = os.path.join(path, name+format)
            if os.path.exists(fmt_path):
                return fmt_path
            try:
                candidates = glob.glob(os.path.join(path, '*'+format))
            except: # If path contains strange characters this throws an exc
                candidates = []
            if format and candidates and os.path.exists(candidates[0]):
                try:
                    shutil.copyfile(candidates[0], fmt_path)
                except:
                    # This can happen if candidates[0] or fmt_path is too long,
                    # which can happen if the user copied the library from a
                    # non windows machine to a windows machine.
                    return None
                return fmt_path

    def copy_format_to(self, index, fmt, dest, index_is_id=False):
        '''
        Copy the format ``fmt`` to the file like object ``dest``. If the
        specified format does not exist, raises :class:`NoSuchFormat` error.
        '''
        path = self.format_abspath(index, fmt, index_is_id=index_is_id)
        if path is None:
            id_ = index if index_is_id else self.id(index)
            raise NoSuchFormat('Record %d has no %s file'%(id_, fmt))
        with lopen(path, 'rb') as f:
            shutil.copyfileobj(f, dest)
        if hasattr(dest, 'flush'):
            dest.flush()

    def format(self, index, format, index_is_id=False, as_file=False,
            mode='r+b', as_path=False, preserve_filename=False):
        '''
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file.

        :param as_file: If True the ebook format is returned as a file object. Note
                        that the file object is a SpooledTemporaryFile, so if what you want to
                        do is copy the format to another file, use :method:`copy_format_to`
                        instead for performance.
        :param as_path: Copies the format file to a temp file and returns the
                        path to the temp file
        :param preserve_filename: If True and returning a path the filename is
                                  the same as that used in the library. Note that using
                                  this means that repeated calls yield the same
                                  temp file (which is re-created each time)
        :param mode: This is ignored (present for legacy compatibility)
        '''
        path = self.format_abspath(index, format, index_is_id=index_is_id)
        if path is not None:
            with lopen(path, mode) as f:
                if as_path:
                    if preserve_filename:
                        bd = base_dir()
                        d = os.path.join(bd, 'format_abspath')
                        try:
                            os.makedirs(d)
                        except:
                            pass
                        fname = os.path.basename(path)
                        ret = os.path.join(d, fname)
                        with lopen(ret, 'wb') as f2:
                            shutil.copyfileobj(f, f2)
                    else:
                        with PersistentTemporaryFile('.'+format.lower()) as pt:
                            shutil.copyfileobj(f, pt)
                            ret = pt.name
                elif as_file:
                    ret = SpooledTemporaryFile(SPOOL_SIZE)
                    shutil.copyfileobj(f, ret)
                    ret.seek(0)
                    # Various bits of code try to use the name as the default
                    # title when reading metadata, so set it
                    ret.name = f.name
                else:
                    ret = f.read()
            return ret

    def add_format_with_hooks(self, index, format, fpath, index_is_id=False,
                              path=None, notify=True):
        npath = self.run_import_plugins(fpath, format)
        format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
        stream = lopen(npath, 'rb')
        format = check_ebook_format(stream, format)
        return self.add_format(index, format, stream,
                               index_is_id=index_is_id, path=path, notify=notify)

    def add_format(self, index, format, stream, index_is_id=False, path=None,
            notify=True, replace=True):
        id = index if index_is_id else self.id(index)
        if not format: format = ''
        self.format_metadata_cache[id].pop(format.upper(), None)
        name = self.format_filename_cache[id].get(format.upper(), None)
        if path is None:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        if name and not replace:
            return False
        name = self.construct_file_name(id)
        ext = ('.' + format.lower()) if format else ''
        dest = os.path.join(path, name+ext)
        pdir = os.path.dirname(dest)
        if not os.path.exists(pdir):
            os.makedirs(pdir)
        if not getattr(stream, 'name', False) or \
                os.path.abspath(dest) != os.path.abspath(stream.name):
            with lopen(dest, 'wb') as f:
                shutil.copyfileobj(stream, f)
        stream.seek(0, 2)
        size=stream.tell()
        self.conn.execute('INSERT OR REPLACE INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                          (id, format.upper(), size, name))
        self.conn.commit()
        self.format_filename_cache[id][format.upper()] = name
        self.refresh_ids([id])
        if notify:
            self.notify('metadata', [id])
        return True

    def save_original_format(self, book_id, fmt, notify=True):
        fmt = fmt.upper()
        if 'ORIGINAL' in fmt:
            raise ValueError('Cannot save original of an original fmt')
        opath = self.format_abspath(book_id, fmt, index_is_id=True)
        if opath is None:
            return False
        nfmt = 'ORIGINAL_'+fmt
        with lopen(opath, 'rb') as f:
            return self.add_format(book_id, nfmt, f, index_is_id=True, notify=notify)

    def original_fmt(self, book_id, fmt):
        fmt = fmt
        nfmt = ('ORIGINAL_%s'%fmt).upper()
        opath = self.format_abspath(book_id, nfmt, index_is_id=True)
        return fmt if opath is None else nfmt

    def delete_book(self, id, notify=True, commit=True, permanent=False,
            do_clean=True):
        '''
        Removes book from the result cache and the underlying database.
        If you set commit to False, you must call clean() manually afterwards
        '''
        try:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        except:
            path = None
        if path and os.path.exists(path):
            self.rmtree(path, permanent=permanent)
            parent = os.path.dirname(path)
            if len(os.listdir(parent)) == 0:
                self.rmtree(parent, permanent=permanent)
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        if commit:
            self.conn.commit()
            if do_clean:
                self.clean()
        self.data.books_deleted([id])
        if notify:
            self.notify('delete', [id])

    def remove_format(self, index, format, index_is_id=False, notify=True,
                      commit=True, db_only=False):
        id = index if index_is_id else self.id(index)
        if not format: format = ''
        self.format_metadata_cache[id].pop(format.upper(), None)
        name = self.format_filename_cache[id].get(format.upper(), None)
        if name:
            if not db_only:
                try:
                    path = self.format_abspath(id, format, index_is_id=True)
                    if path:
                        delete_file(path)
                except:
                    traceback.print_exc()
            self.format_filename_cache[id].pop(format.upper(), None)
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format.upper()))
            if commit:
                self.conn.commit()
            self.refresh_ids([id])
            if notify:
                self.notify('metadata', [id])

    def clean_standard_field(self, field, commit=False):
        # Don't bother with validity checking. Let the exception fly out so
        # we can see what happened
        def doit(table, ltable_col):
            st = ('DELETE FROM books_%s_link WHERE (SELECT COUNT(id) '
                    'FROM books WHERE id=book) < 1;')%table
            self.conn.execute(st)
            st = ('DELETE FROM %(table)s WHERE (SELECT COUNT(id) '
                    'FROM books_%(table)s_link WHERE '
                    '%(ltable_col)s=%(table)s.id) < 1;') % dict(
                            table=table, ltable_col=ltable_col)
            self.conn.execute(st)

        fm = self.field_metadata[field]
        doit(fm['table'], fm['link_column'])
        if commit:
            self.conn.commit()

    def clean(self):
        '''
        Remove orphaned entries.
        '''
        def doit(ltable, table, ltable_col):
            st = ('DELETE FROM books_%s_link WHERE (SELECT COUNT(id) '
                    'FROM books WHERE id=book) < 1;')%ltable
            self.conn.execute(st)
            st = ('DELETE FROM %(table)s WHERE (SELECT COUNT(id) '
                    'FROM books_%(ltable)s_link WHERE '
                    '%(ltable_col)s=%(table)s.id) < 1;') % dict(
                            ltable=ltable, table=table, ltable_col=ltable_col)
            self.conn.execute(st)

        for ltable, table, ltable_col in [
                ('authors', 'authors', 'author'),
                ('publishers', 'publishers', 'publisher'),
                ('tags', 'tags', 'tag'),
                ('series', 'series', 'series'),
                ('languages', 'languages', 'lang_code'),
                ]:
            doit(ltable, table, ltable_col)

        for id_, tag in self.conn.get('SELECT id, name FROM tags', all=True):
            if not tag.strip():
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=?',
                        (id_,))
                self.conn.execute('DELETE FROM tags WHERE id=?', (id_,))
        self.clean_custom()
        self.conn.commit()

    def get_books_for_category(self, category, id_):
        ans = set([])

        if category not in self.field_metadata:
            return ans

        field = self.field_metadata[category]
        if field['datatype'] == 'composite':
            dex = field['rec_index']
            for book in self.data.iterall():
                if field['is_multiple']:
                    vals = [v.strip() for v in
                            book[dex].split(field['is_multiple']['cache_to_list'])
                            if v.strip()]
                    if id_ in vals:
                        ans.add(book[0])
                elif book[dex] == id_:
                    ans.add(book[0])
            return ans

        ans = self.conn.get(
                'SELECT book FROM books_{tn}_link WHERE {col}=?'.format(
                    tn=field['table'], col=field['link_column']), (id_,))
        return set(x[0] for x in ans)

########## data structures for get_categories

    CATEGORY_SORTS = ('name', 'popularity', 'rating')
    MATCH_TYPE = ('any', 'all')

    class TCat_Tag(object):

        def __init__(self, name, sort):
            self.n = name
            self.s = sort
            self.c  = 0
            self.id_set = set()
            self.rt = 0
            self.rc = 0
            self.id = None

        def set_all(self, c, rt, rc, id):
            self.c  = c
            self.rt = rt
            self.rc = rc
            self.id = id

        def __str__(self):
            return unicode(self)

        def __unicode__(self):
            return 'n=%s s=%s c=%d rt=%d rc=%d id=%s'%\
                            (self.n, self.s, self.c, self.rt, self.rc, self.id)

    def clean_user_categories(self):
        user_cats = self.prefs.get('user_categories', {})
        new_cats = {}
        for k in user_cats:
            comps = [c.strip() for c in k.split('.') if c.strip()]
            if len(comps) == 0:
                i = 1
                while True:
                    if unicode(i) not in user_cats:
                        new_cats[unicode(i)] = user_cats[k]
                        break
                    i += 1
            else:
                new_cats['.'.join(comps)] = user_cats[k]
        try:
            if new_cats != user_cats:
                self.prefs.set('user_categories', new_cats)
        except:
            pass
        return new_cats

    def get_categories(self, sort='name', ids=None, icon_map=None):
        #start = last = time.clock()
        if icon_map is not None and type(icon_map) != TagsIcons:
            raise TypeError('icon_map passed to get_categories must be of type TagIcons')
        if sort not in self.CATEGORY_SORTS:
            raise ValueError('sort ' + sort + ' not a valid value')

        self.books_list_filter.change([] if not ids else ids)
        id_filter = None if ids is None else frozenset(ids)

        tb_cats = self.field_metadata
        tcategories = {}
        tids = {}
        md = []

        # First, build the maps. We need a category->items map and an
        # item -> (item_id, sort_val) map to use in the books loop
        for category in tb_cats.iterkeys():
            cat = tb_cats[category]
            if not cat['is_category'] or cat['kind'] in ['user', 'search'] \
                    or category in ['news', 'formats'] or cat.get('is_csp',
                            False):
                continue
            # Get the ids for the item values
            if not cat['is_custom']:
                funcs = {
                        'authors'  : self.get_authors_with_ids,
                        'series'   : self.get_series_with_ids,
                        'publisher': self.get_publishers_with_ids,
                        'tags'     : self.get_tags_with_ids,
                        'languages': self.get_languages_with_ids,
                        'rating'   : self.get_ratings_with_ids,
                    }
                func = funcs.get(category, None)
                if func:
                    list = func()
                else:
                    raise ValueError(category + ' has no get with ids function')
            else:
                list = self.get_custom_items_with_ids(label=cat['label'])
            tids[category] = {}
            if category == 'authors':
                for l in list:
                    (id, val, sort_val) = (l[0], l[1], l[2])
                    tids[category][val] = (id, sort_val)
            elif category == 'languages':
                for l in list:
                    id, val = l[0], calibre_langcode_to_name(l[1])
                    tids[category][l[1]] = (id, val)
            elif cat['datatype'] == 'series':
                for l in list:
                    (id, val) = (l[0], l[1])
                    tids[category][val] = (id, title_sort(val))
            elif cat['datatype'] == 'rating':
                for l in list:
                    (id, val) = (l[0], l[1])
                    tids[category][val] = (id, '{0:05.2f}'.format(val))
            elif cat['datatype'] == 'text' and cat['is_multiple'] and \
                            cat['display'].get('is_names', False):
                    for l in list:
                        (id, val) = (l[0], l[1])
                        tids[category][val] = (id, author_to_author_sort(val))
            else:
                for l in list:
                    (id, val) = (l[0], l[1])
                    tids[category][val] = (id, val)
            # add an empty category to the category map
            tcategories[category] = {}
            # create a list of category/field_index for the books scan to use.
            # This saves iterating through field_metadata for each book
            md.append((category, cat['rec_index'],
                       cat['is_multiple'].get('cache_to_list', None), False))

        for category in tb_cats.iterkeys():
            cat = tb_cats[category]
            if cat['datatype'] == 'composite' and \
                                cat['display'].get('make_category', False):
                tids[category] = {}
                tcategories[category] = {}
                md.append((category, cat['rec_index'],
                           cat['is_multiple'].get('cache_to_list', None),
                           cat['datatype'] == 'composite'))
        #print 'end phase "collection":', time.clock() - last, 'seconds'
        #last = time.clock()

        # Now scan every book looking for category items.
        # Code below is duplicated because it shaves off 10% of the loop time
        id_dex = self.FIELD_MAP['id']
        rating_dex = self.FIELD_MAP['rating']
        tag_class = LibraryDatabase2.TCat_Tag
        for book in self.data.iterall():
            if id_filter is not None and book[id_dex] not in id_filter:
                continue
            rating = book[rating_dex]
            # We kept track of all possible category field_map positions above
            for (cat, dex, mult, is_comp) in md:
                if not book[dex]:
                    continue
                tid_cat = tids[cat]
                tcats_cat = tcategories[cat]
                if not mult:
                    val = book[dex]
                    if is_comp:
                        item = tcats_cat.get(val, None)
                        if not item:
                            item = tag_class(val, val)
                            tcats_cat[val] = item
                        item.c += 1
                        item.id = val
                        if rating > 0:
                            item.rt += rating
                            item.rc += 1
                        continue
                    try:
                        (item_id, sort_val) = tid_cat[val] # let exceptions fly
                        item = tcats_cat.get(val, None)
                        if not item:
                            item = tag_class(val, sort_val)
                            tcats_cat[val] = item
                        item.c += 1
                        item.id_set.add(book[0])
                        item.id = item_id
                        if rating > 0:
                            item.rt += rating
                            item.rc += 1
                    except:
                        prints('get_categories: item', val, 'is not in', cat, 'list!')
                else:
                    vals = book[dex].split(mult)
                    if is_comp:
                        vals = [v.strip() for v in vals if v.strip()]
                        for val in vals:
                            if val not in tid_cat:
                                tid_cat[val] = (val, val)
                    for val in vals:
                        try:
                            (item_id, sort_val) = tid_cat[val] # let exceptions fly
                            item = tcats_cat.get(val, None)
                            if not item:
                                item = tag_class(val, sort_val)
                                tcats_cat[val] = item
                            item.c += 1
                            item.id_set.add(book[0])
                            item.id = item_id
                            if rating > 0:
                                item.rt += rating
                                item.rc += 1
                        except:
                            prints('get_categories: item', val, 'is not in', cat, 'list!')

        #print 'end phase "books":', time.clock() - last, 'seconds'
        #last = time.clock()

        # Now do news
        tcategories['news'] = {}
        cat = tb_cats['news']
        tn = cat['table']
        cn = cat['column']
        if ids is None:
            query = '''SELECT id, {0}, count, avg_rating, sort
                       FROM tag_browser_{1}'''.format(cn, tn)
        else:
            query = '''SELECT id, {0}, count, avg_rating, sort
                       FROM tag_browser_filtered_{1}'''.format(cn, tn)
        # results will be sorted later
        data = self.conn.get(query)
        for r in data:
            item = LibraryDatabase2.TCat_Tag(r[1], r[1])
            item.set_all(c=r[2], rt=r[2]*r[3], rc=r[2], id=r[0])
            tcategories['news'][r[1]] = item

        #print 'end phase "news":', time.clock() - last, 'seconds'
        #last = time.clock()

        # Build the real category list by iterating over the temporary copy
        # and building the Tag instances.
        categories = {}
        tag_class = Tag
        for category in tb_cats.iterkeys():
            if category not in tcategories:
                continue
            cat = tb_cats[category]

            # prepare the place where we will put the array of Tags
            categories[category] = []

            # icon_map is not None if get_categories is to store an icon and
            # possibly a tooltip in the tag structure.
            icon = None
            tooltip = '(' + category + ')'
            label = tb_cats.key_to_label(category)
            if icon_map:
                if not tb_cats.is_custom_field(category):
                    if category in icon_map:
                        icon = icon_map[label]
                else:
                    icon = icon_map['custom:']
                    icon_map[category] = icon

            datatype = cat['datatype']
            avgr = lambda x: 0.0 if x.rc == 0 else x.rt/x.rc
            # Duplicate the build of items below to avoid using a lambda func
            # in the main Tag loop. Saves a few %
            if datatype == 'rating':
                formatter = (lambda x:u'\u2605'*int(x/2))
                avgr = lambda x : x.n
                # eliminate the zero ratings line as well as count == 0
                items = [v for v in tcategories[category].values() if v.c > 0 and v.n != 0]
            elif category == 'authors':
                # Clean up the authors strings to human-readable form
                formatter = (lambda x: x.replace('|', ','))
                items = [v for v in tcategories[category].values() if v.c > 0]
            elif category == 'languages':
                # Use a human readable language string
                formatter = calibre_langcode_to_name
                items = [v for v in tcategories[category].values() if v.c > 0]
            else:
                formatter = (lambda x:unicode(x))
                items = [v for v in tcategories[category].values() if v.c > 0]

            # sort the list
            if sort == 'name':
                kf = lambda x :sort_key(x.s)
                reverse=False
            elif sort == 'popularity':
                kf = lambda x: x.c
                reverse=True
            else:
                kf = avgr
                reverse=True
            items.sort(key=kf, reverse=reverse)

            if tweaks['categories_use_field_for_author_name'] == 'author_sort' and\
                    (category == 'authors' or
                     (cat['display'].get('is_names', False) and
                      cat['is_custom'] and cat['is_multiple'] and
                      cat['datatype'] == 'text')):
                use_sort_as_name = True
            else:
                use_sort_as_name = False
            is_editable = category not in ['news', 'rating', 'languages']
            categories[category] = [tag_class(formatter(r.n), count=r.c, id=r.id,
                                        avg=avgr(r), sort=r.s, icon=icon,
                                        tooltip=tooltip, category=category,
                                        id_set=r.id_set, is_editable=is_editable,
                                        use_sort_as_name=use_sort_as_name)
                                    for r in items]

        #print 'end phase "tags list":', time.clock() - last, 'seconds'
        #last = time.clock()

        # Needed for legacy databases that have multiple ratings that
        # map to n stars
        for r in categories['rating']:
            r.id_set = None
            for x in categories['rating']:
                if r.name == x.name and r.id != x.id:
                    r.count = r.count + x.count
                    categories['rating'].remove(x)
                    break

        # We delayed computing the standard formats category because it does not
        # use a view, but is computed dynamically
        categories['formats'] = []
        icon = None
        if icon_map and 'formats' in icon_map:
                icon = icon_map['formats']
        for fmt in self.conn.get('SELECT DISTINCT format FROM data'):
            fmt = fmt[0]
            if ids is not None:
                count = self.conn.get('''SELECT COUNT(id)
                                       FROM data
                                       WHERE format=? AND
                                       books_list_filter(book)''', (fmt,),
                                       all=False)
            else:
                count = self.conn.get('''SELECT COUNT(id)
                                       FROM data
                                       WHERE format=?''', (fmt,),
                                       all=False)
            if count > 0:
                categories['formats'].append(Tag(fmt, count=count, icon=icon,
                                                 category='formats', is_editable=False))

        if sort == 'popularity':
            categories['formats'].sort(key=lambda x: x.count, reverse=True)
        else: # no ratings exist to sort on
            # No need for ICU here.
            categories['formats'].sort(key = lambda x:x.name)

        # Now do identifiers. This works like formats
        categories['identifiers'] = []
        icon = None
        if icon_map and 'identifiers' in icon_map:
                icon = icon_map['identifiers']
        for ident in self.conn.get('SELECT DISTINCT type FROM identifiers'):
            ident = ident[0]
            if ids is not None:
                count = self.conn.get('''SELECT COUNT(book)
                                       FROM identifiers
                                       WHERE type=? AND
                                       books_list_filter(book)''', (ident,),
                                       all=False)
            else:
                count = self.conn.get('''SELECT COUNT(id)
                                       FROM identifiers
                                       WHERE type=?''', (ident,),
                                       all=False)
            if count > 0:
                categories['identifiers'].append(Tag(ident, count=count, icon=icon,
                                                 category='identifiers',
                                                 is_editable=False))

        if sort == 'popularity':
            categories['identifiers'].sort(key=lambda x: x.count, reverse=True)
        else: # no ratings exist to sort on
            # No need for ICU here.
            categories['identifiers'].sort(key = lambda x:x.name)

        #### Now do the user-defined categories. ####
        user_categories = dict.copy(self.clean_user_categories())

        # We want to use same node in the user category as in the source
        # category. To do that, we need to find the original Tag node. There is
        # a time/space tradeoff here. By converting the tags into a map, we can
        # do the verification in the category loop much faster, at the cost of
        # temporarily duplicating the categories lists.
        taglist = {}
        for c in categories.keys():
            taglist[c] = dict(map(lambda t:(icu_lower(t.name), t), categories[c]))

        muc = self.prefs.get('grouped_search_make_user_categories', [])
        gst = self.prefs.get('grouped_search_terms', {})
        for c in gst:
            if c not in muc:
                continue
            user_categories[c] = []
            for sc in gst[c]:
                if sc in categories.keys():
                    for t in categories[sc]:
                        user_categories[c].append([t.name, sc, 0])

        gst_icon = icon_map['gst'] if icon_map else None
        for user_cat in sorted(user_categories.keys(), key=sort_key):
            items = []
            names_seen = {}
            for (name,label,ign) in user_categories[user_cat]:
                n = icu_lower(name)
                if label in taglist and n in taglist[label]:
                    if user_cat in gst:
                        # for gst items, make copy and consolidate the tags by name.
                        if n in names_seen:
                            t = names_seen[n]
                            t.id_set |= taglist[label][n].id_set
                            t.count += taglist[label][n].count
                            t.tooltip = t.tooltip.replace(')', ', ' + label + ')')
                        else:
                            t = copy.copy(taglist[label][n])
                            t.icon = gst_icon
                            names_seen[t.name] = t
                            items.append(t)
                    else:
                        items.append(taglist[label][n])
                # else: do nothing, to not include nodes w zero counts
            cat_name = '@' + user_cat # add the '@' to avoid name collision
            # Not a problem if we accumulate entries in the icon map
            if icon_map is not None:
                icon_map[cat_name] = icon_map['user:']
            if sort == 'popularity':
                categories[cat_name] = \
                    sorted(items, key=lambda x: x.count, reverse=True)
            elif sort == 'name':
                categories[cat_name] = \
                    sorted(items, key=lambda x: sort_key(x.sort))
            else:
                categories[cat_name] = \
                    sorted(items, key=lambda x:x.avg_rating, reverse=True)

        #### Finally, the saved searches category ####
        items = []
        icon = None
        if icon_map and 'search' in icon_map:
                icon = icon_map['search']
        for srch in saved_searches().names():
            items.append(Tag(srch, tooltip=saved_searches().lookup(srch),
                             sort=srch, icon=icon, category='search',
                             is_editable=False))
        if len(items):
            if icon_map is not None:
                icon_map['search'] = icon_map['search']
            categories['search'] = items

        #print 'last phase ran in:', time.clock() - last, 'seconds'
        #print 'get_categories ran in:', time.clock() - start, 'seconds'

        return categories

    ############# End get_categories

    def tags_older_than(self, tag, delta, must_have_tag=None,
            must_have_authors=None):
        '''
        Return the ids of all books having the tag ``tag`` that are older than
        than the specified time. tag comparison is case insensitive.

        :param delta: A timedelta object or None. If None, then all ids with
        the tag are returned.
        :param must_have_tag: If not None the list of matches will be
        restricted to books that have this tag
        :param must_have_authors: A list of authors. If not None the list of
        matches will be restricted to books that have these authors (case
        insensitive).
        '''
        tag = tag.lower().strip()
        mht = must_have_tag.lower().strip() if must_have_tag else None
        now = nowf()
        tindex = self.FIELD_MAP['timestamp']
        gindex = self.FIELD_MAP['tags']
        iindex = self.FIELD_MAP['id']
        aindex = self.FIELD_MAP['authors']
        mah = must_have_authors
        if mah is not None:
            mah = [x.replace(',', '|').lower() for x in mah]
            mah = ','.join(mah)
        for r in self.data._data:
            if r is not None:
                if delta is None or (now - r[tindex]) > delta:
                    if mah:
                        authors = r[aindex] or ''
                        if authors.lower() != mah:
                            continue
                    tags = r[gindex]
                    if tags:
                        tags = [x.strip() for x in tags.lower().split(',')]
                        if tag in tags and (mht is None or mht in tags):
                            yield r[iindex]

    def get_next_series_num_for(self, series):
        series_id = None
        if series:
            series_id = self.conn.get('SELECT id from series WHERE name=?',
                (series,), all=False)
        if series_id is None:
            if isinstance(tweaks['series_index_auto_increment'], (int, float)):
                return float(tweaks['series_index_auto_increment'])
            return 1.0
        series_indices = self.conn.get(
            ('SELECT series_index FROM books WHERE id IN '
            '(SELECT book FROM books_series_link where series=?) '
            'ORDER BY series_index'),
            (series_id,))
        return self._get_next_series_num_for_list(series_indices)

    def _get_next_series_num_for_list(self, series_indices):
        if not series_indices:
            if isinstance(tweaks['series_index_auto_increment'], (int, float)):
                return float(tweaks['series_index_auto_increment'])
            return 1.0
        series_indices = [x[0] for x in series_indices]
        if tweaks['series_index_auto_increment'] == 'next':
            return series_indices[-1] + 1
        if tweaks['series_index_auto_increment'] == 'first_free':
            for i in range(1, 10000):
                if i not in series_indices:
                    return i
            # really shouldn't get here.
        if tweaks['series_index_auto_increment'] == 'next_free':
            for i in range(int(ceil(series_indices[0])), 10000):
                if i not in series_indices:
                    return i
            # really shouldn't get here.
        if tweaks['series_index_auto_increment'] == 'last_free':
            for i in range(int(ceil(series_indices[-1])), 0, -1):
                if i not in series_indices:
                    return i
            return series_indices[-1] + 1
        if isinstance(tweaks['series_index_auto_increment'], (int, float)):
            return float(tweaks['series_index_auto_increment'])
        return 1.0

    def set(self, row, column, val, allow_case_change=False):
        '''
        Convenience method for setting the title, authors, publisher or rating
        '''
        id = self.data[row][0]
        col = {'title':1, 'authors':2, 'publisher':3, 'rating':4, 'tags':7}[column]

        books_to_refresh = set()
        self.data.set(row, col, val)
        if column == 'authors':
            val = string_to_authors(val)
            books_to_refresh |= self.set_authors(id, val, notify=False,
                                                 allow_case_change=allow_case_change)
        elif column == 'title':
            self.set_title(id, val, notify=False)
        elif column == 'publisher':
            books_to_refresh |= self.set_publisher(id, val, notify=False,
                                                   allow_case_change=allow_case_change)
        elif column == 'rating':
            self.set_rating(id, val, notify=False)
        elif column == 'tags':
            books_to_refresh |= \
                self.set_tags(id, [x.strip() for x in val.split(',') if x.strip()],
                    append=False, notify=False, allow_case_change=allow_case_change)
        self.data.refresh_ids(self, [id])
        self.set_path(id, True)
        self.notify('metadata', [id])
        return books_to_refresh

    def set_metadata(self, id, mi, ignore_errors=False, set_title=True,
                     set_authors=True, commit=True, force_changes=False,
                     notify=True):
        '''
        Set metadata for the book `id` from the `Metadata` object `mi`

        Setting force_changes=True will force set_metadata to update fields even
        if mi contains empty values. In this case, 'None' is distinguished from
        'empty'. If mi.XXX is None, the XXX is not replaced, otherwise it is.
        The tags, identifiers, and cover attributes are special cases. Tags and
        identifiers cannot be set to None so then will always be replaced if
        force_changes is true. You must ensure that mi contains the values you
        want the book to have. Covers are always changed if a new cover is
        provided, but are never deleted. Also note that force_changes has no
        effect on setting title or authors.
        '''
        if callable(getattr(mi, 'to_book_metadata', None)):
            # Handle code passing in a OPF object instead of a Metadata object
            mi = mi.to_book_metadata()

        def doit(func, *args, **kwargs):
            try:
                func(*args, **kwargs)
            except:
                if ignore_errors:
                    traceback.print_exc()
                else:
                    raise

        def should_replace_field(attr):
            return (force_changes and (mi.get(attr, None) is not None)) or \
                    not mi.is_null(attr)

        path_changed = False
        if set_title and mi.title:
            self._set_title(id, mi.title)
            path_changed = True
        if set_authors:
            if not mi.authors:
                mi.authors = [_('Unknown')]
            authors = []
            for a in mi.authors:
                authors += string_to_authors(a)
            self._set_authors(id, authors)
            path_changed = True
        if path_changed:
            self.set_path(id, index_is_id=True)

        if should_replace_field('title_sort'):
            self.set_title_sort(id, mi.title_sort, notify=False, commit=False)
        if should_replace_field('author_sort'):
            doit(self.set_author_sort, id, mi.author_sort, notify=False,
                    commit=False)
        if should_replace_field('publisher'):
            doit(self.set_publisher, id, mi.publisher, notify=False,
                    commit=False)

        # Setting rating to zero is acceptable.
        if mi.rating is not None:
            doit(self.set_rating, id, mi.rating, notify=False, commit=False)
        if should_replace_field('series'):
            doit(self.set_series, id, mi.series, notify=False, commit=False)

        # force_changes has no effect on cover manipulation
        if mi.cover_data[1] is not None:
            doit(self.set_cover, id, mi.cover_data[1], commit=False)
        elif mi.cover is not None:
            if os.access(mi.cover, os.R_OK):
                with lopen(mi.cover, 'rb') as f:
                    raw = f.read()
                if raw:
                    doit(self.set_cover, id, raw, commit=False)

        # if force_changes is true, tags are always replaced because the
        # attribute cannot be set to None.
        if should_replace_field('tags'):
            doit(self.set_tags, id, mi.tags, notify=False, commit=False)

        if should_replace_field('comments'):
            doit(self.set_comment, id, mi.comments, notify=False, commit=False)

        if should_replace_field('languages'):
            doit(self.set_languages, id, mi.languages, notify=False, commit=False)

        # Setting series_index to zero is acceptable
        if mi.series_index is not None:
            doit(self.set_series_index, id, mi.series_index, notify=False,
                    commit=False)
        if should_replace_field('pubdate'):
            doit(self.set_pubdate, id, mi.pubdate, notify=False, commit=False)
        if getattr(mi, 'timestamp', None) is not None:
            doit(self.set_timestamp, id, mi.timestamp, notify=False,
                    commit=False)

        # identifiers will always be replaced if force_changes is True
        mi_idents = mi.get_identifiers()
        if force_changes:
            self.set_identifiers(id, mi_idents, notify=False, commit=False)
        elif mi_idents:
            identifiers = self.get_identifiers(id, index_is_id=True)
            for key, val in mi_idents.iteritems():
                if val and val.strip(): # Don't delete an existing identifier
                    identifiers[icu_lower(key)] = val
            self.set_identifiers(id, identifiers, notify=False, commit=False)


        user_mi = mi.get_all_user_metadata(make_copy=False)
        for key in user_mi.iterkeys():
            if key in self.field_metadata and \
                    user_mi[key]['datatype'] == self.field_metadata[key]['datatype'] and \
                    (user_mi[key]['datatype'] != 'text' or
                     user_mi[key]['is_multiple'] == self.field_metadata[key]['is_multiple']):
                val = mi.get(key, None)
                if force_changes or val is not None:
                    doit(self.set_custom, id, val=val, extra=mi.get_extra(key),
                         label=user_mi[key]['label'], commit=False, notify=False)
        if commit:
            self.conn.commit()
        if notify:
            self.notify('metadata', [id])

    def authors_sort_strings(self, id, index_is_id=False):
        '''
        Given a book, return the list of author sort strings
        for the book's authors
        '''
        id = id if index_is_id else self.id(id)
        aut_strings = self.conn.get('''
                        SELECT sort
                        FROM authors, books_authors_link as bl
                        WHERE bl.book=? and authors.id=bl.author
                        ORDER BY bl.id''', (id,))
        result = []
        for (sort,) in aut_strings:
            result.append(sort)
        return result

    # Given a book, return the map of author sort strings for the book's authors
    def authors_with_sort_strings(self, id, index_is_id=False):
        id = id if index_is_id else self.id(id)
        aut_strings = self.conn.get('''
                        SELECT authors.id, authors.name, authors.sort, authors.link
                        FROM authors, books_authors_link as bl
                        WHERE bl.book=? and authors.id=bl.author
                        ORDER BY bl.id''', (id,))
        result = []
        for (id_, author, sort, link) in aut_strings:
            result.append((id_, author.replace('|', ','), sort, link))
        return result

    # Given a book, return the author_sort string for authors of the book
    def author_sort_from_book(self, id, index_is_id=False):
        auts = self.authors_sort_strings(id, index_is_id)
        return ' & '.join(auts).replace('|', ',')

    # Given an author, return a list of books with that author
    def books_for_author(self, id_, index_is_id=False):
        id_ = id_ if index_is_id else self.id(id_)
        books = self.conn.get('''
                        SELECT bl.book
                        FROM books_authors_link as bl
                        WHERE bl.author=?''', (id_,))
        return [b[0] for b in books]

    # Given a list of authors, return the author_sort string for the authors,
    # preferring the author sort associated with the author over the computed
    # string
    def author_sort_from_authors(self, authors):
        result = []
        for aut in authors:
            r = self.conn.get('SELECT sort FROM authors WHERE name=?',
                              (aut.replace(',', '|'),), all=False)
            if r is None:
                result.append(author_to_author_sort(aut))
            else:
                result.append(r)
        return ' & '.join(result).replace('|', ',')

    def _update_author_in_cache(self, id_, ss, final_authors):
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (ss, id_))
        self.data.set(id_, self.FIELD_MAP['authors'],
                      ','.join([a.replace(',', '|') for a in final_authors]),
                      row_is_id=True)
        self.data.set(id_, self.FIELD_MAP['author_sort'], ss, row_is_id=True)

        aum = self.authors_with_sort_strings(id_, index_is_id=True)
        self.data.set(id_, self.FIELD_MAP['au_map'],
            ':#:'.join([':::'.join((au.replace(',', '|'), aus, aul))
                                            for (_, au, aus, aul) in aum]),
            row_is_id=True)

    def _set_authors(self, id, authors, allow_case_change=False):
        if not authors:
            authors = [_('Unknown')]
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        books_to_refresh = set([])
        final_authors = []
        for a in authors:
            case_change = False
            if not a:
                continue
            a = a.strip().replace(',', '|')
            if not isinstance(a, unicode):
                a = a.decode(preferred_encoding, 'replace')
            aus = self.conn.get('SELECT id, name, sort FROM authors WHERE name=?', (a,))
            if aus:
                aid, name, sort = aus[0]
                # Handle change of case
                if name != a:
                    if allow_case_change:
                        ns = author_to_author_sort(a.replace('|', ','))
                        if strcmp(sort, ns) == 0:
                            sort = ns
                        self.conn.execute('''UPDATE authors SET name=?, sort=?
                                             WHERE id=?''', (a, sort, aid))
                        case_change = True
                    else:
                        a = name
            else:
                aid = self.conn.execute('''INSERT INTO authors(name)
                                           VALUES (?)''', (a,)).lastrowid
            final_authors.append(a.replace('|', ','))
            try:
                self.conn.execute('''INSERT INTO books_authors_link(book, author)
                                     VALUES (?,?)''', (id, aid))
            except IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
            if case_change:
                bks = self.conn.get('''SELECT book FROM books_authors_link
                                       WHERE author=?''', (aid,))
                books_to_refresh |= set([bk[0] for bk in bks])
                for bk in books_to_refresh:
                    ss = self.author_sort_from_book(id, index_is_id=True)
                    aus = self.author_sort(bk, index_is_id=True)
                    if strcmp(aus, ss) ==  0:
                        self._update_author_in_cache(bk, ss, final_authors)
        # This can repeat what was done above in rare cases. Let it.
        ss = self.author_sort_from_book(id, index_is_id=True)
        self._update_author_in_cache(id, ss, final_authors)
        return books_to_refresh

    def set_authors(self, id, authors, notify=True, commit=True,
                    allow_case_change=False):
        '''
        Note that even if commit is False, the db will still be committed to
        because this causes the location of files to change

        :param authors: A list of authors.
        '''
        books_to_refresh = self._set_authors(id, authors,
                                             allow_case_change=allow_case_change)
        self.dirtied(set([id])|books_to_refresh, commit=False)
        if commit:
            self.conn.commit()
        self.set_path(id, index_is_id=True)
        if notify:
            self.notify('metadata', [id])
        return books_to_refresh

    def set_title_sort(self, id, title_sort_, notify=True, commit=True):
        if not title_sort_:
            return False
        if isbytestring(title_sort_):
            title_sort_ = title_sort_.decode(preferred_encoding, 'replace')
        self.conn.execute('UPDATE books SET sort=? WHERE id=?', (title_sort_, id))
        self.data.set(id, self.FIELD_MAP['sort'], title_sort_, row_is_id=True)
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        if notify:
            self.notify('metadata', [id])
        return True

    def _set_title(self, id, title):
        if not title:
            return False
        if isbytestring(title):
            title = title.decode(preferred_encoding, 'replace')
        old_title = self.title(id, index_is_id=True)
        # We cannot check if old_title == title as previous code might have
        # already updated the cache
        only_case_change = icu_lower(old_title) == icu_lower(title)
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.data.set(id, self.FIELD_MAP['title'], title, row_is_id=True)
        if only_case_change:
            # SQLite update trigger will not update sort on a case change
            self.conn.execute('UPDATE books SET sort=? WHERE id=?',
                    (title_sort(title), id))
        ts = self.conn.get('SELECT sort FROM books WHERE id=?', (id,),
                all=False)
        if ts:
            self.data.set(id, self.FIELD_MAP['sort'], ts, row_is_id=True)
        return True

    def set_title(self, id, title, notify=True, commit=True):
        '''
        Note that even if commit is False, the db will still be committed to
        because this causes the location of files to change
        '''
        if not self._set_title(id, title):
            return
        self.set_path(id, index_is_id=True)
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        if notify:
            self.notify('metadata', [id])

    def set_languages(self, book_id, languages, notify=True, commit=True):
        self.conn.execute(
            'DELETE FROM books_languages_link WHERE book=?', (book_id,))
        self.conn.execute('''DELETE FROM languages WHERE (SELECT COUNT(id)
                                 FROM books_languages_link WHERE
                                 books_languages_link.lang_code=languages.id) < 1''')

        books_to_refresh = set([book_id])
        final_languages = []
        for l in languages:
            lc = canonicalize_lang(l)
            if not lc or lc in final_languages or lc in ('und', 'zxx', 'mis',
                    'mul'):
                continue
            final_languages.append(lc)
            lc_id = self.conn.get('SELECT id FROM languages WHERE lang_code=?',
                    (lc,), all=False)
            if lc_id is None:
                lc_id = self.conn.execute('''INSERT INTO languages(lang_code)
                                           VALUES (?)''', (lc,)).lastrowid
            self.conn.execute('''INSERT INTO books_languages_link(book, lang_code)
                                     VALUES (?,?)''', (book_id, lc_id))
        self.dirtied(books_to_refresh, commit=False)
        if commit:
            self.conn.commit()
        self.data.set(book_id, self.FIELD_MAP['languages'],
                u','.join(final_languages), row_is_id=True)
        if notify:
            self.notify('metadata', [book_id])
        return books_to_refresh

    def set_timestamp(self, id, dt, notify=True, commit=True):
        if dt:
            self.conn.execute('UPDATE books SET timestamp=? WHERE id=?', (dt, id))
            self.data.set(id, self.FIELD_MAP['timestamp'], dt, row_is_id=True)
            self.dirtied([id], commit=False)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id])

    def set_pubdate(self, id, dt, notify=True, commit=True):
        if dt:
            self.conn.execute('UPDATE books SET pubdate=? WHERE id=?', (dt, id))
            self.data.set(id, self.FIELD_MAP['pubdate'], dt, row_is_id=True)
            self.dirtied([id], commit=False)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id])


    def set_publisher(self, id, publisher, notify=True, commit=True,
                      allow_case_change=False):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        self.conn.execute('''DELETE FROM publishers WHERE (SELECT COUNT(id)
                             FROM books_publishers_link
                             WHERE publisher=publishers.id) < 1''')
        books_to_refresh = set([])
        if publisher:
            case_change = False
            if not isinstance(publisher, unicode):
                publisher = publisher.decode(preferred_encoding, 'replace')
            pubx = self.conn.get('''SELECT id,name from publishers
                                    WHERE name=?''', (publisher,))
            if pubx:
                aid, cur_name = pubx[0]
                if publisher != cur_name:
                    if allow_case_change:
                        self.conn.execute('''UPDATE publishers SET name=?
                                         WHERE id=?''', (publisher, aid))
                        case_change = True
                    else:
                        publisher = cur_name
            else:
                aid = self.conn.execute('''INSERT INTO publishers(name)
                                           VALUES (?)''', (publisher,)).lastrowid
            self.conn.execute('''INSERT INTO books_publishers_link(book, publisher)
                                 VALUES (?,?)''', (id, aid))
            if case_change:
                bks = self.conn.get('''SELECT book FROM books_publishers_link
                                       WHERE publisher=?''', (aid,))
                books_to_refresh |= set([bk[0] for bk in bks])
        self.dirtied(set([id])|books_to_refresh, commit=False)
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['publisher'], publisher, row_is_id=True)
        if notify:
            self.notify('metadata', [id])
        return books_to_refresh

    def set_uuid(self, id, uuid, notify=True, commit=True):
        if uuid:
            self.conn.execute('UPDATE books SET uuid=? WHERE id=?', (uuid, id))
            self.data.set(id, self.FIELD_MAP['uuid'], uuid, row_is_id=True)
            self.dirtied([id], commit=False)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id])

    # Convenience methods for tags_list_editor
    # Note: we generally do not need to refresh_ids because library_view will
    # refresh everything.

    def get_ratings_with_ids(self):
        result = self.conn.get('SELECT id,rating FROM ratings')
        if not result:
            return []
        return result

    def dirty_books_referencing(self, field, id, commit=True):
        # Get the list of books to dirty -- all books that reference the item
        table = self.field_metadata[field]['table']
        link = self.field_metadata[field]['link_column']
        bks = self.conn.get(
            'SELECT book from books_{0}_link WHERE {1}=?'.format(table, link),
            (id,))
        books = []
        for (book_id,) in bks:
            books.append(book_id)
        self.dirtied(books, commit=commit)

    def get_tags_with_ids(self):
        result = self.conn.get('SELECT id,name FROM tags')
        if not result:
            return []
        return result

    def get_languages_with_ids(self):
        result = self.conn.get('SELECT id,lang_code FROM languages')
        if not result:
            return []
        return result

    def rename_tag(self, old_id, new_name):
        # It is possible that new_name is in fact a set of names. Split it on
        # comma to find out. If it is, then rename the first one and append the
        # rest
        new_names = [t.strip() for t in new_name.strip().split(',') if t.strip()]
        new_name = new_names[0]
        new_names = new_names[1:]

        # get the list of books that reference the tag being changed
        books = self.conn.get('''SELECT book from books_tags_link
                                 WHERE tag=?''', (old_id,))
        books = [b[0] for b in books]

        new_id = self.conn.get(
                    '''SELECT id from tags
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            # easy cases. Simply rename the tag. Do it even if equal, in case
            # there is a change of case
            self.conn.execute('''UPDATE tags SET name=?
                                 WHERE id=?''', (new_name, old_id))
            new_id = old_id
        else:
            # It is possible that by renaming a tag, the tag will appear
            # twice on a book. This will throw an integrity error, aborting
            # all the changes. To get around this, we first delete any links
            # to the new_id from books referencing the old_id, so that
            # renaming old_id to new_id will be unique on the book
            for book_id in books:
                self.conn.execute('''DELETE FROM books_tags_link
                                     WHERE book=? and tag=?''', (book_id, new_id))

            # Change the link table to point at the new tag
            self.conn.execute('''UPDATE books_tags_link SET tag=?
                                 WHERE tag=?''',(new_id, old_id,))
            # Get rid of the no-longer used publisher
            self.conn.execute('DELETE FROM tags WHERE id=?', (old_id,))

        if new_names:
            # have some left-over names to process. Add them to the book.
            for book_id in books:
                self.set_tags(book_id, new_names, append=True, notify=False,
                              commit=False)
        self.dirtied(books, commit=False)
        self.clean_standard_field('tags', commit=False)
        self.conn.commit()

    def delete_tag_using_id(self, id):
        self.dirty_books_referencing('tags', id, commit=False)
        self.conn.execute('DELETE FROM books_tags_link WHERE tag=?', (id,))
        self.conn.execute('DELETE FROM tags WHERE id=?', (id,))
        self.conn.commit()

    def get_series_with_ids(self):
        result = self.conn.get('SELECT id,name FROM series')
        if not result:
            return []
        return result

    def rename_series(self, old_id, new_name, change_index=True):
        new_name = new_name.strip()
        new_id = self.conn.get(
                    '''SELECT id from series
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            new_id = old_id
            self.conn.execute('UPDATE series SET name=? WHERE id=?',
                              (new_name, old_id))
        else:
            # New series exists. Must update the link, then assign a
            # new series index to each of the books.

            if change_index:
                # Get the list of books where we must update the series index
                books = self.conn.get('''SELECT books.id
                                         FROM books, books_series_link as lt
                                         WHERE books.id = lt.book AND lt.series=?
                                         ORDER BY books.series_index''', (old_id,))
            # Now update the link table
            self.conn.execute('''UPDATE books_series_link
                                 SET series=?
                                 WHERE series=?''',(new_id, old_id,))
            if change_index and tweaks['series_index_auto_increment'] != 'no_change':
                # Now set the indices
                for (book_id,) in books:
                    # Get the next series index
                    index = self.get_next_series_num_for(new_name)
                    self.conn.execute('''UPDATE books
                                         SET series_index=?
                                         WHERE id=?''',(index, book_id,))
        self.dirty_books_referencing('series', new_id, commit=False)
        self.clean_standard_field('series', commit=False)
        self.conn.commit()

    def delete_series_using_id(self, id):
        self.dirty_books_referencing('series', id, commit=False)
        books = self.conn.get('SELECT book from books_series_link WHERE series=?', (id,))
        self.conn.execute('DELETE FROM books_series_link WHERE series=?', (id,))
        self.conn.execute('DELETE FROM series WHERE id=?', (id,))
        for (book_id,) in books:
            self.conn.execute('UPDATE books SET series_index=1.0 WHERE id=?', (book_id,))
        self.conn.commit()

    def get_publishers_with_ids(self):
        result = self.conn.get('SELECT id,name FROM publishers')
        if not result:
            return []
        return result

    def rename_publisher(self, old_id, new_name):
        new_name = new_name.strip()
        new_id = self.conn.get(
                    '''SELECT id from publishers
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            new_id = old_id
            # New name doesn't exist. Simply change the old name
            self.conn.execute('UPDATE publishers SET name=? WHERE id=?', \
                              (new_name, old_id))
        else:
            # Change the link table to point at the new one
            self.conn.execute('''UPDATE books_publishers_link
                                 SET publisher=?
                                 WHERE publisher=?''',(new_id, old_id,))
            # Get rid of the no-longer used publisher
            self.conn.execute('DELETE FROM publishers WHERE id=?', (old_id,))
        self.dirty_books_referencing('publisher', new_id, commit=False)
        self.clean_standard_field('publisher', commit=False)
        self.conn.commit()

    def delete_publisher_using_id(self, old_id):
        self.dirty_books_referencing('publisher', old_id, commit=False)
        self.conn.execute('''DELETE FROM books_publishers_link
                             WHERE publisher=?''', (old_id,))
        self.conn.execute('DELETE FROM publishers WHERE id=?', (old_id,))
        self.conn.commit()

    def get_authors_with_ids(self):
        result = self.conn.get('SELECT id,name,sort,link FROM authors')
        if not result:
            return []
        return result

    def get_author_id(self, author):
        author = author.replace(',', '|')
        result = self.conn.get('SELECT id FROM authors WHERE name=?',
                               (author,), all=False)
        return result

    def set_link_field_for_author(self, aid, link, commit=True, notify=False):
        if not link:
            link = ''
        self.conn.execute('UPDATE authors SET link=? WHERE id=?', (link.strip(), aid))
        if commit:
            self.conn.commit()

    def set_sort_field_for_author(self, old_id, new_sort, commit=True, notify=False):
        self.conn.execute('UPDATE authors SET sort=? WHERE id=?', \
                              (new_sort.strip(), old_id))
        if commit:
            self.conn.commit()
        # Now change all the author_sort fields in books by this author
        bks = self.conn.get('SELECT book from books_authors_link WHERE author=?', (old_id,))
        for (book_id,) in bks:
            ss = self.author_sort_from_book(book_id, index_is_id=True)
            self.set_author_sort(book_id, ss, notify=notify, commit=commit)

    def rename_author(self, old_id, new_name):
        # Make sure that any commas in new_name are changed to '|'!
        new_name = new_name.replace(',', '|').strip()
        if not new_name:
            new_name = _('Unknown')

        # Get the list of books we must fix up, one way or the other
        # Save the list so we can use it twice
        bks = self.conn.get('SELECT book from books_authors_link WHERE author=?', (old_id,))
        books = []
        for (book_id,) in bks:
            books.append(book_id)

        # check if the new author already exists
        new_id = self.conn.get('SELECT id from authors WHERE name=?',
                                (new_name,), all=False)
        if new_id is None or old_id == new_id:
            # No name clash. Go ahead and update the author's name
            self.conn.execute('UPDATE authors SET name=? WHERE id=?',
                              (new_name, old_id))
        else:
            # First check for the degenerate case -- changing a value to itself.
            # Update it in case there is a change of case, but do nothing else
            if old_id == new_id:
                self.conn.execute('UPDATE authors SET name=? WHERE id=?',
                              (new_name, old_id))
                self.conn.commit()
                return new_id
            # Author exists. To fix this, we must replace all the authors
            # instead of replacing the one. Reason: db integrity checks can stop
            # the rename process, which would leave everything half-done. We
            # can't do it the same way as tags (delete and add) because author
            # order is important.

            for book_id in books:
                # Get the existing list of authors
                authors = self.conn.get('''
                    SELECT author from books_authors_link
                    WHERE book=?
                    ORDER BY id''',(book_id,))

                # unpack the double-list structure, replacing the old author
                # with the new one while we are at it
                for i,aut in enumerate(authors):
                    authors[i] = aut[0] if aut[0] != old_id else new_id
                # Delete the existing authors list
                self.conn.execute('''DELETE FROM books_authors_link
                                     WHERE book=?''',(book_id,))
                # Change the authors to the new list
                for aid in authors:
                    try:
                        self.conn.execute('''
                            INSERT INTO books_authors_link(book, author)
                            VALUES (?,?)''', (book_id, aid))
                    except IntegrityError:
                        # Sometimes books specify the same author twice in their
                        # metadata. Ignore it.
                        pass
            # Now delete the old author from the DB
            self.conn.execute('DELETE FROM authors WHERE id=?', (old_id,))
        self.dirtied(books, commit=False)
        self.conn.commit()
        # the authors are now changed, either by changing the author's name
        # or replacing the author in the list. Now must fix up the books.
        for book_id in books:
            # First, must refresh the cache to see the new authors
            self.data.refresh_ids(self, [book_id])
            # now fix the filesystem paths
            self.set_path(book_id, index_is_id=True)
            # Next fix the author sort. Reset it to the default
            ss = self.author_sort_from_book(book_id, index_is_id=True)
            self.set_author_sort(book_id, ss)
            # the caller will do a general refresh, so we don't need to
            # do one here
        return new_id

    # end convenience methods

    def get_tags(self, id):
        result = self.conn.get(
        'SELECT name FROM tags WHERE id IN (SELECT tag FROM books_tags_link WHERE book=?)',
        (id,), all=True)
        if not result:
            return set([])
        return set([r[0] for r in result])

    @classmethod
    def cleanup_tags(cls, tags):
        tags = [x.strip().replace(',', ';') for x in tags if x.strip()]
        tags = [x.decode(preferred_encoding, 'replace') \
                    if isbytestring(x) else x for x in tags]
        tags = [u' '.join(x.split()) for x in tags]
        ans, seen = [], set([])
        for tag in tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                ans.append(tag)
        return ans

    def remove_all_tags(self, ids, notify=False, commit=True):
        self.conn.executemany(
            'DELETE FROM books_tags_link WHERE book=?', [(x,) for x in ids])
        self.dirtied(ids, commit=False)
        if commit:
            self.conn.commit()

        for x in ids:
            self.data.set(x, self.FIELD_MAP['tags'], '', row_is_id=True)
        if notify:
            self.notify('metadata', ids)

    def bulk_modify_tags(self, ids, add=[], remove=[], notify=False):
        add = self.cleanup_tags(add)
        remove = self.cleanup_tags(remove)
        remove = set(remove) - set(add)
        if not ids or (not add and not remove):
            return

        # Add tags that do not already exist into the tag table
        all_tags = self.all_tags()
        lt = [t.lower() for t in all_tags]
        new_tags = [t for t in add if t.lower() not in lt]
        if new_tags:
            self.conn.executemany('INSERT INTO tags(name) VALUES (?)', [(x,) for x in
                new_tags])

        # Create the temporary tables to store the ids for books and tags
        # to be operated on
        tables = ('temp_bulk_tag_edit_books', 'temp_bulk_tag_edit_add',
                    'temp_bulk_tag_edit_remove')
        drops = '\n'.join(['DROP TABLE IF EXISTS %s;'%t for t in tables])
        creates = '\n'.join(['CREATE TEMP TABLE %s(id INTEGER PRIMARY KEY);'%t
                for t in tables])
        self.conn.executescript(drops + creates)

        # Populate the books temp table
        self.conn.executemany(
            'INSERT INTO temp_bulk_tag_edit_books VALUES (?)',
                [(x,) for x in ids])

        # Populate the add/remove tags temp tables
        for table, tags in enumerate([add, remove]):
            if not tags:
                continue
            table = tables[table+1]
            insert = ('INSERT INTO %s(id) SELECT tags.id FROM tags WHERE name=?'
                     ' COLLATE PYNOCASE LIMIT 1')
            self.conn.executemany(insert%table, [(x,) for x in tags])

        if remove:
            self.conn.execute(
              '''DELETE FROM books_tags_link WHERE
                    book IN (SELECT id FROM %s) AND
                    tag IN (SELECT id FROM %s)'''
              % (tables[0], tables[2]))

        if add:
            self.conn.execute(
            '''
            INSERT OR REPLACE INTO books_tags_link(book, tag) SELECT {0}.id, {1}.id FROM
            {0}, {1}
            '''.format(tables[0], tables[1])
            )
        self.conn.executescript(drops)
        self.dirtied(ids, commit=False)
        self.conn.commit()

        for x in ids:
            tags = u','.join(self.get_tags(x))
            self.data.set(x, self.FIELD_MAP['tags'], tags, row_is_id=True)
        if notify:
            self.notify('metadata', ids)

    def commit(self):
        self.conn.commit()

    def set_tags(self, id, tags, append=False, notify=True, commit=True,
                 allow_case_change=False):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not tags:
            tags = []
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
            self.conn.execute('''DELETE FROM tags WHERE (SELECT COUNT(id)
                                 FROM books_tags_link WHERE tag=tags.id) < 1''')
        otags = self.get_tags(id)
        tags = self.cleanup_tags(tags)
        books_to_refresh = set([])
        for tag in (set(tags)-otags):
            case_changed = False
            tag = tag.strip()
            if not tag:
                continue
            if not isinstance(tag, unicode):
                tag = tag.decode(preferred_encoding, 'replace')
            existing_tags = self.all_tags()
            lt = [t.lower() for t in existing_tags]
            try:
                idx = lt.index(tag.lower())
            except ValueError:
                idx = -1
            if idx > -1:
                etag = existing_tags[idx]
                tid = self.conn.get('SELECT id FROM tags WHERE name=?', (etag,), all=False)
                if allow_case_change and etag != tag:
                    self.conn.execute('UPDATE tags SET name=? WHERE id=?', (tag, tid))
                    case_changed = True
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid

            if not self.conn.get('''SELECT book FROM books_tags_link
                                    WHERE book=? AND tag=?''', (id, tid), all=False):
                self.conn.execute('''INSERT INTO books_tags_link(book, tag)
                                     VALUES (?,?)''', (id, tid))
            if case_changed:
                bks = self.conn.get('SELECT book FROM books_tags_link WHERE tag=?',
                                        (tid,))
                books_to_refresh |= set([bk[0] for bk in bks])
        self.dirtied(set([id])|books_to_refresh, commit=False)
        if commit:
            self.conn.commit()
        tags = u','.join(self.get_tags(id))
        self.data.set(id, self.FIELD_MAP['tags'], tags, row_is_id=True)
        if notify:
            self.notify('metadata', [id])
        return books_to_refresh

    def unapply_tags(self, book_id, tags, notify=True):
        for tag in tags:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if id:
                self.conn.execute('''DELETE FROM books_tags_link
                                     WHERE tag=? AND book=?''', (id, book_id))
        self.conn.commit()
        self.data.refresh_ids(self, [book_id])
        if notify:
            self.notify('metadata', [id])

    def is_tag_used(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            lt.index(tag.lower())
            return True
        except ValueError:
            return False

    def delete_tag(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            idx = lt.index(tag.lower())
        except ValueError:
            idx = -1
        if idx > -1:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (existing_tags[idx],), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=?', (id,))
                self.conn.execute('DELETE FROM tags WHERE id=?', (id,))
                self.conn.commit()

    series_index_pat = re.compile(r'(.*)\s+\[([.0-9]+)\]$')

    def _get_series_values(self, val):
        if not val:
            return (val, None)
        match = self.series_index_pat.match(val.strip())
        if match is not None:
            idx = match.group(2)
            try:
                idx = float(idx)
                return (match.group(1).strip(), idx)
            except:
                pass
        return (val, None)

    def set_series(self, id, series, notify=True, commit=True, allow_case_change=True):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        self.conn.execute('''DELETE FROM series
                             WHERE (SELECT COUNT(id) FROM books_series_link
                                    WHERE series=series.id) < 1''')
        (series, idx) = self._get_series_values(series)
        books_to_refresh = set([])
        if series:
            case_change = False
            if not isinstance(series, unicode):
                series = series.decode(preferred_encoding, 'replace')
            series = series.strip()
            series = u' '.join(series.split())
            sx = self.conn.get('SELECT id,name from series WHERE name=?', (series,))
            if sx:
                aid, cur_name = sx[0]
                if cur_name != series:
                    if allow_case_change:
                        self.conn.execute('UPDATE series SET name=? WHERE id=?', (series, aid))
                        case_change = True
                    else:
                        series = cur_name
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
            if idx:
                self.set_series_index(id, idx, notify=notify, commit=commit)
            if case_change:
                bks = self.conn.get('SELECT book FROM books_series_link WHERE series=?',
                                        (aid,))
                books_to_refresh |= set([bk[0] for bk in bks])
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['series'], series, row_is_id=True)
        if notify:
            self.notify('metadata', [id])
        return books_to_refresh

    def set_series_index(self, id, idx, notify=True, commit=True):
        if idx is None:
            idx = 1.0
        try:
            idx = float(idx)
        except:
            idx = 1.0
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (idx, id))
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['series_index'], idx, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_rating(self, id, rating, notify=True, commit=True):
        if not rating:
            rating = 0
        rating = int(rating)
        self.conn.execute('DELETE FROM books_ratings_link WHERE book=?',(id,))
        rat = self.conn.get('SELECT id FROM ratings WHERE rating=?', (rating,), all=False)
        rat = rat if rat is not None else self.conn.execute('INSERT INTO ratings(rating) VALUES (?)', (rating,)).lastrowid
        self.conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rat))
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['rating'], rating, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_comment(self, id, text, notify=True, commit=True):
        self.conn.execute('DELETE FROM comments WHERE book=?', (id,))
        if text:
            self.conn.execute('INSERT INTO comments(book,text) VALUES (?,?)', (id, text))
        else:
            text = ''
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['comments'], text, row_is_id=True)
        self.dirtied([id], commit=False)
        if notify:
            self.notify('metadata', [id])

    def set_author_sort(self, id, sort, notify=True, commit=True):
        if not sort:
            sort = ''
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (sort, id))
        self.dirtied([id], commit=False)
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['author_sort'], sort, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def isbn(self, idx, index_is_id=False):
        row = self.data._data[idx] if index_is_id else self.data[idx]
        if row is not None:
            raw = row[self.FIELD_MAP['identifiers']]
            if raw:
                for x in raw.split(','):
                    if x.startswith('isbn:'):
                        return x[5:].strip()

    def get_identifiers(self, idx, index_is_id=False):
        ans = {}
        row = self.data._data[idx] if index_is_id else self.data[idx]
        if row is not None:
            raw = row[self.FIELD_MAP['identifiers']]
            if raw:
                for x in raw.split(','):
                    key, _, val = x.partition(':')
                    key, val = key.strip(), val.strip()
                    if key and val:
                        ans[key] = val

        return ans

    def get_all_identifier_types(self):
        idents = self.conn.get('SELECT DISTINCT type FROM identifiers')
        return [ident[0] for ident in idents]

    def _clean_identifier(self, typ, val):
        typ = icu_lower(typ).strip().replace(':', '').replace(',', '')
        val = val.strip().replace(',', '|').replace(':', '|')
        return typ, val

    def set_identifier(self, id_, typ, val, notify=True, commit=True):
        'If val is empty, deletes identifier of type typ'
        typ, val = self._clean_identifier(typ, val)
        identifiers = self.get_identifiers(id_, index_is_id=True)
        if not typ:
            return
        changed = False
        if not val and typ in identifiers:
            identifiers.pop(typ)
            changed = True
            self.conn.execute(
                'DELETE from identifiers WHERE book=? AND type=?',
                    (id_, typ))
        if val and identifiers.get(typ, None) != val:
            changed = True
            identifiers[typ] = val
            self.conn.execute(
                'INSERT OR REPLACE INTO identifiers (book, type, val) VALUES (?, ?, ?)',
                    (id_, typ, val))
        if changed:
            raw = ','.join(['%s:%s'%(k, v) for k, v in
                identifiers.iteritems()])
            self.data.set(id_, self.FIELD_MAP['identifiers'], raw,
                    row_is_id=True)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id_])

    def set_identifiers(self, id_, identifiers, notify=True, commit=True):
        cleaned = {}
        if not identifiers:
            identifiers = {}
        for typ, val in identifiers.iteritems():
            typ, val = self._clean_identifier(typ, val)
            if val:
                cleaned[typ] = val
        self.conn.execute('DELETE FROM identifiers WHERE book=?', (id_,))
        self.conn.executemany(
            'INSERT INTO identifiers (book, type, val) VALUES (?, ?, ?)',
            [(id_, k, v) for k, v in cleaned.iteritems()])
        raw = ','.join(['%s:%s'%(k, v) for k, v in
                cleaned.iteritems()])
        self.data.set(id_, self.FIELD_MAP['identifiers'], raw,
                    row_is_id=True)
        if commit:
            self.conn.commit()
        if notify:
            self.notify('metadata', [id_])

    def set_isbn(self, id_, isbn, notify=True, commit=True):
        self.set_identifier(id_, 'isbn', isbn, notify=notify, commit=commit)

    def add_catalog(self, path, title):
        from calibre.ebooks.metadata.meta import get_metadata

        format = os.path.splitext(path)[1][1:].lower()
        with lopen(path, 'rb') as stream:
            matches = self.data.get_matches('title', '='+title)
            if matches:
                tag_matches = self.data.get_matches('tags', '='+_('Catalog'))
                matches = matches.intersection(tag_matches)
            db_id = None
            if matches:
                db_id = list(matches)[0]
            if db_id is None:
                obj = self.conn.execute('INSERT INTO books(title, author_sort) VALUES (?, ?)',
                                    (title, 'calibre'))
                db_id = obj.lastrowid
                self.data.books_added([db_id], self)
                self.set_path(db_id, index_is_id=True)
                self.conn.commit()
            try:
                mi = get_metadata(stream, format)
            except:
                mi = Metadata(title, ['calibre'])
            stream.seek(0)
            mi.title, mi.authors = title, ['calibre']
            mi.tags = [_('Catalog')]
            mi.pubdate = mi.timestamp = utcnow()
            if format == 'mobi':
                mi.cover, mi.cover_data = None, (None, None)
            self.set_metadata(db_id, mi)
            self.add_format(db_id, format, stream, index_is_id=True)

        self.conn.commit()
        self.data.refresh_ids(self, [db_id]) # Needed to update format list and size
        return db_id


    def add_news(self, path, arg):
        from calibre.ebooks.metadata.meta import get_metadata

        format = os.path.splitext(path)[1][1:].lower()
        stream = path if hasattr(path, 'read') else lopen(path, 'rb')
        stream.seek(0)
        mi = get_metadata(stream, format, use_libprs_metadata=False,
                force_read_metadata=True)
        # Force the author to calibre as the auto delete of old news checks for
        # both the author==calibre and the tag News
        mi.authors = ['calibre']
        stream.seek(0)
        if mi.series_index is None:
            mi.series_index = self.get_next_series_num_for(mi.series)
        mi.tags = [_('News')]
        if arg['add_title_tag']:
            mi.tags += [arg['title']]
        if arg['custom_tags']:
            mi.tags += arg['custom_tags']
        obj = self.conn.execute('INSERT INTO books(title, author_sort) VALUES (?, ?)',
                              (mi.title, mi.authors[0]))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, index_is_id=True)
        self.conn.commit()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        self.set_metadata(id, mi)

        self.add_format(id, format, stream, index_is_id=True)
        if not hasattr(path, 'read'):
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        return id

    def run_import_plugins(self, path_or_stream, format):
        format = format.lower()
        if hasattr(path_or_stream, 'seek'):
            path_or_stream.seek(0)
            pt = PersistentTemporaryFile('_import_plugin.'+format)
            shutil.copyfileobj(path_or_stream, pt, 1024**2)
            pt.close()
            path = pt.name
        else:
            path = path_or_stream
        return run_plugins_on_import(path, format)

    def _add_newbook_tag(self, mi):
        tags = prefs['new_book_tags']
        if tags:
            for tag in [t.strip() for t in tags]:
                if tag:
                    if mi.tags is None:
                        mi.tags = [tag]
                    else:
                        mi.tags.append(tag)

    def create_book_entry(self, mi, cover=None, add_duplicates=True,
            force_id=None):
        if mi.tags:
            mi.tags = list(mi.tags)
        self._add_newbook_tag(mi)
        if not add_duplicates and self.has_book(mi):
            return None
        series_index = self.get_next_series_num_for(mi.series) \
                    if mi.series_index is None else mi.series_index
        aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
        title = mi.title
        if isbytestring(aus):
            aus = aus.decode(preferred_encoding, 'replace')
        if isbytestring(title):
            title = title.decode(preferred_encoding, 'replace')
        if force_id is None:
            obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                                (title, series_index, aus))
            id = obj.lastrowid
        else:
            id = force_id
            obj = self.conn.execute(
                    'INSERT INTO books(id, title, series_index, '
                        'author_sort) VALUES (?, ?, ?, ?)',
                                (id, title, series_index, aus))

        self.data.books_added([id], self)
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        self.set_metadata(id, mi, ignore_errors=True, commit=True)
        if cover is not None:
            try:
                self.set_cover(id, cover)
            except:
                traceback.print_exc()
        return id


    def add_books(self, paths, formats, metadata, add_duplicates=True,
            return_ids=False):
        '''
        Add a book to the database. The result cache is not updated.
        :param:`paths` List of paths to book files or file-like objects
        '''
        formats, metadata = iter(formats), iter(metadata)
        duplicates = []
        ids = []
        for path in paths:
            mi = metadata.next()
            self._add_newbook_tag(mi)
            format = formats.next()
            if not add_duplicates and self.has_book(mi):
                duplicates.append((path, format, mi))
                continue
            series_index = self.get_next_series_num_for(mi.series) \
                            if mi.series_index is None else mi.series_index
            aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
            title = mi.title
            if isinstance(aus, str):
                aus = aus.decode(preferred_encoding, 'replace')
            if isinstance(title, str):
                title = title.decode(preferred_encoding)
            obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                              (title, series_index, aus))
            id = obj.lastrowid
            self.data.books_added([id], self)
            ids.append(id)
            if mi.timestamp is None:
                mi.timestamp = utcnow()
            if mi.pubdate is None:
                mi.pubdate = utcnow()
            self.set_metadata(id, mi, commit=True, ignore_errors=True)
            npath = self.run_import_plugins(path, format)
            format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
            stream = lopen(npath, 'rb')
            format = check_ebook_format(stream, format)
            self.add_format(id, format, stream, index_is_id=True)
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, ids) # Needed to update format list and size
        if duplicates:
            paths    = list(duplicate[0] for duplicate in duplicates)
            formats  = list(duplicate[1] for duplicate in duplicates)
            metadata = list(duplicate[2] for duplicate in duplicates)
            return (paths, formats, metadata), (ids if return_ids else
                    len(ids))
        return None, (ids if return_ids else len(ids))

    def import_book(self, mi, formats, notify=True, import_hooks=True,
            apply_import_tags=True, preserve_uuid=False):
        series_index = self.get_next_series_num_for(mi.series) \
                        if mi.series_index is None else mi.series_index
        if apply_import_tags:
            self._add_newbook_tag(mi)
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
        if isinstance(aus, str):
            aus = aus.decode(preferred_encoding, 'replace')
        title = mi.title if isinstance(mi.title, unicode) else \
                mi.title.decode(preferred_encoding, 'replace')
        obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                          (title, series_index, aus))
        id = obj.lastrowid
        self.data.books_added([id], self)
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        self.set_metadata(id, mi, ignore_errors=True, commit=True)
        if preserve_uuid and mi.uuid:
            self.set_uuid(id, mi.uuid, commit=False)
        for path in formats:
            ext = os.path.splitext(path)[1][1:].lower()
            if ext == 'opf':
                continue
            if import_hooks:
                self.add_format_with_hooks(id, ext, path, index_is_id=True)
            else:
                with lopen(path, 'rb') as f:
                    self.add_format(id, ext, f, index_is_id=True)
        # Mark the book dirty, It probably already has been done by
        # set_metadata, but probably isn't good enough
        self.dirtied([id], commit=False)
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        if notify:
            self.notify('add', [id])
        return id

    def get_top_level_move_items(self):
        items = set(os.listdir(self.library_path))
        paths = set([])
        for x in self.data.universal_set():
            path = self.path(x, index_is_id=True)
            path = path.split(os.sep)[0]
            paths.add(path)
        paths.add('metadata.db')
        path_map = {}
        for x in paths:
            path_map[x] = x
        if not self.is_case_sensitive:
            for x in items:
                path_map[x.lower()] = x
            items = set(path_map)
            paths = set([x.lower() for x in paths])
        items = items.intersection(paths)
        return items, path_map

    def move_library_to(self, newloc, progress=lambda x: x):
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs = set([])
        items, path_map = self.get_top_level_move_items()
        for x in items:
            src = os.path.join(self.library_path, x)
            dest = os.path.join(newloc, path_map[x])
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                old_dirs.add(src)
            else:
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.copyfile(src, dest)
            x = path_map[x]
            if not isinstance(x, unicode):
                x = x.decode(filesystem_encoding, 'replace')
            progress(x)

        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        opath = self.dbpath
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        self.connect()
        try:
            os.unlink(opath)
        except:
            pass
        for dir in old_dirs:
            try:
                shutil.rmtree(dir)
            except:
                pass

    def __iter__(self):
        for record in self.data._data:
            if record is not None:
                yield record

    def all_ids(self):
        x = self.FIELD_MAP['id']
        for i in iter(self):
            yield i[x]

    def get_data_as_dict(self, prefix=None, authors_as_string=False, ids=None):
        '''
        Return all metadata stored in the database as a dict. Includes paths to
        the cover and each format.

        :param prefix: The prefix for all paths. By default, the prefix is the absolute path
        to the library folder.
        :param ids: Set of ids to return the data for. If None return data for
        all entries in database.
        '''
        if prefix is None:
            prefix = self.library_path
        fdata = self.custom_column_num_map

        FIELDS = set(['title', 'sort', 'authors', 'author_sort', 'publisher',
            'rating', 'timestamp', 'size', 'tags', 'comments', 'series',
            'series_index', 'uuid', 'pubdate', 'last_modified', 'identifiers',
            'languages']).union(set(fdata))
        for x, data in fdata.iteritems():
            if data['datatype'] == 'series':
                FIELDS.add('%d_index'%x)
        data = []
        for record in self.data:
            if record is None: continue
            db_id = record[self.FIELD_MAP['id']]
            if ids is not None and db_id not in ids:
                continue
            x = {}
            for field in FIELDS:
                x[field] = record[self.FIELD_MAP[field]]
            data.append(x)
            x['id'] = db_id
            x['formats'] = []
            isbn = self.isbn(db_id, index_is_id=True)
            x['isbn'] = isbn if isbn else ''
            if not x['authors']:
                x['authors'] = _('Unknown')
            x['authors'] = [i.replace('|', ',') for i in x['authors'].split(',')]
            if authors_as_string:
                x['authors'] = authors_to_string(x['authors'])
            x['tags'] = [i.replace('|', ',').strip() for i in x['tags'].split(',')] if x['tags'] else []
            path = os.path.join(prefix, self.path(record[self.FIELD_MAP['id']], index_is_id=True))
            x['cover'] = os.path.join(path, 'cover.jpg')
            if not record[self.FIELD_MAP['cover']]:
                x['cover'] = None
            formats = self.formats(record[self.FIELD_MAP['id']], index_is_id=True)
            if formats:
                for fmt in formats.split(','):
                    path = self.format_abspath(x['id'], fmt, index_is_id=True)
                    if path is None:
                        continue
                    if prefix != self.library_path:
                        path = os.path.relpath(path, self.library_path)
                        path = os.path.join(prefix, path)
                    x['formats'].append(path)
                    x['fmt_'+fmt.lower()] = path
                x['available_formats'] = [i.upper() for i in formats.split(',')]

        return data

    def migrate_old(self, db, progress):
        from PyQt4.QtCore import QCoreApplication
        header = _(u'<p>Migrating old database to ebook library in %s<br><center>')%self.library_path
        progress.setValue(0)
        progress.setLabelText(header)
        QCoreApplication.processEvents()
        db.conn.row_factory = lambda cursor, row : tuple(row)
        db.conn.text_factory = lambda x : unicode(x, 'utf-8', 'replace')
        books = db.conn.get('SELECT id, title, sort, timestamp, series_index, author_sort, isbn FROM books ORDER BY id ASC')
        progress.setAutoReset(False)
        progress.setRange(0, len(books))

        for book in books:
            self.conn.execute('INSERT INTO books(id, title, sort, timestamp, series_index, author_sort, isbn) VALUES(?, ?, ?, ?, ?, ?, ?, ?);', book)

        tables = '''
authors  ratings      tags    series    books_tags_link
comments               publishers
books_authors_link     conversion_options
books_publishers_link
books_ratings_link
books_series_link      feeds
'''.split()
        for table in tables:
            rows = db.conn.get('SELECT * FROM %s ORDER BY id ASC'%table)
            for row in rows:
                self.conn.execute('INSERT INTO %s VALUES(%s)'%(table, ','.join(repeat('?', len(row)))), row)

        self.conn.commit()
        self.refresh('timestamp', True)
        for i, book in enumerate(books):
            progress.setLabelText(header+_(u'Copying <b>%s</b>')%book[1])
            id = book[0]
            self.set_path(id, True)
            formats = db.formats(id, index_is_id=True)
            if not formats:
                formats = []
            else:
                formats = formats.split(',')
            for format in formats:
                data = db.format(id, format, index_is_id=True)
                if data:
                    self.add_format(id, format, cStringIO.StringIO(data), index_is_id=True)
            cover = db.cover(id, index_is_id=True)
            if cover:
                self.set_cover(id, cover)
            progress.setValue(i+1)
        self.conn.commit()
        progress.setLabelText(_('Compacting database'))
        self.vacuum()
        progress.reset()
        return len(books)

    def find_books_in_directory(self, dirpath, single_book_per_directory):
        dirpath = os.path.abspath(dirpath)
        if single_book_per_directory:
            formats = []
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS and ext != 'opf':
                    continue
                formats.append(path)
            yield formats
        else:
            books = {}
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS:
                    continue

                key = os.path.splitext(path)[0]
                if not books.has_key(key):
                    books[key] = []
                books[key].append(path)

            for formats in books.values():
                yield formats

    def import_book_directory_multiple(self, dirpath, callback=None,
            added_ids=None):
        from calibre.ebooks.metadata.meta import metadata_from_formats

        duplicates = []
        for formats in self.find_books_in_directory(dirpath, False):
            mi = metadata_from_formats(formats)
            if mi.title is None:
                continue
            if self.has_book(mi):
                duplicates.append((mi, formats))
                continue
            book_id = self.import_book(mi, formats)
            if added_ids is not None:
                added_ids.add(book_id)
            if callable(callback):
                if callback(mi.title):
                    break
        return duplicates

    def import_book_directory(self, dirpath, callback=None, added_ids=None):
        from calibre.ebooks.metadata.meta import metadata_from_formats
        dirpath = os.path.abspath(dirpath)
        formats = self.find_books_in_directory(dirpath, True)
        formats = list(formats)[0]
        if not formats:
            return
        mi = metadata_from_formats(formats)
        if mi.title is None:
            return
        if self.has_book(mi):
            return [(mi, formats)]
        book_id = self.import_book(mi, formats)
        if added_ids is not None:
            added_ids.add(book_id)
        if callable(callback):
            callback(mi.title)

    def recursive_import(self, root, single_book_per_directory=True,
            callback=None, added_ids=None):
        root = os.path.abspath(root)
        duplicates  = []
        for dirpath in os.walk(root):
            res = (self.import_book_directory(dirpath[0], callback=callback,
                added_ids=added_ids) if single_book_per_directory else
                self.import_book_directory_multiple(dirpath[0],
                    callback=callback, added_ids=added_ids))
            if res is not None:
                duplicates.extend(res)
            if callable(callback):
                if callback(''):
                    break
        return duplicates

    def add_custom_book_data(self, book_id, name, val):
        x = self.conn.get('SELECT id FROM books WHERE ID=?', (book_id,), all=False)
        if x is None:
            raise ValueError('add_custom_book_data: no such book_id %d'%book_id)
        # Do the json encode first, in case it throws an exception
        s = json.dumps(val, default=to_json)
        self.conn.execute('''INSERT OR REPLACE INTO books_plugin_data(book, name, val)
                             VALUES(?, ?, ?)''', (book_id, name, s))
        self.commit()

    def add_multiple_custom_book_data(self, name, vals, delete_first=False):
        if delete_first:
            self.conn.execute('DELETE FROM books_plugin_data WHERE name=?', (name, ))
        self.conn.executemany(
            'INSERT OR REPLACE INTO books_plugin_data (book, name, val) VALUES (?, ?, ?)',
            [(book_id, name, json.dumps(val, default=to_json))
                    for book_id, val in vals.iteritems()])
        self.commit()

    def get_custom_book_data(self, book_id, name, default=None):
        try:
            s = self.conn.get('''select val FROM books_plugin_data
                    WHERE book=? AND name=?''', (book_id, name), all=False)
            if s is None:
                return default
            return json.loads(s, object_hook=from_json)
        except:
            pass
        return default

    def get_all_custom_book_data(self, name, default=None):
        try:
            s = self.conn.get('''select book, val FROM books_plugin_data
                    WHERE name=?''', (name,))
            if s is None:
                return default
            res = {}
            for r in s:
                res[r[0]] = json.loads(r[1], object_hook=from_json)
            return res
        except:
            pass
        return default

    def delete_custom_book_data(self, book_id, name):
        self.conn.execute('DELETE FROM books_plugin_data WHERE book=? AND name=?',
                          (book_id, name))
        self.commit()

    def delete_all_custom_book_data(self, name):
        self.conn.execute('DELETE FROM books_plugin_data WHERE name=?', (name, ))
        self.commit()

    def get_ids_for_custom_book_data(self, name):
        s = self.conn.get('''SELECT book FROM books_plugin_data WHERE name=?''', (name,))
        return [x[0] for x in s]

    def get_usage_count_by_id(self, field):
        fm = self.field_metadata[field]
        if not fm.get('link_column', None):
            raise ValueError('%s is not an is_multiple field')
        return self.conn.get(
            'SELECT {0}, count(*) FROM books_{1}_link GROUP BY {0}'.format(
                fm['link_column'], fm['table']))


