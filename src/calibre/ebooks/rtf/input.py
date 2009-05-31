from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin

class RTFInput(InputFormatPlugin):

    name        = 'RTF Input'
    author      = 'Kovid Goyal'
    description = 'Convert RTF files to HTML'
    file_types  = set(['rtf'])

    def generate_xml(self, stream):
        from calibre.ebooks.rtf2xml.ParseRtf import ParseRtf
        ofile = 'out.xml'
        parser = ParseRtf(
            in_file    = stream,
            out_file   = ofile,
            # Convert symbol fonts to unicode equivelents. Default
            # is 1
            convert_symbol = 1,

            # Convert Zapf fonts to unicode equivelents. Default
            # is 1.
            convert_zapf = 1,

            # Convert Wingding fonts to unicode equivelents.
            # Default is 1.
            convert_wingdings = 1,

            # Convert RTF caps to real caps.
            # Default is 1.
            convert_caps = 1,

            # Indent resulting XML.
            # Default is 0 (no indent).
            indent = 1,

            # Form lists from RTF. Default is 1.
            form_lists = 1,

            # Convert headings to sections. Default is 0.
            headings_to_sections = 1,

            # Group paragraphs with the same style name. Default is 1.
            group_styles = 1,

            # Group borders. Default is 1.
            group_borders = 1,

            # Write or do not write paragraphs. Default is 0.
            empty_paragraphs = 0,
        )
        parser.parse_rtf()
        ans = open('out.xml').read()
        os.remove('out.xml')
        return ans

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.rtf.xsl import xhtml
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.rtf2xml.ParseRtf import RtfInvalidCodeException
        self.log = log
        self.log('Converting RTF to XML...')
        try:
            xml = self.generate_xml(stream.name)
        except RtfInvalidCodeException:
            raise ValueError(_('This RTF file has a feature calibre does not '
            'support. Convert it to HTML first and then try it.'))
        self.log('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        doc = etree.fromstring(xml, parser=parser)
        self.log('Converting XML to HTML...')
        styledoc = etree.fromstring(xhtml)

        transform = etree.XSLT(styledoc)
        result = transform(doc)
        html = 'index.xhtml'
        with open(html, 'wb') as f:
            res = transform.tostring(result)
            res = res[:100].replace('xmlns:html', 'xmlns') + res[100:]
            f.write(res)
        stream.seek(0)
        mi = get_metadata(stream, 'rtf')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.xhtml', None)])
        opf.create_spine(['index.xhtml'])
        opf.render(open('metadata.opf', 'wb'))
        return os.path.abspath('metadata.opf')

