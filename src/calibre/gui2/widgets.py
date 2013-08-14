__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Miscellaneous widgets used in the GUI
'''
import re, os

from PyQt4.Qt import (QIcon, QFont, QLabel, QListWidget, QAction,
        QListWidgetItem, QTextCharFormat, QApplication, QSyntaxHighlighter,
        QCursor, QColor, QWidget, QPixmap, QSplitterHandle, QToolButton,
        QVariant, Qt, SIGNAL, pyqtSignal, QRegExp, QSize, QSplitter, QPainter,
        QLineEdit, QComboBox, QPen, QGraphicsScene, QMenu, QStringListModel,
        QCompleter, QStringList, QTimer, QRect, QGraphicsView, QByteArray)

from calibre.gui2 import (error_dialog, pixmap_to_data, gprefs,
        warning_dialog)
from calibre.gui2.filename_pattern_ui import Ui_Form
from calibre import fit_image
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.config import prefs, XMLConfig
from calibre.gui2.progress_indicator import ProgressIndicator as _ProgressIndicator
from calibre.gui2.dnd import (dnd_has_image, dnd_get_image, dnd_get_files,
    IMAGE_EXTENSIONS, dnd_has_extension, DownloadDialog)

history = XMLConfig('history')

class ProgressIndicator(QWidget):  # {{{

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.setGeometry(0, 0, 300, 350)
        self.pi = _ProgressIndicator(self)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.setVisible(False)
        self.pos = None

    def start(self, msg=''):
        view = self.parent()
        pwidth, pheight = view.size().width(), view.size().height()
        self.resize(pwidth, min(pheight, 250))
        if self.pos is None:
            self.move(0, (pheight-self.size().height())/2.)
        else:
            self.move(self.pos[0], self.pos[1])
        self.pi.resize(self.pi.sizeHint())
        self.pi.move(int((self.size().width()-self.pi.size().width())/2.), 0)
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

        self.connect(self.test_button, SIGNAL('clicked()'), self.do_test)
        self.connect(self.re.lineEdit(), SIGNAL('returnPressed()'), self.do_test)
        self.re.lineEdit().textChanged.connect(lambda x: self.changed_signal.emit())

    def initialize(self, defaults=False):
        # Get all itmes in the combobox. If we are resting
        # to defaults we don't want to lose what the user
        # has added.
        val_hist = [unicode(self.re.lineEdit().text())] + [unicode(self.re.itemText(i)) for i in xrange(self.re.count())]
        self.re.clear()

        if defaults:
            val = prefs.defaults['filename_pattern']
        else:
            val = prefs['filename_pattern']
        self.re.lineEdit().setText(val)

        val_hist += gprefs.get('filename_pattern_history', [
                               '(?P<title>.+)', '(?P<author>[^_-]+) -?\s*(?P<series>[^_0-9-]*)(?P<series_index>[0-9]*)\s*-\s*(?P<title>[^_].+) ?'])
        if val in val_hist:
            del val_hist[val_hist.index(val)]
        val_hist.insert(0, val)
        for v in val_hist:
            # Ensure we don't have duplicate items.
            if v and self.re.findText(v) == -1:
                self.re.addItem(v)
        self.re.setCurrentIndex(0)

    def do_test(self):
        from calibre.ebooks.metadata.meta import metadata_from_filename
        fname = unicode(self.filename.text())
        ext = os.path.splitext(fname)[1][1:].lower()
        if ext not in BOOK_EXTENSIONS:
            return warning_dialog(self, _('Test name invalid'),
                    _('The name <b>%r</b> does not appear to end with a'
                        ' file extension. The name must end with a file '
                        ' extension like .epub or .mobi')%fname, show=True)

        try:
            pat = self.pattern()
        except Exception as err:
            error_dialog(self, _('Invalid regular expression'),
                         _('Invalid regular expression: %s')%err).exec_()
            return
        mi = metadata_from_filename(fname, pat)
        if mi.title:
            self.title.setText(mi.title)
        else:
            self.title.setText(_('No match'))
        if mi.authors:
            self.authors.setText(', '.join(mi.authors))
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

        if mi.pubdate:
            self.pubdate.setText(mi.pubdate.strftime('%Y-%m-%d'))

        self.isbn.setText(_('No match') if mi.isbn is None else str(mi.isbn))

    def pattern(self):
        pat = unicode(self.re.lineEdit().text())
        return re.compile(pat)

    def commit(self):
        pat = self.pattern().pattern
        prefs['filename_pattern'] = pat

        history = []
        history_pats = [unicode(self.re.lineEdit().text())] + [unicode(self.re.itemText(i)) for i in xrange(self.re.count())]
        for p in history_pats[:14]:
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
        if dnd_has_extension(md, self.DROPABBLE_EXTENSIONS):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.CopyAction)
        md = event.mimeData()
        # Now look for ebook files
        urls, filenames = dnd_get_files(md, self.DROPABBLE_EXTENSIONS)
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
        if event.key() == Qt.Key_Delete:
            self.delete_format.emit()
        else:
            return QListWidget.keyPressEvent(self, event)

# }}}

class ImageDropMixin(object):  # {{{
    '''
    Adds support for dropping images onto widgets and a context menu for
    copy/pasting images.
    '''
    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS

    def __init__(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if dnd_has_extension(md, self.DROPABBLE_EXTENSIONS) or \
                dnd_has_image(md):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.CopyAction)
        md = event.mimeData()

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
                    pmap.loadFromData(open(d.fpath, 'rb').read())
                    if not pmap.isNull():
                        self.handle_image_drop(pmap)

    def handle_image_drop(self, pmap):
        self.set_pixmap(pmap)
        self.cover_changed.emit(pixmap_to_data(pmap))

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def get_pixmap(self):
        return self.pixmap()

    def set_pixmap(self, pmap):
        self.setPixmap(pmap)

    def contextMenuEvent(self, ev):
        cm = QMenu(self)
        paste = cm.addAction(_('Paste Cover'))
        copy = cm.addAction(_('Copy Cover'))
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        cm.exec_(ev.globalPos())

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setPixmap(self.get_pixmap())

    def paste_from_clipboard(self):
        cb = QApplication.instance().clipboard()
        pmap = cb.pixmap()
        if pmap.isNull() and cb.supportsSelection():
            pmap = cb.pixmap(cb.Selection)
        if not pmap.isNull():
            self.set_pixmap(pmap)
            self.cover_changed.emit(
                    pixmap_to_data(pmap))
# }}}

class ImageView(QWidget, ImageDropMixin):  # {{{

    BORDER_WIDTH = 1
    cover_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._pixmap = QPixmap(self)
        self.setMinimumSize(QSize(150, 200))
        ImageDropMixin.__init__(self)
        self.draw_border = True
        self.show_size = False

    def setPixmap(self, pixmap):
        if not isinstance(pixmap, QPixmap):
            raise TypeError('Must use a QPixmap')
        self._pixmap = pixmap
        self.updateGeometry()
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
            pmap = pmap.scaled(nw, nh, Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation)
        w, h = pmap.width(), pmap.height()
        x = int(abs(cw - w)/2.)
        y = int(abs(ch - h)/2.)
        target = QRect(x, y, w, h)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(target, pmap)
        if self.draw_border:
            pen = QPen()
            pen.setWidth(self.BORDER_WIDTH)
            p.setPen(pen)
            p.drawRect(target)
        if self.show_size:
            sztgt = target.adjusted(0, 0, 0, -4)
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            sz = u'\u00a0%d x %d\u00a0'%(ow, oh)
            flags = Qt.AlignBottom|Qt.AlignRight|Qt.TextSingleLine
            szrect = p.boundingRect(sztgt, flags, sz)
            p.fillRect(szrect.adjusted(0, 0, 0, 4), QColor(0, 0, 0, 200))
            p.setPen(QPen(QColor(255,255,255)))
            p.drawText(sztgt, flags, sz)
        p.end()
# }}}

class CoverView(QGraphicsView, ImageDropMixin):  # {{{

    cover_changed = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        QGraphicsView.__init__(self, *args, **kwargs)
        ImageDropMixin.__init__(self)

    def get_pixmap(self):
        for item in self.scene.items():
            if hasattr(item, 'pixmap'):
                return item.pixmap()

    def set_pixmap(self, pmap):
        self.scene = QGraphicsScene()
        self.scene.addPixmap(pmap)
        self.setScene(self.scene)

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

class LineEditECM(object):  # {{{

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        case_menu = QMenu(_('Change Case'))
        action_upper_case = case_menu.addAction(_('Upper Case'))
        action_lower_case = case_menu.addAction(_('Lower Case'))
        action_swap_case = case_menu.addAction(_('Swap Case'))
        action_title_case = case_menu.addAction(_('Title Case'))
        action_capitalize = case_menu.addAction(_('Capitalize'))

        self.connect(action_upper_case, SIGNAL('triggered()'), self.upper_case)
        self.connect(action_lower_case, SIGNAL('triggered()'), self.lower_case)
        self.connect(action_swap_case, SIGNAL('triggered()'), self.swap_case)
        self.connect(action_title_case, SIGNAL('triggered()'), self.title_case)
        self.connect(action_capitalize, SIGNAL('triggered()'), self.capitalize)

        menu.addMenu(case_menu)
        menu.exec_(event.globalPos())

    def upper_case(self):
        self.setText(unicode(self.text()).upper())

    def lower_case(self):
        self.setText(unicode(self.text()).lower())

    def swap_case(self):
        self.setText(unicode(self.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.setText(titlecase(unicode(self.text())))

    def capitalize(self):
        from calibre.utils.icu import capitalize
        self.setText(capitalize(unicode(self.text())))

# }}}

class EnLineEdit(LineEditECM, QLineEdit):  # {{{

    '''
    Enhanced QLineEdit.

    Includes an extended content menu.
    '''

    pass
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
        if completion_prefix.strip() != '':
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

        self.connect(self, SIGNAL('textChanged(QString)'), self.text_changed)

        self.completer = ItemsCompleter(self, complete_items)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)

        self.connect(self,
            SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
            self.completer.update)
        self.connect(self.completer, SIGNAL('activated(QString)'),
            self.complete_text)

        self.completer.setWidget(self)

    def update_items_cache(self, complete_items):
        self.completer.update_items_cache(complete_items)

    def set_separator(self, sep):
        self.separator = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    def text_changed(self, text):
        all_text = unicode(text)
        text = all_text[:self.cursorPosition()]
        prefix = text.split(self.separator)[-1].strip()

        text_items = []
        for t in all_text.split(self.separator):
            t1 = unicode(t).strip()
            if t1 != '':
                text_items.append(t)
        text_items = list(set(text_items))

        self.emit(SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
            text_items, prefix)

    def complete_text(self, text):
        cursor_pos = self.cursorPosition()
        before_text = unicode(self.text())[:cursor_pos]
        after_text = unicode(self.text())[cursor_pos:]
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
        self.setAutoCompletionCaseSensitivity(Qt.CaseInsensitive)
        self.setMinimumContentsLength(20)

    def text(self):
        return unicode(self.currentText())

    def setText(self, text):
        idx = self.findText(text, Qt.MatchFixedString|Qt.MatchCaseSensitive)
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
        self.setInsertPolicy(self.NoInsert)
        self.setMaxCount(10)

    def setPlaceholderText(self, txt):
        return self.lineEdit().setPlaceholderText(txt)

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.addItems(QStringList(history.get(self.store_name, [])))
        self.setEditText('')
        self.lineEdit().editingFinished.connect(self.save_history)

    def save_history(self):
        items = []
        ct = unicode(self.currentText())
        if ct:
            items.append(ct)
        for i in range(self.count()):
            item = unicode(self.itemText(i))
            if item not in items:
                items.append(item)
        self.blockSignals(True)
        self.clear()
        self.addItems(items)
        self.setEditText(ct)
        self.blockSignals(False)
        history.set(self.store_name, items)

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
        self.currentIndexChanged[int].connect(self.index_changed)
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
    way to programatically list all supported encodings
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

    Rules = []
    Formats = {}
    Config = {}

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
        super(PythonHighlighter, self).__init__(parent)
        if not self.Config:
            self.loadConfig()

        self.initializeFormats()

        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % keyword for keyword in self.KEYWORDS])),
                "keyword"))
        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % builtin for builtin in self.BUILTINS])),
                "builtin"))
        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % constant
                for constant in self.CONSTANTS])), "constant"))
        PythonHighlighter.Rules.append((QRegExp(
                r"\b[+-]?[0-9]+[lL]?\b"
                r"|\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b"
                r"|\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"),
                "number"))
        PythonHighlighter.Rules.append((QRegExp(
                r"\bPyQt4\b|\bQt?[A-Z][a-z]\w+\b"), "pyqt"))
        PythonHighlighter.Rules.append((QRegExp(r"\b@\w+\b"), "decorator"))
        stringRe = QRegExp(r"""(?:'[^']*'|"[^"]*")""")
        stringRe.setMinimal(True)
        PythonHighlighter.Rules.append((stringRe, "string"))
        self.stringRe = QRegExp(r"""(:?"["]".*"["]"|'''.*''')""")
        self.stringRe.setMinimal(True)
        PythonHighlighter.Rules.append((self.stringRe, "string"))
        self.tripleSingleRe = QRegExp(r"""'''(?!")""")
        self.tripleDoubleRe = QRegExp(r'''"""(?!')''')

    @classmethod
    def loadConfig(cls):
        Config = cls.Config

        for name in ("window", "shell"):
            Config["%swidth" % name] = QVariant(QApplication.desktop().availableGeometry().width() / 2).toInt()[0]
            Config["%sheight" % name] = QVariant(QApplication.desktop().availableGeometry().height() / 2).toInt()[0]
            Config["%sy" % name] = QVariant(0).toInt()[0]
        Config["toolbars"] = QByteArray(b'')
        Config["splitter"] = QByteArray(b'')
        Config["shellx"] = QVariant(0).toInt()[0]
        Config["windowx"] = QVariant(QApplication.desktop().availableGeometry().width() / 2).toInt()[0]
        Config["remembergeometry"] = QVariant(True).toBool()
        Config["startwithshell"] = QVariant(True).toBool()
        Config["showwindowinfo"] = QVariant(True).toBool()
        Config["backupsuffix"] = QVariant(".bak").toString()
        Config["cwd"]  = QVariant(".").toString()
        Config["tooltipsize"] = QVariant(150).toInt()[0]
        Config["maxlinestoscan"] = QVariant(5000).toInt()[0]
        Config["pythondocpath"] = QVariant("http://docs.python.org").toString()
        Config["autohidefinddialog"] = QVariant(True).toBool()
        Config["findcasesensitive"] = QVariant(False).toBool()
        Config["findwholewords"] = QVariant(False).toBool()
        Config["tabwidth"] = QVariant(4).toInt()[0]
        Config["fontfamily"] = QVariant("monospace").toString()
        Config["fontsize"] = QVariant(10).toInt()[0]
        for name, color, bold, italic in (
                ("normal", "#000000", False, False),
                ("keyword", "#000080", True, False),
                ("builtin", "#0000A0", False, False),
                ("constant", "#0000C0", False, False),
                ("decorator", "#0000E0", False, False),
                ("comment", "#007F00", False, True),
                ("string", "#808000", False, False),
                ("number", "#924900", False, False),
                ("error", "#FF0000", False, False),
                ("pyqt", "#50621A", False, False)):
            Config["%sfontcolor" % name] = QVariant(color).toString()
            Config["%sfontbold" % name] = QVariant(bold).toBool()
            Config["%sfontitalic" % name] = QVariant(italic).toBool()

    @classmethod
    def initializeFormats(cls):
        Config = cls.Config
        baseFormat = QTextCharFormat()
        baseFormat.setFontFamily(Config["fontfamily"])
        baseFormat.setFontPointSize(Config["fontsize"])
        for name in ("normal", "keyword", "builtin", "constant",
                "decorator", "comment", "string", "number", "error",
                "pyqt"):
            format = QTextCharFormat(baseFormat)
            format.setForeground(QColor(Config["%sfontcolor" % name]))
            if Config["%sfontbold" % name]:
                format.setFontWeight(QFont.Bold)
            format.setFontItalic(Config["%sfontitalic" % name])
            PythonHighlighter.Formats[name] = format

    def highlightBlock(self, text):
        NORMAL, TRIPLESINGLE, TRIPLEDOUBLE, ERROR = range(4)

        textLength = text.length()
        prevState = self.previousBlockState()

        self.setFormat(0, textLength,
                       PythonHighlighter.Formats["normal"])

        if text.startsWith("Traceback") or text.startsWith("Error: "):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           PythonHighlighter.Formats["error"])
            return
        if prevState == ERROR and \
           not (text.startsWith('>>>') or text.startsWith("#")):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           PythonHighlighter.Formats["error"])
            return

        for regex, format in PythonHighlighter.Rules:
            i = regex.indexIn(text)
            while i >= 0:
                length = regex.matchedLength()
                self.setFormat(i, length,
                               PythonHighlighter.Formats[format])
                i = regex.indexIn(text, i + length)

        # Slow but good quality highlighting for comments. For more
        # speed, comment this out and add the following to __init__:
        # PythonHighlighter.Rules.append((QRegExp(r"#.*"), "comment"))
        if text.isEmpty():
            pass
        elif text[0] == "#":
            self.setFormat(0, text.length(),
                           PythonHighlighter.Formats["comment"])
        else:
            stack = []
            for i, c in enumerate(text):
                if c in ('"', "'"):
                    if stack and stack[-1] == c:
                        stack.pop()
                    else:
                        stack.append(c)
                elif c == "#" and len(stack) == 0:
                    self.setFormat(i, text.length(),
                                   PythonHighlighter.Formats["comment"])
                    break

        self.setCurrentBlockState(NORMAL)

        if self.stringRe.indexIn(text) != -1:
            return
        # This is fooled by triple quotes inside single quoted strings
        for i, state in ((self.tripleSingleRe.indexIn(text),
                          TRIPLESINGLE),
                         (self.tripleDoubleRe.indexIn(text),
                          TRIPLEDOUBLE)):
            if self.previousBlockState() == state:
                if i == -1:
                    i = text.length()
                    self.setCurrentBlockState(state)
                self.setFormat(0, i + 3,
                               PythonHighlighter.Formats["string"])
            elif i > -1:
                self.setCurrentBlockState(state)
                self.setFormat(i, text.length(),
                               PythonHighlighter.Formats["string"])

    def rehighlight(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QSyntaxHighlighter.rehighlight(self)
        QApplication.restoreOverrideCursor()

# }}}

# Splitter {{{
class SplitterHandle(QSplitterHandle):

    double_clicked = pyqtSignal(object)

    def __init__(self, orientation, splitter):
        QSplitterHandle.__init__(self, orientation, splitter)
        splitter.splitterMoved.connect(self.splitter_moved,
                type=Qt.QueuedConnection)
        self.double_clicked.connect(splitter.double_clicked,
                type=Qt.QueuedConnection)
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

        self.splitter = splitter
        if splitter is not None:
            splitter.state_changed.connect(self.update_state)
        self.setCursor(Qt.PointingHandCursor)
        self.shortcut = ''
        if shortcut:
            self.shortcut = shortcut

    def set_state_to_show(self, *args):
        self.setChecked(False)
        self.setText(_('Show %(label)s [%(shortcut)s]')%dict(label=self.label, shortcut=self.shortcut))
        self.setToolTip(self.text())
        self.setStatusTip(self.text())

    def set_state_to_hide(self, *args):
        self.setChecked(True)
        self.setText(_('Hide %(label)s [%(shortcut)s]')%dict(
            label=self.label, shortcut=self.shortcut))
        self.setToolTip(self.text())
        self.setStatusTip(self.text())

    def update_state(self, *args):
        if self.splitter.is_side_index_hidden:
            self.set_state_to_show()
        else:
            self.set_state_to_hide()

class Splitter(QSplitter):

    state_changed = pyqtSignal(object)

    def __init__(self, name, label, icon, initial_show=True,
            initial_side_size=120, connect_button=True,
            orientation=Qt.Horizontal, side_index=0, parent=None, shortcut=None):
        QSplitter.__init__(self, parent)
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
        self.splitterMoved.connect(self.splitter_moved, type=Qt.QueuedConnection)
        self.button = LayoutButton(icon, label, self, shortcut=shortcut)
        if connect_button:
            self.button.clicked.connect(self.double_clicked)

        if shortcut is not None:
            self.action_toggle = QAction(QIcon(icon), _('Toggle') + ' ' + label,
                    self)
            self.action_toggle.triggered.connect(self.toggle_triggered)
            if parent is not None:
                parent.addAction(self.action_toggle)
                if hasattr(parent, 'keyboard'):
                    parent.keyboard.register_shortcut('splitter %s %s'%(name,
                        label), unicode(self.action_toggle.text()),
                        default_keys=(shortcut,), action=self.action_toggle)
                else:
                    self.action_toggle.setShortcut(shortcut)
            else:
                self.action_toggle.setShortcut(shortcut)

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

    @property
    def is_side_index_hidden(self):
        sizes = list(self.sizes())
        try:
            return sizes[self.side_index] == 0
        except IndexError:
            return True

    @property
    def save_name(self):
        ori = 'horizontal' if self.orientation() == Qt.Horizontal \
                else 'vertical'
        return self._name + '_' + ori

    def print_sizes(self):
        if self.count() > 1:
            print self.save_name, 'side:', self.side_index_size, 'other:',
            print list(self.sizes())[self.other_index]

    @dynamic_property
    def side_index_size(self):
        def fget(self):
            if self.count() < 2:
                return 0
            return self.sizes()[self.side_index]

        def fset(self, val):
            if self.count() < 2:
                return
            if val == 0 and not self.is_side_index_hidden:
                self.save_state()
            sizes = list(self.sizes())
            for i in range(len(sizes)):
                sizes[i] = val if i == self.side_index else 10
            self.setSizes(sizes)
            total = sum(self.sizes())
            sizes = list(self.sizes())
            for i in range(len(sizes)):
                sizes[i] = val if i == self.side_index else total-val
            self.setSizes(sizes)
            self.initialize()

        return property(fget=fget, fset=fset)

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


