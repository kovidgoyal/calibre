#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from io import BytesIO

from calibre.ebooks.docx.container import DOCX
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.ebooks.docx.writer.container import update_doc_props, xml2str
from calibre.utils.imghdr import identify


def get_cover(docx):
    doc = docx.document
    get = docx.namespace.get
    images = docx.namespace.XPath(
        '//*[name()="w:drawing" or name()="w:pict"]/descendant::*[(name()="a:blip" and @r:embed) or (name()="v:imagedata" and @r:id)][1]')
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
            if 0.8 <= height/width <= 1.8 and height*width >= 160000:
                return (fmt, raw)


def get_metadata(stream):
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


def set_metadata(stream, mi):
    from calibre.utils.zipfile import safe_replace
    c = DOCX(stream, extract=False)
    dp_name, ap_name = c.get_document_properties_names()
    dp_raw = c.read(dp_name)
    try:
        ap_raw = c.read(ap_name)
    except Exception:
        ap_raw = None
    cp = safe_xml_fromstring(dp_raw)
    update_doc_props(cp, mi, c.namespace)
    replacements = {}
    if ap_raw is not None:
        ap = safe_xml_fromstring(ap_raw)
        comp = ap.makeelement('{%s}Company' % c.namespace.namespaces['ep'])
        for child in tuple(ap):
            if child.tag == comp.tag:
                ap.remove(child)
        comp.text = mi.publisher
        ap.append(comp)
        replacements[ap_name] = BytesIO(xml2str(ap))
    stream.seek(0)
    safe_replace(stream, dp_name, BytesIO(xml2str(cp)), extra_replacements=replacements)


if __name__ == '__main__':
    import sys
    with open(sys.argv[-1], 'rb') as stream:
        print(get_metadata(stream))
