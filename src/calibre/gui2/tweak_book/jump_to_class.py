#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import suppress
from css_parser.css import CSSRule
from typing import List, NamedTuple, Optional, Tuple

from calibre.ebooks.oeb.parse_utils import barename
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.parsing import parse
from css_selectors import Select, SelectorError


class NoMatchingTagFound(KeyError):
    pass


class NoMatchingRuleFound(KeyError):
    pass


class RuleLocation(NamedTuple):
    rule_address: List[int]
    file_name: str
    style_tag_address: Optional[Tuple[int, List[int]]] = None


def rule_matches_elem(rule, elem, select, class_name):
    for selector in rule.selectorList:
        if class_name in selector.selectorText:
            with suppress(SelectorError):
                if elem in select(selector.selectorText):
                    return True
    return False


def find_first_rule_that_matches_elem(
    container,
    elem,
    select,
    class_name,
    rules,
    current_file_name,
    recursion_level=0,
    rule_address=None
):
    # iterate over rules handling @import and @media rules returning a rule
    # address for matching rule
    if recursion_level > 16:
        return None
    rule_address = rule_address or []
    num_comment_rules = 0
    for i, rule in enumerate(rules):
        if rule.type == CSSRule.STYLE_RULE:
            if rule_matches_elem(rule, elem, select, class_name):
                return RuleLocation(rule_address + [i - num_comment_rules], current_file_name)
        elif rule.type == CSSRule.COMMENT:
            num_comment_rules += 1
        elif rule.type == CSSRule.MEDIA_RULE:
            res = find_first_rule_that_matches_elem(
                container, elem, select, class_name, rule.cssRules,
                current_file_name, recursion_level + 1, rule_address + [i - num_comment_rules]
            )
            if res is not None:
                return res
        elif rule.type == CSSRule.IMPORT_RULE:
            if not rule.href:
                continue
            sname = container.href_to_name(rule.href, current_file_name)
            if sname:
                try:
                    sheet = container.parsed(sname)
                except Exception:
                    continue
                if not hasattr(sheet, 'cssRules'):
                    continue
                res = find_first_rule_that_matches_elem(
                    container, elem, select, class_name, sheet.cssRules, sname,
                    recursion_level + 1
                )
                if res is not None:
                    return res
    return None


def find_first_matching_rule(
    container, html_file_name, raw_html, class_data, lnum_attr='data-lnum'
):
    lnum, tags = class_data['sourceline_address']
    class_name = class_data['class']
    root = parse(
        raw_html,
        decoder=lambda x: x.decode('utf-8'),
        line_numbers=True,
        linenumber_attribute=lnum_attr
    )
    tags_on_line = root.xpath(f'//*[@{lnum_attr}={lnum}]')
    barenames = [barename(tag.tag) for tag in tags_on_line]
    if barenames[:len(tags)] != tags:
        raise NoMatchingTagFound(
            f'No tag matching the specification was found in {html_file_name}'
        )
    target_elem = tags_on_line[len(tags) - 1]
    select = Select(root, ignore_inappropriate_pseudo_classes=True)
    for tag in root.iter('*'):
        tn = barename(tag.tag)
        if tn == 'style' and tag.text and tag.get('type', 'text/css') == 'text/css':
            try:
                sheet = container.parse_css(tag.text)
            except Exception:
                continue
            res = find_first_rule_that_matches_elem(
                container, target_elem, select, class_name, sheet.cssRules,
                html_file_name
            )
            if res is not None:
                return res._replace(style_tag_address=(int(tag.get(lnum_attr)), ['style']))
        elif tn == 'link' and tag.get('href') and tag.get('rel') == 'stylesheet':
            sname = container.href_to_name(tag.get('href'), html_file_name)
            try:
                sheet = container.parsed(sname)
            except Exception:
                continue
            if not hasattr(sheet, 'cssRules'):
                continue
            res = find_first_rule_that_matches_elem(
                container, target_elem, select, class_name, sheet.cssRules, sname
            )
            if res is not None:
                return res
    raise NoMatchingRuleFound(
        f'No CSS rules that apply to the specified tag in {html_file_name} with the class {class_name} found'
    )


def develop():
    container = get_container('/t/demo.epub', tweak_mode=True)
    fname = 'index_split_002.html'
    data = {'class': 'xxx', 'sourceline_address': (13, ['body'])}
    print(
        find_first_matching_rule(
            container, fname,
            container.open(fname).read(), data
        )
    )
