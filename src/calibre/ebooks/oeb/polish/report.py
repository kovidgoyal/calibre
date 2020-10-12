#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath, os, time, types
from collections import namedtuple, defaultdict
from itertools import chain

from calibre import prepare_string_for_xml, force_unicode
from calibre.ebooks.oeb.base import XPath, xml2text
from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, OEB_FONTS
from calibre.ebooks.oeb.polish.spell import get_all_words, count_all_chars
from calibre.utils.icu import numeric_sort_key, safe_chr
from calibre.utils.imghdr import identify
from css_selectors import Select, SelectorError
from polyglot.builtins import iteritems

File = namedtuple('File', 'name dir basename size category')


def get_category(name, mt):
    category = 'misc'
    if mt.startswith('image/'):
        category = 'image'
    elif mt in OEB_FONTS:
        category = 'font'
    elif mt in OEB_STYLES:
        category = 'style'
    elif mt in OEB_DOCS:
        category = 'text'
    ext = name.rpartition('.')[-1].lower()
    if ext in {'ttf', 'otf', 'woff'}:
        # Probably wrong mimetype in the OPF
        category = 'font'
    elif ext == 'opf':
        category = 'opf'
    elif ext == 'ncx':
        category = 'toc'
    return category


def safe_size(container, name):
    try:
        return os.path.getsize(container.name_to_abspath(name))
    except Exception:
        return 0


def safe_img_data(container, name, mt):
    if 'svg' in mt:
        return 0, 0
    try:
        fmt, width, height = identify(container.name_to_abspath(name))
    except Exception:
        width = height = 0
    return width, height


def files_data(container, *args):
    for name, path in iteritems(container.name_path_map):
        yield File(name, posixpath.dirname(name), posixpath.basename(name), safe_size(container, name),
                   get_category(name, container.mime_map.get(name, '')))


Image = namedtuple('Image', 'name mime_type usage size basename id width height')

LinkLocation = namedtuple('LinkLocation', 'name line_number text_on_line')


def sort_locations(container, locations):
    nmap = {n:i for i, (n, l) in enumerate(container.spine_names)}

    def sort_key(l):
        return (nmap.get(l.name, len(nmap)), numeric_sort_key(l.name), l.line_number)
    return sorted(locations, key=sort_key)


def safe_href_to_name(container, href, base):
    try:
        return container.href_to_name(href, base)
    except ValueError:
        pass  # Absolute path on windows


def images_data(container, *args):
    image_usage = defaultdict(set)
    link_sources = OEB_STYLES | OEB_DOCS
    for name, mt in iteritems(container.mime_map):
        if mt in link_sources:
            for href, line_number, offset in container.iterlinks(name):
                target = safe_href_to_name(container, href, name)
                if target and container.exists(target):
                    mt = container.mime_map.get(target)
                    if mt and mt.startswith('image/'):
                        image_usage[target].add(LinkLocation(name, line_number, href))

    image_data = []
    for name, mt in iteritems(container.mime_map):
        if mt.startswith('image/') and container.exists(name):
            image_data.append(Image(name, mt, sort_locations(container, image_usage.get(name, set())), safe_size(container, name),
                                    posixpath.basename(name), len(image_data), *safe_img_data(container, name, mt)))
    return tuple(image_data)


def description_for_anchor(elem):
    def check(x, min_len=4):
        if x:
            x = x.strip()
            if len(x) >= min_len:
                return x[:30]

    desc = check(elem.get('title'))
    if desc is not None:
        return desc
    desc = check(elem.text)
    if desc is not None:
        return desc
    if len(elem) > 0:
        desc = check(elem[0].text)
        if desc is not None:
            return desc
    # Get full text for tags that have only a few descendants
    for i, x in enumerate(elem.iterdescendants('*')):
        if i > 5:
            break
    else:
        desc = check(xml2text(elem), min_len=1)
        if desc is not None:
            return desc


def create_anchor_map(root, pat, name):
    ans = {}
    for elem in pat(root):
        anchor = elem.get('id') or elem.get('name')
        if anchor and anchor not in ans:
            ans[anchor] = (LinkLocation(name, elem.sourceline, anchor), description_for_anchor(elem))
    return ans


