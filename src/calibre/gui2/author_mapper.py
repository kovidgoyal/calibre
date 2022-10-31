#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


from collections import OrderedDict

from calibre.ebooks.metadata import authors_to_string, string_to_authors
from calibre.ebooks.metadata.author_mapper import compile_rules, map_authors
from calibre.gui2 import Application, elided_text
from calibre.gui2.tag_mapper import (
    RuleEdit as RuleEditBase, RuleEditDialog as RuleEditDialogBase,
    RuleItem as RuleItemBase, Rules as RulesBase, RulesDialog as RulesDialogBase,
    Tester as TesterBase
)
from calibre.utils.config import JSONConfig

author_maps = JSONConfig('author-mapping-rules')


class RuleEdit(RuleEditBase):

    ACTION_MAP = OrderedDict((
        ('replace', _('Change')),
        ('capitalize', _('Capitalize')),
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

    MSG = _('Create the rule below, the rule can be used to add or ignore files')
    SUBJECT = _('the author, if the author name')
    VALUE_ERROR = _('You must provide a value for the author name to match')
    REPLACE_TEXT = _('with the name:')
    SINGLE_EDIT_FIELD_NAME = 'authors'

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

    PREFS_NAME = 'edit-author-mapping-rule'
    RuleEditClass = RuleEdit


class RuleItem(RuleItemBase):

    @staticmethod
    def text_from_rule(rule, parent):
        query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
        text = _(
            '<b>{action}</b> the author name, if it <i>{match_type}</i>: <b>{query}</b>').format(
                action=RuleEdit.ACTION_MAP[rule['action']], match_type=RuleEdit.MATCH_TYPE_MAP[rule['match_type']], query=query)
        if rule['action'] == 'replace':
            text += '<br>' + _('to the name') + ' <b>%s</b>' % rule['replace']
        return '<div style="white-space: nowrap">' + text + '</div>'


class Rules(RulesBase):

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog
    MSG = _('You can specify rules to manipulate author names here.'
            ' Click the "Add Rule" button'
            ' below to get started. The rules will be processed in order for every author.')


class Tester(TesterBase):

    DIALOG_TITLE = _('Test author mapping rules')
    PREFS_NAME = 'test-author-mapping-rules'
    LABEL = _('Enter an author name to test:')
    PLACEHOLDER = _('Enter author and click the "Test" button')
    EMPTY_RESULT = '<p>&nbsp;</p>'

    def do_test(self):
        authors = string_to_authors(self.value.strip())
        ans = map_authors(authors, compile_rules(self.rules))
        self.result.setText(authors_to_string(ans))


class RulesDialog(RulesDialogBase):

    DIALOG_TITLE = _('Edit author mapping rules')
    PREFS_NAME = 'edit-author-mapping-rules'
    RulesClass = Rules
    TesterClass = Tester
    PREFS_OBJECT = author_maps


if __name__ == '__main__':
    app = Application([])
    d = RulesDialog()
    d.rules = [
            {'action':'replace', 'query':'alice B & alice bob', 'match_type':'one_of', 'replace':'Alice Bob'},
    ]
    d.exec()
    from pprint import pprint
    pprint(d.rules)
    del d, app
