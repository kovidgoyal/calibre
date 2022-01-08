#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

DEBUG_DIALOG = False

# Imports {{{
import os, time
from threading import Thread, Event
from operator import attrgetter
from io import BytesIO

from qt.core import (
    QStyledItemDelegate, QTextDocument, QRectF, QIcon, Qt, QApplication,
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QStyle, QStackedWidget,
    QWidget, QTableView, QGridLayout, QPalette, QTimer, pyqtSignal,
    QAbstractTableModel, QSize, QListView, QPixmap, QModelIndex,
    QAbstractListModel, QRect, QTextBrowser, QStringListModel, QMenu, QItemSelectionModel,
    QCursor, QHBoxLayout, QPushButton, QSizePolicy, QSplitter, QAbstractItemView)

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata import authors_to_string, rating_to_stars
from calibre.utils.logging import GUILog as Log
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF
from calibre.gui2 import error_dialog, rating_font, gprefs
from calibre.gui2.progress_indicator import SpinAnimator
from calibre.gui2.widgets2 import HTMLDisplay
from calibre.utils.date import (utcnow, fromordinal, format_date,
        UNDEFINED_DATE, as_utc)
from calibre.library.comments import comments_to_html
from calibre import force_unicode
from calibre.utils.ipc.simple_worker import fork_job, WorkerError
from calibre.ptempfile import TemporaryDirectory
from polyglot.builtins import iteritems, itervalues
from polyglot.queue import Queue, Empty
# }}}


class RichTextDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent=None, max_width=160):
        QStyledItemDelegate.__init__(self, parent)
        self.max_width = max_width
        self.dummy_model = QStringListModel([' '], self)
        self.dummy_index = self.dummy_model.index(0)

    def to_doc(self, index, option=None):
        doc = QTextDocument()
        if option is not None and option.state & QStyle.StateFlag.State_Selected:
            p = option.palette
            group = (QPalette.ColorGroup.Active if option.state & QStyle.StateFlag.State_Active else
                    QPalette.ColorGroup.Inactive)
            c = p.color(group, QPalette.ColorRole.HighlightedText)
            c = 'rgb(%d, %d, %d)'%c.getRgb()[:3]
            doc.setDefaultStyleSheet(' * { color: %s }'%c)
        doc.setHtml(index.data() or '')
        return doc

    def sizeHint(self, option, index):
        doc = self.to_doc(index, option=option)
        ans = doc.size().toSize()
        if ans.width() > self.max_width - 10:
            ans.setWidth(self.max_width)
        ans.setHeight(ans.height()+10)
        return ans

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, self.dummy_index)
        painter.save()
        painter.setClipRect(QRectF(option.rect))
        painter.translate(option.rect.topLeft())
        self.to_doc(index, option).drawContents(painter)
        painter.restore()
# }}}


class CoverDelegate(QStyledItemDelegate):  # {{{

    ICON_SIZE = 150, 200

    needs_redraw = pyqtSignal()

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.animator = SpinAnimator(self)
        self.animator.updated.connect(self.needs_redraw)
        self.color = parent.palette().color(QPalette.ColorRole.WindowText)
        self.spinner_width = 64

    def start_animation(self):
        self.animator.start()

    def stop_animation(self):
        self.animator.stop()

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        style = QApplication.style()
        waiting = self.animator.is_running() and bool(index.data(Qt.ItemDataRole.UserRole))
        if waiting:
            rect = QRect(0, 0, self.spinner_width, self.spinner_width)
            rect.moveCenter(option.rect.center())
            self.animator.draw(painter, rect, self.color)
        else:
            # Ensure the cover is rendered over any selection rect
            style.drawItemPixmap(painter, option.rect, Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter,
                QPixmap(index.data(Qt.ItemDataRole.DecorationRole)))

# }}}


