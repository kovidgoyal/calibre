#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


from collections import OrderedDict

from calibre.ebooks.metadata.tag_mapper import map_tags
from calibre.gui2 import Application, elided_text
from calibre.gui2.tag_mapper import RuleEdit as RuleEditBase
from calibre.gui2.tag_mapper import RuleEditDialog as RuleEditDialogBase
from calibre.gui2.tag_mapper import RuleItem as RuleItemBase
from calibre.gui2.tag_mapper import Rules as RulesBase
from calibre.gui2.tag_mapper import RulesDialog as RulesDialogBase
from calibre.gui2.tag_mapper import Tester as TesterBase
from calibre.utils.config import JSONConfig

series_maps = JSONConfig('series-mapping-rules')


class RuleEdit(RuleEditBase):

    ACTION_MAP = OrderedDict((
        ('replace', _('Change')),
        ('capitalize', _('Capitalize')),
        ('titlecase', _('Title-case')),
        ('lower', _('Lower-case')),
        ('upper', _('Upper-case')),
    ))

    MATCH_TYPE_MAP = OrderedDict((
        ('one_of', _('is one of')),
        ('not_one_of', _('is not one of')),
        ('has', _('contains')),
        ('matches', _('matches regex pattern')),
        ('not_matches', _('does not match regex pattern')),
    ))

    MSG = _('Create the rule below, the rule can be used to modify series')
    SUBJECT = _('the series, if the series name')
    VALUE_ERROR = _('You must provide a value for the series name to match')
    REPLACE_TEXT = _('with the name:')
    SINGLE_EDIT_FIELD_NAME = 'series'

    @property
    def can_use_tag_editor(self):
        return False

    def update_state(self):
        a = self.action.currentData()
        replace = a == 'replace'
        self.la3.setVisible(replace), self.replace.setVisible(replace)
        m = self.match_type.currentData()
        is_match = 'matches' in m
        self.regex_help.setVisible(is_match)

    @property
    def rule(self):
        return {
            'action': self.action.currentData(),
            'match_type': self.match_type.currentData(),
            'query': self.query.text().strip(),
            'replace': self.replace.text().strip(),
        }

    @rule.setter
    def rule(self, rule):
        def sc(name):
            c = getattr(self, name)
            idx = c.findData(str(rule.get(name, '')))
            if idx < 0:
                idx = 0
            c.setCurrentIndex(idx)
        sc('match_type'), sc('action')
        self.query.setText(str(rule.get('query', '')).strip())
        self.replace.setText(str(rule.get('replace', '')).strip())


class RuleEditDialog(RuleEditDialogBase):

    PREFS_NAME = 'edit-series-mapping-rule'
    RuleEditClass = RuleEdit


class RuleItem(RuleItemBase):

    @staticmethod
    def text_from_rule(rule, parent):
        query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
        text = _(
            '<b>{action}</b> the series name, if it <i>{match_type}</i>: <b>{query}</b>').format(
                action=RuleEdit.ACTION_MAP[rule['action']], match_type=RuleEdit.MATCH_TYPE_MAP[rule['match_type']], query=query)
        if rule['action'] == 'replace':
            text += '<br>' + _('to the name') + ' <b>%s</b>' % rule['replace']
        return '<div style="white-space: nowrap">' + text + '</div>'


class Rules(RulesBase):

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog
    MSG = _('You can specify rules to manipulate series names here.'
            ' Click the "Add Rule" button'
            ' below to get started. The rules will be processed in order for every series.')


class Tester(TesterBase):

    DIALOG_TITLE = _('Test series mapping rules')
    PREFS_NAME = 'test-series-mapping-rules'
    LABEL = _('Enter a series name to test:')
    PLACEHOLDER = _('Enter series and click the "Test" button')
    EMPTY_RESULT = '<p>&nbsp;</p>'

    def do_test(self):
        series = self.value.strip()
        ans = map_tags([series], self.rules)
        self.result.setText((ans or ('',))[0])


class RulesDialog(RulesDialogBase):

    DIALOG_TITLE = _('Edit series mapping rules')
    PREFS_NAME = 'edit-series-mapping-rules'
    RulesClass = Rules
    TesterClass = Tester
    PREFS_OBJECT = series_maps


if __name__ == '__main__':
    app = Application([])
    d = RulesDialog()
    d.rules = [
            {'action':'replace', 'query':'alice Bob', 'match_type':'one_of', 'replace':'Alice Bob'},
    ]
    d.exec()
    from pprint import pprint
    pprint(d.rules)
    del d, app
