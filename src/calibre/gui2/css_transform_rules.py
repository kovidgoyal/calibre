#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from collections import OrderedDict

from PyQt5.Qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QListWidgetItem
)

from calibre.ebooks.css_transform_rules import compile_pat, parse_css_length_or_number
from calibre.ebooks.oeb.normalize_css import SHORTHAND_DEFAULTS
from calibre.gui2 import error_dialog, elided_text
from calibre.gui2.tag_mapper import RuleEditDialog as RuleEditDialogBase, Rules as RulesBase

class RuleEdit(QWidget):  # {{{

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
        ('*', _('is any value')),
        ('matches', _('matches pattern')),
        ('not_matches', _('does not match pattern'))
        ('==', _('is the same length as')),
        ('<', _('is less than')),
        ('>', _('is greater than')),
        ('<=', _('is less than or equal to')),
        ('>=', _('is greater than or equal to')),
    ))

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()

        self.la = la = QLabel(self.MSG)
        la.setWordWrap(True)
        l.addWidget(la)
        l.addLayout(h)
        english_sentence = '{preamble} {property} {match_type} {query}'
        sentence = _('{preamble} {property} {match_type} {query}')
        if set(sentence.split()) != set(english_sentence.split()):
            sentence = english_sentence
        parts = sentence.split()
        for clause in parts:
            if clause == '{preamble}':
                self.preamble = w = QLabel(_('If the &property:'))
            elif clause == '{property}':
                self.property = w = QLineEdit(self)
                w.setToolTip(_('The name of a CSS property, for example: font-size\n'
                               'Do not use shorthand properties, they will not work.\n'
                               'For instance use margin-top, not margin.'))
            elif clause == '{match_type}':
                self.match_type = w = QComboBox(self)
                for action, text in self.MATCH_TYPE_MAP.iteritems():
                    w.addItem(text, action)
            elif clause == '{query}':
                self.query = w = QLineEdit(self)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))

        self.h2 = h = QHBoxLayout()
        l.addLayout(h)
        english_sentence = '{action} {action_data}'
        sentence = _('{action} {action_data}')
        if set(sentence.split()) != set(english_sentence.split()):
            sentence = english_sentence
        parts = sentence.split()
        for clause in parts:
            if clause == '{action}':
                self.action = w = QComboBox(self)
                for action, text in self.ACTION_MAP.iteritems():
                    w.addItem(text, action)
            elif clause == '{action_data}':
                self.action_data = w = QLineEdit(self)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))

        self.update_state()

    def sizeHint(self):
        a = QWidget.sizeHint(self)
        a.setHeight(a.height() + 75)
        a.setWidth(a.width() + 100)
        return a

    def update_state(self):
        r = self.rule
        self.action_data.setVisible(r['action'] != 'remove')
        tt = _('The CSS property value')
        mt = r['match_type']
        self.query.setVisible(mt != '*')
        if 'matches' in mt:
            tt = _('A regular expression')
        elif mt in '< > <= >='.split():
            tt = _('Either a CSS length, such as 10pt or a unit less number. If a unitless'
                   ' number is used it will be compared with the CSS value using whatever unit'
                   ' the value has. Note that comparison automatically converts units, except'
                   ' for relative units like percentage or em, for which comparison fails'
                   ' if the units are different.')
        self.query.setToolTip(tt)
        tt = ''
        ac = r['action']
        if ac == 'append':
            tt = _('CSS properties to add to the rule that contains the matching style. You'
                   ' can specify more than one property, separated by semi-colons, for example:'
                   ' color:red; font-weight: bold')
        elif ac in '+=*/':
            tt = _('A number')
        self.action_data.setToolTip(tt)

    @property
    def rule(self):
        return {
            'property':self.property.text().strip().lower(),
            'match_type': self.match_type.currentData(),
            'query': self.query.text().strip(),
            'action': self.action.currentData(),
            'action_data': self.action_data.text().strip(),
        }

    @rule.setter
    def rule(self, rule):
        def sc(name):
            c = getattr(self, name)
            idx = c.findData(unicode(rule.get(name, '')))
            if idx < 0:
                idx = 0
            c.setCurrentIndex(idx)
        sc('action'), sc('match_type')
        self.query.setText(unicode(rule.get('query', '')).strip())
        self.action_data.setText(unicode(rule.get('action_data', '')).strip())

    def validate(self):
        rule = self.rule
        mt = rule['match_type']
        if not rule['property']:
            error_dialog(self, _('Property required'), _(
                'You must specify a CSS property to match'), show=True)
            return False
        if rule['property'] in SHORTHAND_DEFAULTS:
            error_dialog(self, _('Shorthand property not allowed'), _(
                '{0} is a shorthand property. Use the full form of the property,'
                ' for example, instead of font, use font-family, instead of margin, use margin-top, etc.'), show=True)
            return False
        if not rule['query'] and mt != '*':
            error_dialog(self, _('Query required'), _(
                'You must specify a value for the CSS property to match'), show=True)
            return False
        if 'matches' in mt:
            try:
                compile_pat(rule['query'])
            except Exception:
                error_dialog(self, _('Query invalid'), _(
                    '%s is not a valid regular expression') % rule['query'], show=True)
                return False
        elif mt in '< > <= >= =='.split():
            try:
                num = parse_css_length_or_number(rule['query'])[0]
                if num is None:
                    raise Exception('not a number')
            except Exception:
                error_dialog(self, _('Query invalid'), _(
                    '%s is not a valid length or number') % rule['query'], show=True)
                return False
        ac, ad = rule['action'], rule['action_data']
        if not ad and ac != 'remove':
            msg = _('You must specify a number')
            if ac == 'append':
                msg = _('You must specify at least one CSS property to add')
            elif ac == 'change':
                msg = _('You must specify a value to change the property to')
            error_dialog(self, _('No data'), msg, show=True)
            return False
        if ac in '+-*/':
            try:
                float(ad)
            except Exception:
                error_dialog(self, _('Invalid number'), _('%s is not a number') % ad, show=True)
                return False
        return True
# }}}

class RuleEditDialog(RuleEditDialogBase):  # {{{

    PREFS_NAME = 'edit-css-transform-rule'
    DIALOG_TITLE = _('Edit rule')
    RuleEditClass = RuleEdit
# }}}

class RuleItem(QListWidgetItem):  # {{{

    @staticmethod
    def text_from_rule(rule, parent):
        query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
        text = _(
            'If the property <i>{property}</i> <b>{match_type}</b> <b>{query}</b><br>{action}').format(
                property=rule['property'], action=RuleEdit.ACTION_MAP[rule['action']],
                match_type=RuleEdit.MATCH_TYPE_MAP[rule['match_type']], query=query)
        if rule['action_data']:
            ad = elided_text(rule['action_data'], font=parent.font(), width=200, pos='right')
            text += ' <code>%s</code>' % ad
        return text
# }}}

class Rules(RulesBase):

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog

    MSG = _('You can specify rules to transform styles here. Click the "Add Rule" button'
            ' below to get started.')
