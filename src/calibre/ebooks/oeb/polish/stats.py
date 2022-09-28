#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial

from lxml.etree import tostring
import regex

from calibre.ebooks.oeb.base import XHTML, css_text
from calibre.ebooks.oeb.polish.cascade import iterrules, resolve_styles, iterdeclaration
from calibre.utils.icu import ord_string, safe_chr
from polyglot.builtins import iteritems, itervalues
from tinycss.fonts3 import parse_font_family


def normalize_font_properties(font):
    w = font.get('font-weight', None)
    if not w and w != 0:
        w = 'normal'
    w = str(w)
    w = {'normal':'400', 'bold':'700'}.get(w, w)
    if w not in {'100', '200', '300', '400', '500', '600', '700',
            '800', '900'}:
        w = '400'
    font['font-weight'] = w

    val = font.get('font-style', None)
    if val not in {'normal', 'italic', 'oblique'}:
        val = 'normal'
    font['font-style'] = val

    val = font.get('font-stretch', None)
    if val not in {'normal', 'ultra-condensed', 'extra-condensed', 'condensed',
                   'semi-condensed', 'semi-expanded', 'expanded',
                   'extra-expanded', 'ultra-expanded'}:
        val = 'normal'
    font['font-stretch'] = val
    return font


widths = {x:i for i, x in enumerate(('ultra-condensed',
        'extra-condensed', 'condensed', 'semi-condensed', 'normal',
        'semi-expanded', 'expanded', 'extra-expanded', 'ultra-expanded'
        ))}


def get_matching_rules(rules, font):
    matches = []

    # Filter on family
    for rule in reversed(rules):
        ff = frozenset(icu_lower(x) for x in font.get('font-family', []))
        if ff.intersection(rule['font-family']):
            matches.append(rule)
    if not matches:
        return []

    # Filter on font stretch
    width = widths[font.get('font-stretch', 'normal')]

    min_dist = min(abs(width-y['width']) for y in matches)
    nearest = [x for x in matches if abs(width-x['width']) == min_dist]
    if width <= 4:
        lmatches = [f for f in nearest if f['width'] <= width]
    else:
        lmatches = [f for f in nearest if f['width'] >= width]
    matches = (lmatches or nearest)

    # Filter on font-style
    fs = font.get('font-style', 'normal')
    order = {
            'oblique':['oblique', 'italic', 'normal'],
            'normal':['normal', 'oblique', 'italic']
        }.get(fs, ['italic', 'oblique', 'normal'])
    for q in order:
        m = [f for f in matches if f.get('font-style', 'normal') == q]
        if m:
            matches = m
            break

    # Filter on font weight
    fw = int(font.get('font-weight', '400'))
    if fw == 400:
        q = [400, 500, 300, 200, 100, 600, 700, 800, 900]
    elif fw == 500:
        q = [500, 400, 300, 200, 100, 600, 700, 800, 900]
    elif fw < 400:
        q = [fw] + list(range(fw-100, -100, -100)) + list(range(fw+100,
            100, 1000))
    else:
        q = [fw] + list(range(fw+100, 100, 1000)) + list(range(fw-100,
            -100, -100))
    for wt in q:
        m = [f for f in matches if f['weight'] == wt]
        if m:
            return m
    return []


def get_css_text(elem, resolve_pseudo_property, which='before'):
    text = resolve_pseudo_property(elem, which, 'content')[0].value
    if text and len(text) > 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return ''


caps_variants = {'smallcaps', 'small-caps', 'all-small-caps', 'petite-caps', 'all-petite-caps', 'unicase'}


