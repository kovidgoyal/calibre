#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import json

from PyQt4.Qt import (Qt, QDialog, QDialogButtonBox, QSyntaxHighlighter, QFont,
                      QRegExp, QApplication, QTextCharFormat, QColor, QCursor)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog_ui import Ui_TemplateDialog
from calibre.utils.formatter_functions import formatter_functions
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.library.coloring import (displayable_columns)


class ParenPosition:

    def __init__(self, block, pos, paren):
        self.block = block
        self.pos = pos
        self.paren = paren
        self.highlight = False

    def set_highlight(self, to_what):
        self.highlight = to_what

class TemplateHighlighter(QSyntaxHighlighter):

    Config = {}
    Rules = []
    Formats = {}
    BN_FACTOR = 1000

    KEYWORDS = ["program"]

    def __init__(self, parent=None):
        super(TemplateHighlighter, self).__init__(parent)

        self.initializeFormats()

        TemplateHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % keyword for keyword in self.KEYWORDS])),
                "keyword"))
        TemplateHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % builtin for builtin in
                          formatter_functions().get_builtins()])),
                "builtin"))

        TemplateHighlighter.Rules.append((QRegExp(
                r"\b[+-]?[0-9]+[lL]?\b"
                r"|\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b"
                r"|\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"),
                "number"))

        stringRe = QRegExp(r"""(?:[^:]'[^']*'|"[^"]*")""")
        stringRe.setMinimal(True)
        TemplateHighlighter.Rules.append((stringRe, "string"))

        lparenRe = QRegExp(r'\(')
        lparenRe.setMinimal(True)
        TemplateHighlighter.Rules.append((lparenRe, "lparen"))
        rparenRe = QRegExp(r'\)')
        rparenRe.setMinimal(True)
        TemplateHighlighter.Rules.append((rparenRe, "rparen"))

        self.regenerate_paren_positions()
        self.highlighted_paren = False

    def initializeFormats(self):
        Config = self.Config
        Config["fontfamily"] = "monospace"
        #Config["fontsize"] = 10
        for name, color, bold, italic in (
                ("normal", "#000000", False, False),
                ("keyword", "#000080", True, False),
                ("builtin", "#0000A0", False, False),
                ("comment", "#007F00", False, True),
                ("string", "#808000", False, False),
                ("number", "#924900", False, False),
                ("lparen", "#000000", True, True),
                ("rparen", "#000000", True, True)):
            Config["%sfontcolor" % name] = color
            Config["%sfontbold" % name] = bold
            Config["%sfontitalic" % name] = italic

        baseFormat = QTextCharFormat()
        baseFormat.setFontFamily(Config["fontfamily"])
        #baseFormat.setFontPointSize(Config["fontsize"])

        for name in ("normal", "keyword", "builtin", "comment",
                     "string", "number", "lparen", "rparen"):
            format = QTextCharFormat(baseFormat)
            format.setForeground(QColor(Config["%sfontcolor" % name]))
            if Config["%sfontbold" % name]:
                format.setFontWeight(QFont.Bold)
            format.setFontItalic(Config["%sfontitalic" % name])
            self.Formats[name] = format

    def find_paren(self, bn, pos):
        dex = bn * self.BN_FACTOR + pos
        return self.paren_pos_map.get(dex, None)

    def highlightBlock(self, text):
        bn = self.currentBlock().blockNumber()
        textLength = text.length()

        self.setFormat(0, textLength, self.Formats["normal"])

        if text.isEmpty():
            pass
        elif text[0] == "#":
            self.setFormat(0, text.length(), self.Formats["comment"])
            return

        for regex, format in TemplateHighlighter.Rules:
            i = regex.indexIn(text)
            while i >= 0:
                length = regex.matchedLength()
                if format in ['lparen', 'rparen']:
                    pp = self.find_paren(bn, i)
                    if pp and pp.highlight:
                        self.setFormat(i, length, self.Formats[format])
                else:
                    self.setFormat(i, length, self.Formats[format])
                i = regex.indexIn(text, i + length)

        if self.generate_paren_positions:
            t = unicode(text)
            i = 0
            foundQuote = False
            while i < len(t):
                c = t[i]
                if c == ':':
                    # Deal with the funky syntax of template program mode.
                    # This won't work if there are more than one template
                    # expression in the document.
                    if not foundQuote and i+1 < len(t) and t[i+1] == "'":
                        i += 2
                elif c in ["'", '"']:
                    foundQuote = True
                    i += 1
                    j = t[i:].find(c)
                    if j < 0:
                        i = len(t)
                    else:
                        i = i + j
                elif c in ['(', ')']:
                    pp = ParenPosition(bn, i, c)
                    self.paren_positions.append(pp)
                    self.paren_pos_map[bn*self.BN_FACTOR+i] = pp
                i += 1

    def rehighlight(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QSyntaxHighlighter.rehighlight(self)
        QApplication.restoreOverrideCursor()

    def check_cursor_pos(self, chr, block, pos_in_block):
        found_pp = -1
        for i, pp in enumerate(self.paren_positions):
            pp.set_highlight(False)
            if pp.block == block and pp.pos == pos_in_block:
                found_pp = i

        if chr not in ['(', ')']:
            if self.highlighted_paren:
                self.rehighlight()
                self.highlighted_paren = False
            return

        if found_pp >= 0:
            stack = 0
            if chr == '(':
                list = self.paren_positions[found_pp+1:]
            else:
                list = reversed(self.paren_positions[0:found_pp])
            for pp in list:
                if pp.paren == chr:
                    stack += 1
                elif stack:
                    stack -= 1
                else:
                    pp.set_highlight(True)
                    self.paren_positions[found_pp].set_highlight(True)
                    break
        self.highlighted_paren = True
        self.rehighlight()

    def regenerate_paren_positions(self):
        self.generate_paren_positions = True
        self.paren_positions = []
        self.paren_pos_map = {}
        self.rehighlight()
        self.generate_paren_positions = False

class TemplateDialog(QDialog, Ui_TemplateDialog):

    def __init__(self, parent, text, mi=None, fm=None, color_field=None):
        QDialog.__init__(self, parent)
        Ui_TemplateDialog.__init__(self)
        self.setupUi(self)

        self.coloring = color_field is not None
        if self.coloring:
            cols = sorted([k for k in displayable_columns(fm)])
            self.colored_field.addItems(cols)
            self.colored_field.setCurrentIndex(self.colored_field.findText(color_field))
            colors = QColor.colorNames()
            colors.sort()
            self.color_name.addItems(colors)
        else:
            self.colored_field.setVisible(False)
            self.colored_field_label.setVisible(False)
            self.color_chooser_label.setVisible(False)
            self.color_name.setVisible(False)
            self.color_copy_button.setVisible(False)
        if mi:
            self.mi = mi
        else:
            self.mi = Metadata(_('Title'), [_('Author')])
            self.mi.author_sort = _('Author Sort')
            self.mi.series = _('Series')
            self.mi.series_index = 3
            self.mi.rating = 4.0
            self.mi.tags = [_('Tag 1'), _('Tag 2')]
            self.mi.languages = ['eng']

        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.last_text = ''
        self.highlighter = TemplateHighlighter(self.textbox.document())
        self.textbox.cursorPositionChanged.connect(self.text_cursor_changed)
        self.textbox.textChanged.connect(self.textbox_changed)

        self.textbox.setTabStopWidth(10)
        self.source_code.setTabStopWidth(10)
        self.documentation.setReadOnly(True)
        self.source_code.setReadOnly(True)

        if text is not None:
            self.textbox.setPlainText(text)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(_('&Cancel'))
        self.color_copy_button.clicked.connect(self.color_to_clipboard)

        try:
            with open(P('template-functions.json'), 'rb') as f:
                self.builtin_source_dict = json.load(f, encoding='utf-8')
        except:
            self.builtin_source_dict = {}

        self.funcs = formatter_functions().get_functions()
        self.builtins = formatter_functions().get_builtins()

        func_names = sorted(self.funcs)
        self.function.clear()
        self.function.addItem('')
        self.function.addItems(func_names)
        self.function.setCurrentIndex(0)
        self.function.currentIndexChanged[str].connect(self.function_changed)
        self.textbox_changed()
        self.rule = (None, '')

        tt = _('Template language tutorial')
        self.template_tutorial.setText(
                '<a href="http://manual.calibre-ebook.com/template_lang.html">'
                '%s</a>'%tt)
        tt = _('Template function reference')
        self.template_func_reference.setText(
                '<a href="http://manual.calibre-ebook.com/template_ref.html">'
                '%s</a>'%tt)

    def color_to_clipboard(self):
        app = QApplication.instance()
        c = app.clipboard()
        c.setText(unicode(self.color_name.currentText()))

    def textbox_changed(self):
        cur_text = unicode(self.textbox.toPlainText())
        if self.last_text != cur_text:
            self.last_text = cur_text
            self.highlighter.regenerate_paren_positions()
            self.text_cursor_changed()
            self.template_value.setText(
                SafeFormat().safe_format(cur_text, self.mi,
                                                _('EXCEPTION: '), self.mi))

    def text_cursor_changed(self):
        cursor = self.textbox.textCursor()
        position = cursor.position()
        t = unicode(self.textbox.toPlainText())
        if position > 0 and position <= len(t):
            block_number = cursor.blockNumber()
            pos_in_block = cursor.positionInBlock() - 1
            self.highlighter.check_cursor_pos(t[position-1], block_number,
                                              pos_in_block)

    def function_changed(self, toWhat):
        name = unicode(toWhat)
        self.source_code.clear()
        self.documentation.clear()
        if name in self.funcs:
            self.documentation.setPlainText(self.funcs[name].doc)
            if name in self.builtins and name in self.builtin_source_dict:
                self.source_code.setPlainText(self.builtin_source_dict[name])
            else:
                self.source_code.setPlainText(self.funcs[name].program_text)

    def accept(self):
        txt = unicode(self.textbox.toPlainText()).rstrip()
        if self.coloring:
            if self.colored_field.currentIndex() == -1:
                error_dialog(self, _('No column chosen'),
                    _('You must specify a column to be colored'), show=True)
                return
            if not txt:
                error_dialog(self, _('No template provided'),
                    _('The template box cannot be empty'), show=True)
                return

        self.rule = (unicode(self.colored_field.currentText()), txt)
        QDialog.accept(self)
