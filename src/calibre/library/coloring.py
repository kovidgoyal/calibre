#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid at kovidgoyal.net>


import json
import re
from textwrap import dedent

from calibre.utils.localization import _
from polyglot.binary import as_hex_unicode, from_hex_bytes

color_row_key = '*row'


class Rule:  # {{{

    SIGNATURE = '# BasicColorRule():'

    INVALID_CONDITION = _('INVALID CONDITION')

    def __init__(self, fm, color=None):
        self.color = color
        self.fm = fm
        self.conditions = []

    def add_condition(self, col, action, val):
        if col not in self.fm:
            raise ValueError(f'{col!r} is not a valid column name')
        v = self.validate_condition(col, action, val)
        if v:
            raise ValueError(v)
        if self.apply_condition((col, action, val)) is None:
            action = self.INVALID_CONDITION
        self.conditions.append((col, action, val))

    def validate_condition(self, col, action, val):
        m = self.fm[col]
        dt = m['datatype']
        if (dt in ('int', 'float', 'rating') and action in ('lt', 'eq', 'gt')):
            try:
                int(val) if dt == 'int' else float(val)
            except:
                return f'{val!r} is not a valid numerical value'

        if (dt in ('comments', 'series', 'text', 'enumeration') and 'pattern'
                in action):
            try:
                re.compile(val)
            except:
                return f'{val!r} is not a valid regular expression'

    @property
    def signature(self):
        args = (self.color, self.conditions)
        sig = json.dumps(args, ensure_ascii=False)
        return self.SIGNATURE + as_hex_unicode(sig)

    @property
    def template(self):
        if not self.color or not self.conditions:
            return None
        conditions = [x for x in map(self.apply_condition, self.conditions) if x is not None]
        conditions = (',\n' + ' '*9).join(conditions)
        if len(self.conditions) > 1:
            return dedent('''\
                    program:
                    {sig}
                    test(and(
                             {conditions}
                        ), '{color}', '');
                    ''').format(sig=self.signature, conditions=conditions,
                            color=self.color)
        else:
            return dedent('''\
                    program:
                    {sig}
                    test({conditions}, '{color}', '');
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
            return f"identifier_in_list(field('identifiers'), '{val}', '1', '')"
        return f"identifier_in_list(field('identifiers'), '{val}', '', '1')"

    def ondevice_condition(self, col, action, val):
        if action == 'is set':
            return 'ondevice()'
        if action == 'is not set':
            return '!ondevice()'

    def bool_condition(self, col, action, val):
        test = {'is true':      '0, 0, 1',
                'is not true':  '1, 1, 0',
                'is false':     '0, 1, 0',
                'is not false': '1, 0, 1',
                'is undefined': '1, 0, 0',
                'is defined':   '0, 1, 1'}[action]
        return f"check_yes_no('{col}', {test})"

    def number_condition(self, col, action, val):
        if action == 'is set':
            return f'${col}'
        if action == 'is not set':
            return f'!${col}'
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        if col == 'size':
            return f"cmp(booksize(), {val}, '{lt}', '{eq}', '{gt}')"
        else:
            return f"cmp(raw_field('{col}', 0), {val}, '{lt}', '{eq}', '{gt}')"

    def rating_condition(self, col, action, val):
        if action == 'is set':
            return f'${col}'
        if action == 'is not set':
            return f'!${col}'
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        return f"cmp(field('{col}'), {val}, '{lt}', '{eq}', '{gt}')"

    def date_condition(self, col, action, val):
        if action == 'count_days':
            return (f"test(field('{col}'), cmp({val}, "
                            "days_between(format_date(today(), 'yyyy-MM-dd'),"
                            f"format_date(raw_field('{col}'), 'yyyy-MM-dd')), '', '1', '1'), '')")
        if action == 'older count days':
            return (f"test(field('{col}'), cmp({val}, "
                            "days_between(format_date(today(), 'yyyy-MM-dd'),"
                            f"format_date(raw_field('{col}'), 'yyyy-MM-dd')), '1', '', ''), '')")
        if action == 'older future days':
            return (f"test(field('{col}'), cmp({val}, "
                            f"days_between(format_date(raw_field('{col}'), 'yyyy-MM-dd'), "
                            "format_date(today(), 'yyyy-MM-dd')), '', '1', '1'), '')")
        if action == 'newer future days':
            return (f"test(field('{col}'), cmp({val}, "
                            f"days_between(format_date(raw_field('{col}'), 'yyyy-MM-dd'), "
                            "format_date(today(), 'yyyy-MM-dd')), '1', '', ''), '')")
        if action == 'is set':
            return (f'${col}')
        if action == 'is not set':
            return (f'!${col}')
        if action == 'is today':
            return f"substr(format_date(raw_field('{col}'), 'iso'), 0, 10) == substr(today(), 0, 10)"
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        return (f"strcmp(format_date(raw_field('{col}'), 'yyyy-MM-dd'), '{val}', '{lt}', '{eq}', '{gt}')")

    def multiple_condition(self, col, action, val, sep):
        if not sep or sep == '|':
            sep = ','
        if action == 'is set':
            return f'${col}'
        if action == 'is not set':
            return f'!${col}'
        if action == 'has':
            return f"str_in_list(field('{col}'), '{sep}', \"{val}\", '1', '')"
        if action == 'does not have':
            return f"str_in_list(field('{col}'), '{sep}', \"{val}\", '', '1')"
        if action == 'has pattern':
            return f"in_list(field('{col}'), '{sep}', \"{val}\", '1', '')"
        if action == 'does not have pattern':
            return f"in_list(field('{col}'), '{sep}', \"{val}\", '', '1')"

    def text_condition(self, col, action, val):
        if action == 'is set':
            return f'${col}'
        if action == 'is not set':
            return f'!${col}'
        if action == 'is':
            return f"strcmp(field('{col}'), \"{val}\", '', '1', '')"
        if action == 'is not':
            return f"strcmp(field('{col}'), \"{val}\", '1', '', '1')"
        if action == 'matches pattern':
            return f"contains(field('{col}'), \"{val}\", '1', '')"
        if action == 'does not match pattern':
            return f"contains(field('{col}'), \"{val}\", '', '1')"
        if action == 'contains':
            return f"contains(field('{col}'), \"{re.escape(val)}\", '1', '')"
        if action == 'does not contain':
            return f"contains(field('{col}'), \"{re.escape(val)}\", '', '1')"

# }}}


def rule_from_template(fm, template):
    ok_lines = []
    for line in template.splitlines():
        if line.startswith(Rule.SIGNATURE):
            raw = line[len(Rule.SIGNATURE):].strip()
            try:
                color, conditions = json.loads(from_hex_bytes(raw))
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
    yield color_row_key
    for key in fm.displayable_field_keys():
        if key not in ('sort', 'author_sort', 'comments', 'identifiers',):
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
