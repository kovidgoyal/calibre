#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil, functools, re, os, traceback
from contextlib import closing
from operator import attrgetter

from PyQt4.Qt import QAbstractTableModel, Qt, pyqtSignal, QIcon, QImage, \
        QModelIndex, QVariant, QDate

from calibre.gui2 import NONE, config, UNDEFINED_QDATE, FunctionDispatcher
from calibre.utils.pyparsing import ParseException
from calibre.ebooks.metadata import fmt_sidx, authors_to_string, string_to_authors
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import tweaks, prefs
from calibre.utils.date import dt_factory, qt_to_dt, isoformat
from calibre.ebooks.metadata.meta import set_metadata as _set_metadata
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, \
    REGEXP_MATCH, CoverCache, MetadataBackup
from calibre.library.cli import parse_series_string
from calibre import strftime, isbytestring, prepare_string_for_xml
from calibre.constants import filesystem_encoding
from calibre.gui2.library import DEFAULT_SORT

def human_readable(size, precision=1):
    """ Convert a size in bytes into megabytes """
    return ('%.'+str(precision)+'f') % ((size/(1024.*1024.)),)

TIME_FMT = '%d %b %Y'

ALIGNMENT_MAP = {'left': Qt.AlignLeft, 'right': Qt.AlignRight, 'center':
        Qt.AlignHCenter}

class FormatPath(unicode):

    def __new__(cls, path, orig_file_path):
        ans = unicode.__new__(cls, path)
        ans.orig_file_path = orig_file_path
        ans.deleted_after_upload = False
        return ans

_default_image = None

def default_image():
    global _default_image
    if _default_image is None:
        _default_image = QImage(I('default_cover.png'))
    return _default_image

