#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from collections import defaultdict
import re

from lxml import etree

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.utils import parse_opf, pretty_print_opf, ensure_unique
from calibre.ebooks.oeb.base import OPF2_NSMAP, OPF, DC

# Utils {{{
# http://www.idpf.org/epub/vocab/package/pfx/
reserved_prefixes = {
    'dcterms':  'http://purl.org/dc/terms/',
    'epubsc':   'http://idpf.org/epub/vocab/sc/#',
    'marc':     'http://id.loc.gov/vocabulary/',
    'media':    'http://www.idpf.org/epub/vocab/overlays/#',
    'onix':     'http://www.editeur.org/ONIX/book/codelists/current.html#',
    'rendition':'http://www.idpf.org/vocab/rendition/#',
    'schema':   'http://schema.org/',
    'xsd':      'http://www.w3.org/2001/XMLSchema#',
}

_xpath_cache = {}
_re_cache = {}

def XPath(x):
    try:
        return _xpath_cache[x]
    except KeyError:
        _xpath_cache[x] = ans = etree.XPath(x, namespaces=OPF2_NSMAP)
        return ans

def regex(r, flags=0):
    try:
        return _re_cache[(r, flags)]
    except KeyError:
        _re_cache[(r, flags)] = ans = re.compile(r, flags)
        return ans

def remove_refines(e, refines):
    for x in refines[e.get('id')]:
        x.getparent().remove(x)
    refines.pop(e.get('id'), None)

def remove_element(e, refines):
    remove_refines(e, refines)
    e.getparent().remove(e)

def properties_for_id(item_id, refines):
    ans = {}
    if item_id:
        for elem in refines[item_id]:
            key = elem.get('property')
            if key:
                val = (elem.text or '').strip()
                if val:
                    ans[key] = val
    return ans

def ensure_id(root, elem):
    eid = elem.get('id')
    if not eid:
        eid = ensure_unique('id', frozenset(XPath('//*/@id')(root)))
        elem.set('id', eid)
    return eid
# }}}

# Prefixes {{{

def parse_prefixes(x):
    return {m.group(1):m.group(2) for m in re.finditer(r'(\S+): \s*(\S+)', x)}

def read_prefixes(root):
    ans = reserved_prefixes.copy()
    ans.update(parse_prefixes(root.get('prefix') or ''))
    return ans

def expand_prefix(raw, prefixes):
    return regex(r'(\S+)\s*:\s*(\S+)').sub(lambda m:(prefixes.get(m.group(1), m.group(1)) + ':' + m.group(2)), raw)
# }}}

# Refines {{{
def read_refines(root):
    ans = defaultdict(list)
    for meta in XPath('./opf:metadata/opf:meta[@refines]')(root):
        r = meta.get('refines') or ''
        if r.startswith('#'):
            ans[r[1:]].append(meta)
    return ans

def refdef(prop, val, scheme=None):
    return (prop, val, scheme)

def set_refines(elem, existing_refines, *new_refines):
    eid = ensure_id(elem.getroottree().getroot(), elem)
    remove_refines(elem, existing_refines)
    for ref in reversed(new_refines):
        prop, val, scheme = ref
        r = elem.makeelement(OPF('meta'))
        r.set('refines', '#' + eid), r.set('property', prop)
        r.text = val.strip()
        if scheme:
            r.set('scheme', scheme)
        p = elem.getparent()
        p.insert(p.index(elem)+1, r)
# }}}

# Identifiers {{{
def parse_identifier(ident, val, refines):
    idid = ident.get('id')
    refines = refines[idid]
    scheme = None
    lval = val.lower()

    def finalize(scheme, val):
        if not scheme or not val:
            return None, None
        scheme = scheme.lower()
        if scheme in ('http', 'https'):
            return None, None
        if scheme.startswith('isbn'):
            scheme = 'isbn'
        if scheme == 'isbn':
            val = val.split(':')[-1]
            val = check_isbn(val)
            if val is None:
                return None, None
        return scheme, val

    # Try the OPF 2 style opf:scheme attribute, which will be present, for
    # example, in EPUB 3 files that have had their metadata set by an
    # application that only understands EPUB 2.
    scheme = ident.get(OPF('scheme'))
    if scheme and not lval.startswith('urn:'):
        return finalize(scheme, val)

    # Technically, we should be looking for refines that define the scheme, but
    # the IDioticPF created such a bad spec that they got their own
    # examples wrong, so I cannot be bothered doing this.
    # http://www.idpf.org/epub/301/spec/epub-publications-errata/

    # Parse the value for the scheme
    if lval.startswith('urn:'):
        val = val[4:]

    prefix, rest = val.partition(':')[::2]
    return finalize(prefix, rest)

def read_identifiers(root, prefixes, refines):
    ans = defaultdict(list)
    for ident in XPath('./opf:metadata/dc:identifier')(root):
        val = (ident.text or '').strip()
        if val:
            scheme, val = parse_identifier(ident, val, refines)
            if scheme and val:
                ans[scheme].append(val)
    return ans