class ResultsModel(QAbstractTableModel):  # {{{

    COLUMNS = (
            '#', _('Title'), _('Published'), _('Has cover'), _('Has summary')
            )
    HTML_COLS = (1, 2)
    ICON_COLS = (3, 4)

    def __init__(self, results, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.results = results
        self.yes_icon = (QIcon.ic('ok.png'))

    def rowCount(self, parent=None):
        return len(self.results)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            try:
                return (self.COLUMNS[section])
            except:
                return None
        return None

    def data_as_text(self, book, col):
        if col == 0:
            return str(book.gui_rank+1)
        if col == 1:
            t = book.title if book.title else _('Unknown')
            a = authors_to_string(book.authors) if book.authors else ''
            return f'<b>{t}</b><br><i>{a}</i>'
        if col == 2:
            d = format_date(book.pubdate, 'yyyy') if book.pubdate else _('Unknown')
            p = book.publisher if book.publisher else ''
            return f'<b>{d}</b><br><i>{p}</i>'

    def data(self, index, role):
        row, col = index.row(), index.column()
        try:
            book = self.results[row]
        except:
            return None
        if role == Qt.ItemDataRole.DisplayRole and col not in self.ICON_COLS:
            res = self.data_as_text(book, col)
            if res:
                return (res)
            return None
        elif role == Qt.ItemDataRole.DecorationRole and col in self.ICON_COLS:
            if col == 3 and getattr(book, 'has_cached_cover_url', False):
                return self.yes_icon
            if col == 4 and book.comments:
                return self.yes_icon
        elif role == Qt.ItemDataRole.UserRole:
            return book
        elif role == Qt.ItemDataRole.ToolTipRole and col == 3:
            return (
                _('The "has cover" indication is not fully\n'
                    'reliable. Sometimes results marked as not\n'
                    'having a cover will find a cover in the download\n'
                    'cover stage, and vice versa.'))

        return None

    def sort(self, col, order=Qt.SortOrder.AscendingOrder):
        key = lambda x: x
        if col == 0:
            key = attrgetter('gui_rank')
        elif col == 1:
            key = attrgetter('title')
        elif col == 2:
            def dategetter(x):
                x = getattr(x, 'pubdate', None)
                if x is None:
                    x = UNDEFINED_DATE
                return as_utc(x)
            key = dategetter
        elif col == 3:
            key = attrgetter('has_cached_cover_url')
        elif key == 4:
            key = lambda x: bool(x.comments)

        self.beginResetModel()
        self.results.sort(key=key, reverse=order==Qt.SortOrder.AscendingOrder)
        self.endResetModel()

# }}}


class ResultsView(QTableView):  # {{{

    show_details_signal = pyqtSignal(object)
    book_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.rt_delegate = RichTextDelegate(self)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setIconSize(QSize(24, 24))
        self.clicked.connect(self.show_details)
        self.doubleClicked.connect(self.select_index)
        self.setSortingEnabled(True)

    def show_results(self, results):
        self._model = ResultsModel(results, self)
        self.setModel(self._model)
        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)
        self.resizeRowsToContents()
        self.resizeColumnsToContents()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        idx = self.model().index(0, 0)
        if idx.isValid() and self.model().rowCount() > 0:
            self.show_details(idx)
            sm = self.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect|QItemSelectionModel.SelectionFlag.Rows)

    def resize_delegate(self):
        self.rt_delegate.max_width = int(self.width()/2.1)
        self.resizeColumnsToContents()

    def resizeEvent(self, ev):
        ret = super().resizeEvent(ev)
        self.resize_delegate()
        return ret

    def currentChanged(self, current, previous):
        ret = QTableView.currentChanged(self, current, previous)
        self.show_details(current)
        return ret

    def show_details(self, index):
        f = rating_font()
        book = self.model().data(index, Qt.ItemDataRole.UserRole)
        parts = [
            '<center>',
            '<h2>%s</h2>'%book.title,
            '<div><i>%s</i></div>'%authors_to_string(book.authors),
        ]
        if not book.is_null('series'):
            series = book.format_field('series')
            if series[1]:
                parts.append('<div>%s: %s</div>'%series)
        if not book.is_null('rating'):
            style = 'style=\'font-family:"%s"\''%f
            parts.append('<div %s>%s</div>'%(style, rating_to_stars(int(2 * book.rating))))
        parts.append('</center>')
        if book.identifiers:
            urls = urls_from_identifiers(book.identifiers)
            ids = ['<a href="%s">%s</a>'%(url, name) for name, ign, ign, url in urls]
            if ids:
                parts.append('<div><b>%s:</b> %s</div><br>'%(_('See at'), ', '.join(ids)))
        if book.tags:
            parts.append('<div>%s</div><div>\u00a0</div>'%', '.join(book.tags))
        if book.comments:
            parts.append(comments_to_html(book.comments))

        self.show_details_signal.emit(''.join(parts))

    def select_index(self, index):
        if self.model() is None:
            return
        if not index.isValid():
            index = self.model().index(0, 0)
        book = self.model().data(index, Qt.ItemDataRole.UserRole)
        self.book_selected.emit(book)

    def get_result(self):
        self.select_index(self.currentIndex())

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            ac = QAbstractItemView.CursorAction.MoveDown if ev.key() == Qt.Key.Key_Right else QAbstractItemView.CursorAction.MoveUp
            index = self.moveCursor(ac, ev.modifiers())
            if index.isValid() and index != self.currentIndex():
                m = self.selectionModel()
                m.select(index, QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Current|QItemSelectionModel.SelectionFlag.Rows)
                self.setCurrentIndex(index)
                ev.accept()
                return
        return QTableView.keyPressEvent(self, ev)

