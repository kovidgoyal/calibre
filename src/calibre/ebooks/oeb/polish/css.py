#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import re
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache, partial
from operator import itemgetter
from typing import TYPE_CHECKING

from css_parser.css import CSSRule, CSSStyleDeclaration, CSSStyleSheet
from css_selectors import Select, SelectorError, SelectorSyntaxError, parse
from css_selectors.parser import tokenize
from lxml import etree

from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, XHTML, css_text
from calibre.ebooks.oeb.normalize_css import normalize_filter_css, normalizers
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style, pretty_xml_tree, serialize
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import numeric_sort_key
from calibre.utils.localization import _, ngettext

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping

    from css_parser.css import CSSRuleList, CSSStyleRule, Property, Selector
    from css_parser.css.value import Value
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.utils.logging import Log

type SheetTransform = Callable[[CSSStyleSheet], bool]
type StyleTransform = Callable[[CSSStyleDeclaration], bool]


class SelectorStatus:
    any_used: bool = False
    any_unused: bool = False


def mark_used_selectors(rules: Iterable[CSSStyleRule], log: Log, select: Select) -> SelectorStatus:
    ans = SelectorStatus()
    for rule in rules:
        for selector in rule.selectorList:
            if getattr(selector, 'calibre_used', False):
                ans.any_used = True
                continue
            try:
                if select.has_matches(selector.selectorText):
                    selector.calibre_used = True
                    ans.any_used = True
                else:
                    ans.any_unused = True
                    selector.calibre_used = False
            except SelectorError:
                # Cannot parse/execute this selector, be safe and assume it
                # matches something
                selector.calibre_used = True
                ans.any_used = True
    return ans


def get_imported_sheets(
    name: str, container: Container, sheets: Mapping[str, CSSStyleSheet], recursion_level: int = 10, sheet: CSSStyleSheet | None = None
) -> set[str]:
    ans: set[str] = set()
    sheet = sheet or sheets[name]
    for rule in sheet.cssRules.rulesOfType(CSSRule.IMPORT_RULE):
        if rule.href:
            iname = container.href_to_name(rule.href, name)
            if iname is not None and iname in sheets:
                ans.add(iname)
    if recursion_level > 0:
        for imported_sheet in tuple(ans):
            ans |= get_imported_sheets(imported_sheet, container, sheets, recursion_level=recursion_level - 1)
    ans.discard(name)
    return ans


def merge_declarations(first: CSSStyleDeclaration, second: CSSStyleDeclaration) -> None:
    for prop in second.getProperties():
        first.setProperty(prop)


def merge_identical_selectors(sheet: CSSStyleSheet) -> int:
    "Merge rules that have identical selectors"
    selector_map: defaultdict[str, list[CSSStyleRule]] = defaultdict(list)
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        selector_map[rule.selectorText].append(rule)
    remove: list[CSSStyleRule] = []
    for rule_group in selector_map.values():
        if len(rule_group) > 1:
            for i in range(1, len(rule_group)):
                merge_declarations(rule_group[0].style, rule_group[i].style)
                remove.append(rule_group[i])
    for rule in remove:
        sheet.cssRules.remove(rule)
    return len(remove)


def merge_identical_properties(sheet: CSSStyleSheet) -> int:
    "Merge rules having identical properties"
    properties_map: defaultdict[tuple[tuple[str, str], ...], list[tuple[int, CSSStyleRule]]] = defaultdict(list)

    def declaration_key(declaration: CSSStyleDeclaration) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(((prop.name, prop.propertyValue.value) for prop in declaration.getProperties()), key=itemgetter(0)))

    for idx, rule in enumerate(sheet.cssRules):
        if rule.type == CSSRule.STYLE_RULE:
            properties_map[declaration_key(rule.style)].append((idx, rule))

    removals: list[int] = []
    num_merged = 0
    for rule_group in properties_map.values():
        if len(rule_group) < 2:
            continue
        num_merged += len(rule_group)
        selectors = rule_group[0][1].selectorList
        seen = {s.selectorText for s in selectors}
        rules = iter(rule_group)
        next(rules)
        for idx, rule in rules:
            removals.append(idx)
            for s in rule.selectorList:
                q = s.selectorText
                if q not in seen:
                    seen.add(q)
                    selectors.append(s)
    for idx in sorted(removals, reverse=True):
        sheet.cssRules.pop(idx)
    return num_merged