Anchor = namedtuple('Anchor', 'id location text')
L = namedtuple('Link', 'location text is_external href path_ok anchor_ok anchor ok')


def Link(location, text, is_external, href, path_ok, anchor_ok, anchor):
    if is_external:
        ok = None
    else:
        ok = path_ok and anchor_ok
    return L(location, text, is_external, href, path_ok, anchor_ok, anchor, ok)


def links_data(container, *args):
    anchor_map = {}
    links = []
    anchor_pat = XPath('//*[@id or @name]')
    link_pat = XPath('//h:a[@href]')
    for name, mt in iteritems(container.mime_map):
        if mt in OEB_DOCS:
            root = container.parsed(name)
            anchor_map[name] = create_anchor_map(root, anchor_pat, name)
            for a in link_pat(root):
                href = a.get('href')
                text = description_for_anchor(a)
                if href:
                    base, frag = href.partition('#')[0::2]
                    if frag and not base:
                        dest = name
                    else:
                        dest = safe_href_to_name(container, href, name)
                    location = LinkLocation(name, a.sourceline, href)
                    links.append((base, frag, dest, location, text))
                else:
                    links.append(('', '', None, location, text))

    for base, frag, dest, location, text in links:
        if dest is None:
            link = Link(location, text, True, base, True, True, Anchor(frag, None, None))
        else:
            if dest in anchor_map:
                loc = LinkLocation(dest, None, None)
                if frag:
                    anchor = anchor_map[dest].get(frag)
                    if anchor is None:
                        link = Link(location, text, False, dest, True, False, Anchor(frag, loc, None))
                    else:
                        link = Link(location, text, False, dest, True, True, Anchor(frag, *anchor))
                else:
                    link = Link(location, text, False, dest, True, True, Anchor(None, loc, None))
            else:
                link = Link(location, text, False, dest, False, False, Anchor(frag, None, None))
        yield link


Word = namedtuple('Word', 'id word locale usage')


def words_data(container, book_locale, *args):
    count, words = get_all_words(container, book_locale, get_word_count=True)
    return (count, tuple(Word(i, word, locale, v) for i, ((word, locale), v) in enumerate(iteritems(words))))


Char = namedtuple('Char', 'id char codepoint usage count')


def chars_data(container, book_locale, *args):
    cc = count_all_chars(container, book_locale)
    nmap = {n:i for i, (n, l) in enumerate(container.spine_names)}

    def sort_key(name):
        return nmap.get(name, len(nmap)), numeric_sort_key(name)

    for i, (codepoint, usage) in enumerate(iteritems(cc.chars)):
        yield Char(i, safe_chr(codepoint), codepoint, sorted(usage, key=sort_key), cc.counter[codepoint])


CSSRule = namedtuple('CSSRule', 'selector location')
RuleLocation = namedtuple('RuleLocation', 'file_name line column')
MatchLocation = namedtuple('MatchLocation', 'tag sourceline')
CSSEntry = namedtuple('CSSEntry', 'rule count matched_files sort_key')
CSSFileMatch = namedtuple('CSSFileMatch', 'file_name locations sort_key')

ClassEntry = namedtuple('ClassEntry', 'cls num_of_matches matched_files sort_key')
ClassFileMatch = namedtuple('ClassFileMatch', 'file_name class_elements sort_key')
ClassElement = namedtuple('ClassElement', 'name line_number text_on_line tag matched_rules')


