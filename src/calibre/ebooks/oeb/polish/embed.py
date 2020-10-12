#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from polyglot.builtins import map

from lxml import etree

from calibre import prints
from calibre.ebooks.oeb.base import XHTML
from calibre.utils.filenames import ascii_filename
from polyglot.builtins import iteritems, itervalues, string_or_bytes

props = {'font-family':None, 'font-weight':'normal', 'font-style':'normal', 'font-stretch':'normal'}


def matching_rule(font, rules):
    ff = font['font-family']
    if not isinstance(ff, string_or_bytes):
        ff = tuple(ff)[0]
    family = icu_lower(ff)
    wt = font['font-weight']
    style = font['font-style']
    stretch = font['font-stretch']

    for rule in rules:
        if rule['font-style'] == style and rule['font-stretch'] == stretch and rule['font-weight'] == wt:
            ff = rule['font-family']
            if not isinstance(ff, string_or_bytes):
                ff = tuple(ff)[0]
            if icu_lower(ff) == family:
                return rule


def format_fallback_match_report(matched_font, font_family, css_font, report):
    msg = _('Could not find a font in the "%s" family exactly matching the CSS font specification,'
            ' will embed a fallback font instead. CSS font specification:') % font_family
    msg += '\n\n* font-weight: %s' % css_font.get('font-weight', 'normal')
    msg += '\n* font-style: %s' % css_font.get('font-style', 'normal')
    msg += '\n* font-stretch: %s' % css_font.get('font-stretch', 'normal')
    msg += '\n\n' + _('Matched font specification:')
    msg += '\n' + matched_font['path']
    msg += '\n\n* font-weight: %s' % matched_font.get('font-weight', 'normal').strip()
    msg += '\n* font-style: %s' % matched_font.get('font-style', 'normal').strip()
    msg += '\n* font-stretch: %s' % matched_font.get('font-stretch', 'normal').strip()
    report(msg)
    report('')


def stretch_as_number(val):
    try:
        return int(val)
    except Exception:
        pass
    try:
        return ('ultra-condensed', 'extra-condensed', 'condensed', 'semi-condensed',
         'normal', 'semi-expanded', 'expanded', 'extra-expanded',
         'ultra-expanded').index(val)
    except Exception:
        return 4  # normal


def filter_by_stretch(fonts, val):
    val = stretch_as_number(val)
    stretch_map = [stretch_as_number(f['font-stretch']) for f in fonts]
    equal = [f for i, f in enumerate(fonts) if stretch_map[i] == val]
    if equal:
        return equal
    condensed = [i for i in range(len(fonts)) if stretch_map[i] <= 4]
    expanded = [i for i in range(len(fonts)) if stretch_map[i] > 4]
    if val <= 4:
        candidates = condensed or expanded
    else:
        candidates = expanded or condensed
    distance_map = {i:abs(stretch_map[i] - val) for i in candidates}
    min_dist = min(itervalues(distance_map))
    return [fonts[i] for i in candidates if distance_map[i] == min_dist]


def filter_by_style(fonts, val):
    order = {
        'normal':('normal', 'oblique', 'italic'),
        'italic':('italic', 'oblique', 'normal'),
        'oblique':('oblique', 'italic', 'normal'),
    }
    if val not in order:
        val = 'normal'
    for q in order[val]:
        ans = [f for f in fonts if f['font-style'] == q]
        if ans:
            return ans
    return fonts


def weight_as_number(wt):
    try:
        return int(wt)
    except Exception:
        return {'normal':400, 'bold':700}.get(wt, 400)


def filter_by_weight(fonts, val):
    val = weight_as_number(val)
    weight_map = [weight_as_number(f['font-weight']) for f in fonts]
    equal = [f for i, f in enumerate(fonts) if weight_map[i] == val]
    if equal:
        return equal
    rmap = {w:i for i, w in enumerate(weight_map)}
    below = [i for i in range(len(fonts)) if weight_map[i] < val]
    above = [i for i in range(len(fonts)) if weight_map[i] > val]
    if val < 400:
        candidates = below or above
    elif val > 500:
        candidates = above or below
    elif val == 400:
        if 500 in rmap:
            return [fonts[rmap[500]]]
        candidates = below or above
    else:
        if 400 in rmap:
            return [fonts[rmap[400]]]
        candidates = below or above
    distance_map = {i:abs(weight_map[i] - val) for i in candidates}
    min_dist = min(itervalues(distance_map))
    return [fonts[i] for i in candidates if distance_map[i] == min_dist]


