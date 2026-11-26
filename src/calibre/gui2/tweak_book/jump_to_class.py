#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import suppress
from typing import TYPE_CHECKING, NamedTuple, TypedDict, cast

from css_parser.css import CSSRule
from css_selectors.errors import SelectorError
from css_selectors.select import Select

from calibre.ebooks.oeb.parse_utils import barename
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.parsing import parse

if TYPE_CHECKING:
    from css_parser.css import CSSRuleList, CSSStyleRule
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container

    # sourceline_address is the line number and tag names on that line of the tag containing the class
    ClassData = TypedDict('ClassData', {'class': str, 'sourceline_address': tuple[int, list[str]]})


class NoMatchingTagFound(KeyError):
    pass


class NoMatchingRuleFound(KeyError):
    pass


class RuleLocation(NamedTuple):
    rule_address: list[int]
    file_name: str
    style_tag_address: tuple[int, list[str]] | None = None


def rule_matches_elem(rule: CSSStyleRule, elem: _Element, select: Select, class_name: str) -> bool:
    for selector in rule.selectorList:
        if class_name in selector.selectorText:
            with suppress(SelectorError):
                if elem in select(selector.selectorText):
                    return True
    return False


def find_first_rule_that_matches_elem(
    container: Container,
    elem: _Element,
    select: Select,
    class_name: str,
    rules: CSSRuleList,
    current_file_name: str,
    recursion_level: int = 0,
    rule_address: list[int] | None = None,
) -> RuleLocation | None:
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
        elif rule.type in (CSSRule.COMMENT, CSSRule.CHARSET_RULE):
            num_comment_rules += 1
        elif rule.type == CSSRule.MEDIA_RULE:
            res = find_first_rule_that_matches_elem(
                container,
                elem,
                select,
                class_name,
                rule.cssRules,
                current_file_name,
                recursion_level + 1,
                rule_address + [i - num_comment_rules],
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
                res = find_first_rule_that_matches_elem(container, elem, select, class_name, cast('CSSRuleList', sheet.cssRules), sname, recursion_level + 1)
                if res is not None:
                    return res
    return None


def find_first_matching_rule(
    container: Container, html_file_name: str, raw_html: str | bytes, class_data: ClassData, lnum_attr: str = 'data-lnum'
) -> RuleLocation:
    lnum, tags = class_data['sourceline_address']
    class_name = class_data['class']
    root = parse(raw_html, decoder=lambda x: x.decode('utf-8'), line_numbers=True, linenumber_attribute=lnum_attr)
    tags_on_line = root.xpath(f'//*[@{lnum_attr}={lnum}]')
    barenames = [barename(tag.tag) for tag in tags_on_line]
    if barenames[: len(tags)] != tags:
        raise NoMatchingTagFound(f'No tag matching the specification was found in {html_file_name}')
    target_elem = tags_on_line[len(tags) - 1]
    select = Select(root, ignore_inappropriate_pseudo_classes=True)
    for tag in root.iter('*'):
        tag_name = tag.tag
        assert isinstance(tag_name, str)  # iter('*') only yields elements, which have str tags
        tn = barename(tag_name)
        if tn == 'style' and tag.text and tag.get('type', 'text/css') == 'text/css':
            try:
                sheet = container.parse_css(tag.text)
            except Exception:
                continue
            res = find_first_rule_that_matches_elem(container, target_elem, select, class_name, sheet.cssRules, html_file_name)
            if res is not None:
                return res._replace(style_tag_address=(int(cast('str', tag.get(lnum_attr))), ['style']))  # parse() sets lnum_attr on all elements
        elif tn == 'link' and tag.get('href') and tag.get('rel', '').lower() == 'stylesheet':
            sname = container.href_to_name(tag.get('href'), html_file_name)
            if sname is None:
                continue
            try:
                sheet = container.parsed(sname)
            except Exception:
                continue
            if not hasattr(sheet, 'cssRules'):
                continue
            res = find_first_rule_that_matches_elem(container, target_elem, select, class_name, cast('CSSRuleList', sheet.cssRules), sname)
            if res is not None:
                return res
    raise NoMatchingRuleFound(f'No CSS rules that apply to the specified tag in {html_file_name} with the class {class_name} found')


def develop() -> None:
    container = get_container('/t/demo.epub', tweak_mode=True)
    fname = 'index_split_002.html'
    data: ClassData = {'class': 'xxx', 'sourceline_address': (13, ['body'])}
    print(find_first_matching_rule(container, fname, container.open(fname).read(), data))
