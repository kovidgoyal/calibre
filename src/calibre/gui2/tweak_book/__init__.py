#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import string
from future_builtins import map

from calibre.utils.config import JSONConfig
from calibre.spell.dictionary import Dictionaries, parse_lang_code

CONTAINER_DND_MIMETYPE = 'application/x-calibre-container-name-list'
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
d['spell_check_case_sensitive_sort'] = False
d['inline_spell_check'] = True
d['custom_themes'] = {}
d['remove_unused_classes'] = False
d['merge_identical_selectors'] = False
d['global_book_toolbar'] = [
'new-file', 'open-book',  'save-book', None, 'global-undo', 'global-redo', 'create-checkpoint', None, 'donate', 'user-manual']
d['global_tools_toolbar'] = [
    'check-book', 'spell-check-book', 'edit-toc', 'insert-character',
    'manage-fonts', 'smarten-punctuation', 'remove-unused-css', 'show-reports'
]
d['global_plugins_toolbar'] = []
d['editor_common_toolbar'] = [('editor-' + x) if x else None for x in ('undo', 'redo', None, 'cut', 'copy', 'paste', 'smart-comment')]
d['editor_css_toolbar'] = ['pretty-current', 'editor-sort-css', 'insert-image']
d['editor_xml_toolbar'] = ['pretty-current', 'insert-tag']
d['editor_html_toolbar'] = ['fix-html-current', 'pretty-current', 'insert-image', 'insert-hyperlink', 'insert-tag', 'change-paragraph']
d['editor_format_toolbar'] = [('format-text-' + x) if x else x for x in (
'bold', 'italic', 'underline', 'strikethrough', 'subscript', 'superscript',
    None, 'color', 'background-color', None, 'justify-left', 'justify-center',
    'justify-right', 'justify-fill')]
d['spell_check_case_sensitive_search'] = False
d['add_cover_preserve_aspect_ratio'] = False
d['templates'] = {}
d['auto_close_tags'] = True
d['restore_book_state'] = True
d['editor_accepts_drops'] = True
d['toolbar_icon_size'] = 24
d['insert_full_screen_image'] = False
d['preserve_aspect_ratio_when_inserting_image'] = False
d['file_list_shows_full_pathname'] = False
d['auto_link_stylesheets'] = True
d['check_external_link_anchors'] = True
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
toolbar_actions = NonReplaceDict()
editor_toolbar_actions = {
    'format':NonReplaceDict(), 'html':NonReplaceDict(), 'xml':NonReplaceDict(), 'css':NonReplaceDict()}

TOP = object()
dictionaries = Dictionaries()


def editor_name(editor):
    for n, ed in editors.iteritems():
        if ed is editor:
            return n


def set_book_locale(lang):
    dictionaries.initialize()
    try:
        dictionaries.default_locale = parse_lang_code(lang)
        if dictionaries.default_locale.langcode == 'und':
            raise ValueError('')
    except ValueError:
        dictionaries.default_locale = dictionaries.ui_locale
    from calibre.gui2.tweak_book.editor.syntax.html import refresh_spell_check_status
    refresh_spell_check_status()


def verify_link(url, name=None):
    if _current_container is None or name is None:
        return None
    try:
        target = _current_container.href_to_name(url, name)
    except ValueError:
        return False  # Absolute URLs that point to a different drive on windows cause this
    if _current_container.has_name(target):
        return True
    if url.startswith('#'):
        return True
    if url.partition(':')[0] in {'http', 'https', 'mailto'}:
        return True
    return False


def update_mark_text_action(ed=None):
    has_mark = False
    if ed is not None and ed.has_line_numbers:
        has_mark = bool(ed.selected_text) or not ed.has_marked_text
    ac = actions['mark-selected-text']
    ac.setText(ac.default_text if has_mark else _('&Unmark marked text'))
