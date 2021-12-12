__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Miscellaneous widgets used in the GUI
'''
import re, os

from qt.core import (QIcon, QFont, QLabel, QListWidget, QAction, QEvent,
        QListWidgetItem, QTextCharFormat, QApplication, QSyntaxHighlighter,
        QCursor, QColor, QWidget, QPixmap, QSplitterHandle, QToolButton,
        Qt, pyqtSignal, QSize, QSplitter, QPainter, QPageSize, QPrinter,
        QLineEdit, QComboBox, QPen, QGraphicsScene, QMenu, QStringListModel, QKeySequence,
        QCompleter, QTimer, QRect, QGraphicsView, QPagedPaintDevice, QPalette, QClipboard)

from calibre.constants import iswindows, ismacos
from calibre.gui2 import (error_dialog, pixmap_to_data, gprefs,
        warning_dialog)
from calibre.gui2.filename_pattern_ui import Ui_Form
from calibre import fit_image, strftime, force_unicode
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.config import prefs, XMLConfig
from calibre.gui2.progress_indicator import ProgressIndicator as _ProgressIndicator
from calibre.gui2.dnd import (dnd_has_image, dnd_get_image, dnd_get_files,
    image_extensions, dnd_has_extension, dnd_get_local_image_and_pixmap, DownloadDialog)
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import native_string_type

history = XMLConfig('history')


class ProgressIndicator(QWidget):  # {{{

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.setGeometry(0, 0, 300, 350)
        self.pi = _ProgressIndicator(self)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.setVisible(False)
        self.pos = None

    def start(self, msg=''):
        view = self.parent()
        pwidth, pheight = view.size().width(), view.size().height()
        self.resize(pwidth, min(pheight, 250))
        if self.pos is None:
            self.move(0, int((pheight-self.size().height())/2))
        else:
            self.move(self.pos[0], self.pos[1])
        self.pi.resize(self.pi.sizeHint())
        self.pi.move(int((self.size().width()-self.pi.size().width())/2), 0)
        self.status.resize(self.size().width(), self.size().height()-self.pi.size().height()-10)
        self.status.move(0, self.pi.size().height()+10)
        self.status.setText('<h1>'+msg+'</h1>')
        self.setVisible(True)
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()
        self.setVisible(False)
# }}}


class FilenamePattern(QWidget, Ui_Form):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        try:
            self.help_label.setText(self.help_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/regexp.html'))
        except TypeError:
            pass  # link already localized

        self.test_button.clicked.connect(self.do_test)
        self.re.lineEdit().returnPressed[()].connect(self.do_test)
        self.filename.returnPressed[()].connect(self.do_test)
        connect_lambda(self.re.lineEdit().textChanged, self, lambda self, x: self.changed_signal.emit())

    def initialize(self, defaults=False):
        # Get all items in the combobox. If we are resetting
        # to defaults we don't want to lose what the user
        # has added.
        val_hist = [str(self.re.lineEdit().text())] + [str(self.re.itemText(i)) for i in range(self.re.count())]
        self.re.clear()

        if defaults:
            val = prefs.defaults['filename_pattern']
        else:
            val = prefs['filename_pattern']
        self.re.lineEdit().setText(val)

        val_hist += gprefs.get('filename_pattern_history', [
                               '(?P<title>.+)', r'(?P<author>[^_-]+) -?\s*(?P<series>[^_0-9-]*)(?P<series_index>[0-9]*)\s*-\s*(?P<title>[^_].+) ?'])
        if val in val_hist:
            del val_hist[val_hist.index(val)]
        val_hist.insert(0, val)
        for v in val_hist:
            # Ensure we don't have duplicate items.
            if v and self.re.findText(v) == -1:
                self.re.addItem(v)
        self.re.setCurrentIndex(0)

    def do_test(self):
        from calibre.ebooks.metadata import authors_to_string
        from calibre.ebooks.metadata.meta import metadata_from_filename
        fname = str(self.filename.text())
        ext = os.path.splitext(fname)[1][1:].lower()
        if ext not in BOOK_EXTENSIONS:
            return warning_dialog(self, _('Test file name invalid'),
                    _('The file name <b>%s</b> does not appear to end with a'
                        ' file extension. It must end with a file '
                        ' extension like .epub or .mobi')%fname, show=True)

        try:
            pat = self.pattern()
        except Exception as err:
            error_dialog(self, _('Invalid regular expression'),
                         _('Invalid regular expression: %s')%err).exec()
            return
        mi = metadata_from_filename(fname, pat)
        if mi.title:
            self.title.setText(mi.title)
        else:
            self.title.setText(_('No match'))
        if mi.authors:
            self.authors.setText(authors_to_string(mi.authors))
        else:
            self.authors.setText(_('No match'))

        if mi.series:
            self.series.setText(mi.series)
        else:
            self.series.setText(_('No match'))

        if mi.series_index is not None:
            self.series_index.setText(str(mi.series_index))
        else:
            self.series_index.setText(_('No match'))

        if mi.publisher:
            self.publisher.setText(mi.publisher)
        else:
            self.publisher.setText(_('No match'))

        if mi.pubdate:
            self.pubdate.setText(strftime('%Y-%m-%d', mi.pubdate))
        else:
            self.pubdate.setText(_('No match'))

        self.isbn.setText(_('No match') if mi.isbn is None else str(mi.isbn))
        self.comments.setText(mi.comments if mi.comments else _('No match'))

    def pattern(self):
        pat = str(self.re.lineEdit().text())
        return re.compile(pat)

    def commit(self):
        pat = self.pattern().pattern
        prefs['filename_pattern'] = pat

        history = []
        history_pats = [str(self.re.lineEdit().text())] + [str(self.re.itemText(i)) for i in range(self.re.count())]
        for p in history_pats[:24]:
            # Ensure we don't have duplicate items.
            if p and p not in history:
                history.append(p)
        gprefs['filename_pattern_history'] = history

        return pat

# }}}


class FormatList(QListWidget):  # {{{
    DROPABBLE_EXTENSIONS = BOOK_EXTENSIONS
    formats_dropped = pyqtSignal(object, object)
    delete_format = pyqtSignal()

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if dnd_has_extension(md, self.DROPABBLE_EXTENSIONS, allow_all_extensions=True):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.DropAction.CopyAction)
        md = event.mimeData()
        # Now look for ebook files
        urls, filenames = dnd_get_files(md, self.DROPABBLE_EXTENSIONS, allow_all_extensions=True)
        if not urls:
            # Nothing found
            return

        if not filenames:
            # Local files
            self.formats_dropped.emit(event, urls)
        else:
            # Remote files, use the first file
            d = DownloadDialog(urls[0], filenames[0], self)
            d.start_download()
            if d.err is None:
                self.formats_dropped.emit(event, [d.fpath])

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_format.emit()
        else:
            return QListWidget.keyPressEvent(self, event)

# }}}


class ImageDropMixin:  # {{{
    '''
    Adds support for dropping images onto widgets and a context menu for
    copy/pasting images.
    '''
    DROPABBLE_EXTENSIONS = None

    def __init__(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        exts = self.DROPABBLE_EXTENSIONS or image_extensions()
        if dnd_has_extension(md, exts) or \
                dnd_has_image(md):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.DropAction.CopyAction)
        md = event.mimeData()
        pmap, data = dnd_get_local_image_and_pixmap(md)
        if pmap is not None:
            self.handle_image_drop(pmap, data)
            return

        x, y = dnd_get_image(md)
        if x is not None:
            # We have an image, set cover
            event.accept()
            if y is None:
                # Local image
                self.handle_image_drop(x)
            else:
                # Remote files, use the first file
                d = DownloadDialog(x, y, self)
                d.start_download()
                if d.err is None:
                    pmap = QPixmap()
                    with lopen(d.fpath, 'rb') as f:
                        data = f.read()
                    pmap.loadFromData(data)
                    if not pmap.isNull():
                        self.handle_image_drop(pmap, data=data)

    def handle_image_drop(self, pmap, data=None):
        self.set_pixmap(pmap)
        self.cover_changed.emit(data or pixmap_to_data(pmap, format='PNG'))

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def get_pixmap(self):
        return self.pixmap()

    def set_pixmap(self, pmap):
        self.setPixmap(pmap)

    def build_context_menu(self):
        cm = QMenu(self)
        paste = cm.addAction(QIcon.ic('edit-paste.png'), _('Paste cover'))
        copy = cm.addAction(QIcon.ic('edit-copy.png'), _('Copy cover'))
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        return cm

    def contextMenuEvent(self, ev):
        self.build_context_menu().exec(ev.globalPos())

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setPixmap(self.get_pixmap())

    def paste_from_clipboard(self):
        cb = QApplication.instance().clipboard()
        pmap = cb.pixmap()
        if pmap.isNull() and cb.supportsSelection():
            pmap = cb.pixmap(QClipboard.Mode.Selection)
        if not pmap.isNull():
            self.set_pixmap(pmap)
            self.cover_changed.emit(
                    pixmap_to_data(pmap, format='PNG'))
# }}}


# ImageView {{{

def draw_size(p, rect, w, h):
    rect = rect.adjusted(0, 0, 0, -4)
    f = p.font()
    f.setBold(True)
    p.setFont(f)
    sz = '\u00a0%d x %d\u00a0'%(w, h)
    flags = Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignRight|Qt.TextFlag.TextSingleLine
    szrect = p.boundingRect(rect, flags, sz)
    p.fillRect(szrect.adjusted(0, 0, 0, 4), QColor(0, 0, 0, 200))
    p.setPen(QPen(QColor(255,255,255)))
    p.drawText(rect, flags, sz)


class ImageView(QWidget, ImageDropMixin):

    BORDER_WIDTH = 1
    cover_changed = pyqtSignal(object)

    def __init__(self, parent=None, show_size_pref_name=None, default_show_size=False):
        QWidget.__init__(self, parent)
        self.show_size_pref_name = ('show_size_on_cover_' + show_size_pref_name) if show_size_pref_name else None
        self._pixmap = QPixmap()
        self.setMinimumSize(QSize(150, 200))
        ImageDropMixin.__init__(self)
        self.draw_border = True
        self.show_size = False
        if self.show_size_pref_name:
            self.show_size = gprefs.get(self.show_size_pref_name, default_show_size)

    def setPixmap(self, pixmap):
        if not isinstance(pixmap, QPixmap):
            raise TypeError('Must use a QPixmap')
        self._pixmap = pixmap
        self.updateGeometry()
        self.update()

    def build_context_menu(self):
        m = ImageDropMixin.build_context_menu(self)
        if self.show_size_pref_name:
            text = _('Hide size in corner') if self.show_size else _('Show size in corner')
            m.addAction(text, self.toggle_show_size)
        return m

    def toggle_show_size(self):
        self.show_size ^= True
        if self.show_size_pref_name:
            gprefs[self.show_size_pref_name] = self.show_size
        self.update()

    def pixmap(self):
        return self._pixmap

    def sizeHint(self):
        if self._pixmap.isNull():
            return self.minimumSize()
        return self._pixmap.size()

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        pmap = self._pixmap
        if pmap.isNull():
            return
        w, h = pmap.width(), pmap.height()
        ow, oh = w, h
        cw, ch = self.rect().width(), self.rect().height()
        scaled, nw, nh = fit_image(w, h, cw, ch)
        if scaled:
            pmap = pmap.scaled(int(nw*pmap.devicePixelRatio()), int(nh*pmap.devicePixelRatio()), Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
        w, h = int(pmap.width()/pmap.devicePixelRatio()), int(pmap.height()/pmap.devicePixelRatio())
        x = int(abs(cw - w)/2)
        y = int(abs(ch - h)/2)
        target = QRect(x, y, w, h)
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(target, pmap)
        if self.draw_border:
            pen = QPen()
            pen.setWidth(self.BORDER_WIDTH)
            p.setPen(pen)
            p.drawRect(target)
        if self.show_size:
            draw_size(p, target, ow, oh)
        p.end()
# }}}


class CoverView(QGraphicsView, ImageDropMixin):  # {{{

    cover_changed = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        self.show_size = kwargs.pop('show_size', False)
        QGraphicsView.__init__(self, *args, **kwargs)
        ImageDropMixin.__init__(self)
        self.pixmap_size = 0, 0
        if self.show_size:
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.set_background()

    def get_pixmap(self):
        for item in self.scene.items():
            if hasattr(item, 'pixmap'):
                return item.pixmap()

    def set_pixmap(self, pmap):
        self.scene = QGraphicsScene()
        self.scene.addPixmap(pmap)
        self.setScene(self.scene)

    def set_background(self, brush=None):
        self.setBackgroundBrush(brush or self.palette().color(QPalette.ColorRole.Window))

    def paintEvent(self, ev):
        QGraphicsView.paintEvent(self, ev)
        if self.show_size:
            v = self.viewport()
            p = QPainter(v)
            draw_size(p, v.rect(), *self.pixmap_size)

# }}}

# BasicList {{{


class BasicListItem(QListWidgetItem):

    def __init__(self, text, user_data=None):
        QListWidgetItem.__init__(self, text)
        self.user_data = user_data

    def __eq__(self, other):
        if hasattr(other, 'text'):
            return self.text() == other.text()
        return False


class BasicList(QListWidget):

    def add_item(self, text, user_data=None, replace=False):
        item = BasicListItem(text, user_data)

        for oitem in self.items():
            if oitem == item:
                if replace:
                    self.takeItem(self.row(oitem))
                else:
                    raise ValueError('Item already in list')

        self.addItem(item)

    def remove_selected_items(self, *args):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def items(self):
        for i in range(self.count()):
            yield self.item(i)
# }}}


class LineEditECM:  # {{{

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def create_change_case_menu(self, menu):
        case_menu = QMenu(_('Change case'), menu)
        action_upper_case = case_menu.addAction(_('Upper case'))
        action_lower_case = case_menu.addAction(_('Lower case'))
        action_swap_case = case_menu.addAction(_('Swap case'))
        action_title_case = case_menu.addAction(_('Title case'))
        action_capitalize = case_menu.addAction(_('Capitalize'))

        action_upper_case.triggered.connect(self.upper_case)
        action_lower_case.triggered.connect(self.lower_case)
        action_swap_case.triggered.connect(self.swap_case)
        action_title_case.triggered.connect(self.title_case)
        action_capitalize.triggered.connect(self.capitalize)
        menu.addMenu(case_menu)
        return case_menu

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        self.create_change_case_menu(menu)
        menu.exec(event.globalPos())

    def modify_case_operation(self, func):
        has_selection = self.hasSelectedText()
        text = self.selectedText() if has_selection else self.text()
        ntext = func(text)
        if ntext != text:
            self.insert(ntext) if has_selection else self.setText(ntext)

    def upper_case(self):
        from calibre.utils.icu import upper
        self.modify_case_operation(upper)

    def lower_case(self):
        from calibre.utils.icu import lower
        self.modify_case_operation(lower)

    def swap_case(self):
        from calibre.utils.icu import swapcase
        self.modify_case_operation(swapcase)

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.modify_case_operation(titlecase)

    def capitalize(self):
        from calibre.utils.icu import capitalize
        self.modify_case_operation(capitalize)

# }}}


class EnLineEdit(LineEditECM, QLineEdit):  # {{{

    '''
    Enhanced QLineEdit.

    Includes an extended content menu.
    '''

    def event(self, ev):
        # See https://bugreports.qt.io/browse/QTBUG-46911
        if ev.type() == QEvent.Type.ShortcutOverride and (
                hasattr(ev, 'key') and ev.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and (
                    ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier) == Qt.KeyboardModifier.ControlModifier):
            ev.accept()
        return QLineEdit.event(self, ev)

# }}}


class ItemsCompleter(QCompleter):  # {{{

    '''
    A completer object that completes a list of tags. It is used in conjunction
    with a CompleterLineEdit.
    '''

    def __init__(self, parent, all_items):
        QCompleter.__init__(self, all_items, parent)
        self.all_items = set(all_items)

    def update(self, text_items, completion_prefix):
        items = list(self.all_items.difference(text_items))
        model = QStringListModel(items, self)
        self.setModel(model)

        self.setCompletionPrefix(completion_prefix)
        if completion_prefix.strip():
            self.complete()

    def update_items_cache(self, items):
        self.all_items = set(items)
        model = QStringListModel(items, self)
        self.setModel(model)

# }}}


class CompleteLineEdit(EnLineEdit):  # {{{

    '''
    A QLineEdit that can complete parts of text separated by separator.
    '''

    def __init__(self, parent=0, complete_items=[], sep=',', space_before_sep=False):
        EnLineEdit.__init__(self, parent)

        self.separator = sep
        self.space_before_sep = space_before_sep

        self.textChanged.connect(self.text_changed)

        self.completer = ItemsCompleter(self, complete_items)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.completer.activated[native_string_type].connect(self.complete_text)

        self.completer.setWidget(self)

    def update_items_cache(self, complete_items):
        self.completer.update_items_cache(complete_items)

    def set_separator(self, sep):
        self.separator = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    def text_changed(self, text):
        all_text = str(text)
        text = all_text[:self.cursorPosition()]
        prefix = text.split(self.separator)[-1].strip()

        text_items = []
        for t in all_text.split(self.separator):
            t1 = str(t).strip()
            if t1:
                text_items.append(t)
        text_items = list(set(text_items))
        self.completer.update(text_items, prefix)

    def complete_text(self, text):
        cursor_pos = self.cursorPosition()
        before_text = str(self.text())[:cursor_pos]
        after_text = str(self.text())[cursor_pos:]
        prefix_len = len(before_text.split(self.separator)[-1].lstrip())
        if self.space_before_sep:
            complete_text_pat = '%s%s %s %s'
            len_extra = 3
        else:
            complete_text_pat = '%s%s%s %s'
            len_extra = 2
        self.setText(complete_text_pat % (before_text[:cursor_pos - prefix_len], text, self.separator, after_text))
        self.setCursorPosition(cursor_pos - prefix_len + len(text) + len_extra)

# }}}


class EnComboBox(QComboBox):  # {{{

    '''
    Enhanced QComboBox.

    Includes an extended context menu.
    '''

    def __init__(self, *args):
        QComboBox.__init__(self, *args)
        self.setLineEdit(EnLineEdit(self))
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMinimumContentsLength(20)

    def text(self):
        return str(self.currentText())

    def setText(self, text):
        idx = self.findText(text, Qt.MatchFlag.MatchFixedString|Qt.MatchFlag.MatchCaseSensitive)
        if idx == -1:
            self.insertItem(0, text)
            idx = 0
        self.setCurrentIndex(idx)

# }}}


class CompleteComboBox(EnComboBox):  # {{{

    def __init__(self, *args):
        EnComboBox.__init__(self, *args)
        self.setLineEdit(CompleteLineEdit(self))

    def update_items_cache(self, complete_items):
        self.lineEdit().update_items_cache(complete_items)

    def set_separator(self, sep):
        self.lineEdit().set_separator(sep)

    def set_space_before_sep(self, space_before):
        self.lineEdit().set_space_before_sep(space_before)

# }}}


class HistoryLineEdit(QComboBox):  # {{{

    lost_focus = pyqtSignal()

    def __init__(self, *args):
        QComboBox.__init__(self, *args)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxCount(10)
        self.setClearButtonEnabled = self.lineEdit().setClearButtonEnabled
        self.textChanged = self.editTextChanged

    def setPlaceholderText(self, txt):
        return self.lineEdit().setPlaceholderText(txt)

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.addItems(history.get(self.store_name, []))
        self.setEditText('')
        self.lineEdit().editingFinished.connect(self.save_history)

    def save_history(self):
        items = []
        ct = str(self.currentText())
        if ct:
            items.append(ct)
        for i in range(self.count()):
            item = str(self.itemText(i))
            if item not in items:
                items.append(item)
        self.blockSignals(True)
        self.clear()
        self.addItems(items)
        self.setEditText(ct)
        self.blockSignals(False)
        try:
            history.set(self.store_name, items)
        except ValueError:
            from calibre.utils.cleantext import clean_ascii_chars
            items = [clean_ascii_chars(force_unicode(x)) for x in items]
            try:
                history.set(self.store_name, items)
            except ValueError:
                pass

    def setText(self, t):
        self.setEditText(t)
        self.lineEdit().setCursorPosition(0)

    def text(self):
        return self.currentText()

    def focusOutEvent(self, e):
        QComboBox.focusOutEvent(self, e)
        if not (self.hasFocus() or self.view().hasFocus()):
            self.lost_focus.emit()

# }}}


class ComboBoxWithHelp(QComboBox):  # {{{
    '''
    A combobox where item 0 is help text. CurrentText will return '' for item 0.
    Be sure to always fetch the text with currentText. Don't use the signals
    that pass a string, because they will not correct the text.
    '''

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.currentIndexChanged.connect(self.index_changed)
        self.help_text = ''
        self.state_set = False

    def initialize(self, help_text=_('Search')):
        self.help_text = help_text
        self.set_state()

    def set_state(self):
        if not self.state_set:
            if self.currentIndex() == 0:
                self.setItemText(0, self.help_text)
                self.setStyleSheet('QComboBox { color: gray }')
            else:
                self.setItemText(0, '')
                self.setStyleSheet('QComboBox { color: black }')

    def index_changed(self, index):
        self.state_set = False
        self.set_state()

    def currentText(self):
        if self.currentIndex() == 0:
            return ''
        return QComboBox.currentText(self)

    def itemText(self, idx):
        if idx == 0:
            return ''
        return QComboBox.itemText(self, idx)

    def showPopup(self):
        self.setItemText(0, '')
        QComboBox.showPopup(self)

    def hidePopup(self):
        QComboBox.hidePopup(self)
        self.set_state()

# }}}


class EncodingComboBox(QComboBox):  # {{{
    '''
    A combobox that holds text encodings support
    by Python. This is only populated with the most
    common and standard encodings. There is no good
    way to programmatically list all supported encodings
    using encodings.aliases.aliases.keys(). It
    will not work.
    '''

    ENCODINGS = ['', 'cp1252', 'latin1', 'utf-8', '', 'ascii', 'big5', 'cp1250', 'cp1251', 'cp1253',
        'cp1254', 'cp1255', 'cp1256', 'euc_jp', 'euc_kr', 'gb2312', 'gb18030',
        'hz', 'iso2022_jp', 'iso2022_kr', 'iso8859_5', 'shift_jis',
    ]

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.setEditable(True)
        self.setLineEdit(EnLineEdit(self))

        for item in self.ENCODINGS:
            self.addItem(item)

# }}}


class PythonHighlighter(QSyntaxHighlighter):  # {{{

    Rules = ()
    Formats = {}

    KEYWORDS = ["and", "as", "assert", "break", "class", "continue", "def",
        "del", "elif", "else", "except", "exec", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "not", "or",
        "pass", "print", "raise", "return", "try", "while", "with",
        "yield"]

    BUILTINS = ["abs", "all", "any", "basestring", "bool", "callable", "chr",
        "classmethod", "cmp", "compile", "complex", "delattr", "dict",
        "dir", "divmod", "enumerate", "eval", "execfile", "exit", "file",
        "filter", "float", "frozenset", "getattr", "globals", "hasattr",
        "hex", "id", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "long", "map", "max", "min", "object", "oct",
        "open", "ord", "pow", "property", "range", "reduce", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted",
        "staticmethod", "str", "sum", "super", "tuple", "type", "unichr",
        "unicode", "vars", "xrange", "zip"]

    CONSTANTS = ["False", "True", "None", "NotImplemented", "Ellipsis"]

    def __init__(self, parent=None):
        super().__init__(parent)
        if not self.Rules:
            self.initialize_class_members()

    @classmethod
    def initialize_class_members(cls):
        cls.initializeFormats()
        r = []

        def a(a, b):
            r.append((a, b))

        a(re.compile(
                "|".join([r"\b%s\b" % keyword for keyword in cls.KEYWORDS])),
                "keyword")
        a(re.compile(
                "|".join([r"\b%s\b" % builtin for builtin in cls.BUILTINS])),
                "builtin")
        a(re.compile(
                "|".join([r"\b%s\b" % constant
                for constant in cls.CONSTANTS])), "constant")
        a(re.compile(
                r"\b[+-]?[0-9]+[lL]?\b"
                r"|\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b"
                r"|\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"),
                "number")
        a(re.compile(
                r"\bPyQt6\b|\bQt?[A-Z][a-z]\w+\b"), "pyqt")
        a(re.compile(r"\b@\w+\b"), "decorator")
        stringRe = re.compile(r"""(?:'[^']*?'|"[^"]*?")""")
        a(stringRe, "string")
        cls.stringRe = re.compile(r"""(:?"["]".*?"["]"|'''.*?''')""")
        a(cls.stringRe, "string")
        cls.tripleSingleRe = re.compile(r"""'''(?!")""")
        cls.tripleDoubleRe = re.compile(r'''"""(?!')''')
        cls.Rules = tuple(r)

    @classmethod
    def initializeFormats(cls):
        baseFormat = QTextCharFormat()
        baseFormat.setFontFamilies(['monospace'])
        p = QApplication.instance().palette()
        for name, color, bold, italic in (
                ("normal", None, False, False),
                ("keyword", p.color(QPalette.ColorRole.Link).name(), True, False),
                ("builtin", p.color(QPalette.ColorRole.Link).name(), False, False),
                ("constant", p.color(QPalette.ColorRole.Link).name(), False, False),
                ("decorator", "#0000E0", False, False),
                ("comment", "#007F00", False, True),
                ("string", "#808000", False, False),
                ("number", "#924900", False, False),
                ("error", "#FF0000", False, False),
                ("pyqt", "#50621A", False, False)):

            fmt = QTextCharFormat(baseFormat)
            if color is not None:
                fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(italic)
            cls.Formats[name] = fmt

    def highlightBlock(self, text):
        NORMAL, TRIPLESINGLE, TRIPLEDOUBLE, ERROR = range(4)

        textLength = len(text)
        prevState = self.previousBlockState()

        self.setFormat(0, textLength,
                       self.Formats["normal"])

        if text.startswith("Traceback") or text.startswith("Error: "):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           self.Formats["error"])
            return
        if prevState == ERROR and \
           not (text.startswith('>>>') or text.startswith("#")):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           self.Formats["error"])
            return

        for regex, fmt in PythonHighlighter.Rules:
            for m in regex.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), self.Formats[fmt])

        # Slow but good quality highlighting for comments. For more
        # speed, comment this out and add the following to __init__:
        # PythonHighlighter.Rules.append((re.compile(r"#.*"), "comment"))
        if not text:
            pass
        elif text[0] == "#":
            self.setFormat(0, len(text), self.Formats["comment"])
        else:
            stack = []
            for i, c in enumerate(text):
                if c in ('"', "'"):
                    if stack and stack[-1] == c:
                        stack.pop()
                    else:
                        stack.append(c)
                elif c == "#" and len(stack) == 0:
                    self.setFormat(i, len(text), self.Formats["comment"])
                    break

        self.setCurrentBlockState(NORMAL)

        if self.stringRe.search(text) is not None:
            return
        # This is fooled by triple quotes inside single quoted strings
        for m, state in (
            (self.tripleSingleRe.search(text), TRIPLESINGLE),
            (self.tripleDoubleRe.search(text), TRIPLEDOUBLE)
        ):
            i = -1 if m is None else m.start()
            if self.previousBlockState() == state:
                if i == -1:
                    i = len(text)
                    self.setCurrentBlockState(state)
                self.setFormat(0, i + 3,
                               self.Formats["string"])
            elif i > -1:
                self.setCurrentBlockState(state)
                self.setFormat(i, len(text),
                               self.Formats["string"])

    def rehighlight(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        super().rehighlight()
        QApplication.restoreOverrideCursor()

# }}}


# Splitter {{{


class SplitterHandle(QSplitterHandle):

    double_clicked = pyqtSignal(object)

    def __init__(self, orientation, splitter):
        QSplitterHandle.__init__(self, orientation, splitter)
        splitter.splitterMoved.connect(self.splitter_moved,
                type=Qt.ConnectionType.QueuedConnection)
        self.double_clicked.connect(splitter.double_clicked,
                type=Qt.ConnectionType.QueuedConnection)
        self.highlight = False
        self.setToolTip(_('Drag to resize')+' '+splitter.label)

    def splitter_moved(self, *args):
        oh = self.highlight
        self.highlight = 0 in self.splitter().sizes()
        if oh != self.highlight:
            self.update()

    def mouseDoubleClickEvent(self, ev):
        self.double_clicked.emit(self)


class LayoutButton(QToolButton):

    def __init__(self, icon, text, splitter=None, parent=None, shortcut=None):
        QToolButton.__init__(self, parent)
        self.label = text
        self.setIcon(QIcon(icon))
        self.setCheckable(True)
        self.icname = os.path.basename(icon).rpartition('.')[0]

        self.splitter = splitter
        if splitter is not None:
            splitter.state_changed.connect(self.update_state)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shortcut = shortcut or ''

    def update_shortcut(self, action_toggle=None):
        action_toggle = action_toggle or getattr(self, 'action_toggle', None)
        if action_toggle:
            sc = ', '.join(sc.toString(QKeySequence.SequenceFormat.NativeText)
                                for sc in action_toggle.shortcuts())
            self.shortcut = sc or ''
            self.update_text()

    def update_text(self):
        t = _('Hide {}') if self.isChecked() else _('Show {}')
        t = t.format(self.label)
        if self.shortcut:
            t += f' [{self.shortcut}]'
        self.setText(t), self.setToolTip(t), self.setStatusTip(t)

    def set_state_to_show(self, *args):
        self.setChecked(False)
        self.update_text()

    def set_state_to_hide(self, *args):
        self.setChecked(True)
        self.update_text()

    def update_state(self, *args):
        if self.splitter.is_side_index_hidden:
            self.set_state_to_show()
        else:
            self.set_state_to_hide()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            if self.icname == 'search':
                gui.iactions['Preferences'].do_config(initial_plugin=('Interface', 'Search'), close_after_initial=True)
                ev.accept()
                return
            tab_name = {'book':'book_details', 'grid':'cover_grid', 'cover_flow':'cover_browser',
                        'tags':'tag_browser', 'quickview':'quickview'}.get(self.icname)
            if tab_name:
                if gui is not None:
                    gui.iactions['Preferences'].do_config(initial_plugin=('Interface', 'Look & Feel', tab_name+'_tab'), close_after_initial=True)
                    ev.accept()
                    return
        return QToolButton.mouseReleaseEvent(self, ev)


class Splitter(QSplitter):

    state_changed = pyqtSignal(object)
    reapply_sizes = pyqtSignal(object)

    def __init__(self, name, label, icon, initial_show=True,
            initial_side_size=120, connect_button=True,
            orientation=Qt.Orientation.Horizontal, side_index=0, parent=None,
            shortcut=None, hide_handle_on_single_panel=True):
        QSplitter.__init__(self, parent)
        self.reapply_sizes.connect(self.setSizes, type=Qt.ConnectionType.QueuedConnection)
        self.hide_handle_on_single_panel = hide_handle_on_single_panel
        if hide_handle_on_single_panel:
            self.state_changed.connect(self.update_handle_width)
        self.original_handle_width = self.handleWidth()
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.desired_side_size = initial_side_size
        self.desired_show = initial_show
        self.resize_timer.setInterval(5)
        self.resize_timer.timeout.connect(self.do_resize)
        self.setOrientation(orientation)
        self.side_index = side_index
        self._name = name
        self.label = label
        self.initial_side_size = initial_side_size
        self.initial_show = initial_show
        self.splitterMoved.connect(self.splitter_moved, type=Qt.ConnectionType.QueuedConnection)
        self.button = LayoutButton(icon, label, self, shortcut=shortcut)
        if connect_button:
            self.button.clicked.connect(self.double_clicked)

        if shortcut is not None:
            self.action_toggle = QAction(QIcon(icon), _('Toggle') + ' ' + label,
                    self)
            self.action_toggle.changed.connect(self.update_shortcut)
            self.action_toggle.triggered.connect(self.toggle_triggered)
            if parent is not None:
                parent.addAction(self.action_toggle)
                if hasattr(parent, 'keyboard'):
                    parent.keyboard.register_shortcut('splitter %s %s'%(name,
                        label), str(self.action_toggle.text()),
                        default_keys=(shortcut,), action=self.action_toggle)
                else:
                    self.action_toggle.setShortcut(shortcut)
            else:
                self.action_toggle.setShortcut(shortcut)

    def update_shortcut(self):
        self.button.update_shortcut(self.action_toggle)

    def toggle_triggered(self, *args):
        self.toggle_side_pane()

    def createHandle(self):
        return SplitterHandle(self.orientation(), self)

    def initialize(self):
        for i in range(self.count()):
            h = self.handle(i)
            if h is not None:
                h.splitter_moved()
        self.state_changed.emit(not self.is_side_index_hidden)

    def splitter_moved(self, *args):
        self.desired_side_size = self.side_index_size
        self.state_changed.emit(not self.is_side_index_hidden)

    def update_handle_width(self, not_one_panel):
        self.setHandleWidth(self.original_handle_width if not_one_panel else 0)

    @property
    def is_side_index_hidden(self):
        sizes = list(self.sizes())
        try:
            return sizes[self.side_index] == 0
        except IndexError:
            return True

    @property
    def save_name(self):
        ori = 'horizontal' if self.orientation() == Qt.Orientation.Horizontal \
                else 'vertical'
        return self._name + '_' + ori

    def print_sizes(self):
        if self.count() > 1:
            print(self.save_name, 'side:', self.side_index_size, 'other:', end=' ')
            print(list(self.sizes())[self.other_index])

    @property
    def side_index_size(self):
        if self.count() < 2:
            return 0
        return self.sizes()[self.side_index]

    @side_index_size.setter
    def side_index_size(self, val):
        if self.count() < 2:
            return
        side_index_hidden = self.is_side_index_hidden
        if val == 0 and not side_index_hidden:
            self.save_state()
        sizes = list(self.sizes())
        for i in range(len(sizes)):
            sizes[i] = val if i == self.side_index else 10
        self.setSizes(sizes)
        sizes = list(self.sizes())
        total = sum(sizes)
        total_needs_adjustment = self.hide_handle_on_single_panel and side_index_hidden
        if total_needs_adjustment:
            total -= self.original_handle_width
        for i in range(len(sizes)):
            sizes[i] = val if i == self.side_index else total-val
        self.setSizes(sizes)
        self.initialize()
        if total_needs_adjustment:
            # the handle visibility and therefore size distribution will change
            # when the event loop ticks
            self.reapply_sizes.emit(sizes)

    def do_resize(self, *args):
        orig = self.desired_side_size
        QSplitter.resizeEvent(self, self._resize_ev)
        if orig > 20 and self.desired_show:
            c = 0
            while abs(self.side_index_size - orig) > 10 and c < 5:
                self.apply_state(self.get_state(), save_desired=False)
                c += 1

    def resizeEvent(self, ev):
        if self.resize_timer.isActive():
            self.resize_timer.stop()
        self._resize_ev = ev
        self.resize_timer.start()

    def get_state(self):
        if self.count() < 2:
            return (False, 200)
        return (self.desired_show, self.desired_side_size)

    def apply_state(self, state, save_desired=True):
        if state[0]:
            self.side_index_size = state[1]
            if save_desired:
                self.desired_side_size = self.side_index_size
        else:
            self.side_index_size = 0
        self.desired_show = state[0]

    def default_state(self):
        return (self.initial_show, self.initial_side_size)

    # Public API {{{

    def update_desired_state(self):
        self.desired_show = not self.is_side_index_hidden

    def save_state(self):
        if self.count() > 1:
            gprefs[self.save_name+'_state'] = self.get_state()

    @property
    def other_index(self):
        return (self.side_index+1)%2

    def restore_state(self):
        if self.count() > 1:
            state = gprefs.get(self.save_name+'_state',
                    self.default_state())
            self.apply_state(state, save_desired=False)
            self.desired_side_size = state[1]

    def toggle_side_pane(self, hide=None):
        if hide is None:
            action = 'show' if self.is_side_index_hidden else 'hide'
        else:
            action = 'hide' if hide else 'show'
        getattr(self, action+'_side_pane')()

    def show_side_pane(self):
        if self.count() < 2 or not self.is_side_index_hidden:
            return
        if self.desired_side_size == 0:
            self.desired_side_size = self.initial_side_size
        self.apply_state((True, self.desired_side_size))

    def hide_side_pane(self):
        if self.count() < 2 or self.is_side_index_hidden:
            return
        self.apply_state((False, self.desired_side_size))

    def double_clicked(self, *args):
        self.toggle_side_pane()

    # }}}

# }}}


class PaperSizes(QComboBox):  # {{{

    system_default_paper_size = None

    def initialize(self, choices=None):
        from calibre.utils.icu import numeric_sort_key
        if self.system_default_paper_size is None:
            PaperSizes.system_default_paper_size = 'a4'
            if iswindows or ismacos:
                # On Linux, this can cause Qt to load the system cups plugin
                # which can crash: https://bugs.launchpad.net/calibre/+bug/1861741
                PaperSizes.system_default_paper_size = 'letter' if QPrinter().pageSize() == QPagedPaintDevice.PageSize.Letter else 'a4'
        if not choices:
            from calibre.ebooks.conversion.plugins.pdf_output import PAPER_SIZES
            choices = PAPER_SIZES
        for a in sorted(choices, key=numeric_sort_key):
            s = getattr(QPageSize.PageSizeId, a.capitalize())
            sz = QPageSize.definitionSize(s)
            unit = {QPageSize.Unit.Millimeter: 'mm', QPageSize.Unit.Inch: 'inch'}[QPageSize.definitionUnits(s)]
            name = f'{QPageSize.name(s)} ({sz.width():g} x {sz.height():g} {unit})'
            self.addItem(name, a)

    @property
    def get_value_for_config(self):
        return self.currentData()

    @get_value_for_config.setter
    def set_value_for_config(self, val):
        idx = self.findData(val or PaperSizes.system_default_paper_size)
        if idx == -1:
            idx = self.findData('a4')
        self.setCurrentIndex(idx)
# }}}


if __name__ == '__main__':
    from qt.core import QTextEdit
    app = QApplication([])
    w = QTextEdit()
    s = PythonHighlighter(w)
    # w.setSyntaxHighlighter(s)
    w.setText(open(__file__, 'rb').read().decode('utf-8'))
    w.show()
    app.exec()
