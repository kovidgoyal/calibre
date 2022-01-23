#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import defaultdict
from functools import partial
from operator import itemgetter

from css_parser.css import CSSRule, CSSStyleDeclaration
from css_selectors import parse, SelectorSyntaxError

from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS, XHTML, css_text
from calibre.ebooks.oeb.normalize_css import normalize_filter_css, normalizers
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style, pretty_xml_tree, serialize
from calibre.utils.icu import numeric_sort_key
from css_selectors import Select, SelectorError
from polyglot.builtins import iteritems, itervalues
from polyglot.functools import lru_cache


class SelectorStatus:
    any_used: bool = False
    any_unused: bool = False


def mark_used_selectors(rules, log, select):
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


def get_imported_sheets(name, container, sheets, recursion_level=10, sheet=None):
    ans = set()
    sheet = sheet or sheets[name]
    for rule in sheet.cssRules.rulesOfType(CSSRule.IMPORT_RULE):
        if rule.href:
            iname = container.href_to_name(rule.href, name)
            if iname in sheets:
                ans.add(iname)
    if recursion_level > 0:
        for imported_sheet in tuple(ans):
            ans |= get_imported_sheets(imported_sheet, container, sheets, recursion_level=recursion_level-1)
    ans.discard(name)
    return ans


def merge_declarations(first, second):
    for prop in second.getProperties():
        first.setProperty(prop)


def merge_identical_selectors(sheet):
    ' Merge rules that have identical selectors '
    selector_map = defaultdict(list)
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        selector_map[rule.selectorText].append(rule)
    remove = []
    for rule_group in itervalues(selector_map):
        if len(rule_group) > 1:
            for i in range(1, len(rule_group)):
                merge_declarations(rule_group[0].style, rule_group[i].style)
                remove.append(rule_group[i])
    for rule in remove:
        sheet.cssRules.remove(rule)
    return len(remove)


def merge_identical_properties(sheet):
    ' Merge rules having identical properties '
    properties_map = defaultdict(list)

    def declaration_key(declaration):
        return tuple(sorted(
            ((prop.name, prop.propertyValue.value) for prop in declaration.getProperties()),
            key=itemgetter(0)
        ))

    for idx, rule in enumerate(sheet.cssRules):
        if rule.type == CSSRule.STYLE_RULE:
            properties_map[declaration_key(rule.style)].append((idx, rule))

    removals = []
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


