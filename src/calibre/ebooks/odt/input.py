from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert an ODT file into a Open Ebook
'''
import os, logging

from lxml import etree
from cssutils import CSSParser
from cssutils.css import CSSRule

from odf.odf2xhtml import ODF2XHTML
from odf.opendocument import load as odLoad
from odf.draw import Frame as odFrame, Image as odImage
from odf.namespaces import TEXTNS as odTEXTNS

from calibre import CurrentDir, walk
from calibre.ebooks.oeb.base import _css_logger

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
        self.filter_css(root, log)
        self.extract_css(root, log)
        self.epubify_markup(root, log)
        html = etree.tostring(root, encoding='utf-8',
                xml_declaration=True)
        return html

    def extract_css(self, root, log):
        ans = []
        for s in root.xpath('//*[local-name() = "style" and @type="text/css"]'):
            ans.append(s.text)
            s.getparent().remove(s)

        head = root.xpath('//*[local-name() = "head"]')
        if head:
            head = head[0]
            ns = head.nsmap.get(None, '')
            if ns:
                ns = '{%s}'%ns
            etree.SubElement(head, ns+'link', {'type':'text/css',
                'rel':'stylesheet', 'href':'odfpy.css'})

        css = u'\n\n'.join(ans)
        parser = CSSParser(loglevel=logging.WARNING,
                            log=_css_logger)
        self.css = parser.parseString(css, validate=False)

        with open('odfpy.css', 'wb') as f:
            f.write(css.encode('utf-8'))

    def get_css_for_class(self, cls):
        if not cls: return None
        for rule in self.css.cssRules.rulesOfType(CSSRule.STYLE_RULE):
            for sel in rule.selectorList:
                q = sel.selectorText
                if q == '.' + cls:
                    return rule

    def epubify_markup(self, root, log):
        from calibre.ebooks.oeb.base import XPath, XHTML
        # Fix empty title tags
        for t in XPath('//h:title')(root):
            if not t.text:
                t.text = u' '
        # Fix <p><div> constructs as the asinine epubchecker complains
        # about them
        pdiv = XPath('//h:p/h:div')
        for div in pdiv(root):
            div.getparent().tag = XHTML('div')

        # Remove the position:relative as it causes problems with some epub
        # renderers. Remove display: block on an image inside a div as it is
        # redundant and prevents text-align:center from working in ADE
        # Also ensure that the img is contained in its containing div
        imgpath = XPath('//h:div/h:img[@style]')
        for img in imgpath(root):
            div = img.getparent()
            if len(div) == 1:
                style = div.attrib.get('style', '')
                if style and not style.endswith(';'):
                    style = style + ';'
                style += 'position:static' # Ensures position of containing
                                           # div is static
                # Ensure that the img is always contained in its frame
                div.attrib['style'] = style
                img.attrib['style'] = 'max-width: 100%; max-height: 100%'

        # Handle anchored images. The default markup + CSS produced by
        # odf2xhtml works with WebKit but not with ADE. So we convert the
        # common cases of left/right/center aligned block images to work on
        # both webkit and ADE. We detect the case of setting the side margins
        # to auto and map it to an appropriate text-align directive, which
        # works in both WebKit and ADE.
        # https://bugs.launchpad.net/bugs/1063207
        # https://bugs.launchpad.net/calibre/+bug/859343
        imgpath = XPath('descendant::h:div/h:div/h:img')
        for img in imgpath(root):
            div2 = img.getparent()
            div1 = div2.getparent()
            if (len(div1), len(div2)) != (1, 1): continue
            cls = div1.get('class', '')
            first_rules = filter(None, [self.get_css_for_class(x) for x in
                cls.split()])
            has_align = False
            for r in first_rules:
                if r.style.getProperty(u'text-align') is not None:
                    has_align = True
            ml = mr = None
            if not has_align:
                aval = None
                cls = div2.get(u'class', u'')
                rules = filter(None, [self.get_css_for_class(x) for x in
                    cls.split()])
                for r in rules:
                    ml = r.style.getPropertyCSSValue(u'margin-left') or ml
                    mr = r.style.getPropertyCSSValue(u'margin-right') or mr
                    ml = getattr(ml, 'value', None)
                    mr = getattr(mr, 'value', None)
                if ml == mr == u'auto':
                    aval = u'center'
                elif ml == u'auto' and mr != u'auto':
                    aval = 'right'
                elif ml != u'auto' and mr == u'auto':
                    aval = 'left'
                if aval is not None:
                    style = div1.attrib.get('style', '').strip()
                    if style and not style.endswith(';'):
                        style = style + ';'
                    style += 'text-align:%s'%aval
                    has_align = True
                    div1.attrib['style'] = style

            if has_align:
                # This is needed for ADE, without it the text-align has no
                # effect
                style = div2.attrib['style']
                div2.attrib['style'] = 'display:inline;'+style


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
        sheet = parseString(css, validate=False)
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

    def search_page_img(self, mi, log):
        for frm in self.document.topnode.getElementsByType(odFrame):
            try:
                if frm.getAttrNS(odTEXTNS,u'anchor-type') == 'page':
                    log.warn('Document has Pictures anchored to Page, will all end up before first page!')
                    break
            except ValueError:
                pass

    def filter_cover(self, mi, log):
        # filter the Element tree (remove the detected cover)
        if mi.cover and mi.odf_cover_frame:
            for frm in self.document.topnode.getElementsByType(odFrame):
                # search the right frame
                if frm.getAttribute('name') == mi.odf_cover_frame:
                    img = frm.getElementsByType(odImage)
                    # only one draw:image allowed in the draw:frame
                    if len(img) == 1 and img[0].getAttribute('href') == mi.cover:
                        # ok, this is the right frame with the right image
                        # check if there are more childs
                        if len(frm.childNodes) != 1:
                            break
                        # check if the parent paragraph more childs
                        para = frm.parentNode
                        if para.tagName != 'text:p' or len(para.childNodes) != 1:
                            break
                        # now it should be safe to remove the text:p
                        parent = para.parentNode
                        parent.removeChild(para)
                        log("Removed cover image paragraph from document...")
                        break

    def filter_load(self, odffile, mi, log):
        """ This is an adaption from ODF2XHTML. It adds a step between
            load and parse of the document where the Element tree can be
            modified.
        """
        # first load the odf structure
        self.lines = []
        self._wfunc = self._wlines
        if isinstance(odffile, basestring) \
                or hasattr(odffile, 'read'): # Added by Kovid
            self.document = odLoad(odffile)
        else:
            self.document = odffile
        # filter stuff
        self.search_page_img(mi, log)
        try:
            self.filter_cover(mi, log)
        except:
            pass
        # parse the modified tree and generate xhtml
        self._walknode(self.document.topnode)

    def __call__(self, stream, odir, log):
        from calibre.utils.zipfile import ZipFile
        from calibre.ebooks.metadata.odt import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator

        if not os.path.exists(odir):
            os.makedirs(odir)
        with CurrentDir(odir):
            log('Extracting ODT file...')
            stream.seek(0)
            mi = get_metadata(stream, 'odt')
            if not mi.title:
                mi.title = _('Unknown')
            if not mi.authors:
                mi.authors = [_('Unknown')]
            self.filter_load(stream, mi, log)
            html = self.xhtml()
            # A blanket img specification like this causes problems
            # with EPUB output as the containing element often has
            # an absolute height and width set that is larger than
            # the available screen real estate
            html = html.replace('img { width: 100%; height: 100%; }', '')
            # odf2xhtml creates empty title tag
            html = html.replace('<title></title>','<title>%s</title>'%(mi.title,))
            try:
                html = self.fix_markup(html, log)
            except:
                log.exception('Failed to filter CSS, conversion may be slow')
            with open('index.xhtml', 'wb') as f:
                f.write(html.encode('utf-8'))
            zf = ZipFile(stream, 'r')
            self.extract_pictures(zf)
            opf = OPFCreator(os.path.abspath(os.getcwdu()), mi)
            opf.create_manifest([(os.path.abspath(f), None) for f in
                walk(os.getcwdu())])
            opf.create_spine([os.path.abspath('index.xhtml')])
            with open('metadata.opf', 'wb') as f:
                opf.render(f)
            return os.path.abspath('metadata.opf')



