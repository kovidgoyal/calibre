from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert an ODT file into a Open Ebook
'''
import os

from lxml import etree
from odf.odf2xhtml import ODF2XHTML

from calibre import CurrentDir, walk
from calibre.customize.conversion import InputFormatPlugin

class Extract(ODF2XHTML):

    def extract_pictures(self, zf):
        if not os.path.exists('Pictures'):
            os.makedirs('Pictures')
        for name in zf.namelist():
            if name.startswith('Pictures'):
                data = zf.read(name)
                with open(name, 'wb') as f:
                    f.write(data)

    def fix_markup(self, html, log):
        root = etree.fromstring(html)
        self.epubify_markup(root, log)
        self.filter_css(root, log)
        html = etree.tostring(root, encoding='utf-8',
                xml_declaration=True)
        return html

    def epubify_markup(self, root, log):
        # Fix <p><div> constructs as the asinine epubchecker complains
        # about them
        from calibre.ebooks.oeb.base import XPath, XHTML
        pdiv = XPath('//h:p/h:div')
        for div in pdiv(root):
            div.getparent().tag = XHTML('div')

        # Remove the position:relative as it causes problems with some epub
        # renderers. Remove display: block on an image inside a div as it is
        # redundant and prevents text-align:center from working in ADE
        imgpath = XPath('//h:div/h:img[@style]')
        for img in imgpath(root):
            div = img.getparent()
            if len(div) == 1:
                style = div.attrib['style'].replace('position:relative', '')
                if style.startswith(';'): style = style[1:]
                div.attrib['style'] = style
                if img.attrib.get('style', '') == 'display: block;':
                    del img.attrib['style']

        # A div/div/img construct causes text-align:center to not work in ADE
        # so set the display of the second div to inline. This should have no
        # effect (apart from minor vspace issues) in a compliant HTML renderer
        # but it fixes the centering of the image via a text-align:center on
        # the first div in ADE
        imgpath = XPath('descendant::h:div/h:div/h:img')
        for img in imgpath(root):
            div2 = img.getparent()
            div1 = div2.getparent()
            if len(div1) == len(div2) == 1:
                style = div2.attrib['style']
                div2.attrib['style'] = 'position:static;display:inline;'+style


    def filter_css(self, root, log):
        style = root.xpath('//*[local-name() = "style" and @type="text/css"]')
        if style:
            style = style[0]
            css = style.text
            if css:
                css, sel_map = self.do_filter_css(css)
                if not isinstance(css, unicode):
                    css = css.decode('utf-8', 'ignore')
                style.text = css
                for x in root.xpath('//*[@class]'):
                    extra = []
                    orig = x.get('class')
                    for cls in orig.split():
                        extra.extend(sel_map.get(cls, []))
                    if extra:
                        x.set('class', orig + ' ' + ' '.join(extra))

    def do_filter_css(self, css):
        from cssutils import parseString
        from cssutils.css import CSSRule
        sheet = parseString(css)
        rules = list(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
        sel_map = {}
        count = 0
        for r in rules:
            # Check if we have only class selectors for this rule
            nc = [x for x in r.selectorList if not
                    x.selectorText.startswith('.')]
            if len(r.selectorList) > 1 and not nc:
                # Replace all the class selectors with a single class selector
                # This will be added to the class attribute of all elements
                # that have one of these selectors.
                replace_name = 'c_odt%d'%count
                count += 1
                for sel in r.selectorList:
                    s = sel.selectorText[1:]
                    if s not in sel_map:
                        sel_map[s] = []
                    sel_map[s].append(replace_name)
                r.selectorText = '.'+replace_name
        return sheet.cssText, sel_map

    def __call__(self, stream, odir, log):
        from calibre.utils.zipfile import ZipFile
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator


        if not os.path.exists(odir):
            os.makedirs(odir)
        with CurrentDir(odir):
            log('Extracting ODT file...')
            html = self.odf2xhtml(stream)
            # A blanket img specification like this causes problems
            # with EPUB output as the containing element often has
            # an absolute height and width set that is larger than
            # the available screen real estate
            html = html.replace('img { width: 100%; height: 100%; }', '')
            try:
                html = self.fix_markup(html, log)
            except:
                log.exception('Failed to filter CSS, conversion may be slow')
            with open('index.xhtml', 'wb') as f:
                f.write(html.encode('utf-8'))
            zf = ZipFile(stream, 'r')
            self.extract_pictures(zf)
            stream.seek(0)
            mi = get_metadata(stream, 'odt')
            if not mi.title:
                mi.title = _('Unknown')
            if not mi.authors:
                mi.authors = [_('Unknown')]
            opf = OPFCreator(os.path.abspath(os.getcwdu()), mi)
            opf.create_manifest([(os.path.abspath(f), None) for f in walk(os.getcwd())])
            opf.create_spine([os.path.abspath('index.xhtml')])
            with open('metadata.opf', 'wb') as f:
                opf.render(f)
            return os.path.abspath('metadata.opf')


class ODTInput(InputFormatPlugin):

    name        = 'ODT Input'
    author      = 'Kovid Goyal'
    description = 'Convert ODT (OpenOffice) files to HTML'
    file_types  = set(['odt'])


    def convert(self, stream, options, file_ext, log,
                accelerators):
        return Extract()(stream, '.', log)


