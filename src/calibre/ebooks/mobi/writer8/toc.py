#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from lxml import etree

from calibre.ebooks.oeb.base import (urlnormalize, XPath, XHTML_NS, XHTML,
        XHTML_MIME)

DEFAULT_TITLE = __('Table of Contents')

TEMPLATE = '''
<html xmlns="{xhtmlns}">
<head>
  <title>{title}</title>
  <style type="text/css">
  li {{ list-style-type: none }}
  a {{ text-decoration: none }}
  a:hover {{ color: red }}
  {extra_css}
  {embed_css}
  </style>
</head>
<body id="calibre_generated_inline_toc">
<h2>{title}</h2>
<ul>
</ul>
</body>
</html>
'''

def find_previous_calibre_inline_toc(oeb):
    if 'toc' in oeb.guide:
        href = urlnormalize(oeb.guide['toc'].href.partition('#')[0])
        if href in oeb.manifest.hrefs:
            item = oeb.manifest.hrefs[href]
            if (hasattr(item.data, 'xpath') and XPath('//h:body[@id="calibre_generated_inline_toc"]')(item.data)):
                return item

class TOCAdder(object):

    def __init__(self, oeb, opts, replace_previous_inline_toc=False, ignore_existing_toc=False):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.title = opts.toc_title or DEFAULT_TITLE
        self.at_start = opts.mobi_toc_at_start
        self.generated_item = None
        self.added_toc_guide_entry = False
        self.has_toc = oeb.toc and oeb.toc.count() > 1

        self.tocitem = tocitem = None
        if find_previous_calibre_inline_toc:
            tocitem = self.tocitem = find_previous_calibre_inline_toc(oeb)
        if ignore_existing_toc and 'toc' in oeb.guide:
            oeb.guide.remove('toc')

        if 'toc' in oeb.guide:
            # Remove spurious toc entry from guide if it is not in spine or it
            # does not have any hyperlinks
            href = urlnormalize(oeb.guide['toc'].href.partition('#')[0])
            if href in oeb.manifest.hrefs:
                item = oeb.manifest.hrefs[href]
                if (hasattr(item.data, 'xpath') and
                    XPath('//h:a[@href]')(item.data)):
                    if oeb.spine.index(item) < 0:
                        oeb.spine.add(item, linear=False)
                    return
                elif self.has_toc:
                    oeb.guide.remove('toc')
            else:
                oeb.guide.remove('toc')

        if (not self.has_toc or 'toc' in oeb.guide or opts.no_inline_toc or
            getattr(opts, 'mobi_passthrough', False)):
            return

        self.log('\tGenerating in-line ToC')

        embed_css = ''
        s = getattr(oeb, 'store_embed_font_rules', None)
        if getattr(s, 'body_font_family', None):
            css = [x.cssText for x in s.rules] + [
                    'body { font-family: %s }'%s.body_font_family]
            embed_css = '\n\n'.join(css)

        root = etree.fromstring(TEMPLATE.format(xhtmlns=XHTML_NS,
            title=self.title, embed_css=embed_css,
            extra_css=(opts.extra_css or '')))
        parent = XPath('//h:ul')(root)[0]
        parent.text = '\n\t'
        for child in self.oeb.toc:
            self.process_toc_node(child, parent)

        if tocitem is not None:
            href = tocitem.href
            if oeb.spine.index(tocitem) > -1:
                oeb.spine.remove(tocitem)
            tocitem.data = root
        else:
            id, href = oeb.manifest.generate('contents', 'contents.xhtml')
            tocitem = self.generated_item = oeb.manifest.add(id, href, XHTML_MIME,
                    data=root)
        if self.at_start:
            oeb.spine.insert(0, tocitem, linear=True)
        else:
            oeb.spine.add(tocitem, linear=False)

        oeb.guide.add('toc', 'Table of Contents', href)

    def process_toc_node(self, toc, parent, level=0):
        li = parent.makeelement(XHTML('li'))
        li.tail = '\n'+ ('\t'*level)
        parent.append(li)
        href = toc.href
        if self.tocitem is not None and href:
            href = self.tocitem.relhref(toc.href)
        a = parent.makeelement(XHTML('a'), href=href or '#')
        a.text = toc.title
        li.append(a)
        if toc.count() > 0:
            parent = li.makeelement(XHTML('ul'))
            li.append(parent)
            a.tail = '\n' + ('\t'*level)
            parent.text = '\n'+('\t'*(level+1))
            parent.tail = '\n' + ('\t'*level)
            for child in toc:
                self.process_toc_node(child, parent, level+1)

    def remove_generated_toc(self):
        if self.generated_item is not None:
            self.oeb.manifest.remove(self.generated_item)
            self.generated_item = None
        if self.added_toc_guide_entry:
            self.oeb.guide.remove('toc')
            self.added_toc_guide_entry = False


