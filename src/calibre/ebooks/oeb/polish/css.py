#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from cssutils.css import CSSRule, CSSStyleDeclaration
from css_selectors import parse, SelectorSyntaxError

from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.normalize_css import normalize_filter_css, normalizers
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style
from css_selectors import Select, SelectorError


def filter_used_rules(rules, log, select):
    for rule in rules:
        used = False
        for selector in rule.selectorList:
            try:
                if select.has_matches(selector.selectorText):
                    used = True
                    break
            except SelectorError:
                # Cannot parse/execute this selector, be safe and assume it
                # matches something
                used = True
                break
        if not used:
            yield rule

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

def remove_unused_css(container, report=None, remove_unused_classes=False):
    '''
    Remove all unused CSS rules from the book. An unused CSS rule is one that does not match any actual content.

    :param report: An optional callable that takes a single argument. It is called with information about the operations being performed.
    :param remove_unused_classes: If True, class attributes in the HTML that do not match any CSS rules are also removed.
    '''
    report = report or (lambda x:x)

    def safe_parse(name):
        try:
            return container.parsed(name)
        except TypeError:
            pass
    sheets = {name:safe_parse(name) for name, mt in container.mime_map.iteritems() if mt in OEB_STYLES}
    sheets = {k:v for k, v in sheets.iteritems() if v is not None}
    import_map = {name:get_imported_sheets(name, container, sheets) for name in sheets}
    if remove_unused_classes:
        class_map = {name:{icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)} for name, sheet in sheets.iteritems()}
    style_rules = {name:tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE)) for name, sheet in sheets.iteritems()}

    num_of_removed_rules = num_of_removed_classes = 0

    for name, mt in container.mime_map.iteritems():
        if mt not in OEB_DOCS:
            continue
        root = container.parsed(name)
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        used_classes = set()
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                sheet = container.parse_css(style.text)
                if remove_unused_classes:
                    used_classes |= {icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)}
                imports = get_imported_sheets(name, container, sheets, sheet=sheet)
                for imported_sheet in imports:
                    style_rules[imported_sheet] = tuple(filter_used_rules(style_rules[imported_sheet], container.log, select))
                    if remove_unused_classes:
                        used_classes |= class_map[imported_sheet]
                rules = tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
                unused_rules = tuple(filter_used_rules(rules, container.log, select))
                if unused_rules:
                    num_of_removed_rules += len(unused_rules)
                    [sheet.cssRules.remove(r) for r in unused_rules]
                    style.text = force_unicode(sheet.cssText, 'utf-8')
                    pretty_script_or_style(container, style)
                    container.dirty(name)

        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = container.href_to_name(link.get('href'), name)
            if sname not in sheets:
                continue
            style_rules[sname] = tuple(filter_used_rules(style_rules[sname], container.log, select))
            if remove_unused_classes:
                used_classes |= class_map[sname]

            for iname in import_map[sname]:
                style_rules[iname] = tuple(filter_used_rules(style_rules[iname], container.log, select))
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

    for name, sheet in sheets.iteritems():
        unused_rules = style_rules[name]
        if unused_rules:
            num_of_removed_rules += len(unused_rules)
            [sheet.cssRules.remove(r) for r in unused_rules]
            container.dirty(name)

    if num_of_removed_rules > 0:
        report(ngettext('Removed %d unused CSS style rule', 'Removed %d unused CSS style rules',
                        num_of_removed_rules) % num_of_removed_rules)
    else:
        report(_('No unused CSS style rules found'))
    if remove_unused_classes:
        if num_of_removed_classes > 0:
            report(ngettext('Removed %d unused class from the HTML', 'Removed %d unused classes from the HTML',
                   num_of_removed_classes) % num_of_removed_classes)
        else:
            report(_('No unused class attributes found'))
    return num_of_removed_rules + num_of_removed_classes > 0

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
    from cssutils.css import CSSRule
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


def transform_css(container, transform_sheet=None, transform_style=None, names=()):
    if not names:
        types = OEB_STYLES | OEB_DOCS
        names = []
        for name, mt in container.mime_map.iteritems():
            if mt in types:
                names.append(name)

    doc_changed = False

    for name in names:
        mt = container.mime_map[name]
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            filtered = transform_sheet(sheet)
            if filtered:
                container.dirty(name)
                doc_changed = True
        elif mt in OEB_DOCS:
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
            if changed:
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
            for x in iter_declarations(rule):
                yield x
    elif hasattr(sheet_or_rule, 'style'):
        yield sheet_or_rule.style
    elif isinstance(sheet_or_rule, CSSStyleDeclaration):
        yield sheet_or_rule

def remove_property_value(prop, predicate):
    ''' Remove the Values that match the predicate from this property. If all
    values of the property would be removed, the property is removed from its
    parent instead. Note that this means the property must have a parent (a
    CSSStyleDeclaration). '''
    removed_vals = []
    removed_vals = filter(predicate, prop.propertyValue)
    if len(removed_vals) == len(prop.propertyValue):
        prop.parent.removeProperty(prop.name)
    else:
        x = prop.propertyValue.cssText
        for v in removed_vals:
            x = x.replace(v.cssText, '').strip()
        prop.propertyValue.cssText = x
    return bool(removed_vals)
