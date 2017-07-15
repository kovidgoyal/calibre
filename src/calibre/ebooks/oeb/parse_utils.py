#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from lxml import etree, html

from calibre import xml_replace_entities, force_unicode
from calibre.constants import filesystem_encoding
from calibre.ebooks.chardet import xml_to_unicode, strip_encoding_declarations

RECOVER_PARSER = etree.XMLParser(recover=True, no_network=True)
XHTML_NS     = 'http://www.w3.org/1999/xhtml'
XMLNS_NS     = 'http://www.w3.org/2000/xmlns/'


class NotHTML(Exception):

    def __init__(self, root_tag):
        Exception.__init__(self, 'Data is not HTML')
        self.root_tag = root_tag


def barename(name):
    return name.rpartition('}')[-1]


def namespace(name):
    return name.rpartition('}')[0][1:]


def XHTML(name):
    return '{%s}%s' % (XHTML_NS, name)


def xpath(elem, expr):
    return elem.xpath(expr, namespaces={'h':XHTML_NS})


def XPath(expr):
    return etree.XPath(expr, namespaces={'h':XHTML_NS})


META_XP = XPath('/h:html/h:head/h:meta[@http-equiv="Content-Type"]')


def merge_multiple_html_heads_and_bodies(root, log=None):
    heads, bodies = xpath(root, '//h:head'), xpath(root, '//h:body')
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
    map(root.append, (head, body))
    if log is not None:
        log.warn('Merging multiple <head> and <body> sections')
    return root


def clone_element(elem, nsmap={}, in_context=True):
    if in_context:
        maker = elem.getroottree().getroot().makeelement
    else:
        maker = etree.Element
    nelem = maker(elem.tag, attrib=elem.attrib,
            nsmap=nsmap)
    nelem.text, nelem.tail = elem.text, elem.tail
    nelem.extend(elem)
    return nelem


def node_depth(node):
    ans = 0
    p = node.getparent()
    while p is not None:
        ans += 1
        p = p.getparent()
    return ans


def html5_parse(data, max_nesting_depth=100):
    from html5_parser import parse
    from calibre.utils.cleantext import clean_xml_chars
    data = parse(clean_xml_chars(data), maybe_xhtml=True, keep_doctype=False, sanitize_names=True)
    # Check that the asinine HTML 5 algorithm did not result in a tree with
    # insane nesting depths
    for x in data.iterdescendants():
        if isinstance(x.tag, basestring) and len(x) is 0:  # Leaf node
            depth = node_depth(x)
            if depth > max_nesting_depth:
                raise ValueError('HTML 5 parsing resulted in a tree with nesting'
                        ' depth > %d'%max_nesting_depth)
    return data


def _html4_parse(data, prefer_soup=False):
    if prefer_soup:
        from calibre.utils.soupparser import fromstring
        data = fromstring(data)
    else:
        data = html.fromstring(data)
    data.attrib.pop('xmlns', None)
    for elem in data.iter(tag=etree.Comment):
        if elem.text:
            elem.text = elem.text.strip('-')
    data = etree.tostring(data, encoding=unicode)

    # Setting huge_tree=True causes crashes in windows with large files
    parser = etree.XMLParser(no_network=True)
    try:
        data = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError:
        data = etree.fromstring(data, parser=RECOVER_PARSER)
    return data


def clean_word_doc(data, log):
    prefixes = []
    for match in re.finditer(r'xmlns:(\S+?)=".*?microsoft.*?"', data):
        prefixes.append(match.group(1))
    if prefixes:
        log.warn('Found microsoft markup, cleaning...')
        # Remove empty tags as they are not rendered by browsers
        # but can become renderable HTML tags like <p/> if the
        # document is parsed by an HTML parser
        pat = re.compile(
                r'<(%s):([a-zA-Z0-9]+)[^>/]*?></\1:\2>'%('|'.join(prefixes)),
                re.DOTALL)
        data = pat.sub('', data)
        pat = re.compile(
                r'<(%s):([a-zA-Z0-9]+)[^>/]*?/>'%('|'.join(prefixes)))
        data = pat.sub('', data)
    return data


class HTML5Doc(ValueError):
    pass


