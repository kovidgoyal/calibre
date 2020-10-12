#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import regex
from polyglot.builtins import map, zip


class Parser(object):

    ''' See epubcfi.ebnf for the specification that this parser tries to
    follow. I have implemented it manually, since I dont want to depend on
    grako, and the grammar is pretty simple. This parser is thread-safe, i.e.
    it can be used from multiple threads simulataneously. '''

    def __init__(self):
        # All allowed unicode characters + escaped special characters
        special_char = r'[\[\](),;=^]'
        unescaped_char = '[[\t\n\r -\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]--%s]' % special_char
        escaped_char = r'\^' + special_char
        chars = r'(?:%s|(?:%s))+' % (unescaped_char, escaped_char)
        chars_no_space = chars.replace('0020', '0021')
        # No leading zeros allowed for integers
        integer = r'(?:[1-9][0-9]*)|0'
        # No leading zeros, except for numbers in (0, 1) and no trailing zeros for the fractional part
        frac = r'\.[0-9]*[1-9]'
        number = r'(?:[1-9][0-9]*(?:{0})?)|(?:0{0})|(?:0)'.format(frac)
        c = lambda x:regex.compile(x, flags=regex.VERSION1)

        # A step of the form /integer
        self.step_pat = c(r'/(%s)' % integer)
        # An id assertion of the form [characters]
        self.id_assertion_pat = c(r'\[(%s)\]' % chars)

        # A text offset of the form :integer
        self.text_offset_pat = c(r':(%s)' % integer)
        # A temporal offset of the form ~number
        self.temporal_offset_pat = c(r'~(%s)' % number)
        # A spatial offset of the form @number:number
        self.spatial_offset_pat = c(r'@({0}):({0})'.format(number))
        # A spatio-temporal offset of the form ~number@number:number
        self.st_offset_pat = c(r'~({0})@({0}):({0})'.format(number))

        # Text assertion patterns
        self.ta1_pat = c(r'({0})(?:,({0})){{0,1}}'.format(chars))
        self.ta2_pat = c(r',(%s)' % chars)
        self.parameters_pat = c(r'(?:;(%s)=((?:%s,?)+))+' % (chars_no_space, chars))
        self.csv_pat = c(r'(?:(%s),?)+' % chars)

        # Unescape characters
        unescape_pat = c(r'%s(%s)' % (escaped_char[:2], escaped_char[2:]))
        self.unescape = lambda x: unescape_pat.sub(r'\1', x)

    def parse_epubcfi(self, raw):
        ' Parse a full epubcfi of the form epubcfi(path [ , path , path ]) '
        null = {}, {}, {}, raw
        if not raw:
            return null

        if not raw.startswith('epubcfi('):
            return null
        raw = raw[len('epubcfi('):]
        parent_cfi, raw = self.parse_path(raw)
        if not parent_cfi:
            return null
        start_cfi, end_cfi = {}, {}
        if raw.startswith(','):
            start_cfi, raw = self.parse_path(raw[1:])
            if raw.startswith(','):
                end_cfi, raw = self.parse_path(raw[1:])
            if not start_cfi or not end_cfi:
                return null
        if raw.startswith(')'):
            raw = raw[1:]
        else:
            return null

        return parent_cfi, start_cfi, end_cfi, raw

    def parse_path(self, raw):
        ' Parse the path component of an epubcfi of the form /step... '
        path = {'steps':[]}
        raw = self._parse_path(raw, path)
        if not path['steps']:
            path = {}
        return path, raw

    def do_match(self, pat, raw):
        m = pat.match(raw)
        if m is not None:
            raw = raw[len(m.group()):]
        return m, raw

    def _parse_path(self, raw, ans):
        m, raw = self.do_match(self.step_pat, raw)
        if m is None:
            return raw
        ans['steps'].append({'num':int(m.group(1))})
        m, raw = self.do_match(self.id_assertion_pat, raw)
        if m is not None:
            ans['steps'][-1]['id'] = self.unescape(m.group(1))
        if raw.startswith('!'):
            ans['redirect'] = r = {'steps':[]}
            return self._parse_path(raw[1:], r)
        else:
            remaining_raw = self.parse_offset(raw, ans['steps'][-1])
            return self._parse_path(raw, ans) if remaining_raw is None else remaining_raw

    def parse_offset(self, raw, ans):
        m, raw = self.do_match(self.text_offset_pat, raw)
        if m is not None:
            ans['text_offset'] = int(m.group(1))
            return self.parse_text_assertion(raw, ans)
        m, raw = self.do_match(self.st_offset_pat, raw)
        if m is not None:
            t, x, y = m.groups()
            ans['temporal_offset'] = float(t)
            ans['spatial_offset'] = tuple(map(float, (x, y)))
            return raw
        m, raw = self.do_match(self.temporal_offset_pat, raw)
        if m is not None:
            ans['temporal_offset'] = float(m.group(1))
            return raw
        m, raw = self.do_match(self.spatial_offset_pat, raw)
        if m is not None:
            ans['spatial_offset'] = tuple(map(float, m.groups()))
            return raw

    def parse_text_assertion(self, raw, ans):
        oraw = raw
        if not raw.startswith('['):
            return oraw
        raw = raw[1:]
        ta = {}
        m, raw = self.do_match(self.ta1_pat, raw)
        if m is not None:
            before, after = m.groups()
            ta['before'] = self.unescape(before)
            if after is not None:
                ta['after'] = self.unescape(after)
        else:
            m, raw = self.do_match(self.ta2_pat, raw)
            if m is not None:
                ta['after'] = self.unescape(m.group(1))

        # parse parameters
        m, raw = self.do_match(self.parameters_pat, raw)
        if m is not None:
            params = {}
            for name, value in zip(m.captures(1), m.captures(2)):
                params[name] = tuple(map(self.unescape, self.csv_pat.match(value).captures(1)))
            if params:
                ta['params'] = params

        if not raw.startswith(']'):
            return oraw  # no closing ] or extra content in the assertion

        if ta:
            ans['text_assertion'] = ta
        return raw[1:]


