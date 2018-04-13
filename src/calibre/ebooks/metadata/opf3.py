#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import re
from collections import defaultdict, namedtuple
from functools import wraps
from future_builtins import map

from lxml import etree

from calibre import prints
from calibre.ebooks.metadata import authors_to_string, check_isbn, string_to_authors
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import (
    decode_is_multiple, encode_is_multiple, object_to_unicode
)
from calibre.ebooks.metadata.utils import (
    create_manifest_item, ensure_unique, normalize_languages, parse_opf,
    pretty_print_opf
)
from calibre.ebooks.oeb.base import DC, OPF, OPF2_NSMAP
from calibre.utils.config import from_json, to_json
from calibre.utils.date import (
    fix_only_date, is_date_undefined, isoformat, parse_date as parse_date_, utcnow,
    w3cdtf
)
from calibre.utils.iso8601 import parse_iso8601
from calibre.utils.localization import canonicalize_lang

# Utils {{{
_xpath_cache = {}
_re_cache = {}


def uniq(vals):
    ''' Remove all duplicates from vals, while preserving order.  '''
    vals = vals or ()
    seen = set()
    seen_add = seen.add
    return list(x for x in vals if x not in seen and not seen_add(x))


def dump_dict(cats):
    return json.dumps(object_to_unicode(cats or {}), ensure_ascii=False, skipkeys=True)


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


def properties_for_id_with_scheme(item_id, prefixes, refines):
    ans = defaultdict(list)
    if item_id:
        for elem in refines[item_id]:
            key = elem.get('property')
            if key:
                val = (elem.text or '').strip()
                if val:
                    scheme = elem.get('scheme') or None
                    scheme_ns = None
                    if scheme is not None:
                        p, r = scheme.partition(':')[::2]
                        if p and r:
                            ns = prefixes.get(p)
                            if ns:
                                scheme_ns = ns
                                scheme = r
                    ans[key].append((scheme_ns, scheme, val))
    return ans


def getroot(elem):
    while True:
        q = elem.getparent()
        if q is None:
            return elem
        elem = q


def ensure_id(elem):
    root = getroot(elem)
    eid = elem.get('id')
    if not eid:
        eid = ensure_unique('id', frozenset(XPath('//*/@id')(root)))
        elem.set('id', eid)
    return eid


def normalize_whitespace(text):
    if not text:
        return text
    return re.sub(r'\s+', ' ', text).strip()


def simple_text(f):
    @wraps(f)
    def wrapper(*args, **kw):
        return normalize_whitespace(f(*args, **kw))
    return wrapper


def items_with_property(root, q, prefixes=None):
    if prefixes is None:
        prefixes = read_prefixes(root)
    q = expand_prefix(q, known_prefixes).lower()
    for item in XPath("./opf:manifest/opf:item[@properties]")(root):
        for prop in (item.get('properties') or '').lower().split():
            prop = expand_prefix(prop, prefixes)
            if prop == q:
                yield item
                break

# }}}

# Prefixes {{{

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

CALIBRE_PREFIX = 'https://calibre-ebook.com'
known_prefixes = reserved_prefixes.copy()
known_prefixes['calibre'] = CALIBRE_PREFIX


def parse_prefixes(x):
    return {m.group(1):m.group(2) for m in re.finditer(r'(\S+): \s*(\S+)', x)}


def read_prefixes(root):
    ans = reserved_prefixes.copy()
    ans.update(parse_prefixes(root.get('prefix') or ''))
    return ans


def expand_prefix(raw, prefixes):
    return regex(r'(\S+)\s*:\s*(\S+)').sub(lambda m:(prefixes.get(m.group(1), m.group(1)) + ':' + m.group(2)), raw or '')


def ensure_prefix(root, prefixes, prefix, value=None):
    if prefixes is None:
        prefixes = read_prefixes(root)
    prefixes[prefix] = value or reserved_prefixes[prefix]
    prefixes = {k:v for k, v in prefixes.iteritems() if reserved_prefixes.get(k) != v}
    if prefixes:
        root.set('prefix', ' '.join('%s: %s' % (k, v) for k, v in prefixes.iteritems()))
    else:
        root.attrib.pop('prefix', None)

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
    eid = ensure_id(elem)
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