def find_matching_font(fonts, weight='normal', style='normal', stretch='normal'):
    # See https://www.w3.org/TR/css-fonts-3/#font-style-matching
    # We dont implement the unicode character range testing
    # We also dont implement bolder, lighter
    for f, q in ((filter_by_stretch, stretch), (filter_by_style, style), (filter_by_weight, weight)):
        fonts = f(fonts, q)
        if len(fonts) == 1:
            return fonts[0]
    return fonts[0]


def do_embed(container, font, report):
    from calibre.utils.fonts.scanner import font_scanner
    report('Embedding font %s from %s' % (font['full_name'], font['path']))
    data = font_scanner.get_font_data(font)
    fname = font['full_name']
    ext = 'otf' if font['is_otf'] else 'ttf'
    fname = ascii_filename(fname).replace(' ', '-').replace('(', '').replace(')', '')
    item = container.generate_item('fonts/%s.%s'%(fname, ext), id_prefix='font')
    name = container.href_to_name(item.get('href'), container.opf_name)
    with container.open(name, 'wb') as out:
        out.write(data)
    href = container.name_to_href(name)
    rule = {k:font.get(k, v) for k, v in iteritems(props)}
    rule['src'] = 'url(%s)' % href
    rule['name'] = name
    return rule


def embed_font(container, font, all_font_rules, report, warned):
    rule = matching_rule(font, all_font_rules)
    ff = font['font-family']
    if not isinstance(ff, string_or_bytes):
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
        wt = weight_as_number(font.get('font-weight'))
        for f in fonts:
            if f['weight'] == wt and f['font-style'] == font.get('font-style', 'normal') and f['font-stretch'] == font.get('font-stretch', 'normal'):
                return do_embed(container, f, report)
        f = find_matching_font(fonts, font.get('font-weight', '400'), font.get('font-style', 'normal'), font.get('font-stretch', 'normal'))
        wkey = ('fallback-font', ff, wt, font.get('font-style'), font.get('font-stretch'))
        if wkey not in warned:
            warned.add(wkey)
            format_fallback_match_report(f, ff, font, report)
        return do_embed(container, f, report)
    else:
        name = rule['src']
        href = container.name_to_href(name)
        rule = {k:ff if k == 'font-family' else rule.get(k, v) for k, v in iteritems(props)}
        rule['src'] = 'url(%s)' % href
        rule['name'] = name
        return rule


def font_key(font):
    return tuple(map(font.get, 'font-family font-weight font-style font-stretch'.split()))


def embed_all_fonts(container, stats, report):
    all_font_rules = tuple(itervalues(stats.all_font_rules))
    warned = set()
    rules, nrules = [], {}
    modified = set()

    for path in container.spine_items:
        name = container.abspath_to_name(path)
        fu = stats.font_usage_map.get(name, None)
        fs = stats.font_spec_map.get(name, None)
        fr = stats.font_rule_map.get(name, None)
        if None in (fs, fu, fr):
            continue
        fs = {icu_lower(x) for x in fs}
        for font in itervalues(fu):
            if icu_lower(font['font-family']) not in fs:
                continue
            rule = matching_rule(font, fr)
            if rule is None:
                # This font was not already embedded in this HTML file, before
                # processing started
                key = font_key(font)
                rule = nrules.get(key)
                if rule is None:
                    rule = embed_font(container, font, all_font_rules, report, warned)
                    if rule is not None:
                        rules.append(rule)
                        nrules[key] = rule
                        modified.add(name)
                        stats.font_stats[rule['name']] = font['text']
                else:
                    # This font was previously embedded by this code, update its stats
                    stats.font_stats[rule['name']] |= font['text']
                    modified.add(name)

    if not rules:
        report(_('No embeddable fonts found'))
        return False

    # Write out CSS
    rules = [';\n\t'.join('%s: %s' % (
        k, '"%s"' % v if k == 'font-family' else v) for k, v in iteritems(rulel) if (k in props and props[k] != v and v != '400') or k == 'src')
        for rulel in rules]
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
    return True


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