def get_element_text(elem, resolve_property, resolve_pseudo_property, capitalize_pat, for_pseudo=None):
    ans = []
    before = get_css_text(elem, resolve_pseudo_property)
    if before:
        ans.append(before)
    if for_pseudo is not None:
        ans.append(tostring(elem, method='text', encoding='unicode', with_tail=False))
    else:
        if elem.text:
            ans.append(elem.text)
        for child in elem.iterchildren():
            t = getattr(child, 'tail', '')
            if t:
                ans.append(t)
    after = get_css_text(elem, resolve_pseudo_property, 'after')
    if after:
        ans.append(after)
    ans = ''.join(ans)
    if for_pseudo is not None:
        tt = resolve_pseudo_property(elem, for_pseudo, 'text-transform')[0].value
        fv = resolve_pseudo_property(elem, for_pseudo, 'font-variant')[0].value
    else:
        tt = resolve_property(elem, 'text-transform')[0].value
        fv = resolve_property(elem, 'font-variant')[0].value
    if fv in caps_variants:
        ans += icu_upper(ans)
    if tt != 'none':
        if tt == 'uppercase':
            ans = icu_upper(ans)
        elif tt == 'lowercase':
            ans = icu_lower(ans)
        elif tt == 'capitalize':
            m = capitalize_pat.search(ans)
            if m is not None:
                ans += icu_upper(m.group())
    return ans


def get_font_dict(elem, resolve_property, pseudo=None):
    ans = {}
    if pseudo is None:
        ff = resolve_property(elem, 'font-family')
    else:
        ff = resolve_property(elem, pseudo, 'font-family')
    ans['font-family'] = tuple(x.value for x in ff)
    for p in 'weight', 'style', 'stretch':
        p = 'font-' + p
        rp = resolve_property(elem, p) if pseudo is None else resolve_property(elem, pseudo, p)
        ans[p] = str(rp[0].value)
    normalize_font_properties(ans)
    return ans


