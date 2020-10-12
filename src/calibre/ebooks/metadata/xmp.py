#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, sys, copy, json
from itertools import repeat
from collections import defaultdict

from lxml import etree
from lxml.builder import ElementMaker

from calibre import prints
from calibre.ebooks.metadata import check_isbn, check_doi
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import dump_dict
from calibre.utils.date import parse_date, isoformat, now
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1
from polyglot.builtins import iteritems, string_or_bytes, filter

_xml_declaration = re.compile(r'<\?xml[^<>]+encoding\s*=\s*[\'"](.*?)[\'"][^<>]*>', re.IGNORECASE)

NS_MAP = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'pdf': 'http://ns.adobe.com/pdf/1.3/',
    'pdfx': 'http://ns.adobe.com/pdfx/1.3/',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'xmpidq': 'http://ns.adobe.com/xmp/Identifier/qual/1.0/',
    'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/',
    'xmpRights': 'http://ns.adobe.com/xap/1.0/rights/',
    'xmpBJ': 'http://ns.adobe.com/xap/1.0/bj/',
    'xmpTPg': 'http://ns.adobe.com/xap/1.0/t/pg/',
    'xmpDM': 'http://ns.adobe.com/xmp/1.0/DynamicMedia/',
    'prism': 'http://prismstandard.org/namespaces/basic/2.0/',
    'crossmark': 'http://crossref.org/crossmark/1.0/',
    'xml': 'http://www.w3.org/XML/1998/namespace',
    'x': 'adobe:ns:meta/',
    'calibre': 'http://calibre-ebook.com/xmp-namespace',
    'calibreSI': 'http://calibre-ebook.com/xmp-namespace-series-index',
    'calibreCC': 'http://calibre-ebook.com/xmp-namespace-custom-columns',
}
KNOWN_ID_SCHEMES = {'isbn', 'url', 'doi'}


def expand(name):
    prefix, name = name.partition(':')[::2]
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
        return safe_xml_fromstring(raw_bytes)
    raw = _xml_declaration.sub('', raw_bytes.decode(enc))  # lxml barfs if encoding declaration present in unicode string
    return safe_xml_fromstring(raw)


def serialize_xmp_packet(root, encoding='utf-8'):
    root.tail = '\n' + '\n'.join(repeat(' '*100, 30))  # Adobe spec recommends inserting padding at the end of the packet
    raw_bytes = etree.tostring(root, encoding=encoding, pretty_print=True, with_tail=True, method='xml')
    return b'<?xpacket begin="%s" id="W5M0MpCehiHzreSzNTczkc9d"?>\n%s\n<?xpacket end="w"?>' % ('\ufeff'.encode(encoding), raw_bytes)


def read_simple_property(elem):
    # A simple property
    if elem is not None:
        if elem.text:
            return elem.text
        return elem.get(expand('rdf:resource'), '')


def read_lang_alt(parent):
    # A text value with possible alternate values in different languages
    items = XPath('descendant::rdf:li[@xml:lang="x-default"]')(parent)
    if items:
        return items[0]
    items = XPath('descendant::rdf:li')(parent)
    if items:
        return items[0]


def read_sequence(parent):
    # A sequence or set of values (assumes simple properties in the sequence)
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
    # Get all values for sequence elements matching expr, ensuring the returned
    # list contains distinct non-null elements preserving their order.
    ans = []
    for item in XPath(expr)(root):
        ans += list(read_sequence(item))
    return list(filter(None, uniq(ans)))


def first_alt(expr, root):
    # The first element matching expr, assumes that the element contains a
    # language alternate array
    for item in XPath(expr)(root):
        q = read_simple_property(read_lang_alt(item))
        if q:
            return q


def first_simple(expr, root):
    # The value for the first occurrence of an element matching expr (assumes
    # simple property)
    for item in XPath(expr)(root):
        q = read_simple_property(item)
        if q:
            return q


def first_sequence(expr, root):
    # The first item in a sequence
    for item in XPath(expr)(root):
        for ans in read_sequence(item):
            return ans


def read_series(root):
    for item in XPath('//calibre:series')(root):
        val = XPath('descendant::rdf:value')(item)
        if val:
            series = val[0].text
            if series and series.strip():
                series_index = 1.0
                for si in XPath('descendant::calibreSI:series_index')(item):
                    try:
                        series_index = float(si.text)
                    except (TypeError, ValueError):
                        continue
                    else:
                        break
                return series, series_index
    return None, None


