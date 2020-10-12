#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial
from collections import OrderedDict
import operator, numbers

from css_parser.css import Property, CSSRule

from calibre import force_unicode
from calibre.ebooks import parse_css_length
from calibre.ebooks.oeb.normalize_css import normalizers, safe_parser
from polyglot.builtins import iteritems, unicode_type


def compile_pat(pat):
    import regex
    REGEX_FLAGS = regex.VERSION1 | regex.UNICODE | regex.IGNORECASE
    return regex.compile(pat, flags=REGEX_FLAGS)


def all_properties(decl):
    ' This is needed because CSSStyleDeclaration.getProperties(None, all=True) does not work and is slower than it needs to be. '
    for item in decl.seq:
        p = item.value
        if isinstance(p, Property):
            yield p


class StyleDeclaration(object):

    def __init__(self, css_declaration):
        self.css_declaration = css_declaration
        self.expanded_properties = {}
        self.changed = False

    def __iter__(self):
        dec = self.css_declaration
        for p in all_properties(dec):
            n = normalizers.get(p.name)
            if n is None:
                yield p, None
            else:
                if p not in self.expanded_properties:
                    self.expanded_properties[p] = [Property(k, v, p.literalpriority) for k, v in iteritems(n(p.name, p.propertyValue))]
                for ep in self.expanded_properties[p]:
                    yield ep, p

    def expand_property(self, parent_prop):
        props = self.expanded_properties.pop(parent_prop, None)
        if props is None:
            return
        dec = self.css_declaration
        seq = dec._tempSeq()
        for item in dec.seq:
            if item.value is parent_prop:
                for c in sorted(props, key=operator.attrgetter('name')):
                    c.parent = dec
                    seq.append(c, 'Property')
            else:
                seq.appendItem(item)
        dec._setSeq(seq)

    def remove_property(self, prop, parent_prop):
        if parent_prop is not None:
            self.expand_property(parent_prop)
        dec = self.css_declaration
        seq = dec._tempSeq()
        for item in dec.seq:
            if item.value is not prop:
                seq.appendItem(item)
        dec._setSeq(seq)
        self.changed = True

    def change_property(self, prop, parent_prop, val, match_pat=None):
        if parent_prop is not None:
            self.expand_property(parent_prop)
        if match_pat is None:
            prop.value = val
        else:
            prop.value = match_pat.sub(val, prop.value)
        self.changed = True

    def append_properties(self, props):
        if props:
            self.changed = True
            for prop in props:
                self.css_declaration.setProperty(Property(prop.name, prop.value, prop.literalpriority, parent=self.css_declaration))

    def set_property(self, name, value, priority='', replace=True):
        # Note that this does not handle shorthand properties, so you must
        # call remove_property() yourself in that case
        self.changed = True
        if replace:
            self.css_declaration.removeProperty(name)
        self.css_declaration.setProperty(Property(name, value, priority, parent=self.css_declaration))

    def __str__(self):
        return force_unicode(self.css_declaration.cssText, 'utf-8')


operator_map = {'==':'eq', '!=': 'ne', '<=':'le', '<':'lt', '>=':'ge', '>':'gt', '-':'sub', '+': 'add', '*':'mul', '/':'truediv'}


def unit_convert(value, unit, dpi=96.0, body_font_size=12):
    result = None
    if unit == 'px':
        result = value * 72.0 / dpi
    elif unit == 'in':
        result = value * 72.0
    elif unit == 'pt':
        result = value
    elif unit == 'pc':
        result = value * 12.0
    elif unit == 'mm':
        result = value * 2.8346456693
    elif unit == 'cm':
        result = value * 28.346456693
    elif unit == 'rem':
        result = value * body_font_size
    elif unit == 'q':
        result = value * 0.708661417325
    return result


def parse_css_length_or_number(raw, default_unit=None):
    if isinstance(raw, numbers.Number):
        return raw, default_unit
    try:
        return float(raw), default_unit
    except Exception:
        return parse_css_length(raw)


