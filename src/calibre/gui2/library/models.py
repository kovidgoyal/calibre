#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools, re, os, traceback, errno, time
from collections import defaultdict

from PyQt4.Qt import (QAbstractTableModel, Qt, pyqtSignal, QIcon, QImage,
        QModelIndex, QVariant, QDateTime, QColor, QPixmap, QFont)

from calibre.gui2 import NONE, UNDEFINED_QDATETIME, error_dialog
from calibre.utils.search_query_parser import ParseException
from calibre.ebooks.metadata import fmt_sidx, authors_to_string, string_to_authors
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import tweaks, device_prefs, prefs
from calibre.utils.date import dt_factory, qt_to_dt, as_local_time
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.db.search import _match, CONTAINS_MATCH, EQUALS_MATCH, REGEXP_MATCH
from calibre.library.caches import (MetadataBackup, force_to_bool)
from calibre.library.save_to_disk import find_plugboard
from calibre import strftime, isbytestring
from calibre.constants import filesystem_encoding, DEBUG, config_dir
from calibre.gui2.library import DEFAULT_SORT
from calibre.utils.localization import calibre_langcode_to_name
from calibre.library.coloring import color_row_key

def human_readable(size, precision=1):
    """ Convert a size in bytes into megabytes """
    return ('%.'+str(precision)+'f') % ((size/(1024.*1024.)),)

TIME_FMT = '%d %b %Y'

ALIGNMENT_MAP = {'left': Qt.AlignLeft, 'right': Qt.AlignRight, 'center':
        Qt.AlignHCenter}

_default_image = None

def default_image():
    global _default_image
    if _default_image is None:
        _default_image = QImage(I('default_cover.png'))
    return _default_image

class ColumnColor(object):

    def __init__(self, formatter, colors):
        self.mi = None
        self.formatter = formatter
        self.colors = colors

    def __call__(self, id_, key, fmt, db, color_cache):
        if id_ in color_cache and key in color_cache[id_]:
            self.mi = None
            return color_cache[id_][key]
        try:
            if self.mi is None:
                self.mi = db.get_metadata(id_, index_is_id=True)
            color = self.formatter.safe_format(fmt, self.mi, '', self.mi)
            if color in self.colors:
                color = QColor(color)
                if color.isValid():
                    color = QVariant(color)
                    color_cache[id_][key] = color
                    self.mi = None
                    return color
        except:
            pass


