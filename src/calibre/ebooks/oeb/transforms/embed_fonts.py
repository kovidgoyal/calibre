#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import logging
from collections import defaultdict

import cssutils
from lxml import etree

from calibre import guess_type
from calibre.ebooks.oeb.base import XPath, CSS_MIME, XHTML
from calibre.ebooks.oeb.transforms.subset import get_font_properties, find_font_face_rules, elem_style
from calibre.utils.filenames import ascii_filename
from calibre.utils.fonts.scanner import font_scanner, NoFonts
from calibre.ebooks.oeb.polish.embed import font_key


def font_families_from_style(style):
    return [unicode(f) for f in style.get('font-family', []) if unicode(f).lower() not in {
        'serif', 'sansserif', 'sans-serif', 'fantasy', 'cursive', 'monospace'}]


def style_key(style):
    style = style.copy()
    style['font-family'] = font_families_from_style(style)[0]
    return font_key(style)


def font_already_embedded(style, newly_embedded_fonts):
    return style_key(style) in newly_embedded_fonts


def used_font(style, embedded_fonts):
    ff = font_families_from_style(style)
    if not ff:
        return False, None
    lnames = {unicode(x).lower() for x in ff}

    matching_set = []

    # Filter on font-family
    for ef in embedded_fonts:
        flnames = {x.lower() for x in ef.get('font-family', [])}
        if not lnames.intersection(flnames):
            continue
        matching_set.append(ef)
    if not matching_set:
        return True, None

    # Filter on font-stretch
    widths = {x:i for i, x in enumerate(('ultra-condensed',
            'extra-condensed', 'condensed', 'semi-condensed', 'normal',
            'semi-expanded', 'expanded', 'extra-expanded', 'ultra-expanded'
            ))}

    width = widths[style.get('font-stretch', 'normal')]
    for f in matching_set:
        f['width'] = widths[style.get('font-stretch', 'normal')]

    min_dist = min(abs(width-f['width']) for f in matching_set)
    if min_dist > 0:
        return True, None
    nearest = [f for f in matching_set if abs(width-f['width']) ==
        min_dist]
    if width <= 4:
        lmatches = [f for f in nearest if f['width'] <= width]
    else:
        lmatches = [f for f in nearest if f['width'] >= width]
    matching_set = (lmatches or nearest)

    # Filter on font-style
    fs = style.get('font-style', 'normal')
    matching_set = [f for f in matching_set if f.get('font-style', 'normal') == fs]

    # Filter on font weight
    fw = int(style.get('font-weight', '400'))
    matching_set = [f for f in matching_set if f.get('weight', 400) == fw]

    if not matching_set:
        return True, None
    return True, matching_set[0]


