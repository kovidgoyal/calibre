#!/usr/bin/env python

import re
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict, Unpack, cast

from lxml import etree
from lxml.html import tostring as htostring

from calibre.ebooks.readability.cleaners import clean_attributes, html_cleaner
from calibre.ebooks.readability.htmls import build_doc, get_body, get_title, shorten_title
from calibre.utils.xml_parse import document_fromstring, fragment_fromstring
from polyglot.builtins import reraise

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lxml.html import HtmlElement

    from calibre.utils.config import OptionParser
    from calibre.utils.logging import Log


class ReadabilityOptions(TypedDict, total=False):
    url: str | None
    keep_elements: str | None
    debug: bool
    retry_length: int | None
    min_text_length: int | None


class Candidate(TypedDict):
    content_score: float
    elem: HtmlElement


def tounicode(tree_or_node: HtmlElement, **kwargs: object) -> str:
    kwargs['encoding'] = str
    return htostring(tree_or_node, **kwargs)  # ty: ignore[no-matching-overload] kwargs are passed through to lxml


REGEXES = {
    'unlikelyCandidatesRe': re.compile(
        r'combx|comment|community|disqus|extra|foot|header|menu|remark|rss|shoutbox|sidebar|sponsor|ad-break|agegate|pagination|pager|popup|tweet|twitter',
        re.I,
    ),
    'okMaybeItsACandidateRe': re.compile(r'and|article|body|column|main|shadow', re.I),
    'positiveRe': re.compile(r'article|body|content|entry|hentry|main|page|pagination|post|text|blog|story', re.I),
    'negativeRe': re.compile(
        r'combx|comment|com-|contact|foot|footer|footnote|masthead|media|meta|outbrain|promo|related|scroll|shoutbox|sidebar|sponsor|shopping|tags|tool|widget',
        re.I,
    ),
    'divToPElementsRe': re.compile(r'<(a|blockquote|dl|div|img|ol|p|pre|table|ul)', re.I),
    # 'replaceBrsRe': re.compile(r'(<br[^>]*>[ \n\r\t]*){2,}',re.I),
    # 'replaceFontsRe': re.compile(r'<(/?)font[^>]*>',re.I),
    # 'trimRe': re.compile(r'^\s+|\s+$/'),
    # 'normalizeRe': re.compile(r'\s{2,}/'),
    # 'killBreaksRe': re.compile(r'(<br\s*/?>(\s|&nbsp;?)*){1,}/'),
    # 'videoRe': re.compile(r'http://(www\.)?(youtube|vimeo)\.com', re.I),
    # skipFootnoteLink:    /^\s*(\[?[a-z0-9]{1,2}\]?|^|edit|citation needed)\s*$/i,
}


def describe(node: HtmlElement, depth: int = 1) -> str:
    if not hasattr(node, 'tag'):
        return f'[{type(node)}]'
    name = node.tag
    assert isinstance(name, str)  # comments/PIs would have failed at name[:4] below anyway
    if nid := node.get('id', ''):
        name += '#' + nid
    if ncls := node.get('class', ''):
        name += '.' + ncls.replace(' ', '.')
    if name[:4] in ['div#', 'div.']:
        name = name[3:]
    if depth and (parent := node.getparent()) is not None:
        return name + ' - ' + describe(parent, depth - 1)
    return name


def to_int(x: str | None) -> int | None:
    if not x:
        return None
    x = x.strip()
    if x.endswith('px'):
        return int(x[:-2])
    if x.endswith('em'):
        return int(x[:-2]) * 12
    return int(x)


