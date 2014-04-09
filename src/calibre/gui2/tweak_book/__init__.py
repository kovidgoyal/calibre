#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import string
from future_builtins import map

from calibre.utils.config import JSONConfig
from calibre.spell.dictionary import Dictionaries, parse_lang_code

tprefs = JSONConfig('tweak_book_gui')
d = tprefs.defaults

d['editor_theme'] = None
d['editor_font_family'] = None
d['editor_font_size'] = 12
d['editor_line_wrap'] = True
d['editor_tab_stop_width'] = 2
d['editor_show_char_under_cursor'] = True
d['replace_entities_as_typed'] = True
d['preview_refresh_time'] = 2
d['choose_tweak_fmt'] = True
d['tweak_fmt_order'] = ['EPUB', 'AZW3']
d['update_metadata_from_calibre'] = True
d['nestable_dock_widgets'] = False
d['dock_top_left'] = 'horizontal'
d['dock_top_right'] = 'horizontal'
d['dock_bottom_left'] = 'horizontal'
d['dock_bottom_right'] = 'horizontal'
d['preview_serif_family'] = 'Liberation Serif'
d['preview_sans_family'] = 'Liberation Sans'
d['preview_mono_family'] = 'Liberation Mono'
d['preview_standard_font_family'] = 'serif'
d['preview_base_font_size'] = 18
d['preview_mono_font_size'] = 14
d['preview_minimum_font_size'] = 8
d['remove_existing_links_when_linking_sheets'] = True
d['charmap_favorites'] = list(map(ord, '\xa0\u2002\u2003\u2009\xad' '‘’“”‹›«»‚„' '—–§¶†‡©®™' '→⇒•·°±−×÷¼½½¾' '…µ¢£€¿¡¨´¸ˆ˜' 'ÀÁÂÃÄÅÆÇÈÉÊË' 'ÌÍÎÏÐÑÒÓÔÕÖØ' 'ŒŠÙÚÛÜÝŸÞßàá' 'âãäåæçèéêëìí' 'îïðñòóôõöøœš' 'ùúûüýÿþªºαΩ∞'))  # noqa
d['folders_for_types'] = {'style':'styles', 'image':'images', 'font':'fonts', 'audio':'audio', 'video':'video'}
d['pretty_print_on_open'] = False
d['disable_completion_popup_for_search'] = False
d['saved_searches'] = []
d['insert_tag_mru'] = ['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'em', 'strong', 'td', 'tr']

del d

ucase_map = {l:string.ascii_uppercase[i] for i, l in enumerate(string.ascii_lowercase)}
def capitalize(x):
    return ucase_map[x[0]] + x[1:]

_current_container = None

def current_container():
    return _current_container

def set_current_container(container):
    global _current_container
    _current_container = container

class NonReplaceDict(dict):

    def __setitem__(self, k, v):
        if k in self:
            raise ValueError('The key %s is already present' % k)
        dict.__setitem__(self, k, v)

actions = NonReplaceDict()
editors = NonReplaceDict()
TOP = object()
dictionaries = Dictionaries()

def set_book_locale(lang):
    try:
        dictionaries.default_locale = parse_lang_code(lang)
        if dictionaries.default_locale.langcode == 'und':
            raise ValueError('')
    except ValueError:
        dictionaries.default_locale = dictionaries.ui_locale
