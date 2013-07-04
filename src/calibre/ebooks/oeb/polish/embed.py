#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from lxml import etree

from calibre import prints
from calibre.ebooks.oeb.base import XHTML
from calibre.ebooks.oeb.polish.stats import normalize_font_properties
from calibre.utils.filenames import ascii_filename

props = {'font-family':None, 'font-weight':'normal', 'font-style':'normal', 'font-stretch':'normal'}

def matching_rule(font, rules):
    ff = font['font-family']
    if not isinstance(ff, basestring):
        ff = tuple(ff)[0]
    family = icu_lower(ff)
    wt = font['font-weight']
    style = font['font-style']
    stretch = font['font-stretch']

    for rule in rules:
        if rule['font-style'] == style and rule['font-stretch'] == stretch and rule['font-weight'] == wt:
            ff = rule['font-family']
            if not isinstance(ff, basestring):
                ff = tuple(ff)[0]
            if icu_lower(ff) == family:
                return rule

def embed_font(container, font, all_font_rules, report, warned):
    rule = matching_rule(font, all_font_rules)
    ff = font['font-family']
    if not isinstance(ff, basestring):
        ff = ff[0]
    if rule is None:
        from calibre.utils.fonts.scanner import font_scanner, NoFonts
        if ff in warned:
            return
        try:
            fonts = font_scanner.fonts_for_family(ff)
        except NoFonts:
            report(_('Failed to find fonts for family: %s, not embedding') % ff)
            warned.add(ff)
            return
        wt = int(font.get('font-weight', '400'))
        for f in fonts:
            if f['weight'] == wt and f['font-style'] == font.get('font-style', 'normal') and f['font-stretch'] == font.get('font-stretch', 'normal'):
                report('Embedding font %s from %s' % (f['full_name'], f['path']))
                data = font_scanner.get_font_data(f)
                fname = f['full_name']
                ext = 'otf' if f['is_otf'] else 'ttf'
                fname = ascii_filename(fname).replace(' ', '-').replace('(', '').replace(')', '')
                item = container.generate_item('fonts/%s.%s'%(fname, ext), id_prefix='font')
                name = container.href_to_name(item.get('href'), container.opf_name)
                with container.open(name, 'wb') as out:
                    out.write(data)
                href = container.name_to_href(name)
                rule = {k:f.get(k, v) for k, v in props.iteritems()}
                rule['src'] = 'url(%s)' % href
                rule['name'] = name
                return rule
        msg = _('Failed to find font matching: family: %s; weight: %s; style: %s; stretch: %s') % (
            ff, font['font-weight'], font['font-style'], font['font-stretch'])
        if msg not in warned:
            warned.add(msg)
            report(msg)
    else:
        name = rule['src']
        href = container.name_to_href(name)
        rule = {k:ff if k == 'font-family' else rule.get(k, v) for k, v in props.iteritems()}
        rule['src'] = 'url(%s)' % href
        rule['name'] = name
        return rule

def embed_all_fonts(container, stats, report):
    all_font_rules = tuple(stats.all_font_rules.itervalues())
    warned = set()
    rules, nrules = [], []
    modified = set()

    for path in container.spine_items:
        name = container.abspath_to_name(path)
        fu = stats.font_usage_map.get(name, None)
        fs = stats.font_spec_map.get(name, None)
        fr = stats.font_rule_map.get(name, None)
        if None in (fs, fu, fr):
            continue
        fs = {icu_lower(x) for x in fs}
        for font in fu.itervalues():
            if icu_lower(font['font-family']) not in fs:
                continue
            rule = matching_rule(font, fr)
            if rule is None:
                # This font was not already embedded in this HTML file, before
                # processing started
                rule = matching_rule(font, nrules)
                if rule is None:
                    rule = embed_font(container, font, all_font_rules, report, warned)
                    if rule is not None:
                        rules.append(rule)
                        nrules.append(normalize_font_properties(rule.copy()))
                        modified.add(name)
                        stats.font_stats[rule['name']] = font['text']
                else:
                    # This font was previously embedded by this code, update its stats
                    stats.font_stats[rule['name']] |= font['text']
                    modified.add(name)

    if not rules:
        report(_('No embeddable fonts found'))
        return

    # Write out CSS
    rules = [';\n\t'.join('%s: %s' % (
        k, '"%s"' % v if k == 'font-family' else v) for k, v in rule.iteritems() if (k in props and props[k] != v and v != '400') or k == 'src')
        for rule in rules]
    css = '\n\n'.join(['@font-face {\n\t%s\n}' % r for r in rules])
    item = container.generate_item('fonts.css', id_prefix='font_embed')
    name = container.href_to_name(item.get('href'), container.opf_name)
    with container.open(name, 'wb') as out:
        out.write(css.encode('utf-8'))

    # Add link to CSS in all files that need it
    for spine_name in modified:
        root = container.parsed(spine_name)
        head = root.xpath('//*[local-name()="head"][1]')[0]
        href = container.name_to_href(name, spine_name)
        etree.SubElement(head, XHTML('link'), rel='stylesheet', type='text/css', href=href).tail = '\n'
        container.dirty(spine_name)


if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.ebooks.oeb.polish.stats import StatsCollector
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    inbook = sys.argv[-1]
    ebook = get_container(inbook, default_log)
    report = []
    stats = StatsCollector(ebook, do_embed=True)
    embed_all_fonts(ebook, stats, report.append)
    outbook, ext = inbook.rpartition('.')[0::2]
    outbook += '_subset.'+ext
    ebook.commit(outbook)
    prints('\nReport:')
    for msg in report:
        prints(msg)
    print()
    prints('Output written to:', outbook)

