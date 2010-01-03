from calibre.ebooks.metadata import authors_to_string
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, textwrap, traceback, time, re
from datetime import timedelta, datetime
from operator import attrgetter

from math import cos, sin, pi
from PyQt4.QtGui import QTableView, QAbstractItemView, QColor, \
                        QItemDelegate, QPainterPath, QLinearGradient, QBrush, \
                        QPen, QStyle, QPainter, \
                        QImage, QApplication, QMenu, \
                        QStyledItemDelegate, QCompleter
from PyQt4.QtCore import QAbstractTableModel, QVariant, Qt, pyqtSignal, \
                         SIGNAL, QObject, QSize, QModelIndex, QDate

from calibre import strftime
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.pyparsing import ParseException
from calibre.library.database2 import FIELD_MAP
from calibre.gui2 import NONE, TableView, qstring_to_unicode, config, \
                         error_dialog
from calibre.gui2.widgets import EnLineEdit, TagsLineEdit
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.ebooks.metadata.meta import set_metadata as _set_metadata
from calibre.ebooks.metadata import string_to_authors, fmt_sidx

class LibraryDelegate(QItemDelegate):
    COLOR    = QColor("blue")
    SIZE     = 16
    PEN      = QPen(COLOR, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def __init__(self, parent):
        QItemDelegate.__init__(self, parent)
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
            QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        self.drawFocus(painter, option, option.rect)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipRect(option.rect)
            y = option.rect.center().y()-self.SIZE/2.
            x = option.rect.right()  - self.SIZE
            painter.setPen(self.PEN)
            painter.setBrush(self.brush)
            painter.translate(x, y)
            i = 0
            while i < num:
                draw_star()
                painter.translate(-self.SIZE, 0)
                i += 1
        except Exception, e:
            traceback.print_exc(e)
        painter.restore()

    def createEditor(self, parent, option, index):
        sb = QItemDelegate.createEditor(self, parent, option, index)
        sb.setMinimum(0)
        sb.setMaximum(5)
        return sb

class DateDelegate(QStyledItemDelegate):

    def displayText(self, val, locale):
        d = val.toDate()
        return d.toString('dd MMM yyyy')

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(unicode(qde.displayFormat()).replace('yy', 'yyyy'))
        qde.setMinimumDate(QDate(101,1,1))
        qde.setCalendarPopup(True)
        return qde

class PubDateDelegate(QStyledItemDelegate):

    def displayText(self, val, locale):
        return val.toDate().toString('MMM yyyy')

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat('MM yyyy')
        qde.setMinimumDate(QDate(101,1,1))
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
            editor = TagsLineEdit(parent, self.db.all_tags())
        else:
            editor = EnLineEdit(parent)
        return editor

class BooksModel(QAbstractTableModel):

    about_to_be_sorted = pyqtSignal(object, name='aboutToBeSorted')
    sorting_done       = pyqtSignal(object, name='sortingDone')

    headers = {
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
        self.column_map = config['column_map']
        self.editable_cols = ['title', 'authors', 'rating', 'publisher',
                              'tags', 'series', 'timestamp', 'pubdate']
        self.default_image = QImage(I('book.svg'))
        self.sorted_on = ('timestamp', Qt.AscendingOrder)
        self.last_search = '' # The last search performed on this model
        self.read_config()
        self.buffer_size = buffer
        self.cover_cache = None

    def clear_caches(self):
        if self.cover_cache:
            self.cover_cache.clear_cache()

    def read_config(self):
        self.use_roman_numbers = config['use_roman_numerals_for_series_number']
        cols = config['column_map']
        if cols != self.column_map:
            self.column_map = cols
            self.reset()
            self.emit(SIGNAL('columns_sorted()'))

    def set_database(self, db):
        self.db = db
        self.build_data_convertors()

    def refresh_ids(self, ids, current_row=-1):
        rows = self.db.refresh_ids(ids)
        if rows:
            self.refresh_rows(rows, current_row=current_row)

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
        self.sorting_done.emit(self.db.index)

    def refresh(self, reset=True):
        try:
            col = self.column_map.index(self.sorted_on[0])
        except:
            col = 0
        self.db.refresh(field=self.column_map[col],
                        ascending=self.sorted_on[1]==Qt.AscendingOrder)
        if reset:
            self.reset()

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
                pt.write(self.db.format(id, format, index_is_id=True))
                pt.flush()
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
                pt.write(self.db.format(row, format))
                pt.flush()
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

        tidx = FIELD_MAP['title']
        aidx = FIELD_MAP['authors']
        sidx = FIELD_MAP['size']
        ridx = FIELD_MAP['rating']
        pidx = FIELD_MAP['publisher']
        tmdx = FIELD_MAP['timestamp']
        pddx = FIELD_MAP['pubdate']
        srdx = FIELD_MAP['series']
        tgdx = FIELD_MAP['tags']
        siix = FIELD_MAP['series_index']

        def authors(r):
            au = self.db.data[r][aidx]
            if au:
                au = [a.strip().replace('|', ',') for a in au.split(',')]
                return ' & '.join(au)

        def timestamp(r):
            dt = self.db.data[r][tmdx]
            if dt:
                dt = dt - timedelta(seconds=time.timezone) + timedelta(hours=time.daylight)
                return QDate(dt.year, dt.month, dt.day)

        def pubdate(r):
            dt = self.db.data[r][pddx]
            if dt:
                dt = dt - timedelta(seconds=time.timezone) + timedelta(hours=time.daylight)
                return QDate(dt.year, dt.month, dt.day)

        def rating(r):
            r = self.db.data[r][ridx]
            r = r/2 if r else 0
            return r

        def publisher(r):
            pub = self.db.data[r][pidx]
            if pub:
                return pub

        def tags(r):
            tags = self.db.data[r][tgdx]
            if tags:
                return ', '.join(sorted(tags.split(',')))

        def series(r):
            series = self.db.data[r][srdx]
            if series:
                idx = fmt_sidx(self.db.data[r][siix])
                return series + ' [%s]'%idx
        def size(r):
            size = self.db.data[r][sidx]
            if size:
                return '%.1f'%(float(size)/(1024*1024))

        self.dc = {
                   'title'    : lambda r : self.db.data[r][tidx],
                   'authors'  : authors,
                   'size'     : size,
                   'timestamp': timestamp,
                   'pubdate' : pubdate,
                   'rating'   : rating,
                   'publisher': publisher,
                   'tags'     : tags,
                   'series'   : series,
                   }

    def data(self, index, role):
        if role in (Qt.DisplayRole, Qt.EditRole):
            ans = self.dc[self.column_map[index.column()]](index.row())
            return NONE if ans is None else QVariant(ans)
        #elif role == Qt.TextAlignmentRole and self.column_map[index.column()] in ('size', 'timestamp'):
        #    return QVariant(Qt.AlignVCenter | Qt.AlignCenter)
        #elif role == Qt.ToolTipRole and index.isValid():
        #    if self.column_map[index.column()] in self.editable_cols:
        #        return QVariant(_("Double click to <b>edit</b> me<br><br>"))
        return NONE

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:
            return QVariant(self.headers[self.column_map[section]])
        else:
            return QVariant(section+1)

    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():
            if self.column_map[index.column()] in self.editable_cols:
                flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            row, col = index.row(), index.column()
            column = self.column_map[col]
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
                    ni = self.db.get_next_series_num_for(val)
                    if ni != 1:
                        self.db.set_series_index(id, ni)
                if val:
                    self.db.set_series(id, val)
            elif column == 'timestamp':
                if val.isNull() or not val.isValid():
                    return False
                dt = datetime(val.year(), val.month(), val.day()) + timedelta(seconds=time.timezone) - timedelta(hours=time.daylight)
                self.db.set_timestamp(id, dt)
            elif column == 'pubdate':
                if val.isNull() or not val.isValid():
                    return False
                dt = datetime(val.year(), val.month(), val.day()) + timedelta(seconds=time.timezone) - timedelta(hours=time.daylight)
                self.db.set_pubdate(id, dt)
            else:
                self.db.set(row, column, val)
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                                index, index)
            if column == self.sorted_on[0]:
                self.resort()

        return True

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
        self.rating_delegate = LibraryDelegate(self)
        self.timestamp_delegate = DateDelegate(self)
        self.pubdate_delegate = PubDateDelegate(self)
        self.tags_delegate = TagsDelegate(self)
        self.authors_delegate = TextDelegate(self)
        self.series_delegate = TextDelegate(self)
        self.publisher_delegate = TextDelegate(self)
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
            urls = [qstring_to_unicode(u.toLocalFile()) for u in event.mimeData().urls()]
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

    def connect_to_book_display(self, bd):
        QObject.connect(self._model, SIGNAL('new_bookdisplay_data(PyQt_PyObject)'),
                        bd)

    def search_done(self, ok):
        self._search_done(self, ok)


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
        query = query.lower().strip()
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
        for i, v in enumerate(locations):
            locations[i] = q[v]
        for i, r in enumerate(self.model.db):
            for loc in locations:
                if query in loc(r):
                    matches.add(i)
                    break
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
            return cmp(datetime(*x[0:6]), datetime(*y[0:6]))
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
        dt = item.datetime
        dt = datetime(*dt[0:6])
        dt = dt - timedelta(seconds=time.timezone) + timedelta(hours=time.daylight)
        data[_('Timestamp')] = strftime('%a %b %d %H:%M:%S %Y', dt.timetuple())
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
                dt = datetime(*dt[0:6])
                dt = dt - timedelta(seconds=time.timezone) + timedelta(hours=time.daylight)
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
            val = qstring_to_unicode(value.toString()).strip()
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



