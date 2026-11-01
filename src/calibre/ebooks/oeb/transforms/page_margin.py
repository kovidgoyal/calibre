#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>

import numbers
from collections import Counter
from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.oeb.base import XPath, barename

if TYPE_CHECKING:
    from optparse import Values

    from css_parser.css import CSSStyleDeclaration
    from lxml.etree import _Element

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class RemoveAdobeMargins:
    """
    Remove margins specified in Adobe's page templates.
    """

    def __call__(self, oeb: OEBBook, log: Log, opts: Values | OptionValues) -> None:
        self.oeb, self.opts, self.log = oeb, opts, log

        for item in self.oeb.manifest:
            if item.media_type in {
                'application/vnd.adobe-page-template+xml',
                'application/vnd.adobe.page-template+xml',
                'application/adobe-page-template+xml',
                'application/adobe.page-template+xml',
            } and isinstance(root := item.data, etree._Element):
                self.log('Removing page margins specified in the Adobe page template')
                for elem in root.xpath('//*[@margin-bottom or @margin-top or @margin-left or @margin-right]'):
                    for margin in ('left', 'right', 'top', 'bottom'):
                        attr = 'margin-' + margin
                        elem.attrib.pop(attr, None)


class NegativeTextIndent(Exception):
    pass


class RemoveFakeMargins:
    """
    Remove left and right margins from paragraph/divs if the same margin is specified
    on almost all the elements at that level.

    Must be called only after CSS flattening
    """

    def __call__(self, oeb: OEBBook, log: Log, opts: Values | OptionValues) -> None:
        if not opts.remove_fake_margins:
            return
        self.oeb, self.log, self.opts = oeb, log, opts
        stylesheet = None
        self.levels: dict[str, list[_Element]] = {}
        self.stats: dict[str, Counter[str]] = {}
        self.selector_map: dict[str, CSSStyleDeclaration] = {}

        stylesheet = self.oeb.manifest.main_stylesheet
        if stylesheet is None:
            return

        self.log('Removing fake margins...')

        from css_parser.css import CSSRule, CSSStyleSheet

        sheet = stylesheet.data
        assert isinstance(sheet, CSSStyleSheet)  # main_stylesheet has a media type in OEB_STYLES

        for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
            self.selector_map[rule.selectorList.selectorText] = rule.style

        self.find_levels()

        for level in self.levels:
            try:
                self.process_level(level)
            except NegativeTextIndent:
                self.log.debug(f'Negative text indent detected at level  {level}, ignoring this level')

    def get_margins(self, elem: _Element) -> tuple[str, str, CSSStyleDeclaration | None]:
        cls = elem.get('class', None)
        if cls:
            style = self.selector_map.get('.' + cls, None)
            if style:
                try:
                    ti = style['text-indent']
                except Exception:
                    pass
                else:
                    if (hasattr(ti, 'startswith') and ti.startswith('-')) or (isinstance(ti, numbers.Number) and ti < 0):
                        raise NegativeTextIndent()
                return style.marginLeft, style.marginRight, style
        return '', '', None

    def process_level(self, level: str) -> None:
        elems = self.levels[level]
        self.stats[level + '_left'] = Counter()
        self.stats[level + '_right'] = Counter()

        for elem in elems:
            lm, rm = self.get_margins(elem)[:2]
            self.stats[level + '_left'][lm] += 1
            self.stats[level + '_right'][rm] += 1

        self.log.debug(level, ' left margin stats:', self.stats[level + '_left'])
        self.log.debug(level, ' right margin stats:', self.stats[level + '_right'])

        remove_left = self.analyze_stats(self.stats[level + '_left'])
        remove_right = self.analyze_stats(self.stats[level + '_right'])

        if remove_left:
            mcl = self.stats[level + '_left'].most_common(1)[0][0]
            self.log(f'Removing level {level} left margin of:', mcl)

        if remove_right:
            mcr = self.stats[level + '_right'].most_common(1)[0][0]
            self.log(f'Removing level {level} right margin of:', mcr)

        if remove_left or remove_right:
            for elem in elems:
                lm, rm, style = self.get_margins(elem)
                # style is None only when the margins are '', which are never removed
                if remove_left and lm == mcl:
                    assert style is not None
                    style.removeProperty('margin-left')
                if remove_right and rm == mcr:
                    assert style is not None
                    style.removeProperty('margin-right')

    def find_levels(self) -> None:

        def level_of(elem: _Element, body: _Element) -> int:
            ans = 1
            while elem.getparent() is not body:
                ans += 1
                elem = elem.getparent()  # ty: ignore[invalid-assignment] elem is a descendant of body
            return ans

        paras = XPath('descendant::h:p|descendant::h:div')

        for item in self.oeb.spine:
            root = item.data
            assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
            body = XPath('//h:body')(root)
            if not body:
                continue
            body = body[0]

            for p in paras(body):
                level = level_of(p, body)
                level = f'{barename(p.tag)}_{level}'
                if level not in self.levels:
                    self.levels[level] = []
                self.levels[level].append(p)

        remove: set[str] = set()
        for k, v in self.levels.items():
            num = len(v)
            self.log.debug(f'Found {num} items of level:', k)
            level = int(k.split('_')[-1])
            tag = k.split('_')[0]
            if tag == 'p' and num < 25:
                remove.add(k)
            if tag == 'div':
                if level > 2 and num < 25:
                    remove.add(k)
                elif level < 3:
                    # Check each level < 3 element and only keep those
                    # that have many child paras
                    for elem in list(v):
                        children = len(paras(elem))
                        if children < 5:
                            v.remove(elem)

        for k in remove:
            self.levels.pop(k)
            self.log.debug('Ignoring level', k)

    def analyze_stats(self, stats: Counter[str]) -> bool:

        if not stats:
            return False
        mc = stats.most_common(1)
        if len(mc) > 1:
            return False
        mc = mc[0]
        most_common, most_common_count = mc
        if not most_common or most_common == '0':
            return False
        total = sum(stats.values())
        # True if greater than 95% of elements have the same margin
        return most_common_count / total > 0.95