class BooksModel(QAbstractTableModel): # {{{

    about_to_be_sorted   = pyqtSignal(object, name='aboutToBeSorted')
    sorting_done         = pyqtSignal(object, name='sortingDone')
    database_changed     = pyqtSignal(object, name='databaseChanged')
    new_bookdisplay_data = pyqtSignal(object)
    count_changed_signal = pyqtSignal(int)
    searched             = pyqtSignal(object)

    orig_headers = {
                        'title'     : _("Title"),
                        'ondevice'   : _("On Device"),
                        'authors'   : _("Author(s)"),
                        'size'      : _("Size (MB)"),
                        'timestamp' : _("Date"),
                        'pubdate'   : _('Published'),
                        'rating'    : _('Rating'),
                        'publisher' : _("Publisher"),
                        'tags'      : _("Tags"),
                        'series'    : _("Series"),
    }

    def __init__(self, parent=None, buffer=40):
        QAbstractTableModel.__init__(self, parent)
        self.db = None
        self.book_on_device = None
        self.editable_cols = ['title', 'authors', 'rating', 'publisher',
                              'tags', 'series', 'timestamp', 'pubdate']
        self.default_image = default_image()
        self.sorted_on = DEFAULT_SORT
        self.sort_history = [self.sorted_on]
        self.last_search = '' # The last search performed on this model
        self.column_map = []
        self.headers = {}
        self.alignment_map = {}
        self.buffer_size = buffer
        self.cover_cache = None
        self.metadata_backup = None
        self.bool_yes_icon = QIcon(I('ok.png'))
        self.bool_no_icon = QIcon(I('list_remove.png'))
        self.bool_blank_icon = QIcon(I('blank.png'))
        self.device_connected = False
        self.read_config()

    def change_alignment(self, colname, alignment):
        if colname in self.column_map and alignment in ('left', 'right', 'center'):
            old = self.alignment_map.get(colname, 'left')
            if old == alignment:
                return
            self.alignment_map.pop(colname, None)
            if alignment != 'left':
                self.alignment_map[colname] = alignment
            col = self.column_map.index(colname)
            for row in xrange(self.rowCount(QModelIndex())):
                self.dataChanged.emit(self.index(row, col), self.index(row,
                    col))

    def is_custom_column(self, cc_label):
        return cc_label in self.custom_columns

    def clear_caches(self):
        if self.cover_cache:
            self.cover_cache.clear_cache()

    def read_config(self):
        self.use_roman_numbers = config['use_roman_numerals_for_series_number']

    def set_device_connected(self, is_connected):
        self.device_connected = is_connected
        self.refresh_ondevice()

    def refresh_ondevice(self):
        self.db.refresh_ondevice()
        self.refresh() # does a resort()
        self.research()

    def set_book_on_device_func(self, func):
        self.book_on_device = func

    def set_database(self, db):
        self.db = db
        self.custom_columns = self.db.field_metadata.custom_field_metadata()
        self.column_map = list(self.orig_headers.keys()) + \
                          list(self.custom_columns)
        def col_idx(name):
            if name == 'ondevice':
                return -1
            if name not in self.db.field_metadata:
                return 100000
            return self.db.field_metadata[name]['rec_index']

        self.column_map.sort(cmp=lambda x,y: cmp(col_idx(x), col_idx(y)))
        for col in self.column_map:
            if col in self.orig_headers:
                self.headers[col] = self.orig_headers[col]
            elif col in self.custom_columns:
                self.headers[col] = self.custom_columns[col]['name']

        self.build_data_convertors()
        self.reset()
        self.database_changed.emit(db)
        if self.cover_cache is not None:
            self.cover_cache.stop()
            # Would like to to a join here, but the thread might be waiting to
            # do something on the GUI thread. Deadlock.
        self.cover_cache = CoverCache(db, FunctionDispatcher(self.db.cover))
        self.cover_cache.start()
        self.stop_metadata_backup()
        self.start_metadata_backup()
        def refresh_cover(event, ids):
            if event == 'cover' and self.cover_cache is not None:
                self.cover_cache.refresh(ids)
        db.add_listener(refresh_cover)

    def start_metadata_backup(self):
        self.metadata_backup = MetadataBackup(self.db)
        self.metadata_backup.start()

    def stop_metadata_backup(self):
        if getattr(self, 'metadata_backup', None) is not None:
            self.metadata_backup.stop()
            # Would like to to a join here, but the thread might be waiting to
            # do something on the GUI thread. Deadlock.


    def refresh_ids(self, ids, current_row=-1):
        rows = self.db.refresh_ids(ids)
        if rows:
            self.refresh_rows(rows, current_row=current_row)

    def refresh_rows(self, rows, current_row=-1):
        for row in rows:
            if row == current_row:
                self.new_bookdisplay_data.emit(
                          self.get_book_display_info(row))
            self.dataChanged.emit(self.index(row, 0), self.index(row,
                self.columnCount(QModelIndex())-1))

    def close(self):
        self.db.close()
        self.db = None
        self.reset()

    def add_books(self, paths, formats, metadata, add_duplicates=False):
        ret = self.db.add_books(paths, formats, metadata,
                                 add_duplicates=add_duplicates)
        self.count_changed()
        return ret

    def add_news(self, path, arg):
        ret = self.db.add_news(path, arg)
        self.count_changed()
        return ret

    def add_catalog(self, path, title):
        ret = self.db.add_catalog(path, title)
        self.count_changed()
        return ret

    def count_changed(self, *args):
        self.count_changed_signal.emit(self.db.count())

    def row_indices(self, index):
        ''' Return list indices of all cells in index.row()'''
        return [ self.index(index.row(), c) for c in range(self.columnCount(None))]

    @property
    def by_author(self):
        return self.sorted_on[0] == 'authors'

    def delete_books(self, indices):
        ids = map(self.id, indices)
        for id in ids:
            self.db.delete_book(id, notify=False)
        self.count_changed()
        self.clear_caches()
        self.reset()
        return ids

    def delete_books_by_id(self, ids):
        for id in ids:
            try:
                row = self.db.row(id)
            except:
                row = -1
            if row > -1:
                self.beginRemoveRows(QModelIndex(), row, row)
            self.db.delete_book(id)
            if row > -1:
                self.endRemoveRows()
        self.count_changed()
        self.clear_caches()

    def books_added(self, num):
        if num > 0:
            self.beginInsertRows(QModelIndex(), 0, num-1)
            self.endInsertRows()
            self.count_changed()

    def search(self, text, reset=True):
        try:
            self.db.search(text)
        except ParseException as e:
            self.searched.emit(e.msg)
            return
        self.last_search = text
        if reset:
            self.clear_caches()
            self.reset()
        if self.last_search:
            # Do not issue search done for the null search. It is used to clear
            # the search and count records for restrictions
            self.searched.emit(True)

    def sort(self, col, order, reset=True):
        if not self.db:
            return
        self.about_to_be_sorted.emit(self.db.id)
        ascending = order == Qt.AscendingOrder
        label = self.column_map[col]
        self.db.sort(label, ascending)
        if reset:
            self.clear_caches()
            self.reset()
        self.sorted_on = (label, order)
        self.sort_history.insert(0, self.sorted_on)
        self.sorting_done.emit(self.db.index)

    def refresh(self, reset=True):
        self.db.refresh(field=None)
        self.resort(reset=reset)

    def resort(self, reset=True):
        if not self.db:
            return
        self.db.multisort(self.sort_history[:tweaks['maximum_resort_levels']])
        if reset:
            self.reset()

    def research(self, reset=True):
        self.search(self.last_search, reset=reset)

    def columnCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.column_map)

    def rowCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.db.data) if self.db else 0

    def count(self):
        return self.rowCount(None)

    def get_book_display_info(self, idx):
        data = {}
        cdata = self.cover(idx)
        if cdata:
            data['cover'] = cdata
        tags = self.db.tags(idx)
        if tags:
            tags = tags.replace(',', ', ')
        else:
            tags = _('None')
        data[_('Tags')] = tags
        formats = self.db.formats(idx)
        if formats:
            formats = formats.replace(',', ', ')
        else:
            formats = _('None')
        data[_('Formats')] = formats
        data[_('Path')] = self.db.abspath(idx)
        data['id'] = self.id(idx)
        comments = self.db.comments(idx)
        if not comments:
            comments = _('None')
        data[_('Comments')] = comments
        series = self.db.series(idx)
        if series:
            sidx = self.db.series_index(idx)
            sidx = fmt_sidx(sidx, use_roman = self.use_roman_numbers)
            data[_('Series')] = \
                _('Book <font face="serif">%s</font> of %s.')%\
                    (sidx, prepare_string_for_xml(series))
        mi = self.db.get_metadata(idx)
        for key in mi.custom_field_keys():
            name, val = mi.format_field(key)
            if val:
                data[name] = val
        return data

    def set_cache(self, idx):
        l, r = 0, self.count()-1
        if self.cover_cache is not None:
            l = max(l, idx-self.buffer_size)
            r = min(r, idx+self.buffer_size)
            k = min(r-idx, idx-l)
            ids = [idx]
            for i in range(1, k):
                ids.extend([idx-i, idx+i])
            ids = ids + [i for i in range(l, r, 1) if i not in ids]
            try:
                ids = [self.db.id(i) for i in ids]
            except IndexError:
                return
            self.cover_cache.set_cache(ids)

    def current_changed(self, current, previous, emit_signal=True):
        if current.isValid():
            idx = current.row()
            self.set_cache(idx)
            data = self.get_book_display_info(idx)
            if emit_signal:
                self.new_bookdisplay_data.emit(data)
            else:
                return data

    def get_book_info(self, index):
        if isinstance(index, int):
            index = self.index(index, 0)
        data = self.current_changed(index, None, False)
        row = index.row()
        data[_('Title')] = self.db.title(row)
        au = self.db.authors(row)
        if not au:
            au = _('Unknown')
        au = ', '.join([a.strip() for a in au.split(',')])
        data[_('Author(s)')] = au
        return data

    def metadata_for(self, ids):
        ans = []
        for id in ids:
            mi = self.db.get_metadata(id, index_is_id=True, get_cover=True)
            ans.append(mi)
        return ans

    def get_metadata(self, rows, rows_are_ids=False, full_metadata=False):
        metadata, _full_metadata = [], []
        if not rows_are_ids:
            rows = [self.db.id(row.row()) for row in rows]
        for id in rows:
            mi = self.db.get_metadata(id, index_is_id=True)
            _full_metadata.append(mi)
            au = authors_to_string(mi.authors if mi.authors else [_('Unknown')])
            tags = mi.tags if mi.tags else []
            if mi.series is not None:
                tags.append(mi.series)
            info = {
                  'title'   : mi.title,
                  'authors' : au,
                  'author_sort' : mi.author_sort,
                  'cover'   : self.db.cover(id, index_is_id=True),
                  'tags'    : tags,
                  'comments': mi.comments,
                  }
            if mi.series is not None:
                info['tag order'] = {
                    mi.series:self.db.books_in_series_of(id, index_is_id=True)
                }

            metadata.append(info)
        if full_metadata:
            return metadata, _full_metadata
        else:
            return metadata

    def get_preferred_formats_from_ids(self, ids, formats,
                              set_metadata=False, specific_format=None,
                              exclude_auto=False, mode='r+b'):
        ans = []
        need_auto = []
        if specific_format is not None:
            formats = [specific_format.lower()]
        for id in ids:
            format = None
            fmts = self.db.formats(id, index_is_id=True)
            if not fmts:
                fmts = ''
            db_formats = set(fmts.lower().split(','))
            available_formats = set([f.lower() for f in formats])
            u = available_formats.intersection(db_formats)
            for f in formats:
                if f.lower() in u:
                    format = f
                    break
            if format is not None:
                pt = PersistentTemporaryFile(suffix='.'+format)
                with closing(self.db.format(id, format, index_is_id=True,
                    as_file=True)) as src:
                    shutil.copyfileobj(src, pt)
                    pt.flush()
                    if getattr(src, 'name', None):
                        pt.orig_file_path = os.path.abspath(src.name)
                pt.seek(0)
                if set_metadata:
                    try:
                        _set_metadata(pt, self.db.get_metadata(id, get_cover=True, index_is_id=True),
                                  format)
                    except:
                        traceback.print_exc()
                pt.close()
                def to_uni(x):
                    if isbytestring(x):
                        x = x.decode(filesystem_encoding)
                    return x
                name, op = map(to_uni, map(os.path.abspath, (pt.name,
                    pt.orig_file_path)))
                ans.append(FormatPath(name, op))
            else:
                need_auto.append(id)
                if not exclude_auto:
                    ans.append(None)
        return ans, need_auto

    def get_preferred_formats(self, rows, formats, paths=False,
                              set_metadata=False, specific_format=None,
                              exclude_auto=False):
        ans = []
        need_auto = []
        if specific_format is not None:
            formats = [specific_format.lower()]
        for row in (row.row() for row in rows):
            format = None
            fmts = self.db.formats(row)
            if not fmts:
                fmts = ''
            db_formats = set(fmts.lower().split(','))
            available_formats = set([f.lower() for f in formats])
            u = available_formats.intersection(db_formats)
            for f in formats:
                if f.lower() in u:
                    format = f
                    break
            if format is not None:
                pt = PersistentTemporaryFile(suffix='.'+format)
                with closing(self.db.format(row, format, as_file=True)) as src:
                    shutil.copyfileobj(src, pt)
                    pt.flush()
                pt.seek(0)
                if set_metadata:
                    _set_metadata(pt, self.db.get_metadata(row, get_cover=True),
                                  format)
                pt.close() if paths else pt.seek(0)
                ans.append(pt)
            else:
                need_auto.append(row)
                if not exclude_auto:
                    ans.append(None)
        return ans, need_auto

    def id(self, row):
        return self.db.id(getattr(row, 'row', lambda:row)())

    def title(self, row_number):
        return self.db.title(row_number)

    def rating(self, row_number):
        ans = self.db.rating(row_number)
        ans = ans/2 if ans else 0
        return int(ans)

    def cover(self, row_number):
        data = None
        try:
            id = self.db.id(row_number)
            if self.cover_cache is not None:
                img = self.cover_cache.cover(id)
                if not img.isNull():
                    return img
            if not data:
                data = self.db.cover(row_number)
        except IndexError: # Happens if database has not yet been refreshed
            pass

        if not data:
            return self.default_image
        img = QImage()
        img.loadFromData(data)
        if img.isNull():
            img = self.default_image
        return img


    def build_data_convertors(self):
        def authors(r, idx=-1):
            au = self.db.data[r][idx]
            if au:
                au = [a.strip().replace('|', ',') for a in au.split(',')]
                return QVariant(' & '.join(au))
            else:
                return None

        def tags(r, idx=-1):
            tags = self.db.data[r][idx]
            if tags:
                return QVariant(', '.join(sorted(tags.split(','))))
            return None

        def series_type(r, idx=-1, siix=-1):
            series = self.db.data[r][idx]
            if series:
                idx = fmt_sidx(self.db.data[r][siix])
                return QVariant(series + ' [%s]'%idx)
            return None

        def size(r, idx=-1):
            size = self.db.data[r][idx]
            if size:
                return QVariant('%.1f'%(float(size)/(1024*1024)))
            return None

        def rating_type(r, idx=-1):
            r = self.db.data[r][idx]
            r = r/2 if r else 0
            return QVariant(r)

        def datetime_type(r, idx=-1):
            val = self.db.data[r][idx]
            if val is not None:
                return QVariant(QDate(val))
            else:
                return QVariant(UNDEFINED_QDATE)

        def bool_type(r, idx=-1):
            return None # displayed using a decorator

        def bool_type_decorator(r, idx=-1, bool_cols_are_tristate=True):
            val = self.db.data[r][idx]
            if not bool_cols_are_tristate:
                if val is None or not val:
                    return self.bool_no_icon
            if val:
                return self.bool_yes_icon
            if val is None:
                return self.bool_blank_icon
            return self.bool_no_icon

        def ondevice_decorator(r, idx=-1):
            text = self.db.data[r][idx]
            if text:
                return self.bool_yes_icon
            return self.bool_blank_icon

        def text_type(r, mult=False, idx=-1):
            text = self.db.data[r][idx]
            if text and mult:
                return QVariant(', '.join(sorted(text.split('|'))))
            return QVariant(text)

        def number_type(r, idx=-1):
            return QVariant(self.db.data[r][idx])

        self.dc = {
                   'title'    : functools.partial(text_type,
                                idx=self.db.field_metadata['title']['rec_index'], mult=False),
                   'authors'  : functools.partial(authors,
                                idx=self.db.field_metadata['authors']['rec_index']),
                   'size'     : functools.partial(size,
                                idx=self.db.field_metadata['size']['rec_index']),
                   'timestamp': functools.partial(datetime_type,
                                idx=self.db.field_metadata['timestamp']['rec_index']),
                   'pubdate'  : functools.partial(datetime_type,
                                idx=self.db.field_metadata['pubdate']['rec_index']),
                   'rating'   : functools.partial(rating_type,
                                idx=self.db.field_metadata['rating']['rec_index']),
                   'publisher': functools.partial(text_type,
                                idx=self.db.field_metadata['publisher']['rec_index'], mult=False),
                   'tags'     : functools.partial(tags,
                                idx=self.db.field_metadata['tags']['rec_index']),
                   'series'   : functools.partial(series_type,
                                idx=self.db.field_metadata['series']['rec_index'],
                                siix=self.db.field_metadata['series_index']['rec_index']),
                   'ondevice' : functools.partial(text_type,
                                idx=self.db.field_metadata['ondevice']['rec_index'], mult=False),
                   }

        self.dc_decorator = {
                'ondevice':functools.partial(ondevice_decorator,
                    idx=self.db.field_metadata['ondevice']['rec_index']),
                    }

        # Add the custom columns to the data converters
        for col in self.custom_columns:
            idx = self.custom_columns[col]['rec_index']
            datatype = self.custom_columns[col]['datatype']
            if datatype in ('text', 'comments', 'composite'):
                self.dc[col] = functools.partial(text_type, idx=idx,
                                                 mult=self.custom_columns[col]['is_multiple'])
            elif datatype in ('int', 'float'):
                self.dc[col] = functools.partial(number_type, idx=idx)
            elif datatype == 'datetime':
                self.dc[col] = functools.partial(datetime_type, idx=idx)
            elif datatype == 'bool':
                self.dc[col] = functools.partial(bool_type, idx=idx)
                self.dc_decorator[col] = functools.partial(
                            bool_type_decorator, idx=idx,
                            bool_cols_are_tristate=tweaks['bool_custom_columns_are_tristate'] == 'yes')
            elif datatype == 'rating':
                self.dc[col] = functools.partial(rating_type, idx=idx)
            elif datatype == 'series':
                self.dc[col] = functools.partial(series_type, idx=idx,
                    siix=self.db.field_metadata.cc_series_index_column_for(col))
            else:
                print 'What type is this?', col, datatype
        # build a index column to data converter map, to remove the string lookup in the data loop
        self.column_to_dc_map = []
        self.column_to_dc_decorator_map = []
        for col in self.column_map:
            self.column_to_dc_map.append(self.dc[col])
            self.column_to_dc_decorator_map.append(self.dc_decorator.get(col, None))

    def data(self, index, role):
        col = index.column()
        # in obscure cases where custom columns are both edited and added, for a time
        # the column map does not accurately represent the screen. In these cases,
        # we will get asked to display columns we don't know about. Must test for this.
        if col >= len(self.column_to_dc_map):
            return NONE
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self.column_to_dc_map[col](index.row())
        elif role == Qt.DecorationRole:
            if self.column_to_dc_decorator_map[col] is not None:
                return self.column_to_dc_decorator_map[index.column()](index.row())
        elif role == Qt.TextAlignmentRole:
            cname = self.column_map[index.column()]
            ans = Qt.AlignVCenter | ALIGNMENT_MAP[self.alignment_map.get(cname,
                'left')]
            return QVariant(ans)
        #elif role == Qt.ToolTipRole and index.isValid():
        #    if self.column_map[index.column()] in self.editable_cols:
        #        return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        return NONE

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal:
            if section >= len(self.column_map): # same problem as in data, the column_map can be wrong
                return None
            if role == Qt.ToolTipRole:
                ht = self.column_map[section]
                if ht == 'timestamp': # change help text because users know this field as 'date'
                    ht = 'date'
                return QVariant(_('The lookup/search name is "{0}"').format(ht))
            if role == Qt.DisplayRole:
                return QVariant(self.headers[self.column_map[section]])
            return NONE
        if role == Qt.DisplayRole: # orientation is vertical
            return QVariant(section+1)
        return NONE


    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            colhead = self.column_map[index.column()]
            if colhead in self.editable_cols:
                flags |= Qt.ItemIsEditable
            elif self.is_custom_column(colhead):
                if self.custom_columns[colhead]['is_editable']:
                    flags |= Qt.ItemIsEditable
        return flags

    def set_custom_column_data(self, row, colhead, value):
        cc = self.custom_columns[colhead]
        typ = cc['datatype']
        label=self.db.field_metadata.key_to_label(colhead)
        s_index = None
        if typ in ('text', 'comments'):
            val = unicode(value.toString()).strip()
            val = val if val else None
        if typ == 'bool':
            val = value.toPyObject()
        elif typ == 'rating':
            val = value.toInt()[0]
            val = 0 if val < 0 else 5 if val > 5 else val
            val *= 2
        elif typ in ('int', 'float'):
            val = unicode(value.toString()).strip()
            if val is None or not val:
                val = None
        elif typ == 'datetime':
            val = value.toDate()
            if val.isNull():
                val = None
            else:
                if not val.isValid():
                    return False
                val = qt_to_dt(val, as_utc=False)
        elif typ == 'series':
            val, s_index = parse_series_string(self.db, label, value.toString())
        elif typ == 'composite':
            tmpl = unicode(value.toString()).strip()
            disp = cc['display']
            disp['composite_template'] = tmpl
            self.db.set_custom_column_metadata(cc['colnum'], display = disp)
            self.refresh(reset=True)
            return True

        id = self.db.id(row)
        self.db.set_custom(id, val, extra=s_index,
                           label=label, num=None, append=False, notify=True)
        self.refresh_ids([id], current_row=row)
        return True

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            row, col = index.row(), index.column()
            column = self.column_map[col]
            if self.is_custom_column(column):
                if not self.set_custom_column_data(row, column, value):
                    return False
            else:
                if column not in self.editable_cols:
                    return False
                val = int(value.toInt()[0]) if column == 'rating' else \
                      value.toDate() if column in ('timestamp', 'pubdate') else \
                      unicode(value.toString())
                id = self.db.id(row)
                if column == 'rating':
                    val = 0 if val < 0 else 5 if val > 5 else val
                    val *= 2
                    self.db.set_rating(id, val)
                elif column == 'series':
                    val = val.strip()
                    pat = re.compile(r'\[([.0-9]+)\]')
                    match = pat.search(val)
                    if match is not None:
                        self.db.set_series_index(id, float(match.group(1)))
                        val = pat.sub('', val).strip()
                    elif val:
                        if tweaks['series_index_auto_increment'] == 'next':
                            ni = self.db.get_next_series_num_for(val)
                            if ni != 1:
                                self.db.set_series_index(id, ni)
                    if val:
                        self.db.set_series(id, val)
                elif column == 'timestamp':
                    if val.isNull() or not val.isValid():
                        return False
                    self.db.set_timestamp(id, qt_to_dt(val, as_utc=False))
                elif column == 'pubdate':
                    if val.isNull() or not val.isValid():
                        return False
                    self.db.set_pubdate(id, qt_to_dt(val, as_utc=False))
                else:
                    self.db.set(row, column, val)
                self.refresh_ids([id], row)
            self.dataChanged.emit(index, index)
        return True

    def set_search_restriction(self, s):
        self.db.data.set_search_restriction(s)
        self.search('')
        return self.rowCount(None)