def css_data(container, book_locale, result_data, *args):
    import tinycss
    from tinycss.css21 import RuleSet, ImportRule

    def css_rules(file_name, rules, sourceline=0):
        ans = []
        for rule in rules:
            if isinstance(rule, RuleSet):
                selector = rule.selector.as_css()
                ans.append(CSSRule(selector, RuleLocation(file_name, sourceline + rule.line, rule.column)))
            elif isinstance(rule, ImportRule):
                import_name = safe_href_to_name(container, rule.uri, file_name)
                if import_name and container.exists(import_name):
                    ans.append(import_name)
            elif getattr(rule, 'rules', False):
                ans.extend(css_rules(file_name, rule.rules, sourceline))
        return ans

    parser = tinycss.make_full_parser()
    importable_sheets = {}
    html_sheets = {}
    spine_names = {name for name, is_linear in container.spine_names}
    style_path, link_path = XPath('//h:style'), XPath('//h:link/@href')

    for name, mt in iteritems(container.mime_map):
        if mt in OEB_STYLES:
            importable_sheets[name] = css_rules(name, parser.parse_stylesheet(container.raw_data(name)).rules)
        elif mt in OEB_DOCS and name in spine_names:
            html_sheets[name] = []
            for style in style_path(container.parsed(name)):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    html_sheets[name].append(
                        css_rules(name, parser.parse_stylesheet(force_unicode(style.text, 'utf-8')).rules, style.sourceline - 1))

    rule_map = defaultdict(lambda : defaultdict(list))

    def rules_in_sheet(sheet):
        for rule in sheet:
            if isinstance(rule, CSSRule):
                yield rule
            else:  # @import rule
                isheet = importable_sheets.get(rule)
                if isheet is not None:
                    for irule in rules_in_sheet(isheet):
                        yield irule

    def sheets_for_html(name, root):
        for href in link_path(root):
            tname = safe_href_to_name(container, href, name)
            sheet = importable_sheets.get(tname)
            if sheet is not None:
                yield sheet

    tt_cache = {}

    def tag_text(elem):
        ans = tt_cache.get(elem)
        if ans is None:
            tag = elem.tag.rpartition('}')[-1]
            if elem.attrib:
                attribs = ' '.join('%s="%s"' % (k, prepare_string_for_xml(elem.get(k, ''), True)) for k in elem.keys())
                return '<%s %s>' % (tag, attribs)
            ans = tt_cache[elem] = '<%s>' % tag

    def matches_for_selector(selector, select, class_map, rule):
        lsel = selector.lower()
        try:
            matches = tuple(select(selector))
        except SelectorError:
            return ()
        for elem in matches:
            for cls in elem.get('class', '').split():
                if '.' + cls.lower() in lsel:
                    class_map[cls][elem].append(rule)

        return (MatchLocation(tag_text(elem), elem.sourceline) for elem in matches)

    class_map = defaultdict(lambda : defaultdict(list))

    for name, inline_sheets in iteritems(html_sheets):
        root = container.parsed(name)
        cmap = defaultdict(lambda : defaultdict(list))
        for elem in root.xpath('//*[@class]'):
            for cls in elem.get('class', '').split():
                cmap[cls][elem] = []
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        for sheet in chain(sheets_for_html(name, root), inline_sheets):
            for rule in rules_in_sheet(sheet):
                rule_map[rule][name].extend(matches_for_selector(rule.selector, select, cmap, rule))
        for cls, elem_map in iteritems(cmap):
            class_elements = class_map[cls][name]
            for elem, usage in iteritems(elem_map):
                class_elements.append(
                    ClassElement(name, elem.sourceline, elem.get('class'), tag_text(elem), tuple(usage)))

    result_data['classes'] = ans = []
    for cls, name_map in iteritems(class_map):
        la = tuple(ClassFileMatch(name, tuple(class_elements), numeric_sort_key(name)) for name, class_elements in iteritems(name_map) if class_elements)
        num_of_matches = sum(sum(len(ce.matched_rules) for ce in cfm.class_elements) for cfm in la)
        ans.append(ClassEntry(cls, num_of_matches, la, numeric_sort_key(cls)))

    ans = []
    for rule, loc_map in iteritems(rule_map):
        la = tuple(CSSFileMatch(name, tuple(locations), numeric_sort_key(name)) for name, locations in iteritems(loc_map) if locations)
        count = sum(len(fm.locations) for fm in la)
        ans.append(CSSEntry(rule, count, la, numeric_sort_key(rule.selector)))

    return ans


def gather_data(container, book_locale):
    timing = {}
    data = {}
    for x in 'files chars images links words css'.split():
        st = time.time()
        data[x] = globals()[x + '_data'](container, book_locale, data)
        if isinstance(data[x], types.GeneratorType):
            data[x] = tuple(data[x])
        timing[x] = time.time() - st
    return data, timing
