#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.customize.conversion import OutputFormatPlugin


class LITOutput(OutputFormatPlugin):

    name = 'LIT Output'
    author = 'Marshall T. Vandegrift'
    file_type = 'lit'
    commit_name = 'lit_output'

    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        from calibre.ebooks.lit.writer import LitWriter
        from calibre.ebooks.oeb.transforms.split import Split
        split = Split(split_on_page_breaks=True, max_flow_size=0,
                remove_css_pagebreaks=False)
        split(self.oeb, self.opts)

        tocadder = HTMLTOCAdder()
        tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        rasterizer = SVGRasterizer()
        rasterizer(oeb, opts)
        lit = LitWriter(self.opts)
        lit(oeb, output_path)
