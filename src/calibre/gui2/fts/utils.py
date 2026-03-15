#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import re

from qt.core import Qt

from calibre import prepare_string_for_xml
from calibre.gui2 import safe_open_url
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets2 import HTMLDisplay


def get_db():
    if hasattr(get_db, 'db'):
        return get_db.db.new_api
    return get_gui().current_db.new_api


def markup_text(text: str) -> str:
    closing = False

    def sub(m):
        nonlocal closing
        closing = not closing
        return '<b><i>' if closing else '</i></b>'

    return re.sub(r'\x1d', sub, prepare_string_for_xml(text))


def jump_shortcut(new_val: str = '') -> str:
    if new_val:
        setattr(jump_shortcut, 'ans', new_val)
    return getattr(jump_shortcut, 'ans', '')


fts_url = 'https://www.sqlite.org/fts5.html#full_text_query_syntax'


def help_html() -> str:
    return '''
<style>
.wrapper { margin-left: 4px }
div { margin-top: 0.5ex }
.h { font-weight: bold; }
.bq { margin-left: 1em; margin-top: 0.5ex; margin-bottom: 0.5ex; font-style: italic }
p { margin: 0; }
</style><div class="wrapper">
                   ''' + _('''
<div class="h">Search for single words</div>
<p>Simply type the word:</p>
<div class="bq">awesome<br>calibre</div>

<div class="h">Search for phrases</div>
<p>Enclose the phrase in quotes:</p>
<div class="bq">"early run"<br>"song of love"</div>

<div class="h">Boolean searches</div>
<div class="bq">(calibre AND ebook) NOT gun<br>simple NOT ("high bar" OR hard)</div>

<div class="h">Phrases near each other</div>
<div class="bq">NEAR("people" "in Asia" "try")<br>NEAR("Kovid" "calibre", 30)</div>
<p>Here, 30 is the most words allowed between near groups. Defaults to 10 when unspecified.</p>

<div style="margin-top: 1em"><a href="{fts_url}">Complete syntax reference</a></div>\
''' + '</div>').format(fts_url=fts_url)


def help_panel(parent=None) -> HTMLDisplay:
    hp = HTMLDisplay(parent)
    hp.setDefaultStyleSheet('a { text-decoration: none; }')
    hp.setHtml(help_html())
    hp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    hp.document().setDocumentMargin(0)
    hp.anchor_clicked.connect(safe_open_url)
    return hp