def read_user_metadata(mi, root):
    from calibre.utils.config import from_json
    from calibre.ebooks.metadata.book.json_codec import decode_is_multiple
    fields = set()
    for item in XPath('//calibre:custom_metadata')(root):
        for li in XPath('./rdf:Bag/rdf:li')(item):
            name = XPath('descendant::calibreCC:name')(li)
            if name:
                name = name[0].text
                if name.startswith('#') and name not in fields:
                    val = XPath('descendant::rdf:value')(li)
                    if val:
                        fm = val[0].text
                        try:
                            fm = json.loads(fm, object_hook=from_json)
                            decode_is_multiple(fm)
                            mi.set_user_metadata(name, fm)
                            fields.add(name)
                        except:
                            prints('Failed to read user metadata:', name)
                            import traceback
                            traceback.print_exc()


def read_xmp_identifers(parent):
    ''' For example:
    <rdf:li rdf:parseType="Resource"><xmpidq:Scheme>URL</xmp:idq><rdf:value>http://foo.com</rdf:value></rdf:li>
    or the longer form:
    <rdf:li><rdf:Description><xmpidq:Scheme>URL</xmp:idq><rdf:value>http://foo.com</rdf:value></rdf:Description></rdf:li>
    '''
    for li in XPath('./rdf:Bag/rdf:li')(parent):
        is_resource = li.attrib.get(expand('rdf:parseType'), None) == 'Resource'
        is_resource = is_resource or (len(li) == 1 and li[0].tag == expand('rdf:Description'))
        if not is_resource:
            yield None, li.text or ''
        value = XPath('descendant::rdf:value')(li)
        if not value:
            continue
        value = value[0].text or ''
        scheme = XPath('descendant::xmpidq:Scheme')(li)
        if not scheme:
            yield None, value
        else:
            yield scheme[0].text or '', value


def safe_parse_date(raw):
    if raw:
        try:
            return parse_date(raw)
        except Exception:
            pass


def more_recent(one, two):
    if one is None:
        return two
    if two is None:
        return one
    try:
        return max(one, two)
    except Exception:
        return one


def metadata_from_xmp_packet(raw_bytes):
    root = parse_xmp_packet(raw_bytes)
    mi = Metadata(_('Unknown'))
    title = first_alt('//dc:title', root)
    if title:
        if title.startswith(r'\376\377'):
            # corrupted XMP packet generated by Nitro PDF. See
            # https://bugs.launchpad.net/calibre/+bug/1541981
            raise ValueError('Corrupted XMP metadata packet detected, probably generated by Nitro PDF')
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
        pubdate = parse_date(first_sequence('//dc:date', root) or first_simple('//xmp:CreateDate', root), assume_utc=False)
    except:
        pass
    else:
        mi.pubdate = pubdate
    bkp = first_simple('//xmp:CreatorTool', root)
    if bkp:
        mi.book_producer = bkp
    md = safe_parse_date(first_simple('//xmp:MetadataDate', root))
    mod = safe_parse_date(first_simple('//xmp:ModifyDate', root))
    fd = more_recent(md, mod)
    if fd is not None:
        mi.metadata_date = fd
    rating = first_simple('//calibre:rating', root)
    if rating is not None:
        try:
            rating = float(rating)
            if 0 <= rating <= 10:
                mi.rating = rating
        except (ValueError, TypeError):
            pass
    series, series_index = read_series(root)
    if series:
        mi.series, mi.series_index = series, series_index
    for x in ('title_sort', 'author_sort'):
        for elem in XPath('//calibre:' + x)(root):
            val = read_simple_property(elem)
            if val:
                setattr(mi, x, val)
                break
    for x in ('author_link_map', 'user_categories'):
        val = first_simple('//calibre:'+x, root)
        if val:
            try:
                setattr(mi, x, json.loads(val))
            except:
                pass

    languages = multiple_sequences('//dc:language', root)
    if languages:
        languages = list(filter(None, map(canonicalize_lang, languages)))
        if languages:
            mi.languages = languages

    identifiers = {}
    for xmpid in XPath('//xmp:Identifier')(root):
        for scheme, value in read_xmp_identifers(xmpid):
            if scheme and value:
                identifiers[scheme.lower()] = value

    for namespace in ('prism', 'pdfx'):
        for scheme in KNOWN_ID_SCHEMES:
            if scheme not in identifiers:
                val = first_simple('//%s:%s' % (namespace, scheme), root)
                scheme = scheme.lower()
                if scheme == 'isbn':
                    val = check_isbn(val)
                elif scheme == 'doi':
                    val = check_doi(val)
                if val:
                    identifiers[scheme] = val

    # Check Dublin Core for recognizable identifier types
    for scheme, check_func in iteritems({'doi':check_doi, 'isbn':check_isbn}):
        if scheme not in identifiers:
            val = check_func(first_simple('//dc:identifier', root))
            if val:
                identifiers['doi'] = val

    if identifiers:
        mi.set_identifiers(identifiers)

    read_user_metadata(mi, root)

    return mi