# }}}

class OnDeviceSearch(SearchQueryParser): # {{{

    USABLE_LOCATIONS = [
        'all',
        'author',
        'authors',
        'collections',
        'format',
        'formats',
        'title',
        'inlibrary'
    ]


    def __init__(self, model):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.model = model

    def universal_set(self):
        return set(range(0, len(self.model.db)))

    def get_matches(self, location, query):
        location = location.lower().strip()
        if location == 'authors':
            location = 'author'

        matchkind = CONTAINS_MATCH
        if len(query) > 1:
            if query.startswith('\\'):
                query = query[1:]
            elif query.startswith('='):
                matchkind = EQUALS_MATCH
                query = query[1:]
            elif query.startswith('~'):
                matchkind = REGEXP_MATCH
                query = query[1:]
        if matchkind != REGEXP_MATCH: ### leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set([])
        matches = set([])
        all_locs = set(self.USABLE_LOCATIONS) - set(['all'])
        locations = all_locs if location == 'all' else [location]
        q = {
             'title' : lambda x : getattr(x, 'title').lower(),
             'author': lambda x: ' & '.join(getattr(x, 'authors')).lower(),
             'collections':lambda x: ','.join(getattr(x, 'device_collections')).lower(),
             'format':lambda x: os.path.splitext(x.path)[1].lower(),
             'inlibrary':lambda x : getattr(x, 'in_library')
             }
        for x in ('author', 'format'):
            q[x+'s'] = q[x]
        for index, row in enumerate(self.model.db):
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if accessor(row) is not None:
                        matches.add(index)
                    continue
                if query == 'false':
                    if accessor(row) is None:
                        matches.add(index)
                    continue
                if locvalue == 'inlibrary':
                    continue    # this is bool, so can't match below
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'collections':
                        vals = accessor(row).split(',')
                    else:
                        vals = [accessor(row)]
                    if _match(query, vals, m):
                        matches.add(index)
                        break
                except ValueError: # Unicode errors
                    traceback.print_exc()
        return matches

