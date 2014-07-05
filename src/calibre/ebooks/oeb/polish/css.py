#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml import etree
from cssutils.css import CSSRule
from cssselect import HTMLTranslator, parse
from cssselect.xpath import XPathExpr, is_safe_name
from cssselect.parser import SelectorSyntaxError

from calibre import force_unicode
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS, XPNSMAP, XHTML_NS
from calibre.ebooks.oeb.normalize_css import normalize_filter_css, normalizers
from calibre.ebooks.oeb.stylizer import MIN_SPACE_RE, is_non_whitespace, xpath_lower_case, fix_namespace
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style

class NamespacedTranslator(HTMLTranslator):

    def xpath_element(self, selector):
        element = selector.element
        if not element:
            element = '*'
            safe = True
        else:
            safe = is_safe_name(element)
            if safe:
                # We use the h: prefix for the XHTML namespace
                element = 'h:%s' % element.lower()
        xpath = XPathExpr(element=element)
        if not safe:
            xpath.add_name_test()
        return xpath

class CaseInsensitiveAttributesTranslator(NamespacedTranslator):
    'Treat class and id CSS selectors case-insensitively'

    def xpath_class(self, class_selector):
        """Translate a class selector."""
        x = self.xpath(class_selector.selector)
        if is_non_whitespace(class_selector.class_name):
            x.add_condition(
                "%s and contains(concat(' ', normalize-space(%s), ' '), %s)"
                % ('@class', xpath_lower_case('@class'), self.xpath_literal(
                    ' '+class_selector.class_name.lower()+' ')))
        else:
            x.add_condition('0')
        return x

    def xpath_hash(self, id_selector):
        """Translate an ID selector."""
        x = self.xpath(id_selector.selector)
        return self.xpath_attrib_equals(x, xpath_lower_case('@id'),
                (id_selector.id.lower()))

css_to_xpath = NamespacedTranslator().css_to_xpath
ci_css_to_xpath = CaseInsensitiveAttributesTranslator().css_to_xpath

def build_selector(text, case_sensitive=True):
    func = css_to_xpath if case_sensitive else ci_css_to_xpath
    try:
        return etree.XPath(fix_namespace(func(text)), namespaces=XPNSMAP)
    except Exception:
        return None

def is_rule_used(root, selector, log, pseudo_pat, cache):
    selector = pseudo_pat.sub('', selector)
    selector = MIN_SPACE_RE.sub(r'\1', selector)
    try:
        xp = cache[(True, selector)]
    except KeyError:
        xp = cache[(True, selector)] = build_selector(selector)
    try:
        if xp(root):
            return True
    except Exception:
        return True

    # See if interpreting class and id selectors case-insensitively gives us
    # matches. Strictly speaking, class and id selectors should be case
    # sensitive for XHTML, but we err on the side of caution and not remove
    # them, since case sensitivity depends on whether the html is rendered in
    # quirks mode or not.
    try:
        xp = cache[(False, selector)]
    except KeyError:
        xp = cache[(False, selector)] = build_selector(selector, case_sensitive=False)
    try:
        return bool(xp(root))
    except Exception:
        return True

def filter_used_rules(root, rules, log, pseudo_pat, cache):
    for rule in rules:
        used = False
        for selector in rule.selectorList:
            text = selector.selectorText
            if is_rule_used(root, text, log, pseudo_pat, cache):
                used = True
                break
        if not used:
            yield rule

def process_namespaces(sheet):
    # Find the namespace prefix (if any) for the XHTML namespace, so that we
    # can preserve it after processing
    for prefix in sheet.namespaces:
        if sheet.namespaces[prefix] == XHTML_NS:
            return prefix