def identifier_writer(name):
    def writer(root, prefixes, refines, ival=None):
        uid = root.get('unique-identifier')
        package_identifier = None
        for ident in XPath('./opf:metadata/dc:identifier')(root):
            is_package_id = uid is not None and uid == ident.get('id')
            if is_package_id:
                package_identifier = ident
            val = (ident.text or '').strip()
            if (val.startswith(name + ':') or ident.get(OPF('scheme')) == name) and not is_package_id:
                remove_element(ident, refines)
        metadata = XPath('./opf:metadata')(root)[0]
        if ival:
            ident = metadata.makeelement(DC('identifier'))
            ident.text = '%s:%s' % (name, ival)
            if package_identifier is None:
                metadata.append(ident)
            else:
                p = package_identifier.getparent()
                p.insert(p.index(package_identifier), ident)
    return writer


set_application_id = identifier_writer('calibre')
set_uuid = identifier_writer('uuid')

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


@simple_text
def read_title(root, prefixes, refines):
    main_title = find_main_title(root, refines)
    return None if main_title is None else main_title.text.strip()


@simple_text
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
    for m in XPath('./opf:metadata/opf:meta[@name="calibre:title_sort"]')(root):
        remove_element(m, refines)

# }}}

# Languages {{{


def read_languages(root, prefixes, refines):
    ans = []
    for lang in XPath('./opf:metadata/dc:language')(root):
        val = canonicalize_lang((lang.text or '').strip())
        if val and val not in ans and val != 'und':
            ans.append(val)
    return uniq(ans)


def set_languages(root, prefixes, refines, languages):
    opf_languages = []
    for lang in XPath('./opf:metadata/dc:language')(root):
        remove_element(lang, refines)
        val = (lang.text or '').strip()
        if val:
            opf_languages.append(val)
    languages = filter(lambda x: x and x != 'und', normalize_languages(opf_languages, languages))
    if not languages:
        # EPUB spec says dc:language is required
        languages = ['und']
    metadata = XPath('./opf:metadata')(root)[0]
    for lang in uniq(languages):
        l = metadata.makeelement(DC('language'))
        l.text = lang
        metadata.append(l)
# }}}

# Creator/Contributor {{{


Author = namedtuple('Author', 'name sort')


def is_relators_role(props, q):
    for role in props.get('role'):
        if role:
            scheme_ns, scheme, role = role
            return role.lower() == q and (scheme_ns is None or (scheme_ns, scheme) == (reserved_prefixes['marc'], 'relators'))
    return False


def read_authors(root, prefixes, refines):
    roled_authors, unroled_authors = [], []

    def author(item, props, val):
        aus = None
        file_as = props.get('file-as')
        if file_as:
            aus = file_as[-1][-1]
        else:
            aus = item.get(OPF('file-as')) or None
        return Author(normalize_whitespace(val), normalize_whitespace(aus))

    for item in XPath('./opf:metadata/dc:creator')(root):
        val = (item.text or '').strip()
        if val:
            props = properties_for_id_with_scheme(item.get('id'), prefixes, refines)
            role = props.get('role')
            opf_role = item.get(OPF('role'))
            if role:
                if is_relators_role(props, 'aut'):
                    roled_authors.append(author(item, props, val))
            elif opf_role:
                if opf_role.lower() == 'aut':
                    roled_authors.append(author(item, props, val))
            else:
                unroled_authors.append(author(item, props, val))

    return uniq(roled_authors or unroled_authors)


def set_authors(root, prefixes, refines, authors):
    ensure_prefix(root, prefixes, 'marc')
    for item in XPath('./opf:metadata/dc:creator')(root):
        props = properties_for_id_with_scheme(item.get('id'), prefixes, refines)
        opf_role = item.get(OPF('role'))
        if (opf_role and opf_role.lower() != 'aut') or (props.get('role') and not is_relators_role(props, 'aut')):
            continue
        remove_element(item, refines)
    metadata = XPath('./opf:metadata')(root)[0]
    for author in authors:
        if author.name:
            a = metadata.makeelement(DC('creator'))
            aid = ensure_id(a)
            a.text = author.name
            metadata.append(a)
            m = metadata.makeelement(OPF('meta'), attrib={'refines':'#'+aid, 'property':'role', 'scheme':'marc:relators'})
            m.text = 'aut'
            metadata.append(m)
            if author.sort:
                m = metadata.makeelement(OPF('meta'), attrib={'refines':'#'+aid, 'property':'file-as'})
                m.text = author.sort
                metadata.append(m)


