#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QSize, pyqtSignal, QMenu
)

from calibre.ebooks.css_transform_rules import (
    validate_rule, safe_parser, compile_rules, transform_sheet, ACTION_MAP, MATCH_TYPE_MAP, export_rules, import_rules)
from calibre.gui2 import error_dialog, elided_text, choose_save_file, choose_files
from calibre.gui2.tag_mapper import (
    RuleEdit as RE, RuleEditDialog as RuleEditDialogBase, Rules as RulesBase,
    RulesDialog as RulesDialogBase, RuleItem as RuleItemBase, SaveLoadMixin)
from calibre.gui2.widgets2 import Dialog
from calibre.utils.config import JSONConfig
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import iteritems, unicode_type


class RuleEdit(QWidget):  # {{{

    MSG = _('Create the rule below, the rule can be used to transform style properties')

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
                for action, text in iteritems(MATCH_TYPE_MAP):
                    w.addItem(text, action)
                w.currentIndexChanged.connect(self.update_state)
            elif clause == '{query}':
                self.query = w = QLineEdit(self)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))
        self.preamble.setBuddy(self.property)

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
                for action, text in iteritems(ACTION_MAP):
                    w.addItem(text, action)
                w.currentIndexChanged.connect(self.update_state)
            elif clause == '{action_data}':
                self.action_data = w = QLineEdit(self)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))

        self.regex_help = la = QLabel('<p>' + RE.REGEXP_HELP_TEXT % localize_user_manual_link(
        'https://manual.calibre-ebook.com/regexp.html'))
        la.setOpenExternalLinks(True)
        la.setWordWrap(True)
        l.addWidget(la)
        l.addStretch(10)

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
            tt = _('Either a CSS length, such as 10pt or a unit less number. If a unit less'
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
        self.regex_help.setVisible('matches' in mt)

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
            idx = c.findData(unicode_type(rule.get(name, '')))
            if idx < 0:
                idx = 0
            c.setCurrentIndex(idx)
        sc('action'), sc('match_type')
        self.property.setText(unicode_type(rule.get('property', '')).strip())
        self.query.setText(unicode_type(rule.get('query', '')).strip())
        self.action_data.setText(unicode_type(rule.get('action_data', '')).strip())
        self.update_state()

    def validate(self):
        rule = self.rule
        title, msg = validate_rule(rule)
        if msg is not None and title is not None:
            error_dialog(self, title, msg, show=True)
            return False
        return True
# }}}


class RuleEditDialog(RuleEditDialogBase):  # {{{

    PREFS_NAME = 'edit-css-transform-rule'
    DIALOG_TITLE = _('Edit rule')
    RuleEditClass = RuleEdit
# }}}


class RuleItem(RuleItemBase):  # {{{

    @staticmethod
    def text_from_rule(rule, parent):
        try:
            query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
            text = _(
                'If the property <i>{property}</i> <b>{match_type}</b> <b>{query}</b><br>{action}').format(
                    property=rule['property'], action=ACTION_MAP[rule['action']],
                    match_type=MATCH_TYPE_MAP[rule['match_type']], query=query)
            if rule['action_data']:
                ad = elided_text(rule['action_data'], font=parent.font(), width=200, pos='right')
                text += ' <code>%s</code>' % ad
        except Exception:
            import traceback
            traceback.print_exc()
            text = _('This rule is invalid, please remove it')
        return text
# }}}


class Rules(RulesBase):  # {{{

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog

    MSG = _('You can specify rules to transform styles here. Click the "Add rule" button'
            ' below to get started.')
# }}}


class Tester(Dialog):  # {{{

    DIALOG_TITLE = _('Test style transform rules')
    PREFS_NAME = 'test-style-transform-rules'
    LABEL = _('Enter a CSS stylesheet below to test')

    def __init__(self, rules, parent=None):
        self.rules = compile_rules(rules)
        Dialog.__init__(self, self.DIALOG_TITLE, self.PREFS_NAME, parent=parent)

    def setup_ui(self):
        from calibre.gui2.tweak_book.editor.text import TextEdit
        self.l = l = QVBoxLayout(self)
        self.bb.setStandardButtons(self.bb.Close)
        self.la = la = QLabel(self.LABEL)
        l.addWidget(la)
        self.css = t = TextEdit(self)
        t.load_text('/* %s */\n' % _('Enter CSS rules below and click the "Test" button'), 'css')
        la.setBuddy(t)
        c = t.textCursor()
        c.movePosition(c.End)
        t.setTextCursor(c)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(t)
        self.test_button = b = QPushButton(_('&Test'), self)
        b.clicked.connect(self.do_test)
        h.addWidget(b)
        self.result = la = TextEdit(self)
        la.setReadOnly(True)
        l.addWidget(la)
        l.addWidget(self.bb)

    @property
    def value(self):
        return self.css.toPlainText()

    def do_test(self):
        decl = safe_parser().parseString(self.value)
        transform_sheet(self.rules, decl)
        css = decl.cssText
        if isinstance(css, bytes):
            css = css.decode('utf-8')
        self.result.load_text('/* %s */\n\n%s' % (_('Resulting stylesheet'), css), 'css')

    def sizeHint(self):
        return QSize(800, 600)
# }}}


class RulesDialog(RulesDialogBase):  # {{{

    DIALOG_TITLE = _('Edit style transform rules')
    PREFS_NAME = 'edit-style-transform-rules'
    RulesClass = Rules
    TesterClass = Tester

    def __init__(self, *args, **kw):
        # This has to be loaded on instantiation as it can be shared by
        # multiple processes
        self.PREFS_OBJECT = JSONConfig('style-transform-rules')
        RulesDialogBase.__init__(self, *args, **kw)
# }}}


class RulesWidget(QWidget, SaveLoadMixin):  # {{{

    changed = pyqtSignal()

    def __init__(self, parent=None):
        self.loaded_ruleset = None
        QWidget.__init__(self, parent)
        self.PREFS_OBJECT = JSONConfig('style-transform-rules')
        l = QVBoxLayout(self)
        self.rules_widget = w = Rules(self)
        w.changed.connect(self.changed.emit)
        l.addWidget(w)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.export_button = b = QPushButton(_('E&xport'), self)
        b.setToolTip(_('Export these rules to a file'))
        b.clicked.connect(self.export_rules)
        h.addWidget(b)
        self.import_button = b = QPushButton(_('&Import'), self)
        b.setToolTip(_('Import previously exported rules'))
        b.clicked.connect(self.import_rules)
        h.addWidget(b)
        self.test_button = b = QPushButton(_('&Test rules'), self)
        b.clicked.connect(self.test_rules)
        h.addWidget(b)
        h.addStretch(10)
        self.save_button = b = QPushButton(_('&Save'), self)
        b.setToolTip(_('Save this ruleset for later re-use'))
        b.clicked.connect(self.save_ruleset)
        h.addWidget(b)
        self.export_button = b = QPushButton(_('&Load'), self)
        self.load_menu = QMenu(self)
        b.setMenu(self.load_menu)
        b.setToolTip(_('Load a previously saved ruleset'))
        b.clicked.connect(self.load_ruleset)
        h.addWidget(b)
        self.build_load_menu()

    def export_rules(self):
        rules = self.rules_widget.rules
        if not rules:
            return error_dialog(self, _('No rules'), _(
                'There are no rules to export'), show=True)
        path = choose_save_file(self, 'export-style-transform-rules', _('Choose file for exported rules'), initial_filename='rules.txt')
        if path:
            raw = export_rules(rules)
            with open(path, 'wb') as f:
                f.write(raw)

    def import_rules(self):
        paths = choose_files(self, 'export-style-transform-rules', _('Choose file to import rules from'), select_only_single_file=True)
        if paths:
            with open(paths[0], 'rb') as f:
                rules = import_rules(f.read())
            self.rules_widget.rules = list(rules) + list(self.rules_widget.rules)
            self.changed.emit()

    def load_ruleset(self, name):
        SaveLoadMixin.load_ruleset(self, name)
        self.changed.emit()

    def test_rules(self):
        Tester(self.rules_widget.rules, self).exec_()

    @property
    def rules(self):
        return self.rules_widget.rules

    @rules.setter
    def rules(self, val):
        try:
            self.rules_widget.rules = val or []
        except Exception:
            import traceback
            traceback.print_exc()
            self.rules_widget.rules = []
# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = RulesDialog()
    d.rules = [
        {'property':'color', 'match_type':'*', 'query':'', 'action':'change', 'action_data':'green'},
    ]
    d.exec_()
    from pprint import pprint
    pprint(d.rules)
    del d, app