def consolidate_metadata(info_mi, info):
    ''' When both the PDF Info dict and XMP metadata are present, prefer the xmp
    metadata unless the Info ModDate is never than the XMP MetadataDate. This
    is the algorithm recommended by the PDF spec. '''
    try:
        raw = info['xmp_metadata'].rstrip()
        if not raw:
            return info_mi
        xmp_mi = metadata_from_xmp_packet(raw)
    except Exception:
        import traceback
        traceback.print_exc()
        return info_mi
    info_title, info_authors, info_tags = info_mi.title or _('Unknown'), list(info_mi.authors or ()), list(info_mi.tags or ())
    info_mi.smart_update(xmp_mi, replace_metadata=True)
    prefer_info = False
    if 'ModDate' in info and hasattr(xmp_mi, 'metadata_date'):
        try:
            info_date = parse_date(info['ModDate'])
        except Exception:
            pass
        else:
            prefer_info = info_date > xmp_mi.metadata_date
    if prefer_info:
        info_mi.title, info_mi.authors, info_mi.tags = info_title, info_authors, info_tags
    else:
        # We'll use the xmp tags/authors but fallback to the info ones if the
        # xmp does not have tags/authors. smart_update() should have taken care of
        # the rest
        info_mi.authors, info_mi.tags = (info_authors if xmp_mi.is_null('authors') else xmp_mi.authors), xmp_mi.tags or info_tags
    return info_mi


def nsmap(*args):
    return {x:NS_MAP[x] for x in args}


def create_simple_property(parent, tag, value):
    e = parent.makeelement(expand(tag))
    parent.append(e)
    e.text = value


def create_alt_property(parent, tag, value):
    e = parent.makeelement(expand(tag))
    parent.append(e)
    alt = e.makeelement(expand('rdf:Alt'))
    e.append(alt)
    li = alt.makeelement(expand('rdf:li'))
    alt.append(li)
    li.set(expand('xml:lang'), 'x-default')
    li.text = value


def create_sequence_property(parent, tag, val, ordered=True):
    e = parent.makeelement(expand(tag))
    parent.append(e)
    seq = e.makeelement(expand('rdf:' + ('Seq' if ordered else 'Bag')))
    e.append(seq)
    for x in val:
        li = seq.makeelement(expand('rdf:li'))
        li.text = x
        seq.append(li)


def create_identifiers(xmp, identifiers):
    xmpid = xmp.makeelement(expand('xmp:Identifier'))
    xmp.append(xmpid)
    bag = xmpid.makeelement(expand('rdf:Bag'))
    xmpid.append(bag)
    for scheme, value in iteritems(identifiers):
        li = bag.makeelement(expand('rdf:li'))
        li.set(expand('rdf:parseType'), 'Resource')
        bag.append(li)
        s = li.makeelement(expand('xmpidq:Scheme'))
        s.text = scheme
        li.append(s)
        val = li.makeelement(expand('rdf:value'))
        li.append(val)
        val.text = value


def create_series(calibre, series, series_index):
    s = calibre.makeelement(expand('calibre:series'))
    s.set(expand('rdf:parseType'), 'Resource')
    calibre.append(s)
    val = s.makeelement(expand('rdf:value'))
    s.append(val)
    val.text = series
    try:
        series_index = float(series_index)
    except (TypeError, ValueError):
        series_index = 1.0
    si = s.makeelement(expand('calibreSI:series_index'))
    si.text = '%.2f' % series_index
    s.append(si)


