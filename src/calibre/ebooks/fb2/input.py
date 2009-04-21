from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'
"""
Convert .fb2 files to .lrf
"""
import os
from base64 import b64decode
from lxml import etree

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre import guess_type

FB2NS = 'http://www.gribuser.ru/xml/fictionbook/2.0'

class FB2Input(InputFormatPlugin):

    name        = 'FB2 Input'
    author      = 'Anatoly Shipitsin'
    description = 'Convert FB2 files to HTML'
    file_types  = set(['fb2'])

    recommendations = set([
        ('level1_toc', '//h:h1', OptionRecommendation.MED),
        ('level2_toc', '//h:h2', OptionRecommendation.MED),
        ('level3_toc', '//h:h3', OptionRecommendation.MED),
        ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.resources import fb2_xsl
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.oeb.base import XLINK_NS
        NAMESPACES = {'f':FB2NS, 'l':XLINK_NS}

        log.debug('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        doc = etree.parse(stream, parser)
        self.extract_embedded_content(doc)
        log.debug('Converting XML to HTML...')
        styledoc = etree.fromstring(fb2_xsl)

        transform = etree.XSLT(styledoc)
        result = transform(doc)
        open('index.xhtml', 'wb').write(transform.tostring(result))
        stream.seek(0)
        mi = get_metadata(stream, 'fb2')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        opf = OPFCreator(os.getcwdu(), mi)
        entries = [(f, guess_type(f)[0]) for f in os.listdir('.')]
        opf.create_manifest(entries)
        opf.create_spine(['index.xhtml'])

        for img in doc.xpath('//f:coverpage/f:image', namespaces=NAMESPACES):
            href = img.get('{%s}href'%XLINK_NS, img.get('href', None))
            if href is not None:
                if href.startswith('#'):
                    href = href[1:]
                opf.guide.set_cover(os.path.abspath(href))

        opf.render(open('metadata.opf', 'wb'))
        return os.path.join(os.getcwd(), 'metadata.opf')

    def extract_embedded_content(self, doc):
        for elem in doc.xpath('./*'):
            if 'binary' in elem.tag and elem.attrib.has_key('id'):
                fname = elem.attrib['id']
                data = b64decode(elem.text.strip())
                open(fname, 'wb').write(data)