# }}}


class Comments(HTMLDisplay):  # {{{

    def __init__(self, parent=None):
        HTMLDisplay.__init__(self, parent)
        self.setAcceptDrops(False)
        self.wait_timer = QTimer(self)
        self.wait_timer.timeout.connect(self.update_wait)
        self.wait_timer.setInterval(800)
        self.dots_count = 0
        self.anchor_clicked.connect(self.link_activated)

    def link_activated(self, url):
        from calibre.gui2 import open_url
        if url.scheme() in {'http', 'https'}:
            open_url(url)

    def show_wait(self):
        self.dots_count = 0
        self.wait_timer.start()
        self.update_wait()

    def update_wait(self):
        self.dots_count += 1
        self.dots_count %= 10
        self.dots_count = self.dots_count or 1
        self.setHtml(
            '<h2>'+_('Please wait')+
            '<br><span id="dots">{}</span></h2>'.format('.' * self.dots_count))

    def show_data(self, html):
        self.wait_timer.stop()

        def color_to_string(col):
            ans = '#000000'
            if col.isValid():
                col = col.toRgb()
                if col.isValid():
                    ans = str(col.name())
            return ans

        c = color_to_string(QApplication.palette().color(QPalette.ColorGroup.Normal,
                        QPalette.ColorRole.WindowText))
        templ = '''\
        <html>
            <head>
            <style type="text/css">
                body, td {background-color: transparent; color: %s }
                a { text-decoration: none; }
                div.description { margin-top: 0; padding-top: 0; text-indent: 0 }
                table { margin-bottom: 0; padding-bottom: 0; }
            </style>
            </head>
            <body>
            <div class="description">
            %%s
            </div>
            </body>
        <html>
        '''%(c,)
        self.setHtml(templ%html)
# }}}


class IdentifyWorker(Thread):  # {{{

    def __init__(self, log, abort, title, authors, identifiers, caches):
        Thread.__init__(self)
        self.daemon = True

        self.log, self.abort = log, abort
        self.title, self.authors, self.identifiers = (title, authors,
                identifiers)

        self.results = []
        self.error = None
        self.caches = caches

    def sample_results(self):
        m1 = Metadata('The Great Gatsby', ['Francis Scott Fitzgerald'])
        m2 = Metadata('The Great Gatsby - An extra long title to test resizing', ['F. Scott Fitzgerald'])
        m1.has_cached_cover_url = True
        m2.has_cached_cover_url = False
        m1.comments  = 'Some comments '*10
        m1.tags = ['tag%d'%i for i in range(20)]
        m1.rating = 4.4
        m1.language = 'en'
        m2.language = 'fr'
        m1.pubdate = utcnow()
        m2.pubdate = fromordinal(1000000)
        m1.publisher = 'Publisher 1'
        m2.publisher = 'Publisher 2'

        return [m1, m2]

    def run(self):
        try:
            if DEBUG_DIALOG:
                self.results = self.sample_results()
            else:
                res = fork_job(
                        'calibre.ebooks.metadata.sources.worker',
                        'single_identify', (self.title, self.authors,
                            self.identifiers), no_output=True, abort=self.abort)
                self.results, covers, caches, log_dump = res['result']
                self.results = [OPF(BytesIO(r), basedir=os.getcwd(),
                    populate_spine=False).to_book_metadata() for r in self.results]
                for r, cov in zip(self.results, covers):
                    r.has_cached_cover_url = cov
                self.caches.update(caches)
                self.log.load(log_dump)
            for i, result in enumerate(self.results):
                result.gui_rank = i
        except WorkerError as e:
            self.error = force_unicode(e.orig_tb)
        except:
            import traceback
            self.error = force_unicode(traceback.format_exc())

# }}}