def remove_unused_selectors_and_rules(rules_container: CSSRuleList, rules: Iterable[CSSStyleRule], removal_stats: dict[str, int]) -> SelectorStatus:
    ans = SelectorStatus()
    for r in rules:
        removals: list[int] = []
        for i, sel in enumerate(r.selectorList):
            if getattr(sel, 'calibre_used', True):
                ans.any_used = True
            else:
                removals.append(i)
        if removals:
            ans.any_unused = True
            if len(removals) == len(r.selectorList):
                rules_container.remove(r)
                removal_stats['rules'] += 1
            else:
                removal_stats['selectors'] += len(removals)
                for i in reversed(removals):
                    del r.selectorList[i]
    return ans


def remove_unused_css(
    container: Container,
    report: Callable[[str], object] | None = None,
    remove_unused_classes: bool = False,
    merge_rules: bool = False,
    merge_rules_with_identical_properties: bool = False,
    remove_unreferenced_sheets: bool = False,
) -> bool:
    """
    Remove all unused CSS rules from the book. An unused CSS rule is one that does not match any actual content.

    :param report: An optional callable that takes a single argument. It is called with information about the operations being performed.
    :param remove_unused_classes: If True, class attributes in the HTML that do not match any CSS rules are also removed.
    :param merge_rules: If True, rules with identical selectors are merged.
    :param merge_rules_with_identical_properties: If True, rules with identical properties are merged.
    :param remove_unreferenced_sheets: If True, stylesheets that are not referenced by any content are removed
    """
    report = report or (lambda x: x)

    def safe_parse(name: str) -> CSSStyleSheet | None:
        try:
            ans = container.parsed(name)
        except TypeError:
            return None
        assert isinstance(ans, CSSStyleSheet)
        return ans

    maybe_sheets = {name: safe_parse(name) for name, mt in container.mime_map.items() if mt in OEB_STYLES}
    sheets = {k: v for k, v in maybe_sheets.items() if v is not None}
    num_merged = num_rules_merged = 0
    if merge_rules:
        for name, sheet in sheets.items():
            num = merge_identical_selectors(sheet)
            if num:
                container.dirty(name)
                num_merged += num
    if merge_rules_with_identical_properties:
        for name, sheet in sheets.items():
            num = merge_identical_properties(sheet)
            if num:
                container.dirty(name)
                num_rules_merged += num
    import_map = {name: get_imported_sheets(name, container, sheets) for name in sheets}
    unreferenced_sheets = set(sheets)
    if remove_unused_classes:
        class_map = {name: {icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)} for name, sheet in sheets.items()}
    style_rules = {name: tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE)) for name, sheet in sheets.items()}

    removal_stats = {'rules': 0, 'selectors': 0}
    num_of_removed_classes = 0

    for name, mt in container.mime_map.items():
        if mt not in OEB_DOCS:
            continue
        root = container.parsed(name)
        assert isinstance(root, etree._Element)
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        used_classes: set[str] = set()
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                sheet = container.parse_css(style.text)
                if merge_rules:
                    num = merge_identical_selectors(sheet)
                    if num:
                        num_merged += num
                        container.dirty(name)
                if merge_rules_with_identical_properties:
                    num = merge_identical_properties(sheet)
                    if num:
                        num_rules_merged += num
                        container.dirty(name)
                if remove_unused_classes:
                    used_classes |= {icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)}
                imports = get_imported_sheets(name, container, sheets, sheet=sheet)
                for imported_sheet in imports:
                    unreferenced_sheets.discard(imported_sheet)
                    mark_used_selectors(style_rules[imported_sheet], container.log, select)
                    if remove_unused_classes:
                        used_classes |= class_map[imported_sheet]
                rules = tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
                if mark_used_selectors(rules, container.log, select).any_unused:
                    remove_unused_selectors_and_rules(sheet.cssRules, rules, removal_stats)
                    style.text = force_unicode(sheet.cssText, 'utf-8')
                    pretty_script_or_style(container, style)
                    container.dirty(name)

        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = container.href_to_name(link.get('href'), name)
            if sname not in sheets:
                continue
            mark_used_selectors(style_rules[sname], container.log, select)
            if remove_unused_classes:
                used_classes |= class_map[sname]
            unreferenced_sheets.discard(sname)

            for iname in import_map[sname]:
                unreferenced_sheets.discard(iname)
                mark_used_selectors(style_rules[iname], container.log, select)
                if remove_unused_classes:
                    used_classes |= class_map[iname]

        if remove_unused_classes:
            for elem in root.xpath('//*[@class]'):
                original_classes: list[str] = elem.get('class', '').split()
                classes: list[str] = []
                for x in original_classes:
                    if icu_lower(x) in used_classes:
                        classes.append(x)
                if len(classes) != len(original_classes):
                    if classes:
                        elem.set('class', ' '.join(classes))
                    else:
                        del elem.attrib['class']
                    num_of_removed_classes += len(original_classes) - len(classes)
                    container.dirty(name)

    for name, sheet in sheets.items():
        if name in unreferenced_sheets:
            continue
        q = remove_unused_selectors_and_rules(sheet.cssRules, style_rules[name], removal_stats)
        if q.any_unused:
            container.dirty(name)
    num_sheets_removed = 0
    if remove_unreferenced_sheets and unreferenced_sheets:
        num_sheets_removed += len(unreferenced_sheets)
        for uname in unreferenced_sheets:
            container.remove_item(uname)

    num_changes = num_merged + num_of_removed_classes + num_rules_merged + removal_stats['rules'] + removal_stats['selectors'] + num_sheets_removed
    if num_changes > 0:
        if removal_stats['rules']:
            report(ngettext('Removed one unused CSS style rule', 'Removed {} unused CSS style rules', removal_stats['rules']).format(removal_stats['rules']))
        if removal_stats['selectors']:
            report(
                ngettext('Removed one unused CSS selector', 'Removed {} unused CSS selectors', removal_stats['selectors']).format(removal_stats['selectors'])
            )
        if num_of_removed_classes > 0:
            report(
                ngettext(
                    'Removed one unused class from the HTML',
                    'Removed {} unused classes from the HTML',
                    num_of_removed_classes,
                ).format(num_of_removed_classes)
            )
        if num_merged > 0:
            report(
                ngettext(
                    'Merged one CSS style rule with identical selectors',
                    'Merged {} CSS style rules with identical selectors',
                    num_merged,
                ).format(num_merged)
            )
        if num_rules_merged > 0:
            report(
                ngettext(
                    'Merged one CSS style rule with identical properties',
                    'Merged {} CSS style rules with identical properties',
                    num_rules_merged,
                ).format(num_rules_merged)
            )
        if num_sheets_removed:
            report(ngettext('Removed one unreferenced stylesheet', 'Removed {} unreferenced stylesheets', num_sheets_removed).format(num_sheets_removed))
    if not removal_stats['rules']:
        report(_('No unused CSS style rules found'))
    if not removal_stats['selectors']:
        report(_('No unused CSS selectors found'))
    if remove_unused_classes and num_of_removed_classes == 0:
        report(_('No unused class attributes found'))
    if merge_rules and num_merged == 0:
        report(_('No style rules that could be merged found'))
    if remove_unreferenced_sheets and num_sheets_removed == 0:
        report(_('No unused stylesheets found'))
    return num_changes > 0


