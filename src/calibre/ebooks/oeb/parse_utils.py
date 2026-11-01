#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>

import re
from typing import TYPE_CHECKING, TypeGuard

from lxml import etree

from calibre import force_unicode, xml_replace_entities
from calibre.constants import filesystem_encoding
from calibre.ebooks.chardet import strip_encoding_declarations, xml_to_unicode
from calibre.utils.localization import _
from calibre.utils.xml_parse import safe_html_fromstring, safe_xml_fromstring
from calibre_extensions.speedup import barename, namespace

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from calibre.ebooks.oeb.base import XPathResult
    from calibre.utils.logging import Log

XHTML_NS = 'http://www.w3.org/1999/xhtml'
XMLNS_NS = 'http://www.w3.org/2000/xmlns/'


class NotHTML(Exception):
    def __init__(self, root_tag: str) -> None:
        Exception.__init__(self, 'Data is not HTML')
        self.root_tag = root_tag


def XHTML(name: str) -> str:
    return f'{{{XHTML_NS}}}{name}'


def is_element_list(x: object) -> TypeGuard[list[etree._Element]]:
    """Use as ``assert is_element_list(ans)`` to narrow the result of an XPath
    expression that selects only elements"""
    return isinstance(x, list) and all(isinstance(y, etree._Element) for y in x)


def is_str_list(x: object) -> TypeGuard[list[str]]:
    """Use as ``assert is_str_list(ans)`` to narrow the result of an XPath
    expression that selects only attribute values or text nodes"""
    return isinstance(x, list) and all(isinstance(y, str) for y in x)


def xpath(elem: etree._Element, expr: str) -> XPathResult:
    return elem.xpath(expr, namespaces={'h': XHTML_NS})


def XPath(expr: str) -> etree.XPath:
    return etree.XPath(expr, namespaces={'h': XHTML_NS})


META_XP = XPath('/h:html/h:head/h:meta[@http-equiv="Content-Type"]')


def merge_multiple_html_heads_and_bodies(root: etree._Element, log: Log | None = None) -> etree._Element:
    heads, bodies = xpath(root, '//h:head'), xpath(root, '//h:body')
    assert is_element_list(heads) and is_element_list(bodies)
    if not (len(heads) > 1 or len(bodies) > 1):
        return root
    for child in root:
        root.remove(child)
    head = root.makeelement(XHTML('head'))
    body = root.makeelement(XHTML('body'))
    for h in heads:
        for x in h:
            head.append(x)
    for b in bodies:
        for x in b:
            body.append(x)
    for x in (head, body):
        root.append(x)
    if log is not None:
        log.warn('Merging multiple <head> and <body> sections')
    return root


def clone_element(elem: etree._Element, nsmap: Mapping[str | None, str] | None = None, in_context: bool = True) -> etree._Element:
    if nsmap is None:
        nsmap = {}
    if in_context:
        maker = elem.getroottree().getroot().makeelement
    else:
        maker = etree.Element
    nelem = maker(elem.tag, attrib=elem.attrib, nsmap=nsmap)
    nelem.text, nelem.tail = elem.text, elem.tail
    nelem.extend(tuple(elem))
    return nelem


def node_depth(node: etree._Element) -> int:
    ans = 0
    p = node.getparent()
    while p is not None:
        ans += 1
        p = p.getparent()
    return ans


def html5_parse(data: str, max_nesting_depth: int = 100) -> etree._Element:
    from html5_parser import parse

    from calibre.utils.cleantext import clean_xml_chars

    root = parse(clean_xml_chars(data), maybe_xhtml=True, keep_doctype=False, sanitize_names=True)
    # Check that the asinine HTML 5 algorithm did not result in a tree with
    # insane nesting depths
    for x in root.iterdescendants():
        if isinstance(x.tag, (str, bytes)) and not len(x):  # Leaf node
            depth = node_depth(x)
            if depth > max_nesting_depth:
                raise ValueError(f'HTML 5 parsing resulted in a tree with nesting depth > {max_nesting_depth}')
    return root


def _html4_parse(data: str) -> etree._Element:
    root = safe_html_fromstring(data)
    root.attrib.pop('xmlns', None)
    for elem in root.iter(tag=etree.Comment):
        if elem.text:
            elem.text = elem.text.strip('-')
    data = etree.tostring(root, encoding='unicode')

    root = safe_xml_fromstring(data)
    return root


def clean_word_doc(data: str, log: Log) -> str:
    prefixes = []
    for match in re.finditer(r'xmlns:(\S+?)=".*?microsoft.*?"', data):
        prefixes.append(match.group(1))
    if prefixes:
        log.warn('Found microsoft markup, cleaning...')
        # Remove empty tags as they are not rendered by browsers
        # but can become renderable HTML tags like <p/> if the
        # document is parsed by an HTML parser
        pat = re.compile(r'<({}):([a-zA-Z0-9]+)[^>/]*?></\1:\2>'.format('|'.join(prefixes)), re.DOTALL)
        data = pat.sub('', data)
        pat = re.compile(r'<({}):([a-zA-Z0-9]+)[^>/]*?/>'.format('|'.join(prefixes)))
        data = pat.sub('', data)
    return data


