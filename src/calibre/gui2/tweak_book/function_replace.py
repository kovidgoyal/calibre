#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, io

from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.tweak_book import dictionaries
from calibre.utils.config import JSONConfig

user_functions = JSONConfig('editor-search-replace-functions')

def compile_code(src):
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    # Python complains if there is a coding declaration in a unicode string
    src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src, flags=re.MULTILINE)
    # Translate newlines to \n
    src = io.StringIO(src, newline=None).getvalue()

    namespace = {}
    exec src in namespace
    return namespace

class Function(object):

    def __init__(self, name, source=None, func=None):
        self._source = source
        self.is_builtin = source is None
        self.name = name
        if func is None:
            self.mod = compile_code(source)
            self.func = self.mod['replace']
        else:
            self.func = func
            self.mod = None
        if not callable(self.func):
            raise ValueError('%r is not a function' % self.func)

    def init_env(self, name=''):
        from calibre.gui2.tweak_book.boss import get_boss
        self.context_name = name or ''
        self.match_index = 0
        self.boss = get_boss()

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == getattr(other, 'name', None)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __call__(self, match):
        self.match_index += 1
        return self.func(match, self.match_index, self.context_name, self.boss.current_metadata, dictionaries, functions())

    @property
    def source(self):
        if self.is_builtin:
            import json
            return json.loads(P('editor-functions.json', data=True, allow_user_override=False))[self.name]
        return self._source

def builtin_functions():
    for name, obj in globals().iteritems():
        if name.startswith('replace_') and callable(obj):
            yield obj

_functions = None
def functions(refresh=False):
    global _functions
    if _functions is None or refresh:
        ans = _functions = {}
        for func in builtin_functions():
            ans[func.name] = Function(func.name, func=func)
        if refresh:
            user_functions.refresh()
        for name, source in user_functions.iteritems():
            try:
                f = Function(name, source=source)
            except Exception:
                continue
            ans[f.name] = f
    return _functions

class FunctionBox(EditWithComplete):

    def __init__(self, parent=None):
        EditWithComplete.__init__(self, parent)
        self.set_separator(None)
        self.refresh()

    def refresh(self):
        self.update_items_cache(set(functions()))

# Builtin functions ##########################################################

from calibre.ebooks.oeb.polish.utils import apply_func_to_match_groups

def replace_uppercase(match, number, file_name, metadata, dictionaries, functions, *args, **kwargs):
    '''Make matched text upper case. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, icu_upper)
replace_uppercase.name = 'Upper-case text'

def replace_lowercase(match, number, file_name, metadata, dictionaries, functions, *args, **kwargs):
    '''Make matched text lower case. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    return apply_func_to_match_groups(match, icu_lower)
replace_lowercase.name = 'Lower-case text'

def replace_capitalize(match, number, file_name, metadata, dictionaries, functions, *args, **kwargs):
    '''Capitalize matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    from calibre.utils.icu import capitalize
    return apply_func_to_match_groups(match, capitalize)
replace_capitalize.name = 'Capitalize text'

def replace_titlecase(match, number, file_name, metadata, dictionaries, functions, *args, **kwargs):
    '''Title-case matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    from calibre.utils.titlecase import titlecase
    return apply_func_to_match_groups(match, titlecase)
replace_titlecase.name = 'Title-case text'

def replace_swapcase(match, number, file_name, metadata, dictionaries, functions, *args, **kwargs):
    '''Swap the case of the matched text. If the regular expression contains groups,
    only the text in the groups will be changed, otherwise the entire text is
    changed.'''
    from calibre.utils.icu import swapcase
    return apply_func_to_match_groups(match, swapcase)
replace_swapcase.name = 'Swap the case of text'
