#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath, os, time, types, re
from collections import namedtuple, defaultdict, Counter

from calibre import prepare_string_for_xml, force_unicode
from calibre.ebooks.oeb.base import XPath
from calibre.ebooks.oeb.polish.container import OEB_DOCS, OEB_STYLES, OEB_FONTS
from calibre.ebooks.oeb.polish.css import build_selector, PSEUDO_PAT, MIN_SPACE_RE
from calibre.ebooks.oeb.polish.spell import get_all_words
from calibre.utils.icu import numeric_sort_key, ord_string, safe_chr
from calibre.utils.magick.draw import identify

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
        width, height, fmt = identify(container.name_to_abspath(name))
    except Exception:
        width = height = 0
    return width, height

def files_data(container, book_locale):
    for name, path in container.name_path_map.iteritems():
        yield File(name, posixpath.dirname(name), posixpath.basename(name), safe_size(container, name),
                   get_category(name, container.mime_map.get(name, '')))

Image = namedtuple('Image', 'name mime_type usage size basename id width height')

LinkLocation = namedtuple('LinkLocation', 'name line_number text_on_line')

def sort_locations(container, locations):
    nmap = {n:i for i, (n, l) in enumerate(container.spine_names)}
    def sort_key(l):
        return (nmap.get(l.name, len(nmap)), numeric_sort_key(l.name), l.line_number)
    return sorted(locations, key=sort_key)

def images_data(container, book_locale):
    image_usage = defaultdict(set)
    link_sources = OEB_STYLES | OEB_DOCS
    for name, mt in container.mime_map.iteritems():
        if mt in link_sources:
            for href, line_number, offset in container.iterlinks(name):
                target = container.href_to_name(href, name)
                if target and container.exists(target):
                    mt = container.mime_map.get(target)
                    if mt and mt.startswith('image/'):
                        image_usage[target].add(LinkLocation(name, line_number, href))

    image_data = []
    for name, mt in container.mime_map.iteritems():
        if mt.startswith('image/') and container.exists(name):
            image_data.append(Image(name, mt, sort_locations(container, image_usage.get(name, set())), safe_size(container, name),
                                    posixpath.basename(name), len(image_data), *safe_img_data(container, name, mt)))
    return tuple(image_data)

Word = namedtuple('Word', 'id word locale usage')

def words_data(container, book_locale):
    count, words = get_all_words(container, book_locale, get_word_count=True)
    return (count, tuple(Word(i, word, locale, v) for i, ((word, locale), v) in enumerate(words.iteritems())))

Char = namedtuple('Char', 'id char codepoint usage count')

def chars_data(container, book_locale):
    chars = defaultdict(set)
    counter = Counter()
    def count(codepoint):
        counter[codepoint] += 1

    for name, is_linear in container.spine_names:
        if container.mime_map.get(name) not in OEB_DOCS:
            continue
        raw = container.raw_data(name)
        counts = Counter(ord_string(raw))
        counter.update(counts)
        for codepoint in counts:
            chars[codepoint].add(name)

    nmap = {n:i for i, (n, l) in enumerate(container.spine_names)}
    def sort_key(name):
        return nmap.get(name, len(nmap)), numeric_sort_key(name)

    for i, (codepoint, usage) in enumerate(chars.iteritems()):
        yield Char(i, safe_chr(codepoint), codepoint, sorted(usage, key=sort_key), counter[codepoint])


CSSRule = namedtuple('CSSRule', 'selector location')
RuleLocation = namedtuple('RuleLocation', 'file_name line column')
MatchLocation = namedtuple('MatchLocation', 'tag sourceline')
CSSEntry = namedtuple('CSSEntry', 'rule count matched_files sort_key')
CSSFileMatch = namedtuple('CSSFileMatch', 'file_name locations sort_key')

def css_data(container, book_locale):
    import tinycss
    from tinycss.css21 import RuleSet, ImportRule

    def css_rules(file_name, rules, sourceline=0):
        ans = []
        for rule in rules:
            if isinstance(rule, RuleSet):
                selector = rule.selector.as_css()
                ans.append(CSSRule(selector, RuleLocation(file_name, sourceline + rule.line, rule.column)))
            elif isinstance(rule, ImportRule):
                import_name = container.href_to_name(rule.uri, file_name)
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

    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES:
            importable_sheets[name] = css_rules(name, parser.parse_stylesheet(container.raw_data(name)).rules)
        elif mt in OEB_DOCS and name in spine_names:
            html_sheets[name] = []
            for style in style_path(container.parsed(name)):
                if style.get('type', 'text/css') == 'text/css' and style.text:
                    html_sheets[name].append(
                        css_rules(name, parser.parse_stylesheet(force_unicode(style.text, 'utf-8')).rules, style.sourceline - 1))

    rule_map = defaultdict(lambda : defaultdict(list))
    pseudo_pat = re.compile(PSEUDO_PAT, re.I)
    cache = {}

    def rules_in_sheet(sheet):
        for rule in sheet:
            if isinstance(rule, CSSRule):
                yield rule
            sheet = importable_sheets.get(rule)
            if sheet is not None:
                for rule in rules_in_sheet(sheet):
                    yield rule

    def sheets_for_html(name, root):
        for href in link_path(root):
            tname = container.href_to_name(href, name)
            sheet = importable_sheets.get(tname)
            if sheet is not None:
                yield sheet

    def tag_text(elem):
        tag = elem.tag.rpartition('}')[-1]
        if elem.attrib:
            attribs = ' '.join('%s="%s"' % (k, prepare_string_for_xml(elem.get(k, ''), True)) for k in elem.keys())
            return '<%s %s>' % (tag, attribs)
        return '<%s>' % tag

    def matches_for_selector(selector, root):
        selector = pseudo_pat.sub('', selector)
        selector = MIN_SPACE_RE.sub(r'\1', selector)
        try:
            xp = cache[(True, selector)]
        except KeyError:
            xp = cache[(True, selector)] = build_selector(selector)

        try:
            matches = xp(root)
        except Exception:
            return ()
        if not matches:
            try:
                xp = cache[(False, selector)]
            except KeyError:
                xp = cache[(False, selector)] = build_selector(selector, case_sensitive=False)
            try:
                matches = xp(root)
            except Exception:
                return ()
        return (MatchLocation(tag_text(elem), elem.sourceline) for elem in matches)

    for name, inline_sheets in html_sheets.iteritems():
        root = container.parsed(name)
        for sheet in list(sheets_for_html(name, root)) + inline_sheets:
            for rule in sheet:
                rule_map[rule][name].extend(matches_for_selector(rule.selector, root))

    ans = []
    for rule, loc_map in rule_map.iteritems():
        la = tuple(CSSFileMatch(name, tuple(locations), numeric_sort_key(name)) for name, locations in loc_map.iteritems() if locations)
        count = sum(len(fm.locations) for fm in la)
        ans.append(CSSEntry(rule, count, la, numeric_sort_key(rule)))

    return ans


def gather_data(container, book_locale):
    timing = {}
    data = {}
    for x in 'files chars images words css'.split():
        st = time.time()
        data[x] = globals()[x + '_data'](container, book_locale)
        if isinstance(data[x], types.GeneratorType):
            data[x] = tuple(data[x])
        timing[x] = time.time() - st
    return data, timing
