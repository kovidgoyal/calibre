#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


import re, sys
from collections import defaultdict

from polyglot.builtins import reraise, unicode_type

from lxml.html import (fragment_fromstring, document_fromstring,
        tostring as htostring)

from calibre.ebooks.readability.htmls import build_doc, get_body, get_title, shorten_title
from calibre.ebooks.readability.cleaners import html_cleaner, clean_attributes


def tounicode(tree_or_node, **kwargs):
    kwargs['encoding'] = unicode_type
    return htostring(tree_or_node, **kwargs)


REGEXES = {
    'unlikelyCandidatesRe': re.compile('combx|comment|community|disqus|extra|foot|header|menu|remark|rss|shoutbox|sidebar|sponsor|ad-break|agegate|pagination|pager|popup|tweet|twitter',re.I),  # noqa
    'okMaybeItsACandidateRe': re.compile('and|article|body|column|main|shadow',re.I),
    'positiveRe': re.compile('article|body|content|entry|hentry|main|page|pagination|post|text|blog|story',re.I),
    'negativeRe': re.compile('combx|comment|com-|contact|foot|footer|footnote|masthead|media|meta|outbrain|promo|related|scroll|shoutbox|sidebar|sponsor|shopping|tags|tool|widget',re.I),  # noqa
    'divToPElementsRe': re.compile('<(a|blockquote|dl|div|img|ol|p|pre|table|ul)',re.I),
    # 'replaceBrsRe': re.compile('(<br[^>]*>[ \n\r\t]*){2,}',re.I),
    # 'replaceFontsRe': re.compile('<(\/?)font[^>]*>',re.I),
    # 'trimRe': re.compile('^\s+|\s+$/'),
    # 'normalizeRe': re.compile('\s{2,}/'),
    # 'killBreaksRe': re.compile('(<br\s*\/?>(\s|&nbsp;?)*){1,}/'),
    # 'videoRe': re.compile('http:\/\/(www\.)?(youtube|vimeo)\.com', re.I),
    # skipFootnoteLink:    /^\s*(\[?[a-z0-9]{1,2}\]?|^|edit|citation needed)\s*$/i,
}


def describe(node, depth=1):
    if not hasattr(node, 'tag'):
        return "[%s]" % type(node)
    name = node.tag
    if node.get('id', ''):
        name += '#'+node.get('id')
    if node.get('class', ''):
        name += '.' + node.get('class').replace(' ','.')
    if name[:4] in ['div#', 'div.']:
        name = name[3:]
    if depth and node.getparent() is not None:
        return name+' - '+describe(node.getparent(), depth-1)
    return name


def to_int(x):
    if not x:
        return None
    x = x.strip()
    if x.endswith('px'):
        return int(x[:-2])
    if x.endswith('em'):
        return int(x[:-2]) * 12
    return int(x)


def clean(text):
    text = re.sub('\\s*\n\\s*', '\n', text)
    text = re.sub('[ \t]{2,}', ' ', text)
    return text.strip()


def text_length(i):
    return len(clean(i.text_content() or ""))


class Unparseable(ValueError):
    pass


