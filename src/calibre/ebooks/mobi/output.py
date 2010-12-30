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
        OptionRecommendation(name='personal_doc', recommended_value='[PDOC]',
            help=_('Tag marking book to be filed with Personal Docs')
        ),
        OptionRecommendation(name='mobi_ignore_margins',
            recommended_value=False,
            help=_('Ignore margins in the input document. If False, then '
                'the MOBI output plugin will try to convert margins specified'
                ' in the input document, otherwise it will ignore them.')
        ),
    ])

    def check_for_periodical(self):
        if self.is_periodical:
            self.periodicalize_toc()
            self.check_for_masthead()
            self.opts.mobi_periodical = True
        else:
            self.opts.mobi_periodical = False

    def check_for_masthead(self):
        found = 'masthead' in self.oeb.guide
        if not found:
            self.oeb.log.debug('No masthead found in manifest, generating default mastheadImage...')
            try:
                from PIL import Image as PILImage
                PILImage
            except ImportError:
                import Image as PILImage

            raw = open(P('content_server/calibre_banner.png'), 'rb')
            im = PILImage.open(raw)
            of = StringIO()
            im.save(of, 'GIF')
            raw = of.getvalue()
            id, href = self.oeb.manifest.generate('masthead', 'masthead')
            self.oeb.manifest.add(id, href, 'image/gif', data=raw)
            self.oeb.guide.add('masthead', 'Masthead Image', href)
        else:
            self.oeb.log.debug('Using mastheadImage supplied in manifest...')


    def dump_toc(self, toc) :
        self.log( "\n         >>> TOC contents <<<")
        self.log( "     toc.title: %s" % toc.title)
        self.log( "      toc.href: %s" % toc.href)
        for periodical in toc.nodes :
            self.log( "\tperiodical title: %s" % periodical.title)
            self.log( "\t            href: %s" % periodical.href)
            for section in periodical :
                self.log( "\t\tsection title: %s" % section.title)
                self.log( "\t\tfirst article: %s" % section.href)
                for article in section :
                    self.log( "\t\t\tarticle title: %s" % repr(article.title))
                    self.log( "\t\t\t         href: %s" % article.href)

    def dump_manifest(self) :
        self.log( "\n         >>> Manifest entries <<<")
        for href in self.oeb.manifest.hrefs :
            self.log ("\t%s" % href)

    def periodicalize_toc(self):
        from calibre.ebooks.oeb.base import TOC
        toc = self.oeb.toc
        if not toc or len(self.oeb.spine) < 3:
            return
        if toc and toc[0].klass != 'periodical':
            one, two = self.oeb.spine[0], self.oeb.spine[1]
            self.log('Converting TOC for MOBI periodical indexing...')

            articles = {}
            if toc.depth() < 3:
                # single section periodical
                self.oeb.manifest.remove(one)
                self.oeb.manifest.remove(two)
                sections = [TOC(klass='section', title=_('All articles'),
                    href=self.oeb.spine[0].href)]
                for x in toc:
                    sections[0].nodes.append(x)
            else:
                # multi-section periodical
                self.oeb.manifest.remove(one)
                sections = list(toc)
                for i,x in enumerate(sections):
                    x.klass = 'section'
                    articles_ = list(x)
                    if articles_:
                        self.oeb.manifest.remove(self.oeb.manifest.hrefs[x.href])
                        x.href = articles_[0].href


            for sec in sections:
                articles[id(sec)] = []
                for a in list(sec):
                    a.klass = 'article'
                    articles[id(sec)].append(a)
                    sec.nodes.remove(a)

            root = TOC(klass='periodical', href=self.oeb.spine[0].href,
                    title=unicode(self.oeb.metadata.title[0]))

            for s in sections:
                if articles[id(s)]:
                    for a in articles[id(s)]:
                        s.nodes.append(a)
                    root.nodes.append(s)

            for x in list(toc.nodes):
                toc.nodes.remove(x)

            toc.nodes.append(root)

            # Fix up the periodical href to point to first section href
            toc.nodes[0].href = toc.nodes[0].nodes[0].href

            # GR diagnostics
            if self.opts.verbose > 3:
                self.dump_toc(toc)
                self.dump_manifest()


    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb
        from calibre.ebooks.mobi.writer import PALM_MAX_IMAGE_SIZE, \
                MobiWriter, PALMDOC, UNCOMPRESSED
        from calibre.ebooks.mobi.mobiml import MobiMLizer
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        from calibre.customize.ui import plugin_for_input_format
        imagemax = PALM_MAX_IMAGE_SIZE if opts.rescale_images else None
        if not opts.no_inline_toc:
            tocadder = HTMLTOCAdder(title=opts.toc_title)
            tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        try:
            rasterizer = SVGRasterizer()
            rasterizer(oeb, opts)
        except Unavailable:
            self.log.warn('SVG rasterizer unavailable, SVG will not be converted')
        mobimlizer = MobiMLizer(ignore_tables=opts.linearize_tables)
        mobimlizer(oeb, opts)
        self.check_for_periodical()
        write_page_breaks_after_item = not input_plugin is plugin_for_input_format('cbz')
        writer = MobiWriter(opts, imagemax=imagemax,
                compression=UNCOMPRESSED if opts.dont_compress else PALMDOC,
                            prefer_author_sort=opts.prefer_author_sort,
                            write_page_breaks_after_item=write_page_breaks_after_item)
        writer(oeb, output_path)

