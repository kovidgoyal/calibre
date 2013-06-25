#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import json, os, traceback

from PyQt4.Qt import (Qt, QDialog, QDialogButtonBox, QSyntaxHighlighter, QFont,
                      QRegExp, QApplication, QTextCharFormat, QColor, QCursor,
                      QIcon, QSize)

from calibre import sanitize_file_name_unicode
from calibre.constants import config_dir
from calibre.gui2.dialogs.template_dialog_ui import Ui_TemplateDialog
from calibre.utils.formatter_functions import formatter_functions
from calibre.utils.icu import sort_key
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.library.coloring import (displayable_columns, color_row_key)
from calibre.gui2 import error_dialog, choose_files, pixmap_to_data


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

    def __init__(self, parent, text, mi=None, fm=None, color_field=None,
                 icon_field_key=None, icon_rule_kind=None):
        QDialog.__init__(self, parent)
        Ui_TemplateDialog.__init__(self)
        self.setupUi(self)

        self.coloring = color_field is not None
        self.iconing = icon_field_key is not None

        cols = []
        if fm is not None:
            for key in sorted(displayable_columns(fm),
                              key=lambda(k): sort_key(fm[k]['name']) if k != color_row_key else 0):
                if key == color_row_key and not self.coloring:
                    continue
                from calibre.gui2.preferences.coloring import all_columns_string
                name = all_columns_string if key == color_row_key else fm[key]['name']
                if name:
                    cols.append((name, key))

        self.color_layout.setVisible(False)
        self.icon_layout.setVisible(False)

        if self.coloring:
            self.color_layout.setVisible(True)
            for n1, k1 in cols:
                self.colored_field.addItem(n1, k1)
            self.colored_field.setCurrentIndex(self.colored_field.findData(color_field))
            colors = QColor.colorNames()
            colors.sort()
            self.color_name.addItems(colors)
        elif self.iconing:
            self.icon_layout.setVisible(True)
            for n1, k1 in cols:
                self.icon_field.addItem(n1, k1)
            self.icon_file_names = []
            d = os.path.join(config_dir, 'cc_icons')
            if os.path.exists(d):
                for icon_file in os.listdir(d):
                    icon_file = icu_lower(icon_file)
                    if os.path.exists(os.path.join(d, icon_file)):
                        if icon_file.endswith('.png'):
                            self.icon_file_names.append(icon_file)
            self.icon_file_names.sort(key=sort_key)
            self.update_filename_box()
            self.icon_with_text.setChecked(True)
            if icon_rule_kind == 'icon_only':
                self.icon_without_text.setChecked(True)
            self.icon_field.setCurrentIndex(self.icon_field.findData(icon_field_key))

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
            if fm is not None:
                self.mi.set_all_user_metadata(fm.custom_field_metadata())

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
        self.filename_button.clicked.connect(self.filename_button_clicked)
        self.icon_copy_button.clicked.connect(self.icon_to_clipboard)

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

    def filename_button_clicked(self):
        try:
            path = choose_files(self, 'choose_category_icon',
                        _('Select Icon'), filters=[
                        ('Images', ['png', 'gif', 'jpg', 'jpeg'])],
                    all_files=False, select_only_single_file=True)
            if path:
                icon_path = path[0]
                icon_name = sanitize_file_name_unicode(
                             os.path.splitext(
                                   os.path.basename(icon_path))[0]+'.png')
                if icon_name not in self.icon_file_names:
                    self.icon_file_names.append(icon_name)
                    self.update_filename_box()
                    try:
                        p = QIcon(icon_path).pixmap(QSize(128, 128))
                        d = os.path.join(config_dir, 'cc_icons')
                        if not os.path.exists(os.path.join(d, icon_name)):
                            if not os.path.exists(d):
                                os.makedirs(d)
                            with open(os.path.join(d, icon_name), 'wb') as f:
                                f.write(pixmap_to_data(p, format='PNG'))
                    except:
                        traceback.print_exc()
                self.icon_files.setCurrentIndex(self.icon_files.findText(icon_name))
                self.icon_files.adjustSize()
        except:
            traceback.print_exc()
        return

    def update_filename_box(self):
        self.icon_files.clear()
        self.icon_file_names.sort(key=sort_key)
        self.icon_files.addItem('')
        self.icon_files.addItems(self.icon_file_names)
        for i,filename in enumerate(self.icon_file_names):
            icon = QIcon(os.path.join(config_dir, 'cc_icons', filename))
            self.icon_files.setItemIcon(i+1, icon)

    def color_to_clipboard(self):
        app = QApplication.instance()
        c = app.clipboard()
        c.setText(unicode(self.color_name.currentText()))

    def icon_to_clipboard(self):
        app = QApplication.instance()
        c = app.clipboard()
        c.setText(unicode(self.icon_files.currentText()))

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

            self.rule = (unicode(self.colored_field.itemData(
                                self.colored_field.currentIndex()).toString()), txt)
        elif self.iconing:
            rt = 'icon' if self.icon_with_text.isChecked() else 'icon_only'
            self.rule = (rt,
                         unicode(self.icon_field.itemData(
                                self.icon_field.currentIndex()).toString()),
                         txt)
        else:
            self.rule = ('', txt)
        QDialog.accept(self)
