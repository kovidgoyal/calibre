#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap, os

from lxml import etree
from lxml.builder import ElementMaker

from calibre import guess_type
from calibre.constants import numeric_version, __appname__
from calibre.ebooks.docx.names import DOCXNamespace
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.pdf.render.common import PAPER_SIZES
from calibre.utils.date import utcnow
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1
from calibre.utils.zipfile import ZipFile
from polyglot.builtins import iteritems, native_string_type


def xml2str(root, pretty_print=False, with_tail=False):
    if hasattr(etree, 'cleanup_namespaces'):
        etree.cleanup_namespaces(root)
    ans = etree.tostring(root, encoding='utf-8', xml_declaration=True,
                          pretty_print=pretty_print, with_tail=with_tail)
    return ans


def page_size(opts):
    width, height = PAPER_SIZES[opts.docx_page_size]
    if opts.docx_custom_page_size is not None:
        width, height = map(float, opts.docx_custom_page_size.partition('x')[0::2])
    return width, height


def page_margin(opts, which):
    val = getattr(opts, 'docx_page_margin_' + which)
    if val == 0.0:
        val = getattr(opts, 'margin_' + which)
    return val


def page_effective_area(opts):
    width, height = page_size(opts)
    width -= page_margin(opts, 'left') + page_margin(opts, 'right')
    height -= page_margin(opts, 'top') + page_margin(opts, 'bottom')
    return width, height  # in pts


def create_skeleton(opts, namespaces=None):
    namespaces = namespaces or DOCXNamespace().namespaces

    def w(x):
        return '{{{}}}{}'.format(namespaces['w'], x)
    dn = {k:v for k, v in iteritems(namespaces) if k in {'w', 'r', 'm', 've', 'o', 'wp', 'w10', 'wne', 'a', 'pic'}}
    E = ElementMaker(namespace=dn['w'], nsmap=dn)
    doc = E.document()
    body = E.body()
    doc.append(body)
    width, height = page_size(opts)
    width, height = int(20 * width), int(20 * height)

    def margin(which):
        val = page_margin(opts, which)
        return w(which), str(int(val * 20))
    body.append(E.sectPr(
        E.pgSz(**{w('w'):str(width), w('h'):str(height)}),
        E.pgMar(**dict(map(margin, 'left top right bottom'.split()))),
        E.cols(**{w('space'):'720'}),
        E.docGrid(**{w('linePitch'):"360"}),
    ))

    dn = {k:v for k, v in iteritems(namespaces) if k in tuple('wra') + ('wp',)}
    E = ElementMaker(namespace=dn['w'], nsmap=dn)
    styles = E.styles(
        E.docDefaults(
            E.rPrDefault(
                E.rPr(
                    E.rFonts(**{w('asciiTheme'):"minorHAnsi", w('eastAsiaTheme'):"minorEastAsia", w('hAnsiTheme'):"minorHAnsi", w('cstheme'):"minorBidi"}),
                    E.sz(**{w('val'):'22'}),
                    E.szCs(**{w('val'):'22'}),
                    E.lang(**{w('val'):'en-US', w('eastAsia'):"en-US", w('bidi'):"ar-SA"})
                )
            ),
            E.pPrDefault(
                E.pPr(
                    E.spacing(**{w('after'):"0", w('line'):"276", w('lineRule'):"auto"})
                )
            )
        )
    )
    return doc, styles, body


def update_doc_props(root, mi, namespace):
    def setm(name, text=None, ns='dc'):
        ans = root.makeelement(f'{{{namespace.namespaces[ns]}}}{name}')
        for child in tuple(root):
            if child.tag == ans.tag:
                root.remove(child)
        ans.text = text
        root.append(ans)
        return ans
    setm('title', mi.title)
    setm('creator', authors_to_string(mi.authors))
    if mi.tags:
        setm('keywords', ', '.join(mi.tags), ns='cp')
    if mi.comments:
        setm('description', mi.comments)
    if mi.languages:
        l = canonicalize_lang(mi.languages[0])
        setm('language', lang_as_iso639_1(l) or l)


class DocumentRelationships:

    def __init__(self, namespace):
        self.rmap = {}
        self.namespace = namespace
        for typ, target in iteritems({
                namespace.names['STYLES']: 'styles.xml',
                namespace.names['NUMBERING']: 'numbering.xml',
                namespace.names['WEB_SETTINGS']: 'webSettings.xml',
                namespace.names['FONTS']: 'fontTable.xml',
        }):
            self.add_relationship(target, typ)

    def get_relationship_id(self, target, rtype, target_mode=None):
        return self.rmap.get((target, rtype, target_mode))

    def add_relationship(self, target, rtype, target_mode=None):
        ans = self.get_relationship_id(target, rtype, target_mode)
        if ans is None:
            ans = 'rId%d' % (len(self.rmap) + 1)
            self.rmap[(target, rtype, target_mode)] = ans
        return ans

    def add_image(self, target):
        return self.add_relationship(target, self.namespace.names['IMAGES'])

    def serialize(self):
        namespaces = self.namespace.namespaces
        E = ElementMaker(namespace=namespaces['pr'], nsmap={None:namespaces['pr']})
        relationships = E.Relationships()
        for (target, rtype, target_mode), rid in iteritems(self.rmap):
            r = E.Relationship(Id=rid, Type=rtype, Target=target)
            if target_mode is not None:
                r.set('TargetMode', target_mode)
            relationships.append(r)
        return xml2str(relationships)


