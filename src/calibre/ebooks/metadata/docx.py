#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

from io import BytesIO
from typing import IO, TYPE_CHECKING

from lxml import etree

from calibre.ebooks.docx.container import DOCX
from calibre.ebooks.docx.writer.container import update_doc_props, xml2str
from calibre.utils.imghdr import identify
from calibre.utils.xml_parse import safe_xml_fromstring

if TYPE_CHECKING:
    import unittest

    from calibre.ebooks.metadata.book.base import Metadata


def get_cover(docx: DOCX) -> tuple[str | None, bytes] | None:
    doc = docx.document
    get = docx.namespace.get
    images = docx.namespace.XPath(
        '//*[name()="w:drawing" or name()="w:pict"]/descendant::*[(name()="a:blip" and @r:embed) or (name()="v:imagedata" and @r:id)][1]'
    )
    rid_map = docx.document_relationships[0]
    for image in images(doc):
        rid = get(image, 'r:embed') or get(image, 'r:id')
        if rid in rid_map:
            try:
                raw = docx.read(rid_map[rid])
                fmt, width, height = identify(raw)
            except Exception:
                continue
            if width < 0 or height < 0:
                continue
            if 0.8 <= height / width <= 1.8 and height * width >= 160000:
                return fmt, raw


def get_metadata(stream: IO[bytes]) -> Metadata:
    c = DOCX(stream, extract=False)
    mi = c.metadata
    try:
        cdata = get_cover(c)
    except Exception:
        cdata = None
        import traceback

        traceback.print_exc()
    c.close()
    stream.seek(0)
    if cdata is not None:
        mi.cover_data = cdata

    return mi


def register_core_properties(c: DOCX, dp_name: str, replacements: dict[str, BytesIO]) -> None:
    """
    Make sure the core properties part is declared in [Content_Types].xml and
    linked from _rels/.rels, adding the modified files to replacements. Word
    only reads core properties through the package relationship.
    """
    ns = c.namespace.namespaces
    part_name = '/' + dp_name.lstrip('/')
    ct = safe_xml_fromstring(c.read('[Content_Types].xml'))
    if not any('/' + (x.get('PartName') or '').lstrip('/').lower() == part_name.lower() for x in ct.iterchildren('{{{}}}Override'.format(ns['ct']))):
        ct.append(
            ct.makeelement(
                '{{{}}}Override'.format(ns['ct']),
                PartName=part_name,
                ContentType='application/vnd.openxmlformats-package.core-properties+xml',
            )
        )
        replacements['[Content_Types].xml'] = BytesIO(xml2str(ct))
    if c.namespace.names['DOCPROPS'] not in c.relationships:
        rels = safe_xml_fromstring(c.read('_rels/.rels'))
        rel_tag = '{{{}}}Relationship'.format(ns['pr'])
        existing_ids = {x.get('Id') for x in rels.iterchildren(rel_tag)}
        num = 1
        while f'rIdCoreProps{num}' in existing_ids:
            num += 1
        rels.append(rels.makeelement(rel_tag, Id=f'rIdCoreProps{num}', Type=c.namespace.names['DOCPROPS'], Target=part_name.lstrip('/')))
        replacements['_rels/.rels'] = BytesIO(xml2str(rels))


def set_metadata(stream: IO[bytes], mi: Metadata) -> None:
    from calibre.utils.zipfile import safe_replace

    c = DOCX(stream, extract=False)
    try:
        dp_name, ap_name = c.get_document_properties_names()
        replacements: dict[str, BytesIO] = {}
        if dp_name is None:
            dp_name = 'docProps/core.xml'
        if c.exists(dp_name):
            cp = safe_xml_fromstring(c.read(dp_name))
        else:
            # The core properties part is optional and some DOCX producers omit it
            ns = c.namespace.namespaces
            cp = etree.Element('{{{}}}coreProperties'.format(ns['cp']), nsmap={x: ns[x] for x in 'cp dc dcterms xsi'.split()})
        register_core_properties(c, dp_name, replacements)
        try:
            ap_raw = None if ap_name is None else c.read(ap_name)
        except Exception:
            ap_raw = None
    finally:
        c.close()
    update_doc_props(cp, mi, c.namespace)
    if ap_raw is not None and ap_name is not None:
        ap = safe_xml_fromstring(ap_raw)
        comp = ap.makeelement('{{{}}}Company'.format(c.namespace.namespaces['ep']))
        for child in tuple(ap):
            if child.tag == comp.tag:
                ap.remove(child)
        comp.text = mi.publisher
        ap.append(comp)
        replacements[ap_name] = BytesIO(xml2str(ap))
    stream.seek(0)
    safe_replace(stream, dp_name, BytesIO(xml2str(cp)), extra_replacements=replacements, add_missing=True)


