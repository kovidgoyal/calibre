#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, NamedTuple, TypedDict, cast

from kgcss import GroupingRule, ImportRule, Select, SelectorError, StyleRule, Stylesheet

from calibre.ebooks.oeb.parse_utils import barename
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.parsing import parse

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kgcss import Rule
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


def rule_matches_elem(rule: StyleRule, elem: _Element, select: Select[_Element], class_name: str) -> bool:
    class_name = class_name.lower()
    for selector in rule.selectors:
        try:
            # Classes match case-insensitively, see the Select in find_first_matching_rule()
            if class_name in {c.lower() for c in selector.class_names()} and select.matches(elem, selector):
                return True
        except SelectorError:
            continue  # an invalid selector, which browsers ignore, matches nothing
    return False


def find_first_rule_that_matches_elem(
    container: Container,
    elem: _Element,
    select: Select[_Element],
    class_name: str,
    sheet: Stylesheet,
    current_file_name: str,
    recursion_level: int = 0,
    rules: Iterable[Rule] | None = None,
) -> RuleLocation | None:
    # iterate over rules handling @import and grouping rules such as @media,
    # returning the address of the matching rule as browsers count rules
    if recursion_level > 16:
        return None
    for rule in sheet.rules if rules is None else rules:
        if isinstance(rule, StyleRule):
            if rule_matches_elem(rule, elem, select, class_name):
                return RuleLocation(list(sheet.browser_index_path(rule)), current_file_name)
        elif isinstance(rule, GroupingRule):
            res = find_first_rule_that_matches_elem(container, elem, select, class_name, sheet, current_file_name, recursion_level + 1, rule.rules)
            if res is not None:
                return res
        elif isinstance(rule, ImportRule):
            if not rule.href:
                continue
            sname = container.href_to_name(rule.href, current_file_name)
            # Imports of missing sheets are ignored, as browsers do
            if sname and container.has_name(sname):
                try:
                    isheet = container.parsed_object(sname)
                except OSError:
                    continue
                if isinstance(isheet, Stylesheet):
                    res = find_first_rule_that_matches_elem(container, elem, select, class_name, isheet, sname, recursion_level + 1)
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
    # quirks_mode matches ids and classes case-insensitively, as the selector
    # engine used before kgcss did
    select = Select(root, ignore_inappropriate_pseudo_classes=True, quirks_mode=True)
    for tag in root.iter('*'):
        tag_name = tag.tag
        assert isinstance(tag_name, str)  # iter('*') only yields elements, which have str tags
        tn = barename(tag_name)
        if tn == 'style' and tag.text and tag.get('type', 'text/css') == 'text/css':
            sheet = container.parse_stylesheet(tag.text)
            res = find_first_rule_that_matches_elem(container, target_elem, select, class_name, sheet, html_file_name)
            if res is not None:
                return res._replace(style_tag_address=(int(cast('str', tag.get(lnum_attr))), ['style']))  # parse() sets lnum_attr on all elements
        elif tn == 'link' and tag.get('href') and tag.get('rel', '').lower() == 'stylesheet':
            sname = container.href_to_name(tag.get('href'), html_file_name)
            if sname is None:
                continue
            if not container.has_name(sname):
                continue  # a link to a missing sheet
            try:
                sheet = container.parsed_object(sname)
            except OSError:
                continue
            if not isinstance(sheet, Stylesheet):
                continue
            res = find_first_rule_that_matches_elem(container, target_elem, select, class_name, sheet, sname)
            if res is not None:
                return res
    raise NoMatchingRuleFound(f'No CSS rules that apply to the specified tag in {html_file_name} with the class {class_name} found')


def develop() -> None:
    container = get_container('/t/demo.epub', tweak_mode=True)
    fname = 'index_split_002.html'
    data: ClassData = {'class': 'xxx', 'sourceline_address': (13, ['body'])}
    print(find_first_matching_rule(container, fname, container.open(fname).read(), data))
