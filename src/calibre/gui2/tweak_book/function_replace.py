#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, io, weakref, sys
from cStringIO import StringIO

from PyQt5.Qt import (
    pyqtSignal, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel, QFontMetrics,
    QSize, Qt, QApplication, QIcon)

from calibre.ebooks.oeb.polish.utils import apply_func_to_match_groups, apply_func_to_html_text
from calibre.gui2 import error_dialog
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.tweak_book import dictionaries
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.tweak_book.editor.text import TextEdit
from calibre.utils.config import JSONConfig
from calibre.utils.icu import capitalize, upper, lower, swapcase
from calibre.utils.titlecase import titlecase
from calibre.utils.localization import localize_user_manual_link

user_functions = JSONConfig('editor-search-replace-functions')


def compile_code(src, name='<string>'):
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    if not src or not src.strip():
        src = EMPTY_FUNC
    # Python complains if there is a coding declaration in a unicode string
    src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src, flags=re.MULTILINE)
    # Translate newlines to \n
    src = io.StringIO(src, newline=None).getvalue()
    code = compile(src, name, 'exec')

    namespace = {}
    exec code in namespace
    return namespace


class Function(object):

    def __init__(self, name, source=None, func=None):
        self._source = source
        self.is_builtin = source is None
        self.name = name
        if func is None:
            self.mod = compile_code(source, name)
            self.func = self.mod['replace']
        else:
            self.func = func
            self.mod = None
        if not callable(self.func):
            raise ValueError('%r is not a function' % self.func)
        self.file_order = getattr(self.func, 'file_order', None)

    def init_env(self, name=''):
        from calibre.gui2.tweak_book.boss import get_boss
        self.context_name = name or ''
        self.match_index = 0
        self.boss = get_boss()
        self.data = {}
        self.debug_buf = StringIO()
        self.functions = {name:func.mod for name, func in functions().iteritems() if func.mod is not None}

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == getattr(other, 'name', None)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __call__(self, match):
        self.match_index += 1
        oo, oe, sys.stdout, sys.stderr = sys.stdout, sys.stderr, self.debug_buf, self.debug_buf
        try:
            return self.func(match, self.match_index, self.context_name, self.boss.current_metadata, dictionaries, self.data, self.functions)
        finally:
            sys.stdout, sys.stderr = oo, oe

    @property
    def source(self):
        if self.is_builtin:
            import json
            return json.loads(P('editor-functions.json', data=True, allow_user_override=False))[self.name]
        return self._source

    def end(self):
        if getattr(self.func, 'call_after_last_match', False):
            oo, oe, sys.stdout, sys.stderr = sys.stdout, sys.stderr, self.debug_buf, self.debug_buf
            try:
                return self.func(None, self.match_index, self.context_name, self.boss.current_metadata, dictionaries, self.data, self.functions)
            finally:
                sys.stdout, sys.stderr = oo, oe
        self.data, self.boss, self.functions = {}, None, {}


class DebugOutput(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, 'Debug output', 'sr-function-debug-output')
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.text = t = QPlainTextEdit(self)
        self.log_text = ''
        l.addWidget(t)
        l.addWidget(self.bb)
        self.bb.setStandardButtons(self.bb.Close)
        self.cb = b = self.bb.addButton(_('&Copy to clipboard'), self.bb.ActionRole)
        b.clicked.connect(self.copy_to_clipboard)
        b.setIcon(QIcon(I('edit-copy.png')))

    def show_log(self, name, text):
        self.setWindowTitle(_('Debug output from %s') % name)
        self.text.setPlainText(self.windowTitle() + '\n\n' + text)
        self.log_text = text
        self.show()
        self.raise_()

    def sizeHint(self):
        fm = QFontMetrics(self.text.font())
        return QSize(fm.averageCharWidth() * 120, 400)

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setText(self.log_text)


def builtin_functions():
    for name, obj in globals().iteritems():
        if name.startswith('replace_') and callable(obj) and hasattr(obj, 'imports'):
            yield obj


_functions = None


def functions(refresh=False):
    global _functions
    if _functions is None or refresh:
        ans = _functions = {}
        for func in builtin_functions():
            ans[func.name] = Function(func.name, func=func)
        for name, source in user_functions.iteritems():
            try:
                f = Function(name, source=source)
            except Exception:
                continue
            ans[f.name] = f
    return _functions


def remove_function(name, gui_parent=None):
    funcs = functions()
    if not name:
        return False
    if name not in funcs:
        error_dialog(gui_parent, _('No such function'), _(
            'There is no function named %s') % name, show=True)
        return False
    if name not in user_functions:
        error_dialog(gui_parent, _('Cannot remove builtin function'), _(
            'The function %s is a builtin function, it cannot be removed.') % name, show=True)
    del user_functions[name]
    functions(refresh=True)
    refresh_boxes()
    return True


boxes = []


def refresh_boxes():
    for ref in boxes:
        box = ref()
        if box is not None:
            box.refresh()


