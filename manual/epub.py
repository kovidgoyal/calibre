#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from sphinx.builders.epub3 import Epub3Builder as EpubBuilder

from calibre.ebooks.oeb.base import OPF
from calibre.ebooks.oeb.polish.container import get_container, OEB_DOCS
from calibre.ebooks.oeb.polish.check.links import check_links, UnreferencedResource
from calibre.ebooks.oeb.polish.pretty import pretty_html_tree, pretty_opf
from calibre.utils.imghdr import identify
from polyglot.builtins import iteritems


class EPUBHelpBuilder(EpubBuilder):
    name = 'myepub'

    def build_epub(self, outdir=None, outname=None):
        if outdir:
            EpubBuilder.build_epub(self, outdir, outname)
        else:
            EpubBuilder.build_epub(self)
            outdir = self.outdir
            outname = self.config.epub_basename + '.epub'
        container = get_container(os.path.join(outdir, outname))
        self.fix_epub(container)
        container.commit()

    def fix_epub(self, container):
        ' Fix all the brokenness that sphinx\'s epub builder creates '
        for name, mt in iteritems(container.mime_map):
            if mt in OEB_DOCS:
                self.workaround_ade_quirks(container, name)
                pretty_html_tree(container, container.parsed(name))
                container.dirty(name)
        self.fix_opf(container)

    def workaround_ade_quirks(self, container, name):
        root = container.parsed(name)
        # ADE blows up floating images if their sizes are not specified
        for img in root.xpath('//*[local-name() = "img" and (@class = "float-right-img" or @class = "float-left-img")]'):
            if 'style' not in img.attrib:
                imgname = container.href_to_name(img.get('src'), name)
                fmt, width, height = identify(container.raw_data(imgname))
                if width == -1:
                    raise ValueError('Failed to read size of: %s' % imgname)
                img.set('style', 'width: %dpx; height: %dpx' % (width, height))

    def fix_opf(self, container):
        spine_names = {n for n, l in container.spine_names}
        spine = container.opf_xpath('//opf:spine')[0]
        rmap = {v:k for k, v in iteritems(container.manifest_id_map)}
        # Add unreferenced text files to the spine
        for name, mt in iteritems(container.mime_map):
            if mt in OEB_DOCS and name not in spine_names:
                spine_names.add(name)
                container.insert_into_xml(spine, spine.makeelement(OPF('itemref'), idref=rmap[name]))

        # Remove duplicate entries from spine
        seen = set()
        for item, name, linear in container.spine_iter:
            if name in seen:
                container.remove_from_xml(item)
            seen.add(name)

        # Remove the <guide> which is not needed in EPUB 3
        for guide in container.opf_xpath('//*[local-name()="guide"]'):
            guide.getparent().remove(guide)

        # Ensure that the cover-image property is set
        cover_id = rmap['_static/' + self.config.epub_cover[0]]
        for item in container.opf_xpath('//opf:item[@id="{}"]'.format(cover_id)):
            item.set('properties', 'cover-image')
        for item in container.opf_xpath('//opf:item[@href="epub-cover.xhtml"]'):
            item.set('properties', 'svg calibre:title-page')
        for item in container.opf_xpath('//opf:package'):
            prefix = item.get('prefix') or ''
            if prefix:
                prefix += ' '
            item.set('prefix', prefix + 'calibre: https://calibre-ebook.com')

        # Remove any <meta cover> tag as it is not needed in epub 3
        for meta in container.opf_xpath('//opf:meta[@name="cover"]'):
            meta.getparent().remove(meta)

        # Remove unreferenced files
        for error in check_links(container):
            if error.__class__ is UnreferencedResource:
                container.remove_item(error.name)

        # Pretty print the OPF
        pretty_opf(container.parsed(container.opf_name))
        container.dirty(container.opf_name)
