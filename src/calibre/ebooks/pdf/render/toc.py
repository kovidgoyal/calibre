#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from lxml.html import tostring
from lxml.html.builder import (HTML, HEAD, BODY, TABLE, TR, TD, H1, STYLE)

def convert_node(toc, table, level, pdf):
    tr = TR(
        TD(toc.text or _('Unknown')), TD(),
    )
    tr.set('class', 'level-%d' % level)
    anchors = pdf.links.anchors

    path = toc.abspath or None
    frag = toc.fragment or None
    if path is None:
        return
    path = os.path.normcase(os.path.abspath(path))
    if path not in anchors:
        return None
    a = anchors[path]
    dest = a.get(frag, a[None])
    num = pdf.page_tree.obj.get_num(dest[0])
    tr[1].text = type('')(num)
    table.append(tr)


def process_children(toc, table, level, pdf):
    for child in toc:
        convert_node(child, table, level, pdf)
        process_children(child, table, level+1, pdf)

def toc_as_html(toc, pdf, opts):
    pdf = pdf.engine.pdf
    indents = []
    for i in xrange(1, 7):
        indents.extend((i, 1.4*i))
    html = HTML(
        HEAD(
            STYLE(
            '''
            .calibre-pdf-toc table { width: 100%% }

            .calibre-pdf-toc table tr td:last-of-type { text-align: right }

            .calibre-pdf-toc .level-0 {
                font-size: larger;
            }

            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            .calibre-pdf-toc .level-%d td:first-of-type { padding-left: %.1gem }
            ''' % tuple(indents) + (opts.extra_css or '')
            )
        ),
        BODY(
            H1(_('Table of Contents')),
            TABLE(),
        )
    )
    body = html[1]
    body.set('class', 'calibre-pdf-toc')

    process_children(toc, body[1], 0, pdf)

    return tostring(html, pretty_print=True, include_meta_content_type=True, encoding='utf-8')