def read_book_producers(root, prefixes, refines):
    ans = []
    for item in XPath('./opf:metadata/dc:contributor')(root):
        val = (item.text or '').strip()
        if val:
            props = properties_for_id_with_scheme(item.get('id'), prefixes, refines)
            role = props.get('role')
            opf_role = item.get(OPF('role'))
            if role:
                if is_relators_role(props, 'bkp'):
                    ans.append(normalize_whitespace(val))
            elif opf_role and opf_role.lower() == 'bkp':
                ans.append(normalize_whitespace(val))
    return ans


def set_book_producers(root, prefixes, refines, producers):
    for item in XPath('./opf:metadata/dc:contributor')(root):
        props = properties_for_id_with_scheme(item.get('id'), prefixes, refines)
        opf_role = item.get(OPF('role'))
        if (opf_role and opf_role.lower() != 'bkp') or (props.get('role') and not is_relators_role(props, 'bkp')):
            continue
        remove_element(item, refines)
    metadata = XPath('./opf:metadata')(root)[0]
    for bkp in producers:
        if bkp:
            a = metadata.makeelement(DC('contributor'))
            aid = ensure_id(a)
            a.text = bkp
            metadata.append(a)
            m = metadata.makeelement(OPF('meta'), attrib={'refines':'#'+aid, 'property':'role', 'scheme':'marc:relators'})
            m.text = 'bkp'
            metadata.append(m)
# }}}

# Dates {{{


def parse_date(raw, is_w3cdtf=False):
    raw = raw.strip()
    if is_w3cdtf:
        ans = parse_iso8601(raw, assume_utc=True)
        if 'T' not in raw and ' ' not in raw:
            ans = fix_only_date(ans)
    else:
        ans = parse_date_(raw, assume_utc=True)
        if ' ' not in raw and 'T' not in raw and (ans.hour, ans.minute, ans.second) == (0, 0, 0):
            ans = fix_only_date(ans)
    return ans


def read_pubdate(root, prefixes, refines):
    for date in XPath('./opf:metadata/dc:date')(root):
        val = (date.text or '').strip()
        if val:
            try:
                return parse_date(val)
            except Exception:
                continue


def set_pubdate(root, prefixes, refines, val):
    for date in XPath('./opf:metadata/dc:date')(root):
        remove_element(date, refines)
    if not is_date_undefined(val):
        val = isoformat(val)
        m = XPath('./opf:metadata')(root)[0]
        d = m.makeelement(DC('date'))
        d.text = val
        m.append(d)


def read_timestamp(root, prefixes, refines):
    pq = '%s:timestamp' % CALIBRE_PREFIX
    sq = '%s:w3cdtf' % reserved_prefixes['dcterms']
    for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
        val = (meta.text or '').strip()
        if val:
            prop = expand_prefix(meta.get('property'), prefixes)
            if prop.lower() == pq:
                scheme = expand_prefix(meta.get('scheme'), prefixes).lower()
                try:
                    return parse_date(val, is_w3cdtf=scheme == sq)
                except Exception:
                    continue
    for meta in XPath('./opf:metadata/opf:meta[@name="calibre:timestamp"]')(root):
        val = meta.get('content')
        if val:
            try:
                return parse_date(val, is_w3cdtf=True)
            except Exception:
                continue


def create_timestamp(root, prefixes, m, val):
    if not is_date_undefined(val):
        ensure_prefix(root, prefixes, 'calibre', CALIBRE_PREFIX)
        ensure_prefix(root, prefixes, 'dcterms')
        val = w3cdtf(val)
        d = m.makeelement(OPF('meta'), attrib={'property':'calibre:timestamp', 'scheme':'dcterms:W3CDTF'})
        d.text = val
        m.append(d)


def set_timestamp(root, prefixes, refines, val):
    pq = '%s:timestamp' % CALIBRE_PREFIX
    for meta in XPath('./opf:metadata/opf:meta')(root):
        prop = expand_prefix(meta.get('property'), prefixes)
        if prop.lower() == pq or meta.get('name') == 'calibre:timestamp':
            remove_element(meta, refines)
    create_timestamp(root, prefixes, XPath('./opf:metadata')(root)[0], val)


def read_last_modified(root, prefixes, refines):
    pq = '%s:modified' % reserved_prefixes['dcterms']
    sq = '%s:w3cdtf' % reserved_prefixes['dcterms']
    for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
        val = (meta.text or '').strip()
        if val:
            prop = expand_prefix(meta.get('property'), prefixes)
            if prop.lower() == pq:
                scheme = expand_prefix(meta.get('scheme'), prefixes).lower()
                try:
                    return parse_date(val, is_w3cdtf=scheme == sq)
                except Exception:
                    continue