class EmbedFonts(object):

    '''
    Embed all referenced fonts, if found on system. Must be called after CSS flattening.
    '''

    def __call__(self, oeb, log, opts):
        self.oeb, self.log, self.opts = oeb, log, opts
        self.sheet_cache = {}
        self.find_style_rules()
        self.find_embedded_fonts()
        self.parser = cssutils.CSSParser(loglevel=logging.CRITICAL, log=logging.getLogger('calibre.css'))
        self.warned = set()
        self.warned2 = set()
        self.newly_embedded_fonts = set()

        for item in oeb.spine:
            if not hasattr(item.data, 'xpath'):
                continue
            sheets = []
            for href in XPath('//h:link[@href and @type="text/css"]/@href')(item.data):
                sheet = self.oeb.manifest.hrefs.get(item.abshref(href), None)
                if sheet is not None:
                    sheets.append(sheet)
            if sheets:
                self.process_item(item, sheets)

    def find_embedded_fonts(self):
        '''
        Find all @font-face rules and extract the relevant info from them.
        '''
        self.embedded_fonts = []
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'cssRules'):
                continue
            self.embedded_fonts.extend(find_font_face_rules(item, self.oeb))

    def find_style_rules(self):
        '''
        Extract all font related style information from all stylesheets into a
        dict mapping classes to font properties specified by that class. All
        the heavy lifting has already been done by the CSS flattening code.
        '''
        rules = defaultdict(dict)
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'cssRules'):
                continue
            for i, rule in enumerate(item.data.cssRules):
                if rule.type != rule.STYLE_RULE:
                    continue
                props = {k:v for k,v in
                        get_font_properties(rule).iteritems() if v}
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

    def get_page_sheet(self):
        if self.page_sheet is None:
            manifest = self.oeb.manifest
            id_, href = manifest.generate('page_css', 'page_styles.css')
            self.page_sheet = manifest.add(id_, href, CSS_MIME, data=self.parser.parseString('', validate=False))
            head = self.current_item.data.xpath('//*[local-name()="head"][1]')
            if head:
                href = self.current_item.relhref(href)
                l = etree.SubElement(head[0], XHTML('link'),
                    rel='stylesheet', type=CSS_MIME, href=href)
                l.tail = '\n'
            else:
                self.log.warn('No <head> cannot embed font rules')
        return self.page_sheet

    def process_item(self, item, sheets):
        ff_rules = []
        self.current_item = item
        self.page_sheet = None
        for sheet in sheets:
            if 'page_css' in sheet.id:
                ff_rules.extend(find_font_face_rules(sheet, self.oeb))
                self.page_sheet = sheet

        base = {'font-family':['serif'], 'font-weight': '400',
                'font-style':'normal', 'font-stretch':'normal'}

        for body in item.data.xpath('//*[local-name()="body"]'):
            self.find_usage_in(body, base, ff_rules)

    def find_usage_in(self, elem, inherited_style, ff_rules):
        style = elem_style(self.style_rules, elem.get('class', '') or '', inherited_style)
        for child in elem:
            self.find_usage_in(child, style, ff_rules)
        has_font, existing = used_font(style, ff_rules)
        if not has_font or font_already_embedded(style, self.newly_embedded_fonts):
            return
        if existing is None:
            in_book = used_font(style, self.embedded_fonts)[1]
            if in_book is None:
                # Try to find the font in the system
                added = self.embed_font(style)
                if added is not None:
                    self.newly_embedded_fonts.add(style_key(style))
                    ff_rules.append(added)
                    self.embedded_fonts.append(added)
            else:
                # TODO: Create a page rule from the book rule (cannot use it
                # directly as paths might be different)
                item = in_book['item']
                sheet = self.parser.parseString(in_book['rule'].cssText, validate=False)
                rule = sheet.cssRules[0]
                page_sheet = self.get_page_sheet()
                href = page_sheet.abshref(item.href)
                rule.style.setProperty('src', 'url(%s)' % href)
                ff_rules.append(find_font_face_rules(sheet, self.oeb)[0])
                page_sheet.data.insertRule(rule, len(page_sheet.data.cssRules))

    def embed_font(self, style):
        from calibre.ebooks.oeb.polish.embed import find_matching_font, weight_as_number
        ff = font_families_from_style(style)
        if not ff:
            return
        ff = ff[0]
        if ff in self.warned or ff == 'inherit':
            return
        try:
            fonts = font_scanner.fonts_for_family(ff)
        except NoFonts:
            self.log.warn('Failed to find fonts for family:', ff, 'not embedding')
            self.warned.add(ff)
            return
        weight = weight_as_number(style.get('font-weight', '400'))

        def do_embed(f):
            data = font_scanner.get_font_data(f)
            name = f['full_name']
            ext = 'otf' if f['is_otf'] else 'ttf'
            name = ascii_filename(name).replace(' ', '-').replace('(', '').replace(')', '')
            fid, href = self.oeb.manifest.generate(id=u'font', href=u'fonts/%s.%s'%(name, ext))
            item = self.oeb.manifest.add(fid, href, guess_type('dummy.'+ext)[0], data=data)
            item.unload_data_from_memory()
            page_sheet = self.get_page_sheet()
            href = page_sheet.relhref(item.href)
            css = '''@font-face { font-family: "%s"; font-weight: %s; font-style: %s; font-stretch: %s; src: url(%s) }''' % (
                f['font-family'], f['font-weight'], f['font-style'], f['font-stretch'], href)
            sheet = self.parser.parseString(css, validate=False)
            page_sheet.data.insertRule(sheet.cssRules[0], len(page_sheet.data.cssRules))
            return find_font_face_rules(sheet, self.oeb)[0]

        for f in fonts:
            if f['weight'] == weight and f['font-style'] == style.get('font-style', 'normal') and f['font-stretch'] == style.get('font-stretch', 'normal'):
                self.log('Embedding font %s from %s' % (f['full_name'], f['path']))
                return do_embed(f)
        try:
            f = find_matching_font(fonts, style.get('font-weight', 'normal'), style.get('font-style', 'normal'), style.get('font-stretch', 'normal'))
        except Exception:
            if ff not in self.warned2:
                self.log.exception('Failed to find a matching font for family', ff, 'not embedding')
                self.warned2.add(ff)
                return
        self.log('Embedding font %s from %s' % (f['full_name'], f['path']))
        return do_embed(f)