def numeric_match(value, unit, pts, op, raw):
    try:
        v, u = parse_css_length_or_number(raw)
    except Exception:
        return False
    if v is None:
        return False
    if unit is None or u is None or unit == u:
        return op(v, value)
    if pts is None:
        return False
    p = unit_convert(v, u)
    if p is None:
        return False
    return op(p, pts)


def transform_number(val, op, raw):
    try:
        v, u = parse_css_length_or_number(raw, default_unit='')
    except Exception:
        return raw
    if v is None:
        return raw
    v = op(v, val)
    if int(v) == v:
        v = int(v)
    return unicode_type(v) + u


class Rule(object):

    def __init__(self, property='color', match_type='*', query='', action='remove', action_data=''):
        self.property_name = property.lower()
        self.action, self.action_data = action, action_data
        self.match_pat = None
        if self.action == 'append':
            decl = safe_parser().parseStyle(self.action_data)
            self.appended_properties = list(all_properties(decl))
        elif self.action in '+-/*':
            self.action_operator = partial(transform_number, float(self.action_data), getattr(operator, operator_map[self.action]))
        if match_type == 'is':
            self.property_matches = lambda x: x.lower() == query.lower()
        elif match_type == 'is_not':
            self.property_matches = lambda x: x.lower() != query.lower()
        elif match_type == '*':
            self.property_matches = lambda x: True
        elif 'matches' in match_type:
            self.match_pat = compile_pat(query)
            if match_type.startswith('not_'):
                self.property_matches = lambda x: self.match_pat.match(x) is None
            else:
                self.property_matches = lambda x: self.match_pat.match(x) is not None
        else:
            value, unit = parse_css_length_or_number(query)
            op = getattr(operator, operator_map[match_type])
            pts = unit_convert(value, unit)
            self.property_matches = partial(numeric_match, value, unit, pts, op)

    def process_declaration(self, declaration):
        oval, declaration.changed = declaration.changed, False
        for prop, parent_prop in tuple(declaration):
            if prop.name == self.property_name and self.property_matches(prop.value):
                if self.action == 'remove':
                    declaration.remove_property(prop, parent_prop)
                elif self.action == 'change':
                    declaration.change_property(prop, parent_prop, self.action_data, self.match_pat)
                elif self.action == 'append':
                    declaration.append_properties(self.appended_properties)
                else:
                    val = prop.value
                    nval = self.action_operator(val)
                    if val != nval:
                        declaration.change_property(prop, parent_prop, nval)
        changed = declaration.changed
        declaration.changed = oval or changed
        return changed


ACTION_MAP = OrderedDict((
    ('remove', _('Remove the property')),
    ('append', _('Add extra properties')),
    ('change', _('Change the value to')),
    ('*', _('Multiply the value by')),
    ('/', _('Divide the value by')),
    ('+', _('Add to the value')),
    ('-', _('Subtract from the value')),
))

MATCH_TYPE_MAP = OrderedDict((
    ('is', _('is')),
    ('is_not', _('is not')),
    ('*', _('is any value')),
    ('matches', _('matches pattern')),
    ('not_matches', _('does not match pattern')),
    ('==', _('is the same length as')),
    ('!=', _('is not the same length as')),
    ('<', _('is less than')),
    ('>', _('is greater than')),
    ('<=', _('is less than or equal to')),
    ('>=', _('is greater than or equal to')),
))

allowed_keys = frozenset('property match_type query action action_data'.split())