def remove_unused_selectors_and_rules(rules_container, rules, removal_stats):
    ans = SelectorStatus()
    for r in rules:
        removals = []
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
    container, report=None,
    remove_unused_classes=False,
    merge_rules=False,
    merge_rules_with_identical_properties=False,
    remove_unreferenced_sheets=False,
):
    '''
    Remove all unused CSS rules from the book. An unused CSS rule is one that does not match any actual content.

    :param report: An optional callable that takes a single argument. It is called with information about the operations being performed.
    :param remove_unused_classes: If True, class attributes in the HTML that do not match any CSS rules are also removed.
    :param merge_rules: If True, rules with identical selectors are merged.
    :param merge_rules_with_identical_properties: If True, rules with identical properties are merged.
    :param remove_unreferenced_sheets: If True, stylesheets that are not referenced by any content are removed
    '''
    report = report or (lambda x:x)

    def safe_parse(name):
        try:
            return container.parsed(name)
        except TypeError:
            pass
    sheets = {name:safe_parse(name) for name, mt in iteritems(container.mime_map) if mt in OEB_STYLES}
    sheets = {k:v for k, v in iteritems(sheets) if v is not None}
    num_merged = num_rules_merged = 0
    if merge_rules:
        for name, sheet in iteritems(sheets):
            num = merge_identical_selectors(sheet)
            if num:
                container.dirty(name)
                num_merged += num
    if merge_rules_with_identical_properties:
        for name, sheet in iteritems(sheets):
            num = merge_identical_properties(sheet)
            if num:
                container.dirty(name)
                num_rules_merged += num
    import_map = {name:get_imported_sheets(name, container, sheets) for name in sheets}
    unreferenced_sheets = set(sheets)
    if remove_unused_classes:
        class_map = {name:{icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)} for name, sheet in iteritems(sheets)}
    style_rules = {name:tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE)) for name, sheet in iteritems(sheets)}

    removal_stats = {'rules': 0, 'selectors': 0}
    num_of_removed_classes = 0

    for name, mt in iteritems(container.mime_map):
        if mt not in OEB_DOCS:
            continue
        root = container.parsed(name)
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        used_classes = set()
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
                original_classes, classes = elem.get('class', '').split(), []
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

    for name, sheet in iteritems(sheets):
        if name in unreferenced_sheets:
            continue
        q = remove_unused_selectors_and_rules(sheet.cssRules, style_rules[name], removal_stats)
        if q.any_unused:
            container.dirty(name)
    num_sheets_removed = 0
    if remove_unreferenced_sheets and len(unreferenced_sheets):
        num_sheets_removed += len(unreferenced_sheets)
        for uname in unreferenced_sheets:
            container.remove_item(uname)

    num_changes = num_merged + num_of_removed_classes + num_rules_merged + removal_stats['rules'] + removal_stats['selectors'] + num_sheets_removed
    if num_changes > 0:
        if removal_stats['rules']:
            report(ngettext('Removed one unused CSS style rule', 'Removed {} unused CSS style rules',
                            removal_stats['rules']).format(removal_stats['rules']))
        if removal_stats['selectors']:
            report(ngettext('Removed one unused CSS selector', 'Removed {} unused CSS selectors',
                            removal_stats['selectors']).format(removal_stats['selectors']))
        if num_of_removed_classes > 0:
            report(ngettext('Removed one unused class from the HTML', 'Removed {} unused classes from the HTML',
                   num_of_removed_classes).format(num_of_removed_classes))
        if num_merged > 0:
            report(ngettext('Merged one CSS style rule with identical selectors', 'Merged {} CSS style rules with identical selectors',
                            num_merged).format(num_merged))
        if num_rules_merged > 0:
            report(ngettext('Merged one CSS style rule with identical properties', 'Merged {} CSS style rules with identical properties',
                            num_rules_merged).format(num_rules_merged))
        if num_sheets_removed:
            report(ngettext('Removed one unreferenced stylesheet', 'Removed {} unreferenced stylesheets',
                            num_sheets_removed).format(num_sheets_removed))
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


def filter_declaration(style, properties=()):
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


def filter_sheet(sheet, properties=()):
    from css_parser.css import CSSRule
    changed = False
    remove = []
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        if filter_declaration(rule.style, properties):
            changed = True
            if rule.style.length == 0:
                remove.append(rule)
    for rule in remove:
        sheet.cssRules.remove(rule)
    return changed


def transform_inline_styles(container, name, transform_sheet, transform_style):
    root = container.parsed(name)
    changed = False
    for style in root.xpath('//*[local-name()="style"]'):
        if style.text and (style.get('type') or 'text/css').lower() == 'text/css':
            sheet = container.parse_css(style.text)
            if transform_sheet(sheet):
                changed = True
                style.text = force_unicode(sheet.cssText, 'utf-8')
                pretty_script_or_style(container, style)
    for elem in root.xpath('//*[@style]'):
        text = elem.get('style', None)
        if text:
            style = container.parse_css(text, is_declaration=True)
            if transform_style(style):
                changed = True
                if style.length == 0:
                    del elem.attrib['style']
                else:
                    elem.set('style', force_unicode(style.getCssText(separator=' '), 'utf-8'))
    return changed


def transform_css(container, transform_sheet=None, transform_style=None, names=()):
    if not names:
        types = OEB_STYLES | OEB_DOCS
        names = []
        for name, mt in iteritems(container.mime_map):
            if mt in types:
                names.append(name)

    doc_changed = False

    for name in names:
        mt = container.mime_map[name]
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            if transform_sheet(sheet):
                container.dirty(name)
                doc_changed = True
        elif mt in OEB_DOCS:
            if transform_inline_styles(container, name, transform_sheet, transform_style):
                container.dirty(name)
                doc_changed = True

    return doc_changed


def filter_css(container, properties, names=()):
    '''
    Remove the specified CSS properties from all CSS rules in the book.

    :param properties: Set of properties to remove. For example: :code:`{'font-family', 'color'}`.
    :param names: The files from which to remove the properties. Defaults to all HTML and CSS files in the book.
    '''
    properties = normalize_filter_css(properties)
    return transform_css(container, transform_sheet=partial(filter_sheet, properties=properties),
                         transform_style=partial(filter_declaration, properties=properties), names=names)


