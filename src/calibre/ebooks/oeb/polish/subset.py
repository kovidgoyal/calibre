#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys

from calibre import prints
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS, XPath
from calibre.ebooks.oeb.polish.container import OEB_FONTS
from calibre.utils.fonts.sfnt.subset import subset
from calibre.utils.fonts.utils import get_font_names

def remove_font_face_rules(container, sheet, remove_names):
    changed = False
    for rule in tuple(sheet.cssRules):
        if rule.type != rule.FONT_FACE_RULE:
            continue
        try:
            uri = rule.style.getProperty('src').propertyValue[0].uri
        except (IndexError, KeyError, AttributeError, TypeError, ValueError):
            continue
        name = container.href_to_name(uri)
        if name in remove_names:
            sheet.deleteRule(rule)
            changed = True
    return changed

def subset_all_fonts(container, font_stats, report):
    remove = set()
    total_old = total_new = 0
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_FONTS or name.rpartition('.')[-1].lower() in {'otf', 'ttf'}:
            chars = font_stats.get(name, set())
            path = container.name_path_map[name]
            total_old += os.path.getsize(path)
            if not chars:
                remove.add(name)
                report('Removed unused font: %s'%name)
                continue
            with open(path, 'r+b') as f:
                raw = f.read()
                font_name = get_font_names(raw)[-1]
                warnings = []
                container.log('Subsetting font: %s'%font_name)
                nraw, old_sizes, new_sizes = subset(raw, chars,
                                                   warnings=warnings)
                for w in warnings:
                    container.log.warn(w)
                olen = sum(old_sizes.itervalues())
                nlen = sum(new_sizes.itervalues())
                total_new += len(nraw)
                report('Decreased the font %s to %.1f%% of its original size'%
                       (font_name, nlen/olen * 100))
                f.seek(0), f.truncate(), f.write(nraw)

    for name in remove:
        container.remove_item(name)

    if remove:
        for name, mt in container.mime_map.iteritems():
            if mt in OEB_STYLES:
                sheet = container.parsed(name)
                if remove_font_face_rules(container, sheet, remove):
                    container.dirty(name)
            elif mt in OEB_DOCS:
                for style in XPath('//h:style')(container.parsed(name)):
                    if style.get('type', 'text/css') == 'text/css' and style.text:
                        sheet = container.parse_css(style.text, name)
                        if remove_font_face_rules(container, sheet, remove):
                            style.text = sheet.cssText
                            container.dirty(name)
    report('Reduced total font size to %.1f%% of original'%(
        total_new/total_old*100))

if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.ebooks.oeb.polish.stats import StatsCollector
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    inbook = sys.argv[-1]
    ebook = get_container(inbook, default_log)
    report = []
    stats = StatsCollector(ebook).font_stats
    subset_all_fonts(ebook, stats, report.append)
    outbook, ext = inbook.rpartition('.')[0::2]
    outbook += '_subset.'+ext
    ebook.commit(outbook)
    prints('\nReport:')
    for msg in report:
        prints(msg)
    print()
    prints('Output written to:', outbook)

