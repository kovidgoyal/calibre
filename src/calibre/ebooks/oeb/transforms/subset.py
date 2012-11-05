#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import defaultdict

from calibre.ebooks.oeb.base import urlnormalize
from calibre.utils.fonts.subset import subset, NoGlyphs, UnsupportedFont

class SubsetFonts(object):

    '''
    Subset all embedded fonts. Must be run after CSS flattening, as it requires
    CSS normalization and flattening to work.
    '''

    def __call__(self, oeb, log, opts):
        self.oeb, self.log, self.opts = oeb, log, opts

        self.find_embedded_fonts()
        if not self.embedded_fonts:
            self.log.debug('No embedded fonts found')
            return
        self.find_style_rules()
        self.find_font_usage()

        totals = [0, 0]

        def remove(font):
            totals[1] += len(font['item'].data)
            self.oeb.manifest.remove(font['item'])
            font['rule'].parentStyleSheet.deleteRule(font['rule'])

        for font in self.embedded_fonts:
            if not font['chars']:
                self.log('The font %s is unused. Removing it.'%font['src'])
                remove(font)
                continue
            try:
                raw, old_stats, new_stats = subset(font['item'].data, font['chars'])
            except NoGlyphs:
                self.log('The font %s has no used glyphs. Removing it.'%font['src'])
                remove(font)
                continue
            except UnsupportedFont as e:
                self.log.warn('The font %s is unsupported for subsetting. %s'%(
                    font['src'], e))
                sz = len(font['item'].data)
                totals[0] += sz
                totals[1] += sz
            else:
                font['item'].data = raw
                nlen = sum(new_stats.itervalues())
                olen = sum(old_stats.itervalues())
                self.log('Decreased the font %s to %.1f%% of its original size'%
                        (font['src'], nlen/olen *100))
                totals[0] += nlen
                totals[1] += olen

            font['item'].unload_data_from_memory()

        if totals[0]:
            self.log('Reduced total font size to %.1f%% of original'%
                    (totals[0]/totals[1] * 100))

    def get_font_properties(self, rule, default=None):
        '''
        Given a CSS rule, extract normalized font properties from
        it. Note that shorthand font property should already have been expanded
        by the CSS flattening code.
        '''
        props = {}
        s = rule.style
        for q in ('font-family', 'src', 'font-weight', 'font-stretch',
                'font-style'):
            g = 'uri' if q == 'src' else 'value'
            try:
                val = s.getProperty(q).propertyValue[0]
                val = getattr(val, g)
                if q == 'font-family':
                    val = [x.value for x in s.getProperty(q).propertyValue]
                    if val and val[0] == 'inherit':
                        val = None
            except (IndexError, KeyError, AttributeError, TypeError, ValueError):
                val = None if q in {'src', 'font-family'} else default
            if q in {'font-weight', 'font-stretch', 'font-style'}:
                val = val.lower() if val else val
                if val == 'inherit':
                    val = default
            if q == 'font-weight':
                val = {'normal':'400', 'bold':'700'}.get(val, val)
                if val not in {'100', '200', '300', '400', '500', '600', '700',
                        '800', '900', 'bolder', 'lighter'}:
                    val = default
                if val == 'normal': val = '400'
            elif q == 'font-style':
                if val not in {'normal', 'italic', 'oblique'}:
                    val = default
            elif q == 'font-stretch':
                if val not in { 'normal', 'ultra-condensed', 'extra-condensed',
                        'condensed', 'semi-condensed', 'semi-expanded',
                        'expanded', 'extra-expanded', 'ultra-expanded'}:
                    val = default
            props[q] = val
        return props

    def find_embedded_fonts(self):
        '''
        Find all @font-face rules and extract the relevant info from them.
        '''
        self.embedded_fonts = []
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'cssRules'): continue
            for i, rule in enumerate(item.data.cssRules):
                if rule.type != rule.FONT_FACE_RULE:
                    continue
                props = self.get_font_properties(rule, default='normal')
                if not props['font-family'] or not props['src']:
                    continue

                path = item.abshref(props['src'])
                ff = self.oeb.manifest.hrefs.get(urlnormalize(path), None)
                if not ff:
                    continue
                props['item'] = ff
                if props['font-weight'] in {'bolder', 'lighter'}:
                    props['font-weight'] = '400'
                props['weight'] = int(props['font-weight'])
                props['chars'] = set()
                props['rule'] = rule
                self.embedded_fonts.append(props)

    def find_style_rules(self):
        '''
        Extract all font related style information from all stylesheets into a
        dict mapping classes to font properties specified by that class. All
        the heavy lifting has already been done by the CSS flattening code.
        '''
        rules = defaultdict(dict)
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'cssRules'): continue
            for i, rule in enumerate(item.data.cssRules):
                if rule.type != rule.STYLE_RULE:
                    continue
                props = {k:v for k,v in
                        self.get_font_properties(rule).iteritems() if v}
                if not props:
                    continue
                for sel in rule.selectorList:
                    sel = sel.selectorText
                    if sel and sel.startswith('.'):
                        # We dont care about pseudo-selectors as the worst that
                        # can happen is some extra characters will remain in
                        # the font
                        sel = sel.partition(':')[0]
                        rules[sel[1:]].update(props)

        self.style_rules = dict(rules)

    def find_font_usage(self):
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'xpath'): continue
            for body in item.data.xpath('//*[local-name()="body"]'):
                base = {'font-family':['serif'], 'font-weight': '400',
                        'font-style':'normal', 'font-stretch':'normal'}
                self.find_usage_in(body, base)

    def elem_style(self, cls, inherited_style):
        '''
        Find the effective style for the given element.
        '''
        classes = cls.split()
        style = inherited_style.copy()
        for cls in classes:
            style.update(self.style_rules.get(cls, {}))
        wt = style.get('font-weight', None)
        pwt = inherited_style.get('font-weight', '400')
        if wt == 'bolder':
            style['font-weight'] = {
                    '100':'400',
                    '200':'400',
                    '300':'400',
                    '400':'700',
                    '500':'700',
                    }.get(pwt, '900')
        elif wt == 'lighter':
            style['font-weight'] = {
                    '600':'400', '700':'400',
                    '800':'700', '900':'700'}.get(pwt, '100')

        return style

    def used_font(self, style):
        '''
        Given a style find the embedded font that matches it. Returns None if
        no match is found ( can happen if not family matches).
        '''
        ff = style.get('font-family', [])
        lnames = {x.lower() for x in ff}
        matching_set = []

        # Filter on font-family
        for ef in self.embedded_fonts:
            flnames = {x.lower() for x in ef.get('font-family', [])}
            if not lnames.intersection(flnames):
                continue
            matching_set.append(ef)
        if not matching_set:
            return None

        # Filter on font-stretch
        widths = {x:i for i, x in enumerate(( 'ultra-condensed',
                'extra-condensed', 'condensed', 'semi-condensed', 'normal',
                'semi-expanded', 'expanded', 'extra-expanded', 'ultra-expanded'
                ))}

        width = widths[style.get('font-stretch', 'normal')]
        for f in matching_set:
            f['width'] = widths[style.get('font-stretch', 'normal')]

        min_dist = min(abs(width-f['width']) for f in matching_set)
        nearest = [f for f in matching_set if abs(width-f['width']) ==
            min_dist]
        if width <= 4:
            lmatches = [f for f in nearest if f['width'] <= width]
        else:
            lmatches = [f for f in nearest if f['width'] >= width]
        matching_set = (lmatches or nearest)

        # Filter on font-style
        fs = style.get('font-style', 'normal')
        order = {
                'oblique':['oblique', 'italic', 'normal'],
                'normal':['normal', 'oblique', 'italic']
            }.get(fs, ['italic', 'oblique', 'normal'])
        for q in order:
            matches = [f for f in matching_set if f.get('font-style', 'normal')
                    == q]
            if matches:
                matching_set = matches
                break

        # Filter on font weight
        fw = int(style.get('font-weight', '400'))
        if fw == 400:
            q = [400, 500, 300, 200, 100, 600, 700, 800, 900]
        elif fw == 500:
            q = [500, 400, 300, 200, 100, 600, 700, 800, 900]
        elif fw < 400:
            q = [fw] + list(xrange(fw-100, -100, -100)) + list(xrange(fw+100,
                100, 1000))
        else:
            q = [fw] + list(xrange(fw+100, 100, 1000)) + list(xrange(fw-100,
                -100, -100))
        for wt in q:
            matches = [f for f in matching_set if f['weight'] == wt]
            if matches:
                return matches[0]

    def find_chars(self, elem):
        ans = set()
        if elem.text:
            ans |= set(elem.text)
        for child in elem:
            if child.tail:
                ans |= set(child.tail)
        return ans

    def find_usage_in(self, elem, inherited_style):
        style = self.elem_style(elem.get('class', ''), inherited_style)
        for child in elem:
            self.find_usage_in(child, style)
        font = self.used_font(style)
        if font:
            chars = self.find_chars(elem)
            if chars:
                font['chars'] |= chars