def ensure_namespace_prefixes(node: etree._Element, nsmap: Mapping[str | None, str]) -> etree._Element:
    namespace_uris = frozenset(nsmap.values())
    fnsmap = {k: v for k, v in node.nsmap.items() if v not in namespace_uris}
    fnsmap.update(nsmap)
    if fnsmap != dict(node.nsmap):
        node = clone_element(node, nsmap=fnsmap, in_context=False)
    return node


class HTML5Doc(ValueError):
    pass


def check_for_html5(prefix: str, root: etree._Element) -> None:
    if re.search(r'<!DOCTYPE\s+html\s*>', prefix, re.IGNORECASE) is not None:
        if root.xpath('//svg'):
            raise HTML5Doc('This document appears to be un-namespaced HTML 5, should be parsed by the HTML 5 parser')


def parse_html(
    data: str | bytes,
    log: Log | None = None,
    decoder: Callable[[bytes], str] | None = None,
    preprocessor: Callable[[str], str] | None = None,
    filename: str | bytes = '<string>',
    non_html_file_tags: Collection[str] = frozenset(),
) -> etree._Element:
    if log is None:
        from calibre.utils.logging import default_log

        log = default_log

    filename = force_unicode(filename, enc=filesystem_encoding)

    if not isinstance(data, str):
        if decoder is not None:
            data = decoder(data)
        else:
            data = xml_to_unicode(data)[0]

    data = strip_encoding_declarations(data)
    # Remove DOCTYPE declaration as it messes up parsing
    # In particular, it causes tostring to insert xmlns
    # declarations, which messes up the coercing logic
    pre = ''
    idx = data.find('<html')
    if idx == -1:
        idx = data.find('<HTML')
    has_html4_doctype = False
    if idx > -1:
        pre = data[:idx]
        data = data[idx:]
        if '<!DOCTYPE' in pre:  # Handle user defined entities
            # kindlegen produces invalid xhtml with uppercase attribute names
            # if fed HTML 4 with uppercase attribute names, so try to detect
            # and compensate for that.
            has_html4_doctype = re.search(r'<!DOCTYPE\s+[^>]+HTML\s+4.0[^.]+>', pre) is not None
            # Process private entities
            user_entities = {}
            for match in re.finditer(r'<!ENTITY\s+(\S+)\s+([^>]+)', pre):
                val = match.group(2)
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                user_entities[match.group(1)] = val
            if user_entities:
                pat = re.compile(r'&({});'.format('|'.join(list(user_entities.keys()))))
                data = pat.sub(lambda m: user_entities[m.group(1)], data)

    if preprocessor is not None:
        data = preprocessor(data)

    # There could be null bytes in data if it had &#0; entities in it
    data = data.replace('\0', '')
    data = raw = clean_word_doc(data, log)

    # Try with more & more drastic measures to parse
    try:
        root = safe_xml_fromstring(data, recover=False)
        check_for_html5(pre, root)
    except HTML5Doc, etree.XMLSyntaxError:
        log.debug('Initial parse failed, using more forgiving parsers')
        raw = data = xml_replace_entities(raw)
        try:
            root = safe_xml_fromstring(data, recover=False)
            check_for_html5(pre, root)
        except HTML5Doc, etree.XMLSyntaxError:
            log.debug(f'Parsing {filename} as HTML')
            data = raw
            try:
                root = html5_parse(data)
            except Exception:
                log.exception('HTML 5 parsing failed, falling back to older parsers')
                root = _html4_parse(data)

    if has_html4_doctype or root.tag == 'HTML' or (len(root) and (root[-1].get('LANG') or root[-1].get('DIR'))):
        # Lower case all tag and attribute names
        assert isinstance(root.tag, str)
        root.tag = root.tag.lower()
        for x in root.iterdescendants():
            try:
                if isinstance(x.tag, str):
                    x.tag = x.tag.lower()
                for key, val in list(x.attrib.items()):
                    del x.attrib[key]
                    key = key.lower()
                    x.attrib[key] = val
            except Exception:
                pass

    if not isinstance(root.tag, str) or barename(root.tag) != 'html':
        if isinstance(root.tag, str) and barename(root.tag) in non_html_file_tags:
            raise NotHTML(root.tag)
        log.warn(f'File {filename!r} does not appear to be (X)HTML')
        nroot = safe_xml_fromstring('<html></html>')
        has_body = False
        for child in list(root):
            if isinstance(child.tag, str) and barename(child.tag) == 'body':
                has_body = True
                break
        parent = nroot
        if not has_body:
            log.warn(f'File {filename!r} appears to be a HTML fragment')
            nroot = safe_xml_fromstring('<html><body/></html>')
            parent = nroot[0]
        for child in list(root.iter()):
            oparent = child.getparent()
            if oparent is not None:
                oparent.remove(child)
            parent.append(child)
        root = nroot

    # Force into the XHTML namespace
    if not isinstance(root.tag, str) or not namespace(root.tag):
        log.warn('Forcing', filename, 'into XHTML namespace')
        root.attrib['xmlns'] = XHTML_NS
        sdata = etree.tostring(root, encoding='unicode')

        try:
            root = safe_xml_fromstring(sdata, recover=False)
        except Exception:
            sdata = sdata.replace(':=', '=').replace(':>', '>')
            sdata = sdata.replace('<http:/>', '')
            try:
                root = safe_xml_fromstring(sdata, recover=False)
            except etree.XMLSyntaxError:
                log.warn(f'Stripping comments from {filename}')
                sdata = re.compile(r'<!--.*?-->', re.DOTALL).sub('', sdata)
                sdata = sdata.replace("<?xml version='1.0' encoding='utf-8'?><o:p></o:p>", '')
                sdata = sdata.replace("<?xml version='1.0' encoding='utf-8'??>", '')
                try:
                    root = safe_xml_fromstring(sdata)
                except etree.XMLSyntaxError:
                    log.warn(f'Stripping meta tags from {filename}')
                    sdata = re.sub(r'<meta\s+[^>]+?>', '', sdata)
                    root = safe_xml_fromstring(sdata)
    elif isinstance(root.tag, str) and namespace(root.tag) != XHTML_NS:
        # OEB_DOC_NS, but possibly others
        ns = namespace(root.tag)
        attrib = dict(root.attrib)
        nroot = etree.Element(XHTML('html'), nsmap={None: XHTML_NS}, attrib=attrib)
        for elem in root.iterdescendants():
            if isinstance(elem.tag, str) and namespace(elem.tag) == ns:
                elem.tag = XHTML(barename(elem.tag))
        for elem in root:
            nroot.append(elem)
        root = nroot

    # Remove non default prefixes referring to the XHTML namespace
    root = ensure_namespace_prefixes(root, {None: XHTML_NS})

    root = merge_multiple_html_heads_and_bodies(root, log)
    # Ensure has a <head/>
    heads = xpath(root, '/h:html/h:head')
    assert is_element_list(heads)
    head = heads[0] if heads else None
    if head is None:
        log.warn(f'File {filename} missing <head/> element')
        head = etree.Element(XHTML('head'))
        root.insert(0, head)
        title = etree.SubElement(head, XHTML('title'))
        title.text = _('Unknown')
    elif not xpath(root, '/h:html/h:head/h:title'):
        title = etree.SubElement(head, XHTML('title'))
        title.text = _('Unknown')
    # Ensure <title> is not empty
    titles = xpath(root, '/h:html/h:head/h:title')
    assert is_element_list(titles)
    title = titles[0]
    if not title.text or not title.text.strip():
        title.text = _('Unknown')
    # Remove any encoding-specifying <meta/> elements
    for meta in META_XP(root):
        meta.getparent().remove(meta)
    meta = etree.SubElement(head, XHTML('meta'), attrib={'http-equiv': 'Content-Type'})
    meta.set('content', 'text/html; charset=utf-8')  # Ensure content is second attribute

    # Ensure has a <body/>
    if not xpath(root, '/h:html/h:body'):
        bodies = xpath(root, '//h:body')
        assert is_element_list(bodies)
        if bodies:
            body = bodies[0]
            bparent = body.getparent()
            assert bparent is not None  # body is not the root, which is <html>
            bparent.remove(body)
            root.append(body)
        else:
            log.warn(f'File {filename} missing <body/> element')
            etree.SubElement(root, XHTML('body'))

    # Remove microsoft office markup
    r: list[etree._Element] = []
    for x in root.iterdescendants(etree.Element):
        tag = x.tag
        assert isinstance(tag, str)  # the etree.Element filter excludes comments/PIs/entities
        if 'microsoft-com' in tag:
            r.append(x)
    for x in r:
        x.tag = XHTML('span')

    def remove_elem(a: etree._Element) -> None:

        p = a.getparent()
        assert p is not None  # a is a descendant of the <html> root
        idx = p.index(a) - 1
        p.remove(a)
        if a.tail:
            if idx < 0:
                p.text = (p.text or '') + a.tail
            else:
                p[idx].tail = (p[idx].tail or '') + a.tail

    # Remove hyperlinks with no content as they cause rendering
    # artifacts in browser based renderers
    # Also remove empty <b>, <u> and <i> tags
    links = xpath(root, '//h:a[@href]|//h:i|//h:b|//h:u')
    assert is_element_list(links)
    for a in links:
        if a.get('id', None) is None and a.get('name', None) is None and len(a) == 0 and not a.text:
            remove_elem(a)

    # Convert <br>s with content into paragraphs as ADE can't handle
    # them
    brs = xpath(root, '//h:br')
    assert is_element_list(brs)
    for br in brs:
        if len(br) > 0 or br.text:
            br.tag = XHTML('div')

    # Remove any stray text in the <head> section and format it nicely
    root.text = '\n  '
    heads = xpath(root, '//h:head')
    assert is_element_list(heads)
    if heads:
        head = heads[0]
        head.text = '\n    '
        head.tail = '\n  '
        for child in head:
            child.tail = '\n    '
        child.tail = '\n  '

    return root
