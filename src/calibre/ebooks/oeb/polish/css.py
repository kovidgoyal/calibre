#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from collections import defaultdict
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from kgcss import DeclarationBlock, FontFaceRule, GroupingRule, RuleContainer, RuleType, Select, SelectorError, StyleRule, Stylesheet
from lxml import etree

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, XHTML
from calibre.ebooks.oeb.normalize_css import normalize_filter_css, normalize_shorthand
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style, pretty_xml_tree, serialize
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import numeric_sort_key
from calibre.utils.localization import _, ngettext

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping

    from kgcss import Rule, RuleList, Selector
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.utils.logging import Log

type SheetTransform = Callable[[Stylesheet], bool]
type StyleTransform = Callable[[DeclarationBlock], bool]


class SelectorStatus:
    any_used: bool = False
    any_unused: bool = False


def delete_rule(rule: Rule) -> None:
    "Remove a rule from the sheet or rule that contains it"
    parent = rule.parent_rule
    if isinstance(parent, RuleContainer):
        parent.delete_rule(rule)
    elif (sheet := rule.parent_style_sheet) is not None:
        sheet.delete_rule(rule)


def rule_lists(sheet: Stylesheet) -> Iterator[RuleList]:
    "The list of top level rules of sheet and the lists of rules of the grouping rules in it, such as @media, at any depth"
    yield sheet.rules
    for rule in sheet.iter_rules():
        if isinstance(rule, GroupingRule):
            yield rule.rules


#: Whether selectors match something, selectors that were never checked are
#: not in it
type UsedSelectors = dict[Selector, bool]


def mark_used_selectors(rules: Iterable[StyleRule], log: Log, select: Select[_Element], used: UsedSelectors) -> SelectorStatus:
    ans = SelectorStatus()
    for rule in rules:
        for selector in rule.selectors:
            if used.get(selector, False):
                ans.any_used = True
                continue
            try:
                if select.has_matches(selector):
                    used[selector] = True
                    ans.any_used = True
                else:
                    ans.any_unused = True
                    used[selector] = False
            except SelectorError:
                # Cannot parse/execute this selector, be safe and assume it
                # matches something
                used[selector] = True
                ans.any_used = True
    return ans


def get_imported_sheets(
    name: str, container: Container, sheets: Mapping[str, Stylesheet], recursion_level: int = 10, sheet: Stylesheet | None = None
) -> set[str]:
    ans: set[str] = set()
    sheet = sheet or sheets[name]
    for rule in sheet.rules.of_type(RuleType.IMPORT):
        if rule.href:
            iname = container.href_to_name(rule.href, name)
            if iname is not None and iname in sheets:
                ans.add(iname)
    if recursion_level > 0:
        for imported_sheet in tuple(ans):
            ans |= get_imported_sheets(imported_sheet, container, sheets, recursion_level=recursion_level - 1)
    ans.discard(name)
    return ans


def merge_declarations(first: DeclarationBlock, second: DeclarationBlock) -> None:
    for prop in second:
        first.set_property(prop)


def merge_identical_selectors(sheet: Stylesheet) -> int:
    "Merge rules that have identical selectors, in the same list of rules"
    num_removed = 0
    for rules in rule_lists(sheet):
        selector_map: defaultdict[str, list[StyleRule]] = defaultdict(list)
        for rule in rules.of_type(RuleType.STYLE):
            # Merging moves declarations only, not nested rules
            if not rule.rules:
                selector_map[rule.selector_text].append(rule)
        for rule_group in selector_map.values():
            for rule in rule_group[1:]:
                merge_declarations(rule_group[0].style, rule.style)
                rules.remove(rule)
                num_removed += 1
    return num_removed


def merge_identical_properties(sheet: Stylesheet) -> int:
    "Merge rules having identical properties, in the same list of rules"

    def declaration_key(declaration: DeclarationBlock) -> tuple[tuple[str, str, str], ...]:
        return tuple(sorted((prop.name, prop.value_to_css(), prop.priority) for prop in declaration))

    num_merged = 0
    for rules in rule_lists(sheet):
        properties_map: defaultdict[tuple[tuple[str, str, str], ...], list[StyleRule]] = defaultdict(list)
        for rule in rules.of_type(RuleType.STYLE):
            # Merging moves selectors only, not nested rules
            if not rule.rules:
                properties_map[declaration_key(rule.style)].append(rule)
        for rule_group in properties_map.values():
            if len(rule_group) < 2:
                continue
            num_merged += len(rule_group)
            selectors = rule_group[0].selectors
            seen = {s.text for s in selectors}
            for rule in rule_group[1:]:
                for s in rule.selectors:
                    if s.text not in seen:
                        seen.add(s.text)
                        selectors.append(s)
                rules.remove(rule)
    return num_merged


