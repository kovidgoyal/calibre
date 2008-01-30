##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'''
Miscellanous widgets used in the GUI
'''
from PyQt4.QtGui import QListView, QIcon, QFont, QLabel, QListWidget, \
                        QListWidgetItem, QTextCharFormat, QApplication, \
                        QSyntaxHighlighter, QCursor, QColor
from PyQt4.QtCore import QAbstractListModel, QVariant, Qt, QSize, SIGNAL, \
                         QObject, QRegExp, QSettings

from libprs500.gui2.jobs import DetailView
from libprs500.gui2 import human_readable, NONE, TableView
from libprs500 import fit_image, get_font_families

class ImageView(QLabel):
    
    MAX_WIDTH  = 400
    MAX_HEIGHT = 300
    
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
                      QVariant(QIcon(':/images/sd.svg'))]
        self.text = [_('Library'),
                     _('Reader\n%s available'),
                     _('Card\n%s available')]
        self.free = [-1, -1]
        self.highlight_row = 0            
        
    def rowCount(self, parent):
        return 1 + sum([1 for i in self.free if i >= 0])
    
    def data(self, index, role):
        row = index.row()    
        data = NONE
        if role == Qt.DisplayRole:
            text = self.text[row]%(human_readable(self.free[row-1])) if row > 0 \
                            else self.text[row]
            data = QVariant(text)
        elif role == Qt.DecorationRole:                
            data = self.icons[row]
        elif role == Qt.SizeHintRole:
            if row == 1: 
                return QVariant(QSize(150, 65))
        elif role == Qt.FontRole and row == self.highlight_row: 
            font = QFont()
            font.setBold(True)
            data =  QVariant(font)
        return data
    
    def headerData(self, section, orientation, role):
        return NONE
    
    def update_devices(self, cp=None, fs=[-1, -1, -1]):
        self.free[0] = fs[0]
        self.free[1] = max(fs[1:])
        if cp == None:
            self.free[1] = -1
        self.reset()        
        
    def location_changed(self, row):
        self.highlight_row = row
        self.reset()

class LocationView(QListView):
        
    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setModel(LocationModel(self))
        self.reset()
        QObject.connect(self.selectionModel(), SIGNAL('currentChanged(QModelIndex, QModelIndex)'), self.current_changed)        
    
    def current_changed(self, current, previous):
        i = current.row()
        location = 'library' if i == 0 else 'main' if i == 1 else 'card'
        self.emit(SIGNAL('location_selected(PyQt_PyObject)'), location)
        
    def location_changed(self, row):
        if 0 <= row and row <= 2:
            self.model().location_changed(row)
                        
class JobsView(TableView):
    
    def __init__(self, parent):
        TableView.__init__(self, parent)
        self.connect(self, SIGNAL('activated(QModelIndex)'), self.show_details)
        
    def show_details(self, index):
        row = index.row()
        job = self.model().row_to_job(row)[0]
        DetailView(self, job).exec_()
            

class FontFamilyModel(QAbstractListModel):
    
    def __init__(self, *args):
        QAbstractListModel.__init__(self, *args)
        self.family_map = get_font_families()
        self.families = self.family_map.keys()
        self.families.sort()
        self.families[:0] = ['None']
        
    def rowCount(self, *args):
        return len(self.families)
    
    def data(self, index, role):
        try:
            family = self.families[index.row()]
        except:
            import traceback
            traceback.print_exc()
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(family)
        if role == Qt.FontRole:
            return QVariant(QFont(family))
        return NONE
    
    def path_of(self, family):
        if family != None:
            return self.family_map[family]
        return None
    
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
        def setDefaultString(name, default):
            value = settings.value(name).toString()
            if value.isEmpty():
                value = default
            Config[name] = value
    
        settings = QSettings()
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

