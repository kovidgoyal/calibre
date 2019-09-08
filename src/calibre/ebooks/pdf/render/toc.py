#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from lxml.html import tostring
from lxml.html.builder import (HTML, HEAD, BODY, TABLE, TR, TD, H2, STYLE)

from polyglot.builtins import range, unicode_type


def calculate_page_number(num, map_expression, evaljs):
    if map_expression:
        num = int(evaljs('(function(){{var n={}; return {};}})()'.format(
            num, map_expression)))
    return num


def convert_node(toc, table, level, pdf, pdf_page_number_map, evaljs):
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
    num = calculate_page_number(pdf.page_tree.obj.get_num(dest[0]), pdf_page_number_map, evaljs)
    tr[1].text = unicode_type(num)
    table.append(tr)


def process_children(toc, table, level, pdf, pdf_page_number_map, evaljs):
    for child in toc:
        convert_node(child, table, level, pdf, pdf_page_number_map, evaljs)
        process_children(child, table, level+1, pdf, pdf_page_number_map, evaljs)


def toc_as_html(toc, pdf, opts, evaljs):
    pdf = pdf.engine.pdf
    indents = []
    for i in range(1, 7):
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
            H2(opts.toc_title or _('Table of Contents')),
            TABLE(),
        )
    )
    body = html[1]
    body.set('class', 'calibre-pdf-toc')

    process_children(toc, body[1], 0, pdf, opts.pdf_page_number_map, evaljs)

    return tostring(html, pretty_print=True, include_meta_content_type=True, encoding='utf-8')