# }}}

class DeviceBooksModel(BooksModel): # {{{

    booklist_dirtied = pyqtSignal()
    upload_collections = pyqtSignal(object)

    def __init__(self, parent):
        BooksModel.__init__(self, parent)
        self.db  = []
        self.map = []
        self.sorted_map = []
        self.sorted_on = DEFAULT_SORT
        self.sort_history = [self.sorted_on]
        self.unknown = _('Unknown')
        self.column_map = ['inlibrary', 'title', 'authors', 'timestamp', 'size',
                'collections']
        self.headers = {
                'inlibrary'   : _('In Library'),
                'title'       : _('Title'),
                'authors'     : _('Author(s)'),
                'timestamp'   : _('Date'),
                'size'        : _('Size'),
                'collections' : _('Collections')
                }
        self.marked_for_deletion = {}
        self.search_engine = OnDeviceSearch(self)
        self.editable = ['title', 'authors', 'collections']
        self.book_in_library = None

    def mark_for_deletion(self, job, rows, rows_are_ids=False):
        if rows_are_ids:
            self.marked_for_deletion[job] = rows
            self.reset()
        else:
            self.marked_for_deletion[job] = self.indices(rows)
            for row in rows:
                indices = self.row_indices(row)
                self.dataChanged.emit(indices[0], indices[-1])

    def deletion_done(self, job, succeeded=True):
        if not self.marked_for_deletion.has_key(job):
            return
        rows = self.marked_for_deletion.pop(job)
        for row in rows:
            if not succeeded:
                indices = self.row_indices(self.index(row, 0))
                self.dataChanged.emit(indices[0], indices[-1])

    def paths_deleted(self, paths):
        self.map = list(range(0, len(self.db)))
        self.resort(False)
        self.research(True)

    def indices_to_be_deleted(self):
        ans = []
        for v in self.marked_for_deletion.values():
            ans.extend(v)
        return ans

    def clear_ondevice(self, db_ids, to_what=None):
        for data in self.db:
            if data is None:
                continue
            app_id = getattr(data, 'application_id', None)
            if app_id is not None and app_id in db_ids:
                data.in_library = to_what
            self.reset()

    def flags(self, index):
        if self.map[index.row()] in self.indices_to_be_deleted():
            return Qt.ItemIsUserCheckable  # Can't figure out how to get the disabled flag in python
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            cname = self.column_map[index.column()]
            if cname in self.editable and \
                     (cname != 'collections' or \
                     (callable(getattr(self.db, 'supports_collections', None)) and \
                      self.db.supports_collections() and \
                      prefs['manage_device_metadata']=='manual')):
                flags |= Qt.ItemIsEditable
        return flags

    def search(self, text, reset=True):
        if not text or not text.strip():
            self.map = list(range(len(self.db)))
        else:
            try:
                matches = self.search_engine.parse(text)
            except ParseException:
                self.searched.emit(False)
                return

            self.map = []
            for i in range(len(self.db)):
                if i in matches:
                    self.map.append(i)
        self.resort(reset=False)
        if reset:
            self.reset()
        self.last_search = text
        if self.last_search:
            self.searched.emit(True)


    def sort(self, col, order, reset=True):
        descending = order != Qt.AscendingOrder
        def strcmp(attr):
            ag = attrgetter(attr)
            def _strcmp(x, y):
                x = ag(self.db[x])
                y = ag(self.db[y])
                if x == None:
                    x = ''
                if y == None:
                    y = ''
                x, y = x.strip().lower(), y.strip().lower()
                return cmp(x, y)
            return _strcmp
        def datecmp(x, y):
            x = self.db[x].datetime
            y = self.db[y].datetime
            return cmp(dt_factory(x, assume_utc=True), dt_factory(y,
                assume_utc=True))
        def sizecmp(x, y):
            x, y = int(self.db[x].size), int(self.db[y].size)
            return cmp(x, y)
        def tagscmp(x, y):
            x = ','.join(sorted(getattr(self.db[x], 'device_collections', []))).lower()
            y = ','.join(sorted(getattr(self.db[y], 'device_collections', []))).lower()
            return cmp(x, y)
        def libcmp(x, y):
            x, y = self.db[x].in_library, self.db[y].in_library
            return cmp(x, y)
        def authorcmp(x, y):
            ax = getattr(self.db[x], 'author_sort', None)
            ay = getattr(self.db[y], 'author_sort', None)
            if ax and ay:
                x = ax
                y = ay
            else:
                x, y = authors_to_string(self.db[x].authors), \
                                authors_to_string(self.db[y].authors)
            return cmp(x, y)
        cname = self.column_map[col]
        fcmp = {
                'title': strcmp('title_sorter'),
                'authors' : authorcmp,
                'size' : sizecmp,
                'timestamp': datecmp,
                'collections': tagscmp,
                'inlibrary': libcmp,
                }[cname]
        self.map.sort(cmp=fcmp, reverse=descending)
        if len(self.map) == len(self.db):
            self.sorted_map = list(self.map)
        else:
            self.sorted_map = list(range(len(self.db)))
            self.sorted_map.sort(cmp=fcmp, reverse=descending)
        self.sorted_on = (self.column_map[col], order)
        self.sort_history.insert(0, self.sorted_on)
        if reset:
            self.reset()

    def resort(self, reset=True):
        if self.sorted_on:
            self.sort(self.column_map.index(self.sorted_on[0]),
                      self.sorted_on[1], reset=False)
        if reset:
            self.reset()

    def columnCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.column_map)

    def rowCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.map)

    def set_database(self, db):
        self.custom_columns = {}
        self.db = db
        self.map = list(range(0, len(db)))

    def cover(self, row):
        item = self.db[self.map[row]]
        cdata = item.thumbnail
        img = QImage()
        if cdata is not None:
            if hasattr(cdata, 'image_path'):
                img.load(cdata.image_path)
            elif cdata:
                if isinstance(cdata, (tuple, list)):
                    img.loadFromData(cdata[-1])
                else:
                    img.loadFromData(cdata)
        if img.isNull():
            img = self.default_image
        return img

    def current_changed(self, current, previous):
        data = {}
        item = self.db[self.map[current.row()]]
        cover = self.cover(current.row())
        if cover is not self.default_image:
            data['cover'] = cover
        type = _('Unknown')
        ext = os.path.splitext(item.path)[1]
        if ext:
            type = ext[1:].lower()
        data[_('Format')] = type
        data[_('Path')] = item.path
        dt = dt_factory(item.datetime, assume_utc=True)
        data[_('Timestamp')] = isoformat(dt, sep=' ', as_utc=False)
        data[_('Collections')] = ', '.join(item.device_collections)

        tags = getattr(item, 'tags', None)
        if tags:
            tags = u', '.join(tags)
        else:
            tags = _('None')
        data[_('Tags')] = tags
        comments = getattr(item, 'comments', None)
        if not comments:
            comments = _('None')
        data[_('Comments')] = comments
        series = getattr(item, 'series', None)
        if series:
            sidx = getattr(item, 'series_index', 0)
            sidx = fmt_sidx(sidx, use_roman = self.use_roman_numbers)
            data[_('Series')] = _('Book <font face="serif">%s</font> of %s.')%(sidx, series)

        self.new_bookdisplay_data.emit(data)

    def paths(self, rows):
        return [self.db[self.map[r.row()]].path for r in rows ]

    def paths_for_db_ids(self, db_ids):
        res = []
        for r,b in enumerate(self.db):
            if b.application_id in db_ids:
                res.append((r,b))
        return res

    def get_collections_with_ids(self):
        collections = set()
        for book in self.db:
            if book.device_collections is not None:
                collections.update(set(book.device_collections))
        self.collections = []
        result = []
        for i,collection in enumerate(collections):
            result.append((i, collection))
            self.collections.append(collection)
        return result

    def rename_collection(self, old_id, new_name):
        old_name = self.collections[old_id]
        for book in self.db:
            if book.device_collections is None:
                continue
            if old_name in book.device_collections:
                book.device_collections.remove(old_name)
                if new_name not in book.device_collections:
                    book.device_collections.append(new_name)

    def delete_collection_using_id(self, old_id):
        old_name = self.collections[old_id]
        for book in self.db:
            if book.device_collections is None:
                continue
            if old_name in book.device_collections:
                book.device_collections.remove(old_name)

    def indices(self, rows):
        '''
        Return indices into underlying database from rows
        '''
        return [self.map[r.row()] for r in rows]

    def data(self, index, role):
        row, col = index.row(), index.column()
        cname = self.column_map[col]
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if cname == 'title':
                text = self.db[self.map[row]].title
                if not text:
                    text = self.unknown
                return QVariant(text)
            elif cname == 'authors':
                au = self.db[self.map[row]].authors
                if not au:
                    au = self.unknown
                return QVariant(authors_to_string(au))
            elif cname == 'size':
                size = self.db[self.map[row]].size
                return QVariant(human_readable(size))
            elif cname == 'timestamp':
                dt = self.db[self.map[row]].datetime
                dt = dt_factory(dt, assume_utc=True, as_utc=False)
                return QVariant(strftime(TIME_FMT, dt.timetuple()))
            elif cname == 'collections':
                tags = self.db[self.map[row]].device_collections
                if tags:
                    tags.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))
                    return QVariant(', '.join(tags))
        elif role == Qt.ToolTipRole and index.isValid():
            if self.map[row] in self.indices_to_be_deleted():
                return QVariant(_('Marked for deletion'))
            if cname in ['title', 'authors'] or (cname == 'collections' and \
                    self.db.supports_collections()):
                return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        elif role == Qt.DecorationRole and cname == 'inlibrary':
            if self.db[self.map[row]].in_library:
                return QVariant(self.bool_yes_icon)
            elif self.db[self.map[row]].in_library is not None:
                return QVariant(self.bool_no_icon)
        elif role == Qt.TextAlignmentRole:
            cname = self.column_map[index.column()]
            ans = Qt.AlignVCenter | ALIGNMENT_MAP[self.alignment_map.get(cname,
                'left')]
            return QVariant(ans)


        return NONE

    def headerData(self, section, orientation, role):
        if role == Qt.ToolTipRole:
            return QVariant(_('The lookup/search name is "{0}"').format(self.column_map[section]))
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:
            cname = self.column_map[section]
            text = self.headers[cname]
            return QVariant(text)
        else:
            return QVariant(section+1)

    def setData(self, index, value, role):
        done = False
        if role == Qt.EditRole:
            row, col = index.row(), index.column()
            cname = self.column_map[col]
            if cname in ('size', 'timestamp', 'inlibrary'):
                return False
            val = unicode(value.toString()).strip()
            idx = self.map[row]
            if cname == 'collections':
                tags = [i.strip() for i in val.split(',')]
                tags = [t for t in tags if t]
                self.db[idx].device_collections = tags
                self.dataChanged.emit(index, index)
                self.upload_collections.emit(self.db)
                return True

            if cname == 'title' :
                self.db[idx].title = val
            elif cname == 'authors':
                self.db[idx].authors = string_to_authors(val)
            self.dataChanged.emit(index, index)
            self.booklist_dirtied.emit()
            done = True
        return done

    def set_editable(self, editable):
        # Cannot edit if metadata is sent on connect. Reason: changes will
        # revert to what is in the library on next connect.
        if isinstance(editable, list):
            self.editable = editable
        elif editable:
            self.editable = ['title', 'authors', 'collections']
        else:
            self.editable = []
        if prefs['manage_device_metadata']=='on_connect':
            self.editable = []

    def set_search_restriction(self, s):
        pass

# }}}