def filter_declaration(style: CSSStyleDeclaration, properties: set[str] | frozenset[str] = frozenset()) -> bool:
    changed = False
    for prop in properties:
        if style.removeProperty(prop) != '':
            changed = True
    all_props = set(style.keys())
    for prop in style.getProperties():
        n = normalizers.get(prop.name, None)
        if n is not None:
            normalized = n(prop.name, prop.propertyValue)
            removed = properties.intersection(set(normalized))
            if removed:
                changed = True
                style.removeProperty(prop.name)
                for prop in set(normalized) - removed - all_props:
                    style.setProperty(prop, normalized[prop])
    return changed


def filter_sheet(sheet: CSSStyleSheet, properties: set[str] | frozenset[str] = frozenset()) -> bool:
    from css_parser.css import CSSRule

    changed = False
    remove: list[CSSStyleRule] = []
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        if filter_declaration(rule.style, properties):
            changed = True
            if rule.style.length == 0:
                remove.append(rule)
    for rule in remove:
        sheet.cssRules.remove(rule)
    return changed


def transform_inline_styles(container: Container, name: str, transform_sheet: SheetTransform | None, transform_style: StyleTransform | None) -> bool:
    root = container.parsed(name)
    assert isinstance(root, etree._Element)
    changed = False
    for style in root.xpath('//*[local-name()="style"]') if transform_sheet is not None else ():
        if style.text and (style.get('type') or 'text/css').lower() == 'text/css':
            sheet = container.parse_css(style.text)
            assert transform_sheet is not None  # the loop only runs if transform_sheet is not None
            if transform_sheet(sheet):
                changed = True
                style.text = force_unicode(sheet.cssText, 'utf-8')
                pretty_script_or_style(container, style)
    for elem in root.xpath('//*[@style]') if transform_style is not None else ():
        text = elem.get('style', None)
        if text:
            style = container.parse_css(text, is_declaration=True)
            assert transform_style is not None  # the loop only runs if transform_style is not None
            if transform_style(style):
                changed = True
                if style.length == 0:
                    del elem.attrib['style']
                else:
                    elem.set('style', force_unicode(style.getCssText(separator=' '), 'utf-8'))
    return changed