def remove_unused_selectors_and_rules(rules: Iterable[StyleRule], removal_stats: dict[str, int], used: UsedSelectors) -> SelectorStatus:
    ans = SelectorStatus()
    for r in rules:
        removals: list[int] = []
        for i, sel in enumerate(r.selectors):
            if used.get(sel, True):
                ans.any_used = True
            else:
                removals.append(i)
        if removals:
            ans.any_unused = True
            if len(removals) == len(r.selectors):
                delete_rule(r)
                removal_stats['rules'] += 1
            else:
                removal_stats['selectors'] += len(removals)
                for i in reversed(removals):
                    del r.selectors[i]
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

    def safe_parse(name: str) -> Stylesheet | None:
        try:
            return container.parsed_stylesheet(name)
        except TypeError:
            return None

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
        class_map = {name: {icu_lower(x) for x in classes_in_sheet(sheet)} for name, sheet in sheets.items()}
    style_rules = {name: tuple(sheet.iter_rules(RuleType.STYLE)) for name, sheet in sheets.items()}

    removal_stats = {'rules': 0, 'selectors': 0}
    used: UsedSelectors = {}
    num_of_removed_classes = 0

    for name, mt in container.mime_map.items():
        if mt not in OEB_DOCS:
            continue
        root = container.parsed(name)
        assert isinstance(root, etree._Element)
        # quirks_mode matches ids and classes case-insensitively, as the
        # selector engine used before kgcss did
        select = Select(root, ignore_inappropriate_pseudo_classes=True, quirks_mode=True)
        used_classes: set[str] = set()
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                sheet = container.parse_stylesheet(style.text)
                changed = False
                if merge_rules:
                    num = merge_identical_selectors(sheet)
                    if num:
                        num_merged += num
                        changed = True
                if merge_rules_with_identical_properties:
                    num = merge_identical_properties(sheet)
                    if num:
                        num_rules_merged += num
                        changed = True
                if remove_unused_classes:
                    used_classes |= {icu_lower(x) for x in classes_in_sheet(sheet)}
                imports = get_imported_sheets(name, container, sheets, sheet=sheet)
                for imported_sheet in imports:
                    unreferenced_sheets.discard(imported_sheet)
                    mark_used_selectors(style_rules[imported_sheet], container.log, select, used)
                    if remove_unused_classes:
                        used_classes |= class_map[imported_sheet]
                rules = tuple(sheet.iter_rules(RuleType.STYLE))
                if mark_used_selectors(rules, container.log, select, used).any_unused:
                    remove_unused_selectors_and_rules(rules, removal_stats, used)
                    changed = True
                if changed:
                    style.text = container.stylesheet_text(sheet)
                    pretty_script_or_style(container, style)
                    container.dirty(name)

        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = container.href_to_name(link.get('href'), name)
            if sname not in sheets:
                continue
            mark_used_selectors(style_rules[sname], container.log, select, used)
            if remove_unused_classes:
                used_classes |= class_map[sname]
            unreferenced_sheets.discard(sname)

            for iname in import_map[sname]:
                unreferenced_sheets.discard(iname)
                mark_used_selectors(style_rules[iname], container.log, select, used)
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
        q = remove_unused_selectors_and_rules(style_rules[name], removal_stats, used)
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


def filter_declaration(style: DeclarationBlock, properties: set[str] | frozenset[str] = frozenset()) -> bool:
    changed = False
    for prop in properties:
        if style.remove(prop) != '':
            changed = True
    all_props = set(style.keys())
    for prop in tuple(style):
        normalized = normalize_shorthand(prop.name, prop.value_to_css())
        if normalized is not None:
            removed = properties.intersection(normalized)
            if removed:
                changed = True
                style.remove(prop.name)
                for name, value in normalized.items():
                    if name not in removed and name not in all_props:
                        style.set(name, value, prop.priority)
    return changed


def filter_sheet(sheet: Stylesheet, properties: set[str] | frozenset[str] = frozenset()) -> bool:
    changed = False
    for rule in tuple(sheet.iter_rules(RuleType.STYLE)):
        if filter_declaration(rule.style, properties):
            changed = True
            if len(rule.style) == 0 and not rule.rules:
                delete_rule(rule)
    return changed


def transform_inline_styles(container: Container, name: str, transform_sheet: SheetTransform | None, transform_style: StyleTransform | None) -> bool:
    root = container.parsed(name)
    assert isinstance(root, etree._Element)
    changed = False
    for style in root.xpath('//*[local-name()="style"]') if transform_sheet is not None else ():
        if style.text and (style.get('type') or 'text/css').lower() == 'text/css':
            sheet = container.parse_stylesheet(style.text)
            assert transform_sheet is not None  # the loop only runs if transform_sheet is not None
            if transform_sheet(sheet):
                changed = True
                style.text = container.stylesheet_text(sheet)
                pretty_script_or_style(container, style)
    for elem in root.xpath('//*[@style]') if transform_style is not None else ():
        text = elem.get('style', None)
        if text:
            style = container.parse_style(text)
            assert transform_style is not None  # the loop only runs if transform_style is not None
            if transform_style(style):
                changed = True
                if len(style) == 0:
                    del elem.attrib['style']
                else:
                    elem.set('style', style.to_css(single_line=True))
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
            sheet = container.parsed_stylesheet(name)
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


