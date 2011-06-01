#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, binascii, re
from textwrap import dedent

from PyQt4.Qt import (QWidget, QDialog, QLabel, QGridLayout, QComboBox,
        QLineEdit, QIntValidator, QDoubleValidator, QFrame, QColor, Qt, QIcon,
        QScrollArea, QPushButton, QVBoxLayout, QDialogButtonBox)

from calibre.utils.icu import sort_key
from calibre.gui2 import error_dialog

class Rule(object): # {{{

    SIGNATURE = '# BasicColorRule():'

    def __init__(self, fm):
        self.color = None
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
                test(and('1',
                         {conditions}
                    ), {color}, '')
                ''').format(sig=self.signature, conditions=conditions,
                        color=self.color)

    def apply_condition(self, condition):
        col, action, val = condition
        m = self.fm[col]
        dt = m['datatype']

        if dt == 'bool':
            return self.bool_condition(col, action, val)

        if dt in ('int', 'float', 'rating'):
            return self.number_condition(col, action, val)

        if dt == 'datetime':
            return self.date_condition(col, action, val)

        if dt in ('comments', 'series', 'text', 'enumeration'):
            ism = m.get('is_multiple', False)
            if ism:
                return self.multiple_condition(col, action, val, ism)
            return self.text_condition(col, action, val)

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
        lt, eq, gt = '', '1', ''
        return "cmp(field('%s'), %s, '%s', '%s', '%s')" % (col, val, lt, eq, gt)

    def date_condition(self, col, action, val):
        lt, eq, gt = {
                'eq': ('', '1', ''),
                'lt': ('1', '', ''),
                'gt': ('', '', '1')
        }[action]
        return "cmp(format_date('%s', 'yyyy-MM-dd'), %s, '%s', '%s', '%s')" % (col,
                val, lt, eq, gt)

    def multiple_condition(self, col, action, val, sep):
        if action == 'is set':
            return "test('%s', '1', '')"%col
        if action == 'is not set':
            return "test('%s', '', '1')"%col
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
            return "test('%s', '1', '')"%col
        if action == 'is not set':
            return "test('%s', '', '1')"%col
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
                'comments', 'text', 'enumeration', 'datetime'):
            yield key


def displayable_columns(fm):
    for key in fm.displayable_field_keys():
        if key not in ('sort', 'author_sort', 'comments', 'formats',
                'identifiers', 'path'):
            yield key

class ConditionEditor(QWidget):

    def __init__(self, fm, parent=None):
        QWidget.__init__(self, parent)
        self.fm = fm

        self.action_map = {
            'bool' : (
                    (_('is true'), 'is true',),
                    (_('is false'), 'is false'),
                    (_('is undefined'), 'is undefined')
            ),
            'int' : (
                (_('is equal to'), 'eq'),
                (_('is less than'), 'lt'),
                (_('is greater than'), 'gt')
            ),
            'multiple' : (
                (_('has'), 'has'),
                (_('does not have'), 'does not have'),
                (_('has pattern'), 'has pattern'),
                (_('does not have pattern'), 'does not have pattern'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
            ),
            'single'   : (
                (_('is'), 'is'),
                (_('is not'), 'is not'),
                (_('matches pattern'), 'matches pattern'),
                (_('does not match pattern'), 'does not match pattern'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
            ),
        }

        for x in ('float', 'rating', 'datetime'):
            self.action_map[x] = self.action_map['int']

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel(_('If the '))
        l.addWidget(l1, 0, 0)

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 0, 1)

        self.l2 = l2 = QLabel(_(' column '))
        l.addWidget(l2, 0, 2)

        self.action_box = QComboBox(self)
        l.addWidget(self.action_box, 0, 3)

        self.l3 = l3 = QLabel(_(' the value '))
        l.addWidget(l3, 0, 4)

        self.value_box = QLineEdit(self)
        l.addWidget(self.value_box, 0, 5)

        self.column_box.addItem('', '')
        for key in sorted(
                conditionable_columns(fm),
                key=lambda x:sort_key(fm[x]['name'])):
            self.column_box.addItem(fm[key]['name'], key)
        self.column_box.setCurrentIndex(0)

        self.column_box.currentIndexChanged.connect(self.init_action_box)
        self.action_box.currentIndexChanged.connect(self.init_value_box)

        for b in (self.column_box, self.action_box):
            b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(15)

    @dynamic_property
    def current_col(self):
        def fget(self):
            idx = self.column_box.currentIndex()
            return unicode(self.column_box.itemData(idx).toString())
        def fset(self, val):
            for idx in range(self.column_box.count()):
                c = unicode(self.column_box.itemData(idx).toString())
                if c == val:
                    self.column_box.setCurrentIndex(idx)
                    return
            raise ValueError('Column %r not found'%val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def current_action(self):
        def fget(self):
            idx = self.action_box.currentIndex()
            return unicode(self.action_box.itemData(idx).toString())
        def fset(self, val):
            for idx in range(self.action_box.count()):
                c = unicode(self.action_box.itemData(idx).toString())
                if c == val:
                    self.action_box.setCurrentIndex(idx)
                    return
            raise ValueError('Action %r not valid for current column'%val)
        return property(fget=fget, fset=fset)

    @property
    def current_val(self):
        return unicode(self.value_box.text()).strip()

    @dynamic_property
    def condition(self):

        def fget(self):
            c, a, v = (self.current_col, self.current_action,
                    self.current_val)
            if not c or not a:
                return None
            return (c, a, v)

        def fset(self, condition):
            c, a, v = condition
            if not v:
                v = ''
            v = v.strip()
            self.current_col = c
            self.current_action = a
            self.value_box.setText(v)

        return property(fget=fget, fset=fset)

    def init_action_box(self):
        self.action_box.blockSignals(True)
        self.action_box.clear()
        self.action_box.addItem('', '')
        col = self.current_col
        m = self.fm[col]
        dt = m['datatype']
        if dt in self.action_map:
            actions = self.action_map[dt]
        else:
            k = 'multiple' if m['is_multiple'] else 'single'
            actions = self.action_map[k]

        for text, key in actions:
            self.action_box.addItem(text, key)
        self.action_box.setCurrentIndex(0)
        self.action_box.blockSignals(False)
        self.init_value_box()

    def init_value_box(self):
        self.value_box.setEnabled(True)
        self.value_box.setText('')
        self.value_box.setInputMask('')
        self.value_box.setValidator(None)
        col = self.current_col
        m = self.fm[col]
        dt = m['datatype']
        action = self.current_action
        if not col or not action:
            return
        tt = ''
        if dt in ('int', 'float', 'rating'):
            tt = _('Enter a number')
            v = QIntValidator if dt == 'int' else QDoubleValidator
            self.value_box.setValidator(v(self.value_box))
        elif dt == 'datetime':
            self.value_box.setInputMask('9999-99-99')
            tt = _('Enter a date in the format YYYY-MM-DD')
        else:
            tt = _('Enter a string')
            if 'pattern' in action:
                tt = _('Enter a regular expression')
        self.value_box.setToolTip(tt)
        if action in ('is set', 'is not set'):
            self.value_box.setEnabled(False)


class RuleEditor(QDialog):

    def __init__(self, fm, parent=None):
        QDialog.__init__(self, parent)
        self.fm = fm

        self.setWindowIcon(QIcon(I('format-fill-color.png')))
        self.setWindowTitle(_('Create/edit a column coloring rule'))

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel(_('Create a coloring rule by'
            ' filling in the boxes below'))
        l.addWidget(l1, 0, 0, 1, 4)

        self.f1 = QFrame(self)
        self.f1.setFrameShape(QFrame.HLine)
        l.addWidget(self.f1, 1, 0, 1, 4)

        self.l2 = l2 = QLabel(_('Set the color of the column:'))
        l.addWidget(l2, 2, 0)

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 2, 1)

        self.l3 = l3 = QLabel(_('to'))
        l3.setAlignment(Qt.AlignHCenter)
        l.addWidget(l3, 2, 2)

        self.color_box = QComboBox(self)
        l.addWidget(self.color_box, 2, 3)

        self.l4 = l4 = QLabel(
            _('Only if the following conditions are all satisfied:'))
        l4.setAlignment(Qt.AlignHCenter)
        l.addWidget(l4, 3, 0, 1, 4)

        self.scroll_area = sa = QScrollArea(self)
        sa.setMinimumHeight(300)
        sa.setMinimumWidth(950)
        sa.setWidgetResizable(True)
        l.addWidget(sa, 4, 0, 1, 4)

        self.add_button = b = QPushButton(QIcon(I('plus.png')),
                _('Add another condition'))
        l.addWidget(b, 5, 0, 1, 4)
        b.clicked.connect(self.add_blank_condition)

        self.l5 = l5 = QLabel(_('You can disable a condition by'
            ' blanking all of its boxes'))
        l.addWidget(l5, 6, 0, 1, 4)

        self.bb = bb = QDialogButtonBox(
                QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 7, 0, 1, 4)

        self.conditions_widget = QWidget(self)
        sa.setWidget(self.conditions_widget)
        self.conditions_widget.setLayout(QVBoxLayout())
        self.conditions = []

        for b in (self.column_box, self.color_box):
            b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(15)

        for key in sorted(
                displayable_columns(fm),
                key=lambda x:sort_key(fm[x]['name'])):
            name = fm[key]['name']
            if name:
                self.column_box.addItem(name, key)
        self.column_box.setCurrentIndex(0)

        self.color_box.addItems(QColor.colorNames())
        self.color_box.setCurrentIndex(0)

        self.resize(self.sizeHint())

    def add_blank_condition(self):
        c = ConditionEditor(self.fm, parent=self.conditions_widget)
        self.conditions.append(c)
        self.conditions_widget.layout().addWidget(c)

    def accept(self):
        if self.validate():
            QDialog.accept(self)

    def validate(self):
        r = Rule(self.fm)
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                try:
                    r.add_condition(*condition)
                except Exception as e:
                    import traceback
                    error_dialog(self, _('Invalid condition'),
                            _('One of the conditions for this rule is'
                                ' invalid: <b>%s</b>')%e,
                            det_msg=traceback.format_exc(), show=True)
                    return False
        if len(r.conditions) < 1:
            error_dialog(self, _('No conditions'),
                    _('You must specify at least one non-empty condition'
                        ' for this rule'), show=True)
            return False
        return True

    @property
    def rule(self):
        r = Rule(self.fm)
        r.color = unicode(self.color_box.currentText())
        idx = self.column_box.currentIndex()
        col = unicode(self.column_box.itemData(idx).toString())
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                r.add_condition(*condition)

        return col, r



if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])

    from calibre.library import db

    d = RuleEditor(db().field_metadata)
    d.add_blank_condition()
    d.exec_()

    col, r = d.rule

    print ('Column to be colored:', col)
    print ('Template:')
    print (r.template)