def transform_css(
    container: Container, transform_sheet: SheetTransform | None = None, transform_style: StyleTransform | None = None, names: Collection[str] = ()
) -> bool:
    if not names:
        types = OEB_STYLES | OEB_DOCS
        all_names: list[str] = []
        for name, mt in container.mime_map.items():
            if mt in types:
                all_names.append(name)
        names = all_names

    doc_changed = False

    for name in names:
        mt = container.mime_map[name]
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            assert isinstance(sheet, CSSStyleSheet)
            if transform_sheet is not None and transform_sheet(sheet):
                container.dirty(name)
                doc_changed = True
        elif mt in OEB_DOCS:
            if transform_inline_styles(container, name, transform_sheet, transform_style):
                container.dirty(name)
                doc_changed = True

    return doc_changed


def filter_css(container: Container, properties: Iterable[str], names: Collection[str] = ()) -> bool:
    """
    Remove the specified CSS properties from all CSS rules in the book.

    :param properties: Set of properties to remove. For example: :code:`{'font-family', 'color'}`.
    :param names: The files from which to remove the properties. Defaults to all HTML and CSS files in the book.
    """
    nproperties = normalize_filter_css(properties)
    return transform_css(
        container,
        transform_sheet=partial(filter_sheet, properties=nproperties),
        transform_style=partial(filter_declaration, properties=nproperties),
        names=names,
    )


def _classes_in_selector(selector: object, classes: set[str]) -> None:
    for attr in ('selector', 'subselector', 'parsed_tree'):
        s = getattr(selector, attr, None)
        if s is not None:
            _classes_in_selector(s, classes)
    # Selectors such as :is(), :not(), :has() and :nth-child(An+B of S)
    for s in getattr(selector, 'selector_list', None) or ():
        _classes_in_selector(s, classes)
    cn = getattr(selector, 'class_name', None)
    if cn is not None:
        classes.add(cn)


@lru_cache(maxsize=4096)
def classes_in_selector(text: str) -> set[str]:
    classes: set[str] = set()
    try:
        for selector in parse(text):
            _classes_in_selector(selector, classes)
    except SelectorSyntaxError:
        pass
    return classes


def classes_in_rule_list(css_rules: CSSRuleList) -> set[str]:
    classes: set[str] = set()
    for rule in css_rules:
        if rule.type == rule.STYLE_RULE:
            classes |= classes_in_selector(rule.selectorText)
        elif hasattr(rule, 'cssRules'):
            classes |= classes_in_rule_list(rule.cssRules)
    return classes