class Document:
    TEXT_LENGTH_THRESHOLD = 25
    RETRY_LENGTH = 250

    def __init__(self, input, log, **options):
        self.input = input
        self.options = defaultdict(lambda: None)
        for k, v in options.items():
            self.options[k] = v
        self.html = None
        self.log = log
        self.keep_elements = set()

    def _html(self, force=False):
        if force or self.html is None:
            self.html = self._parse(self.input)
            path = self.options['keep_elements']
            if path is not None:
                self.keep_elements = set(self.html.xpath(path))

        return self.html

    def _parse(self, input):
        doc = build_doc(input)
        doc = html_cleaner.clean_html(doc)
        base_href = self.options['url']
        if base_href:
            doc.make_links_absolute(base_href, resolve_base_href=True)
        else:
            doc.resolve_base_href()
        return doc

    def content(self):
        return get_body(self._html(True))

    def title(self):
        return get_title(self._html(True))

    def short_title(self):
        return shorten_title(self._html(True))

    def summary(self):
        try:
            ruthless = True
            while True:
                self._html(True)

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
                else:
                    if ruthless:
                        self.log.debug("ruthless removal did not work. ")
                        ruthless = False
                        self.debug("ended up stripping too much - going for a safer _parse")
                        # try again
                        continue
                    else:
                        self.log.debug("Ruthless and lenient parsing did not work. Returning raw html")
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
            reraise(Unparseable, Unparseable(unicode_type(e)), sys.exc_info()[2])

    def get_article(self, candidates, best_candidate):
        # Now that we have the top candidate, look through its siblings for content that might also be related.
        # Things like preambles, content split by ads that we removed, etc.

        sibling_score_threshold = max([10, best_candidate['content_score'] * 0.2])
        output = document_fromstring('<div/>')
        parent = output.xpath('//div')[0]
        best_elem = best_candidate['elem']
        for sibling in best_elem.getparent().getchildren():
            # if isinstance(sibling, NavigableString): continue#in lxml there no concept of simple text
            append = False
            if sibling is best_elem:
                append = True
            if sibling in candidates and candidates[sibling]['content_score'] >= sibling_score_threshold:
                append = True
            if sibling in self.keep_elements:
                append = True

            if sibling.tag == "p":
                link_density = self.get_link_density(sibling)
                node_content = sibling.text or ""
                node_length = len(node_content)

                if node_length > 80 and link_density < 0.25:
                    append = True
                elif node_length < 80 and link_density == 0 and re.search(r'\.( |$)', node_content):
                    append = True

            if append:
                parent.append(sibling)
        # if output is not None:
        #   output.append(best_elem)
        return output.find('body')

    def select_best_candidate(self, candidates):
        sorted_candidates = sorted(candidates.values(), key=lambda x: x['content_score'], reverse=True)
        for candidate in sorted_candidates[:5]:
            elem = candidate['elem']
            self.debug("Top 5 : %6.3f %s" % (candidate['content_score'], describe(elem)))

        if len(sorted_candidates) == 0:
            return None

        best_candidate = sorted_candidates[0]
        return best_candidate

    def get_link_density(self, elem):
        link_length = 0
        for i in elem.findall(".//a"):
            link_length += text_length(i)
        # if len(elem.findall(".//div") or elem.findall(".//p")):
        #   link_length = link_length
        total_length = text_length(elem)
        return float(link_length) / max(total_length, 1)

    def score_paragraphs(self, ):
        MIN_LEN = self.options.get('min_text_length', self.TEXT_LENGTH_THRESHOLD)
        candidates = {}
        # self.debug(unicode_type([describe(node) for node in self.tags(self.html, "div")]))

        ordered = []
        for elem in self.tags(self.html, "p", "pre", "td"):
            parent_node = elem.getparent()
            if parent_node is None:
                continue
            grand_parent_node = parent_node.getparent()

            inner_text = clean(elem.text_content() or "")
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
            #   candidates[elem] = self.score_node(elem)

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
            self.debug("Candid: %6.3f %s link density %.3f -> %6.3f" % (score, describe(elem), ld, score*(1-ld)))
            candidate['content_score'] *= (1 - ld)

        return candidates

    def class_weight(self, e):
        weight = 0
        if e.get('class', None):
            if REGEXES['negativeRe'].search(e.get('class')):
                weight -= 25

            if REGEXES['positiveRe'].search(e.get('class')):
                weight += 25

        if e.get('id', None):
            if REGEXES['negativeRe'].search(e.get('id')):
                weight -= 25

            if REGEXES['positiveRe'].search(e.get('id')):
                weight += 25

        return weight

    def score_node(self, elem):
        content_score = self.class_weight(elem)
        name = elem.tag.lower()
        if name == "div":
            content_score += 5
        elif name in ["pre", "td", "blockquote"]:
            content_score += 3
        elif name in ["address", "ol", "ul", "dl", "dd", "dt", "li", "form"]:
            content_score -= 3
        elif name in ["h1", "h2", "h3", "h4", "h5", "h6", "th"]:
            content_score -= 5
        return {
            'content_score': content_score,
            'elem': elem
        }

    def debug(self, *a):
        # if self.options['debug']:
        self.log.debug(*a)

    def remove_unlikely_candidates(self):
        for elem in self.html.iter():
            if elem in self.keep_elements:
                continue
            s = "%s %s" % (elem.get('class', ''), elem.get('id', ''))
            # self.debug(s)
            if REGEXES['unlikelyCandidatesRe'].search(s) and (not REGEXES['okMaybeItsACandidateRe'].search(s)) and elem.tag != 'body':
                self.debug("Removing unlikely candidate - %s" % describe(elem))
                elem.drop_tree()

    def transform_misused_divs_into_paragraphs(self):
        for elem in self.tags(self.html, 'div'):
            # transform <div>s that do not contain other block elements into <p>s
            if not REGEXES['divToPElementsRe'].search(unicode_type(''.join(map(tounicode, list(elem))))):
                # self.debug("Altering %s to p" % (describe(elem)))
                elem.tag = "p"
                # print("Fixed element "+describe(elem))

        for elem in self.tags(self.html, 'div'):
            if elem.text and elem.text.strip():
                p = fragment_fromstring('<p/>')
                p.text = elem.text
                elem.text = None
                elem.insert(0, p)
                # print("Appended "+tounicode(p)+" to "+describe(elem))

            for pos, child in reversed(list(enumerate(elem))):
                if child.tail and child.tail.strip():
                    p = fragment_fromstring('<p/>')
                    p.text = child.tail
                    child.tail = None
                    elem.insert(pos + 1, p)
                    # print("Inserted "+tounicode(p)+" to "+describe(elem))
                if child.tag == 'br':
                    # print('Dropped <br> at '+describe(elem))
                    child.drop_tree()

    def tags(self, node, *tag_names):
        for tag_name in tag_names:
            for e in node.findall('.//%s' % tag_name):
                yield e

    def reverse_tags(self, node, *tag_names):
        for tag_name in tag_names:
            for e in reversed(node.findall('.//%s' % tag_name)):
                yield e

    def sanitize(self, node, candidates):
        MIN_LEN = self.options.get('min_text_length', self.TEXT_LENGTH_THRESHOLD)
        for header in self.tags(node, "h1", "h2", "h3", "h4", "h5", "h6"):
            if self.class_weight(header) < 0 or self.get_link_density(header) > 0.33:
                header.drop_tree()

        for elem in self.tags(node, "form", "iframe", "textarea"):
            elem.drop_tree()
        allowed = {}
        # Conditionally clean <table>s, <ul>s, and <div>s
        for el in self.reverse_tags(node, "table", "ul", "div"):
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
                self.debug("Cleaned %s with score %6.3f and weight %-3s" %
                    (describe(el), content_score, weight, ))
                el.drop_tree()
            elif el.text_content().count(",") < 10:
                counts = {}
                for kind in ['p', 'img', 'li', 'a', 'embed', 'input']:
                    counts[kind] = len(el.findall('.//%s' %kind))
                counts["li"] -= 100

                content_length = text_length(el)  # Count the text length excluding any surrounding whitespace
                link_density = self.get_link_density(el)
                parent_node = el.getparent()
                if parent_node is not None:
                    if parent_node in candidates:
                        content_score = candidates[parent_node]['content_score']
                    else:
                        content_score = 0
                # if parent_node is not None:
                    # pweight = self.class_weight(parent_node) + content_score
                    # pname = describe(parent_node)
                # else:
                    # pweight = 0
                    # pname = "no parent"
                to_remove = False
                reason = ""

                # if el.tag == 'div' and counts["img"] >= 1:
                #   continue
                if counts["p"] and counts["img"] > counts["p"]:
                    reason = "too many images (%s)" % counts["img"]
                    to_remove = True
                elif counts["li"] > counts["p"] and tag != "ul" and tag != "ol":
                    reason = "more <li>s than <p>s"
                    to_remove = True
                elif counts["input"] > (counts["p"] / 3):
                    reason = "less than 3x <p>s than <input>s"
                    to_remove = True
                elif content_length < (MIN_LEN) and (counts["img"] == 0 or counts["img"] > 2):
                    reason = "too short content length %s without a single image" % content_length
                    to_remove = True
                elif weight < 25 and link_density > 0.2:
                    reason = "too many links %.3f for its weight %s" % (link_density, weight)
                    to_remove = True
                elif weight >= 25 and link_density > 0.5:
                    reason = "too many links %.3f for its weight %s" % (link_density, weight)
                    to_remove = True
                elif (counts["embed"] == 1 and content_length < 75) or counts["embed"] > 1:
                    reason = "<embed>s with too short content length, or too many <embed>s"
                    to_remove = True