def check_for_html5(prefix, root):
    if re.search(r'<!DOCTYPE\s+html\s*>', prefix, re.IGNORECASE) is not None:
        if root.xpath('//svg'):
            raise HTML5Doc('This document appears to be un-namespaced HTML 5, should be parsed by the HTML 5 parser')


def parse_html(data, log=None, decoder=None, preprocessor=None,
        filename='<string>', non_html_file_tags=frozenset()):
    if log is None:
        from calibre.utils.logging import default_log
        log = default_log

    filename = force_unicode(filename, enc=filesystem_encoding)

    if not isinstance(data, unicode):
        if decoder is not None:
            data = decoder(data)
        else:
            data = xml_to_unicode(data)[0]

    data = strip_encoding_declarations(data)
    if preprocessor is not None:
        data = preprocessor(data)

    # There could be null bytes in data if it had &#0; entities in it
    data = data.replace('\0', '')

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
            has_html4_doctype = re.search(r'<!DOCTYPE\s+[^>]+HTML\s+4.0[^.]+>', pre) is not None
            # kindlegen produces invalid xhtml with uppercase attribute names
            # if fed HTML 4 with uppercase attribute names, so try to detect
            # and compensate for that.
            user_entities = {}
            for match in re.finditer(r'<!ENTITY\s+(\S+)\s+([^>]+)', pre):
                val = match.group(2)
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                user_entities[match.group(1)] = val
            if user_entities:
                pat = re.compile(r'&(%s);'%('|'.join(user_entities.keys())))
                data = pat.sub(lambda m:user_entities[m.group(1)], data)

    data = raw = clean_word_doc(data, log)

    # Setting huge_tree=True causes crashes in windows with large files
    parser = etree.XMLParser(no_network=True)

    # Try with more & more drastic measures to parse
    try:
        data = etree.fromstring(data, parser=parser)
        check_for_html5(pre, data)
    except (HTML5Doc, etree.XMLSyntaxError):
        log.debug('Initial parse failed, using more'
                ' forgiving parsers')
        raw = data = xml_replace_entities(raw)
        try:
            data = etree.fromstring(data, parser=parser)
            check_for_html5(pre, data)
        except (HTML5Doc, etree.XMLSyntaxError):
            log.debug('Parsing %s as HTML' % filename)
            data = raw
            try:
                data = html5_parse(data)
            except Exception:
                log.exception(
                    'HTML 5 parsing failed, falling back to older parsers')
                data = _html4_parse(data)

    if has_html4_doctype or data.tag == 'HTML' or (len(data) and (data[-1].get('LANG') or data[-1].get('DIR'))):
        # Lower case all tag and attribute names
        data.tag = data.tag.lower()
        for x in data.iterdescendants():
            try:
                x.tag = x.tag.lower()
                for key, val in list(x.attrib.iteritems()):
                    del x.attrib[key]
                    key = key.lower()
                    x.attrib[key] = val
            except:
                pass

    if barename(data.tag) != 'html':
        if barename(data.tag) in non_html_file_tags:
            raise NotHTML(data.tag)
        log.warn('File %r does not appear to be (X)HTML'%filename)
        nroot = etree.fromstring('<html></html>')
        has_body = False
        for child in list(data):
            if isinstance(child.tag, (unicode, str)) and barename(child.tag) == 'body':
                has_body = True
                break
        parent = nroot
        if not has_body:
            log.warn('File %r appears to be a HTML fragment'%filename)
            nroot = etree.fromstring('<html><body/></html>')
            parent = nroot[0]
        for child in list(data.iter()):
            oparent = child.getparent()
            if oparent is not None:
                oparent.remove(child)
            parent.append(child)
        data = nroot

    # Force into the XHTML namespace
    if not namespace(data.tag):
        log.warn('Forcing', filename, 'into XHTML namespace')
        data.attrib['xmlns'] = XHTML_NS
        data = etree.tostring(data, encoding=unicode)

        try:
            data = etree.fromstring(data, parser=parser)
        except:
            data = data.replace(':=', '=').replace(':>', '>')
            data = data.replace('<http:/>', '')
            try:
                data = etree.fromstring(data, parser=parser)
            except etree.XMLSyntaxError:
                log.warn('Stripping comments from %s'%
                        filename)
                data = re.compile(r'<!--.*?-->', re.DOTALL).sub('',
                        data)
                data = data.replace(
                    "<?xml version='1.0' encoding='utf-8'?><o:p></o:p>",
                    '')
                data = data.replace("<?xml version='1.0' encoding='utf-8'??>", '')
                try:
                    data = etree.fromstring(data,
                            parser=RECOVER_PARSER)
                except etree.XMLSyntaxError:
                    log.warn('Stripping meta tags from %s'% filename)
                    data = re.sub(r'<meta\s+[^>]+?>', '', data)
                    data = etree.fromstring(data, parser=RECOVER_PARSER)
    elif namespace(data.tag) != XHTML_NS:
        # OEB_DOC_NS, but possibly others
        ns = namespace(data.tag)
        attrib = dict(data.attrib)
        nroot = etree.Element(XHTML('html'),
            nsmap={None: XHTML_NS}, attrib=attrib)
        for elem in data.iterdescendants():
            if isinstance(elem.tag, basestring) and \
                namespace(elem.tag) == ns:
                elem.tag = XHTML(barename(elem.tag))
        for elem in data:
            nroot.append(elem)
        data = nroot

    fnsmap = {k:v for k, v in data.nsmap.iteritems() if v != XHTML_NS}
    fnsmap[None] = XHTML_NS
    if fnsmap != dict(data.nsmap):
        # Remove non default prefixes referring to the XHTML namespace
        data = clone_element(data, nsmap=fnsmap, in_context=False)

    data = merge_multiple_html_heads_and_bodies(data, log)
    # Ensure has a <head/>
    head = xpath(data, '/h:html/h:head')
    head = head[0] if head else None
    if head is None:
        log.warn('File %s missing <head/> element' % filename)
        head = etree.Element(XHTML('head'))
        data.insert(0, head)
        title = etree.SubElement(head, XHTML('title'))
        title.text = _('Unknown')
    elif not xpath(data, '/h:html/h:head/h:title'):
        title = etree.SubElement(head, XHTML('title'))
        title.text = _('Unknown')
    # Ensure <title> is not empty
    title = xpath(data, '/h:html/h:head/h:title')[0]
    if not title.text or not title.text.strip():
        title.text = _('Unknown')
    # Remove any encoding-specifying <meta/> elements
    for meta in META_XP(data):
        meta.getparent().remove(meta)
    meta = etree.SubElement(head, XHTML('meta'),
        attrib={'http-equiv': 'Content-Type'})
    meta.set('content', 'text/html; charset=utf-8')  # Ensure content is second attribute

    # Ensure has a <body/>
    if not xpath(data, '/h:html/h:body'):
        body = xpath(data, '//h:body')
        if body:
            body = body[0]
            body.getparent().remove(body)
            data.append(body)
        else:
            log.warn('File %s missing <body/> element' % filename)
            etree.SubElement(data, XHTML('body'))

    # Remove microsoft office markup
    r = [x for x in data.iterdescendants(etree.Element) if 'microsoft-com' in x.tag]
    for x in r:
        x.tag = XHTML('span')

    def remove_elem(a):
        p = a.getparent()
        idx = p.index(a) -1
        p.remove(a)
        if a.tail:
            if idx < 0:
                if p.text is None:
                    p.text = ''
                p.text += a.tail
            else:
                if p[idx].tail is None:
                    p[idx].tail = ''
                p[idx].tail += a.tail

    # Remove hyperlinks with no content as they cause rendering
    # artifacts in browser based renderers
    # Also remove empty <b>, <u> and <i> tags
    for a in xpath(data, '//h:a[@href]|//h:i|//h:b|//h:u'):
        if a.get('id', None) is None and a.get('name', None) is None \
                and len(a) == 0 and not a.text:
            remove_elem(a)

    # Convert <br>s with content into paragraphs as ADE can't handle
    # them
    for br in xpath(data, '//h:br'):
        if len(br) > 0 or br.text:
            br.tag = XHTML('div')

    # Remove any stray text in the <head> section and format it nicely
    data.text = '\n  '
    head = xpath(data, '//h:head')
    if head:
        head = head[0]
        head.text = '\n    '
        head.tail = '\n  '
        for child in head:
            child.tail = '\n    '
        child.tail = '\n  '

    return data