def set_last_modified(root, prefixes, refines, val=None):
    pq = '%s:modified' % reserved_prefixes['dcterms']
    sq = '%s:w3cdtf' % reserved_prefixes['dcterms']
    val = w3cdtf(val or utcnow())
    for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
        prop = expand_prefix(meta.get('property'), prefixes)
        if prop.lower() == pq:
            iid = meta.get('id')
            if not iid or not refines[iid]:
                break
    else:
        ensure_prefix(root, prefixes, 'dcterms')
        m = XPath('./opf:metadata')(root)[0]
        meta = m.makeelement(OPF('meta'), attrib={'property':'dcterms:modified', 'scheme':'dcterms:W3CDTF'})
        m.append(meta)
    meta.text = val
# }}}

# Comments {{{


def read_comments(root, prefixes, refines):
    ans = ''
    for dc in XPath('./opf:metadata/dc:description')(root):
        if dc.text:
            ans += '\n' + dc.text.strip()
    return ans.strip()


def set_comments(root, prefixes, refines, val):
    for dc in XPath('./opf:metadata/dc:description')(root):
        remove_element(dc, refines)
    m = XPath('./opf:metadata')(root)[0]
    if val:
        val = val.strip()
        if val:
            c = m.makeelement(DC('description'))
            c.text = val
            m.append(c)
# }}}

# Publisher {{{


@simple_text
def read_publisher(root, prefixes, refines):
    for dc in XPath('./opf:metadata/dc:publisher')(root):
        if dc.text:
            return dc.text


def set_publisher(root, prefixes, refines, val):
    for dc in XPath('./opf:metadata/dc:publisher')(root):
        remove_element(dc, refines)
    m = XPath('./opf:metadata')(root)[0]
    if val:
        val = val.strip()
        if val:
            c = m.makeelement(DC('publisher'))
            c.text = normalize_whitespace(val)
            m.append(c)
# }}}

# Tags {{{


def read_tags(root, prefixes, refines):
    ans = []
    for dc in XPath('./opf:metadata/dc:subject')(root):
        if dc.text:
            ans.extend(map(normalize_whitespace, dc.text.split(',')))
    return uniq(filter(None, ans))


def set_tags(root, prefixes, refines, val):
    for dc in XPath('./opf:metadata/dc:subject')(root):
        remove_element(dc, refines)
    m = XPath('./opf:metadata')(root)[0]
    if val:
        val = uniq(filter(None, val))
        for x in val:
            c = m.makeelement(DC('subject'))
            c.text = normalize_whitespace(x)
            if c.text:
                m.append(c)
# }}}

# Rating {{{


def read_rating(root, prefixes, refines):
    pq = '%s:rating' % CALIBRE_PREFIX
    for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
        val = (meta.text or '').strip()
        if val:
            prop = expand_prefix(meta.get('property'), prefixes)
            if prop.lower() == pq:
                try:
                    return float(val)
                except Exception:
                    continue
    for meta in XPath('./opf:metadata/opf:meta[@name="calibre:rating"]')(root):
        val = meta.get('content')
        if val:
            try:
                return float(val)
            except Exception:
                continue


def create_rating(root, prefixes, val):
    ensure_prefix(root, prefixes, 'calibre', CALIBRE_PREFIX)
    m = XPath('./opf:metadata')(root)[0]
    d = m.makeelement(OPF('meta'), attrib={'property':'calibre:rating'})
    d.text = val
    m.append(d)


def set_rating(root, prefixes, refines, val):
    pq = '%s:rating' % CALIBRE_PREFIX
    for meta in XPath('./opf:metadata/opf:meta[@name="calibre:rating"]')(root):
        remove_element(meta, refines)
    for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
        prop = expand_prefix(meta.get('property'), prefixes)
        if prop.lower() == pq:
            remove_element(meta, refines)
    if val:
        create_rating(root, prefixes, '%.2g' % val)
# }}}

# Series {{{