class FunctionBox(EditWithComplete):

    save_search = pyqtSignal()
    show_saved_searches = pyqtSignal()

    def __init__(self, parent=None, show_saved_search_actions=False):
        EditWithComplete.__init__(self, parent)
        self.set_separator(None)
        self.show_saved_search_actions = show_saved_search_actions
        self.refresh()
        self.setToolTip(_('Choose a function to run on matched text (by name)'))
        boxes.append(weakref.ref(self))

    def refresh(self):
        self.update_items_cache(set(functions()))

    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        if self.show_saved_search_actions:
            menu.addSeparator()
            menu.addAction(_('Save current search'), self.save_search.emit)
            menu.addAction(_('Show saved searches'), self.show_saved_searches.emit)
        menu.exec_(event.globalPos())


class FunctionEditor(Dialog):

    def __init__(self, func_name='', parent=None):
        self._func_name = func_name
        Dialog.__init__(self, _('Create/edit a function'), 'edit-sr-func', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)

        self.la1 = la = QLabel(_('F&unction name:'))
        h.addWidget(la)
        self.fb = fb = FunctionBox(self)
        la.setBuddy(fb)
        h.addWidget(fb, stretch=10)

        self.la3 = la = QLabel(_('&Code:'))
        self.source_code = TextEdit(self)
        self.source_code.load_text('', 'python')
        la.setBuddy(self.source_code)
        l.addWidget(la), l.addWidget(self.source_code)

        if self._func_name:
            self.fb.setText(self._func_name)
            func = functions().get(self._func_name)
            if func is not None:
                self.source_code.setPlainText(func.source or ('\n' + EMPTY_FUNC))
        else:
            self.source_code.setPlainText('\n' + EMPTY_FUNC)

        self.la2 = la = QLabel(_(
            'For help with creating functions, see the <a href="%s">User Manual</a>') %
            localize_user_manual_link('https://manual.calibre-ebook.com/function_mode.html'))
        la.setOpenExternalLinks(True)
        l.addWidget(la)

        l.addWidget(self.bb)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(fm.averageCharWidth() * 120, 600)

    @property
    def func_name(self):
        return self.fb.text().strip()

    @property
    def source(self):
        return self.source_code.toPlainText()

    def accept(self):
        if not self.func_name:
            return error_dialog(self, _('Must specify name'), _(
                'You must specify a name for this function.'), show=True)
        source = self.source
        try:
            mod = compile_code(source, self.func_name)
        except Exception as err:
            return error_dialog(self, _('Invalid Python code'), _(
                'The code you created is not valid Python code, with error: %s') % err, show=True)
        if not callable(mod.get('replace')):
            return error_dialog(self, _('No replace function'), _(
                'You must create a Python function named replace in your code'), show=True)
        user_functions[self.func_name] = source
        functions(refresh=True)
        refresh_boxes()

        Dialog.accept(self)

# Builtin functions ##########################################################


def builtin(name, *args):
    def f(func):
        func.name = name
        func.imports = args
        return func
    return f


EMPTY_FUNC = '''\
def replace(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    return ''
'''


@builtin('Upper-case text', upper, apply_func_to_match_groups)
def replace_uppercase(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Make matched text upper case. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, upper)


@builtin('Lower-case text', lower, apply_func_to_match_groups)
def replace_lowercase(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Make matched text lower case. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, lower)


@builtin('Capitalize text', capitalize, apply_func_to_match_groups)
def replace_capitalize(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Capitalize matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, capitalize)


@builtin('Title-case text', titlecase, apply_func_to_match_groups)
def replace_titlecase(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Title-case matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, titlecase)


@builtin('Swap the case of text', swapcase, apply_func_to_match_groups)
def replace_swapcase(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Swap the case of the matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, swapcase)


@builtin('Upper-case text (ignore tags)', upper, apply_func_to_html_text)
def replace_uppercase_ignore_tags(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Make matched text upper case, ignoring the text inside tag definitions.'''
    return apply_func_to_html_text(match, upper)


@builtin('Lower-case text (ignore tags)', lower, apply_func_to_html_text)
def replace_lowercase_ignore_tags(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Make matched text lower case, ignoring the text inside tag definitions.'''
    return apply_func_to_html_text(match, lower)


@builtin('Capitalize text (ignore tags)', capitalize, apply_func_to_html_text)
def replace_capitalize_ignore_tags(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Capitalize matched text, ignoring the text inside tag definitions.'''
    return apply_func_to_html_text(match, capitalize)


@builtin('Title-case text (ignore tags)', titlecase, apply_func_to_html_text)
def replace_titlecase_ignore_tags(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Title-case matched text, ignoring the text inside tag definitions.'''
    return apply_func_to_html_text(match, titlecase)


@builtin('Swap the case of text (ignore tags)', swapcase, apply_func_to_html_text)
def replace_swapcase_ignore_tags(match, number, file_name, metadata, dictionaries, data, functions, *args, **kwargs):
    '''Swap the case of the matched text, ignoring the text inside tag definitions.'''
    return apply_func_to_html_text(match, swapcase)


if __name__ == '__main__':
    app = QApplication([])
    FunctionEditor().exec_()
    del app
