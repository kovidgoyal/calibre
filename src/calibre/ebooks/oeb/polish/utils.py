#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re, os
from bisect import bisect

from calibre import guess_type as _guess_type, replace_entities


BLOCK_TAG_NAMES = frozenset((
    'address', 'article', 'aside', 'blockquote', 'center', 'dir', 'fieldset',
    'isindex', 'menu', 'noframes', 'hgroup', 'noscript', 'pre', 'section',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'p', 'div', 'dd', 'dl', 'ul',
    'ol', 'li', 'body', 'td', 'th'))


def guess_type(x):
    return _guess_type(x)[0] or 'application/octet-stream'


# All font mimetypes seen in e-books
OEB_FONTS = frozenset({
    'font/otf',
    'font/woff',
    'font/woff2',
    'font/ttf',
    'application/x-font-ttf',
    'application/x-font-otf',
    'application/font-sfnt',
    'application/vnd.ms-opentype',
    'application/x-font-truetype',
})


def adjust_mime_for_epub(filename='', mime='', opf_version=(2, 0)):
    mime = mime or guess_type(filename)
    if mime == 'text/html':
        # epubcheck complains if the mimetype for text documents is set to text/html in EPUB 2 books. Sigh.
        return 'application/xhtml+xml'
    if mime not in OEB_FONTS:
        return mime
    if 'ttf' in mime or 'truetype' in mime:
        mime = 'font/ttf'
    elif 'otf' in mime or 'opentype' in mime:
        mime = 'font/otf'
    elif mime == 'application/font-sfnt':
        mime = 'font/otf' if filename.lower().endswith('.otf') else 'font/ttf'
    elif 'woff2' in mime:
        mime = 'font/woff2'
    elif 'woff' in mime:
        mime = 'font/woff'
    opf_version = tuple(opf_version[:2])
    if opf_version == (3, 0):
        mime = {
            'font/ttf': 'application/vnd.ms-opentype',  # this is needed by the execrable epubchek
            'font/otf': 'application/vnd.ms-opentype',
            'font/woff': 'application/font-woff'}.get(mime, mime)
    elif opf_version == (3, 1):
        mime = {
        'font/ttf': 'application/font-sfnt',
        'font/otf': 'application/font-sfnt',
        'font/woff': 'application/font-woff'}.get(mime, mime)
    elif opf_version < (3, 0):
        mime = {
            'font/ttf': 'application/x-font-truetype',
            'font/otf': 'application/vnd.ms-opentype',
            'font/woff': 'application/font-woff'}.get(mime, mime)
    return mime


def setup_css_parser_serialization(tab_width=2):
    import css_parser
    prefs = css_parser.ser.prefs
    prefs.indent = tab_width * ' '
    prefs.indentClosingBrace = False
    prefs.omitLastSemicolon = False


def actual_case_for_name(container, name):
    from calibre.utils.filenames import samefile
    if not container.exists(name):
        raise ValueError('Cannot get actual case for %s as it does not exist' % name)
    parts = name.split('/')
    base = ''
    ans = []
    for i, x in enumerate(parts):
        base = '/'.join(ans + [x])
        path = container.name_to_abspath(base)
        pdir = os.path.dirname(path)
        candidates = {os.path.join(pdir, q) for q in os.listdir(pdir)}
        if x in candidates:
            correctx = x
        else:
            for q in candidates:
                if samefile(q, path):
                    correctx = os.path.basename(q)
                    break
            else:
                raise RuntimeError('Something bad happened')
        ans.append(correctx)
    return '/'.join(ans)


def corrected_case_for_name(container, name):
    parts = name.split('/')
    ans = []
    base = ''
    for i, x in enumerate(parts):
        base = '/'.join(ans + [x])
        if container.exists(base):
            correctx = x
        else:
            try:
                candidates = {q for q in os.listdir(os.path.dirname(container.name_to_abspath(base)))}
            except OSError:
                return None  # one of the non-terminal components of name is a file instead of a directory
            for q in candidates:
                if q.lower() == x.lower():
                    correctx = q
                    break
            else:
                return None
        ans.append(correctx)
    return '/'.join(ans)


class PositionFinder:

    def __init__(self, raw):
        pat = br'\n' if isinstance(raw, bytes) else r'\n'
        self.new_lines = tuple(m.start() + 1 for m in re.finditer(pat, raw))

    def __call__(self, pos):
        lnum = bisect(self.new_lines, pos)
        try:
            offset = abs(pos - self.new_lines[lnum - 1])
        except IndexError:
            offset = pos
        return (lnum + 1, offset)


