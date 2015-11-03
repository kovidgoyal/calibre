# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import re

import html5lib
from html5lib.sanitizer import HTMLSanitizer
from html5lib.serializer.htmlserializer import HTMLSerializer

from . import callbacks as linkify_callbacks
from .encoding import force_unicode
from .sanitizer import BleachSanitizer


VERSION = (1, 4, 2)
__version__ = '.'.join([str(n) for n in VERSION])

__all__ = ['clean', 'linkify']

log = logging.getLogger('bleach')

ALLOWED_TAGS = [
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'code',
    'em',
    'i',
    'li',
    'ol',
    'strong',
    'ul',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
}

ALLOWED_STYLES = []

TLDS = """ac ad ae aero af ag ai al am an ao aq ar arpa as asia at au aw ax az
       ba bb bd be bf bg bh bi biz bj bm bn bo br bs bt bv bw by bz ca cat
       cc cd cf cg ch ci ck cl cm cn co com coop cr cu cv cx cy cz de dj dk
       dm do dz ec edu ee eg er es et eu fi fj fk fm fo fr ga gb gd ge gf gg
       gh gi gl gm gn gov gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il
       im in info int io iq ir is it je jm jo jobs jp ke kg kh ki km kn kp
       kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mil mk
       ml mm mn mo mobi mp mq mr ms mt mu museum mv mw mx my mz na name nc ne
       net nf ng ni nl no np nr nu nz om org pa pe pf pg ph pk pl pm pn post
       pr pro ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si sj sk sl
       sm sn so sr ss st su sv sx sy sz tc td tel tf tg th tj tk tl tm tn to
       tp tr travel tt tv tw tz ua ug uk us uy uz va vc ve vg vi vn vu wf ws
       xn xxx ye yt yu za zm zw""".split()

# Make sure that .com doesn't get matched by .co first
TLDS.reverse()

PROTOCOLS = HTMLSanitizer.acceptable_protocols

url_re = re.compile(
    r"""\(*  # Match any opening parentheses.
    \b(?<![@.])(?:(?:{0}):/{{0,3}}(?:(?:\w+:)?\w+@)?)?  # http://
    ([\w-]+\.)+(?:{1})(?:\:\d+)?(?!\.\w)\b   # xx.yy.tld(:##)?
    (?:[/?][^\s\{{\}}\|\\\^\[\]`<>"]*)?
        # /path/zz (excluding "unsafe" chars from RFC 1738,
        # except for # and ~, which happen in practice)
    """.format('|'.join(PROTOCOLS), '|'.join(TLDS)),
    re.IGNORECASE | re.VERBOSE | re.UNICODE)

proto_re = re.compile(r'^[\w-]+:/{0,3}', re.IGNORECASE)

punct_re = re.compile(r'([\.,]+)$')