def create_user_metadata(calibre, all_user_metadata):
    from calibre.utils.config import to_json
    from calibre.ebooks.metadata.book.json_codec import object_to_unicode, encode_is_multiple

    s = calibre.makeelement(expand('calibre:custom_metadata'))
    calibre.append(s)
    bag = s.makeelement(expand('rdf:Bag'))
    s.append(bag)
    for name, fm in iteritems(all_user_metadata):
        try:
            fm = copy.copy(fm)
            encode_is_multiple(fm)
            fm = object_to_unicode(fm)
            fm = json.dumps(fm, default=to_json, ensure_ascii=False)
        except:
            prints('Failed to write user metadata:', name)
            import traceback
            traceback.print_exc()
            continue
        li = bag.makeelement(expand('rdf:li'))
        li.set(expand('rdf:parseType'), 'Resource')
        bag.append(li)
        n = li.makeelement(expand('calibreCC:name'))
        li.append(n)
        n.text = name
        val = li.makeelement(expand('rdf:value'))
        val.text = fm
        li.append(val)


def metadata_to_xmp_packet(mi):
    A = ElementMaker(namespace=NS_MAP['x'], nsmap=nsmap('x'))
    R = ElementMaker(namespace=NS_MAP['rdf'], nsmap=nsmap('rdf'))
    root = A.xmpmeta(R.RDF)
    rdf = root[0]
    dc = rdf.makeelement(expand('rdf:Description'), nsmap=nsmap('dc'))
    dc.set(expand('rdf:about'), '')
    rdf.append(dc)
    for prop, tag in iteritems({'title':'dc:title', 'comments':'dc:description'}):
        val = mi.get(prop) or ''
        create_alt_property(dc, tag, val)
    for prop, (tag, ordered) in iteritems({
        'authors':('dc:creator', True), 'tags':('dc:subject', False), 'publisher':('dc:publisher', False),
    }):
        val = mi.get(prop) or ()
        if isinstance(val, string_or_bytes):
            val = [val]
        create_sequence_property(dc, tag, val, ordered)
    if not mi.is_null('pubdate'):
        create_sequence_property(dc, 'dc:date', [isoformat(mi.pubdate, as_utc=False)])  # Adobe spec recommends local time
    if not mi.is_null('languages'):
        langs = list(filter(None, map(lambda x:lang_as_iso639_1(x) or canonicalize_lang(x), mi.languages)))
        if langs:
            create_sequence_property(dc, 'dc:language', langs, ordered=False)

    xmp = rdf.makeelement(expand('rdf:Description'), nsmap=nsmap('xmp', 'xmpidq'))
    xmp.set(expand('rdf:about'), '')
    rdf.append(xmp)
    extra_ids = {}
    for x in ('prism', 'pdfx'):
        p = extra_ids[x] = rdf.makeelement(expand('rdf:Description'), nsmap=nsmap(x))
        p.set(expand('rdf:about'), '')
        rdf.append(p)

    identifiers = mi.get_identifiers()
    if identifiers:
        create_identifiers(xmp, identifiers)
        for scheme, val in iteritems(identifiers):
            if scheme in {'isbn', 'doi'}:
                for prefix, parent in iteritems(extra_ids):
                    ie = parent.makeelement(expand('%s:%s'%(prefix, scheme)))
                    ie.text = val
                    parent.append(ie)

    d = xmp.makeelement(expand('xmp:MetadataDate'))
    d.text = isoformat(now(), as_utc=False)
    xmp.append(d)

    calibre = rdf.makeelement(expand('rdf:Description'), nsmap=nsmap('calibre', 'calibreSI', 'calibreCC'))
    calibre.set(expand('rdf:about'), '')
    rdf.append(calibre)
    if not mi.is_null('rating'):
        try:
            r = float(mi.rating)
        except (TypeError, ValueError):
            pass
        else:
            create_simple_property(calibre, 'calibre:rating', '%g' % r)
    if not mi.is_null('series'):
        create_series(calibre, mi.series, mi.series_index)
    if not mi.is_null('timestamp'):
        create_simple_property(calibre, 'calibre:timestamp', isoformat(mi.timestamp, as_utc=False))
    for x in ('author_link_map', 'user_categories'):
        val = getattr(mi, x, None)
        if val:
            create_simple_property(calibre, 'calibre:'+x, dump_dict(val))

    for x in ('title_sort', 'author_sort'):
        if not mi.is_null(x):
            create_simple_property(calibre, 'calibre:'+x, getattr(mi, x))

    all_user_metadata = mi.get_all_user_metadata(True)
    if all_user_metadata:
        create_user_metadata(calibre, all_user_metadata)
    return serialize_xmp_packet(root)


