__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, textwrap, traceback, re, shutil, functools, sys

from operator import attrgetter
from math import cos, sin, pi
from contextlib import closing

from PyQt4.QtGui import QTableView, QAbstractItemView, QColor, \
                        QPainterPath, QLinearGradient, QBrush, \
                        QPen, QStyle, QPainter, QStyleOptionViewItemV4, \
                        QIcon, QImage, QMenu, QSpinBox, QDoubleSpinBox, \
                        QStyledItemDelegate, QCompleter, \
                        QComboBox
from PyQt4.QtCore import QAbstractTableModel, QVariant, Qt, pyqtSignal, \
                         SIGNAL, QObject, QSize, QModelIndex, QDate

from calibre import strftime
from calibre.ebooks.metadata import string_to_authors, fmt_sidx, authors_to_string
from calibre.ebooks.metadata.meta import set_metadata as _set_metadata
from calibre.gui2 import NONE, TableView, config, error_dialog, UNDEFINED_DATE
from calibre.gui2.dialogs.comments_dialog import CommentsDialog
from calibre.gui2.widgets import EnLineEdit, TagsLineEdit
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, REGEXP_MATCH
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import tweaks
from calibre.utils.date import dt_factory, qt_to_dt, isoformat
from calibre.utils.pyparsing import ParseException
from calibre.utils.search_query_parser import SearchQueryParser