class ColumnIcon(object):

    def __init__(self, formatter):
        self.mi = None
        self.formatter = formatter

    def __call__(self, id_, key, fmt, kind, db, icon_cache, icon_bitmap_cache):
        dex = key+kind
        if id_ in icon_cache and dex in icon_cache[id_]:
            self.mi = None
            return icon_cache[id_][dex]
        try:
            if self.mi is None:
                self.mi = db.get_metadata(id_, index_is_id=True)
            icon = self.formatter.safe_format(fmt, self.mi, '', self.mi)
            if icon:
                if icon in icon_bitmap_cache:
                    icon_bitmap = icon_bitmap_cache[icon]
                    icon_cache[id_][dex] = icon_bitmap
                    return icon_bitmap
                d = os.path.join(config_dir, 'cc_icons', icon)
                if (os.path.exists(d)):
                    icon_bitmap = QPixmap(d)
                    h = icon_bitmap.height()
                    w = icon_bitmap.width()
                    # If the image is landscape and width is more than 50%
                    # large than height, use the pixmap. This tells Qt to display
                    # the image full width. It might be clipped to row height.
                    if w < (3 * h)/2:
                        icon_bitmap = QIcon(icon_bitmap)
                    icon_cache[id_][dex] = icon_bitmap
                    icon_bitmap_cache[icon] = icon_bitmap
                    self.mi = None
                    return icon_bitmap
        except:
            pass

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
                        'series'    : ngettext("Series", 'Series', 1),
                        'last_modified' : _('Modified'),
                        'languages' : _('Languages'),
    }

    def __init__(self, parent=None, buffer=40):
        QAbstractTableModel.__init__(self, parent)
        self.db = None

        self.formatter = SafeFormat()
        self.colors = frozenset([unicode(c) for c in QColor.colorNames()])
        self._clear_caches()
        self.column_color = ColumnColor(self.formatter, self.colors)
        self.column_icon = ColumnIcon(self.formatter)

        self.book_on_device = None
        self.editable_cols = ['title', 'authors', 'rating', 'publisher',
                              'tags', 'series', 'timestamp', 'pubdate',
                              'languages']
        self.default_image = default_image()
        self.sorted_on = DEFAULT_SORT
        self.sort_history = [self.sorted_on]
        self.last_search = '' # The last search performed on this model
        self.column_map = []
        self.headers = {}
        self.alignment_map = {}
        self.buffer_size = buffer
        self.metadata_backup = None
        self.bool_yes_icon = QIcon(I('ok.png'))
        self.bool_no_icon = QIcon(I('list_remove.png'))
        self.bool_blank_icon = QIcon(I('blank.png'))
        self.device_connected = False
        self.ids_to_highlight = []
        self.ids_to_highlight_set = set()
        self.current_highlighted_idx = None
        self.highlight_only = False
        self.current_index_column = -1
        self.current_index_row = -1
        self.selected_header_font = QFont()
        self.selected_header_font.setBold(True)
        self.selected_header_font.setItalic(True)

        self.read_config()

    def _clear_caches(self):
        self.color_cache = defaultdict(dict)
        self.icon_cache = defaultdict(dict)
        self.icon_bitmap_cache = {}
        self.color_row_fmt_cache = None

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

    def read_config(self):
        pass

    def set_device_connected(self, is_connected):
        self.device_connected = is_connected

    def refresh_ondevice(self):
        self.db.refresh_ondevice()
        self.resort()
        self.research()

    def set_book_on_device_func(self, func):
        self.book_on_device = func

    def set_database(self, db):
        self.ids_to_highlight = []
        self.ids_to_highlight_set = set()
        self.current_highlighted_idx = None
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
        self.stop_metadata_backup()
        self.start_metadata_backup()

    def start_metadata_backup(self):
        self.metadata_backup = MetadataBackup(self.db)
        self.metadata_backup.start()

    def stop_metadata_backup(self):
        if getattr(self, 'metadata_backup', None) is not None:
            self.metadata_backup.stop()
            # Would like to to a join here, but the thread might be waiting to
            # do something on the GUI thread. Deadlock.


    def refresh_ids(self, ids, current_row=-1):
        self._clear_caches()
        rows = self.db.refresh_ids(ids)
        if rows:
            self.refresh_rows(rows, current_row=current_row)

    def refresh_rows(self, rows, current_row=-1):
        self._clear_caches()
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

    def add_books(self, paths, formats, metadata, add_duplicates=False,
            return_ids=False):
        ret = self.db.add_books(paths, formats, metadata,
                add_duplicates=add_duplicates, return_ids=return_ids)
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
        self._clear_caches()
        self.count_changed_signal.emit(self.db.count())

    def row_indices(self, index):
        ''' Return list indices of all cells in index.row()'''
        return [ self.index(index.row(), c) for c in range(self.columnCount(None))]

    @property
    def by_author(self):
        return self.sorted_on[0] == 'authors'

    def books_deleted(self):
        self.count_changed()
        self.reset()

    def delete_books(self, indices, permanent=False):
        ids = map(self.id, indices)
        self.delete_books_by_id(ids, permanent=permanent)
        return ids

    def delete_books_by_id(self, ids, permanent=False):
        for id in ids:
            self.db.delete_book(id, permanent=permanent, do_clean=False)
        self.db.clean()
        self.books_deleted()

    def books_added(self, num):
        if num > 0:
            self.beginInsertRows(QModelIndex(), 0, num-1)
            self.endInsertRows()
            self.count_changed()

    def set_highlight_only(self, toWhat):
        self.highlight_only = toWhat

    def get_current_highlighted_id(self):
        if len(self.ids_to_highlight) == 0 or self.current_highlighted_idx is None:
            return None
        try:
            return self.ids_to_highlight[self.current_highlighted_idx]
        except:
            return None

    def get_next_highlighted_id(self, current_row, forward):
        if len(self.ids_to_highlight) == 0 or self.current_highlighted_idx is None:
            return None
        if current_row is None:
            row_ = self.current_highlighted_idx
        else:
            row_ = current_row
        while True:
            row_ += 1 if forward else -1
            if row_ < 0:
                row_ = self.count() - 1;
            elif row_ >= self.count():
                row_ = 0
            if self.id(row_) in self.ids_to_highlight_set:
                break
        try:
            self.current_highlighted_idx = self.ids_to_highlight.index(self.id(row_))
        except:
            # This shouldn't happen ...
            return None
        return self.get_current_highlighted_id()

    def highlight_ids(self, ids_to_highlight):
        self.ids_to_highlight = ids_to_highlight
        self.ids_to_highlight_set = set(self.ids_to_highlight)
        if self.ids_to_highlight:
            self.current_highlighted_idx = 0
        else:
            self.current_highlighted_idx = None
        self.reset()

    def search(self, text, reset=True):
        try:
            if self.highlight_only:
                self.db.search('')
                if not text:
                    self.ids_to_highlight = []
                    self.ids_to_highlight_set = set()
                    self.current_highlighted_idx = None
                else:
                    self.ids_to_highlight = self.db.search(text, return_matches=True)
                    self.ids_to_highlight_set = set(self.ids_to_highlight)
                    if self.ids_to_highlight:
                        self.current_highlighted_idx = 0
                    else:
                        self.current_highlighted_idx = None
            else:
                self.ids_to_highlight = []
                self.ids_to_highlight_set = set()
                self.current_highlighted_idx = None
                self.db.search(text)
        except ParseException as e:
            self.searched.emit(e.msg)
            return
        self.last_search = text
        if reset:
            self.reset()
        if self.last_search:
            # Do not issue search done for the null search. It is used to clear
            # the search and count records for restrictions
            self.searched.emit(True)

    def sort(self, col, order, reset=True):
        if not self.db:
            return
        if not isinstance(order, bool):
            order = order == Qt.AscendingOrder
        label = self.column_map[col]
        self._sort(label, order, reset)

    def sort_by_named_field(self, field, order, reset=True):
        if field in self.db.field_metadata.keys():
            self._sort(field, order, reset)

    def _sort(self, label, order, reset):
        self.about_to_be_sorted.emit(self.db.id)
        self.db.sort(label, order)
        if reset:
            self.reset()
        self.sorted_on = (label, order)
        self.sort_history.insert(0, self.sorted_on)
        self.sorting_done.emit(self.db.index)

    def refresh(self, reset=True):
        self.db.refresh(field=None)
        self.resort(reset=reset)

    def reset(self):
        self._clear_caches()
        QAbstractTableModel.reset(self)

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
        mi = self.db.get_metadata(idx)
        mi.size = mi.book_size
        mi.cover_data = ('jpg', self.cover(idx))
        mi.id = self.db.id(idx)
        mi.field_metadata = self.db.field_metadata
        mi.path = self.db.abspath(idx, create_dirs=False)
        return mi

    def current_changed(self, current, previous, emit_signal=True):
        if current.isValid():
            idx = current.row()
            data = self.get_book_display_info(idx)
            if emit_signal:
                self.new_bookdisplay_data.emit(data)
            else:
                return data

    def get_book_info(self, index):
        if isinstance(index, int):
            index = self.index(index, 0)
        # If index is not valid returns None
        data = self.current_changed(index, None, False)
        return data

    def metadata_for(self, ids, get_cover=True):
        '''
        WARNING: if get_cover=True temp files are created for mi.cover.
        Remember to delete them once you are done with them.
        '''
        ans = []
        for id in ids:
            mi = self.db.get_metadata(id, index_is_id=True, get_cover=get_cover)
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
                              exclude_auto=False, mode='r+b',
                              use_plugboard=None, plugboard_formats=None):
        from calibre.ebooks.metadata.meta import set_metadata as _set_metadata
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
                pt = PersistentTemporaryFile(suffix='caltmpfmt.'+format)
                self.db.copy_format_to(id, format, pt, index_is_id=True)
                pt.seek(0)
                if set_metadata:
                    try:
                        mi = self.db.get_metadata(id, get_cover=True,
                                                  index_is_id=True,
                                                  cover_as_data=True)
                        newmi = None
                        if use_plugboard and format.lower() in plugboard_formats:
                            plugboards = self.db.prefs.get('plugboards', {})
                            cpb = find_plugboard(use_plugboard, format.lower(),
                                                 plugboards)
                            if cpb:
                                newmi = mi.deepcopy_metadata()
                                newmi.template_to_attribute(mi, cpb)
                        if newmi is not None:
                            _set_metadata(pt, newmi, format)
                        else:
                            _set_metadata(pt, mi, format)
                    except:
                        traceback.print_exc()
                pt.close()
                def to_uni(x):
                    if isbytestring(x):
                        x = x.decode(filesystem_encoding)
                    return x
                ans.append(to_uni(os.path.abspath(pt.name)))
            else:
                need_auto.append(id)
                if not exclude_auto:
                    ans.append(None)
        return ans, need_auto

    def get_preferred_formats(self, rows, formats, paths=False,
                              set_metadata=False, specific_format=None,
                              exclude_auto=False):
        from calibre.ebooks.metadata.meta import set_metadata as _set_metadata
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
                self.db.copy_format_to(id, format, pt, index_is_id=True)
                pt.seek(0)
                if set_metadata:
                    _set_metadata(pt, self.db.get_metadata(row, get_cover=True,
                        cover_as_data=True), format)
                pt.close() if paths else pt.seek(0)
                ans.append(pt)
            else:
                need_auto.append(row)
                if not exclude_auto:
                    ans.append(None)
        return ans, need_auto

    def id(self, row):
        return self.db.id(getattr(row, 'row', lambda:row)())

    def authors(self, row_number):
        return self.db.authors(row_number)

    def title(self, row_number):
        return self.db.title(row_number)

    def rating(self, row_number):
        ans = self.db.rating(row_number)
        ans = ans/2 if ans else 0
        return int(ans)

    def cover(self, row_number):
        data = None
        try:
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

        def languages(r, idx=-1):
            lc = self.db.data[r][idx]
            if lc:
                langs = [calibre_langcode_to_name(l.strip()) for l in lc.split(',')]
                return QVariant(', '.join(langs))
            return None

        def tags(r, idx=-1):
            tags = self.db.data[r][idx]
            if tags:
                return QVariant(', '.join(sorted(tags.split(','), key=sort_key)))
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
                ans = '%.1f'%(float(size)/(1024*1024))
                if size > 0 and ans == '0.0':
                    ans = '<0.1'
                return QVariant(ans)
            return None

        def rating_type(r, idx=-1):
            r = self.db.data[r][idx]
            r = r/2.0 if r else 0
            return QVariant(int(r))

        def datetime_type(r, idx=-1):
            val = self.db.data[r][idx]
            if val is not None:
                return QVariant(QDateTime(as_local_time(val)))
            else:
                return QVariant(UNDEFINED_QDATETIME)

        def bool_type(r, idx=-1):
            return None # displayed using a decorator

        def bool_type_decorator(r, idx=-1, bool_cols_are_tristate=True):
            val = force_to_bool(self.db.data[r][idx])
            if val is None:
                if not bool_cols_are_tristate:
                    return self.bool_no_icon
                return NONE
            if val:
                return self.bool_yes_icon
            return self.bool_no_icon

        def ondevice_decorator(r, idx=-1):
            text = self.db.data[r][idx]
            if text:
                return self.bool_yes_icon
            return self.bool_blank_icon

        def text_type(r, mult=None, idx=-1):
            text = self.db.data[r][idx]
            if text and mult:
                jv = mult['list_to_ui']
                sv = mult['cache_to_list']
                return QVariant(jv.join(
                    sorted([t.strip() for t in text.split(sv)], key=sort_key)))
            return QVariant(text)

        def decorated_text_type(r, idx=-1):
            text = self.db.data[r][idx]
            if force_to_bool(text) is not None:
                return None
            return QVariant(text)

        def number_type(r, idx=-1, fmt=None):
            if fmt is not None:
                try:
                    return QVariant(fmt.format(self.db.data[r][idx]))
                except:
                    pass
            return QVariant(self.db.data[r][idx])

        self.dc = {
                   'title'    : functools.partial(text_type,
                                idx=self.db.field_metadata['title']['rec_index'], mult=None),
                   'authors'  : functools.partial(authors,
                                idx=self.db.field_metadata['authors']['rec_index']),
                   'size'     : functools.partial(size,
                                idx=self.db.field_metadata['size']['rec_index']),
                   'timestamp': functools.partial(datetime_type,
                                idx=self.db.field_metadata['timestamp']['rec_index']),
                   'pubdate'  : functools.partial(datetime_type,
                                idx=self.db.field_metadata['pubdate']['rec_index']),
                   'last_modified': functools.partial(datetime_type,
                                idx=self.db.field_metadata['last_modified']['rec_index']),
                   'rating'   : functools.partial(rating_type,
                                idx=self.db.field_metadata['rating']['rec_index']),
                   'publisher': functools.partial(text_type,
                                idx=self.db.field_metadata['publisher']['rec_index'], mult=None),
                   'tags'     : functools.partial(tags,
                                idx=self.db.field_metadata['tags']['rec_index']),
                   'series'   : functools.partial(series_type,
                                idx=self.db.field_metadata['series']['rec_index'],
                                siix=self.db.field_metadata['series_index']['rec_index']),
                   'ondevice' : functools.partial(text_type,
                                idx=self.db.field_metadata['ondevice']['rec_index'], mult=None),
                   'languages': functools.partial(languages,
                                idx=self.db.field_metadata['languages']['rec_index']),
                   }

        self.dc_decorator = {
                'ondevice':functools.partial(ondevice_decorator,
                    idx=self.db.field_metadata['ondevice']['rec_index']),
                    }

        # Add the custom columns to the data converters
        for col in self.custom_columns:
            idx = self.custom_columns[col]['rec_index']
            datatype = self.custom_columns[col]['datatype']
            if datatype in ('text', 'comments', 'composite', 'enumeration'):
                mult=self.custom_columns[col]['is_multiple']
                self.dc[col] = functools.partial(text_type, idx=idx, mult=mult)
                if datatype in ['text', 'composite', 'enumeration'] and not mult:
                    if self.custom_columns[col]['display'].get('use_decorations', False):
                        self.dc[col] = functools.partial(decorated_text_type, idx=idx)
                        self.dc_decorator[col] = functools.partial(
                            bool_type_decorator, idx=idx,
                            bool_cols_are_tristate=
                                self.db.prefs.get('bools_are_tristate'))
            elif datatype in ('int', 'float'):
                fmt = self.custom_columns[col]['display'].get('number_format', None)
                self.dc[col] = functools.partial(number_type, idx=idx, fmt=fmt)
            elif datatype == 'datetime':
                self.dc[col] = functools.partial(datetime_type, idx=idx)
            elif datatype == 'bool':
                self.dc[col] = functools.partial(bool_type, idx=idx)
                self.dc_decorator[col] = functools.partial(
                            bool_type_decorator, idx=idx,
                            bool_cols_are_tristate=
                                self.db.prefs.get('bools_are_tristate'))
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
        if role == Qt.DisplayRole:
            rules = self.db.prefs['column_icon_rules']
            if rules:
                key = self.column_map[col]
                id_ = None
                for kind, k, fmt in rules:
                    if k == key and kind == 'icon_only':
                        if id_ is None:
                            id_ = self.id(index)
                            self.column_icon.mi = None
                        ccicon = self.column_icon(id_, key, fmt, 'icon_only', self.db,
                                              self.icon_cache, self.icon_bitmap_cache)
                        if ccicon is not None:
                            return NONE
                self.icon_cache[id_][key+'icon_only'] = None
            return self.column_to_dc_map[col](index.row())
        elif role in (Qt.EditRole, Qt.ToolTipRole):
            return self.column_to_dc_map[col](index.row())
        elif role == Qt.BackgroundRole:
            if self.id(index) in self.ids_to_highlight_set:
                return QVariant(QColor('lightgreen'))
        elif role == Qt.ForegroundRole:
            key = self.column_map[col]
            id_ = self.id(index)
            self.column_color.mi = None

            if self.color_row_fmt_cache is None:
                self.color_row_fmt_cache = tuple(fmt for key, fmt in
                    self.db.prefs['column_color_rules'] if key == color_row_key)

            for k, fmt in self.db.prefs['column_color_rules']:
                if k == key:
                    ccol = self.column_color(id_, key, fmt, self.db,
                                             self.color_cache)
                    if ccol is not None:
                        return ccol

            if self.is_custom_column(key) and \
                        self.custom_columns[key]['datatype'] == 'enumeration':
                cc = self.custom_columns[self.column_map[col]]['display']
                colors = cc.get('enum_colors', [])
                values = cc.get('enum_values', [])
                txt = unicode(index.data(Qt.DisplayRole).toString())
                if len(colors) > 0 and txt in values:
                    try:
                        color = QColor(colors[values.index(txt)])
                        if color.isValid():
                            self.column_color.mi = None
                            return QVariant(color)
                    except:
                        pass

            for fmt in self.color_row_fmt_cache:
                ccol = self.column_color(id_, color_row_key, fmt, self.db,
                                         self.color_cache)
                if ccol is not None:
                    return ccol

            self.column_color.mi = None
            return NONE
        elif role == Qt.DecorationRole:
            if self.column_to_dc_decorator_map[col] is not None:
                ccicon = self.column_to_dc_decorator_map[index.column()](index.row())
                if ccicon != NONE:
                    return ccicon

            rules = self.db.prefs['column_icon_rules']
            if rules:
                key = self.column_map[col]
                id_ = None
                need_icon_with_text = False
                for kind, k, fmt in rules:
                    if k == key and kind in ('icon', 'icon_only'):
                        if id_ is None:
                            id_ = self.id(index)
                            self.column_icon.mi = None
                        if kind == 'icon':
                            need_icon_with_text = True
                        ccicon = self.column_icon(id_, key, fmt, kind, self.db,
                                          self.icon_cache, self.icon_bitmap_cache)
                        if ccicon is not None:
                            return ccicon
                if need_icon_with_text:
                    self.icon_cache[id_][key+'icon'] = self.bool_blank_icon
                    return self.bool_blank_icon
                self.icon_cache[id_][key+'icon'] = None
        elif role == Qt.TextAlignmentRole:
            cname = self.column_map[index.column()]
            ans = Qt.AlignVCenter | ALIGNMENT_MAP[self.alignment_map.get(cname,
                'left')]
            return QVariant(ans)
        #elif role == Qt.ToolTipRole and index.isValid():
        #    if self.column_map[index.column()] in self.editable_cols:
        #        return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        return NONE

    def set_current_cell(self, idx):
        if idx and idx.isValid():
            # Copy these out here for performance, avoiding using idx in headerData
            self.current_index_column = idx.column()
            self.current_index_row = idx.row()
        else:
            self.current_index_column = -1
            self.current_index_row = -1

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
            if role == Qt.FontRole and self.current_index_column == section:
                return QVariant(self.selected_header_font)
            return NONE
        if DEBUG and role == Qt.ToolTipRole and orientation == Qt.Vertical:
                col = self.db.field_metadata['uuid']['rec_index']
                return QVariant(_('This book\'s UUID is "{0}"').format(self.db.data[section][col]))

        if role == Qt.DisplayRole: # orientation is vertical
            return QVariant(section+1)
        if role == Qt.FontRole and self.current_index_row == section:
            return QVariant(self.selected_header_font)
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
        elif typ == 'enumeration':
            val = unicode(value.toString()).strip()
            if not val:
                val = None
        elif typ == 'bool':
            val = value.toPyObject()
        elif typ == 'rating':
            val = value.toInt()[0]
            val = 0 if val < 0 else 5 if val > 5 else val
            val *= 2
        elif typ in ('int', 'float'):
            val = unicode(value.toString()).strip()
            if not val:
                val = None
        elif typ == 'datetime':
            val = value.toDateTime()
            if val.isNull():
                val = None
            else:
                if not val.isValid():
                    return False
                val = qt_to_dt(val, as_utc=False)
        elif typ == 'series':
            val = unicode(value.toString()).strip()
            if val:
                pat = re.compile(r'\[([.0-9]+)\]')
                match = pat.search(val)
                if match is not None:
                    s_index = float(match.group(1))
                    val = pat.sub('', val).strip()
                elif val:
                    # it is OK to leave s_index == None when using 'no_change'
                    if tweaks['series_index_auto_increment'] != 'const' and \
                            tweaks['series_index_auto_increment'] != 'no_change':
                        s_index = self.db.get_next_cc_series_num_for(val,
                                                        label=label, num=None)
        elif typ == 'composite':
            tmpl = unicode(value.toString()).strip()
            disp = cc['display']
            disp['composite_template'] = tmpl
            self.db.set_custom_column_metadata(cc['colnum'], display = disp)
            self.refresh(reset=True)
            return True

        id = self.db.id(row)
        books_to_refresh = set([id])
        books_to_refresh |= self.db.set_custom(id, val, extra=s_index,
                           label=label, num=None, append=False, notify=True)
        self.refresh_ids(list(books_to_refresh), current_row=row)
        return True

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            from calibre.gui2.ui import get_gui
            try:
                return self._set_data(index, value)
            except (IOError, OSError) as err:
                import traceback
                if getattr(err, 'errno', None) == errno.EACCES: # Permission denied
                    fname = getattr(err, 'filename', None)
                    p = 'Locked file: %s\n\n'%fname if fname else ''
                    error_dialog(get_gui(), _('Permission denied'),
                            _('Could not change the on disk location of this'
                                ' book. Is it open in another program?'),
                            det_msg=p+traceback.format_exc(), show=True)
                    return False
                error_dialog(get_gui(), _('Failed to set data'),
                        _('Could not set data, click Show Details to see why.'),
                        det_msg=traceback.format_exc(), show=True)
            except:
                import traceback
                traceback.print_exc()
                error_dialog(get_gui(), _('Failed to set data'),
                        _('Could not set data, click Show Details to see why.'),
                        det_msg=traceback.format_exc(), show=True)
        return False

    def _set_data(self, index, value):
        row, col = index.row(), index.column()
        column = self.column_map[col]
        if self.is_custom_column(column):
            if not self.set_custom_column_data(row, column, value):
                return False
        else:
            if column not in self.editable_cols:
                return False
            val = (int(value.toInt()[0]) if column == 'rating' else
                    value.toDateTime() if column in ('timestamp', 'pubdate')
                    else unicode(value.toString()).strip())
            id = self.db.id(row)
            books_to_refresh = set([id])
            if column == 'rating':
                val = 0 if val < 0 else 5 if val > 5 else val
                val *= 2
                self.db.set_rating(id, val)
            elif column == 'series':
                val = val.strip()
                if not val:
                    books_to_refresh |= self.db.set_series(id, val,
                                                    allow_case_change=True)
                    self.db.set_series_index(id, 1.0)
                else:
                    pat = re.compile(r'\[([.0-9]+)\]')
                    match = pat.search(val)
                    if match is not None:
                        self.db.set_series_index(id, float(match.group(1)))
                        val = pat.sub('', val).strip()
                    elif val:
                        if tweaks['series_index_auto_increment'] != 'const' and \
                            tweaks['series_index_auto_increment'] != 'no_change':
                            ni = self.db.get_next_series_num_for(val)
                            if ni != 1:
                                self.db.set_series_index(id, ni)
                    if val:
                        books_to_refresh |= self.db.set_series(id, val,
                                                    allow_case_change=True)
            elif column == 'timestamp':
                if val.isNull() or not val.isValid():
                    return False
                self.db.set_timestamp(id, qt_to_dt(val, as_utc=False))
            elif column == 'pubdate':
                if val.isNull() or not val.isValid():
                    return False
                self.db.set_pubdate(id, qt_to_dt(val, as_utc=False))
            elif column == 'languages':
                val = val.split(',')
                self.db.set_languages(id, val)
            else:
                books_to_refresh |= self.db.set(row, column, val,
                                                allow_case_change=True)
            self.refresh_ids(list(books_to_refresh), row)
        self.dataChanged.emit(index, index)
        return True

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
        upf = prefs['use_primary_find_in_search']
        for index, row in enumerate(self.model.db):
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if accessor(row):
                        matches.add(index)
                    continue
                if query == 'false':
                    if not accessor(row):
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
                    if _match(query, vals, m, use_primary_find_in_search=upf):
                        matches.add(index)
                        break
                except ValueError: # Unicode errors
                    traceback.print_exc()
        return matches