def clean(text: str) -> str:
    text = re.sub(r'\s*\n\s*', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def text_content(elem: HtmlElement) -> str:
    if hasattr(elem, 'text_content'):
        return elem.text_content()
    return etree.tostring(elem, method='text', encoding='unicode')


def text_length(i: HtmlElement) -> int:
    return len(clean(text_content(i) or ''))


class Unparsable(ValueError):
    pass


class Document:
    TEXT_LENGTH_THRESHOLD = 25
    RETRY_LENGTH = 250

    def __init__(self, input: str | bytes, log: Log, **options: Unpack[ReadabilityOptions]) -> None:
        self.input = input
        # missing options read as None
        self.options = cast('ReadabilityOptions', defaultdict(lambda: None))
        self.options.update(options)
        self.html: HtmlElement | None = None
        self.log = log
        self.keep_elements: set[HtmlElement] = set()

    def _html(self, force: bool = False) -> HtmlElement:
        if force or self.html is None:
            self.html = self._parse(self.input)
            path = self.options['keep_elements']
            if path is not None:
                self.keep_elements = set(self.html.xpath(path))

        return self.html

    def _parse(self, input: str | bytes) -> HtmlElement:
        doc = build_doc(input)
        doc = html_cleaner.clean_html(doc)
        base_href = self.options['url']
        if base_href:
            doc.make_links_absolute(base_href, resolve_base_href=True)
        else:
            doc.resolve_base_href()
        return doc

    def content(self) -> str:
        return get_body(self._html(True))

    def title(self) -> str:
        return get_title(self._html(True))

    def short_title(self) -> str:
        return shorten_title(self._html(True))

    def summary(self) -> str:
        try:
            ruthless = True
            while True:
                self._html(True)
                assert self.html is not None

                for i in self.tags(self.html, 'script', 'style'):
                    i.drop_tree()
                for i in self.tags(self.html, 'body'):
                    i.set('id', 'readabilityBody')
                if ruthless:
                    self.remove_unlikely_candidates()
                self.transform_misused_divs_into_paragraphs()
                candidates = self.score_paragraphs()

                best_candidate = self.select_best_candidate(candidates)
                if best_candidate:
                    article = self.get_article(candidates, best_candidate)
                elif ruthless:
                    self.log.debug('ruthless removal did not work. ')
                    ruthless = False
                    self.debug('ended up stripping too much - going for a safer _parse')
                    # try again
                    continue
                else:
                    self.log.debug('Ruthless and lenient parsing did not work. Returning raw html')
                    assert self.html is not None
                    article = self.html.find('body')
                    if article is None:
                        article = self.html

                cleaned_article = self.sanitize(article, candidates)
                of_acceptable_length = len(cleaned_article or '') >= (self.options['retry_length'] or self.RETRY_LENGTH)
                if ruthless and not of_acceptable_length:
                    ruthless = False
                    continue  # try again
                else:
                    return cleaned_article
        except Exception as e:
            self.log.exception('error getting summary: ')
            reraise(Unparsable, Unparsable(str(e)), sys.exc_info()[2])

    def get_article(self, candidates: dict[HtmlElement, Candidate], best_candidate: Candidate) -> HtmlElement:
        # Now that we have the top candidate, look through its siblings for content that might also be related.
        # Things like preambles, content split by ads that we removed, etc.

        sibling_score_threshold = max([10, best_candidate['content_score'] * 0.2])
        output = cast('HtmlElement', document_fromstring('<div/>'))  # parsed with the lxml.html parser
        parent = output.xpath('//div')[0]
        best_elem = best_candidate['elem']
        for sibling in list(best_elem.getparent()):  # ty: ignore[invalid-argument-type] candidates always have a parent in practice
            # if isinstance(sibling, NavigableString): continue#in lxml there no concept of simple text
            append = False
            if sibling is best_elem:
                append = True
            if sibling in candidates and candidates[sibling]['content_score'] >= sibling_score_threshold:
                append = True
            if sibling in self.keep_elements:
                append = True

            if sibling.tag == 'p':
                link_density = self.get_link_density(sibling)
                node_content = sibling.text or ''
                node_length = len(node_content)

                if node_length > 80 and link_density < 0.25:
                    append = True
                elif node_length < 80 and link_density == 0 and re.search(r'\.( |$)', node_content):
                    append = True

            if append:
                parent.append(sibling)
        # if output is not None:
        #     output.append(best_elem)
        body = output.find('body')
        assert body is not None  # the HTML parser always creates a body
        return body

    def select_best_candidate(self, candidates: dict[HtmlElement, Candidate]) -> Candidate | None:
        sorted_candidates = sorted(candidates.values(), key=lambda x: x['content_score'], reverse=True)
        for candidate in sorted_candidates[:5]:
            elem = candidate['elem']
            self.debug('Top 5 : {:6.3f} {}'.format(candidate['content_score'], describe(elem)))

        if len(sorted_candidates) == 0:
            return None

        best_candidate = sorted_candidates[0]
        return best_candidate

    def get_link_density(self, elem: HtmlElement) -> float:
        link_length = 0
        for i in elem.findall('.//a'):
            link_length += text_length(i)
        # if len(elem.findall(".//div") or elem.findall(".//p")):
        #     link_length = link_length
        total_length = text_length(elem)
        return float(link_length) / max(total_length, 1)

    def score_paragraphs(
        self,
    ) -> dict[HtmlElement, Candidate]:
        MIN_LEN = self.options.get('min_text_length') or self.TEXT_LENGTH_THRESHOLD
        candidates: dict[HtmlElement, Candidate] = {}
        assert self.html is not None
        # self.debug(str([describe(node) for node in self.tags(self.html, "div")]))

        ordered = []
        for elem in self.tags(self.html, 'p', 'pre', 'td'):
            parent_node = elem.getparent()
            if parent_node is None:
                continue
            grand_parent_node = parent_node.getparent()

            inner_text = clean(text_content(elem) or '')
            inner_text_len = len(inner_text)

            # If this paragraph is less than 25 characters, don't even count it.
            if inner_text_len < MIN_LEN:
                continue

            if parent_node not in candidates:
                candidates[parent_node] = self.score_node(parent_node)
                ordered.append(parent_node)

            if grand_parent_node is not None and grand_parent_node not in candidates:
                candidates[grand_parent_node] = self.score_node(grand_parent_node)
                ordered.append(grand_parent_node)

            content_score = 1
            content_score += len(inner_text.split(','))
            content_score += min((inner_text_len / 100), 3)
            # if elem not in candidates:
            #     candidates[elem] = self.score_node(elem)

            # WTF? candidates[elem]['content_score'] += content_score
            candidates[parent_node]['content_score'] += content_score
            if grand_parent_node is not None:
                candidates[grand_parent_node]['content_score'] += content_score / 2.0

        # Scale the final candidates score based on link density. Good content should have a
        # relatively small link density (5% or less) and be mostly unaffected by this operation.
        for elem in ordered:
            candidate = candidates[elem]
            ld = self.get_link_density(elem)
            score = candidate['content_score']
            self.debug(f'Candid: {score:6.3f} {describe(elem)} link density {ld:.3f} -> {score * (1 - ld):6.3f}')
            candidate['content_score'] *= 1 - ld

        return candidates

    def class_weight(self, e: HtmlElement) -> int:
        weight = 0
        if cls := e.get('class', None):
            if REGEXES['negativeRe'].search(cls):
                weight -= 25

            if REGEXES['positiveRe'].search(cls):
                weight += 25

        if eid := e.get('id', None):
            if REGEXES['negativeRe'].search(eid):
                weight -= 25

            if REGEXES['positiveRe'].search(eid):
                weight += 25

        return weight

    def score_node(self, elem: HtmlElement) -> Candidate:
        content_score = self.class_weight(elem)
        tag = elem.tag
        assert isinstance(tag, str)  # elem is the parent of an element, so it is an element, not a comment/PI
        name = tag.lower()
        if name == 'div':
            content_score += 5
        elif name in ['pre', 'td', 'blockquote']:
            content_score += 3
        elif name in ['address', 'ol', 'ul', 'dl', 'dd', 'dt', 'li', 'form']:
            content_score -= 3
        elif name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th']:
            content_score -= 5
        return {'content_score': content_score, 'elem': elem}

    def debug(self, *a: object) -> None:
        # if self.options['debug']:
        self.log.debug(*a)

    def remove_unlikely_candidates(self) -> None:
        assert self.html is not None
        for elem in self.html.iter():
            if elem in self.keep_elements:
                continue
            s = '{} {}'.format(elem.get('class', ''), elem.get('id', ''))
            # self.debug(s)
            if REGEXES['unlikelyCandidatesRe'].search(s) and (not REGEXES['okMaybeItsACandidateRe'].search(s)) and elem.tag != 'body':
                self.debug(f'Removing unlikely candidate - {describe(elem)}')
                elem.drop_tree()

    def transform_misused_divs_into_paragraphs(self) -> None:
        assert self.html is not None
        for elem in self.tags(self.html, 'div'):
            # transform <div>s that do not contain other block elements into <p>s
            if not REGEXES['divToPElementsRe'].search(str(''.join(map(tounicode, list(elem))))):
                # self.debug("Altering %s to p" % (describe(elem)))
                elem.tag = 'p'
                # print('Fixed element '+describe(elem))

        for elem in self.tags(self.html, 'div'):
            if elem.text and elem.text.strip():
                p = cast('HtmlElement', fragment_fromstring('<p/>'))  # parsed with the lxml.html parser
                p.text = elem.text
                elem.text = None
                elem.insert(0, p)
                # print('Appended '+tounicode(p)+' to '+describe(elem))

            for pos, child in reversed(list(enumerate(elem))):
                if child.tail and child.tail.strip():
                    p = cast('HtmlElement', fragment_fromstring('<p/>'))  # parsed with the lxml.html parser
                    p.text = child.tail
                    child.tail = None
                    elem.insert(pos + 1, p)
                    # print('Inserted '+tounicode(p)+' to '+describe(elem))
                if child.tag == 'br':
                    # print('Dropped <br> at '+describe(elem))
                    child.drop_tree()

    def tags(self, node: HtmlElement, *tag_names: str) -> Iterator[HtmlElement]:
        for tag_name in tag_names:
            yield from node.findall(f'.//{tag_name}')

    def reverse_tags(self, node: HtmlElement, *tag_names: str) -> Iterator[HtmlElement]:
        for tag_name in tag_names:
            yield from reversed(node.findall(f'.//{tag_name}'))

    def sanitize(self, node: HtmlElement, candidates: dict[HtmlElement, Candidate]) -> str:
        MIN_LEN = self.options.get('min_text_length') or self.TEXT_LENGTH_THRESHOLD
        for header in self.tags(node, 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            if self.class_weight(header) < 0 or self.get_link_density(header) > 0.33:
                header.drop_tree()

        for elem in self.tags(node, 'form', 'iframe', 'textarea'):
            elem.drop_tree()
        allowed: dict[HtmlElement, bool] = {}
        # Conditionally clean <table>s, <ul>s, and <div>s
        for el in self.reverse_tags(node, 'table', 'ul', 'div'):
            if el in allowed or el in self.keep_elements:
                continue
            weight = self.class_weight(el)
            if el in candidates:
                content_score = candidates[el]['content_score']
                # print('!',el, '-> %6.3f' % content_score)
            else:
                content_score = 0
            tag = el.tag

            if weight + content_score < 0:
                self.debug(f'Cleaned {describe(el)} with score {content_score:6.3f} and weight {weight:<3}')
                el.drop_tree()
            elif text_content(el).count(',') < 10:
                counts: dict[str, int] = {}
                for kind in ['p', 'img', 'li', 'a', 'embed', 'input']:
                    counts[kind] = len(el.findall(f'.//{kind}'))
                counts['li'] -= 100

                content_length = text_length(el)  # Count the text length excluding any surrounding whitespace
                link_density = self.get_link_density(el)
                parent_node = el.getparent()
                if parent_node is not None:
                    if parent_node in candidates:
                        content_score = candidates[parent_node]['content_score']
                    else:
                        content_score = 0
                # if parent_node is not None:
                #     pweight = self.class_weight(parent_node) + content_score
                #     pname = describe(parent_node)
                # else:
                #     pweight = 0
                #     pname = "no parent"
                to_remove = False
                reason = ''

                # if el.tag == 'div' and counts["img"] >= 1:
                #     continue
                if counts['p'] and counts['img'] > counts['p']:
                    reason = 'too many images ({})'.format(counts['img'])
                    to_remove = True
                elif counts['li'] > counts['p'] and tag not in {'ul', 'ol'}:
                    reason = 'more <li>s than <p>s'
                    to_remove = True
                elif counts['input'] > (counts['p'] / 3):
                    reason = 'less than 3x <p>s than <input>s'
                    to_remove = True
                elif content_length < (MIN_LEN) and (counts['img'] == 0 or counts['img'] > 2):
                    reason = f'too short content length {content_length} without a single image'
                    to_remove = True
                elif weight < 25 and link_density > 0.2:
                    reason = f'too many links {link_density:.3f} for its weight {weight}'
                    to_remove = True
                elif weight >= 25 and link_density > 0.5:
                    reason = f'too many links {link_density:.3f} for its weight {weight}'
                    to_remove = True
                elif (counts['embed'] == 1 and content_length < 75) or counts['embed'] > 1:
                    reason = '<embed>s with too short content length, or too many <embed>s'
                    to_remove = True
                    # if el.tag == 'div' and counts['img'] >= 1 and to_remove:
                    #     imgs = el.findall('.//img')
                    #     valid_img = False
                    #     self.debug(tounicode(el))
                    #     for img in imgs:
                    #
                    #         height = img.get('height')
                    #         text_length = img.get('text_length')
                    #         self.debug ("height %s text_length %s" %(repr(height), repr(text_length)))
                    #         if to_int(height) >= 100 or to_int(text_length) >= 100:
                    #             valid_img = True
                    #             self.debug("valid image" + tounicode(img))
                    #             break
                    #     if valid_img:
                    #         to_remove = False
                    #         self.debug("Allowing %s" %text_content(el))
                    #         for desnode in self.tags(el, "table", "ul", "div"):
                    #             allowed[desnode] = True

                    # find x non empty preceding and succeeding siblings
                    i, j = 0, 0
                    x = 1
                    siblings = []
                    for sib in el.itersiblings():
                        # self.debug(text_content(sib))
                        sib_content_length = text_length(sib)
                        if sib_content_length:
                            i += 1
                            siblings.append(sib_content_length)
                            if i == x:
                                break
                    for sib in el.itersiblings(preceding=True):
                        # self.debug(text_content(sib))
                        sib_content_length = text_length(sib)
                        if sib_content_length:
                            j = +1
                            siblings.append(sib_content_length)
                            if j == x:
                                break
                    # self.debug(str(siblings))
                    if siblings and sum(siblings) > 1000:
                        to_remove = False
                        self.debug(f'Allowing {describe(el)}')
                        for desnode in self.tags(el, 'table', 'ul', 'div'):
                            allowed[desnode] = True

                if to_remove:
                    self.debug(f'Cleaned {content_score:6.3f} {describe(el)} with weight {weight} cause it has {reason}.')
                    # print(tounicode(el))
                    # self.debug("pname %s pweight %.3f" %(pname, pweight))
                    el.drop_tree()

        return clean_attributes(tounicode(node))


def option_parser() -> OptionParser:
    from calibre.utils.config import OptionParser

    parser = OptionParser(usage='%prog: [options] file')
    parser.add_option(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        dest='verbose',
        help='Show detailed output information. Useful for debugging',
    )
    parser.add_option(
        '-k',
        '--keep-elements',
        default=None,
        action='store',
        dest='keep_elements',
        help='XPath specifying elements that should not be removed',
    )

    return parser


def main() -> None:
    from calibre.utils.logging import default_log

    parser = option_parser()
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        raise SystemExit(1)

    with open(args[0], 'rb') as f:
        raw = f.read()

    assert sys.__stdout__ is not None
    enc = sys.__stdout__.encoding or 'utf-8'
    if options.verbose:
        default_log.filter_level = default_log.DEBUG
    print(Document(raw, default_log, debug=options.verbose, keep_elements=options.keep_elements).summary().encode(enc, 'replace'))


if __name__ == '__main__':
    main()
