#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Add/remove the markup needed for Kobo's custom EPUB renderer. It's
# mostly completely unnecessary junk added to the HTML because Kobo
# doesn't know how to render EPUB without needing such hacks. The list of
# changes:
#     * Add Kobo style tweaks
#     * Add body div wrappers (used to apply pagination styles)
#     * Add spans around sentences. Apparently Kobo cannot implement
#       highlighting and bookmarking without this, they should be using CFI for this, sigh.
#     * Cover marking in the OPF
#     * Markup cleanup (remove various things that trip up the Kobo renderer)

from calibre.ebooks.oeb.base import XHTML, XPath
from calibre.ebooks.oeb.parse_utils import merge_multiple_html_heads_and_bodies
from calibre.ebooks.oeb.polish.utils import extract, insert_self_closing

KOBO_STYLE_HACKS = 'kobostylehacks'
OUTER_DIV_ID = 'book-columns'
INNER_DIV_ID = 'book-inner'


def add_style(root, css='div#book-inner { margin-top: 0; margin-bottom: 0;}', cls=KOBO_STYLE_HACKS) -> bool:

    def add(parent):
        e = parent.makeelement(XHTML('style'), type='text/css')
        e.text = css
        e.set('class', cls)
        insert_self_closing(parent, e)

    if heads := XPath('./h:head')(root):
        add(heads[-1])
        return True
    if bodies := XPath('./h:body')(root):
        add(bodies[-1])
        return True
    return False


def remove_kobo_styles(root):
    for x in XPath(f'//h:style[@type="text/css" and @class="{KOBO_STYLE_HACKS}"]')(root):
        extract(x)


def wrap_body_contents(body):
    # To match official KEPUBs. Kobo wraps the body with two div tags,
    # div#book-columns > div#book-inner to provide a target for applying
    # pagination styles.
    for elem in XPath(f'//*[@id="{OUTER_DIV_ID}" or @id={INNER_DIV_ID}]')(body):
        elem.attrib.pop('id')
    outer = body.makeelement(XHTML('div'), id=OUTER_DIV_ID)
    inner = body.makeelement(XHTML('div'), id=INNER_DIV_ID)
    outer.append(inner)
    inner.text = body.text
    body.text = None
    for child in body:
        inner.append(child)
    del body[:]
    body.append(outer)


def unwrap_body_contents(body):
    children = []
    text = ''
    for inner in XPath(f'./h:div[@id="{OUTER_DIV_ID}"]/h:div[@id="{INNER_DIV_ID}"]')(body):
        children.extend(inner)
        if inner.text:
            text += inner.text
        extract(inner.getparent())
    body.extend(children)
    body.text = text


def add_kobo_markup_to_html(root):
    add_style(root)
    for body in XPath('./h:body')(root):
        wrap_body_contents(body)


def remove_kobo_markup_from_html(root):
    remove_kobo_styles(root)
    for body in XPath('./h:body')(root):
        unwrap_body_contents(body)


def kepubify_html(root):
    remove_kobo_markup_from_html(root)
    merge_multiple_html_heads_and_bodies(root)
    add_kobo_markup_to_html(root)