def preserve_htmlns_prefix(sheet, prefix):
    if prefix is None:
        while 'h' in sheet.namespaces:
            del sheet.namespaces['h']
    else:
        sheet.namespaces[prefix] = XHTML_NS

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
    sheet_namespace = {}
    for sheet in sheets.itervalues():
        sheet_namespace[sheet] = process_namespaces(sheet)
        sheet.namespaces['h'] = XHTML_NS
    style_rules = {name:tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE)) for name, sheet in sheets.iteritems()}

    num_of_removed_rules = num_of_removed_classes = 0
    pseudo_pat = re.compile(r':(first-letter|first-line|link|hover|visited|active|focus|before|after)', re.I)
    cache = {}

    for name, mt in container.mime_map.iteritems():
        if mt not in OEB_DOCS:
            continue
        root = container.parsed(name)
        used_classes = set()
        for style in root.xpath('//*[local-name()="style"]'):
            if style.get('type', 'text/css') == 'text/css' and style.text:
                sheet = container.parse_css(style.text)
                if remove_unused_classes:
                    used_classes |= {icu_lower(x) for x in classes_in_rule_list(sheet.cssRules)}
                imports = get_imported_sheets(name, container, sheets, sheet=sheet)
                for imported_sheet in imports:
                    style_rules[imported_sheet] = tuple(filter_used_rules(root, style_rules[imported_sheet], container.log, pseudo_pat, cache))
                    if remove_unused_classes:
                        used_classes |= class_map[imported_sheet]
                ns = process_namespaces(sheet)
                sheet.namespaces['h'] = XHTML_NS
                rules = tuple(sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE))
                unused_rules = tuple(filter_used_rules(root, rules, container.log, pseudo_pat, cache))
                if unused_rules:
                    num_of_removed_rules += len(unused_rules)
                    [sheet.cssRules.remove(r) for r in unused_rules]
                    preserve_htmlns_prefix(sheet, ns)
                    style.text = force_unicode(sheet.cssText, 'utf-8')
                    pretty_script_or_style(container, style)
                    container.dirty(name)

        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = container.href_to_name(link.get('href'), name)
            if sname not in sheets:
                continue
            style_rules[sname] = tuple(filter_used_rules(root, style_rules[sname], container.log, pseudo_pat, cache))
            if remove_unused_classes:
                used_classes |= class_map[sname]

            for iname in import_map[sname]:
                style_rules[iname] = tuple(filter_used_rules(root, style_rules[iname], container.log, pseudo_pat, cache))
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
        preserve_htmlns_prefix(sheet, sheet_namespace[sheet])
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

def filter_declaration(style, properties):
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

def filter_sheet(sheet, properties):
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


def filter_css(container, properties, names=()):
    '''
    Remove the specified CSS properties from all CSS rules in the book.

    :param properties: Set of properties to remove. For example: :code:`{'font-family', 'color'}`.
    :param names: The files from which to remove the properties. Defaults to all HTML and CSS files in the book.
    '''
    if not names:
        types = OEB_STYLES | OEB_DOCS
        names = []
        for name, mt in container.mime_map.iteritems():
            if mt in types:
                names.append(name)
    properties = normalize_filter_css(properties)
    doc_changed = False

    for name in names:
        mt = container.mime_map[name]
        if mt in OEB_STYLES:
            sheet = container.parsed(name)
            filtered = filter_sheet(sheet, properties)
            if filtered:
                container.dirty(name)
                doc_changed = True
        elif mt in OEB_DOCS:
            root = container.parsed(name)
            changed = False
            for style in root.xpath('//*[local-name()="style"]'):
                if style.text and style.get('type', 'text/css') in {None, '', 'text/css'}:
                    sheet = container.parse_css(style.text)
                    if filter_sheet(sheet, properties):
                        changed = True
                        style.text = force_unicode(sheet.cssText, 'utf-8')
                        pretty_script_or_style(container, style)
            for elem in root.xpath('//*[@style]'):
                text = elem.get('style', None)
                if text:
                    style = container.parse_css(text, is_declaration=True)
                    if filter_declaration(style, properties):
                        changed = True
                        if style.length == 0:
                            del elem.attrib['style']
                        else:
                            elem.set('style', force_unicode(style.getCssText(separator=' '), 'utf-8'))
            if changed:
                container.dirty(name)
                doc_changed = True

    return doc_changed

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