#               if el.tag == 'div' and counts['img'] >= 1 and to_remove:
#                   imgs = el.findall('.//img')
#                   valid_img = False
#                   self.debug(tounicode(el))
#                   for img in imgs:
#
#                       height = img.get('height')
#                       text_length = img.get('text_length')
#                       self.debug ("height %s text_length %s" %(repr(height), repr(text_length)))
#                       if to_int(height) >= 100 or to_int(text_length) >= 100:
#                           valid_img = True
#                           self.debug("valid image" + tounicode(img))
#                           break
#                   if valid_img:
#                       to_remove = False
#                       self.debug("Allowing %s" %el.text_content())
#                       for desnode in self.tags(el, "table", "ul", "div"):
#                           allowed[desnode] = True

                    # find x non empty preceding and succeeding siblings
                    i, j = 0, 0
                    x  = 1
                    siblings = []
                    for sib in el.itersiblings():
                        # self.debug(sib.text_content())
                        sib_content_length = text_length(sib)
                        if sib_content_length:
                            i += 1
                            siblings.append(sib_content_length)
                            if i == x:
                                break
                    for sib in el.itersiblings(preceding=True):
                        # self.debug(sib.text_content())
                        sib_content_length = text_length(sib)
                        if sib_content_length:
                            j =+ 1
                            siblings.append(sib_content_length)
                            if j == x:
                                break
                    # self.debug(unicode_type(siblings))
                    if siblings and sum(siblings) > 1000 :
                        to_remove = False
                        self.debug("Allowing %s" % describe(el))
                        for desnode in self.tags(el, "table", "ul", "div"):
                            allowed[desnode] = True

                if to_remove:
                    self.debug("Cleaned %6.3f %s with weight %s cause it has %s." %
                        (content_score, describe(el), weight, reason))
                    # print(tounicode(el))
                    # self.debug("pname %s pweight %.3f" %(pname, pweight))
                    el.drop_tree()

        return clean_attributes(tounicode(node))


def option_parser():
    from calibre.utils.config import OptionParser
    parser = OptionParser(usage='%prog: [options] file')
    parser.add_option('-v', '--verbose', default=False, action='store_true',
            dest='verbose',
            help='Show detailed output information. Useful for debugging')
    parser.add_option('-k', '--keep-elements', default=None, action='store',
            dest='keep_elements',
            help='XPath specifying elements that should not be removed')

    return parser


def main():
    from calibre.utils.logging import default_log
    parser = option_parser()
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        raise SystemExit(1)

    with open(args[0], 'rb') as f:
        raw = f.read()

    enc = sys.__stdout__.encoding or 'utf-8'
    if options.verbose:
        default_log.filter_level = default_log.DEBUG
    print(Document(raw, default_log,
            debug=options.verbose,
            keep_elements=options.keep_elements).summary().encode(enc,
                'replace'))


if __name__ == '__main__':
    main()
