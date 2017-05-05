#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from collections import OrderedDict
from future_builtins import map

from calibre.db.adding import compile_glob, filter_filename, compile_rule
from calibre.gui2 import elided_text, Application, error_dialog
from calibre.gui2.tag_mapper import (
    RuleEdit as RuleEditBase, RuleEditDialog as
    RuleEditDialogBase, RuleItem as RuleItemBase, Rules as RulesBase,
    Tester as TesterBase, RulesDialog as RulesDialogBase
)
from calibre.utils.config import JSONConfig

add_filters = JSONConfig('add-filter-rules')


class RuleEdit(RuleEditBase):

    ACTION_MAP = OrderedDict((
        ('ignore', _('Ignore')),
        ('add', _('Add')),
    ))

    MATCH_TYPE_MAP = OrderedDict((
        ('startswith', _('starts with')),
        ('not_startswith', _('does not start with')),
        ('endswith', _('ends with')),
        ('not_endswith', _('does not end with')),
        ('glob', _('matches glob pattern')),
        ('not_glob', _('does not match glob pattern')),
        ('matches', _('matches regex pattern')),
        ('not_matches', _('does not match regex pattern')),
    ))

    MSG = _('Create the rule below, the rule can be used to add or ignore files')
    SUBJECT = _('the file, if the filename')
    VALUE_ERROR = _('You must provide a value for the filename to match')

    def update_state(self):
        tt = _('A comma separated list of tags')
        q = self.match_type.currentData()
        if 'with' in q:
            tt = _('Matching is case-insensitive')
        elif 'glob' in q:
            tt = _('A case-insensitive filename pattern, for example: {0} or {1}').format('*.pdf', 'number-?.epub')
        else:
            tt = _('A regular expression')
        self.regex_help.setVisible('matches' in q)
        self.query.setToolTip(tt)

    @property
    def rule(self):
        return {
            'action': self.action.currentData(),
            'match_type': self.match_type.currentData(),
            'query': self.query.text().strip(),
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

    def validate(self):
        ans = super(RuleEdit, self).validate()
        if ans:
            rule = self.rule
            if 'glob' in rule['match_type']:
                try:
                    compile_glob(rule['query'])
                except Exception:
                    error_dialog(self, _('Query invalid'), _(
                        '%s is not a valid glob expression') % rule['query'], show=True)
                    return False
        return ans


class RuleEditDialog(RuleEditDialogBase):

    PREFS_NAME = 'edit-add-filter-rule'
    RuleEditClass = RuleEdit


class RuleItem(RuleItemBase):

    @staticmethod
    def text_from_rule(rule, parent):
        query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
        text = _(
            '<b>{action}</b> the file, if the filename <i>{match_type}</i>: <b>{query}</b>').format(
                action=RuleEdit.ACTION_MAP[rule['action']], match_type=RuleEdit.MATCH_TYPE_MAP[rule['match_type']], query=query)
        return text


class Rules(RulesBase):

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog
    MSG = _('You can specify rules to add/ignore files here. They will be used'
            ' when recursively adding files from directories/archives and also'
            ' when auto-adding. Click the "Add Rule" button'
            ' below to get started. The rules will be processed in order for every file until either an'
            ' "add" or an "ignore" rule matches. If no rules match, the file will be added only'
            ' if its file extension is of a known e-book type.')


class Tester(TesterBase):

    DIALOG_TITLE = _('Test filename filter rules')
    PREFS_NAME = 'test-file-filter-rules'
    LABEL = _('Enter a filename to test:')
    PLACEHOLDER = _('Enter filename and click the "Test" button')
    EMPTY_RESULT = '<p>&nbsp;</p>'

    def do_test(self):
        filename = self.value.strip()
        allowed = filter_filename(map(compile_rule, self.rules), filename)
        if allowed is None:
            self.result.setText(_('The filename %s did not match any rules') % filename)
        else:
            self.result.setText(_('The filename {0} will be {1}').format(filename, _('added' if allowed else 'ignored')))


class RulesDialog(RulesDialogBase):

    DIALOG_TITLE = _('Edit file filter rules')
    PREFS_NAME = 'edit-file-filter-rules'
    RulesClass = Rules
    TesterClass = Tester
    PREFS_OBJECT = add_filters


if __name__ == '__main__':
    app = Application([])
    d = RulesDialog()
    d.rules = [
        {'action':'ignore', 'query':'ignore-me', 'match_type':'startswith'},
        {'action':'add', 'query':'*.moose', 'match_type':'glob'},
    ]
    d.exec_()
    from pprint import pprint
    pprint(d.rules)
    del d, app
