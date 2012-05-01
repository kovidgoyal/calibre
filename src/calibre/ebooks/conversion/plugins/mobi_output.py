#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.conversion import (OutputFormatPlugin,
        OptionRecommendation)

def remove_html_cover(oeb, log):
    from calibre.ebooks.oeb.base import OEB_DOCS

    if not oeb.metadata.cover \
        or 'cover' not in oeb.guide:
        return
    href = oeb.guide['cover'].href
    del oeb.guide['cover']
    item = oeb.manifest.hrefs[href]
    if item.spine_position is not None:
        log.warn('Found an HTML cover: ', item.href, 'removing it.',
                'If you find some content missing from the output MOBI, it '
                'is because you misidentified the HTML cover in the input '
                'document')
        oeb.spine.remove(item)
        if item.media_type in OEB_DOCS:
            oeb.manifest.remove(item)

def extract_mobi(output_path, opts):
    if opts.extract_to is not None:
        from calibre.ebooks.mobi.debug.main import inspect_mobi
        ddir = opts.extract_to
        inspect_mobi(output_path, ddir=ddir)

class MOBIOutput(OutputFormatPlugin):

    name = 'MOBI Output'
    author = 'Kovid Goyal'
    file_type = 'mobi'

    options = set([
        OptionRecommendation(name='prefer_author_sort',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('When present, use author sort field as author.')
        ),
        OptionRecommendation(name='no_inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Don\'t add Table of Contents to the book. Useful if '
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
        OptionRecommendation(name='mobi_toc_at_start',
            recommended_value=False,
            help=_('When adding the Table of Contents to the book, add it at the start of the '
                'book instead of the end. Not recommended.')
        ),
        OptionRecommendation(name='extract_to', recommended_value=None,
            help=_('Extract the contents of the MOBI file to the'
                ' specified directory. If the directory already '
                'exists, it will be deleted.')
        ),
        OptionRecommendation(name='share_not_sync', recommended_value=False,
            help=_('Enable sharing of book content via Facebook etc. '
                ' on the Kindle. WARNING: Using this feature means that '
                ' the book will not auto sync its last read position '
                ' on multiple devices. Complain to Amazon.')
        ),
        OptionRecommendation(name='mobi_keep_original_images',
            recommended_value=False,
            help=_('By default calibre converts all images to JPEG format '
                'in the output MOBI file. This is for maximum compatibility '
                'as some older MOBI viewers have problems with other image '
                'formats. This option tells calibre not to do this. '
                'Useful if your document contains lots of GIF/PNG images that '
                'become very large when converted to JPEG.')),
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
            from calibre.ebooks import generate_masthead
            self.oeb.log.debug('No masthead found in manifest, generating default mastheadImage...')
            raw = generate_masthead(unicode(self.oeb.metadata['title'][0]))
            id, href = self.oeb.manifest.generate('masthead', 'masthead')
            self.oeb.manifest.add(id, href, 'image/gif', data=raw)
            self.oeb.guide.add('masthead', 'Masthead Image', href)
        else:
            self.oeb.log.debug('Using mastheadImage supplied in manifest...')

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

    def convert(self, oeb, output_path, input_plugin, opts, log):
        from calibre.utils.config import tweaks
        from calibre.ebooks.mobi.writer2.resources import Resources
        self.log, self.opts, self.oeb = log, opts, oeb

        mobi_type = tweaks.get('test_mobi_output_type', 'old')
        if self.is_periodical:
            mobi_type = 'old' # Amazon does not support KF8 periodicals
        create_kf8 = mobi_type in ('new', 'both')

        remove_html_cover(self.oeb, self.log)
        resources = Resources(oeb, opts, self.is_periodical,
                add_fonts=create_kf8)
        self.check_for_periodical()

        if create_kf8:
            # Split on pagebreaks so that the resulting KF8 works better with
            # calibre's viewer, which does not support CSS page breaks
            from calibre.ebooks.oeb.transforms.split import Split
            Split()(self.oeb, self.opts)


        kf8 = self.create_kf8(resources, for_joint=mobi_type=='both'
                ) if create_kf8 else None
        if mobi_type == 'new':
            kf8.write(output_path)
            extract_mobi(output_path, opts)
            return

        self.log('Creating MOBI 6 output')
        self.write_mobi(input_plugin, output_path, kf8, resources)

    def create_kf8(self, resources, for_joint=False):
        from calibre.ebooks.mobi.writer8.main import create_kf8_book
        return create_kf8_book(self.oeb, self.opts, resources,
                for_joint=for_joint)

    def write_mobi(self, input_plugin, output_path, kf8, resources):
        from calibre.ebooks.mobi.mobiml import MobiMLizer
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        from calibre.customize.ui import plugin_for_input_format

        opts, oeb = self.opts, self.oeb
        if not opts.no_inline_toc:
            tocadder = HTMLTOCAdder(title=opts.toc_title, position='start' if
                    opts.mobi_toc_at_start else 'end')
            tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        try:
            rasterizer = SVGRasterizer()
            rasterizer(oeb, opts)
        except Unavailable:
            self.log.warn('SVG rasterizer unavailable, SVG will not be converted')
        else:
            # Add rasterized SVG images
            resources.add_extra_images()
        mobimlizer = MobiMLizer(ignore_tables=opts.linearize_tables)
        mobimlizer(oeb, opts)
        write_page_breaks_after_item = input_plugin is not plugin_for_input_format('cbz')
        from calibre.ebooks.mobi.writer2.main import MobiWriter
        writer = MobiWriter(opts, resources, kf8,
                        write_page_breaks_after_item=write_page_breaks_after_item)
        writer(oeb, output_path)
        extract_mobi(output_path, opts)

class AZW3Output(OutputFormatPlugin):

    name = 'AZW3 Output'
    author = 'Kovid Goyal'
    file_type = 'azw3'

    options = set([
        OptionRecommendation(name='prefer_author_sort',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('When present, use author sort field as author.')
        ),
        OptionRecommendation(name='no_inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Don\'t add Table of Contents to the book. Useful if '
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
        OptionRecommendation(name='mobi_toc_at_start',
            recommended_value=False,
            help=_('When adding the Table of Contents to the book, add it at the start of the '
                'book instead of the end. Not recommended.')
        ),
        OptionRecommendation(name='extract_to', recommended_value=None,
            help=_('Extract the contents of the MOBI file to the'
                ' specified directory. If the directory already '
                'exists, it will be deleted.')
        ),
        OptionRecommendation(name='share_not_sync', recommended_value=False,
            help=_('Enable sharing of book content via Facebook etc. '
                ' on the Kindle. WARNING: Using this feature means that '
                ' the book will not auto sync its last read position '
                ' on multiple devices. Complain to Amazon.')
        ),
    ])

    def convert(self, oeb, output_path, input_plugin, opts, log):
        from calibre.ebooks.mobi.writer2.resources import Resources
        from calibre.ebooks.mobi.writer8.main import create_kf8_book

        self.oeb, self.opts, self.log = oeb, opts, log
        opts.mobi_periodical = self.is_periodical

        resources = Resources(self.oeb, self.opts, self.is_periodical,
                add_fonts=True, process_images=False)
        remove_html_cover(self.oeb, self.log)

        # Split on pagebreaks so that the resulting KF8 works better with
        # calibre's viewer, which does not support CSS page breaks
        from calibre.ebooks.oeb.transforms.split import Split
        Split()(self.oeb, self.opts)

        kf8 = create_kf8_book(self.oeb, self.opts, resources, for_joint=False)

        kf8.write(output_path)
        extract_mobi(output_path, opts)