email_re = re.compile(
    r"""(?<!//)
    (([-!#$%&'*+/=?^_`{0!s}|~0-9A-Z]+
        (\.[-!#$%&'*+/=?^_`{1!s}|~0-9A-Z]+)*  # dot-atom
    |^"([\001-\010\013\014\016-\037!#-\[\]-\177]
        |\\[\001-011\013\014\016-\177])*"  # quoted-string
    )@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6})\.?  # domain
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE)

NODE_TEXT = 4  # The numeric ID of a text node in simpletree.

ETREE_TAG = lambda x: "".join(['{http://www.w3.org/1999/xhtml}', x])
# a simple routine that returns the tag name with the namespace prefix
# as returned by etree's Element.tag attribute

DEFAULT_CALLBACKS = [linkify_callbacks.nofollow]


def clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES,
          styles=ALLOWED_STYLES, strip=False, strip_comments=True):
    """Clean an HTML fragment and return it"""
    if not text:
        return ''

    text = force_unicode(text)

    class s(BleachSanitizer):
        allowed_elements = tags
        allowed_attributes = attributes
        allowed_css_properties = styles
        strip_disallowed_elements = strip
        strip_html_comments = strip_comments

    parser = html5lib.HTMLParser(tokenizer=s)

    return _render(parser.parseFragment(text))


def linkify(text, callbacks=DEFAULT_CALLBACKS, skip_pre=False,
            parse_email=False, tokenizer=HTMLSanitizer):
    """Convert URL-like strings in an HTML fragment to links.

    linkify() converts strings that look like URLs or domain names in a
    blob of text that may be an HTML fragment to links, while preserving
    (a) links already in the string, (b) urls found in attributes, and
    (c) email addresses.
    """
    text = force_unicode(text)

    if not text:
        return ''

    parser = html5lib.HTMLParser(tokenizer=tokenizer)

    forest = parser.parseFragment(text)
    _seen = set([])

    def replace_nodes(tree, new_frag, node, index=0):
        """
        Doesn't really replace nodes, but inserts the nodes contained in
        new_frag into the treee at position index and returns the number
        of nodes inserted.
        If node is passed in, it is removed from the tree
        """
        count = 0
        new_tree = parser.parseFragment(new_frag)
        # capture any non-tag text at the start of the fragment
        if new_tree.text:
            if index == 0:
                tree.text = tree.text or ''
                tree.text += new_tree.text
            else:
                tree[index - 1].tail = tree[index - 1].tail or ''
                tree[index - 1].tail += new_tree.text
        # the put in the tagged elements into the old tree
        for n in new_tree:
            if n.tag == ETREE_TAG('a'):
                _seen.add(n)
            tree.insert(index + count, n)
            count += 1
        # if we got a node to remove...
        if node is not None:
            tree.remove(node)
        return count

    def strip_wrapping_parentheses(fragment):
        """Strips wrapping parentheses.

        Returns a tuple of the following format::

            (string stripped from wrapping parentheses,
             count of stripped opening parentheses,
             count of stripped closing parentheses)
        """
        opening_parentheses = closing_parentheses = 0
        # Count consecutive opening parentheses
        # at the beginning of the fragment (string).
        for char in fragment:
            if char == '(':
                opening_parentheses += 1
            else:
                break

        if opening_parentheses:
            newer_frag = ''
            # Cut the consecutive opening brackets from the fragment.
            fragment = fragment[opening_parentheses:]
            # Reverse the fragment for easier detection of parentheses
            # inside the URL.
            reverse_fragment = fragment[::-1]
            skip = False
            for char in reverse_fragment:
                # Remove the closing parentheses if it has a matching
                # opening parentheses (they are balanced).
                if (char == ')' and
                        closing_parentheses < opening_parentheses and
                        not skip):
                    closing_parentheses += 1
                    continue
                # Do not remove ')' from the URL itself.
                elif char != ')':
                    skip = True
                newer_frag += char
            fragment = newer_frag[::-1]

        return fragment, opening_parentheses, closing_parentheses

    def apply_callbacks(attrs, new):
        for cb in callbacks:
            attrs = cb(attrs, new)
            if attrs is None:
                return None
        return attrs

    def _render_inner(node):
        out = ['' if node.text is None else node.text]
        for subnode in node:
            out.append(_render(subnode))
            if subnode.tail:
                out.append(subnode.tail)
        return ''.join(out)

    def linkify_nodes(tree, parse_text=True):
        children = len(tree)
        current_child = -1
        # start at -1 to process the parent first
        while current_child < len(tree):
            if current_child < 0:
                node = tree
                if parse_text and node.text:
                    new_txt = old_txt = node.text
                    if parse_email:
                        new_txt = re.sub(email_re, email_repl, node.text)
                        if new_txt and new_txt != node.text:
                            node.text = ''
                            adj = replace_nodes(tree, new_txt, None, 0)
                            children += adj
                            current_child += adj
                            linkify_nodes(tree, True)
                            continue

                    new_txt = re.sub(url_re, link_repl, new_txt)
                    if new_txt != old_txt:
                        node.text = ''
                        adj = replace_nodes(tree, new_txt, None, 0)
                        children += adj
                        current_child += adj
                        continue
            else:
                node = tree[current_child]

            if parse_text and node.tail:
                new_tail = old_tail = node.tail
                if parse_email:
                    new_tail = re.sub(email_re, email_repl, new_tail)
                    if new_tail != node.tail:
                        node.tail = ''
                        adj = replace_nodes(tree, new_tail, None,
                                            current_child + 1)
                        # Insert the new nodes made from my tail into
                        # the tree right after me. current_child+1
                        children += adj
                        continue

                new_tail = re.sub(url_re, link_repl, new_tail)
                if new_tail != old_tail:
                    node.tail = ''
                    adj = replace_nodes(tree, new_tail, None,
                                        current_child + 1)
                    children += adj

            if node.tag == ETREE_TAG('a') and not (node in _seen):
                if not node.get('href', None) is None:
                    attrs = dict(node.items())

                    _text = attrs['_text'] = _render_inner(node)

                    attrs = apply_callbacks(attrs, False)

                    if attrs is None:
                        # <a> tag replaced by the text within it
                        adj = replace_nodes(tree, _text, node,
                                            current_child)
                        current_child -= 1
                        # pull back current_child by 1 to scan the
                        # new nodes again.
                    else:
                        text = force_unicode(attrs.pop('_text'))
                        for attr_key, attr_val in attrs.items():
                            node.set(attr_key, attr_val)

                        for n in reversed(list(node)):
                            node.remove(n)
                        text = parser.parseFragment(text)
                        node.text = text.text
                        for n in text:
                            node.append(n)
                        _seen.add(node)

            elif current_child >= 0:
                if node.tag == ETREE_TAG('pre') and skip_pre:
                    linkify_nodes(node, False)
                elif not (node in _seen):
                    linkify_nodes(node, True)

            current_child += 1

    def email_repl(match):
        addr = match.group(0).replace('"', '&quot;')
        link = {
            '_text': addr,
            'href': 'mailto:{0!s}'.format(addr),
        }
        link = apply_callbacks(link, True)

        if link is None:
            return addr

        _href = link.pop('href')
        _text = link.pop('_text')

        repl = '<a href="{0!s}" {1!s}>{2!s}</a>'
        attr = '{0!s}="{1!s}"'
        attribs = ' '.join(attr.format(k, v) for k, v in link.items())
        return repl.format(_href, attribs, _text)

    def link_repl(match):
        url = match.group(0)
        open_brackets = close_brackets = 0
        if url.startswith('('):
            _wrapping = strip_wrapping_parentheses(url)
            url, open_brackets, close_brackets = _wrapping
        end = ''
        m = re.search(punct_re, url)
        if m:
            end = m.group(0)
            url = url[0:m.start()]
        if re.search(proto_re, url):
            href = url
        else:
            href = ''.join(['http://', url])

        link = {
            '_text': url,
            'href': href,
        }

        link = apply_callbacks(link, True)

        if link is None:
            return '(' * open_brackets + url + ')' * close_brackets

        _text = link.pop('_text')
        _href = link.pop('href')

        repl = '{0!s}<a href="{1!s}" {2!s}>{3!s}</a>{4!s}{5!s}'
        attr = '{0!s}="{1!s}"'
        attribs = ' '.join(attr.format(k, v) for k, v in link.items())

        return repl.format('(' * open_brackets,
                           _href, attribs, _text, end,
                           ')' * close_brackets)

    try:
        linkify_nodes(forest)
    except RuntimeError as e:
        # If we hit the max recursion depth, just return what we've got.
        log.exception('Probable recursion error: {0!r}'.format(e))

    return _render(forest)


def _render(tree):
    """Try rendering as HTML, then XML, then give up."""
    return force_unicode(_serialize(tree))


def _serialize(domtree):
    walker = html5lib.treewalkers.getTreeWalker('etree')
    stream = walker(domtree)
    serializer = HTMLSerializer(quote_attr_values=True,
                                alphabetical_attributes=True,
                                omit_optional_tags=False)
    return serializer.render(stream)