def find_used_namespaces(elem):
    getns = lambda x: (x.partition('}')[0][1:] if '}' in x else None)
    ans = {getns(x) for x in list(elem.attrib) + [elem.tag]}
    for child in elem.iterchildren(etree.Element):
        ans |= find_used_namespaces(child)
    return ans


def find_preferred_prefix(namespace, elems):
    for elem in elems:
        ans = {v:k for k, v in iteritems(elem.nsmap)}.get(namespace, None)
        if ans is not None:
            return ans
        return find_preferred_prefix(namespace, elem.iterchildren(etree.Element))


def find_nsmap(elems):
    used_namespaces = set()
    for elem in elems:
        used_namespaces |= find_used_namespaces(elem)
    ans = {}
    used_namespaces -= {NS_MAP['xml'], NS_MAP['x'], None, NS_MAP['rdf']}
    rmap = {v:k for k, v in iteritems(NS_MAP)}
    i = 0
    for ns in used_namespaces:
        if ns in rmap:
            ans[rmap[ns]] = ns
        else:
            pp = find_preferred_prefix(ns, elems)
            if pp and pp not in ans:
                ans[pp] = ns
            else:
                i += 1
                ans['ns%d' % i] = ns
    return ans


def clone_into(parent, elem):
    ' Clone the element, assuming that all namespace declarations are present in parent '
    clone = parent.makeelement(elem.tag)
    parent.append(clone)
    if elem.text and not elem.text.isspace():
        clone.text = elem.text
    if elem.tail and not elem.tail.isspace():
        clone.tail = elem.tail
    clone.attrib.update(elem.attrib)
    for child in elem.iterchildren(etree.Element):
        clone_into(clone, child)


def merge_xmp_packet(old, new):
    ''' Merge metadata present in the old packet that is not present in the new
    one into the new one. Assumes the new packet was generated by
    metadata_to_xmp_packet() '''
    old, new = parse_xmp_packet(old), parse_xmp_packet(new)
    # As per the adobe spec all metadata items have to be present inside top-level rdf:Description containers
    item_xpath = XPath('//rdf:RDF/rdf:Description/*')

    # First remove all data fields that metadata_to_xmp_packet() knowns about,
    # since either they will have been set or if not present, imply they have
    # been cleared
    defined_tags = {expand(prefix + ':' + scheme) for prefix in ('prism', 'pdfx') for scheme in KNOWN_ID_SCHEMES}
    defined_tags |= {expand('dc:' + x) for x in ('identifier', 'title', 'creator', 'date', 'description', 'language', 'publisher', 'subject')}
    defined_tags |= {expand('xmp:' + x) for x in ('MetadataDate', 'Identifier')}
    # For redundancy also remove all fields explicitly set in the new packet
    defined_tags |= {x.tag for x in item_xpath(new)}
    calibrens = '{%s}' % NS_MAP['calibre']
    for elem in item_xpath(old):
        if elem.tag in defined_tags or (elem.tag and elem.tag.startswith(calibrens)):
            elem.getparent().remove(elem)

    # Group all items into groups based on their namespaces
    groups = defaultdict(list)
    for item in item_xpath(new):
        ns = item.nsmap[item.prefix]
        groups[ns].append(item)

    for item in item_xpath(old):
        ns = item.nsmap[item.prefix]
        groups[ns].append(item)

    A = ElementMaker(namespace=NS_MAP['x'], nsmap=nsmap('x'))
    R = ElementMaker(namespace=NS_MAP['rdf'], nsmap=nsmap('rdf'))
    root = A.xmpmeta(R.RDF)
    rdf = root[0]

    for namespace in sorted(groups, key=lambda x:{NS_MAP['dc']:'a', NS_MAP['xmp']:'b', NS_MAP['calibre']:'c'}.get(x, 'z'+x)):
        items = groups[namespace]
        desc = rdf.makeelement(expand('rdf:Description'), nsmap=find_nsmap(items))
        desc.set(expand('rdf:about'), '')
        rdf.append(desc)
        for item in items:
            clone_into(desc, item)

    return serialize_xmp_packet(root)


if __name__ == '__main__':
    from calibre.utils.podofo import get_xmp_metadata
    xmp_packet = get_xmp_metadata(sys.argv[-1])
    mi = metadata_from_xmp_packet(xmp_packet)
    np = metadata_to_xmp_packet(mi)
    print(merge_xmp_packet(xmp_packet, np))