# }}}

class DeviceDBSortKeyGen(object): # {{{

    def __init__(self, attr, keyfunc, db):
        self.attr = attr
        self.db = db
        self.keyfunc = keyfunc

    def __call__(self, x):
        try:
            ans = self.keyfunc(getattr(self.db[x], self.attr))
        except:
            ans = None
        return ans
# }}}

class DeviceBooksModel(BooksModel): # {{{

    booklist_dirtied = pyqtSignal()
    upload_collections = pyqtSignal(object)
    resize_rows = pyqtSignal()

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
        db_indices = rows if rows_are_ids else self.indices(rows)
        db_items = [self.db[i] for i in db_indices if -1 < i < len(self.db)]
        self.marked_for_deletion[job] = db_items
        if rows_are_ids:
            self.reset()
        else:
            for row in rows:
                indices = self.row_indices(row)
                self.dataChanged.emit(indices[0], indices[-1])

    def find_item_in_db(self, item):
        idx = None
        try:
            idx = self.db.index(item)
        except:
            path = getattr(item, 'path', None)
            if path:
                for i, x in enumerate(self.db):
                    if getattr(x, 'path', None) == path:
                        idx = i
                        break
        return idx

    def deletion_done(self, job, succeeded=True):
        db_items = self.marked_for_deletion.pop(job, [])
        rows = []
        for item in db_items:
            idx = self.find_item_in_db(item)
            if idx is not None:
                try:
                    rows.append(self.map.index(idx))
                except ValueError:
                    pass

        for row in rows:
            if not succeeded:
                indices = self.row_indices(self.index(row, 0))
                self.dataChanged.emit(indices[0], indices[-1])

    def paths_deleted(self, paths):
        self.map = list(range(0, len(self.db)))
        self.resort(False)
        self.research(True)

    def is_row_marked_for_deletion(self, row):
        try:
            item = self.db[self.map[row]]
        except IndexError:
            return False

        path = getattr(item, 'path', None)
        for items in self.marked_for_deletion.itervalues():
            for x in items:
                if x is item or (path and path == getattr(x, 'path', None)):
                    return True
        return False

    def clear_ondevice(self, db_ids, to_what=None):
        for data in self.db:
            if data is None:
                continue
            app_id = getattr(data, 'application_id', None)
            if app_id is not None and app_id in db_ids:
                data.in_library = to_what
            self.reset()

    def flags(self, index):
        if self.is_row_marked_for_deletion(index.row()):
            return Qt.NoItemFlags
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            cname = self.column_map[index.column()]
            if cname in self.editable and \
                     (cname != 'collections' or \
                     (callable(getattr(self.db, 'supports_collections', None)) and \
                      self.db.supports_collections() and \
                      device_prefs['manage_device_metadata']=='manual')):
                flags |= Qt.ItemIsEditable
        return flags

    def search(self, text, reset=True):
        # This should not be here, but since the DeviceBooksModel does not
        # implement count_changed and I am too lazy to fix that, this kludge
        # will have to do
        self.resize_rows.emit()

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

    def research(self, reset=True):
        self.search(self.last_search, reset)

    def sort(self, col, order, reset=True):
        descending = order != Qt.AscendingOrder
        cname = self.column_map[col]
        def author_key(x):
            try:
                ax = self.db[x].author_sort
                if not ax:
                    raise Exception('')
            except:
                try:
                    ax = authors_to_string(self.db[x].authors)
                except:
                    ax = ''
            try:
                return sort_key(ax)
            except:
                return ax

        keygen = {
                'title': ('title_sorter', lambda x: sort_key(x) if x else ''),
                'authors' : author_key,
                'size' : ('size', int),
                'timestamp': ('datetime', functools.partial(dt_factory, assume_utc=True)),
                'collections': ('device_collections', lambda x:sorted(x,
                    key=sort_key)),
                'inlibrary': ('in_library', lambda x: x),
                }[cname]
        keygen = keygen if callable(keygen) else DeviceDBSortKeyGen(
            keygen[0], keygen[1], self.db)
        self.map.sort(key=keygen, reverse=descending)
        if len(self.map) == len(self.db):
            self.sorted_map = list(self.map)
        else:
            self.sorted_map = list(range(len(self.db)))
            self.sorted_map.sort(key=keygen, reverse=descending)
        self.sorted_on = (self.column_map[col], order)
        self.sort_history.insert(0, self.sorted_on)
        if hasattr(keygen, 'db'):
            keygen.db = None
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
        self.research(reset=False)
        self.resort()

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

    def get_book_display_info(self, idx):
        from calibre.ebooks.metadata.book.base import Metadata
        item = self.db[self.map[idx]]
        cover = self.cover(idx)
        if cover is self.default_image:
            cover = None
        title = item.title
        if not title:
            title = _('Unknown')
        au = item.authors
        if not au:
            au = [_('Unknown')]
        mi = Metadata(title, au)
        mi.cover_data = ('jpg', cover)
        fmt = _('Unknown')
        ext = os.path.splitext(item.path)[1]
        if ext:
            fmt = ext[1:].lower()
        mi.formats = [fmt]
        mi.path = (item.path if item.path else None)
        dt = dt_factory(item.datetime, assume_utc=True)
        mi.timestamp = dt
        mi.device_collections = list(item.device_collections)
        mi.tags = list(getattr(item, 'tags', []))
        mi.comments = getattr(item, 'comments', None)
        series = getattr(item, 'series', None)
        if series:
            sidx = getattr(item, 'series_index', 0)
            mi.series = series
            mi.series_index = sidx
        return mi

    def current_changed(self, current, previous, emit_signal=True):
        if current.isValid():
            idx = current.row()
            data = self.get_book_display_info(idx)
            if emit_signal:
                self.new_bookdisplay_data.emit(data)
            else:
                return data

    def paths(self, rows):
        return [self.db[self.map[r.row()]].path for r in rows ]

    def paths_for_db_ids(self, db_ids, as_map=False):
        res = defaultdict(list) if as_map else []
        for r,b in enumerate(self.db):
            if b.application_id in db_ids:
                if as_map:
                    res[b.application_id].append(b)
                else:
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
                    au = [_('Unknown')]
                return QVariant(authors_to_string(au))
            elif cname == 'size':
                size = self.db[self.map[row]].size
                if not isinstance(size, (float, int)):
                    size = 0
                return QVariant(human_readable(size))
            elif cname == 'timestamp':
                dt = self.db[self.map[row]].datetime
                try:
                    dt = dt_factory(dt, assume_utc=True, as_utc=False)
                except OverflowError:
                    dt = dt_factory(time.gmtime(), assume_utc=True,
                                    as_utc=False)
                return QVariant(strftime(TIME_FMT, dt.timetuple()))
            elif cname == 'collections':
                tags = self.db[self.map[row]].device_collections
                if tags:
                    tags.sort(key=sort_key)
                    return QVariant(', '.join(tags))
            elif DEBUG and cname == 'inlibrary':
                return QVariant(self.db[self.map[row]].in_library)
        elif role == Qt.ToolTipRole and index.isValid():
            if self.is_row_marked_for_deletion(row):
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
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            return QVariant(_('The lookup/search name is "{0}"').format(self.column_map[section]))
        if DEBUG and role == Qt.ToolTipRole and orientation == Qt.Vertical:
            return QVariant(_('This book\'s UUID is "{0}"').format(self.db[self.map[section]].uuid))
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
        if device_prefs['manage_device_metadata']=='on_connect':
            self.editable = []

# }}}