class RatingDelegate(QStyledItemDelegate):
    COLOR    = QColor("blue")
    SIZE     = 16
    PEN      = QPen(COLOR, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self._parent = parent
        self.dummy = QModelIndex()
        self.star_path = QPainterPath()
        self.star_path.moveTo(90, 50)
        for i in range(1, 5):
            self.star_path.lineTo(50 + 40 * cos(0.8 * i * pi), \
                                  50 + 40 * sin(0.8 * i * pi))
        self.star_path.closeSubpath()
        self.star_path.setFillRule(Qt.WindingFill)
        gradient = QLinearGradient(0, 0, 0, 100)
        gradient.setColorAt(0.0, self.COLOR)
        gradient.setColorAt(1.0, self.COLOR)
        self.brush = QBrush(gradient)
        self.factor = self.SIZE/100.

    def sizeHint(self, option, index):
        #num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        return QSize(5*(self.SIZE), self.SIZE+4)

    def paint(self, painter, option, index):
        style = self._parent.style()
        option = QStyleOptionViewItemV4(option)
        self.initStyleOption(option, self.dummy)
        num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        def draw_star():
            painter.save()
            painter.scale(self.factor, self.factor)
            painter.translate(50.0, 50.0)
            painter.rotate(-20)
            painter.translate(-50.0, -50.0)
            painter.drawPath(self.star_path)
            painter.restore()

        painter.save()
        if hasattr(QStyle, 'CE_ItemViewItem'):
            style.drawControl(QStyle.CE_ItemViewItem, option,
                    painter, self._parent)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipRect(option.rect)
            y = option.rect.center().y()-self.SIZE/2.
            x = option.rect.left()
            painter.setPen(self.PEN)
            painter.setBrush(self.brush)
            painter.translate(x, y)
            i = 0
            while i < num:
                draw_star()
                painter.translate(self.SIZE, 0)
                i += 1
        except:
            traceback.print_exc()
        painter.restore()

    def createEditor(self, parent, option, index):
        sb = QStyledItemDelegate.createEditor(self, parent, option, index)
        sb.setMinimum(0)
        sb.setMaximum(5)
        return sb

class DateDelegate(QStyledItemDelegate):

    def displayText(self, val, locale):
        d = val.toDate()
        if d == UNDEFINED_DATE:
            return ''
        return d.toString('dd MMM yyyy')

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        stdformat = unicode(qde.displayFormat())
        if 'yyyy' not in stdformat:
            stdformat = stdformat.replace('yy', 'yyyy')
        qde.setDisplayFormat(stdformat)
        qde.setMinimumDate(UNDEFINED_DATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

class PubDateDelegate(QStyledItemDelegate):

    def displayText(self, val, locale):
        d = val.toDate()
        if d == UNDEFINED_DATE:
            return ''
        return d.toString('MMM yyyy')

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat('MM yyyy')
        qde.setMinimumDate(UNDEFINED_DATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

class TextDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        '''
        Delegate for text data. If auto_complete_function needs to return a list
        of text items to auto-complete with. The funciton is None no
        auto-complete will be used.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.auto_complete_function = None

    def set_auto_complete_function(self, f):
        self.auto_complete_function = f

    def createEditor(self, parent, option, index):
        editor = EnLineEdit(parent)
        if self.auto_complete_function:
            complete_items = [i[1] for i in self.auto_complete_function()]
            completer = QCompleter(complete_items, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.InlineCompletion)
            editor.setCompleter(completer)
        return editor

class TagsDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.db = None

    def set_database(self, db):
        self.db = db

    def createEditor(self, parent, option, index):
        if self.db:
            col = index.model().column_map[index.column()]
            if not index.model().is_custom_column(col):
                editor = TagsLineEdit(parent, self.db.all_tags())
            else:
                editor = TagsLineEdit(parent, sorted(list(self.db.all_custom(label=col))))
                return editor
        else:
            editor = EnLineEdit(parent)
        return editor

class CcDateDelegate(QStyledItemDelegate):
    '''
    Delegate for custom columns dates. Because this delegate stores the
    format as an instance variable, a new instance must be created for each
    column. This differs from all the other delegates.
    '''

    def set_format(self, format):
        if not format:
            self.format = 'dd MMM yyyy'
        else:
            self.format = format

    def displayText(self, val, locale):
        d = val.toDate()
        if d == UNDEFINED_DATE:
            return ''
        return d.toString(self.format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.format)
        qde.setMinimumDate(UNDEFINED_DATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

class CcTextDelegate(QStyledItemDelegate):
    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        typ = m.custom_columns[col]['datatype']
        if typ == 'int':
            editor = QSpinBox(parent)
            editor.setRange(-100, sys.maxint)
            editor.setSpecialValueText(_('Undefined'))
            editor.setSingleStep(1)
        elif typ == 'float':
            editor = QDoubleSpinBox(parent)
            editor.setSpecialValueText(_('Undefined'))
            editor.setRange(-100., float(sys.maxint))
            editor.setDecimals(2)
        else:
            editor = EnLineEdit(parent)
            complete_items = sorted(list(m.db.all_custom(label=col)))
            completer = QCompleter(complete_items, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
        return editor

class CcCommentsDelegate(QStyledItemDelegate):
    '''
    Delegate for comments data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        # db col is not named for the field, but for the table number. To get it,
        # gui column -> column label -> table number -> db column
        text = m.db.data[index.row()][m.db.FIELD_MAP[m.custom_columns[col]['num']]]
        editor = CommentsDialog(parent, text)
        d = editor.exec_()
        if d:
            m.setData(index, QVariant(editor.textbox.toPlainText()), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.textbox.toPlainText()), Qt.EditRole)

class CcBoolDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        items = [_('Y'), _('N'), ' ']
        icons = [I('ok.svg'), I('list_remove.svg'), I('blank.svg')]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            editor.addItem(QIcon(icon), text)
        return editor

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False, 2:None}[editor.currentIndex()]
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        # db col is not named for the field, but for the table number. To get it,
        # gui column -> column label -> table number -> db column
        val = m.db.data[index.row()][m.db.FIELD_MAP[m.custom_columns[m.column_map[index.column()]]['num']]]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            val = 1 if not val else 0
        else:
            val = 2 if val is None else 1 if not val else 0
        editor.setCurrentIndex(val)

class BooksModel(QAbstractTableModel):

    about_to_be_sorted = pyqtSignal(object, name='aboutToBeSorted')
    sorting_done       = pyqtSignal(object, name='sortingDone')
    database_changed   = pyqtSignal(object, name='databaseChanged')

    orig_headers = {
                        'title'     : _("Title"),
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
        self.editable_cols = ['title', 'authors', 'rating', 'publisher',
                              'tags', 'series', 'timestamp', 'pubdate']
        self.default_image = QImage(I('book.svg'))
        self.sorted_on = ('timestamp', Qt.AscendingOrder)
        self.sort_history = [self.sorted_on]
        self.last_search = '' # The last search performed on this model
        self.column_map = []
        self.headers = {}
        self.buffer_size = buffer
        self.cover_cache = None
        self.bool_yes_icon = QIcon(I('ok.svg'))
        self.bool_no_icon = QIcon(I('list_remove.svg'))
        self.bool_blank_icon = QIcon(I('blank.svg'))

    def is_custom_column(self, cc_label):
        return cc_label in self.custom_columns

    def clear_caches(self):
        if self.cover_cache:
            self.cover_cache.clear_cache()

    def read_config(self):
        self.use_roman_numbers = config['use_roman_numerals_for_series_number']
        cmap = config['column_map'][:] # force a copy
        self.headers = {}
        self.column_map = []
        for col in cmap: # take out any columns no longer in the db
            if col in self.orig_headers or col in self.custom_columns:
                self.column_map.append(col)
        for col in self.column_map:
            if col in self.orig_headers:
                self.headers[col] = self.orig_headers[col]
            elif col in self.custom_columns:
                self.headers[col] = self.custom_columns[col]['name']
        self.build_data_convertors()
        self.reset()
        self.emit(SIGNAL('columns_sorted()'))

    def set_database(self, db):
        self.db = db
        self.custom_columns = self.db.custom_column_label_map
        self.read_config()
        self.database_changed.emit(db)

    def refresh_ids(self, ids, current_row=-1):
        rows = self.db.refresh_ids(ids)
        if rows:
            self.refresh_rows(rows, current_row=current_row)

    def refresh_cover_cache(self, ids):
        if self.cover_cache:
            self.cover_cache.refresh(ids)

    def refresh_rows(self, rows, current_row=-1):
        for row in rows:
            if self.cover_cache:
                id = self.db.id(row)
                self.cover_cache.refresh([id])
            if row == current_row:
                self.emit(SIGNAL('new_bookdisplay_data(PyQt_PyObject)'),
                          self.get_book_display_info(row))
            self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                      self.index(row, 0), self.index(row, self.columnCount(QModelIndex())-1))

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
        self.emit(SIGNAL('count_changed(int)'), self.db.count())

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

    def search(self, text, refinement, reset=True):
        try:
            self.db.search(text)
        except ParseException:
            self.emit(SIGNAL('searched(PyQt_PyObject)'), False)
            return
        self.last_search = text
        if reset:
            self.clear_caches()
            self.reset()
        if self.last_search:
            self.emit(SIGNAL('searched(PyQt_PyObject)'), True)


    def sort(self, col, order, reset=True):
        if not self.db:
            return
        self.about_to_be_sorted.emit(self.db.id)
        ascending = order == Qt.AscendingOrder
        self.db.sort(self.column_map[col], ascending)
        if reset:
            self.clear_caches()
            self.reset()
        self.sorted_on = (self.column_map[col], order)
        self.sort_history.insert(0, self.sorted_on)
        del self.sort_history[3:] # clean up older searches
        self.sorting_done.emit(self.db.index)

    def refresh(self, reset=True):
        try:
            col = self.column_map.index(self.sorted_on[0])
        except:
            col = 0
        self.db.refresh(field=None)
        self.sort(col, self.sorted_on[1], reset=reset)

    def resort(self, reset=True):
        try:
            col = self.column_map.index(self.sorted_on[0])
        except:
            col = 0
        self.sort(col, self.sorted_on[1], reset=reset)

    def research(self, reset=True):
        self.search(self.last_search, False, reset=reset)

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
        comments = self.db.comments(idx)
        if not comments:
            comments = _('None')
        data[_('Comments')] = comments
        series = self.db.series(idx)
        if series:
            sidx = self.db.series_index(idx)
            sidx = fmt_sidx(sidx, use_roman = self.use_roman_numbers)
            data[_('Series')] = _('Book <font face="serif">%s</font> of %s.')%(sidx, series)

        return data

    def set_cache(self, idx):
        l, r = 0, self.count()-1
        if self.cover_cache:
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
        idx = current.row()
        self.set_cache(idx)
        data = self.get_book_display_info(idx)
        if emit_signal:
            self.emit(SIGNAL('new_bookdisplay_data(PyQt_PyObject)'), data)
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
            if mi.series is not None:
                mi.tag_order = { mi.series: self.db.books_in_series_of(id,
                    index_is_id=True)}
            ans.append(mi)
        return ans

    def get_metadata(self, rows, rows_are_ids=False, full_metadata=False):
        # Should this add the custom columns? It doesn't at the moment
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

    def get_preferred_formats_from_ids(self, ids, formats, paths=False,
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
                pt.seek(0)
                if set_metadata:
                    _set_metadata(pt, self.db.get_metadata(id, get_cover=True, index_is_id=True),
                                  format)
                pt.close() if paths else pt.seek(0)
                ans.append(pt)
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

    def cover(self, row_number):
        data = None
        try:
            id = self.db.id(row_number)
            if self.cover_cache:
                img = self.cover_cache.cover(id)
                if img:
                    if img.isNull():
                        img = self.default_image
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

        def series(r, idx=-1, siix=-1):
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
                return QVariant(UNDEFINED_DATE)

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

        def text_type(r, mult=False, idx=-1):
            text = self.db.data[r][idx]
            if text and mult:
                return QVariant(', '.join(sorted(text.split('|'))))
            return QVariant(text)

        def number_type(r, idx=-1):
            return QVariant(self.db.data[r][idx])

        self.dc = {
                   'title'    : functools.partial(text_type,
                                idx=self.db.FIELD_MAP['title'], mult=False),
                   'authors'  : functools.partial(authors,
                                idx=self.db.FIELD_MAP['authors']),
                   'size'     : functools.partial(size,
                                idx=self.db.FIELD_MAP['size']),
                   'timestamp': functools.partial(datetime_type,
                                idx=self.db.FIELD_MAP['timestamp']),
                   'pubdate'  : functools.partial(datetime_type,
                                idx=self.db.FIELD_MAP['pubdate']),
                   'rating'   : functools.partial(rating_type,
                                idx=self.db.FIELD_MAP['rating']),
                   'publisher': functools.partial(text_type,
                                idx=self.db.FIELD_MAP['publisher'], mult=False),
                   'tags'     : functools.partial(tags,
                                idx=self.db.FIELD_MAP['tags']),
                   'series'   : functools.partial(series,
                                idx=self.db.FIELD_MAP['series'],
                                siix=self.db.FIELD_MAP['series_index']),
                   }
        self.dc_decorator = {}

        # Add the custom columns to the data converters
        for col in self.custom_columns:
            idx = self.db.FIELD_MAP[self.custom_columns[col]['num']]
            datatype = self.custom_columns[col]['datatype']
            if datatype in ('text', 'comments'):
                self.dc[col] = functools.partial(text_type, idx=idx, mult=self.custom_columns[col]['is_multiple'])
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
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self.column_to_dc_map[col](index.row())
        elif role == Qt.DecorationRole:
            if self.column_to_dc_decorator_map[col] is not None:
                return self.column_to_dc_decorator_map[index.column()](index.row())
        #elif role == Qt.TextAlignmentRole and self.column_map[index.column()] in ('size', 'timestamp'):
        #    return QVariant(Qt.AlignVCenter | Qt.AlignCenter)
        #elif role == Qt.ToolTipRole and index.isValid():
        #    if self.column_map[index.column()] in self.editable_cols:
        #        return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        return NONE

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal:
            if section >= len(self.column_map): # same problem as in data, the column_map can be wrong
                return None
            if role == Qt.ToolTipRole:
                return QVariant(_('The lookup/search name is "{0}"').format(self.column_map[section]))
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
                if self.custom_columns[colhead]['editable']:
                    flags |= Qt.ItemIsEditable
        return flags

    def set_custom_column_data(self, row, colhead, value):
        typ = self.custom_columns[colhead]['datatype']
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
            if val.isNull() or not val.isValid():
                return False
            val = qt_to_dt(val, as_utc=False)
        self.db.set_custom(self.db.id(row), val, label=colhead, num=None, append=False, notify=True)
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
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                                index, index)
            if column == self.sorted_on[0]:
                self.resort()
        return True

    def set_search_restriction(self, s):
        self.db.data.set_search_restriction(s)

class BooksView(TableView):
    TIME_FMT = '%d %b %Y'
    wrapper = textwrap.TextWrapper(width=20)

    @classmethod
    def wrap(cls, s, width=20):
        cls.wrapper.width = width
        return cls.wrapper.fill(s)

    @classmethod
    def human_readable(cls, size, precision=1):
        """ Convert a size in bytes into megabytes """
        return ('%.'+str(precision)+'f') % ((size/(1024.*1024.)),)

    def __init__(self, parent, modelcls=BooksModel):
        TableView.__init__(self, parent)
        self.rating_delegate = RatingDelegate(self)
        self.timestamp_delegate = DateDelegate(self)
        self.pubdate_delegate = PubDateDelegate(self)
        self.tags_delegate = TagsDelegate(self)
        self.authors_delegate = TextDelegate(self)
        self.series_delegate = TextDelegate(self)
        self.publisher_delegate = TextDelegate(self)
        self.cc_text_delegate = CcTextDelegate(self)
        self.cc_bool_delegate = CcBoolDelegate(self)
        self.cc_comments_delegate = CcCommentsDelegate(self)
        self.display_parent = parent
        self._model = modelcls(self)
        self.setModel(self._model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.columns_sorted()
        QObject.connect(self.selectionModel(), SIGNAL('currentRowChanged(QModelIndex, QModelIndex)'),
                        self._model.current_changed)
        self.connect(self._model, SIGNAL('columns_sorted()'),
                self.columns_sorted, Qt.QueuedConnection)
        hv = self.verticalHeader()
        hv.setClickable(True)
        hv.setCursor(Qt.PointingHandCursor)
        self.selected_ids = []
        self._model.about_to_be_sorted.connect(self.about_to_be_sorted)
        self._model.sorting_done.connect(self.sorting_done)

    def about_to_be_sorted(self, idc):
        selected_rows = [r.row() for r in self.selectionModel().selectedRows()]
        self.selected_ids = [idc(r) for r in selected_rows]

    def sorting_done(self, indexc):
        if self.selected_ids:
            indices = [self.model().index(indexc(i), 0) for i in
                    self.selected_ids]
            sm = self.selectionModel()
            for idx in indices:
                sm.select(idx, sm.Select|sm.Rows)
        self.selected_ids = []

    def columns_sorted(self):
        for i in range(self.model().columnCount(None)):
            if self.itemDelegateForColumn(i) in (self.rating_delegate,
                    self.timestamp_delegate, self.pubdate_delegate):
                self.setItemDelegateForColumn(i, self.itemDelegate())

        cm = self._model.column_map

        if 'rating' in cm:
            self.setItemDelegateForColumn(cm.index('rating'), self.rating_delegate)
        if 'timestamp' in cm:
            self.setItemDelegateForColumn(cm.index('timestamp'), self.timestamp_delegate)
        if 'pubdate' in cm:
            self.setItemDelegateForColumn(cm.index('pubdate'), self.pubdate_delegate)
        if 'tags' in cm:
            self.setItemDelegateForColumn(cm.index('tags'), self.tags_delegate)
        if 'authors' in cm:
            self.setItemDelegateForColumn(cm.index('authors'), self.authors_delegate)
        if 'publisher' in cm:
            self.setItemDelegateForColumn(cm.index('publisher'), self.publisher_delegate)
        if 'series' in cm:
            self.setItemDelegateForColumn(cm.index('series'), self.series_delegate)
        for colhead in cm:
            if not self._model.is_custom_column(colhead):
                continue
            cc = self._model.custom_columns[colhead]
            if cc['datatype'] == 'datetime':
                delegate = CcDateDelegate(self)
                delegate.set_format(cc['display'].get('date_format',''))
                self.setItemDelegateForColumn(cm.index(colhead), delegate)
            elif cc['datatype'] == 'comments':
                self.setItemDelegateForColumn(cm.index(colhead), self.cc_comments_delegate)
            elif cc['datatype'] == 'text':
                if cc['is_multiple']:
                    self.setItemDelegateForColumn(cm.index(colhead), self.tags_delegate)
                else:
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
            elif cc['datatype'] in ('int', 'float'):
                self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
            elif cc['datatype'] == 'bool':
                self.setItemDelegateForColumn(cm.index(colhead), self.cc_bool_delegate)
            elif cc['datatype'] == 'rating':
                self.setItemDelegateForColumn(cm.index(colhead), self.rating_delegate)

    def set_context_menu(self, edit_metadata, send_to_device, convert, view,
                         save, open_folder, book_details, delete, similar_menu=None):
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.context_menu = QMenu(self)
        if edit_metadata is not None:
            self.context_menu.addAction(edit_metadata)
        if send_to_device is not None:
            self.context_menu.addAction(send_to_device)
        if convert is not None:
            self.context_menu.addAction(convert)
        self.context_menu.addAction(view)
        self.context_menu.addAction(save)
        if open_folder is not None:
            self.context_menu.addAction(open_folder)
        if delete is not None:
            self.context_menu.addAction(delete)
        if book_details is not None:
            self.context_menu.addAction(book_details)
        if similar_menu is not None:
            self.context_menu.addMenu(similar_menu)

    def contextMenuEvent(self, event):
        self.context_menu.popup(event.globalPos())
        event.accept()

    def restore_sort_at_startup(self, saved_history):
        if tweaks['sort_columns_at_startup'] is not None:
            saved_history = tweaks['sort_columns_at_startup']

        if saved_history is None:
            return
        for col,order in reversed(saved_history):
            self.sortByColumn(col, order)
        self.model().sort_history = saved_history

    def sortByColumn(self, colname, order):
        try:
            idx = self._model.column_map.index(colname)
        except ValueError:
            idx = 0
        TableView.sortByColumn(self, idx, order)

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            return [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)

        if paths:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.emit(SIGNAL('files_dropped(PyQt_PyObject)'), paths)

    def set_database(self, db):
        self._model.set_database(db)
        self.tags_delegate.set_database(db)
        self.authors_delegate.set_auto_complete_function(db.all_authors)
        self.series_delegate.set_auto_complete_function(db.all_series)
        self.publisher_delegate.set_auto_complete_function(db.all_publishers)

    def close(self):
        self._model.close()

    def set_editable(self, editable):
        self._model.set_editable(editable)

    def connect_to_search_box(self, sb, search_done):
        QObject.connect(sb, SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'),
                        self._model.search)
        self._search_done = search_done
        self.connect(self._model, SIGNAL('searched(PyQt_PyObject)'),
                self.search_done)

    def connect_to_restriction_set(self, tv):
        QObject.connect(tv, SIGNAL('restriction_set(PyQt_PyObject)'),
                        self._model.set_search_restriction) # must be synchronous (not queued)

    def connect_to_book_display(self, bd):
        QObject.connect(self._model, SIGNAL('new_bookdisplay_data(PyQt_PyObject)'),
                        bd)

    def search_done(self, ok):
        self._search_done(self, ok)

    def row_count(self):
        return self._model.count()


class DeviceBooksView(BooksView):

    def __init__(self, parent):
        BooksView.__init__(self, parent, DeviceBooksModel)
        self.columns_resized = False
        self.resize_on_select = False
        self.rating_delegate = None
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.setDragDropMode(self.NoDragDrop)
        self.setAcceptDrops(False)

    def set_database(self, db):
        self._model.set_database(db)

    def resizeColumnsToContents(self):
        QTableView.resizeColumnsToContents(self)
        self.columns_resized = True

    def connect_dirtied_signal(self, slot):
        QObject.connect(self._model, SIGNAL('booklist_dirtied()'), slot)

    def sortByColumn(self, col, order):
        TableView.sortByColumn(self, col, order)

    def dropEvent(self, *args):
        error_dialog(self, _('Not allowed'),
        _('Dropping onto a device is not supported. First add the book to the calibre library.')).exec_()

class OnDeviceSearch(SearchQueryParser):

    def __init__(self, model):
        SearchQueryParser.__init__(self)
        self.model = model

    def universal_set(self):
        return set(range(0, len(self.model.db)))

    def get_matches(self, location, query):
        location = location.lower().strip()

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

        if location not in ('title', 'author', 'tag', 'all', 'format'):
            return set([])
        matches = set([])
        locations = ['title', 'author', 'tag', 'format'] if location == 'all' else [location]
        q = {
             'title' : lambda x : getattr(x, 'title').lower(),
             'author': lambda x: getattr(x, 'authors').lower(),
             'tag':lambda x: ','.join(getattr(x, 'tags')).lower(),
             'format':lambda x: os.path.splitext(x.path)[1].lower()
             }
        for index, row in enumerate(self.model.db):
            for locvalue in locations:
                accessor = q[locvalue]
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'tag':
                        vals = accessor(row).split(',')
                    else:
                        vals = [accessor(row)]
                    if _match(query, vals, m):
                        matches.add(index)
                        break
                except ValueError: # Unicode errors
                    traceback.print_exc()
        return matches


class DeviceBooksModel(BooksModel):

    def __init__(self, parent):
        BooksModel.__init__(self, parent)
        self.db  = []
        self.map = []
        self.sorted_map = []
        self.unknown = _('Unknown')
        self.marked_for_deletion = {}
        self.search_engine = OnDeviceSearch(self)
        self.editable = True

    def mark_for_deletion(self, job, rows):
        self.marked_for_deletion[job] = self.indices(rows)
        for row in rows:
            indices = self.row_indices(row)
            self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), indices[0], indices[-1])

    def deletion_done(self, job, succeeded=True):
        if not self.marked_for_deletion.has_key(job):
            return
        rows = self.marked_for_deletion.pop(job)
        for row in rows:
            if not succeeded:
                indices = self.row_indices(self.index(row, 0))
                self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), indices[0], indices[-1])

    def paths_deleted(self, paths):
        self.map = list(range(0, len(self.db)))
        self.resort(False)
        self.research(True)

    def indices_to_be_deleted(self):
        ans = []
        for v in self.marked_for_deletion.values():
            ans.extend(v)
        return ans

    def flags(self, index):
        if self.map[index.row()] in self.indices_to_be_deleted():
            return Qt.ItemIsUserCheckable  # Can't figure out how to get the disabled flag in python
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid() and self.editable:
            if index.column() in [0, 1] or (index.column() == 4 and self.db.supports_tags()):
                flags |= Qt.ItemIsEditable
        return flags


    def search(self, text, refinement, reset=True):
        if not text or not text.strip():
            self.map = list(range(len(self.db)))
        else:
            try:
                matches = self.search_engine.parse(text)
            except ParseException:
                self.emit(SIGNAL('searched(PyQt_PyObject)'), False)
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
            self.emit(SIGNAL('searched(PyQt_PyObject)'), True)


    def resort(self, reset):
        self.sort(self.sorted_on[0], self.sorted_on[1], reset=reset)

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
            x, y = ','.join(self.db[x].tags), ','.join(self.db[y].tags)
            return cmp(x, y)
        fcmp = strcmp('title_sorter') if col == 0 else strcmp('authors') if col == 1 else \
               sizecmp if col == 2 else datecmp if col == 3 else tagscmp
        self.map.sort(cmp=fcmp, reverse=descending)
        if len(self.map) == len(self.db):
            self.sorted_map = list(self.map)
        else:
            self.sorted_map = list(range(len(self.db)))
            self.sorted_map.sort(cmp=fcmp, reverse=descending)
        self.sorted_on = (col, order)
        if reset:
            self.reset()

    def columnCount(self, parent):
        if parent and parent.isValid():
            return 0
        return 5

    def rowCount(self, parent):
        if parent and parent.isValid():
            return 0
        return len(self.map)

    def set_database(self, db):
        self.db = db
        self.map = list(range(0, len(db)))

    def current_changed(self, current, previous):
        data = {}
        item = self.db[self.map[current.row()]]
        cdata = item.thumbnail
        if cdata:
            img = QImage()
            img.loadFromData(cdata)
            if img.isNull():
                img = self.default_image
            data['cover'] = img
        type = _('Unknown')
        ext = os.path.splitext(item.path)[1]
        if ext:
            type = ext[1:].lower()
        data[_('Format')] = type
        data[_('Path')] = item.path
        dt = dt_factory(item.datetime, assume_utc=True)
        data[_('Timestamp')] = isoformat(dt, sep=' ', as_utc=False)
        data[_('Tags')] = ', '.join(item.tags)
        self.emit(SIGNAL('new_bookdisplay_data(PyQt_PyObject)'), data)

    def paths(self, rows):
        return [self.db[self.map[r.row()]].path for r in rows ]

    def indices(self, rows):
        '''
        Return indices into underlying database from rows
        '''
        return [ self.map[r.row()] for r in rows]


    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            row, col = index.row(), index.column()
            if col == 0:
                text = self.db[self.map[row]].title
                if not text:
                    text = self.unknown
                return QVariant(text)
            elif col == 1:
                au = self.db[self.map[row]].authors
                if not au:
                    au = self.unknown
                if role == Qt.EditRole:
                    return QVariant(au)
                authors = string_to_authors(au)
                return QVariant("\n".join(authors))
            elif col == 2:
                size = self.db[self.map[row]].size
                return QVariant(BooksView.human_readable(size))
            elif col == 3:
                dt = self.db[self.map[row]].datetime
                dt = dt_factory(dt, assume_utc=True, as_utc=False)
                return QVariant(strftime(BooksView.TIME_FMT, dt.timetuple()))
            elif col == 4:
                tags = self.db[self.map[row]].tags
                if tags:
                    return QVariant(', '.join(tags))
        elif role == Qt.TextAlignmentRole and index.column() in [2, 3]:
            return QVariant(Qt.AlignRight | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole and index.isValid():
            if self.map[index.row()] in self.indices_to_be_deleted():
                return QVariant('Marked for deletion')
            col = index.column()
            if col in [0, 1] or (col == 4 and self.db.supports_tags()):
                return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        return NONE

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ""
        if orientation == Qt.Horizontal:
            if   section == 0: text = _("Title")
            elif section == 1: text = _("Author(s)")
            elif section == 2: text = _("Size (MB)")
            elif section == 3: text = _("Date")
            elif section == 4: text = _("Tags")
            return QVariant(text)
        else:
            return QVariant(section+1)

    def setData(self, index, value, role):
        done = False
        if role == Qt.EditRole:
            row, col = index.row(), index.column()
            if col in [2, 3]:
                return False
            val = unicode(value.toString()).strip()
            idx = self.map[row]
            if col == 0:
                self.db[idx].title = val
                self.db[idx].title_sorter = val
            elif col == 1:
                self.db[idx].authors = val
            elif col == 4:
                tags = [i.strip() for i in val.split(',')]
                tags = [t for t in tags if t]
                self.db.set_tags(self.db[idx], tags)
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
            self.emit(SIGNAL('booklist_dirtied()'))
            if col == self.sorted_on[0]:
                self.sort(col, self.sorted_on[1])
            done = True
        return done

    def set_editable(self, editable):
        self.editable = editable

    def set_search_restriction(self, s):
        pass

