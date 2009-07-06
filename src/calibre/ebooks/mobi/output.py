#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from cStringIO import StringIO

from calibre.customize.conversion import OutputFormatPlugin
from calibre.customize.conversion import OptionRecommendation

class MOBIOutput(OutputFormatPlugin):

    name = 'MOBI Output'
    author = 'Marshall T. Vandegrift'
    file_type = 'mobi'

    options = set([
        OptionRecommendation(name='rescale_images', recommended_value=False,
            help=_('Modify images to meet Palm device size limitations.')
        ),
        OptionRecommendation(name='prefer_author_sort',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('When present, use author sort field as author.')
        ),
        OptionRecommendation(name='no_inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Don\'t add Table of Contents to end of book. Useful if '
                'the book has its own table of contents.')),
        OptionRecommendation(name='toc_title', recommended_value=None,
            help=_('Title for any generated in-line table of contents.')
        ),
        OptionRecommendation(name='dont_compress',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Disable compression of the file contents.')
        ),
    ])

    def check_for_periodical(self):
        if self.oeb.metadata.publication_type and \
            self.oeb.metadata.publication_type[0].startswith('periodical:'):
                self.periodicalize_toc()
                self.check_for_masthead()
                self.opts.mobi_periodical = True
        else:
            self.opts.mobi_periodical = False

    def check_for_masthead(self):
        found = False
        for typ in self.oeb.guide:
            if type == 'masthead':
                found = True
                break
        if not found:
            self.oeb.debug('No masthead found, generating default one...')
            from calibre.resources import server_resources
            try:
                from PIL import Image as PILImage
                PILImage
            except ImportError:
                import Image as PILImage

            raw = StringIO(server_resources['calibre.png'])
            im = PILImage.open(raw)
            of = StringIO()
            im.save(of, 'GIF')
            raw = of.getvalue()
            id, href = self.oeb.manifest.generate('masthead', 'masthead')
            self.oeb.manifest.add(id, href, 'image/gif', data=raw)
            self.oeb.guide.add('masthead', 'Masthead Image', href)


    def periodicalize_toc(self):
        from calibre.ebooks.oeb.base import TOC
        toc = self.oeb.toc
        if toc and toc[0].klass != 'periodical':
            self.log('Converting TOC for MOBI periodical indexing...')
            articles = {}
            if toc.depth < 3:
                sections = [TOC(klass='section')]
                for x in toc:
                    sections[0].append(x)
            else:
                sections = list(toc)
            for sec in sections:
                articles[id(sec)] = []
                for a in list(sec):
                    articles[id(sec)].append(a)
                    sec.nodes.remove(a)
            root = TOC(klass='periodical', title=self.oeb.metadata.title[0])
            for s in sections:
                if articles[id(s)]:
                    for a in articles[id(s)]:
                        s.nodes.append(a)
            root.nodes.append(s)

            for x in list(toc.nodes):
                toc.nodes.remove(x)

            toc.nodes.append(root)


    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb
        from calibre.ebooks.mobi.writer import PALM_MAX_IMAGE_SIZE, \
                MobiWriter, PALMDOC, UNCOMPRESSED
        from calibre.ebooks.mobi.mobiml import MobiMLizer
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        from calibre.customize.ui import plugin_for_input_format
        imagemax = PALM_MAX_IMAGE_SIZE if opts.rescale_images else None
        if not opts.no_inline_toc:
            tocadder = HTMLTOCAdder(title=opts.toc_title)
            tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        rasterizer = SVGRasterizer()
        rasterizer(oeb, opts)
        mobimlizer = MobiMLizer(ignore_tables=opts.linearize_tables)
        mobimlizer(oeb, opts)
        self.check_for_periodical()
        write_page_breaks_after_item = not input_plugin is plugin_for_input_format('cbz')
        writer = MobiWriter(opts, imagemax=imagemax,
                compression=UNCOMPRESSED if opts.dont_compress else PALMDOC,
                            prefer_author_sort=opts.prefer_author_sort,
                            write_page_breaks_after_item=write_page_breaks_after_item)
        writer(oeb, output_path)