class CommentFinder:

    def __init__(self, raw, pat=r'(?s)/\*.*?\*/'):
        self.starts, self.ends = [], []
        for m in re.finditer(pat, raw):
            start, end = m.span()
            self.starts.append(start), self.ends.append(end)

    def __call__(self, offset):
        if not self.starts:
            return False
        q = bisect(self.starts, offset) - 1
        return q >= 0 and self.starts[q] <= offset <= self.ends[q]


def link_stylesheets(container, names, sheets, remove=False, mtype='text/css'):
    from calibre.ebooks.oeb.base import XPath, XHTML
    changed_names = set()
    snames = set(sheets)
    lp = XPath('//h:link[@href]')
    hp = XPath('//h:head')
    for name in names:
        root = container.parsed(name)
        if remove:
            for link in lp(root):
                if (link.get('type', mtype) or mtype) == mtype:
                    container.remove_from_xml(link)
                    changed_names.add(name)
                    container.dirty(name)
        existing = {container.href_to_name(l.get('href'), name) for l in lp(root) if (l.get('type', mtype) or mtype) == mtype}
        extra = snames - existing
        if extra:
            changed_names.add(name)
            try:
                parent = hp(root)[0]
            except (TypeError, IndexError):
                parent = root.makeelement(XHTML('head'))
                container.insert_into_xml(root, parent, index=0)
            for sheet in sheets:
                if sheet in extra:
                    container.insert_into_xml(
                        parent, parent.makeelement(XHTML('link'), rel='stylesheet', type=mtype,
                                                   href=container.name_to_href(sheet, name)))
            container.dirty(name)

    return changed_names


def lead_text(top_elem, num_words=10):
    ''' Return the leading text contained in top_elem (including descendants)
    up to a maximum of num_words words. More efficient than using
    etree.tostring(method='text') as it does not have to serialize the entire
    sub-tree rooted at top_elem.'''
    pat = re.compile(r'\s+', flags=re.UNICODE)
    words = []

    def get_text(x, attr='text'):
        ans = getattr(x, attr)
        if ans:
            words.extend(filter(None, pat.split(ans)))

    stack = [(top_elem, 'text')]
    while stack and len(words) < num_words:
        elem, attr = stack.pop()
        get_text(elem, attr)
        if attr == 'text':
            if elem is not top_elem:
                stack.append((elem, 'tail'))
            stack.extend(reversed(list((c, 'text') for c in elem.iterchildren('*'))))
    return ' '.join(words[:num_words])


def parse_css(data, fname='<string>', is_declaration=False, decode=None, log_level=None, css_preprocessor=None):
    if log_level is None:
        import logging
        log_level = logging.WARNING
    from css_parser import CSSParser, log
    from calibre.ebooks.oeb.base import _css_logger
    log.setLevel(log_level)
    log.raiseExceptions = False
    data = data or ''
    if isinstance(data, bytes):
        data = data.decode('utf-8') if decode is None else decode(data)
    if css_preprocessor is not None:
        data = css_preprocessor(data)
    parser = CSSParser(loglevel=log_level,
                        # We dont care about @import rules
                        fetcher=lambda x: (None, None), log=_css_logger)
    if is_declaration:
        data = parser.parseStyle(data, validate=False)
    else:
        data = parser.parseString(data, href=fname, validate=False)
    return data


def handle_entities(text, func):
    return func(replace_entities(text))


def apply_func_to_match_groups(match, func=icu_upper, handle_entities=handle_entities):
    '''Apply the specified function to individual groups in the match object (the result of re.search() or
    the whole match if no groups were defined. Returns the replaced string.'''
    found_groups = False
    i = 0
    parts, pos = [], match.start()
    f = lambda text:handle_entities(text, func)
    while True:
        i += 1
        try:
            start, end = match.span(i)
        except IndexError:
            break
        found_groups = True
        if start > -1:
            parts.append(match.string[pos:start])
            parts.append(f(match.string[start:end]))
            pos = end
    if not found_groups:
        return f(match.group())
    parts.append(match.string[pos:match.end()])
    return ''.join(parts)


def apply_func_to_html_text(match, func=icu_upper, handle_entities=handle_entities):
    ''' Apply the specified function only to text between HTML tag definitions. '''
    f = lambda text:handle_entities(text, func)
    parts = re.split(r'(<[^>]+>)', match.group())
    parts = (x if x.startswith('<') else f(x) for x in parts)
    return ''.join(parts)


def extract(elem):
    ''' Remove an element from the tree, keeping elem.tail '''
    p = elem.getparent()
    if p is not None:
        idx = p.index(elem)
        p.remove(elem)
        if elem.tail:
            if idx > 0:
                p[idx-1].tail = (p[idx-1].tail or '') + elem.tail
            else:
                p.text = (p.text or '') + elem.tail
