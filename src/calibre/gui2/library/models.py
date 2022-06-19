#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import functools
import numbers
import os
import re
import time
import traceback
from collections import defaultdict, namedtuple
from itertools import groupby

from calibre import (
    fit_image, force_unicode, human_readable, isbytestring, prepare_string_for_xml,
    strftime
)
from calibre.constants import DEBUG, config_dir, dark_link_color, filesystem_encoding
from calibre.db.search import CONTAINS_MATCH, EQUALS_MATCH, REGEXP_MATCH, _match
from calibre.ebooks.metadata import authors_to_string, fmt_sidx, string_to_authors
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import error_dialog
from calibre.gui2.library import DEFAULT_SORT
from calibre.library.caches import force_to_bool
from calibre.library.coloring import color_row_key
from calibre.library.save_to_disk import find_plugboard
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import device_prefs, prefs, tweaks
from calibre.utils.date import (UNDEFINED_DATE, as_local_time, dt_factory,
                                is_date_undefined, qt_to_dt)
from calibre.utils.icu import sort_key
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.search_query_parser import ParseException, SearchQueryParser
from polyglot.builtins import iteritems, itervalues, string_or_bytes
from qt.core import (QAbstractTableModel, QApplication, QColor, QDateTime,
                     QFont, QFontMetrics, QIcon, QImage, QModelIndex, QPainter,
                     QPixmap, Qt, pyqtSignal)

Counts = namedtuple('Counts', 'library_total total current')

TIME_FMT = '%d %b %Y'

ALIGNMENT_MAP = {'left': Qt.AlignmentFlag.AlignLeft, 'right': Qt.AlignmentFlag.AlignRight, 'center':
        Qt.AlignmentFlag.AlignHCenter}


def render_pin(color='green', save_to=None):
    svg = P('pin-template.svg', data=True).replace(b'fill:#f39509', ('fill:' + color).encode('utf-8'))
    pm = QPixmap()
    dpr = QApplication.instance().devicePixelRatio()
    pm.setDevicePixelRatio(dpr)
    pm.loadFromData(svg, 'svg')
    if save_to:
        pm.save(save_to)
    return pm


def group_numbers(numbers):
    for k, g in groupby(enumerate(sorted(numbers)), lambda i_x:i_x[0] - i_x[1]):
        first = None
        for last in g:
            if first is None:
                first = last[1]
        yield first, last[1]


class ColumnColor:  # {{{

    def __init__(self, formatter):
        self.mi = None
        self.formatter = formatter

    def __call__(self, id_, key, fmt, db, color_cache, template_cache):
        key += str(hash(fmt))
        if id_ in color_cache and key in color_cache[id_]:
            self.mi = None
            color = color_cache[id_][key]
            if color.isValid():
                return color
            return None
        try:
            if self.mi is None:
                self.mi = db.new_api.get_proxy_metadata(id_)
            color = QColor(self.formatter.safe_format(fmt, self.mi, '', self.mi,
                                                  column_name=key,
                                                  template_cache=template_cache))
            color_cache[id_][key] = color
            if color.isValid():
                self.mi = None
                return color
        except:
            pass
# }}}


class ColumnIcon:  # {{{

    def __init__(self, formatter, model):
        self.mi = None
        self.formatter = formatter
        self.model = model
        self.dpr = QApplication.instance().devicePixelRatio()

    def __call__(self, id_, fmts, cache_index, db, icon_cache, icon_bitmap_cache,
             template_cache):
        if id_ in icon_cache and cache_index in icon_cache[id_]:
            self.mi = None
            return icon_cache[id_][cache_index]
        try:
            if self.mi is None:
                self.mi = db.new_api.get_proxy_metadata(id_)
            icons = []
            for dex, (kind, fmt) in enumerate(fmts):
                rule_icons = self.formatter.safe_format(fmt, self.mi, '', self.mi,
                                    column_name=cache_index+str(dex),
                                    template_cache=template_cache)
                if not rule_icons:
                    continue
                icon_list = [ic.strip() for ic in rule_icons.split(':') if ic.strip()]
                icons.extend(icon_list)
                if icon_list and not kind.endswith('_composed'):
                    break

            if icons:
                icon_string = ':'.join(icons)
                if icon_string in icon_bitmap_cache:
                    icon_bitmap = icon_bitmap_cache[icon_string]
                    icon_cache[id_][cache_index] = icon_bitmap
                    return icon_bitmap

                icon_bitmaps = []
                total_width = 0
                rh = max(2, self.model.row_height - 4)
                dim = int(self.dpr * rh)
                for icon in icons:
                    d = os.path.join(config_dir, 'cc_icons', icon)
                    if (os.path.exists(d)):
                        bm = QPixmap(d)
                        scaled, nw, nh = fit_image(bm.width(), bm.height(), bm.width(), dim)
                        bm = bm.scaled(int(nw), int(nh), aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio,
                                       transformMode=Qt.TransformationMode.SmoothTransformation)
                        bm.setDevicePixelRatio(self.dpr)
                        icon_bitmaps.append(bm)
                        total_width += bm.width()
                if len(icon_bitmaps) > 1:
                    i = len(icon_bitmaps)
                    result = QPixmap(total_width + ((i-1)*2), dim)
                    result.setDevicePixelRatio(self.dpr)
                    result.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(result)
                    x = 0
                    for bm in icon_bitmaps:
                        painter.drawPixmap(x, 0, bm)
                        x += int(bm.width() / self.dpr) + 2
                    painter.end()
                else:
                    result = icon_bitmaps[0]

                icon_cache[id_][cache_index] = result
                icon_bitmap_cache[icon_string] = result
                self.mi = None
                return result
        except:
            pass
