#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json
from functools import partial

from lxml import html

from calibre import browser
from calibre.ebooks.oeb.polish.container import OEB_DOCS
from calibre.ebooks.oeb.polish.utils import guess_type


class URLMap:

    def __init__(self):
        self.cache = {}

    def __getitem__(self, key):
        try:
            return self.cache[key]
        except KeyError:
            try:
                self.cache[key] = ans = json.loads(P('editor-help/%s.json' % key, data=True))
            except OSError:
                raise KeyError('The mapping %s is not available' % key)
            return ans


_url_map = URLMap()


def help_url(item, item_type, doc_name, extra_data=None):
    url = None
    url_maps = ()
    item = item.lower()
    if item_type == 'css_property':
        url_maps = ('css',)
    else:
        mt = guess_type(doc_name)
        if mt in OEB_DOCS:
            url_maps = ('html', 'svg', 'mathml')
        elif mt == guess_type('a.svg'):
            url_maps = ('svg',)
        elif mt == guess_type('a.opf'):
            version = '3' if getattr(extra_data, 'startswith', lambda x: False)('3') else '2'
            url_maps = (('opf' + version),)
        elif mt == guess_type('a.svg'):
            url_maps = ('svg',)
        elif mt == guess_type('a.ncx'):
            url_maps = ('opf2',)

    for umap in url_maps:
        umap = _url_map[umap]
        if item in umap:
            url = umap[item]
            break
        item = item.partition(':')[-1]
        if item and item in umap:
            url = umap[item]
            break

    return url


def get_mdn_tag_index(category):
    url = 'https://developer.mozilla.org/docs/Web/%s/Element' % category
    if category == 'CSS':
        url = url.replace('Element', 'Reference')
    br = browser()
    raw = br.open(url).read()
    root = html.fromstring(raw)
    ans = {}
    if category == 'CSS':
        xpath = '//div[@class="index"]/descendant::a[contains(@href, "/Web/CSS/")]/@href'
    else:
        xpath = '//a[contains(@href, "/%s/Element/")]/@href' % category
    for href in root.xpath(xpath):
        href = href.replace('/en-US/', '/')
        ans[href.rpartition('/')[-1].lower()] = 'https://developer.mozilla.org' + href
    return ans


def get_opf2_tag_index():
    base = 'http://www.idpf.org/epub/20/spec/OPF_2.0.1_draft.htm#'
    ans = {}
    for i, tag in enumerate(('package', 'metadata', 'manifest', 'spine', 'tours', 'guide')):
        ans[tag] = base + 'Section2.%d' % (i + 1)
    for i, tag in enumerate((
            'title', 'creator', 'subject', 'description', 'publisher',
            'contributor', 'date', 'type', 'format', 'identifier', 'source',
            'language', 'relation', 'coverage', 'rights')):
        ans[tag] = base + 'Section2.2.%d' % (i + 1)
    ans['item'] = ans['manifest']
    ans['itemref'] = ans['spine']
    ans['reference'] = ans['guide']
    for tag in ('ncx', 'docTitle', 'docAuthor', 'navMap', 'navPoint', 'navLabel', 'text', 'content', 'pageList', 'pageTarget'):
        ans[tag.lower()] = base + 'Section2.4.1.2'
    return ans


def get_opf3_tag_index():
    base = 'http://www.idpf.org/epub/301/spec/epub-publications.html#'
    ans = {}
    for tag in (
            'package', 'metadata', 'identifier', 'title', 'language', 'meta',
            'link', 'manifest', 'item', 'spine', 'itemref', 'guide',
            'bindings', 'mediaType', 'collection'):
        ans[tag.lower()] = base + 'sec-%s-elem' % tag
    for tag in ('contributor', 'creator', 'date', 'source', 'type',):
        ans[tag.lower()] = base + 'sec-opf-dc' + tag
    return ans


def write_tag_help():
    base = 'editor-help/%s.json'
    dump = partial(json.dumps, indent=2, sort_keys=True)

    for category in ('HTML', 'SVG', 'MathML', 'CSS'):
        data = get_mdn_tag_index(category)
        with open(P(base % category.lower()), 'wb') as f:
            f.write(dump(data))

    with open(P(base % 'opf2'), 'wb') as f:
        f.write(dump(get_opf2_tag_index()))

    with open(P(base % 'opf3'), 'wb') as f:
        f.write(dump(get_opf3_tag_index()))


if __name__ == '__main__':
    write_tag_help()
