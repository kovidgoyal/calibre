#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import numbers
from collections import Counter

from calibre.ebooks.oeb.base import barename, XPath
from polyglot.builtins import iteritems


class RemoveAdobeMargins:
    '''
    Remove margins specified in Adobe's page templates.
    '''

    def __call__(self, oeb, log, opts):
        self.oeb, self.opts, self.log = oeb, opts, log

        for item in self.oeb.manifest:
            if item.media_type in {
                'application/vnd.adobe-page-template+xml', 'application/vnd.adobe.page-template+xml',
                'application/adobe-page-template+xml', 'application/adobe.page-template+xml',
            } and hasattr(item.data, 'xpath'):
                self.log('Removing page margins specified in the'
                        ' Adobe page template')
                for elem in item.data.xpath(
                        '//*[@margin-bottom or @margin-top '
                        'or @margin-left or @margin-right]'):
                    for margin in ('left', 'right', 'top', 'bottom'):
                        attr = 'margin-'+margin
                        elem.attrib.pop(attr, None)


class NegativeTextIndent(Exception):
    pass


class RemoveFakeMargins:

    '''
    Remove left and right margins from paragraph/divs if the same margin is specified
    on almost all the elements at that level.

    Must be called only after CSS flattening
    '''

    def __call__(self, oeb, log, opts):
        if not opts.remove_fake_margins:
            return
        self.oeb, self.log, self.opts = oeb, log, opts
        stylesheet = None
        self.levels = {}
        self.stats = {}
        self.selector_map = {}

        stylesheet = self.oeb.manifest.main_stylesheet
        if stylesheet is None:
            return

        self.log('Removing fake margins...')

        stylesheet = stylesheet.data

        from css_parser.css import CSSRule
        for rule in stylesheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
            self.selector_map[rule.selectorList.selectorText] = rule.style

        self.find_levels()

        for level in self.levels:
            try:
                self.process_level(level)
            except NegativeTextIndent:
                self.log.debug('Negative text indent detected at level '
                        ' %s, ignoring this level'%level)

    def get_margins(self, elem):
        cls = elem.get('class', None)
        if cls:
            style = self.selector_map.get('.'+cls, None)
            if style:
                try:
                    ti = style['text-indent']
                except:
                    pass
                else:
                    if ((hasattr(ti, 'startswith') and ti.startswith('-')) or
                            isinstance(ti, numbers.Number) and ti < 0):
                        raise NegativeTextIndent()
                return style.marginLeft, style.marginRight, style
        return '', '', None

    def process_level(self, level):
        elems = self.levels[level]
        self.stats[level+'_left'] = Counter()
        self.stats[level+'_right'] = Counter()

        for elem in elems:
            lm, rm = self.get_margins(elem)[:2]
            self.stats[level+'_left'][lm] += 1
            self.stats[level+'_right'][rm] += 1

        self.log.debug(level, ' left margin stats:', self.stats[level+'_left'])
        self.log.debug(level, ' right margin stats:', self.stats[level+'_right'])

        remove_left = self.analyze_stats(self.stats[level+'_left'])
        remove_right = self.analyze_stats(self.stats[level+'_right'])

        if remove_left:
            mcl = self.stats[level+'_left'].most_common(1)[0][0]
            self.log('Removing level %s left margin of:'%level, mcl)

        if remove_right:
            mcr = self.stats[level+'_right'].most_common(1)[0][0]
            self.log('Removing level %s right margin of:'%level, mcr)

        if remove_left or remove_right:
            for elem in elems:
                lm, rm, style = self.get_margins(elem)
                if remove_left and lm == mcl:
                    style.removeProperty('margin-left')
                if remove_right and rm == mcr:
                    style.removeProperty('margin-right')

    def find_levels(self):

        def level_of(elem, body):
            ans = 1
            while elem.getparent() is not body:
                ans += 1
                elem = elem.getparent()
            return ans

        paras = XPath('descendant::h:p|descendant::h:div')

        for item in self.oeb.spine:
            body = XPath('//h:body')(item.data)
            if not body:
                continue
            body = body[0]

            for p in paras(body):
                level = level_of(p, body)
                level = '%s_%d'%(barename(p.tag), level)
                if level not in self.levels:
                    self.levels[level] = []
                self.levels[level].append(p)

        remove = set()
        for k, v in iteritems(self.levels):
            num = len(v)
            self.log.debug('Found %d items of level:'%num, k)
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

    def analyze_stats(self, stats):
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
        return most_common_count/total > 0.95