def rename_ids_in_selector(text: str, id_map: dict[str, str]) -> str:
    """Return the selector text with the ids in id_map renamed, in both #id
    and [id="..."] selectors. The new ids must be valid CSS identifiers."""
    try:
        tokens = tuple(tokenize(text))
    except SelectorSyntaxError:
        return text

    def skip_space(i: int, step: int = 1) -> int:
        while 0 <= i < len(tokens) and tokens[i].type == 'S':
            i += step
        return i

    replacements: list[tuple[int, int, str]] = []
    for i, tok in enumerate(tokens):
        if tok.type == 'HASH':
            nid = id_map.get(tok.value)
            if nid is not None:
                replacements.append((tok.pos, tokens[i + 1].pos, '#' + nid))
        elif tok.type == 'IDENT' and tok.value.lower() == 'id':
            prev = skip_space(i - 1, -1)
            if prev < 0 or not tokens[prev].is_delim('['):
                continue
            j = skip_space(i + 1)
            if not tokens[j].is_delim('='):
                continue
            j = skip_space(j + 1)
            val = tokens[j]
            if val.type in ('STRING', 'IDENT'):
                nid = id_map.get(val.value)
                if nid is not None:
                    replacements.append((val.pos, tokens[j + 1].pos, f'"{nid}"'))
    for start, end, repl in reversed(replacements):
        text = text[:start] + repl + text[end:]
    return text


def rename_ids_in_rule_list(css_rules: CSSRuleList, id_map: dict[str, str]) -> bool:
    changed = False
    for rule in css_rules:
        if rule.type == rule.STYLE_RULE:
            q = rename_ids_in_selector(rule.selectorText, id_map)
            if q != rule.selectorText:
                rule.selectorText = q
                changed = True
        elif hasattr(rule, 'cssRules'):
            changed = rename_ids_in_rule_list(rule.cssRules, id_map) or changed
    return changed


def rename_ids_in_css(container: Container, id_map: dict[str, str], names: Collection[str] = ()) -> bool:
    """
    Rename id selectors in all CSS rules in the book, both in stylesheets and
    in <style> tags.

    :param id_map: A mapping of {old_id: new_id}. The new ids must be valid CSS identifiers.
    :param names: The files in which to rename. Defaults to all HTML and CSS files in the book.
    """
    return transform_css(container, transform_sheet=lambda sheet: rename_ids_in_rule_list(sheet.cssRules, id_map), names=names)


def iter_declarations(sheet_or_rule: CSSStyleSheet | CSSRule | CSSStyleDeclaration) -> Iterator[CSSStyleDeclaration]:
    if hasattr(sheet_or_rule, 'cssRules'):
        for rule in sheet_or_rule.cssRules:
            yield from iter_declarations(rule)
    elif hasattr(sheet_or_rule, 'style'):
        yield sheet_or_rule.style
    elif isinstance(sheet_or_rule, CSSStyleDeclaration):
        yield sheet_or_rule


def remove_property_value(prop: Property, predicate: Callable[[Value], bool]) -> bool:
    """Remove the Values that match the predicate from this property. If all
    values of the property would be removed, the property is removed from its
    parent instead. Note that this means the property must have a parent (a
    CSSStyleDeclaration)."""
    removed_vals = list(filter(predicate, prop.propertyValue))
    if len(removed_vals) == len(prop.propertyValue):
        prop.parent.removeProperty(prop.name)
    else:
        x = css_text(prop.propertyValue)
        for v in removed_vals:
            x = x.replace(css_text(v), '').strip()
        prop.propertyValue.cssText = x
    return bool(removed_vals)


RULE_PRIORITIES = {t: i for i, t in enumerate((CSSRule.COMMENT, CSSRule.CHARSET_RULE, CSSRule.IMPORT_RULE, CSSRule.NAMESPACE_RULE))}


