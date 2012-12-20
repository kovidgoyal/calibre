#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import binascii, re, json
from textwrap import dedent

color_row_key = '*row'

class Rule(object): # {{{

    SIGNATURE = '# BasicColorRule():'

    def __init__(self, fm, color=None):
        self.color = color
        self.fm = fm
        self.conditions = []

    def add_condition(self, col, action, val):
        if col not in self.fm:
            raise ValueError('%r is not a valid column name'%col)
        v = self.validate_condition(col, action, val)
        if v:
            raise ValueError(v)
        self.conditions.append((col, action, val))

    def validate_condition(self, col, action, val):
        m = self.fm[col]
        dt = m['datatype']
        if (dt in ('int', 'float', 'rating') and action in ('lt', 'eq', 'gt')):
            try:
                int(val) if dt == 'int' else float(val)
            except:
                return '%r is not a valid numerical value'%val

        if (dt in ('comments', 'series', 'text', 'enumeration') and 'pattern'
                in action):
            try:
                re.compile(val)
            except:
                return '%r is not a valid regular expression'%val

    @property
    def signature(self):
        args = (self.color, self.conditions)
        sig = json.dumps(args, ensure_ascii=False)
        return self.SIGNATURE + binascii.hexlify(sig.encode('utf-8'))

    @property
    def template(self):
        if not self.color or not self.conditions:
            return None
        conditions = map(self.apply_condition, self.conditions)
        conditions = (',\n' + ' '*9).join(conditions)
        return dedent('''\
                program:
                {sig}
                test(and(
                         {conditions}
                    ), '{color}', '');
                ''').format(sig=self.signature, conditions=conditions,
                        color=self.color)

    def apply_condition(self, condition):
        col, action, val = condition
        m = self.fm[col]
        dt = m['datatype']

        if col == 'ondevice':
            return self.ondevice_condition(col, action, val)

        if col == 'identifiers':
            return self.identifiers_condition(col, action, val)

        if dt == 'bool':
            return self.bool_condition(col, action, val)

        if dt in ('int', 'float'):
            return self.number_condition(col, action, val)

        if dt == 'rating':
            return self.rating_condition(col, action, val)

        if dt == 'datetime':
            return self.date_condition(col, action, val)

        if dt in ('comments', 'series', 'text', 'enumeration', 'composite'):
            ism = m.get('is_multiple', False)
            if ism:
                return self.multiple_condition(col, action, val, ism['ui_to_list'])
            return self.text_condition(col, action, val)

    def identifiers_condition(self, col, action, val):
        if action == 'has id':
            return "identifier_in_list(field('identifiers'), '%s', '1', '')"%val
        return "identifier_in_list(field('identifiers'), '%s', '', '1')"%val

    def ondevice_condition(self, col, action, val):
        if action == 'is set':
            return "test(ondevice(), '1', '')"
        if action == 'is not set':
            return "test(ondevice(), '', '1')"

    def bool_condition(self, col, action, val):
        test = {'is true': 'True',
                'is false': 'False',
                'is undefined': 'None'}[action]
        return "strcmp('%s', raw_field('%s'), '', '1', '')"%(test, col)

    def number_condition(self, col, action, val):
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        if col == 'size':
            return "cmp(booksize(), %s, '%s', '%s', '%s')" % (val, lt, eq, gt)
        else:
            return "cmp(raw_field('%s'), %s, '%s', '%s', '%s')" % (col, val, lt, eq, gt)

    def rating_condition(self, col, action, val):
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        return "cmp(field('%s'), %s, '%s', '%s', '%s')" % (col, val, lt, eq, gt)

    def date_condition(self, col, action, val):
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        return "strcmp(format_date(raw_field('%s'), 'yyyy-MM-dd'), '%s', '%s', '%s', '%s')" % (col,
                val, lt, eq, gt)

    def multiple_condition(self, col, action, val, sep):
        if not sep or sep == '|':
            sep = ','
        if action == 'is set':
            return "test(field('%s'), '1', '')"%col
        if action == 'is not set':
            return "test(field('%s'), '', '1')"%col
        if action == 'has':
            return "str_in_list(field('%s'), '%s', \"%s\", '1', '')"%(col, sep, val)
        if action == 'does not have':
            return "str_in_list(field('%s'), '%s', \"%s\", '', '1')"%(col, sep, val)
        if action == 'has pattern':
            return "in_list(field('%s'), '%s', \"%s\", '1', '')"%(col, sep, val)
        if action == 'does not have pattern':
            return "in_list(field('%s'), '%s', \"%s\", '', '1')"%(col, sep, val)

    def text_condition(self, col, action, val):
        if action == 'is set':
            return "test(field('%s'), '1', '')"%col
        if action == 'is not set':
            return "test(field('%s'), '', '1')"%col
        if action == 'is':
            return "strcmp(field('%s'), \"%s\", '', '1', '')"%(col, val)
        if action == 'is not':
            return "strcmp(field('%s'), \"%s\", '1', '', '1')"%(col, val)
        if action == 'matches pattern':
            return "contains(field('%s'), \"%s\", '1', '')"%(col, val)
        if action == 'does not match pattern':
            return "contains(field('%s'), \"%s\", '', '1')"%(col, val)

# }}}

def rule_from_template(fm, template):
    ok_lines = []
    for line in template.splitlines():
        if line.startswith(Rule.SIGNATURE):
            raw = line[len(Rule.SIGNATURE):].strip()
            try:
                color, conditions = json.loads(binascii.unhexlify(raw).decode('utf-8'))
            except:
                continue
            r = Rule(fm)
            r.color = color
            for c in conditions:
                try:
                    r.add_condition(*c)
                except:
                    continue
            if r.color and r.conditions:
                return r
        else:
            ok_lines.append(line)
    return '\n'.join(ok_lines)

def conditionable_columns(fm):
    for key in fm:
        m = fm[key]
        dt = m['datatype']
        if m.get('name', False) and dt in ('bool', 'int', 'float', 'rating', 'series',
                'comments', 'text', 'enumeration', 'datetime', 'composite'):
            if key == 'sort':
                yield 'title_sort'
            else:
                yield key

def displayable_columns(fm):
    yield (color_row_key)
    for key in fm.displayable_field_keys():
        if key not in ('sort', 'author_sort', 'comments', 'formats',
                'identifiers', 'path'):
            yield key

def migrate_old_rule(fm, template):
    if template.startswith('program:\n#tag wizard'):
        rules = []
        for line in template.splitlines():
            if line.startswith('#') and ':|:' in line:
                value, color = line[1:].split(':|:')
                r = Rule(fm, color=color)
                r.add_condition('tags', 'has', value)
                rules.append(r.template)
        return rules
    return [template]

