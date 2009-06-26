#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


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
        OptionRecommendation(name='toc_title', recommended_value=None,
            help=_('Title for any generated in-line table of contents.')
        ),
        OptionRecommendation(name='mobi_periodical',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Generate a periodical rather than a book.')
        ),
        OptionRecommendation(name='dont_compress',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Disable compression of the file contents.')
        ),


    ])

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
        tocadder = HTMLTOCAdder(title=opts.toc_title)
        tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        rasterizer = SVGRasterizer()
        rasterizer(oeb, opts)
        mobimlizer = MobiMLizer(ignore_tables=opts.linearize_tables)
        mobimlizer(oeb, opts)
        write_page_breaks_after_item = not input_plugin is plugin_for_input_format('cbz')
        print 111111, write_page_breaks_after_item
        writer = MobiWriter(opts, imagemax=imagemax,
                compression=UNCOMPRESSED if opts.dont_compress else PALMDOC,
                            prefer_author_sort=opts.prefer_author_sort,
                            write_page_breaks_after_item=write_page_breaks_after_item)
        writer(oeb, output_path)

