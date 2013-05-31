from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'
"""
Convert .fb2 files to .lrf
"""
import os, re

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

    options = set([
    OptionRecommendation(name='no_inline_fb2_toc',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Do not insert a Table of Contents at the beginning of the book.'
                )
        ),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from lxml import etree
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.oeb.base import XLINK_NS, XHTML_NS, RECOVER_PARSER
        from calibre.ebooks.chardet import xml_to_unicode
        NAMESPACES = {'f':FB2NS, 'l':XLINK_NS}
        self.log = log
        log.debug('Parsing XML...')
        raw = stream.read().replace('\0', '')
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
            assume_utf8=True, resolve_entities=True)[0]
        try:
            doc = etree.fromstring(raw)
        except etree.XMLSyntaxError:
            try:
                doc = etree.fromstring(raw, parser=RECOVER_PARSER)
                if doc is None:
                    raise Exception('parse failed')
            except:
                doc = etree.fromstring(raw.replace('& ', '&amp;'),
                        parser=RECOVER_PARSER)
        if doc is None:
            raise ValueError('The FB2 file is not valid XML')
        stylesheets = doc.xpath('//*[local-name() = "stylesheet" and @type="text/css"]')
        css = ''
        for s in stylesheets:
            css += etree.tostring(s, encoding=unicode, method='text',
                    with_tail=False) + '\n\n'
        if css:
            import cssutils, logging
            parser = cssutils.CSSParser(fetcher=None,
                    log=logging.getLogger('calibre.css'))

            XHTML_CSS_NAMESPACE = '@namespace "%s";\n' % XHTML_NS
            text = XHTML_CSS_NAMESPACE + css
            log.debug('Parsing stylesheet...')
            stylesheet = parser.parseString(text)
            stylesheet.namespaces['h'] = XHTML_NS
            css = unicode(stylesheet.cssText).replace('h|style', 'h|span')
            css = re.sub(r'name\s*=\s*', 'class=', css)
        self.extract_embedded_content(doc)
        log.debug('Converting XML to HTML...')
        ss = open(P('templates/fb2.xsl'), 'rb').read()
        if options.no_inline_fb2_toc:
            log('Disabling generation of inline FB2 TOC')
            ss = re.compile(r'<!-- BUILD TOC -->.*<!-- END BUILD TOC -->',
                    re.DOTALL).sub('', ss)

        styledoc = etree.fromstring(ss)

        transform = etree.XSLT(styledoc)
        result = transform(doc)
        for img in result.xpath('//img[@src]'):
            src = img.get('src')
            img.set('src', self.binary_map.get(src, src))
        index = transform.tostring(result)
        open(u'index.xhtml', 'wb').write(index)
        open(u'inline-styles.css', 'wb').write(css)
        stream.seek(0)
        mi = get_metadata(stream, 'fb2')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        cpath = None
        if mi.cover_data and mi.cover_data[1]:
            with open(u'fb2_cover_calibre_mi.jpg', 'wb') as f:
                f.write(mi.cover_data[1])
            cpath = os.path.abspath(u'fb2_cover_calibre_mi.jpg')
        else:
            for img in doc.xpath('//f:coverpage/f:image', namespaces=NAMESPACES):
                href = img.get('{%s}href'%XLINK_NS, img.get('href', None))
                if href is not None:
                    if href.startswith('#'):
                        href = href[1:]
                    cpath = os.path.abspath(href)
                    break

        opf = OPFCreator(os.getcwdu(), mi)
        entries = [(f2, guess_type(f2)[0]) for f2 in os.listdir(u'.')]
        opf.create_manifest(entries)
        opf.create_spine([u'index.xhtml'])
        if cpath:
            opf.guide.set_cover(cpath)
        with open(u'metadata.opf', 'wb') as f:
            opf.render(f)
        return os.path.join(os.getcwdu(), u'metadata.opf')

    def extract_embedded_content(self, doc):
        from calibre.ebooks.fb2 import base64_decode
        self.binary_map = {}
        for elem in doc.xpath('./*'):
            if elem.text and 'binary' in elem.tag and 'id' in elem.attrib:
                ct = elem.get('content-type', '')
                fname = elem.attrib['id']
                ext = ct.rpartition('/')[-1].lower()
                if ext in ('png', 'jpeg', 'jpg'):
                    if fname.lower().rpartition('.')[-1] not in {'jpg', 'jpeg',
                            'png'}:
                        fname += '.' + ext
                    self.binary_map[elem.get('id')] = fname
                raw = elem.text.strip()
                try:
                    data = base64_decode(raw)
                except TypeError:
                    self.log.exception('Binary data with id=%s is corrupted, ignoring'%(
                        elem.get('id')))
                else:
                    with open(fname, 'wb') as f:
                        f.write(data)


