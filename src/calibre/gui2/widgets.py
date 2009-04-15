__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Miscellaneous widgets used in the GUI
'''
import re, os, traceback
from PyQt4.QtGui import QListView, QIcon, QFont, QLabel, QListWidget, \
                        QListWidgetItem, QTextCharFormat, QApplication, \
                        QSyntaxHighlighter, QCursor, QColor, QWidget, QDialog, \
                        QPixmap, QMovie, QPalette
from PyQt4.QtCore import QAbstractListModel, QVariant, Qt, SIGNAL, \
                         QRegExp, QSettings, QSize, QModelIndex

from calibre.gui2.jobs2 import DetailView
from calibre.gui2 import human_readable, NONE, TableView, \
                         qstring_to_unicode, error_dialog
from calibre.gui2.filename_pattern_ui import Ui_Form
from calibre import fit_image
from calibre.utils.fontconfig import find_font_families
from calibre.ebooks.metadata.meta import metadata_from_filename
from calibre.utils.config import prefs
from calibre.gui2.dialogs.warning_ui import Ui_Dialog as Ui_WarningDialog

class ProgressIndicator(QWidget):

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.setGeometry(0, 0, 300, 350)
        self.movie = QMovie(':/images/jobs-animated.mng')
        self.ml = QLabel(self)
        self.ml.setMovie(self.movie)
        self.movie.start()
        self.movie.setPaused(True)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.status.font().setBold(True)
        self.status.font().setPointSize(self.font().pointSize()+6)
        self.setVisible(False)

    def start(self, msg=''):
        view = self.parent()
        pwidth, pheight = view.size().width(), view.size().height()
        self.resize(pwidth, min(pheight, 250))
        self.move(0, (pheight-self.size().height())/2.)
        self.ml.resize(self.ml.sizeHint())
        self.ml.move(int((self.size().width()-self.ml.size().width())/2.), 0)
        self.status.resize(self.size().width(), self.size().height()-self.ml.size().height()-10)
        self.status.move(0, self.ml.size().height()+10)
        self.status.setText(msg)
        self.setVisible(True)
        self.movie.setPaused(False)

    def stop(self):
        if self.movie.state() == self.movie.Running:
            self.movie.setPaused(True)
            self.setVisible(False)


class WarningDialog(QDialog, Ui_WarningDialog):

    def __init__(self, title, msg, details, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.msg.setText(msg)
        self.details.setText(details)

class FilenamePattern(QWidget, Ui_Form):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.connect(self.test_button, SIGNAL('clicked()'), self.do_test)
        self.connect(self.re, SIGNAL('returnPressed()'), self.do_test)
        self.re.setText(prefs['filename_pattern'])

    def do_test(self):
        try:
            pat = self.pattern()
        except Exception, err:
            error_dialog(self, _('Invalid regular expression'),
                         _('Invalid regular expression: %s')%err).exec_()
            return
        mi = metadata_from_filename(qstring_to_unicode(self.filename.text()), pat)
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

        self.isbn.setText(_('No match') if mi.isbn is None else str(mi.isbn))


    def pattern(self):
        pat = qstring_to_unicode(self.re.text())
        return re.compile(pat)

    def commit(self):
        pat = self.pattern().pattern
        prefs['filename_pattern'] = pat
        return pat




class ImageView(QLabel):

    MAX_WIDTH  = 400
    MAX_HEIGHT = 300
    DROPABBLE_EXTENSIONS = ('jpg', 'jpeg', 'gif', 'png', 'bmp')

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [qstring_to_unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            urls = [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]
            return [u for u in urls if os.path.splitext(u)[1][1:].lower() in cls.DROPABBLE_EXTENSIONS]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)
        if paths:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        for path in paths:
            pmap = QPixmap()
            pmap.load(path)
            if not pmap.isNull():
                self.setPixmap(pmap)
                event.accept()
                self.emit(SIGNAL('cover_changed()'), paths, Qt.QueuedConnection)
                break

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def setPixmap(self, pixmap):
        QLabel.setPixmap(self, pixmap)
        width, height = fit_image(pixmap.width(), pixmap.height(), self.MAX_WIDTH, self.MAX_HEIGHT)[1:]
        self.setMaximumWidth(width)
        self.setMaximumHeight(height)


class LocationModel(QAbstractListModel):

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.icons = [QVariant(QIcon(':/library')),
                      QVariant(QIcon(':/images/reader.svg')),
                      QVariant(QIcon(':/images/sd.svg')),
                      QVariant(QIcon(':/images/sd.svg'))]
        self.text = [_('Library\n%d\nbooks'),
                     _('Reader\n%s\navailable'),
                     _('Card A\n%s\navailable'),
                     _('Card B\n%s\navailable')]
        self.free = [-1, -1, -1]
        self.count = 0
        self.highlight_row = 0
        self.tooltips = [
                         _('Click to see the list of books available on your computer'),
                         _('Click to see the list of books in the main memory of your reader'),
                         _('Click to see the list of books on storage card A in your reader'),
                         _('Click to see the list of books on storage card B in your reader')
                         ]

    def rowCount(self, parent):
        return 1 + sum([1 for i in self.free if i >= 0])

    def data(self, index, role):
        row = index.row()
        data = NONE
        if role == Qt.DisplayRole:
            text = self.text[row]%(human_readable(self.free[row-1])) if row > 0 \
                            else self.text[row]%self.count
            data = QVariant(text)
        elif role == Qt.DecorationRole:
            data = self.icons[row]
        elif role == Qt.ToolTipRole:
            data = QVariant(self.tooltips[row])
        elif role == Qt.SizeHintRole:
            data = QVariant(QSize(155, 90))
        elif role == Qt.FontRole:
            font = QFont('monospace')
            font.setBold(row == self.highlight_row)
            data = QVariant(font)
        elif role == Qt.ForegroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.HighlightedText))
        elif role == Qt.BackgroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.Highlight))

        return data

    def headerData(self, section, orientation, role):
        return NONE

    def update_devices(self, cp=None, fs=[-1, -1, -1]):
        self.free[0] = fs[0]
        self.free[1] = fs[1]
        self.free[2] = fs[2]
        if cp != None:
            self.free[1] = fs[1] if fs[1] else -1
            self.free[2] = fs[2] if fs[2] else -1
        else:
            self.free[1] = -1
            self.free[2] = -1
        self.reset()

    def location_changed(self, row):
        self.highlight_row = row
        self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                self.index(0), self.index(self.rowCount(QModelIndex())-1))

class LocationView(QListView):

    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setModel(LocationModel(self))
        self.reset()
        self.setCursor(Qt.PointingHandCursor)
        self.currentChanged = self.current_changed

    def count_changed(self, new_count):
        self.model().count = new_count
        self.model().reset()

    def current_changed(self, current, previous):
        if current.isValid():
            i = current.row()
            location = 'library' if i == 0 else 'main' if i == 1 else 'carda' if i == 2 else 'cardb'
            self.emit(SIGNAL('location_selected(PyQt_PyObject)'), location)
            self.model().location_changed(i)

    def location_changed(self, row):
        if 0 <= row and row <= 3:
            self.model().location_changed(row)

class JobsView(TableView):

    def __init__(self, parent):
        TableView.__init__(self, parent)
        self.connect(self, SIGNAL('doubleClicked(QModelIndex)'), self.show_details)

    def show_details(self, index):
        row = index.row()
        job = self.model().row_to_job(row)
        d = DetailView(self, job)
        self.connect(self.model(), SIGNAL('output_received()'), d.update)
        d.exec_()


class FontFamilyModel(QAbstractListModel):

    def __init__(self, *args):
        QAbstractListModel.__init__(self, *args)
        try:
            self.families = find_font_families()
        except:
            self.families = []
            print 'WARNING: Could not load fonts'
            traceback.print_exc()
        self.families.sort()
        self.families[:0] = ['None']

    def rowCount(self, *args):
        return len(self.families)

    def data(self, index, role):
        try:
            family = self.families[index.row()]
        except:
            traceback.print_exc()
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(family)
        if role == Qt.FontRole:
            return QVariant(QFont(family))
        return NONE

    def index_of(self, family):
        return self.families.index(family.strip())


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



class PythonHighlighter(QSyntaxHighlighter):

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
                "|".join([r"\b%s\b" % constant \
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
        settings = QSettings()
        def setDefaultString(name, default):
            value = settings.value(name).toString()
            if value.isEmpty():
                value = default
            Config[name] = value

        for name in ("window", "shell"):
            Config["%swidth" % name] = settings.value("%swidth" % name,
                    QVariant(QApplication.desktop() \
                             .availableGeometry().width() / 2)).toInt()[0]
            Config["%sheight" % name] = settings.value("%sheight" % name,
                    QVariant(QApplication.desktop() \
                             .availableGeometry().height() / 2)).toInt()[0]
            Config["%sy" % name] = settings.value("%sy" % name,
                    QVariant(0)).toInt()[0]
        Config["toolbars"] = settings.value("toolbars").toByteArray()
        Config["splitter"] = settings.value("splitter").toByteArray()
        Config["shellx"] = settings.value("shellx", QVariant(0)).toInt()[0]
        Config["windowx"] = settings.value("windowx", QVariant(QApplication \
                .desktop().availableGeometry().width() / 2)).toInt()[0]
        Config["remembergeometry"] = settings.value("remembergeometry",
                QVariant(True)).toBool()
        Config["startwithshell"] = settings.value("startwithshell",
                QVariant(True)).toBool()
        Config["showwindowinfo"] = settings.value("showwindowinfo",
                QVariant(True)).toBool()
        setDefaultString("shellstartup", """\
    from __future__ import division
    import codecs
    import sys
    sys.stdin = codecs.getreader("UTF8")(sys.stdin)
    sys.stdout = codecs.getwriter("UTF8")(sys.stdout)""")
        setDefaultString("newfile", """\
    #!/usr/bin/env python

    from __future__ import division

    import sys
    """)
        Config["backupsuffix"] = settings.value("backupsuffix",
                QVariant(".bak")).toString()
        setDefaultString("beforeinput", "#>>>")
        setDefaultString("beforeoutput", "#---")
        Config["cwd"] = settings.value("cwd", QVariant(".")).toString()
        Config["tooltipsize"] = settings.value("tooltipsize",
                QVariant(150)).toInt()[0]
        Config["maxlinestoscan"] = settings.value("maxlinestoscan",
                QVariant(5000)).toInt()[0]
        Config["pythondocpath"] = settings.value("pythondocpath",
                QVariant("http://docs.python.org")).toString()
        Config["autohidefinddialog"] = settings.value("autohidefinddialog",
                QVariant(True)).toBool()
        Config["findcasesensitive"] = settings.value("findcasesensitive",
                QVariant(False)).toBool()
        Config["findwholewords"] = settings.value("findwholewords",
                QVariant(False)).toBool()
        Config["tabwidth"] = settings.value("tabwidth",
                QVariant(4)).toInt()[0]
        Config["fontfamily"] = settings.value("fontfamily",
                QVariant("Bitstream Vera Sans Mono")).toString()
        Config["fontsize"] = settings.value("fontsize",
                QVariant(10)).toInt()[0]
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
            Config["%sfontcolor" % name] = settings.value(
                    "%sfontcolor" % name, QVariant(color)).toString()
            Config["%sfontbold" % name] = settings.value(
                    "%sfontbold" % name, QVariant(bold)).toBool()
            Config["%sfontitalic" % name] = settings.value(
                    "%sfontitalic" % name, QVariant(italic)).toBool()


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
            i = text.indexOf(regex)
            while i >= 0:
                length = regex.matchedLength()
                self.setFormat(i, length,
                               PythonHighlighter.Formats[format])
                i = text.indexOf(regex, i + length)

        # Slow but good quality highlighting for comments. For more
        # speed, comment this out and add the following to __init__:
        #   PythonHighlighter.Rules.append((QRegExp(r"#.*"), "comment"))
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

        if text.indexOf(self.stringRe) != -1:
            return
        # This is fooled by triple quotes inside single quoted strings
        for i, state in ((text.indexOf(self.tripleSingleRe),
                          TRIPLESINGLE),
                         (text.indexOf(self.tripleDoubleRe),
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

