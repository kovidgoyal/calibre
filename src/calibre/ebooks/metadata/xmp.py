#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, sys
from itertools import repeat

from lxml import etree

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.date import parse_date

_xml_declaration = re.compile(r'<\?xml[^<>]+encoding\s*=\s*[\'"](.*?)[\'"][^<>]*>', re.IGNORECASE)

NS_MAP = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'xmpidq': 'http://ns.adobe.com/xmp/Identifier/qual/1.0/',
    'pdf': 'http://ns.adobe.com/pdf/1.3/',
    'xmpmm': 'http://ns.adobe.com/xap/1.0/mm/',
    'pdfx': 'http://ns.adobe.com/pdfx/1.3/',
    'prism': 'http://prismstandard.org/namespaces/basic/2.0/',
    'crossmark': 'http://crossref.org/crossmark/1.0/',
    'rights': 'http://ns.adobe.com/xap/1.0/rights/',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

def NS(prefix, name):
    return '{%s}%s' % (NS_MAP[prefix], name)

xpath_cache = {}

def XPath(expr):
    ans = xpath_cache.get(expr, None)
    if ans is None:
        xpath_cache[expr] = ans = etree.XPath(expr, namespaces=NS_MAP)
    return ans

def parse_xmp_packet(raw_bytes):
    raw_bytes = raw_bytes.strip()
    enc = None
    pat = r'''<?xpacket\s+[^>]*?begin\s*=\s*['"]([^'"]*)['"]'''
    encodings = ('8', '16-le', '16-be', '32-le', '32-be')
    header = raw_bytes[:1024]
    emap = {'\ufeff'.encode('utf-'+x):'utf-'+x for x in encodings}
    emap[b''] = 'utf-8'
    for q in encodings:
        m = re.search(pat.encode('utf-'+q), header)
        if m is not None:
            enc = emap.get(m.group(1), enc)
            break
    if enc is None:
        return etree.fromstring(raw_bytes)
    raw = _xml_declaration.sub('', raw_bytes.decode(enc))  # lxml barfs if encoding declaration present in unicode string
    return etree.fromstring(raw)

def serialize_xmp_packet(root, encoding='utf-8'):
    root.tail = '\n' + '\n'.join(repeat(' '*100, 30))  # Adobe spec recommends inserting padding at the end of the packet
    raw_bytes = etree.tostring(root, encoding=encoding, pretty_print=True, with_tail=True, method='xml')
    return b'<?xpacket begin="%s" id="W5M0MpCehiHzreSzNTczkc9d"?>\n%s\n<?xpacket end="w"?>' % ('\ufeff'.encode(encoding), raw_bytes)

def read_simple_property(elem):
    if elem.text:
        return elem.text
    return elem.get(NS('rdf', 'resource'), '')

def read_lang_alt(parent):
    items = XPath('descendant::rdf:li[@xml:lang="x-default"]')(parent)
    if items:
        return items[0]
    items = XPath('descendant::rdf:li')(parent)
    if items:
        return items[0]

def read_sequence(parent):
    for item in XPath('descendant::rdf:li')(parent):
        yield read_simple_property(item)

def uniq(vals, kmap=lambda x:x):
    ''' Remove all duplicates from vals, while preserving order. kmap must be a
    callable that returns a hashable value for every item in vals '''
    vals = vals or ()
    lvals = (kmap(x) for x in vals)
    seen = set()
    seen_add = seen.add
    return tuple(x for x, k in zip(vals, lvals) if k not in seen and not seen_add(k))

def multiple_sequences(expr, root):
    ans = []
    for item in XPath(expr)(root):
        ans += list(read_sequence(item))
    return filter(None, uniq(ans))

def first_alt(expr, root):
    for item in XPath(expr)(root):
        q = read_simple_property(read_lang_alt(item))
        if q:
            return q

def first_simple(expr, root):
    for item in XPath(expr)(root):
        q = read_simple_property(item)
        if q:
            return q

def read_xmp_identifer(parent):
    ''' For example:
    <xmp:Identifier rdf:parseType="Resource"><xmpidq:Scheme>URL</xmp:idq><rdf:value>http://foo.com</rdf:value></xmp:Identifier>
    or the longer form:
    <xmp:Identifier><rdf:Description><xmpidq:Scheme>URL</xmp:idq><rdf:value>http://foo.com</rdf:value></rdf:Description></xmp:Identifier>
    '''
    is_resource = parent.attrib.get(NS('rdf', 'parseType'), None) == 'Resource'
    is_resource = is_resource or (len(parent) == 1 and parent[0].tag == NS('rdf', 'Description'))
    if not is_resource:
        return None, None
    value = XPath('descendant::rdf:value')(parent)
    if not value:
        return None, None
    value = value.text or ''
    scheme = XPath('descendant::xmpidq:Scheme')(parent)
    if not scheme:
        return None, value
    return scheme.text or '', value

def read_xmp_packet(raw_bytes):
    root = parse_xmp_packet(raw_bytes)
    mi = Metadata(_('Unknown'))
    title = first_alt('//dc:title', root)
    if title:
        mi.title = title
    authors = multiple_sequences('//dc:creator', root)
    if authors:
        mi.authors = authors
    tags = multiple_sequences('//dc:subject', root) or multiple_sequences('//pdf:Keywords', root)
    if tags:
        mi.tags = tags
    comments = first_alt('//dc:description', root)
    if comments:
        mi.comments = comments
    publishers = multiple_sequences('//dc:publisher', root)
    if publishers:
        mi.publisher = publishers[0]
    try:
        pubdate = parse_date(first_simple('//dc:date', root) or first_simple('//xmp:CreateDate', root), assume_utc=False)
    except:
        pass
    else:
        mi.pubdate = pubdate
    bkp = first_simple('//xmp:CreatorTool', root)
    mi.book_producer = bkp

    identifiers = {}
    for xmpid in XPath('//xmp:Identifier')(root):
        scheme, value = read_xmp_identifer(xmpid)
        if scheme and value:
            identifiers[scheme.lower()] = value

    for namespace in ('prism', 'pdfx'):
        for scheme in ('doi', 'url', 'isbn', 'ISBN'):
            if scheme not in identifiers:
                val = first_simple('//%s:%s' % (namespace, scheme), root)
                scheme = scheme.lower()
                if scheme == 'isbn':
                    val = check_isbn(val)
                if val:
                    identifiers[scheme] = val
    if identifiers:
        mi.set_identifiers(identifiers)

    return mi

def consolidate_metadata(info_mi, xmp_packet):
    ' When both the PDF Info dict and XMP metadata are present, prefer the xmp metadata '
    try:
        xmp_mi = read_xmp_packet(xmp_packet)
    except:
        import traceback
        traceback.print_exc()
    else:
        info_mi.smart_update(xmp_mi, replace_metadata=True)
    return info_mi


if __name__ == '__main__':
    from calibre.utils.podofo import get_xmp_metadata
    xmp_packet = get_xmp_metadata(sys.argv[-1])
    print (read_xmp_packet(xmp_packet))