def sort_sheet(container: Container, sheet_or_text: str | CSSStyleSheet) -> CSSStyleSheet:
    """Sort the rules in a stylesheet. Note that in the general case this can
    change the effective styles, but for most common sheets, it should be safe.
    """
    sheet = container.parse_css(sheet_or_text) if isinstance(sheet_or_text, str) else sheet_or_text

    def text_sort_key(x: object) -> bytes:
        return numeric_sort_key(str(x or ''))

    def selector_sort_key(x: Selector) -> tuple[tuple[int, int, int, int], bytes]:
        return (x.specificity, text_sort_key(x.selectorText))

    def rule_sort_key(rule: CSSRule) -> tuple[int, bytes, object]:
        primary = RULE_PRIORITIES.get(rule.type, len(RULE_PRIORITIES))
        secondary = text_sort_key(getattr(rule, 'atkeyword', '') or '')
        tertiary = None
        if rule.type == CSSRule.STYLE_RULE:
            primary += 1
            selectors = sorted(rule.selectorList, key=selector_sort_key)
            tertiary = selector_sort_key(selectors[0])
            rule.selectorText = ', '.join(s.selectorText for s in selectors)
        elif rule.type == CSSRule.FONT_FACE_RULE:
            try:
                tertiary = text_sort_key(rule.style.getPropertyValue('font-family'))
            except Exception:
                pass

        return primary, secondary, tertiary

    sheet.cssRules.sort(key=rule_sort_key)
    return sheet


def add_stylesheet_links(container: Container, name: str, text: str) -> bytes | None:
    root = container.parse_xhtml(text, name)
    heads = root.xpath('//*[local-name() = "head"]')
    if not heads:
        return
    head = heads[0]
    # skip manifest entries whose href does not resolve to a name in the book
    sheets = tuple(x for x in container.manifest_items_of_type(lambda mt: mt in OEB_STYLES) if x is not None)
    if not sheets:
        return
    for sname in sheets:
        link = head.makeelement(XHTML('link'), type='text/css', rel='stylesheet', href=container.name_to_href(sname, name))
        head.append(link)
    pretty_xml_tree(head)
    return serialize(root, 'text/html')


def rename_class_in_rule_list(css_rules: CSSRuleList, old_name: str, new_name: str) -> bool:
    # this regex will not match class names inside attribute value selectors
    # and it will match id selectors that contain .old_name but its the best
    # that can be done without implementing a full parser for CSS selectors
    pat = re.compile(rf'(?<=\.){re.escape(old_name)}(?:\W|$)')

    def repl(m: re.Match[str]) -> str:
        return m.group().replace(old_name, new_name)

    changed = False
    for rule in css_rules:
        if rule.type == rule.STYLE_RULE:
            old = rule.selectorText
            q = pat.sub(repl, old)
            if q != old:
                changed = True
                rule.selectorText = q
        elif hasattr(rule, 'cssRules'):
            if rename_class_in_rule_list(rule.cssRules, old_name, new_name):
                changed = True
    return changed


def rename_class_in_doc(container: Container, root: _Element, old_name: str, new_name: str) -> bool:
    changed = False
    pat = re.compile(rf'(?:^|\W){re.escape(old_name)}(?:\W|$)')

    def repl(m: re.Match[str]) -> str:
        return m.group().replace(old_name, new_name)

    for elem in root.xpath('//*[@class]'):
        old = elem.get('class')
        if old:
            new = pat.sub(repl, old)
            if new != old:
                changed = True
                elem.set('class', new)
    for style in root.xpath('//*[local-name()="style"]'):
        if style.get('type', 'text/css') == 'text/css' and style.text:
            sheet = container.parse_css(style.text)
            if rename_class_in_rule_list(sheet.cssRules, old_name, new_name):
                changed = True
                style.text = force_unicode(sheet.cssText, 'utf-8')
    return changed


def rename_class(container: Container, old_name: str, new_name: str) -> bool:
    changed = False
    if not old_name or old_name == new_name:
        return changed
    for sheet_name in container.manifest_items_of_type(lambda mt: mt in OEB_STYLES):
        if sheet_name is None:  # manifest entry whose href does not resolve to a name in the book
            continue
        sheet = container.parsed(sheet_name)
        assert isinstance(sheet, CSSStyleSheet)
        if rename_class_in_rule_list(sheet.cssRules, old_name, new_name):
            container.dirty(sheet_name)
            changed = True
    for doc_name in container.manifest_items_of_type(lambda mt: mt in OEB_DOCS):
        if doc_name is None:  # manifest entry whose href does not resolve to a name in the book
            continue
        doc = container.parsed(doc_name)
        assert isinstance(doc, etree._Element)
        if rename_class_in_doc(container, doc, old_name, new_name):
            container.dirty(doc_name)
            changed = True
    return changed
