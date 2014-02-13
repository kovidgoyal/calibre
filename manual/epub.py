#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from sphinx.builders.epub import EpubBuilder

from calibre.ebooks.oeb.base import OPF, DC
from calibre.ebooks.oeb.polish.container import get_container, OEB_DOCS
from calibre.ebooks.oeb.polish.check.links import check_links, UnreferencedResource
from calibre.ebooks.oeb.polish.pretty import pretty_html_tree, pretty_opf
from calibre.utils.magick.draw import identify_data

class EPUBHelpBuilder(EpubBuilder):
    name = 'myepub'

    def build_epub(self, outdir, outname):
        EpubBuilder.build_epub(self, outdir, outname)
        container = get_container(os.path.join(outdir, outname))
        self.fix_epub(container)
        container.commit()

    def fix_epub(self, container):
        ' Fix all the brokenness that sphinx\'s epub builder creates '
        for name, mt in container.mime_map.iteritems():
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
                width, height, fmt = identify_data(container.raw_data(imgname))
                img.set('style', 'width: %dpx; height: %dpx' % (width, height))

    def fix_opf(self, container):
        spine_names = {n for n, l in container.spine_names}
        spine = container.opf_xpath('//opf:spine')[0]
        rmap = {v:k for k, v in container.manifest_id_map.iteritems()}
        # Add unreferenced text files to the spine
        for name, mt in container.mime_map.iteritems():
            if mt in OEB_DOCS and name not in spine_names:
                spine_names.add(name)
                container.insert_into_xml(spine, spine.makeelement(OPF('itemref'), idref=rmap[name]))

        # Remove duplicate entries from spine
        seen = set()
        for item, name, linear in container.spine_iter:
            if name in seen:
                container.remove_from_xml(item)
            seen.add(name)

        # Ensure that the meta cover tag is correct
        cover_id = rmap['_static/' + self.config.epub_cover[0]]
        for meta in container.opf_xpath('//opf:meta[@name="cover"]'):
            meta.set('content', cover_id)

        # Add description metadata
        metadata = container.opf_xpath('//opf:metadata')[0]
        container.insert_into_xml(metadata, metadata.makeelement(DC('description')))
        metadata[-1].text = 'Comprehensive documentation for calibre'

        # Remove search.html since it is useless in EPUB
        container.remove_item('search.html')

        # Remove unreferenced files
        for error in check_links(container):
            if error.__class__ is UnreferencedResource:
                container.remove_item(error.name)

        # Pretty print the OPF
        pretty_opf(container.parsed(container.opf_name))
        container.dirty(container.opf_name)