class IdentifyWidget(QWidget):  # {{{

    rejected = pyqtSignal()
    results_found = pyqtSignal()
    book_selected = pyqtSignal(object, object)

    def __init__(self, log, parent=None):
        QWidget.__init__(self, parent)
        self.log = log
        self.abort = Event()
        self.caches = {}

        self.l = l = QVBoxLayout(self)

        names = ['<b>'+p.name+'</b>' for p in metadata_plugins(['identify']) if
                p.is_configured()]
        self.top = QLabel('<p>'+_('calibre is downloading metadata from: ') +
            ', '.join(names))
        self.top.setWordWrap(True)
        l.addWidget(self.top)

        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s, 100)
        self.results_view = ResultsView(self)
        self.results_view.book_selected.connect(self.emit_book_selected)
        self.get_result = self.results_view.get_result
        s.addWidget(self.results_view)

        self.comments_view = Comments(self)
        s.addWidget(self.comments_view)
        s.setStretchFactor(0, 2)
        s.setStretchFactor(1, 1)

        self.results_view.show_details_signal.connect(self.comments_view.show_data)

        self.query = QLabel('download starting...')
        self.query.setWordWrap(True)
        self.query.setTextFormat(Qt.TextFormat.PlainText)
        l.addWidget(self.query)

        self.comments_view.show_wait()
        state = gprefs.get('metadata-download-identify-widget-splitter-state')
        if state is not None:
            s.restoreState(state)

    def save_state(self):
        gprefs['metadata-download-identify-widget-splitter-state'] = bytearray(self.splitter.saveState())

    def emit_book_selected(self, book):
        self.book_selected.emit(book, self.caches)

    def start(self, title=None, authors=None, identifiers={}):
        self.log.clear()
        self.log('Starting download')
        parts, simple_desc = [], ''
        if title:
            parts.append('title:'+title)
            simple_desc += _('Title: %s ') % title
        if authors:
            parts.append('authors:'+authors_to_string(authors))
            simple_desc += _('Authors: %s ') % authors_to_string(authors)
        if identifiers:
            x = ', '.join('%s:%s'%(k, v) for k, v in iteritems(identifiers))
            parts.append(x)
            if 'isbn' in identifiers:
                simple_desc += 'ISBN: %s' % identifiers['isbn']
        self.query.setText(simple_desc)
        self.log(str(self.query.text()))

        self.worker = IdentifyWorker(self.log, self.abort, title,
                authors, identifiers, self.caches)

        self.worker.start()

        QTimer.singleShot(50, self.update)

    def update(self):
        if self.worker.is_alive():
            QTimer.singleShot(50, self.update)
        else:
            self.process_results()

    def process_results(self):
        if self.worker.error is not None:
            error_dialog(self, _('Download failed'),
                    _('Failed to download metadata. Click '
                        'Show Details to see details'),
                    show=True, det_msg=self.worker.error)
            self.rejected.emit()
            return

        if not self.worker.results:
            log = ''.join(self.log.plain_text)
            error_dialog(self, _('No matches found'), '<p>' +
                    _('Failed to find any books that '
                        'match your search. Try making the search <b>less '
                        'specific</b>. For example, use only the author\'s '
                        'last name and a single distinctive word from '
                        'the title.<p>To see the full log, click "Show details".'),
                    show=True, det_msg=log)
            self.rejected.emit()
            return

        self.results_view.show_results(self.worker.results)
        self.results_found.emit()

    def cancel(self):
        self.abort.set()
# }}}


class CoverWorker(Thread):  # {{{

    def __init__(self, log, abort, title, authors, identifiers, caches):
        Thread.__init__(self, name='CoverWorker')
        self.daemon = True

        self.log, self.abort = log, abort
        self.title, self.authors, self.identifiers = (title, authors,
                identifiers)
        self.caches = caches

        self.rq = Queue()
        self.error = None

    def fake_run(self):
        images = ['donate.png', 'config.png', 'column.png', 'eject.png', ]
        time.sleep(2)
        for pl, im in zip(metadata_plugins(['cover']), images):
            self.rq.put((pl.name, 1, 1, 'png', I(im, data=True)))

    def run(self):
        try:
            if DEBUG_DIALOG:
                self.fake_run()
            else:
                self.run_fork()
        except WorkerError as e:
            self.error = force_unicode(e.orig_tb)
        except:
            import traceback
            self.error = force_unicode(traceback.format_exc())

    def run_fork(self):
        with TemporaryDirectory('_single_metadata_download') as tdir:
            self.keep_going = True
            t = Thread(target=self.monitor_tdir, args=(tdir,))
            t.daemon = True
            t.start()

            try:
                res = fork_job('calibre.ebooks.metadata.sources.worker',
                    'single_covers',
                    (self.title, self.authors, self.identifiers, self.caches,
                        tdir),
                    no_output=True, abort=self.abort)
                self.log.append_dump(res['result'])
            finally:
                self.keep_going = False
                t.join()

    def scan_once(self, tdir, seen):
        for x in list(os.listdir(tdir)):
            if x in seen:
                continue
            if x.endswith('.cover') and os.path.exists(os.path.join(tdir,
                    x+'.done')):
                name = x.rpartition('.')[0]
                try:
                    plugin_name, width, height, fmt = name.split(',,')
                    width, height = int(width), int(height)
                    with open(os.path.join(tdir, x), 'rb') as f:
                        data = f.read()
                except:
                    import traceback
                    traceback.print_exc()
                else:
                    seen.add(x)
                    self.rq.put((plugin_name, width, height, fmt, data))

    def monitor_tdir(self, tdir):
        seen = set()
        while self.keep_going:
            time.sleep(1)
            self.scan_once(tdir, seen)
        # One last scan after the download process has ended
        self.scan_once(tdir, seen)