def find_tests() -> unittest.TestSuite:
    import unittest
    from zipfile import ZipFile

    from calibre.ebooks.metadata.book.base import Metadata

    ct_tmpl = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '{}</Types>'
    )
    rels_tmpl = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '{}</Relationships>'
    )
    core_rel = (
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    )
    core_override = '<Override PartName="{}" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    core = (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Old</dc:title><dc:subject>Kept</dc:subject></cp:coreProperties>'
    )
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>'
    )

    def make_docx(rels: str = '', override: str = '', has_core: bool = False) -> BytesIO:
        stream = BytesIO()
        with ZipFile(stream, 'w') as zf:
            zf.writestr('[Content_Types].xml', ct_tmpl.format(override))
            zf.writestr('_rels/.rels', rels_tmpl.format(rels))
            zf.writestr('word/document.xml', document)
            if has_core:
                zf.writestr('docProps/core.xml', core)
        stream.seek(0)
        return stream

    class TestDOCXMetadata(unittest.TestCase):
        def check(self, stream: BytesIO) -> None:
            mi = Metadata('New title', ['Some Author'])
            mi.comments = 'Some description'
            set_metadata(stream, mi)
            stream.seek(0)
            rmi = get_metadata(stream)
            self.assertEqual(rmi.title, 'New title')
            self.assertEqual(rmi.authors, ['Some Author'])
            self.assertEqual(rmi.comments, 'Some description')
            stream.seek(0)
            with ZipFile(stream) as zf:
                self.assertIsNone(zf.testzip())
                rels = zf.read('_rels/.rels').decode()
                ct = zf.read('[Content_Types].xml').decode()
                self.assertIn('docProps/core.xml', zf.namelist())
            self.assertEqual(rels.count('metadata/core-properties'), 1)
            self.assertEqual(ct.lower().count('docprops/core.xml'), 1)
            stream.seek(0)
            c = DOCX(stream, extract=False)
            self.assertEqual(c.relationships.get(c.namespace.names['DOCPROPS']), 'docProps/core.xml')
            c.close()

        def test_core_properties_present(self) -> None:
            self.check(make_docx(core_rel, core_override.format('/docProps/core.xml'), has_core=True))

        def test_core_properties_missing(self) -> None:
            stream = make_docx()
            self.check(stream)
            # Writing again must not add duplicate registrations
            stream.seek(0)
            self.check(stream)

        def test_core_properties_relationship_without_part(self) -> None:
            self.check(make_docx(core_rel, core_override.format('/docProps/core.xml')))

        def test_core_properties_part_without_relationship(self) -> None:
            self.check(make_docx(has_core=True))

        def test_core_properties_override_without_leading_slash(self) -> None:
            self.check(make_docx(override=core_override.format('docProps/core.xml')))

        def test_core_properties_relationship_target_case_differs(self) -> None:
            # Must update the existing part, not add a second one differing only in case
            stream = make_docx(core_rel.replace('core.xml', 'Core.xml'), core_override.format('/docProps/core.xml'), has_core=True)
            set_metadata(stream, Metadata('New title', ['Some Author']))
            stream.seek(0)
            with ZipFile(stream) as zf:
                names = [n for n in zf.namelist() if n.lower() == 'docprops/core.xml']
                self.assertEqual(names, ['docProps/core.xml'])
                raw = zf.read('docProps/core.xml').decode()
                ct = zf.read('[Content_Types].xml').decode()
            self.assertIn('New title', raw)
            self.assertIn('Kept', raw)
            self.assertEqual(ct.lower().count('docprops/core.xml'), 1)
            stream.seek(0)
            self.assertEqual(get_metadata(stream).title, 'New title')

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDOCXMetadata)


if __name__ == '__main__':
    import sys

    with open(sys.argv[-1], 'rb') as stream:
        print(get_metadata(stream))
