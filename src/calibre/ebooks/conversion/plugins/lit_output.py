#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from calibre.customize.conversion import OutputFormatPlugin


class LITOutput(OutputFormatPlugin):
    name = 'LIT Output'
    author = 'Marshall T. Vandegrift'
    file_type = 'lit'
    commit_name = 'lit_output'

    def convert(self, oeb_book, output, input_plugin, opts, log):
        oeb = oeb_book
        output_path = output
        self.log, self.opts, self.oeb = log, opts, oeb
        from calibre.ebooks.lit.writer import LitWriter
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        from calibre.ebooks.oeb.transforms.split import Split

        split = Split(split_on_page_breaks=True, max_flow_size=0, remove_css_pagebreaks=False)
        split(self.oeb, self.opts)

        tocadder = HTMLTOCAdder()
        tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        rasterizer = SVGRasterizer()
        rasterizer(oeb, opts)
        lit = LitWriter(self.opts)
        lit(oeb, output_path)
