"""
    Parses XMP metadata from PDF files.
    adapted from:
    http://blog.matt-swain.com/post/25650072381/a-lightweight-xmp-parser-for-extracting-pdf-metadata-in
"""

from collections import defaultdict
from xml.etree import ElementTree as ET

RDF_NS = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
NS_MAP = {
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#'    : 'rdf',
    'http://purl.org/dc/elements/1.1/'               : 'dc',
    'http://ns.adobe.com/xap/1.0/'                   : 'xap',
    'http://ns.adobe.com/pdf/1.3/'                   : 'pdf',
    'http://ns.adobe.com/xap/1.0/mm/'                : 'xapmm',
    'http://ns.adobe.com/pdfx/1.3/'                  : 'pdfx',
    'http://prismstandard.org/namespaces/basic/2.0/' : 'prism',
    'http://crossref.org/crossmark/1.0/'             : 'crossmark',
    'http://ns.adobe.com/xap/1.0/rights/'            : 'rights',
    'http://www.w3.org/XML/1998/namespace'           : 'xml'
}

def _parse_tag(el):
    """ Extract the namespace and tag from an element. """
    ns = None
    tag = el.tag
    if tag[0] == "{":
        ns, tag = tag[1:].split('}',1)
        if ns in NS_MAP:
            ns = NS_MAP[ns]
    return ns, tag

def _parse_value(el):
    """ Extract the metadata value from an element. """
    if el.find(RDF_NS+'Bag') is not None:
        value = [li.text for li in el.findall(RDF_NS+'Bag/'+RDF_NS+'li')]
    elif el.find(RDF_NS+'Seq') is not None:
        value = [li.text for li in el.findall(RDF_NS+'Seq/'+RDF_NS+'li')]
    elif el.find(RDF_NS+'Alt') is not None:
        value = {li.get(XML_NS+'lang'):li.text \
                    for li in el.findall(RDF_NS+'Alt/'+RDF_NS+'li')}
    else:
        value = el.text
    return value

def xmp_to_dict(xmp):
    """ Parsing an XMP string into a python dictionary. """

    tree = ET.XML(xmp)
    rdftree = tree.find(RDF_NS+'RDF')
    meta = defaultdict(dict)

    for desc in rdftree.findall(RDF_NS+'Description'):
        for el in desc.getchildren():
            ns, tag =  _parse_tag(el)
            value = _parse_value(el)
            meta[ns][tag] = value

    return dict(meta)