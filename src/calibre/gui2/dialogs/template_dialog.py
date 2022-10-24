#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import json, os, traceback, re
from functools import partial
import sys

from qt.core import (Qt, QDialog, QDialogButtonBox, QSyntaxHighlighter, QFont,
                      QApplication, QTextCharFormat, QColor, QCursor,
                      QIcon, QSize, QPalette, QLineEdit, QFontInfo,
                      QFontDatabase, QVBoxLayout, QTableWidget, QTableWidgetItem,
                      QComboBox, QAbstractItemView, QTextOption, QFontMetrics)

from calibre import sanitize_file_name
from calibre.constants import config_dir
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import (gprefs, error_dialog, choose_files, choose_save_file,
                          pixmap_to_data, question_dialog)
from calibre.gui2.dialogs.template_dialog_ui import Ui_TemplateDialog
from calibre.library.coloring import (displayable_columns, color_row_key)
from calibre.utils.config_base import tweaks
from calibre.utils.date import DEFAULT_DATE
from calibre.utils.formatter_functions import formatter_functions, StoredObjectType
from calibre.utils.formatter import StopException, PythonTemplateContext
from calibre.utils.icu import sort_key
from calibre.utils.localization import localize_user_manual_link


class ParenPosition:

    def __init__(self, block, pos, paren):
        self.block = block
        self.pos = pos
        self.paren = paren
        self.highlight = False

    def set_highlight(self, to_what):
        self.highlight = to_what