def read_series(root, prefixes, refines):
    series_index = 1.0
    for meta in XPath('./opf:metadata/opf:meta[@property="belongs-to-collection" and @id]')(root):
        val = (meta.text or '').strip()
        if val:
            props = properties_for_id(meta.get('id'), refines)
            if props.get('collection-type') == 'series':
                try:
                    series_index = float(props.get('group-position').strip())
                except Exception:
                    pass
                return normalize_whitespace(val), series_index
    for si in XPath('./opf:metadata/opf:meta[@name="calibre:series_index"]/@content')(root):
        try:
            series_index = float(si)
            break
        except:
            pass
    for s in XPath('./opf:metadata/opf:meta[@name="calibre:series"]/@content')(root):
        s = normalize_whitespace(s)
        if s:
            return s, series_index
    return None, series_index


def create_series(root, refines, series, series_index):
    m = XPath('./opf:metadata')(root)[0]
    d = m.makeelement(OPF('meta'), attrib={'property':'belongs-to-collection'})
    d.text = series
    m.append(d)
    set_refines(d, refines, refdef('collection-type', 'series'), refdef('group-position', series_index))


def set_series(root, prefixes, refines, series, series_index):
    for meta in XPath('./opf:metadata/opf:meta[@name="calibre:series" or @name="calibre:series_index"]')(root):
        remove_element(meta, refines)
    for meta in XPath('./opf:metadata/opf:meta[@property="belongs-to-collection"]')(root):
        remove_element(meta, refines)
    if series:
        create_series(root, refines, series, '%.2g' % series_index)
# }}}

# User metadata {{{


def dict_reader(name, load=json.loads, try2=True):
    pq = '%s:%s' % (CALIBRE_PREFIX, name)

    def reader(root, prefixes, refines):
        for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
            val = (meta.text or '').strip()
            if val:
                prop = expand_prefix(meta.get('property'), prefixes)
                if prop.lower() == pq:
                    try:
                        ans = load(val)
                        if isinstance(ans, dict):
                            return ans
                    except Exception:
                        continue
        if try2:
            for meta in XPath('./opf:metadata/opf:meta[@name="calibre:%s"]' % name)(root):
                val = meta.get('content')
                if val:
                    try:
                        ans = load(val)
                        if isinstance(ans, dict):
                            return ans
                    except Exception:
                        continue
    return reader


read_user_categories = dict_reader('user_categories')
read_author_link_map = dict_reader('author_link_map')


def dict_writer(name, serialize=dump_dict, remove2=True):
    pq = '%s:%s' % (CALIBRE_PREFIX, name)

    def writer(root, prefixes, refines, val):
        if remove2:
            for meta in XPath('./opf:metadata/opf:meta[@name="calibre:%s"]' % name)(root):
                remove_element(meta, refines)
        for meta in XPath('./opf:metadata/opf:meta[@property]')(root):
            prop = expand_prefix(meta.get('property'), prefixes)
            if prop.lower() == pq:
                remove_element(meta, refines)
        if val:
            ensure_prefix(root, prefixes, 'calibre', CALIBRE_PREFIX)
            m = XPath('./opf:metadata')(root)[0]
            d = m.makeelement(OPF('meta'), attrib={'property':'calibre:%s' % name})
            d.text = serialize(val)
            m.append(d)
    return writer


set_user_categories = dict_writer('user_categories')
set_author_link_map = dict_writer('author_link_map')


def deserialize_user_metadata(val):
    val = json.loads(val, object_hook=from_json)
    ans = {}
    for name, fm in val.iteritems():
        decode_is_multiple(fm)
        ans[name] = fm
    return ans


read_user_metadata3 = dict_reader('user_metadata', load=deserialize_user_metadata, try2=False)


def read_user_metadata2(root, remove_tags=False):
    ans = {}
    for meta in XPath('./opf:metadata/opf:meta[starts-with(@name, "calibre:user_metadata:")]')(root):
        name = meta.get('name')
        name = ':'.join(name.split(':')[2:])
        if not name or not name.startswith('#'):
            continue
        fm = meta.get('content')
        if remove_tags:
            meta.getparent().remove(meta)
        try:
            fm = json.loads(fm, object_hook=from_json)
            decode_is_multiple(fm)
            ans[name] = fm
        except Exception:
            prints('Failed to read user metadata:', name)
            import traceback
            traceback.print_exc()
            continue
    return ans


def read_user_metadata(root, prefixes, refines):
    return read_user_metadata3(root, prefixes, refines) or read_user_metadata2(root)


def serialize_user_metadata(val):
    return json.dumps(object_to_unicode(val), ensure_ascii=False, default=to_json, indent=2, sort_keys=True)