def set_identifiers(root, prefixes, refines, new_identifiers, force_identifiers=False):
    uid = root.get('unique-identifier')
    package_identifier = None
    for ident in XPath('./opf:metadata/dc:identifier')(root):
        if uid is not None and uid == ident.get('id'):
            package_identifier = ident
            continue
        val = (ident.text or '').strip()
        if not val:
            ident.getparent().remove(ident)
            continue
        scheme, val = parse_identifier(ident, val, refines)
        if not scheme or not val or force_identifiers or scheme in new_identifiers:
            remove_element(ident, refines)
            continue
    metadata = XPath('./opf:metadata')(root)[0]
    for scheme, val in new_identifiers.iteritems():
        ident = metadata.makeelement(DC('identifier'))
        ident.text = '%s:%s' % (scheme, val)
        if package_identifier is None:
            metadata.append(ident)
        else:
            p = package_identifier.getparent()
            p.insert(p.index(package_identifier), ident)

def set_application_id(root, refines, new_application_id=None):
    uid = root.get('unique-identifier')
    package_identifier = None
    for ident in XPath('./opf:metadata/dc:identifier')(root):
        is_package_id = uid is not None and uid == ident.get('id')
        if is_package_id:
            package_identifier = ident
        val = (ident.text or '').strip()
        if val.startswith('calibre:') and not is_package_id:
            remove_element(ident, refines)
    metadata = XPath('./opf:metadata')(root)[0]
    if new_application_id:
        ident = metadata.makeelement(DC('identifier'))
        ident.text = 'calibre:%s' % new_application_id
        if package_identifier is None:
            metadata.append(ident)
        else:
            p = package_identifier.getparent()
            p.insert(p.index(package_identifier), ident)

# }}}

# Title {{{

def find_main_title(root, refines, remove_blanks=False):
    first_title = main_title = None
    for title in XPath('./opf:metadata/dc:title')(root):
        if not title.text or not title.text.strip():
            if remove_blanks:
                remove_element(title, refines)
            continue
        if first_title is None:
            first_title = title
        props = properties_for_id(title.get('id'), refines)
        if props.get('title-type') == 'main':
            main_title = title
            break
    else:
        main_title = first_title
    return main_title

def read_title(root, prefixes, refines):
    main_title = find_main_title(root, refines)
    return None if main_title is None else main_title.text.strip()

def read_title_sort(root, prefixes, refines):
    main_title = find_main_title(root, refines)
    if main_title is not None:
        fa = properties_for_id(main_title.get('id'), refines).get('file-as')
        if fa:
            return fa
    # Look for OPF 2.0 style title_sort
    for m in XPath('./opf:metadata/opf:meta[@name="calibre:title_sort"]')(root):
        ans = m.get('content')
        if ans:
            return ans

def set_title(root, prefixes, refines, title, title_sort=None):
    main_title = find_main_title(root, refines, remove_blanks=True)
    if main_title is None:
        m = XPath('./opf:metadata')(root)[0]
        main_title = m.makeelement('dc:title')
        m.insert(0, main_title)
    main_title.text = title or None
    ts = [refdef('file-as', title_sort)] if title_sort else ()
    set_refines(main_title, refines, refdef('title-type', 'main'), *ts)

# }}}

def read_metadata(root):
    ans = Metadata(_('Unknown'), [_('Unknown')])
    prefixes, refines = read_prefixes(root), read_refines(root)
    identifiers = read_identifiers(root, prefixes, refines)
    ids = {}
    for key, vals in identifiers.iteritems():
        if key == 'calibre':
            ans.application_id = vals[0]
        elif key != 'uuid':
            ids[key] = vals[0]
    ans.set_identifiers(ids)
    ans.title = read_title(root, prefixes, refines) or ans.title
    ans.title_sort = read_title_sort(root, prefixes, refines) or ans.title_sort

    return ans

def get_metadata(stream):
    root = parse_opf(stream)
    return read_metadata(root)

def apply_metadata(root, mi, cover_prefix='', cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False):
    prefixes, refines = read_prefixes(root), read_refines(root)
    set_identifiers(root, prefixes, refines, mi.identifiers, force_identifiers=force_identifiers)
    set_title(root, prefixes, refines, mi.title, mi.title_sort)

    pretty_print_opf(root)

def set_metadata(stream, mi, cover_prefix='', cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False, add_missing_cover=True):
    root = parse_opf(stream)
    return apply_metadata(
        root, mi, cover_prefix=cover_prefix, cover_data=cover_data,
        apply_null=apply_null, update_timestamp=update_timestamp,
        force_identifiers=force_identifiers)

if __name__ == '__main__':
    import sys
    print(get_metadata(open(sys.argv[-1], 'rb')))