bad_fonts = {'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'sansserif', 'inherit'}
exclude_chars = frozenset(ord_string('\n\r\t'))
skip_tags = {XHTML(x) for x in 'script style title meta link'.split()}
font_keys = {'font-weight', 'font-style', 'font-stretch', 'font-family'}


def prepare_font_rule(cssdict):
    cssdict['font-family'] = frozenset(cssdict['font-family'][:1])
    cssdict['width'] = widths[cssdict['font-stretch']]
    cssdict['weight'] = int(cssdict['font-weight'])


class StatsCollector:

    first_letter_pat = capitalize_pat = None

    def __init__(self, container, do_embed=False):
        if self.first_letter_pat is None:
            StatsCollector.first_letter_pat = self.first_letter_pat = regex.compile(
                r'^[\p{P}]*[\p{L}\p{N}]', regex.VERSION1 | regex.UNICODE)
            StatsCollector.capitalize_pat = self.capitalize_pat = regex.compile(
                r'[\p{L}\p{N}]', regex.VERSION1 | regex.UNICODE)

        self.collect_font_stats(container, do_embed)

    def collect_font_face_rules(self, container, processed, spine_name, sheet, sheet_name):
        if sheet_name in processed:
            sheet_rules = processed[sheet_name]
        else:
            sheet_rules = []
            if sheet_name != spine_name:
                processed[sheet_name] = sheet_rules
            for rule, base_name, rule_index in iterrules(container, sheet_name, rules=sheet, rule_type='FONT_FACE_RULE'):
                cssdict = {}
                for prop in iterdeclaration(rule.style):
                    if prop.name == 'font-family':
                        cssdict['font-family'] = [icu_lower(x) for x in parse_font_family(css_text(prop.propertyValue))]
                    elif prop.name.startswith('font-'):
                        cssdict[prop.name] = prop.propertyValue[0].value
                    elif prop.name == 'src':
                        for val in prop.propertyValue:
                            x = val.value
                            fname = container.href_to_name(x, sheet_name)
                            if container.has_name(fname):
                                cssdict['src'] = fname
                                break
                        else:
                            container.log.warn('The @font-face rule refers to a font file that does not exist in the book: %s' % css_text(prop.propertyValue))
                if 'src' not in cssdict:
                    continue
                ff = cssdict.get('font-family')
                if not ff or ff[0] in bad_fonts:
                    continue
                normalize_font_properties(cssdict)
                prepare_font_rule(cssdict)
                sheet_rules.append(cssdict)
        self.font_rule_map[spine_name].extend(sheet_rules)

    def get_element_font_usage(self, elem, resolve_property, resolve_pseudo_property, font_face_rules, do_embed, font_usage_map, font_spec):
        text = get_element_text(elem, resolve_property, resolve_pseudo_property, self.capitalize_pat)
        if not text:
            return

        def update_usage_for_embed(font, chars):
            if not do_embed:
                return
            ff = [icu_lower(x) for x in font.get('font-family', ())]
            if ff and ff[0] not in bad_fonts:
                key = frozenset(((k, ff[0] if k == 'font-family' else v) for k, v in iteritems(font) if k in font_keys))
                val = font_usage_map.get(key)
                if val is None:
                    val = font_usage_map[key] = {'text': set()}
                    for k in font_keys:
                        val[k] = font[k][0] if k == 'font-family' else font[k]
                val['text'] |= chars
            for ff in font.get('font-family', ()):
                if ff and icu_lower(ff) not in bad_fonts:
                    font_spec.add(ff)

        font = get_font_dict(elem, resolve_property)
        chars = frozenset(ord_string(text)) - exclude_chars
        update_usage_for_embed(font, chars)
        for rule in get_matching_rules(font_face_rules, font):
            self.font_stats[rule['src']] |= chars
        if resolve_pseudo_property(elem, 'first-letter', 'font-family', check_if_pseudo_applies=True):
            font = get_font_dict(elem, resolve_pseudo_property, pseudo='first-letter')
            text = get_element_text(elem, resolve_property, resolve_pseudo_property, self.capitalize_pat, for_pseudo='first-letter')
            m = self.first_letter_pat.search(text.lstrip())
            if m is not None:
                chars = frozenset(ord_string(m.group())) - exclude_chars
                update_usage_for_embed(font, chars)
                for rule in get_matching_rules(font_face_rules, font):
                    self.font_stats[rule['src']] |= chars
        if resolve_pseudo_property(elem, 'first-line', 'font-family', check_if_pseudo_applies=True, check_ancestors=True):
            font = get_font_dict(elem, partial(resolve_pseudo_property, check_ancestors=True), pseudo='first-line')
            text = get_element_text(elem, resolve_property, resolve_pseudo_property, self.capitalize_pat, for_pseudo='first-line')
            chars = frozenset(ord_string(text)) - exclude_chars
            update_usage_for_embed(font, chars)
            for rule in get_matching_rules(font_face_rules, font):
                self.font_stats[rule['src']] |= chars

    def get_font_usage(self, container, spine_name, resolve_property, resolve_pseudo_property, font_face_rules, do_embed):
        root = container.parsed(spine_name)
        for body in root.iterchildren(XHTML('body')):
            for elem in body.iter('*'):
                if elem.tag not in skip_tags:
                    self.get_element_font_usage(
                        elem, resolve_property, resolve_pseudo_property, font_face_rules, do_embed,
                        self.font_usage_map[spine_name], self.font_spec_map[spine_name])

    def collect_font_stats(self, container, do_embed=False):
        self.font_stats = {}
        self.font_usage_map = {}
        self.font_spec_map = {}
        self.font_rule_map = {}
        self.all_font_rules = {}

        processed_sheets = {}
        for name, is_linear in container.spine_names:
            self.font_rule_map[name] = font_face_rules = []
            resolve_property, resolve_pseudo_property, select = resolve_styles(container, name, sheet_callback=partial(
                self.collect_font_face_rules, container, processed_sheets, name))

            for rule in font_face_rules:
                self.all_font_rules[rule['src']] = rule
                if rule['src'] not in self.font_stats:
                    self.font_stats[rule['src']] = set()

            self.font_usage_map[name] = {}
            self.font_spec_map[name] = set()
            self.get_font_usage(container, name, resolve_property, resolve_pseudo_property, font_face_rules, do_embed)
        self.font_stats = {k:{safe_chr(x) for x in v} for k, v in iteritems(self.font_stats)}
        for fum in itervalues(self.font_usage_map):
            for v in itervalues(fum):
                v['text'] = {safe_chr(x) for x in v['text']}


if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    ebook = get_container(sys.argv[-1], default_log)
    from pprint import pprint
    pprint(StatsCollector(ebook, do_embed=True).font_stats)