set_user_metadata3 = dict_writer('user_metadata', serialize=serialize_user_metadata, remove2=False)


def set_user_metadata(root, prefixes, refines, val):
    for meta in XPath('./opf:metadata/opf:meta[starts-with(@name, "calibre:user_metadata:")]')(root):
        remove_element(meta, refines)
    if val:
        nval = {}
        for name, fm in val.items():
            fm = fm.copy()
            encode_is_multiple(fm)
            nval[name] = fm
        set_user_metadata3(root, prefixes, refines, nval)

# }}}

# Covers {{{


def read_raster_cover(root, prefixes, refines):

    def get_href(item):
        mt = item.get('media-type')
        if mt and 'xml' not in mt and 'html' not in mt:
            href = item.get('href')
            if href:
                return href

    for item in items_with_property(root, 'cover-image', prefixes):
        href = get_href(item)
        if href:
            return href

    for item_id in XPath('./opf:metadata/opf:meta[@name="cover"]/@content')(root):
        for item in XPath('./opf:manifest/opf:item[@id and @href and @media-type]')(root):
            if item.get('id') == item_id:
                href = get_href(item)
                if href:
                    return href


def ensure_is_only_raster_cover(root, prefixes, refines, raster_cover_item_href):
    for item in XPath('./opf:metadata/opf:meta[@name="cover"]')(root):
        remove_element(item, refines)
    for item in items_with_property(root, 'cover-image', prefixes):
        prop = normalize_whitespace(item.get('properties').replace('cover-image', ''))
        if prop:
            item.set('properties', prop)
        else:
            del item.attrib['properties']
    for item in XPath('./opf:manifest/opf:item')(root):
        if item.get('href') == raster_cover_item_href:
            item.set('properties', normalize_whitespace((item.get('properties') or '') + ' cover-image'))

# }}}

# Reading/setting Metadata objects {{{


def first_spine_item(root, prefixes, refines):
    for i in XPath('./opf:spine/opf:itemref/@idref')(root):
        for item in XPath('./opf:manifest/opf:item')(root):
            if item.get('id') == i:
                return item.get('href') or None


def set_last_modified_in_opf(root):
    prefixes, refines = read_prefixes(root), read_refines(root)
    set_last_modified(root, prefixes, refines)


def read_metadata(root, ver=None, return_extra_data=False):
    ans = Metadata(_('Unknown'), [_('Unknown')])
    prefixes, refines = read_prefixes(root), read_refines(root)
    identifiers = read_identifiers(root, prefixes, refines)
    ids = {}
    for key, vals in identifiers.iteritems():
        if key == 'calibre':
            ans.application_id = vals[0]
        elif key == 'uuid':
            ans.uuid = vals[0]
        else:
            ids[key] = vals[0]
    ans.set_identifiers(ids)
    ans.title = read_title(root, prefixes, refines) or ans.title
    ans.title_sort = read_title_sort(root, prefixes, refines) or ans.title_sort
    ans.languages = read_languages(root, prefixes, refines) or ans.languages
    auts, aus = [], []
    for a in read_authors(root, prefixes, refines):
        auts.append(a.name), aus.append(a.sort)
    ans.authors = auts or ans.authors
    ans.author_sort = authors_to_string(aus) or ans.author_sort
    bkp = read_book_producers(root, prefixes, refines)
    if bkp:
        if bkp[0]:
            ans.book_producer = bkp[0]
    pd = read_pubdate(root, prefixes, refines)
    if not is_date_undefined(pd):
        ans.pubdate = pd
    ts = read_timestamp(root, prefixes, refines)
    if not is_date_undefined(ts):
        ans.timestamp = ts
    lm = read_last_modified(root, prefixes, refines)
    if not is_date_undefined(lm):
        ans.last_modified = lm
    ans.comments = read_comments(root, prefixes, refines) or ans.comments
    ans.publisher = read_publisher(root, prefixes, refines) or ans.publisher
    ans.tags = read_tags(root, prefixes, refines) or ans.tags
    ans.rating = read_rating(root, prefixes, refines) or ans.rating
    s, si = read_series(root, prefixes, refines)
    if s:
        ans.series, ans.series_index = s, si
    ans.author_link_map = read_author_link_map(root, prefixes, refines) or ans.author_link_map
    ans.user_categories = read_user_categories(root, prefixes, refines) or ans.user_categories
    for name, fm in (read_user_metadata(root, prefixes, refines) or {}).iteritems():
        ans.set_user_metadata(name, fm)
    if return_extra_data:
        ans = ans, ver, read_raster_cover(root, prefixes, refines), first_spine_item(root, prefixes, refines)
    return ans