# }}}


class BooksModel(QAbstractTableModel):  # {{{

    about_to_be_sorted   = pyqtSignal(object, name='aboutToBeSorted')
    sorting_done         = pyqtSignal(object, name='sortingDone')
    database_changed     = pyqtSignal(object, name='databaseChanged')
    new_bookdisplay_data = pyqtSignal(object)
    count_changed_signal = pyqtSignal(int)
    searched             = pyqtSignal(object)
    search_done          = pyqtSignal()

    def __init__(self, parent=None, buffer=40):
        QAbstractTableModel.__init__(self, parent)
        base_font = parent.font() if parent else QApplication.instance().font()
        self.bold_font = QFont(base_font)
        self.bold_font.setBold(True)
        self.italic_font = QFont(base_font)
        self.italic_font.setItalic(True)
        self.bi_font = QFont(self.bold_font)
        self.bi_font.setItalic(True)
        self.styled_columns = {}
        self.orig_headers = {
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

        self.db = None

        self.formatter = SafeFormat()
        self._clear_caches()
        self.column_color = ColumnColor(self.formatter)
        self.column_icon = ColumnIcon(self.formatter, self)

        self.book_on_device = None
        self.editable_cols = ['title', 'authors', 'rating', 'publisher',
                              'tags', 'series', 'timestamp', 'pubdate',
                              'languages']
        self.sorted_on = DEFAULT_SORT
        self.sort_history = [self.sorted_on]
        self.last_search = ''  # The last search performed on this model
        self.column_map = []
        self.headers = {}
        self.alignment_map = {}
        self.buffer_size = buffer
        self.metadata_backup = None
        icon_height = (parent.fontMetrics() if hasattr(parent, 'fontMetrics') else QFontMetrics(QApplication.font())).lineSpacing()
        self.bool_yes_icon = QIcon.ic('ok.png').pixmap(icon_height)
        self.bool_no_icon = QIcon.ic('list_remove.png').pixmap(icon_height)
        self.bool_blank_icon = QIcon.ic('blank.png').pixmap(icon_height)
        # Qt auto-scales marked icon correctly, so we dont need to do it (and
        # remember that the cover grid view needs a larger version of the icon,
        # anyway)
        self.marked_icon = QIcon.ic('marked.png')
        self.bool_blank_icon_as_icon = QIcon(self.bool_blank_icon)
        self.row_decoration = None
        self.device_connected = False
        self.ids_to_highlight = []
        self.ids_to_highlight_set = set()
        self.current_highlighted_idx = None
        self.highlight_only = False
        self.row_height = 0
        self.marked_text_icons = {}
        self.read_config()

    def marked_text_icon_for(self, label):
        import random
        ans = self.marked_text_icons.get(label)
        if ans is not None:
            return ans[1]
        used_labels = self.db.data.all_marked_labels()
        for qlabel in tuple(self.marked_text_icons):
            if qlabel not in used_labels:
                del self.marked_text_icons[qlabel]
        used_colors = {x[0] for x in self.marked_text_icons.values()}
        if QApplication.instance().is_dark_theme:
            all_colors = {dark_link_color, 'lightgreen', 'red', 'maroon', 'cyan', 'pink'}
        else:
            all_colors = {'blue', 'green', 'red', 'maroon', 'cyan', 'pink'}
        for c in all_colors - used_colors:
            color = c
            break
        else:
            color = random.choice(sorted(all_colors))
        pm = render_pin(color)
        ans = QIcon(pm)
        self.marked_text_icons[label] = color, ans
        return ans

    @property
    def default_image(self):
        return QApplication.instance().cached_qimage('default_cover.png')

    def _clear_caches(self):
        self.color_cache = defaultdict(dict)
        self.icon_cache = defaultdict(dict)
        self.icon_bitmap_cache = {}
        self.cover_grid_emblem_cache = defaultdict(dict)
        self.cover_grid_bitmap_cache = {}
        self.color_row_fmt_cache = None
        self.color_template_cache = {}
        self.icon_template_cache = {}
        self.cover_grid_template_cache = {}

    def set_row_height(self, height):
        self.row_height = height

    def set_row_decoration(self, current_marked):
        self.row_decoration = self.bool_blank_icon_as_icon if current_marked else None

    def change_alignment(self, colname, alignment):
        if colname in self.column_map and alignment in ('left', 'right', 'center'):
            old = self.alignment_map.get(colname, 'left')
            if old == alignment:
                return
            self.alignment_map.pop(colname, None)
            if alignment != 'left':
                self.alignment_map[colname] = alignment
            col = self.column_map.index(colname)
            for row in range(self.rowCount(QModelIndex())):
                self.dataChanged.emit(self.index(row, col), self.index(row,
                    col))

    def change_column_font(self, colname, font_type):
        if colname in self.column_map and font_type in ('normal', 'bold', 'italic', 'bi'):
            db = self.db.new_api
            old = db.pref('styled_columns', {})
            old.pop(colname, None)
            self.styled_columns.pop(colname, None)
            if font_type != 'normal':
                self.styled_columns[colname] = getattr(self, f'{font_type}_font')
                old[colname] = font_type
            self.db.new_api.set_pref('styled_columns', old)
            col = self.column_map.index(colname)
            for row in range(self.rowCount(QModelIndex())):
                self.dataChanged.emit(self.index(row, col), self.index(row,
                    col))

    def is_custom_column(self, cc_label):
        try:
            return cc_label in self.custom_columns
        except AttributeError:
            return False

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

        if db:
            style_map = {'bold': self.bold_font, 'bi': self.bi_font, 'italic': self.italic_font}
            self.styled_columns = {k: style_map.get(v, None) for k, v in iteritems(db.new_api.pref('styled_columns', {}))}
        self.alignment_map = {}
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

        self.column_map.sort(key=lambda x: col_idx(x))
        for col in self.column_map:
            if col in self.orig_headers:
                self.headers[col] = self.orig_headers[col]
            elif col in self.custom_columns:
                self.headers[col] = self.custom_columns[col]['name']

        self.build_data_convertors()
        self.beginResetModel(), self.endResetModel()
        self.database_changed.emit(db)
        self.stop_metadata_backup()
        self.start_metadata_backup()

    def start_metadata_backup(self):
        from calibre.db.backup import MetadataBackup
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
        cc = self.columnCount(QModelIndex()) - 1
        for first_row, last_row in group_numbers(rows):
            self.dataChanged.emit(self.index(first_row, 0), self.index(last_row, cc))
            if current_row >= 0 and first_row <= current_row <= last_row:
                self.new_bookdisplay_data.emit(self.get_book_display_info(current_row))

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
            self.beginResetModel(), self.endResetModel()

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

    def counts(self):
        library_total = total = self.db.count()
        if self.db.data.search_restriction_applied():
            total  = self.db.data.get_search_restriction_book_count()
        return Counts(library_total, total, self.count())

    def row_indices(self, index):
        ''' Return list indices of all cells in index.row()'''
        return [self.index(index.row(), c) for c in range(self.columnCount(None))]

    @property
    def by_author(self):
        return self.sorted_on[0] == 'authors'

    def books_deleted(self):
        self.count_changed()
        self.beginResetModel(), self.endResetModel()

    def delete_books(self, indices, permanent=False):
        ids = list(map(self.id, indices))
        self.delete_books_by_id(ids, permanent=permanent)
        return ids

    def delete_books_by_id(self, ids, permanent=False):
        self.db.new_api.remove_books(ids, permanent=permanent)
        self.ids_deleted(ids)

    def ids_deleted(self, ids):
        self.db.data.books_deleted(tuple(ids))
        self.db.notify('delete', list(ids))
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
                row_ = self.count() - 1
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
        self.beginResetModel(), self.endResetModel()

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
            self.beginResetModel(), self.endResetModel()
        if self.last_search:
            # Do not issue search done for the null search. It is used to clear
            # the search and count records for restrictions
            self.searched.emit(True)
        self.search_done.emit()

    def sort(self, col, order=Qt.SortOrder.AscendingOrder, reset=True):
        if not self.db:
            return
        if not isinstance(order, bool):
            order = order == Qt.SortOrder.AscendingOrder
        label = self.column_map[col]
        self._sort(label, order, reset)

    def sort_by_named_field(self, field, order, reset=True):
        if field in list(self.db.field_metadata.keys()):
            self._sort(field, order, reset)

    def _sort(self, label, order, reset):
        self.about_to_be_sorted.emit(self.db.id)
        self.db.data.incremental_sort([(label, order)])
        if reset:
            self.beginResetModel(), self.endResetModel()
        self.sorted_on = (label, order)
        self.sort_history.insert(0, self.sorted_on)
        self.sorting_done.emit(self.db.index)

    def refresh(self, reset=True):
        self.db.refresh(field=None)
        self.resort(reset=reset)

    def beginResetModel(self):
        self._clear_caches()
        QAbstractTableModel.beginResetModel(self)

    def reset(self):
        self.beginResetModel(), self.endResetModel()

    def resort(self, reset=True):
        if not self.db:
            return
        self.db.multisort(self.sort_history[:tweaks['maximum_resort_levels']])
        if reset:
            self.beginResetModel(), self.endResetModel()

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
        mi.size = mi._proxy_metadata.book_size
        mi.cover_data = ('jpg', self.cover(idx))
        mi.id = self.db.id(idx)
        mi.field_metadata = self.db.field_metadata
        mi.path = self.db.abspath(idx, create_dirs=False)
        mi.format_files = self.db.new_api.format_files(self.db.data.index_to_id(idx))
        mi.row_number = idx
        try:
            mi.marked = self.db.data.get_marked(idx, index_is_id=False)
        except:
            mi.marked = None
        return mi

    def current_changed(self, current, previous, emit_signal=True):
        if current.isValid():
            idx = current.row()
            try:
                data = self.get_book_display_info(idx)
            except Exception:
                import traceback
                error_dialog(None, _('Unhandled error'), _(
                    'Failed to read book data from calibre library. Click "Show details" for more information'), det_msg=traceback.format_exc(), show=True)
            else:
                if emit_signal:
                    self.new_bookdisplay_data.emit(data)
                else:
                    return data

    def get_book_info(self, index):
        if isinstance(index, numbers.Integral):
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
            available_formats = {f.lower() for f in formats}
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
                            plugboards = self.db.new_api.pref('plugboards', {})
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
            available_formats = {f.lower() for f in formats}
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
        except IndexError:  # Happens if database has not yet been refreshed
            pass
        except MemoryError:
            raise ValueError(_('The cover for the book %s is too large, cannot load it.'
                             ' Resize or delete it.') % self.db.title(row_number))

        if not data:
            return self.default_image
        img = QImage()
        img.loadFromData(data)
        if img.isNull():
            img = self.default_image
        return img

    def build_data_convertors(self):
        rating_fields = {}
        bool_fields = set()

        def renderer(field, decorator=False):
            idfunc = self.db.id
            fffunc = self.db.new_api.fast_field_for
            field_obj = self.db.new_api.fields[field]
            m = field_obj.metadata.copy()
            if 'display' not in m:
                m['display'] = {}
            dt = m['datatype']

            if decorator == 'bool':
                bool_fields.add(field)
                bt = self.db.new_api.pref('bools_are_tristate')
                bn = self.bool_no_icon
                by = self.bool_yes_icon

                if dt != 'bool':
                    def func(idx):
                        val = fffunc(field_obj, idfunc(idx))
                        if val is None:
                            return None
                        val = force_to_bool(val)
                        if val is None:
                            return None
                        return by if val else bn
                else:
                    if m['display'].get('bools_show_icons', True):
                        def func(idx):
                            val = force_to_bool(fffunc(field_obj, idfunc(idx)))
                            if val is None:
                                return None if bt else bn
                            return by if val else bn
                    else:
                        def func(idx):
                            return None
            elif field == 'size':
                sz_mult = 1/(1024**2)

                def func(idx):
                    val = fffunc(field_obj, idfunc(idx), default_value=0) or 0
                    if val == 0:
                        return None
                    ans = '%.1f' % (val * sz_mult)
                    return ('<0.1' if ans == '0.0' else ans)
            elif field == 'languages':
                def func(idx):
                    return (', '.join(calibre_langcode_to_name(x) for x in fffunc(field_obj, idfunc(idx))))
            elif field == 'ondevice' and decorator:
                by = self.bool_yes_icon
                bb = self.bool_blank_icon

                def func(idx):
                    return by if fffunc(field_obj, idfunc(idx)) else bb
            elif dt in {'text', 'comments', 'composite', 'enumeration'}:
                if m['is_multiple']:
                    jv = m['is_multiple']['list_to_ui']
                    do_sort = '&' not in jv
                    if field_obj.is_composite:
                        if do_sort:
                            sv = m['is_multiple']['cache_to_list']

                            def func(idx):
                                val = fffunc(field_obj, idfunc(idx), default_value='') or ''
                                return (jv.join(sorted((x.strip() for x in val.split(sv)), key=sort_key)))
                        else:
                            def func(idx):
                                return (fffunc(field_obj, idfunc(idx), default_value=''))
                    else:
                        if do_sort:
                            def func(idx):
                                return (jv.join(sorted(fffunc(field_obj, idfunc(idx), default_value=()), key=sort_key)))
                        else:
                            def func(idx):
                                return (jv.join(fffunc(field_obj, idfunc(idx), default_value=())))
                else:
                    if dt in {'text', 'composite', 'enumeration'} and m['display'].get('use_decorations', False):
                        def func(idx):
                            text = fffunc(field_obj, idfunc(idx))
                            return (text) if force_to_bool(text) is None else None
                    else:
                        def func(idx):
                            return (fffunc(field_obj, idfunc(idx), default_value=''))
            elif dt == 'datetime':
                def func(idx):
                    val = fffunc(field_obj, idfunc(idx), default_value=UNDEFINED_DATE)
                    return None if is_date_undefined(val) else QDateTime(as_local_time(val))
            elif dt == 'rating':
                rating_fields[field] = m['display'].get('allow_half_stars', False)

                def func(idx):
                    return int(fffunc(field_obj, idfunc(idx), default_value=0))
            elif dt == 'series':
                sidx_field = self.db.new_api.fields[field + '_index']

                def func(idx):
                    book_id = idfunc(idx)
                    series = fffunc(field_obj, book_id, default_value=False)
                    if series:
                        return (f'{series} [{fmt_sidx(fffunc(sidx_field, book_id, default_value=1.0))}]')
                    return None
            elif dt in {'int', 'float'}:
                fmt = m['display'].get('number_format', None)

                def func(idx):
                    val = fffunc(field_obj, idfunc(idx))
                    if val is None:
                        return None
                    if fmt:
                        try:
                            return (fmt.format(val))
                        except (TypeError, ValueError, AttributeError, IndexError, KeyError):
                            pass
                    return (val)
            elif dt == 'bool':
                if m['display'].get('bools_show_text', False):
                    def func(idx):
                        v = fffunc(field_obj, idfunc(idx))
                        return (None if v is None else (_('Yes') if v else _('No')))
                else:
                    def func(idx):
                        return(None)
            else:
                def func(idx):
                    return None

            return func

        self.dc = {f:renderer(f) for f in 'title authors size timestamp pubdate last_modified rating publisher tags series ondevice languages'.split()}
        self.dc_decorator = {f:renderer(f, True) for f in ('ondevice',)}

        for col in self.custom_columns:
            self.dc[col] = renderer(col)
            m = self.custom_columns[col]
            dt = m['datatype']
            mult = m['is_multiple']
            if dt in {'text', 'composite', 'enumeration'} and not mult and m['display'].get('use_decorations', False):
                self.dc_decorator[col] = renderer(col, 'bool')
            elif dt == 'bool':
                self.dc_decorator[col] = renderer(col, 'bool')

        tc = self.dc.copy()

        def stars_tooltip(func, allow_half=True):
            def f(idx):
                val = int(func(idx))
                ans = str(val // 2)
                if allow_half and val % 2:
                    ans += '.5'
                return _('%s stars') % ans
            return f

        def bool_tooltip(key):
            def f(idx):
                return self.db.new_api.fast_field_for(self.db.new_api.fields[key],
                                                     self.db.id(idx))
            return f

        for f, allow_half in iteritems(rating_fields):
            tc[f] = stars_tooltip(self.dc[f], allow_half)
        for f in bool_fields:
            tc[f] = bool_tooltip(f)
        # build a index column to data converter map, to remove the string lookup in the data loop
        self.column_to_dc_map = [self.dc[col] for col in self.column_map]
        self.column_to_tc_map = [tc[col] for col in self.column_map]
        self.column_to_dc_decorator_map = [self.dc_decorator.get(col, None) for col in self.column_map]

    def data(self, index, role):
        col = index.column()
        # in obscure cases where custom columns are both edited and added, for a time
        # the column map does not accurately represent the screen. In these cases,
        # we will get asked to display columns we don't know about. Must test for this.
        if col >= len(self.column_to_dc_map) or col < 0:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            rules = self.db.new_api.pref('column_icon_rules')
            if rules:
                key = self.column_map[col]
                id_ = None
                fmts = []
                for kind, k, fmt in rules:
                    if k == key and kind in {'icon_only', 'icon_only_composed'}:
                        if id_ is None:
                            id_ = self.id(index)
                            self.column_icon.mi = None
                        fmts.append((kind, fmt))

                if fmts:
                    cache_index = key + ':DisplayRole'
                    ccicon = self.column_icon(id_, fmts, cache_index, self.db,
                                      self.icon_cache, self.icon_bitmap_cache,
                                      self.icon_template_cache)
                    if ccicon is not None:
                        return None
                    self.icon_cache[id_][cache_index] = None
            return self.column_to_dc_map[col](index.row())
        elif role == Qt.ItemDataRole.ToolTipRole:
            return self.column_to_tc_map[col](index.row())
        elif role == Qt.ItemDataRole.EditRole:
            return self.column_to_dc_map[col](index.row())
        elif role == Qt.ItemDataRole.BackgroundRole:
            if self.id(index) in self.ids_to_highlight_set:
                return QColor('#027524') if QApplication.instance().is_dark_theme else QColor('#b4ecb4')
        elif role == Qt.ItemDataRole.ForegroundRole:
            key = self.column_map[col]
            id_ = self.id(index)
            self.column_color.mi = None

            for k, fmt in self.db.new_api.pref('column_color_rules', ()):
                if k == key:
                    ccol = self.column_color(id_, key, fmt, self.db,
                                         self.color_cache, self.color_template_cache)
                    if ccol is not None:
                        return ccol

            if self.is_custom_column(key) and \
                        self.custom_columns[key]['datatype'] == 'enumeration':
                cc = self.custom_columns[self.column_map[col]]['display']
                colors = cc.get('enum_colors', [])
                values = cc.get('enum_values', [])
                txt = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
                if len(colors) > 0 and txt in values:
                    try:
                        color = QColor(colors[values.index(txt)])
                        if color.isValid():
                            self.column_color.mi = None
                            return (color)
                    except:
                        pass

            if self.color_row_fmt_cache is None:
                self.color_row_fmt_cache = tuple(fmt for key, fmt in
                    self.db.new_api.pref('column_color_rules', ()) if key == color_row_key)
            for fmt in self.color_row_fmt_cache:
                ccol = self.column_color(id_, color_row_key, fmt, self.db,
                                         self.color_cache, self.color_template_cache)
                if ccol is not None:
                    return ccol

            self.column_color.mi = None
            return None
        elif role == Qt.ItemDataRole.DecorationRole:
            default_icon = None
            if self.column_to_dc_decorator_map[col] is not None:
                default_icon = self.column_to_dc_decorator_map[index.column()](index.row())
            rules = self.db.new_api.pref('column_icon_rules')
            if rules:
                key = self.column_map[col]
                id_ = None
                need_icon_with_text = False
                fmts = []
                for kind, k, fmt in rules:
                    if k == key and kind.startswith('icon'):
                        if id_ is None:
                            id_ = self.id(index)
                            self.column_icon.mi = None
                        fmts.append((kind, fmt))
                        if kind in ('icon', 'icon_composed'):
                            need_icon_with_text = True
                if fmts:
                    cache_index = key + ':DecorationRole'
                    ccicon = self.column_icon(id_, fmts, cache_index, self.db,
                                  self.icon_cache, self.icon_bitmap_cache,
                                  self.icon_template_cache)
                    if ccicon is not None:
                        return ccicon
                    if need_icon_with_text and default_icon is None:
                        self.icon_cache[id_][cache_index] = self.bool_blank_icon
                        return self.bool_blank_icon
                    self.icon_cache[id_][cache_index] = None
            return default_icon
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            cname = self.column_map[index.column()]
            ans = Qt.AlignmentFlag.AlignVCenter | ALIGNMENT_MAP[self.alignment_map.get(cname,
                'left')]
            return ans.value
        elif role == Qt.ItemDataRole.FontRole and self.styled_columns:
            cname = self.column_map[index.column()]
            return self.styled_columns.get(cname)
        # elif role == Qt.ItemDataRole.ToolTipRole and index.isValid():
        #    if self.column_map[index.column()] in self.editable_cols:
        #        return (_("Double click to <b>edit</b> me<br><br>"))
        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal:
            if section >= len(self.column_map):  # same problem as in data, the column_map can be wrong
                return None
            if role == Qt.ItemDataRole.ToolTipRole:
                ht = self.column_map[section]
                title = self.headers[ht]
                fm = self.db.field_metadata[self.column_map[section]]
                if ht == 'timestamp':  # change help text because users know this field as 'date'
                    ht = 'date'
                if fm['is_category']:
                    is_cat = '<br><br>' + prepare_string_for_xml(_('Click in this column and press Q to Quickview books with the same "%s"') % ht)
                else:
                    is_cat = ''
                cust_desc = ''
                if fm['is_custom']:
                    cust_desc = fm['display'].get('description', '')
                    if cust_desc:
                        cust_desc = ('<br><b>{}</b>'.format(_('Description:')) +
                                     '<span style="white-space:pre-wrap"> ' +
                                     prepare_string_for_xml(cust_desc) + '</span>')
                return '<b>{}</b>: {}'.format(
                    prepare_string_for_xml(title),
                    _('The lookup/search name is <i>{0}</i>').format(ht) + cust_desc + is_cat
                )
            if role == Qt.ItemDataRole.DisplayRole:
                return (self.headers[self.column_map[section]])
            return None
        if role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Vertical:
            col = self.db.field_metadata['marked']['rec_index']
            marked = self.db.data[section][col]
            if marked is not None:
                s = _('Marked with text "{0}"').format(marked) if marked != 'true' else _('Marked without text')
            else:
                s = ''
            if DEBUG:
                col = self.db.field_metadata['uuid']['rec_index']
                s += ('\n' if s else '') + _('This book\'s UUID is "{0}"').format(self.db.data[section][col])
            return s

        if role == Qt.ItemDataRole.DisplayRole:  # orientation is vertical
            return (section+1)
        if role == Qt.ItemDataRole.DecorationRole:
            try:
                m = self.db.data.get_marked(self.db.data.index_to_id(section))
                if m:
                    i = self.marked_icon if m == 'true' else self.marked_text_icon_for(m)
                else:
                    i = self.row_decoration
                return i
            except (ValueError, IndexError):
                pass
        return None

    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            colhead = self.column_map[index.column()]
            if colhead in self.editable_cols:
                flags |= Qt.ItemFlag.ItemIsEditable
            elif self.is_custom_column(colhead):
                if self.custom_columns[colhead]['is_editable']:
                    flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def set_custom_column_data(self, row, colhead, value):
        cc = self.custom_columns[colhead]
        typ = cc['datatype']
        label=self.db.field_metadata.key_to_label(colhead)
        s_index = None
        if typ in ('text', 'comments'):
            val = str(value or '').strip()
            val = val if val else None
        elif typ == 'enumeration':
            val = str(value or '').strip()
            if not val:
                val = None
        elif typ == 'bool':
            val = value if value is None else bool(value)
        elif typ == 'rating':
            val = max(0, min(int(value or 0), 10))
        elif typ in ('int', 'float'):
            if value == 0:
                val = '0'
            else:
                val = str(value or '').strip()
            if not val:
                val = None
        elif typ == 'datetime':
            val = value
            if val is None:
                val = None
            else:
                if not val.isValid():
                    return False
                val = qt_to_dt(val, as_utc=False)
        elif typ == 'series':
            val = str(value or '').strip()
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
            tmpl = str(value or '').strip()
            disp = cc['display']
            disp['composite_template'] = tmpl
            self.db.set_custom_column_metadata(cc['colnum'], display=disp,
                                               update_last_modified=True)
            self.refresh(reset=False)
            self.research(reset=True)
            return True

        id = self.db.id(row)
        books_to_refresh = {id}
        books_to_refresh |= self.db.set_custom(id, val, extra=s_index,
                           label=label, num=None, append=False, notify=True,
                           allow_case_change=True)
        self.refresh_ids(list(books_to_refresh), current_row=row)
        return True

    def setData(self, index, value, role):
        from calibre.gui2.ui import get_gui
        if get_gui().shutting_down:
            return False
        if role == Qt.ItemDataRole.EditRole:
            from calibre.gui2.ui import get_gui
            try:
                return self._set_data(index, value)
            except OSError as err:
                import traceback
                if getattr(err, 'errno', None) == errno.EACCES:  # Permission denied
                    fname = getattr(err, 'filename', None)
                    p = 'Locked file: %s\n\n'%force_unicode(fname if fname else '')
                    error_dialog(get_gui(), _('Permission denied'),
                            _('Could not change the on disk location of this'
                                ' book. Is it open in another program?'),
                            det_msg=p+force_unicode(traceback.format_exc()), show=True)
                    return False
                error_dialog(get_gui(), _('Failed to set data'),
                        _('Could not set data, click "Show details" to see why.'),
                        det_msg=traceback.format_exc(), show=True)
            except:
                import traceback
                traceback.print_exc()
                error_dialog(get_gui(), _('Failed to set data'),
                        _('Could not set data, click "Show details" to see why.'),
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
            val = (int(value) if column == 'rating' else
                    value if column in ('timestamp', 'pubdate')
                    else re.sub(r'\s', ' ', str(value or '').strip()))
            id = self.db.id(row)
            books_to_refresh = {id}
            if column == 'rating':
                val = max(0, min(int(val or 0), 10))
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
                if val is None or not val.isValid():
                    return False
                self.db.set_timestamp(id, qt_to_dt(val, as_utc=False))
            elif column == 'pubdate':
                if val is None or not val.isValid():
                    return False
                self.db.set_pubdate(id, qt_to_dt(val, as_utc=False))
            elif column == 'languages':
                val = val.split(',')
                self.db.set_languages(id, val)
            else:
                if column == 'authors' and val:
                    val = authors_to_string(string_to_authors(val))
                books_to_refresh |= self.db.set(row, column, val,
                                                allow_case_change=True)
            self.refresh_ids(list(books_to_refresh), row)
        self.dataChanged.emit(index, index)
        return True

# }}}


class OnDeviceSearch(SearchQueryParser):  # {{{

    USABLE_LOCATIONS = [
        'all',
        'author',
        'authors',
        'collections',
        'format',
        'formats',
        'title',
        'inlibrary',
        'tags',
        'search'
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
        if matchkind != REGEXP_MATCH:  # leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set()
        matches = set()
        all_locs = set(self.USABLE_LOCATIONS) - {'all', 'tags', 'search'}
        locations = all_locs if location == 'all' else [location]
        q = {
             'title' : lambda x : getattr(x, 'title').lower(),
             'author': lambda x: ' & '.join(getattr(x, 'authors')).lower(),
             'collections':lambda x: ','.join(getattr(x, 'device_collections')).lower(),
             'format':lambda x: os.path.splitext(x.path)[1].lower(),
             'inlibrary':lambda x : getattr(x, 'in_library'),
             'tags':lambda x : getattr(x, 'tags', [])
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
                    # Can't separate authors because comma is used for name sep and author sep
                    # Exact match might not get what you want. For that reason, turn author
                    # exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    vals = accessor(row)
                    if vals is None:
                        vals = ''
                    if isinstance(vals, string_or_bytes):
                        vals = vals.split(',') if locvalue == 'collections' else [vals]
                    if _match(query, vals, m, use_primary_find_in_search=upf):
                        matches.add(index)
                        break
                except ValueError:  # Unicode errors
                    traceback.print_exc()
        return matches

# }}}


class DeviceDBSortKeyGen:  # {{{

    def __init__(self, attr, keyfunc, db):
        self.attr = attr
        self.db = db
        self.keyfunc = keyfunc

    def __call__(self, x):
        try:
            ans = self.keyfunc(getattr(self.db[x], self.attr))
        except Exception:
            ans = ''
        return ans
# }}}


class DeviceBooksModel(BooksModel):  # {{{

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
        self.sync_icon = QIcon.ic('sync.png')

    def counts(self):
        return Counts(len(self.db), len(self.db), len(self.map))

    def count_changed(self, *args):
        self.count_changed_signal.emit(len(self.db))

    def mark_for_deletion(self, job, rows, rows_are_ids=False):
        db_indices = rows if rows_are_ids else self.indices(rows)
        db_items = [self.db[i] for i in db_indices if -1 < i < len(self.db)]
        self.marked_for_deletion[job] = db_items
        if rows_are_ids:
            self.beginResetModel(), self.endResetModel()
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
        self.count_changed()

    def paths_deleted(self, paths):
        self.map = list(range(0, len(self.db)))
        self.resort(False)
        self.research(True)
        self.count_changed()

    def is_row_marked_for_deletion(self, row):
        try:
            item = self.db[self.map[row]]
        except IndexError:
            return False

        path = getattr(item, 'path', None)
        for items in itervalues(self.marked_for_deletion):
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
            self.beginResetModel(), self.endResetModel()

    def flags(self, index):
        if self.is_row_marked_for_deletion(index.row()):
            return Qt.ItemFlag.NoItemFlags
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            cname = self.column_map[index.column()]
            if cname in self.editable and \
                     (cname != 'collections' or
                     (callable(getattr(self.db, 'supports_collections', None)) and
                      self.db.supports_collections() and
                      device_prefs['manage_device_metadata']=='manual')):
                flags |= Qt.ItemFlag.ItemIsEditable
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
            self.beginResetModel(), self.endResetModel()
        self.last_search = text
        if self.last_search:
            self.searched.emit(True)
        self.count_changed()

    def research(self, reset=True):
        self.search(self.last_search, reset)

    def sort(self, col, order, reset=True):
        descending = order != Qt.SortOrder.AscendingOrder
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
                'inlibrary': ('in_library', lambda x: x or ''),
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
            self.beginResetModel(), self.endResetModel()

    def resort(self, reset=True):
        if self.sorted_on:
            self.sort(self.column_map.index(self.sorted_on[0]),
                      self.sorted_on[1], reset=False)
        if reset:
            self.beginResetModel(), self.endResetModel()

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
        self.count_changed()

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
            try:
                data = self.get_book_display_info(idx)
            except Exception:
                import traceback
                error_dialog(None, _('Unhandled error'), _(
                    'Failed to read book data from calibre library. Click "Show details" for more information'), det_msg=traceback.format_exc(), show=True)
            else:
                if emit_signal:
                    self.new_bookdisplay_data.emit(data)
                else:
                    return data

    def paths(self, rows):
        return [self.db[self.map[r.row()]].path for r in rows]

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
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if cname == 'title':
                text = self.db[self.map[row]].title
                if not text:
                    text = self.unknown
                return (text)
            elif cname == 'authors':
                au = self.db[self.map[row]].authors
                if not au:
                    au = [_('Unknown')]
                return (authors_to_string(au))
            elif cname == 'size':
                size = self.db[self.map[row]].size
                if not isinstance(size, numbers.Number):
                    size = 0
                return (human_readable(size))
            elif cname == 'timestamp':
                dt = self.db[self.map[row]].datetime
                try:
                    dt = dt_factory(dt, assume_utc=True, as_utc=False)
                except OverflowError:
                    dt = dt_factory(time.gmtime(), assume_utc=True,
                                    as_utc=False)
                return (strftime(TIME_FMT, dt.timetuple()))
            elif cname == 'collections':
                tags = self.db[self.map[row]].device_collections
                if tags:
                    tags.sort(key=sort_key)
                    return (', '.join(tags))
            elif DEBUG and cname == 'inlibrary':
                return (self.db[self.map[row]].in_library)
        elif role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            if col == 0 and hasattr(self.db[self.map[row]], 'in_library_waiting'):
                return (_('Waiting for metadata to be updated'))
            if self.is_row_marked_for_deletion(row):
                return (_('Marked for deletion'))
            if cname in ['title', 'authors'] or (
                    cname == 'collections' and (
                        callable(getattr(self.db, 'supports_collections', None)) and self.db.supports_collections())
            ):
                return (_("Double click to <b>edit</b> me<br><br>"))
        elif role == Qt.ItemDataRole.DecorationRole and cname == 'inlibrary':
            if hasattr(self.db[self.map[row]], 'in_library_waiting'):
                return (self.sync_icon)
            elif self.db[self.map[row]].in_library:
                return (self.bool_yes_icon)
            elif self.db[self.map[row]].in_library is not None:
                return (self.bool_no_icon)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            cname = self.column_map[index.column()]
            ans = Qt.AlignmentFlag.AlignVCenter | ALIGNMENT_MAP[self.alignment_map.get(cname,
                'left')]
            return ans.value
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Horizontal:
            cname = self.column_map[section]
            text = self.headers[cname]
            return '<b>{}</b>: {}'.format(
                prepare_string_for_xml(text),
                prepare_string_for_xml(_('The lookup/search name is')) + f' <i>{self.column_map[section]}</i>')
        if DEBUG and role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Vertical:
            return (_('This book\'s UUID is "{0}"').format(self.db[self.map[section]].uuid))
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            cname = self.column_map[section]
            text = self.headers[cname]
            return (text)
        else:
            return (section+1)

    def setData(self, index, value, role):
        from calibre.gui2.ui import get_gui
        if get_gui().shutting_down:
            return False
        done = False
        if role == Qt.ItemDataRole.EditRole:
            row, col = index.row(), index.column()
            cname = self.column_map[col]
            if cname in ('size', 'timestamp', 'inlibrary'):
                return False
            val = str(value or '').strip()
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