class TemplateHighlighter(QSyntaxHighlighter):
    # Code in this class is liberally borrowed from gui2.widgets.PythonHighlighter

    BN_FACTOR = 1000

    KEYWORDS_GPM = ['if', 'then', 'else', 'elif', 'fi', 'for', 'rof',
                    'separator', 'break', 'continue', 'return', 'in', 'inlist',
                    'def', 'fed', 'limit']

    KEYWORDS_PYTHON = ["and", "as", "assert", "break", "class", "continue", "def",
                       "del", "elif", "else", "except", "exec", "finally", "for", "from",
                       "global", "if", "import", "in", "is", "lambda", "not", "or",
                       "pass", "print", "raise", "return", "try", "while", "with",
                       "yield"]

    BUILTINS_PYTHON = ["abs", "all", "any", "basestring", "bool", "callable", "chr",
                       "classmethod", "cmp", "compile", "complex", "delattr", "dict",
                       "dir", "divmod", "enumerate", "eval", "execfile", "exit", "file",
                       "filter", "float", "frozenset", "getattr", "globals", "hasattr",
                       "hex", "id", "int", "isinstance", "issubclass", "iter", "len",
                       "list", "locals", "long", "map", "max", "min", "object", "oct",
                       "open", "ord", "pow", "property", "range", "reduce", "repr",
                       "reversed", "round", "set", "setattr", "slice", "sorted",
                       "staticmethod", "str", "sum", "super", "tuple", "type", "unichr",
                       "unicode", "vars", "xrange", "zip"]

    CONSTANTS_PYTHON = ["False", "True", "None", "NotImplemented", "Ellipsis"]

    def __init__(self, parent=None, builtin_functions=None):
        super().__init__(parent)
        self.initialize_formats()
        self.initialize_rules(builtin_functions, for_python=False)
        self.regenerate_paren_positions()
        self.highlighted_paren = False

    def initialize_rules(self, builtin_functions, for_python=False):
        self.for_python = for_python
        r = []

        def a(a, b):
            r.append((re.compile(a), b))

        if not for_python:
            a(r"\b[a-zA-Z]\w*\b(?!\(|\s+\()"
              r"|\$+#?[a-zA-Z]\w*",
              "identifier")
            a(r"^program:", "keymode")
            a("|".join([r"\b%s\b" % keyword for keyword in self.KEYWORDS_GPM]), "keyword")
            a("|".join([r"\b%s\b" % builtin for builtin in
                            (builtin_functions if builtin_functions else
                                                formatter_functions().get_builtins())]),
                "builtin")
            a(r"""(?<!:)'[^']*'|"[^"]*\"""", "string")
        else:
            a(r"^python:", "keymode")
            a("|".join([r"\b%s\b" % keyword for keyword in self.KEYWORDS_PYTHON]), "keyword")
            a("|".join([r"\b%s\b" % builtin for builtin in self.BUILTINS_PYTHON]), "builtin")
            a("|".join([r"\b%s\b" % constant for constant in self.CONSTANTS_PYTHON]), "constant")
            a(r"\bPyQt6\b|\bqt.core\b|\bQt?[A-Z][a-z]\w+\b", "pyqt")
            a(r"@\w+(\.\w+)?\b", "decorator")

            stringRe = r'''(["'])(?:(?!\1)[^\\]|\\.)*\1'''
            a(stringRe, "string")
            self.stringRe = re.compile(stringRe)
            self.checkTripleInStringRe = re.compile(r"""((?:"|'){3}).*?\1""")
            self.tripleSingleRe = re.compile(r"""'''(?!")""")
            self.tripleDoubleRe = re.compile(r'''"""(?!')''')
        a(
            r"\b[+-]?[0-9]+[lL]?\b"
            r"|\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b"
            r"|\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b",
            "number")

        a(r'\(', "lparen")
        a(r'\)', "rparen")
        self.Rules = tuple(r)

    def initialize_formats(self):
        font_name = gprefs.get('gpm_template_editor_font', None)
        size = gprefs['gpm_template_editor_font_size']
        if font_name is None:
            font = QFont()
            font.setFixedPitch(True)
            font.setPointSize(size)
            font_name = font.family()
        config = self.Config = {}
        config["fontfamily"] = font_name
        app_palette = QApplication.instance().palette()

        all_formats = (
            # name, color, bold, italic
            ("normal", None, False, False),
            ("keyword", app_palette.color(QPalette.ColorRole.Link).name(), True, False),
            ("builtin", app_palette.color(QPalette.ColorRole.Link).name(), False, False),
            ("constant", app_palette.color(QPalette.ColorRole.Link).name(), False, False),
            ("identifier", None, False, True),
            ("comment", "#007F00", False, True),
            ("string", "#808000", False, False),
            ("number", "#924900", False, False),
            ("decorator", "#FF8000", False, True),
            ("pyqt", None, False, False),
            ("lparen", None, True, True),
            ("rparen", None, True, True))

        for name, color, bold, italic in all_formats:
            config["%sfontcolor" % name] = color
            config["%sfontbold" % name] = bold
            config["%sfontitalic" % name] = italic
        base_format = QTextCharFormat()
        base_format.setFontFamilies([config["fontfamily"]])
        config["fontsize"] = size
        base_format.setFontPointSize(config["fontsize"])

        self.Formats = {}
        for name, color, bold, italic in all_formats:
            format_ = QTextCharFormat(base_format)
            color = config["%sfontcolor" % name]
            if color:
                format_.setForeground(QColor(color))
            if config["%sfontbold" % name]:
                format_.setFontWeight(QFont.Weight.Bold)
            format_.setFontItalic(config["%sfontitalic" % name])
            self.Formats[name] = format_

    def find_paren(self, bn, pos):
        dex = bn * self.BN_FACTOR + pos
        return self.paren_pos_map.get(dex, None)

    def replace_strings_with_dash(self, mo):
        found = mo.group(0)
        return '-' * len(found)

    def highlightBlock(self, text):
        NORMAL, TRIPLESINGLE, TRIPLEDOUBLE = range(3)

        bn = self.currentBlock().blockNumber()
        textLength = len(text)

        self.setFormat(0, textLength, self.Formats["normal"])

        if not text:
            pass
        elif text[0] == "#":
            self.setFormat(0, textLength, self.Formats["comment"])
            return

        for regex, format_ in self.Rules:
            for m in regex.finditer(text):
                i, length = m.start(), m.end() - m.start()
                if format_ in ['lparen', 'rparen']:
                    pp = self.find_paren(bn, i)
                    if pp and pp.highlight:
                        self.setFormat(i, length, self.Formats[format_])
                elif format_ == 'keymode':
                    if bn > 0 and i == 0:
                        continue
                    self.setFormat(i, length, self.Formats['keyword'])
                else:
                    self.setFormat(i, length, self.Formats[format_])

        # Deal with comments not at the beginning of the line.
        if self.for_python and '#' in text:
            # Remove any strings from the text before we check for '#'. This way
            # we avoid thinking a # inside a string starts a comment.
            t = re.sub(self.stringRe, self.replace_strings_with_dash, text)
            sharp_pos = t.find('#')
            if sharp_pos >= 0:  # Do we still have a #?
                self.setFormat(sharp_pos, len(text), self.Formats["comment"])

        self.setCurrentBlockState(NORMAL)

        if self.for_python and self.checkTripleInStringRe.search(text) is None:
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
                    self.setFormat(0, i + 3, self.Formats["string"])
                elif i > -1:
                    self.setCurrentBlockState(state)
                    self.setFormat(i, len(text), self.Formats["string"])

        if self.generate_paren_positions:
            t = str(text)
            i = 0
            found_quote = False
            while i < len(t):
                c = t[i]
                if c == ':':
                    # Deal with the funky syntax of template program mode.
                    # This won't work if there are more than one template
                    # expression in the document.
                    if not found_quote and i+1 < len(t) and t[i+1] == "'":
                        i += 2
                elif c in ["'", '"']:
                    found_quote = True
                    i += 1
                    j = t[i:].find(c)
                    if j < 0:
                        i = len(t)
                    else:
                        i = i + j
                elif c in ('(', ')'):
                    pp = ParenPosition(bn, i, c)
                    self.paren_positions.append(pp)
                    self.paren_pos_map[bn*self.BN_FACTOR+i] = pp
                i += 1

    def rehighlight(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        super().rehighlight()
        QApplication.restoreOverrideCursor()

    def check_cursor_pos(self, chr_, block, pos_in_block):
        paren_pos = -1
        for i, pp in enumerate(self.paren_positions):
            pp.set_highlight(False)
            if pp.block == block and pp.pos == pos_in_block:
                paren_pos = i

        if chr_ not in ('(', ')'):
            if self.highlighted_paren:
                self.rehighlight()
                self.highlighted_paren = False
            return

        if paren_pos >= 0:
            stack = 0
            if chr_ == '(':
                list_ = self.paren_positions[paren_pos+1:]
            else:
                list_ = reversed(self.paren_positions[0:paren_pos])
            for pp in list_:
                if pp.paren == chr_:
                    stack += 1
                elif stack:
                    stack -= 1
                else:
                    pp.set_highlight(True)
                    self.paren_positions[paren_pos].set_highlight(True)
                    break
        self.highlighted_paren = True
        self.rehighlight()

    def regenerate_paren_positions(self):
        self.generate_paren_positions = True
        self.paren_positions = []
        self.paren_pos_map = {}
        self.rehighlight()
        self.generate_paren_positions = False


translate_table = str.maketrans({
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\\': '\\\\',
})


class TemplateDialog(QDialog, Ui_TemplateDialog):

    def __init__(self, parent, text, mi=None, fm=None, color_field=None,
                 icon_field_key=None, icon_rule_kind=None, doing_emblem=False,
                 text_is_placeholder=False, dialog_is_st_editor=False,
                 global_vars=None, all_functions=None, builtin_functions=None,
                 python_context_object=None):
        QDialog.__init__(self, parent)
        Ui_TemplateDialog.__init__(self)
        self.setupUi(self)

        self.coloring = color_field is not None
        self.iconing = icon_field_key is not None
        self.embleming = doing_emblem
        self.dialog_is_st_editor = dialog_is_st_editor
        self.global_vars = global_vars or {}
        self.python_context_object = python_context_object or PythonTemplateContext()

        cols = []
        self.fm = fm
        if fm is not None:
            for key in sorted(displayable_columns(fm),
                              key=lambda k: sort_key(fm[k]['name'] if k != color_row_key else 0)):
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
                self.colored_field.addItem(n1 +
                       (' (' + k1 + ')' if k1 != color_row_key else ''), k1)
            self.colored_field.setCurrentIndex(self.colored_field.findData(color_field))
        elif self.iconing or self.embleming:
            self.icon_layout.setVisible(True)
            self.icon_select_layout.setContentsMargins(0, 0, 0, 0)
            if self.embleming:
                self.icon_kind_label.setVisible(False)
                self.icon_kind.setVisible(False)
                self.icon_chooser_label.setVisible(False)
                self.icon_field.setVisible(False)

            for n1, k1 in cols:
                self.icon_field.addItem(f'{n1} ({k1})', k1)
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

            if self.iconing:
                dex = 0
                from calibre.gui2.preferences.coloring import icon_rule_kinds
                for i,tup in enumerate(icon_rule_kinds):
                    txt,val = tup
                    self.icon_kind.addItem(txt, userData=(val))
                    if val == icon_rule_kind:
                        dex = i
                self.icon_kind.setCurrentIndex(dex)
                self.icon_field.setCurrentIndex(self.icon_field.findData(icon_field_key))

        self.setup_saved_template_editor(not dialog_is_st_editor, dialog_is_st_editor)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.all_functions = all_functions if all_functions else formatter_functions().get_functions()
        self.builtins = (builtin_functions if builtin_functions else
                         formatter_functions().get_builtins_and_aliases())

        # Set up the breakpoint bar
        s = gprefs.get('template_editor_break_on_print', False)
        self.go_button.setEnabled(s)
        self.remove_all_button.setEnabled(s)
        self.set_all_button.setEnabled(s)
        self.toggle_button.setEnabled(s)
        self.breakpoint_line_box.setEnabled(s)
        self.breakpoint_line_box_label.setEnabled(s)
        self.break_box.setChecked(s)
        self.break_box.stateChanged.connect(self.break_box_changed)
        self.go_button.clicked.connect(self.go_button_pressed)

        # Set up the display table
        self.table_column_widths = None
        try:
            self.table_column_widths = \
                        gprefs.get('template_editor_table_widths', None)
        except:
            pass
        self.set_mi(mi, fm)

        self.last_text = ''
        self.highlighting_gpm = True
        self.highlighter = TemplateHighlighter(self.textbox.document(), builtin_functions=self.builtins)
        self.textbox.cursorPositionChanged.connect(self.text_cursor_changed)
        self.textbox.textChanged.connect(self.textbox_changed)
        self.set_editor_font()

        self.documentation.setReadOnly(True)
        self.source_code.setReadOnly(True)

        if text is not None:
            if text_is_placeholder:
                self.textbox.setPlaceholderText(text)
                self.textbox.clear()
                text = ''
            else:
                self.textbox.setPlainText(text)
        else:
            text = ''
        self.original_text = text

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText(_('&OK'))
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText(_('&Cancel'))

        self.color_copy_button.clicked.connect(self.color_to_clipboard)
        self.filename_button.clicked.connect(self.filename_button_clicked)
        self.icon_copy_button.clicked.connect(self.icon_to_clipboard)

        try:
            with open(P('template-functions.json'), 'rb') as f:
                self.builtin_source_dict = json.load(f, encoding='utf-8')
        except:
            self.builtin_source_dict = {}

        func_names = sorted(self.all_functions)
        self.function.clear()
        self.function.addItem('')
        for f in func_names:
            self.function.addItem('{}  --  {}'.format(f,
                               self.function_type_string(f, longform=False)), f)
        self.function.setCurrentIndex(0)
        self.function.currentIndexChanged.connect(self.function_changed)
        self.rule = (None, '')

        tt = _('Template language tutorial')
        self.template_tutorial.setText(
            '<a href="{}">{}</a>'.format(
                localize_user_manual_link('https://manual.calibre-ebook.com/template_lang.html'), tt))
        tt = _('Template function reference')
        self.template_func_reference.setText(
            '<a href="{}">{}</a>'.format(
                localize_user_manual_link('https://manual.calibre-ebook.com/generated/en/template_ref.html'), tt))

        self.textbox.setFocus()
        self.set_up_font_boxes()
        self.toggle_button.clicked.connect(self.toggle_button_pressed)
        self.remove_all_button.clicked.connect(self.remove_all_button_pressed)
        self.set_all_button.clicked.connect(self.set_all_button_pressed)

        self.load_button.clicked.connect(self.load_template_from_file)
        self.save_button.clicked.connect(self.save_template)

        self.set_word_wrap(gprefs.get('gpm_template_editor_word_wrap_mode', True))
        self.textbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.textbox.customContextMenuRequested.connect(self.show_context_menu)
        # Now geometry
        self.restore_geometry(gprefs, 'template_editor_dialog_geometry')

    def setup_saved_template_editor(self, show_buttonbox, show_doc_and_name):
        self.buttonBox.setVisible(show_buttonbox)
        self.new_doc_label.setVisible(show_doc_and_name)
        self.new_doc.setVisible(show_doc_and_name)
        self.template_name_label.setVisible(show_doc_and_name)
        self.template_name.setVisible(show_doc_and_name)

    def set_mi(self, mi, fm):
        '''
        This sets the metadata for the test result books table. It doesn't reset
        the contents of the field selectors for editing rules.
        '''
        self.fm = fm
        if mi:
            if not isinstance(mi, list):
                mi = (mi, )
        else:
            mi = Metadata(_('Title'), [_('Author')])
            mi.author_sort = _('Author Sort')
            mi.series = ngettext('Series', 'Series', 1)
            mi.series_index = 3
            mi.rating = 4.0
            mi.tags = [_('Tag 1'), _('Tag 2')]
            mi.languages = ['eng']
            mi.id = 1
            if self.fm is not None:
                mi.set_all_user_metadata(self.fm.custom_field_metadata())
            else:
                # No field metadata. Grab a copy from the current library so
                # that we can validate any custom column names. The values for
                # the columns will all be empty, which in some very unusual
                # cases might cause formatter errors. We can live with that.
                from calibre.gui2.ui import get_gui
                fm = get_gui().current_db.new_api.field_metadata
                mi.set_all_user_metadata(fm.custom_field_metadata())
            for col in mi.get_all_user_metadata(False):
                if fm[col]['datatype'] == 'datetime':
                    mi.set(col, DEFAULT_DATE)
                elif fm[col]['datatype'] in ('int', 'float', 'rating'):
                    mi.set(col, 2)
                elif fm[col]['datatype'] == 'bool':
                    mi.set(col, False)
                elif fm[col]['is_multiple']:
                    mi.set(col, (col,))
                else:
                    mi.set(col, col, 1)
            mi = (mi, )
        self.mi = mi
        tv = self.template_value
        tv.setColumnCount(2)
        tv.setHorizontalHeaderLabels((_('Book title'), _('Template value')))
        tv.horizontalHeader().setStretchLastSection(True)
        tv.horizontalHeader().sectionResized.connect(self.table_column_resized)
        tv.setRowCount(len(mi))
        # Set the height of the table
        h = tv.rowHeight(0) * min(len(mi), 5)
        h += 2 * tv.frameWidth() + tv.horizontalHeader().height()
        tv.setMinimumHeight(h)
        tv.setMaximumHeight(h)
        # Set the size of the title column
        if self.table_column_widths:
            tv.setColumnWidth(0, self.table_column_widths[0])
        else:
            tv.setColumnWidth(0, tv.fontMetrics().averageCharWidth() * 10)
        tv.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tv.setRowCount(len(mi))
        # Use our own widget to get rid of elision. setTextElideMode() doesn't work
        for r in range(0, len(mi)):
            w = QLineEdit(tv)
            w.setReadOnly(True)
            w.setText(mi[r].title)
            tv.setCellWidget(r, 0, w)
            w = QLineEdit(tv)
            w.setReadOnly(True)
            tv.setCellWidget(r, 1, w)
        self.set_waiting_message()

    def set_waiting_message(self):
        if self.break_box.isChecked():
            for i in range(len(self.mi)):
                self.template_value.cellWidget(i, 1).setText('')
            self.template_value.cellWidget(0, 1).setText(
                _("*** Breakpoints are enabled. Waiting for the 'Go' button to be pressed"))

    def show_context_menu(self, point):
        m = self.textbox.createStandardContextMenu()
        m.addSeparator()
        word_wrapping = gprefs['gpm_template_editor_word_wrap_mode']
        if word_wrapping:
            ca = m.addAction(_('Disable word wrap'))
            ca.setIcon(QIcon.ic('list_remove.png'))
        else:
            ca = m.addAction(_('Enable word wrap'))
            ca.setIcon(QIcon.ic('ok.png'))
        ca.triggered.connect(partial(self.set_word_wrap, not word_wrapping))
        m.addSeparator()
        ca = m.addAction(_('Add Python template definition text'))
        ca.triggered.connect(self.add_python_template_header_text)
        m.addSeparator()
        ca = m.addAction(_('Load template from the Template tester'))
        m.addSeparator()
        ca.triggered.connect(self.load_last_template_text)
        ca = m.addAction(_('Load template from file'))
        ca.setIcon(QIcon.ic('document_open.png'))
        ca.triggered.connect(self.load_template_from_file)
        ca = m.addAction(_('Save template to file'))
        ca.setIcon(QIcon.ic('save.png'))
        ca.triggered.connect(self.save_template)
        m.exec(self.textbox.mapToGlobal(point))

    def add_python_template_header_text(self):
        self.textbox.setPlainText('''python:
def evaluate(book, context):
    # book is a calibre metadata object
    # context is an instance of calibre.utils.formatter.PythonTemplateContext,
    # which currently contains the following attributes:
    # db: a calibre legacy database object.
    # globals: the template global variable dictionary.
    # arguments: is a list of arguments if the template is called by a GPM template, otherwise None.
    # funcs: used to call Built-in/User functions and Stored GPM/Python templates.
    # Example: context.funcs.list_re_group()

    # your Python code goes here
    return 'a string'
''')

    def set_word_wrap(self, to_what):
        gprefs['gpm_template_editor_word_wrap_mode'] = to_what
        self.textbox.setWordWrapMode(QTextOption.WrapMode.WordWrap if to_what else QTextOption.WrapMode.NoWrap)

    def load_last_template_text(self):
        from calibre.customize.ui import find_plugin
        tt = find_plugin('Template Tester')
        if tt and tt.actual_plugin_:
            self.textbox.setPlainText(tt.actual_plugin_.last_template_text())
        else:
            # I don't think we can get here, but just in case ...
            self.textbox.setPlainText(_('No Template tester text is available'))

    def load_template_from_file(self):
        filename = choose_files(self, 'template_dialog_save_templates',
                _('Load template from file'),
                filters=[
                    (_('Template file'), ['txt'])
                    ], select_only_single_file=True)
        if filename:
            with open(filename[0]) as f:
                self.textbox.setPlainText(f.read())

    def save_template(self):
        filename = choose_save_file(self, 'template_dialog_save_templates',
                _('Save template to file'),
                filters=[
                    (_('Template file'), ['txt'])
                    ])
        if filename:
            with open(filename, 'w') as f:
                f.write(str(self.textbox.toPlainText()))

    def get_current_font(self):
        font_name = gprefs.get('gpm_template_editor_font', None)
        size = gprefs['gpm_template_editor_font_size']
        if font_name is None:
            font = QFont()
            font.setFixedPitch(True)
            font.setPointSize(size)
        else:
            font = QFont(font_name, pointSize=size)
        return font

    def set_editor_font(self):
        font = self.get_current_font()
        fm = QFontMetrics(font)
        chars = tweaks['template_editor_tab_stop_width']
        w = fm.averageCharWidth() * chars
        self.textbox.setTabStopDistance(w)
        self.source_code.setTabStopDistance(w)
        self.textbox.setFont(font)
        self.highlighter.initialize_formats()
        self.highlighter.rehighlight()

    def set_up_font_boxes(self):
        font = self.get_current_font()
        self.font_box.setWritingSystem(QFontDatabase.WritingSystem.Latin)
        self.font_box.setCurrentFont(font)
        self.font_box.setEditable(False)
        gprefs['gpm_template_editor_font'] = str(font.family())
        self.font_size_box.setValue(font.pointSize())
        self.font_box.currentFontChanged.connect(self.font_changed)
        self.font_size_box.valueChanged.connect(self.font_size_changed)

    def font_changed(self, font):
        fi = QFontInfo(font)
        gprefs['gpm_template_editor_font'] = str(fi.family())
        self.set_editor_font()

    def font_size_changed(self, toWhat):
        gprefs['gpm_template_editor_font_size'] = toWhat
        self.set_editor_font()

    def break_box_changed(self, new_state):
        gprefs['template_editor_break_on_print'] = new_state != 0
        self.go_button.setEnabled(new_state != 0)
        self.remove_all_button.setEnabled(new_state != 0)
        self.set_all_button.setEnabled(new_state != 0)
        self.toggle_button.setEnabled(new_state != 0)
        self.breakpoint_line_box.setEnabled(new_state != 0)
        self.breakpoint_line_box_label.setEnabled(new_state != 0)
        if new_state == 0:
            self.display_values(str(self.textbox.toPlainText()))
        else:
            self.set_waiting_message()

    def go_button_pressed(self):
        self.display_values(str(self.textbox.toPlainText()))

    def remove_all_button_pressed(self):
        self.textbox.set_clicked_line_numbers(set())

    def set_all_button_pressed(self):
        self.textbox.set_clicked_line_numbers({i for i in range(1, self.textbox.blockCount()+1)})

    def toggle_button_pressed(self):
        ln = self.breakpoint_line_box.value()
        if ln > self.textbox.blockCount():
            return
        cln = self.textbox.clicked_line_numbers
        if ln:
            if ln in self.textbox.clicked_line_numbers:
                cln.discard(ln)
            else:
                cln.add(ln)
            self.textbox.set_clicked_line_numbers(cln)

    def break_reporter(self, txt, val, locals_={}, line_number=0):
        l = self.template_value.selectionModel().selectedRows()
        mi_to_use = self.mi[0 if len(l) == 0 else l[0].row()]
        if self.break_box.isChecked():
            if line_number is None or line_number not in self.textbox.clicked_line_numbers:
                return
            self.break_reporter_dialog = BreakReporter(self, mi_to_use,
                                                       txt, val, locals_, line_number)
            if not self.break_reporter_dialog.exec():
                raise StopException()

    def filename_button_clicked(self):
        try:
            path = choose_files(self, 'choose_category_icon',
                        _('Select icon'), filters=[
                        ('Images', ['png', 'gif', 'jpg', 'jpeg'])],
                    all_files=False, select_only_single_file=True)
            if path:
                icon_path = path[0]
                icon_name = sanitize_file_name(
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
        c.setText(str(self.color_name.color))

    def icon_to_clipboard(self):
        app = QApplication.instance()
        c = app.clipboard()
        c.setText(str(self.icon_files.currentText()))

    @property
    def is_python(self):
        return self.textbox.toPlainText().startswith('python:')

    def textbox_changed(self):
        cur_text = str(self.textbox.toPlainText())
        if self.is_python:
            if self.highlighting_gpm is True:
                self.highlighter.initialize_rules(self.builtins, True)
                self.highlighting_gpm = False
                self.break_box.setEnabled(True)
        elif not self.highlighting_gpm:
            self.highlighter.initialize_rules(self.builtins, False)
            self.highlighting_gpm = True
            self.break_box.setEnabled(True)
        if self.last_text != cur_text:
            self.last_text = cur_text
            self.highlighter.regenerate_paren_positions()
            self.text_cursor_changed()
            if not self.break_box.isChecked():
                self.display_values(cur_text)
            else:
                self.set_waiting_message()

    def trace_lines(self, frame, event, arg):
        if event != 'line':
            return
        # Only respond to events in the "string" which is the template
        if frame.f_code.co_filename != '<string>':
            return
        # Check that there is a breakpoint at the line
        if frame.f_lineno not in self.textbox.clicked_line_numbers:
            return
        l = self.template_value.selectionModel().selectedRows()
        mi_to_use = self.mi[0 if len(l) == 0 else l[0].row()]
        self.break_reporter_dialog = PythonBreakReporter(self, mi_to_use, frame)
        if not self.break_reporter_dialog.exec():
            raise StopException()

    def trace_calls(self, frame, event, arg):
        if event != 'call':
            return
        # If this is the "string" file (the template), return the trace_lines function
        if frame.f_code.co_filename == '<string>':
            return self.trace_lines
        return None

    def display_values(self, txt):
        tv = self.template_value
        l = self.template_value.selectionModel().selectedRows()
        break_on_mi = 0 if len(l) == 0 else l[0].row()
        for r,mi in enumerate(self.mi):
            w = tv.cellWidget(r, 0)
            w.setText(mi.title)
            w.setCursorPosition(0)
            if self.break_box.isChecked() and r == break_on_mi and self.is_python:
                sys.settrace(self.trace_calls)
            else:
                sys.settrace(None)
            try:
                v = SafeFormat().safe_format(txt, mi, _('EXCEPTION:'),
                                 mi, global_vars=self.global_vars,
                                 template_functions=self.all_functions,
                                 break_reporter=self.break_reporter if r == break_on_mi else None,
                                 python_context_object=self.python_context_object)
                w = tv.cellWidget(r, 1)
                w.setText(v.translate(translate_table))
                w.setCursorPosition(0)
            finally:
                sys.settrace(None)

    def text_cursor_changed(self):
        cursor = self.textbox.textCursor()
        position = cursor.position()
        t = str(self.textbox.toPlainText())
        if position > 0 and position <= len(t):
            block_number = cursor.blockNumber()
            pos_in_block = cursor.positionInBlock() - 1
            self.highlighter.check_cursor_pos(t[position-1], block_number,
                                              pos_in_block)

    def function_type_string(self, name, longform=True):
        if self.all_functions[name].object_type is StoredObjectType.PythonFunction:
            if name in self.builtins:
                return (_('Built-in template function') if longform else
                            _('Built-in function'))
            return (_('User defined Python template function') if longform else
                            _('User function'))
        elif self.all_functions[name].object_type is StoredObjectType.StoredPythonTemplate:
            return (_('Stored user defined Python template') if longform else _('Stored template'))
        return (_('Stored user defined GPM template') if longform else _('Stored template'))

    def function_changed(self, toWhat):
        name = str(self.function.itemData(toWhat))
        self.source_code.clear()
        self.documentation.clear()
        self.func_type.clear()
        if name in self.all_functions:
            self.documentation.setPlainText(self.all_functions[name].doc)
            if name in self.builtins and name in self.builtin_source_dict:
                self.source_code.setPlainText(self.builtin_source_dict[name])
            else:
                self.source_code.setPlainText(self.all_functions[name].program_text)
            self.func_type.setText(self.function_type_string(name, longform=True))

    def table_column_resized(self, col, old, new):
        self.table_column_widths = []
        for c in range(0, self.template_value.columnCount()):
            self.table_column_widths.append(self.template_value.columnWidth(c))

    def save_geometry(self):
        gprefs['template_editor_table_widths'] = self.table_column_widths
        super().save_geometry(gprefs, 'template_editor_dialog_geometry')

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            # Check about ESC to avoid killing the dialog by mistake
            if self.textbox.toPlainText() != self.original_text:
                r = question_dialog(self, _('Discard changes?'),
                      _('Do you really want to close this dialog, discarding any changes?'))
                if not r:
                    return
        QDialog.keyPressEvent(self, ev)

    def accept(self):
        txt = str(self.textbox.toPlainText()).rstrip()
        if (self.coloring or self.iconing or self.embleming) and not txt:
            error_dialog(self, _('No template provided'),
                _('The template box cannot be empty'), show=True)
            return
        if self.coloring:
            if self.colored_field.currentIndex() == -1:
                error_dialog(self, _('No column chosen'),
                    _('You must specify a column to be colored'), show=True)
                return
            self.rule = (str(self.colored_field.itemData(
                                self.colored_field.currentIndex()) or ''), txt)
        elif self.iconing:
            if self.icon_field.currentIndex() == -1:
                error_dialog(self, _('No column chosen'),
                    _('You must specify the column where the icons are applied'), show=True)
                return
            rt = str(self.icon_kind.itemData(self.icon_kind.currentIndex()) or '')
            self.rule = (rt,
                         str(self.icon_field.itemData(
                                self.icon_field.currentIndex()) or ''),
                         txt)
        elif self.embleming:
            self.rule = ('icon', 'title', txt)
        else:
            self.rule = ('', txt)
        self.save_geometry()
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)
        if self.dialog_is_st_editor:
            parent = self.parent()
            while True:
                if hasattr(parent, 'reject'):
                    parent.reject()
                    break
                parent = parent.parent()
                if parent is None:
                    break


class BreakReporterItem(QTableWidgetItem):

    def __init__(self, txt):
        super().__init__(txt.translate(translate_table) if txt else txt)
        self.setFlags(self.flags() & ~(Qt.ItemFlag.ItemIsEditable))


class BreakReporterBase(QDialog):

    def setup_ui(self, mi, line_number, locals_, leading_rows):
        self.mi = mi
        self.leading_rows = leading_rows
        self.setModal(True)
        l = QVBoxLayout(self)
        t = self.table = QTableWidget(self)
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        t.setColumnCount(2)
        t.setHorizontalHeaderLabels((_('Name'), _('Value')))
        t.setRowCount(leading_rows)
        l.addWidget(t)

        self.table_column_widths = None
        try:
            self.table_column_widths = \
                        gprefs.get('template_editor_break_table_widths', None)
            t.setColumnWidth(0, self.table_column_widths[0])
        except:
            t.setColumnWidth(0, t.fontMetrics().averageCharWidth() * 20)
        t.horizontalHeader().sectionResized.connect(self.table_column_resized)
        t.horizontalHeader().setStretchLastSection(True)

        bb = QDialogButtonBox()
        b = bb.addButton(_('&Continue'), QDialogButtonBox.ButtonRole.AcceptRole)
        b.setIcon(QIcon.ic('sync-right.png'))
        b.setToolTip(_('Continue running the template'))
        b.setDefault(True)
        l.addWidget(bb)
        b = bb.addButton(_('&Stop'), QDialogButtonBox.ButtonRole.RejectRole)
        b.setIcon(QIcon.ic('list_remove.png'))
        b.setToolTip(_('Stop running the template'))
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.setLayout(l)
        self.setWindowTitle(_('Break: line {0}, book {1}').format(line_number, self.mi.title))

        self.mi_combo = QComboBox()
        t.setCellWidget(leading_rows-1, 0, self.mi_combo)
        self.mi_combo.addItems(self.get_field_keys())
        self.mi_combo.setToolTip('Choose a book metadata field to display')
        self.mi_combo.currentTextChanged.connect(self.get_field_value)
        self.mi_combo.setCurrentIndex(self.mi_combo.findText('title'))
        self.restore_geometry(gprefs, 'template_editor_break_geometry')
        self.setup_locals(locals_)

    def setup_locals(self, locals_):
        raise NotImplementedError

    def add_local_line(self, locals, row, key):
        itm = BreakReporterItem(key)
        itm.setToolTip(_('A variable in the template'))
        self.table.setItem(row, 0, itm)
        itm = BreakReporterItem(repr(locals[key]))
        itm.setToolTip(_('The value of the variable'))
        self.table.setItem(row, 1, itm)

    def get_field_value(self, field):
        val = self.displayable_field_value(self.mi, field)
        self.table.setItem(self.leading_rows-1, 1, BreakReporterItem(val))

    def displayable_field_value(self, mi, field):
        raise NotImplementedError

    def table_column_resized(self, col, old, new):
        self.table_column_widths = []
        for c in range(0, self.table.columnCount()):
            self.table_column_widths.append(self.table.columnWidth(c))

    def get_field_keys(self):
        from calibre.gui2.ui import get_gui
        keys = set(get_gui().current_db.new_api.field_metadata.displayable_field_keys())
        keys.discard('sort')
        keys.discard('timestamp')
        keys.add('title_sort')
        keys.add('date')
        return sorted(keys)

    def save_geometry(self):
        super().save_geometry(gprefs, 'template_editor_break_geometry')
        gprefs['template_editor_break_table_widths'] = self.table_column_widths

    def reject(self):
        self.save_geometry()
        QDialog.reject(self)

    def accept(self):
        self.save_geometry()
        QDialog.accept(self)


class BreakReporter(BreakReporterBase):

    def __init__(self, parent, mi, op_label, op_value, locals_, line_number):
        super().__init__(parent)
        self.setup_ui(mi, line_number, locals_, leading_rows=2)
        self.table.setItem(0, 0, BreakReporterItem(op_label))
        self.table.item(0,0).setToolTip(_('The name of the template language operation'))
        self.table.setItem(0, 1, BreakReporterItem(op_value))

    def setup_locals(self, locals):
        local_names = sorted(locals.keys())
        rows = len(local_names)
        self.table.setRowCount(rows+2)
        for i,k in enumerate(local_names, start=2):
            self.add_local_line(locals, i, k)

    def displayable_field_value(self, mi, field):
        return self.mi.format_field('timestamp' if field == 'date' else field)[1]


class PythonBreakReporter(BreakReporterBase):

    def __init__(self, parent, mi, frame):
        super().__init__(parent)
        self.frame = frame
        line_number = frame.f_lineno
        locals = frame.f_locals
        self.setup_ui(mi, line_number, locals, leading_rows=1)

    def setup_locals(self, locals):
        locals = self.frame.f_locals
        local_names = sorted(k for k in locals.keys() if k not in ('book', 'context'))
        rows = len(local_names)
        self.table.setRowCount(rows+1)

        for i,k in enumerate(local_names, start=1):
            if k in ('book', 'context'):
                continue
            self.add_local_line(locals, i, k)

    def displayable_field_value(self, mi, field):
        return repr(self.mi.get('timestamp' if field == 'date' else field))


class EmbeddedTemplateDialog(TemplateDialog):

    def __init__(self, parent):
        TemplateDialog.__init__(self, parent, _('A General Program Mode Template'), text_is_placeholder=True,
                                dialog_is_st_editor=True)
        self.setParent(parent)
        self.setWindowFlags(Qt.WindowType.Widget)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    from calibre.ebooks.metadata.book.base import field_metadata
    d = TemplateDialog(None, '{title}', fm=field_metadata)
    d.exec()
    del app