class DOCX:

    def __init__(self, opts, log):
        self.namespace = DOCXNamespace()
        namespaces = self.namespace.namespaces
        self.opts, self.log = opts, log
        self.document_relationships = DocumentRelationships(self.namespace)
        self.font_table = etree.Element('{%s}fonts' % namespaces['w'], nsmap={k:namespaces[k] for k in 'wr'})
        self.numbering = etree.Element('{%s}numbering' % namespaces['w'], nsmap={k:namespaces[k] for k in 'wr'})
        E = ElementMaker(namespace=namespaces['pr'], nsmap={None:namespaces['pr']})
        self.embedded_fonts = E.Relationships()
        self.fonts = {}
        self.images = {}

    # Boilerplate {{{
    @property
    def contenttypes(self):
        E = ElementMaker(namespace=self.namespace.namespaces['ct'], nsmap={None:self.namespace.namespaces['ct']})
        types = E.Types()
        for partname, mt in iteritems({
            "/word/footnotes.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
            "/word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            "/word/numbering.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
            "/word/styles.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
            "/word/endnotes.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
            "/word/settings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
            "/word/theme/theme1.xml": "application/vnd.openxmlformats-officedocument.theme+xml",
            "/word/fontTable.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
            "/word/webSettings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml",
            "/docProps/core.xml": "application/vnd.openxmlformats-package.core-properties+xml",
            "/docProps/app.xml": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
        }):
            types.append(E.Override(PartName=partname, ContentType=mt))
        added = {'png', 'gif', 'jpeg', 'jpg', 'svg', 'xml'}
        for ext in added:
            types.append(E.Default(Extension=ext, ContentType=guess_type('a.'+ext)[0]))
        for ext, mt in iteritems({
            "rels": "application/vnd.openxmlformats-package.relationships+xml",
            "odttf": "application/vnd.openxmlformats-officedocument.obfuscatedFont",
        }):
            added.add(ext)
            types.append(E.Default(Extension=ext, ContentType=mt))
        for fname in self.images:
            ext = fname.rpartition(os.extsep)[-1]
            if ext not in added:
                added.add(ext)
                mt = guess_type('a.' + ext)[0]
                if mt:
                    types.append(E.Default(Extension=ext, ContentType=mt))
        return xml2str(types)

    @property
    def appproperties(self):
        E = ElementMaker(namespace=self.namespace.namespaces['ep'], nsmap={None:self.namespace.namespaces['ep']})
        props = E.Properties(
            E.Application(__appname__),
            E.AppVersion('%02d.%04d' % numeric_version[:2]),
            E.DocSecurity('0'),
            E.HyperlinksChanged('false'),
            E.LinksUpToDate('true'),
            E.ScaleCrop('false'),
            E.SharedDoc('false'),
        )
        if self.mi.publisher:
            props.append(E.Company(self.mi.publisher))
        return xml2str(props)

    @property
    def containerrels(self):
        return textwrap.dedent('''\
        <?xml version='1.0' encoding='utf-8'?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
            <Relationship Id="rId3" Type="{APPPROPS}" Target="docProps/app.xml"/>
            <Relationship Id="rId2" Type="{DOCPROPS}" Target="docProps/core.xml"/>
            <Relationship Id="rId1" Type="{DOCUMENT}" Target="word/document.xml"/>
        </Relationships>'''.format(**self.namespace.names)).encode('utf-8')

    @property
    def websettings(self):
        E = ElementMaker(namespace=self.namespace.namespaces['w'], nsmap={'w':self.namespace.namespaces['w']})
        ws = E.webSettings(
            E.optimizeForBrowser, E.allowPNG, E.doNotSaveAsSingleFile)
        return xml2str(ws)

    # }}}

    def convert_metadata(self, mi):
        namespaces = self.namespace.namespaces
        E = ElementMaker(namespace=namespaces['cp'], nsmap={x:namespaces[x] for x in 'cp dc dcterms xsi'.split()})
        cp = E.coreProperties(E.revision("1"), E.lastModifiedBy('calibre'))
        ts = utcnow().isoformat(native_string_type('T')).rpartition('.')[0] + 'Z'
        for x in 'created modified'.split():
            x = cp.makeelement('{{{}}}{}'.format(namespaces['dcterms'], x), **{'{%s}type' % namespaces['xsi']:'dcterms:W3CDTF'})
            x.text = ts
            cp.append(x)
        self.mi = mi
        update_doc_props(cp, self.mi, self.namespace)
        return xml2str(cp)

    def create_empty_document(self, mi):
        self.document, self.styles = create_skeleton(self.opts)[:2]

    def write(self, path_or_stream, mi, create_empty_document=False):
        if create_empty_document:
            self.create_empty_document(mi)
        with ZipFile(path_or_stream, 'w') as zf:
            zf.writestr('[Content_Types].xml', self.contenttypes)
            zf.writestr('_rels/.rels', self.containerrels)
            zf.writestr('docProps/core.xml', self.convert_metadata(mi))
            zf.writestr('docProps/app.xml', self.appproperties)
            zf.writestr('word/webSettings.xml', self.websettings)
            zf.writestr('word/document.xml', xml2str(self.document))
            zf.writestr('word/styles.xml', xml2str(self.styles))
            zf.writestr('word/numbering.xml', xml2str(self.numbering))
            zf.writestr('word/fontTable.xml', xml2str(self.font_table))
            zf.writestr('word/_rels/document.xml.rels', self.document_relationships.serialize())
            zf.writestr('word/_rels/fontTable.xml.rels', xml2str(self.embedded_fonts))
            for fname, data_getter in iteritems(self.images):
                zf.writestr(fname, data_getter())
            for fname, data in iteritems(self.fonts):
                zf.writestr(fname, data)


if __name__ == '__main__':
    d = DOCX(None, None)
    print(d.websettings)