def classes_in_sheet(sheet: Stylesheet) -> set[str]:
    "The class names used in the selectors of the style rules of sheet, at any depth"
    classes: set[str] = set()
    for rule in sheet.iter_rules(RuleType.STYLE):
        for selector in rule.selectors:
            try:
                classes |= selector.class_names()
            except SelectorError:
                continue  # an invalid selector, which browsers ignore, has no classes
    return classes


def rename_ids_in_sheet(sheet: Stylesheet, id_map: Mapping[str, str]) -> bool:
    "Rename the ids, in #id and [id=...] selectors, of the style rules of sheet, at any depth"
    changed = False
    for rule in sheet.iter_rules(RuleType.STYLE):
        if rule.selectors.rename_ids(id_map):
            changed = True
    return changed


def rename_ids_in_css(container: Container, id_map: dict[str, str], names: Collection[str] = ()) -> bool:
    """
    Rename id selectors in all CSS rules in the book, both in stylesheets and
    in <style> tags.

    :param id_map: A mapping of {old_id: new_id}.
    :param names: The files in which to rename. Defaults to all HTML and CSS files in the book.
    """
    return transform_css(container, transform_sheet=partial(rename_ids_in_sheet, id_map=id_map), names=names)


RULE_PRIORITIES = {t: i for i, t in enumerate((RuleType.COMMENT, RuleType.CHARSET, RuleType.IMPORT, RuleType.NAMESPACE))}


def sort_sheet(container: Container, sheet_or_text: str | Stylesheet) -> Stylesheet:
    """Sort the rules in a stylesheet. Note that in the general case this can
    change the effective styles, but for most common sheets, it should be safe.
    """
    sheet = container.parse_stylesheet(sheet_or_text) if isinstance(sheet_or_text, str) else sheet_or_text

    def text_sort_key(x: object) -> bytes:
        return numeric_sort_key(str(x or ''))

    def selector_sort_key(x: Selector) -> tuple[tuple[int, int, int], bytes]:
        try:
            specificity = x.specificity
        except SelectorError:
            specificity = (0, 0, 0)
        return specificity, text_sort_key(x.text)

    def rule_sort_key(rule: Rule) -> tuple[int, bytes, object]:
        primary = RULE_PRIORITIES.get(rule.type, len(RULE_PRIORITIES))
        tertiary = None
        if isinstance(rule, StyleRule):
            primary += 1
            secondary = b''
            # In place, as assigning the text of an invalid selector raises
            rule.selectors.sort(key=selector_sort_key)
            tertiary = selector_sort_key(rule.selectors[0])
        else:
            secondary = text_sort_key(rule.type.value)
            if isinstance(rule, FontFaceRule):
                tertiary = text_sort_key(rule.style.get_value('font-family'))
        return primary, secondary, tertiary

    sheet.rules.sort(key=rule_sort_key)
    return sheet


def add_stylesheet_links(container: Container, name: str, text: str | bytes) -> bytes | None:
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


def rename_class_in_sheet(sheet: Stylesheet, old_name: str, new_name: str) -> bool:
    "Rename a class in the selectors of the style rules of sheet, at any depth"
    changed = False
    for rule in sheet.iter_rules(RuleType.STYLE):
        if rule.selectors.rename_classes({old_name: new_name}):
            changed = True
    return changed


def rename_class_in_doc(container: Container, root: _Element, old_name: str, new_name: str) -> bool:
    changed = False
    for elem in root.xpath('//*[@class]'):
        old = elem.get('class')
        if old:
            classes = old.split()
            if old_name in classes:
                changed = True
                elem.set('class', ' '.join(new_name if x == old_name else x for x in classes))
    for style in root.xpath('//*[local-name()="style"]'):
        if style.get('type', 'text/css') == 'text/css' and style.text:
            sheet = container.parse_stylesheet(style.text)
            if rename_class_in_sheet(sheet, old_name, new_name):
                changed = True
                style.text = container.stylesheet_text(sheet)
    return changed


def rename_class(container: Container, old_name: str, new_name: str) -> bool:
    changed = False
    if not old_name or old_name == new_name:
        return changed
    for sheet_name in container.manifest_items_of_type(lambda mt: mt in OEB_STYLES):
        if sheet_name is None:  # manifest entry whose href does not resolve to a name in the book
            continue
        sheet = container.parsed_stylesheet(sheet_name)
        if rename_class_in_sheet(sheet, old_name, new_name):
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