def validate_rule(rule):
    keys = frozenset(rule)
    extra = keys - allowed_keys
    if extra:
        return _('Unknown keys'), _(
            'The rule has unknown keys: %s') % ', '.join(extra)
    missing = allowed_keys - keys
    if missing:
        return _('Missing keys'), _(
            'The rule has missing keys: %s') % ', '.join(missing)
    mt = rule['match_type']
    if not rule['property']:
        return _('Property required'), _('You must specify a CSS property to match')
    if rule['property'] in normalizers:
        return _('Shorthand property not allowed'), _(
            '{0} is a shorthand property. Use the full form of the property,'
            ' for example, instead of font, use font-family, instead of margin, use margin-top, etc.').format(rule['property'])
    if not rule['query'] and mt != '*':
        _('Query required'), _(
            'You must specify a value for the CSS property to match')
    if mt not in MATCH_TYPE_MAP:
        return _('Unknown match type'), _(
            'The match type %s is not known') % mt
    if 'matches' in mt:
        try:
            compile_pat(rule['query'])
        except Exception:
            return _('Query invalid'), _(
                '%s is not a valid regular expression') % rule['query']
    elif mt in '< > <= >= == !='.split():
        try:
            num = parse_css_length_or_number(rule['query'])[0]
            if num is None:
                raise Exception('not a number')
        except Exception:
            return _('Query invalid'), _(
                '%s is not a valid length or number') % rule['query']
    ac, ad = rule['action'], rule['action_data']
    if ac not in ACTION_MAP:
        return _('Unknown action type'), _(
            'The action type %s is not known') % mt
    if not ad and ac != 'remove':
        msg = _('You must specify a number')
        if ac == 'append':
            msg = _('You must specify at least one CSS property to add')
        elif ac == 'change':
            msg = _('You must specify a value to change the property to')
        return _('No data'), msg
    if ac in '+-*/':
        try:
            float(ad)
        except Exception:
            return _('Invalid number'), _('%s is not a number') % ad
    return None, None


def compile_rules(serialized_rules):
    return [Rule(**r) for r in serialized_rules]


def transform_declaration(compiled_rules, decl):
    decl = StyleDeclaration(decl)
    changed = False
    for rule in compiled_rules:
        if rule.process_declaration(decl):
            changed = True
    return changed


def transform_sheet(compiled_rules, sheet):
    changed = False
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        if transform_declaration(compiled_rules, rule.style):
            changed = True
    return changed


def transform_container(container, serialized_rules, names=()):
    from calibre.ebooks.oeb.polish.css import transform_css
    rules = compile_rules(serialized_rules)
    return transform_css(
        container, transform_sheet=partial(transform_sheet, rules),
        transform_style=partial(transform_declaration, rules), names=names
    )


def rule_to_text(rule):
    def get(prop):
        return rule.get(prop) or ''
    text = _(
        'If the property {property} {match_type} {query}\n{action}').format(
            property=get('property'), action=ACTION_MAP[rule['action']],
            match_type=MATCH_TYPE_MAP[rule['match_type']], query=get('query'))
    if get('action_data'):
        text += get('action_data')
    return text


def export_rules(serialized_rules):
    lines = []
    for rule in serialized_rules:
        lines.extend('# ' + l for l in rule_to_text(rule).splitlines())
        lines.extend('%s: %s' % (k, v.replace('\n', ' ')) for k, v in iteritems(rule) if k in allowed_keys)
        lines.append('')
    return '\n'.join(lines).encode('utf-8')


def import_rules(raw_data):
    import regex
    pat = regex.compile(r'\s*(\S+)\s*:\s*(.+)', flags=regex.VERSION1)
    current_rule = {}

    def sanitize(r):
        return {k:(r.get(k) or '') for k in allowed_keys}

    for line in raw_data.decode('utf-8').splitlines():
        if not line.strip():
            if current_rule:
                yield sanitize(current_rule)
            current_rule = {}
            continue
        if line.lstrip().startswith('#'):
            continue
        m = pat.match(line)
        if m is not None:
            k, v = m.group(1).lower(), m.group(2)
            if k in allowed_keys:
                current_rule[k] = v
    if current_rule:
        yield sanitize(current_rule)


