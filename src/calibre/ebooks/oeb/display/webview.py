#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre import guess_type
from polyglot.builtins import iteritems


class EntityDeclarationProcessor(object):  # {{{

    def __init__(self, html):
        self.declared_entities = {}
        for match in re.finditer(r'<!\s*ENTITY\s+([^>]+)>', html):
            tokens = match.group(1).split()
            if len(tokens) > 1:
                self.declared_entities[tokens[0].strip()] = tokens[1].strip().replace('"', '')
        self.processed_html = html
        for key, val in iteritems(self.declared_entities):
            self.processed_html = self.processed_html.replace('&%s;'%key, val)
# }}}


def self_closing_sub(match):
    tag = match.group(1)
    if tag.lower().strip() == 'br':
        return match.group()
    return '<%s%s></%s>'%(match.group(1), match.group(2), match.group(1))


def cleanup_html(html):
    html = EntityDeclarationProcessor(html).processed_html
    self_closing_pat = re.compile(r'<\s*([:A-Za-z0-9-]+)([^>]*)/\s*>')
    html = self_closing_pat.sub(self_closing_sub, html)
    return html


xml_detect_pat = re.compile(r'<!(?:\[CDATA\[|ENTITY)')


def load_as_html(html):
    return re.search(r'<[a-zA-Z0-9-]+:svg', html) is None and xml_detect_pat.search(html) is None


def load_html(path, view, codec='utf-8', mime_type=None,
              pre_load_callback=lambda x:None, path_is_html=False,
              force_as_html=False, loading_url=None):
    from PyQt5.Qt import QUrl, QByteArray
    if mime_type is None:
        mime_type = guess_type(path)[0]
        if not mime_type:
            mime_type = 'text/html'
    if path_is_html:
        html = path
    else:
        with open(path, 'rb') as f:
            html = f.read().decode(codec, 'replace')

    html = cleanup_html(html)
    loading_url = loading_url or QUrl.fromLocalFile(path)
    pre_load_callback(loading_url)

    if force_as_html or load_as_html(html):
        view.setHtml(html, loading_url)
    else:
        view.setContent(QByteArray(html.encode(codec)), mime_type,
                loading_url)
        mf = view.page().mainFrame()
        elem = mf.findFirstElement('parsererror')
        if not elem.isNull():
            return False
    return True