def _classes_in_selector(selector, classes):
    for attr in ('selector', 'subselector', 'parsed_tree'):
        s = getattr(selector, attr, None)
        if s is not None:
            _classes_in_selector(s, classes)
    cn = getattr(selector, 'class_name', None)
    if cn is not None:
        classes.add(cn)


@lru_cache(maxsize=4096)
def classes_in_selector(text):
    classes = set()
    try:
        for selector in parse(text):
            _classes_in_selector(selector, classes)
    except SelectorSyntaxError:
        pass
    return classes


def classes_in_rule_list(css_rules):
    classes = set()
    for rule in css_rules:
        if rule.type == rule.STYLE_RULE:
            classes |= classes_in_selector(rule.selectorText)
        elif hasattr(rule, 'cssRules'):
            classes |= classes_in_rule_list(rule.cssRules)
    return classes


def iter_declarations(sheet_or_rule):
    if hasattr(sheet_or_rule, 'cssRules'):
        for rule in sheet_or_rule.cssRules:
            yield from iter_declarations(rule)
    elif hasattr(sheet_or_rule, 'style'):
        yield sheet_or_rule.style
    elif isinstance(sheet_or_rule, CSSStyleDeclaration):
        yield sheet_or_rule


def remove_property_value(prop, predicate):
    ''' Remove the Values that match the predicate from this property. If all
    values of the property would be removed, the property is removed from its
    parent instead. Note that this means the property must have a parent (a
    CSSStyleDeclaration). '''
    removed_vals = list(filter(predicate, prop.propertyValue))
    if len(removed_vals) == len(prop.propertyValue):
        prop.parent.removeProperty(prop.name)
    else:
        x = css_text(prop.propertyValue)
        for v in removed_vals:
            x = x.replace(css_text(v), '').strip()
        prop.propertyValue.cssText = x
    return bool(removed_vals)


RULE_PRIORITIES = {t:i for i, t in enumerate((CSSRule.COMMENT, CSSRule.CHARSET_RULE, CSSRule.IMPORT_RULE, CSSRule.NAMESPACE_RULE))}


def sort_sheet(container, sheet_or_text):
    ''' Sort the rules in a stylesheet. Note that in the general case this can
    change the effective styles, but for most common sheets, it should be safe.
    '''
    sheet = container.parse_css(sheet_or_text) if isinstance(sheet_or_text, str) else sheet_or_text

    def text_sort_key(x):
        return numeric_sort_key(str(x or ''))

    def selector_sort_key(x):
        return (x.specificity, text_sort_key(x.selectorText))

    def rule_sort_key(rule):
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


def add_stylesheet_links(container, name, text):
    root = container.parse_xhtml(text, name)
    head = root.xpath('//*[local-name() = "head"]')
    if not head:
        return
    head = head[0]
    sheets = tuple(container.manifest_items_of_type(lambda mt: mt in OEB_STYLES))
    if not sheets:
        return
    for sname in sheets:
        link = head.makeelement(XHTML('link'), type='text/css', rel='stylesheet', href=container.name_to_href(sname, name))
        head.append(link)
    pretty_xml_tree(head)
    return serialize(root, 'text/html')


def rename_class_in_rule_list(css_rules, old_name, new_name):
    # this regex will not match class names inside attribute value selectors
    # and it will match id selectors that contain .old_name but its the best
    # that can be done without implementing a full parser for CSS selectors
    pat = re.compile(rf'(?<=\.){re.escape(old_name)}(?:\W|$)')

    def repl(m):
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


def rename_class_in_doc(container, root, old_name, new_name):
    changed = False
    pat = re.compile(rf'(?:^|\W){re.escape(old_name)}(?:\W|$)')

    def repl(m):
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


def rename_class(container, old_name, new_name):
    changed = False
    if not old_name or old_name == new_name:
        return changed
    for sheet_name in container.manifest_items_of_type(lambda mt: mt in OEB_STYLES):
        sheet = container.parsed(sheet_name)
        if rename_class_in_rule_list(sheet.cssRules, old_name, new_name):
            container.dirty(sheet_name)
            changed = True
    for doc_name in container.manifest_items_of_type(lambda mt: mt in OEB_DOCS):
        doc = container.parsed(doc_name)
        if rename_class_in_doc(container, doc, old_name, new_name):
            container.dirty(doc_name)
            changed = True
    return changed