def test(return_tests=False):  # {{{
    import unittest

    def apply_rule(style, **rule):
        r = Rule(**rule)
        decl = StyleDeclaration(safe_parser().parseStyle(style))
        r.process_declaration(decl)
        return unicode_type(decl)

    class TestTransforms(unittest.TestCase):
        longMessage = True
        maxDiff = None
        ae = unittest.TestCase.assertEqual

        def test_matching(self):

            def m(match_type='*', query='', action_data=''):
                action = 'change' if action_data else 'remove'
                self.ae(apply_rule(
                    css, property=prop, match_type=match_type, query=query, action=action, action_data=action_data
                ), ecss)

            prop = 'font-size'
            css, ecss = 'font-size: 1.2rem', 'font-size: 1.2em'
            m('matches', query='(.+)rem', action_data=r'\1em')

            prop = 'color'
            css, ecss = 'color: red; margin: 0', 'margin: 0'
            m('*')
            m('is', 'red')
            m('is_not', 'blue')
            m('matches', 'R.d')
            m('not_matches', 'blue')
            ecss = css.replace('; ', ';\n')
            m('is', 'blue')
            css, ecss = 'color: currentColor; line-height: 0', 'line-height: 0'
            m('is', 'currentColor')

            prop = 'margin-top'
            css, ecss = 'color: red; margin-top: 10', 'color: red'
            m('*')
            m('==', '10')
            m('!=', '11')
            m('<=', '10')
            m('>=', '10')
            m('<', '11')
            m('>', '9')
            css, ecss = 'color: red; margin-top: 1mm', 'color: red'
            m('==', '1')
            m('==', '1mm')
            m('==', '4q')
            ecss = css.replace('; ', ';\n')
            m('==', '1pt')

        def test_expansion(self):

            def m(css, ecss, action='remove', action_data=''):
                self.ae(ecss, apply_rule(css, property=prop, action=action, action_data=action_data))

            prop = 'margin-top'
            m('margin: 0', 'margin-bottom: 0;\nmargin-left: 0;\nmargin-right: 0')
            m('margin: 0 !important', 'margin-bottom: 0 !important;\nmargin-left: 0 !important;\nmargin-right: 0 !important')
            m('margin: 0', 'margin-bottom: 0;\nmargin-left: 0;\nmargin-right: 0;\nmargin-top: 1pt', 'change', '1pt')
            prop = 'font-family'
            m('font: 10em "Kovid Goyal", monospace', 'font-size: 10em;\nfont-style: normal;\nfont-variant: normal;\nfont-weight: normal;\nline-height: normal')

        def test_append(self):
            def m(css, ecss, action_data=''):
                self.ae(ecss, apply_rule(css, property=prop, action='append', action_data=action_data))
            prop = 'color'
            m('color: red', 'color: red;\nmargin: 1pt;\nfont-weight: bold', 'margin: 1pt; font-weight: bold')

        def test_change(self):
            def m(css, ecss, action='change', action_data=''):
                self.ae(ecss, apply_rule(css, property=prop, action=action, action_data=action_data))
            prop = 'font-family'
            m('font-family: a, b', 'font-family: "c c", d', action_data='"c c", d')
            prop = 'line-height'
            m('line-height: 1', 'line-height: 3', '*', '3')
            m('line-height: 1em', 'line-height: 4em', '+', '3')
            m('line-height: 1', 'line-height: 0', '-', '1')
            m('line-height: 2', 'line-height: 1', '/', '2')
            prop = 'border-top-width'
            m('border-width: 1', 'border-bottom-width: 1;\nborder-left-width: 1;\nborder-right-width: 1;\nborder-top-width: 3', '*', '3')
            prop = 'font-size'

        def test_export_import(self):
            rule = {'property':'a', 'match_type':'*', 'query':'some text', 'action':'remove', 'action_data':'color: red; a: b'}
            self.ae(rule, next(import_rules(export_rules([rule]))))

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestTransforms)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)


if __name__ == '__main__':
    test()
# }}}