_parser = None


def parser():
    global _parser
    if _parser is None:
        _parser = Parser()
    return _parser


def get_steps(pcfi):
    ans = tuple(pcfi['steps'])
    if 'redirect' in pcfi:
        ans += get_steps(pcfi['redirect'])
    return ans


def cfi_sort_key(cfi, only_path=True):
    p = parser()
    try:
        if only_path:
            pcfi = p.parse_path(cfi)[0]
        else:
            parent, start = p.parse_epubcfi(cfi)[:2]
            pcfi = start or parent
    except Exception:
        import traceback
        traceback.print_exc()
        return (), (0, (0, 0), 0)
    if not pcfi:
        import sys
        print('Failed to parse CFI: %r' % cfi, file=sys.stderr)
        return (), (0, (0, 0), 0)
    steps = get_steps(pcfi)
    step_nums = tuple(s.get('num', 0) for s in steps)
    step = steps[-1] if steps else {}
    offsets = (step.get('temporal_offset', 0), tuple(reversed(step.get('spatial_offset', (0, 0)))), step.get('text_offset', 0), )
    return step_nums, offsets


def decode_cfi(root, cfi):
    from lxml.etree import XPathEvalError
    p = parser()
    try:
        pcfi = p.parse_path(cfi)[0]
    except Exception:
        import traceback
        traceback.print_exc()
        return
    if not pcfi:
        import sys
        print('Failed to parse CFI: %r' % pcfi, file=sys.stderr)
        return
    steps = get_steps(pcfi)
    ans = root
    for step in steps:
        num = step.get('num', 0)
        node_id = step.get('id')
        try:
            match = ans.xpath('descendant::*[@id="%s"]' % node_id)
        except XPathEvalError:
            match = ()
        if match:
            ans = match[0]
            continue
        index = 0
        for child in ans.iterchildren('*'):
            index |= 1  # increment index by 1 if it is even
            index += 1
            if index == num:
                ans = child
                break
        else:
            return
    return ans