def get_metadata(stream):
    root = parse_opf(stream)
    return read_metadata(root)


def apply_metadata(root, mi, cover_prefix='', cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False, add_missing_cover=True):
    prefixes, refines = read_prefixes(root), read_refines(root)
    current_mi = read_metadata(root)
    if apply_null:
        def ok(x):
            return True
    else:
        def ok(x):
            return not mi.is_null(x)
    if ok('identifiers'):
        set_identifiers(root, prefixes, refines, mi.identifiers, force_identifiers=force_identifiers)
    if ok('title'):
        set_title(root, prefixes, refines, mi.title, mi.title_sort)
    if ok('languages'):
        set_languages(root, prefixes, refines, mi.languages)
    if ok('book_producer'):
        set_book_producers(root, prefixes, refines, (mi.book_producer,))
    aus = string_to_authors(mi.author_sort or '')
    authors = []
    for i, aut in enumerate(mi.authors):
        authors.append(Author(aut, aus[i] if i < len(aus) else None))
    if authors or apply_null:
        set_authors(root, prefixes, refines, authors)
    if ok('pubdate'):
        set_pubdate(root, prefixes, refines, mi.pubdate)
    if update_timestamp and mi.timestamp is not None:
        set_timestamp(root, prefixes, refines, mi.timestamp)
    if ok('comments'):
        set_comments(root, prefixes, refines, mi.comments)
    if ok('publisher'):
        set_publisher(root, prefixes, refines, mi.publisher)
    if ok('tags'):
        set_tags(root, prefixes, refines, mi.tags)
    if ok('rating') and mi.rating > 0.1:
        set_rating(root, prefixes, refines, mi.rating)
    if ok('series'):
        set_series(root, prefixes, refines, mi.series, mi.series_index or 1)
    if ok('author_link_map'):
        set_author_link_map(root, prefixes, refines, getattr(mi, 'author_link_map', None))
    if ok('user_categories'):
        set_user_categories(root, prefixes, refines, getattr(mi, 'user_categories', None))
    # We ignore apply_null for the next two to match the behavior with opf2.py
    if mi.application_id:
        set_application_id(root, prefixes, refines, mi.application_id)
    if mi.uuid:
        set_uuid(root, prefixes, refines, mi.uuid)
    new_user_metadata, current_user_metadata = mi.get_all_user_metadata(True), current_mi.get_all_user_metadata(True)
    missing = object()
    for key in tuple(new_user_metadata):
        meta = new_user_metadata.get(key)
        if meta is None:
            if apply_null:
                new_user_metadata[key] = None
            continue
        dt = meta.get('datatype')
        if dt == 'text' and meta.get('is_multiple'):
            val = mi.get(key, [])
            if val or apply_null:
                current_user_metadata[key] = meta
        elif dt in {'int', 'float', 'bool'}:
            val = mi.get(key, missing)
            if val is missing:
                if apply_null:
                    current_user_metadata[key] = meta
            elif apply_null or val is not None:
                current_user_metadata[key] = meta
        elif apply_null or not mi.is_null(key):
            current_user_metadata[key] = meta

    set_user_metadata(root, prefixes, refines, current_user_metadata)
    raster_cover = read_raster_cover(root, prefixes, refines)
    if not raster_cover and cover_data and add_missing_cover:
        if cover_prefix and not cover_prefix.endswith('/'):
            cover_prefix += '/'
        name = cover_prefix + 'cover.jpg'
        i = create_manifest_item(root, name, 'cover')
        if i is not None:
            ensure_is_only_raster_cover(root, prefixes, refines, name)
            raster_cover = name

    pretty_print_opf(root)
    return raster_cover


def set_metadata(stream, mi, cover_prefix='', cover_data=None, apply_null=False, update_timestamp=False, force_identifiers=False, add_missing_cover=True):
    root = parse_opf(stream)
    return apply_metadata(
        root, mi, cover_prefix=cover_prefix, cover_data=cover_data,
        apply_null=apply_null, update_timestamp=update_timestamp,
        force_identifiers=force_identifiers)
# }}}


if __name__ == '__main__':
    import sys
    print(get_metadata(open(sys.argv[-1], 'rb')))