# }}}


class CoversModel(QAbstractListModel):  # {{{

    def __init__(self, current_cover, parent=None):
        QAbstractListModel.__init__(self, parent)

        if current_cover is None:
            current_cover = QPixmap(I('default_cover.png'))
        current_cover.setDevicePixelRatio(QApplication.instance().devicePixelRatio())

        self.blank = QIcon.ic('blank.png').pixmap(*CoverDelegate.ICON_SIZE)
        self.cc = current_cover
        self.reset_covers(do_reset=False)

    def reset_covers(self, do_reset=True):
        self.covers = [self.get_item(_('Current cover'), self.cc)]
        self.plugin_map = {}
        for i, plugin in enumerate(metadata_plugins(['cover'])):
            self.covers.append((plugin.name+'\n'+_('Searching...'),
                (self.blank), None, True))
            self.plugin_map[plugin] = [i+1]

        if do_reset:
            self.beginResetModel(), self.endResetModel()

    def get_item(self, src, pmap, waiting=False):
        sz = '%dx%d'%(pmap.width(), pmap.height())
        text = (src + '\n' + sz)
        scaled = pmap.scaled(
            int(CoverDelegate.ICON_SIZE[0] * pmap.devicePixelRatio()), int(CoverDelegate.ICON_SIZE[1] * pmap.devicePixelRatio()),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(pmap.devicePixelRatio())
        return (text, (scaled), pmap, waiting)

    def rowCount(self, parent=None):
        return len(self.covers)

    def data(self, index, role):
        try:
            text, pmap, cover, waiting = self.covers[index.row()]
        except:
            return None
        if role == Qt.ItemDataRole.DecorationRole:
            return pmap
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.ToolTipRole:
            return text
        if role == Qt.ItemDataRole.UserRole:
            return waiting
        return None

    def plugin_for_index(self, index):
        row = index.row() if hasattr(index, 'row') else index
        for k, v in iteritems(self.plugin_map):
            if row in v:
                return k

    def clear_failed(self):
        # Remove entries that are still waiting
        good = []
        pmap = {}

        def keygen(x):
            pmap = x[2]
            if pmap is None:
                return 1
            return pmap.width()*pmap.height()
        dcovers = sorted(self.covers[1:], key=keygen, reverse=True)
        cmap = {i:self.plugin_for_index(i) for i in range(len(self.covers))}
        for i, x in enumerate(self.covers[0:1] + dcovers):
            if not x[-1]:
                good.append(x)
                plugin = cmap[i]
                if plugin is not None:
                    try:
                        pmap[plugin].append(len(good) - 1)
                    except KeyError:
                        pmap[plugin] = [len(good)-1]
        self.covers = good
        self.plugin_map = pmap
        self.beginResetModel(), self.endResetModel()

    def pointer_from_index(self, index):
        row = index.row() if hasattr(index, 'row') else index
        try:
            return self.covers[row][2]
        except IndexError:
            pass

    def index_from_pointer(self, pointer):
        for r, (text, scaled, pmap, waiting) in enumerate(self.covers):
            if pointer == pmap:
                return self.index(r)
        return self.index(0)

    def load_pixmap(self, data):
        pmap = QPixmap()
        pmap.loadFromData(data)
        pmap.setDevicePixelRatio(QApplication.instance().devicePixelRatio())
        return pmap

    def update_result(self, plugin_name, width, height, data):
        if plugin_name.endswith('}'):
            # multi cover plugin
            plugin_name = plugin_name.partition('{')[0]
            plugin = [plugin for plugin in self.plugin_map if plugin.name == plugin_name]
            if not plugin:
                return
            plugin = plugin[0]
            last_row = max(self.plugin_map[plugin])
            pmap = self.load_pixmap(data)
            if pmap.isNull():
                return
            self.beginInsertRows(QModelIndex(), last_row, last_row)
            for rows in itervalues(self.plugin_map):
                for i in range(len(rows)):
                    if rows[i] >= last_row:
                        rows[i] += 1
            self.plugin_map[plugin].insert(-1, last_row)
            self.covers.insert(last_row, self.get_item(plugin_name, pmap, waiting=False))
            self.endInsertRows()
        else:
            # single cover plugin
            idx = None
            for plugin, rows in iteritems(self.plugin_map):
                if plugin.name == plugin_name:
                    idx = rows[0]
                    break
            if idx is None:
                return
            pmap = self.load_pixmap(data)
            if pmap.isNull():
                return
            self.covers[idx] = self.get_item(plugin_name, pmap, waiting=False)
            self.dataChanged.emit(self.index(idx), self.index(idx))

    def cover_pixmap(self, index):
        row = index.row()
        if row > 0 and row < len(self.covers):
            pmap = self.covers[row][2]
            if pmap is not None and not pmap.isNull():
                return pmap

# }}}


class CoversView(QListView):  # {{{

    chosen = pyqtSignal()

    def __init__(self, current_cover, parent=None):
        QListView.__init__(self, parent)
        self.m = CoversModel(current_cover, self)
        self.setModel(self.m)

        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setGridSize(QSize(190, 260))
        self.setIconSize(QSize(*CoverDelegate.ICON_SIZE))
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setViewMode(QListView.ViewMode.IconMode)

        self.delegate = CoverDelegate(self)
        self.setItemDelegate(self.delegate)
        self.delegate.needs_redraw.connect(self.redraw_spinners,
                type=Qt.ConnectionType.QueuedConnection)

        self.doubleClicked.connect(self.chosen, type=Qt.ConnectionType.QueuedConnection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def redraw_spinners(self):
        m = self.model()
        for r in range(m.rowCount()):
            idx = m.index(r)
            if bool(m.data(idx, Qt.ItemDataRole.UserRole)):
                m.dataChanged.emit(idx, idx)

    def select(self, num):
        current = self.model().index(num)
        sm = self.selectionModel()
        sm.select(current, QItemSelectionModel.SelectionFlag.SelectCurrent)

    def start(self):
        self.select(0)
        self.delegate.start_animation()

    def stop(self):
        self.delegate.stop_animation()

    def reset_covers(self):
        self.m.reset_covers()

    def clear_failed(self):
        pointer = self.m.pointer_from_index(self.currentIndex())
        self.m.clear_failed()
        if pointer is None:
            self.select(0)
        else:
            self.select(self.m.index_from_pointer(pointer).row())

    def show_context_menu(self, point):
        idx = self.currentIndex()
        if idx and idx.isValid() and not idx.data(Qt.ItemDataRole.UserRole):
            m = QMenu(self)
            m.addAction(QIcon.ic('view.png'), _('View this cover at full size'), self.show_cover)
            m.addAction(QIcon.ic('edit-copy.png'), _('Copy this cover to clipboard'), self.copy_cover)
            m.exec(QCursor.pos())

    def show_cover(self):
        idx = self.currentIndex()
        pmap = self.model().cover_pixmap(idx)
        if pmap is None and idx.row() == 0:
            pmap = self.model().cc
        if pmap is not None:
            from calibre.gui2.image_popup import ImageView
            d = ImageView(self, pmap, str(idx.data(Qt.ItemDataRole.DisplayRole) or ''), geom_name='metadata_download_cover_popup_geom')
            d(use_exec=True)

    def copy_cover(self):
        idx = self.currentIndex()
        pmap = self.model().cover_pixmap(idx)
        if pmap is None and idx.row() == 0:
            pmap = self.model().cc
        if pmap is not None:
            QApplication.clipboard().setPixmap(pmap)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.chosen.emit()
            ev.accept()
            return
        return QListView.keyPressEvent(self, ev)

# }}}


class CoversWidget(QWidget):  # {{{

    chosen = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, log, current_cover, parent=None):
        QWidget.__init__(self, parent)
        self.log = log
        self.abort = Event()

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.msg = QLabel()
        self.msg.setWordWrap(True)
        l.addWidget(self.msg, 0, 0)

        self.covers_view = CoversView(current_cover, self)
        self.covers_view.chosen.connect(self.chosen)
        l.addWidget(self.covers_view, 1, 0)
        self.continue_processing = True

    def reset_covers(self):
        self.covers_view.reset_covers()

    def start(self, book, current_cover, title, authors, caches):
        self.continue_processing = True
        self.abort.clear()
        self.book, self.current_cover = book, current_cover
        self.title, self.authors = title, authors
        self.log('Starting cover download for:', book.title)
        self.log('Query:', title, authors, self.book.identifiers)
        self.msg.setText('<p>'+
            _('Downloading covers for <b>%s</b>, please wait...')%book.title)
        self.covers_view.start()

        self.worker = CoverWorker(self.log, self.abort, self.title,
                self.authors, book.identifiers, caches)
        self.worker.start()
        QTimer.singleShot(50, self.check)
        self.covers_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def check(self):
        if self.worker.is_alive() and not self.abort.is_set():
            QTimer.singleShot(50, self.check)
            try:
                self.process_result(self.worker.rq.get_nowait())
            except Empty:
                pass
        else:
            self.process_results()

    def process_results(self):
        while self.continue_processing:
            try:
                self.process_result(self.worker.rq.get_nowait())
            except Empty:
                break

        if self.continue_processing:
            self.covers_view.clear_failed()

        if self.worker.error and self.worker.error.strip():
            error_dialog(self, _('Download failed'),
                    _('Failed to download any covers, click'
                        ' "Show details" for details.'),
                    det_msg=self.worker.error, show=True)

        num = self.covers_view.model().rowCount()
        if num < 2:
            txt = _('Could not find any covers for <b>%s</b>')%self.book.title
        else:
            if num == 2:
                txt = _('Found a cover for {title}').format(title=self.title)
            else:
                txt = _(
                    'Found <b>{num}</b> covers for {title}. When the download completes,'
                    ' the covers will be sorted by size.').format(
                            title=self.title, num=num-1)
        self.msg.setText(txt)
        self.msg.setWordWrap(True)
        self.covers_view.stop()

        self.finished.emit()

    def process_result(self, result):
        if not self.continue_processing:
            return
        plugin_name, width, height, fmt, data = result
        self.covers_view.model().update_result(plugin_name, width, height, data)

    def cleanup(self):
        self.covers_view.delegate.stop_animation()
        self.continue_processing = False

    def cancel(self):
        self.cleanup()
        self.abort.set()

    def cover_pixmap(self):
        idx = None
        for i in self.covers_view.selectionModel().selectedIndexes():
            if i.isValid():
                idx = i
                break
        if idx is None:
            idx = self.covers_view.currentIndex()
        return self.covers_view.model().cover_pixmap(idx)

# }}}


class LogViewer(QDialog):  # {{{

    def __init__(self, log, parent=None):
        QDialog.__init__(self, parent)
        self.log = log
        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tb = QTextBrowser(self)
        l.addWidget(self.tb)

        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        l.addWidget(self.bb)
        self.copy_button = self.bb.addButton(_('Copy to clipboard'),
                QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setIcon(QIcon.ic('edit-copy.png'))
        self.bb.rejected.connect(self.reject)
        self.bb.accepted.connect(self.accept)

        self.setWindowTitle(_('Download log'))
        self.setWindowIcon(QIcon.ic('debug.png'))
        self.resize(QSize(800, 400))

        self.keep_updating = True
        self.last_html = None
        self.finished.connect(self.stop)
        QTimer.singleShot(100, self.update_log)

        self.show()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(''.join(self.log.plain_text))

    def stop(self, *args):
        self.keep_updating = False

    def update_log(self):
        if not self.keep_updating:
            return
        html = self.log.html
        if html != self.last_html:
            self.last_html = html
            self.tb.setHtml('<pre style="font-family:monospace">%s</pre>'%html)
        QTimer.singleShot(1000, self.update_log)

# }}}


class FullFetch(QDialog):  # {{{

    def __init__(self, current_cover=None, parent=None):
        QDialog.__init__(self, parent)
        self.current_cover = current_cover
        self.log = Log()
        self.book = self.cover_pixmap = None

        self.setWindowTitle(_('Downloading metadata...'))
        self.setWindowIcon(QIcon.ic('download-metadata.png'))

        self.stack = QStackedWidget()
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(self.stack)

        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.bb.rejected.connect(self.reject)
        self.bb.accepted.connect(self.accept)
        self.ok_button = self.bb.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.ok_clicked)
        self.prev_button = pb = QPushButton(QIcon.ic('back.png'), _('&Back'), self)
        pb.clicked.connect(self.back_clicked)
        pb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.log_button = self.bb.addButton(_('&View log'), QDialogButtonBox.ButtonRole.ActionRole)
        self.log_button.clicked.connect(self.view_log)
        self.log_button.setIcon(QIcon.ic('debug.png'))
        self.prev_button.setVisible(False)
        h.addWidget(self.prev_button), h.addWidget(self.bb)

        self.identify_widget = IdentifyWidget(self.log, self)
        self.identify_widget.rejected.connect(self.reject)
        self.identify_widget.results_found.connect(self.identify_results_found)
        self.identify_widget.book_selected.connect(self.book_selected)
        self.stack.addWidget(self.identify_widget)

        self.covers_widget = CoversWidget(self.log, self.current_cover, parent=self)
        self.covers_widget.chosen.connect(self.ok_clicked)
        self.stack.addWidget(self.covers_widget)

        self.resize(850, 600)
        geom = gprefs.get('metadata_single_gui_geom', None)
        if geom is not None and geom:
            QApplication.instance().safe_restore_geometry(self, geom)

        self.finished.connect(self.cleanup)

    def view_log(self):
        self._lv = LogViewer(self.log, self)

    def book_selected(self, book, caches):
        self.prev_button.setVisible(True)
        self.book = book
        self.stack.setCurrentIndex(1)
        self.log('\n\n')
        self.covers_widget.start(book, self.current_cover,
                self.title, self.authors, caches)
        self.ok_button.setFocus()

    def back_clicked(self):
        self.prev_button.setVisible(False)
        self.stack.setCurrentIndex(0)
        self.covers_widget.cancel()
        self.covers_widget.reset_covers()

    def accept(self):
        # Prevent the usual dialog accept mechanisms from working
        gprefs['metadata_single_gui_geom'] = bytearray(self.saveGeometry())
        self.identify_widget.save_state()
        if DEBUG_DIALOG:
            if self.stack.currentIndex() == 2:
                return QDialog.accept(self)
        else:
            if self.stack.currentIndex() == 1:
                return QDialog.accept(self)

    def reject(self):
        gprefs['metadata_single_gui_geom'] = bytearray(self.saveGeometry())
        self.identify_widget.cancel()
        self.covers_widget.cancel()
        return QDialog.reject(self)

    def cleanup(self):
        self.covers_widget.cleanup()

    def identify_results_found(self):
        self.ok_button.setEnabled(True)

    def next_clicked(self, *args):
        gprefs['metadata_single_gui_geom'] = bytearray(self.saveGeometry())
        self.identify_widget.get_result()

    def ok_clicked(self, *args):
        self.cover_pixmap = self.covers_widget.cover_pixmap()
        if self.stack.currentIndex() == 0:
            self.next_clicked()
            return
        if DEBUG_DIALOG:
            if self.cover_pixmap is not None:
                self.w = QLabel()
                self.w.setPixmap(self.cover_pixmap)
                self.stack.addWidget(self.w)
                self.stack.setCurrentIndex(2)
        else:
            QDialog.accept(self)

    def start(self, title=None, authors=None, identifiers={}):
        self.title, self.authors = title, authors
        self.identify_widget.start(title=title, authors=authors,
                identifiers=identifiers)
        return self.exec()
# }}}


class CoverFetch(QDialog):  # {{{

    def __init__(self, current_cover=None, parent=None):
        QDialog.__init__(self, parent)
        self.current_cover = current_cover
        self.log = Log()
        self.cover_pixmap = None

        self.setWindowTitle(_('Downloading cover...'))
        self.setWindowIcon(QIcon.ic('default_cover.png'))

        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.covers_widget = CoversWidget(self.log, self.current_cover, parent=self)
        self.covers_widget.chosen.connect(self.accept)
        l.addWidget(self.covers_widget)

        self.resize(850, 600)

        self.finished.connect(self.cleanup)

        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        l.addWidget(self.bb)
        self.log_button = self.bb.addButton(_('&View log'), QDialogButtonBox.ButtonRole.ActionRole)
        self.log_button.clicked.connect(self.view_log)
        self.log_button.setIcon(QIcon.ic('debug.png'))
        self.bb.rejected.connect(self.reject)
        self.bb.accepted.connect(self.accept)

        geom = gprefs.get('single-cover-fetch-dialog-geometry', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

    def cleanup(self):
        self.covers_widget.cleanup()

    def reject(self):
        gprefs.set('single-cover-fetch-dialog-geometry', bytearray(self.saveGeometry()))
        self.covers_widget.cancel()
        return QDialog.reject(self)

    def accept(self, *args):
        gprefs.set('single-cover-fetch-dialog-geometry', bytearray(self.saveGeometry()))
        self.cover_pixmap = self.covers_widget.cover_pixmap()
        QDialog.accept(self)

    def start(self, title, authors, identifiers):
        book = Metadata(title, authors)
        book.identifiers = identifiers
        self.covers_widget.start(book, self.current_cover,
                title, authors, {})
        return self.exec()

    def view_log(self):
        self._lv = LogViewer(self.log, self)

# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    DEBUG_DIALOG = True
    app = Application([])
    d = FullFetch()
    d.start(title='great gatsby', authors=['fitzgerald'], identifiers={})
