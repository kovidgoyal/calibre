#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QComboBox, QFrame, QHBoxLayout, QIcon, QLabel, QLineEdit, QPushButton,
    QScrollArea, Qt, QToolButton, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import prepare_string_for_xml
from calibre.ebooks.html_transform_rules import (
    ACTION_MAP, MATCH_TYPE_MAP, export_rules, import_rules, transform_html,
    validate_rule
)
from calibre.gui2 import elided_text, error_dialog
from calibre.gui2.convert.xpath_wizard import XPathEdit
from calibre.gui2.css_transform_rules import (
    RulesWidget as RulesWidgetBase, Tester as TesterBase
)
from calibre.gui2.tag_mapper import (
    RuleEditDialog as RuleEditDialogBase, RuleItem as RuleItemBase,
    Rules as RulesBase, RulesDialog as RulesDialogBase
)

# Classes for rule edit widget {{{


class TagAction(QWidget):

    remove_action = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)

        english_sentence = '{action_type} {action_data}'
        sentence = _('{action_type} {action_data}')
        if set(sentence.split()) != set(english_sentence.split()):
            sentence = english_sentence
        parts = sentence.split()
        for clause in parts:
            if clause == '{action_data}':
                self.action_data = w = QLineEdit(self)
                w.setClearButtonEnabled(True)
            elif clause == '{action_type}':
                self.action_type = w = QComboBox(self)
                for action, ac in ACTION_MAP.items():
                    w.addItem(ac.short_text, action)
                w.currentIndexChanged.connect(self.update_state)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))
        self.h2 = h = QHBoxLayout()
        l.addLayout(h)

        self.remove_button = b = QToolButton(self)
        b.setToolTip(_('Remove this action')), b.setIcon(QIcon.ic('minus.png'))
        b.clicked.connect(self.request_remove)
        h.addWidget(b)
        self.action_desc = la = QLabel('')
        la.setWordWrap(True)
        la.setTextFormat(Qt.TextFormat.RichText)
        h.addWidget(la)
        self.sep = sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        l.addWidget(sep)
        self.update_state()

    def request_remove(self):
        self.remove_action.emit(self)

    @property
    def as_dict(self):
        return {'type': self.action_type.currentData(), 'data': self.action_data.text()}

    @as_dict.setter
    def as_dict(self, val):
        self.action_data.setText(val.get('data') or '')
        at = val.get('type')
        if at:
            idx = self.action_type.findData(at)
            if idx > -1:
                self.action_type.setCurrentIndex(idx)

    def update_state(self):
        val = self.as_dict
        ac = ACTION_MAP[val['type']]
        self.action_desc.setText(ac.long_text)
        if ac.placeholder:
            self.action_data.setVisible(True)
            self.action_data.setPlaceholderText(ac.placeholder)
        else:
            self.action_data.setVisible(False)


class ActionsContainer(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.w = w = QWidget()
        self.setWidget(w)
        w.l = QVBoxLayout(w)
        w.l.addStretch(1)
        self.all_actions = []
        self.new_action()

    def new_action(self):
        a = TagAction(self)
        self.all_actions.append(a)
        l = self.w.l
        a.remove_action.connect(self.remove_action)
        l.insertWidget(l.count() - 1, a)
        a.action_type.setFocus(Qt.FocusReason.OtherFocusReason)
        return a

    def remove_action(self, ac):
        if ac in self.all_actions:
            self.w.l.removeWidget(ac)
            del self.all_actions[self.all_actions.index(ac)]
            ac.deleteLater()

    def sizeHint(self):
        ans = super().sizeHint()
        ans.setHeight(ans.height() + 200)
        return ans

    @property
    def as_list(self):
        return [t.as_dict for t in self.all_actions]

    @as_list.setter
    def as_list(self, val):
        for ac in tuple(self.all_actions):
            self.remove_action(ac)
        for entry in val:
            self.new_action().as_dict = entry


class GenericEdit(QLineEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setClearButtonEnabled(True)

    @property
    def value(self):
        return self.text()

    @value.setter
    def value(self, val):
        self.setText(str(val))


class CSSEdit(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.edit = le = GenericEdit(self)
        l.addWidget(le)
        l.addSpacing(5)
        self.la = la = QLabel(_('<a href="{}">CSS selector help</a>').format('https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Selectors'))
        la.setOpenExternalLinks(True)
        l.addWidget(la)
        self.setPlaceholderText = self.edit.setPlaceholderText

    @property
    def value(self):
        return self.edit.value

    @value.setter
    def value(self, val):
        self.edit.value = val
# }}}


class RuleEdit(QWidget):  # {{{

    MSG = _('Create the rule to transform HTML tags below')

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()

        self.la = la = QLabel(self.MSG)
        la.setWordWrap(True)
        l.addWidget(la)
        l.addLayout(h)
        english_sentence = '{preamble} {match_type}'
        sentence = _('{preamble} {match_type}')
        if set(sentence.split()) != set(english_sentence.split()):
            sentence = english_sentence
        parts = sentence.split()
        for clause in parts:
            if clause == '{preamble}':
                self.preamble = w = QLabel(_('If the tag'))
            elif clause == '{match_type}':
                self.match_type = w = QComboBox(self)
                for action, m in MATCH_TYPE_MAP.items():
                    w.addItem(m.text, action)
                w.currentIndexChanged.connect(self.update_state)
            h.addWidget(w)
            if clause is not parts[-1]:
                h.addWidget(QLabel('\xa0'))
        h.addStretch(1)
        self.generic_query = gq = GenericEdit(self)
        self.css_query = cq = CSSEdit(self)
        self.xpath_query = xq = XPathEdit(self, object_name='html_transform_rules_xpath', show_msg=False)
        l.addWidget(gq), l.addWidget(cq), l.addWidget(xq)

        self.thenl = QLabel(_('Then:'))
        l.addWidget(self.thenl)
        self.actions = a = ActionsContainer(self)
        l.addWidget(a)
        self.add_button = b = QPushButton(QIcon.ic('plus.png'), _('Add another action'))
        b.clicked.connect(self.actions.new_action)
        l.addWidget(b)
        self.update_state()

    def sizeHint(self):
        a = QWidget.sizeHint(self)
        a.setHeight(a.height() + 375)
        a.setWidth(a.width() + 125)
        return a

    @property
    def current_query_widget(self):
        return {'css': self.css_query, 'xpath': self.xpath_query}.get(self.match_type.currentData(), self.generic_query)

    def update_state(self):
        r = self.rule
        mt = r['match_type']
        self.generic_query.setVisible(False), self.css_query.setVisible(False), self.xpath_query.setVisible(False)
        self.current_query_widget.setVisible(True)
        self.current_query_widget.setPlaceholderText(MATCH_TYPE_MAP[mt].placeholder)

    @property
    def rule(self):
        try:
            return {
                'match_type': self.match_type.currentData(),
                'query': self.current_query_widget.value,
                'actions': self.actions.as_list,
            }
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    @rule.setter
    def rule(self, rule):
        def sc(name):
            c = getattr(self, name)
            c.setCurrentIndex(max(0, c.findData(str(rule.get(name, '')))))
        sc('match_type')
        self.current_query_widget.value = str(rule.get('query', '')).strip()
        self.actions.as_list = rule.get('actions') or []
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

    PREFS_NAME = 'edit-html-transform-rule'
    DIALOG_TITLE = _('Edit rule')
    RuleEditClass = RuleEdit
# }}}


class RuleItem(RuleItemBase):  # {{{

    @staticmethod
    def text_from_rule(rule, parent):
        try:
            query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
            text = _('If the tag <b>{match_type}</b> <b>{query}</b>').format(
                match_type=MATCH_TYPE_MAP[rule['match_type']].text, query=prepare_string_for_xml(query))
            for action in rule['actions']:
                text += '<br>' + ACTION_MAP[action['type']].short_text
                if action.get('data'):
                    ad = elided_text(action['data'], font=parent.font(), width=200, pos='right')
                    text += f' <code>{prepare_string_for_xml(ad)}</code>'
        except Exception:
            import traceback
            traceback.print_exc()
            text = _('This rule is invalid, please remove it')
        return text
# }}}


class Rules(RulesBase):  # {{{

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog
    ACTION_KEY = 'actions'
    MSG = _('You can specify rules to transform HTML here. Click the "Add rule" button'
            ' below to get started.')
# }}}


class Tester(TesterBase):  # {{{

    DIALOG_TITLE = _('Test HTML transform rules')
    PREFS_NAME = 'test-html-transform-rules'
    LABEL = _('Enter an HTML document below and click the "Test" button')
    SYNTAX = 'html'
    RESULTS = '<!-- %s -->\n\n' % _('Resulting HTML')

    def compile_rules(self, rules):
        return rules

    def do_test(self):
        changed, html = transform_html('\n' + self.value + '\n', self.rules)
        self.set_result(html)
# }}}


class RulesDialog(RulesDialogBase):  # {{{

    DIALOG_TITLE = _('Edit HTML transform rules')
    PREFS_NAME = 'edit-html-transform-rules'
    PREFS_OBJECT_NAME = 'html-transform-rules'
    RulesClass = Rules
    TesterClass = Tester

    def extra_bottom_widget(self):
        self.scope_cb = cb = QComboBox()
        cb.addItem(_('Current HTML file'), 'current')
        cb.addItem(_('All HTML files'), 'all')
        cb.addItem(_('Open HTML files'), 'open')
        cb.addItem(_('Selected HTML files'), 'selected')
        return cb

    @property
    def transform_scope(self):
        return self.scope_cb.currentData()

    @transform_scope.setter
    def transform_scope(self, val):
        idx = self.scope_cb.findData(val)
        self.scope_cb.setCurrentIndex(max(0, idx))

# }}}


class HtmlRulesWidget(RulesWidgetBase):  # {{{
    PREFS_NAME = 'html-transform-rules'
    INITIAL_FILE_NAME = 'html-rules.txt'
    DIR_SAVE_NAME = 'export-html-transform-rules'
    export_func = export_rules
    import_func = import_rules
    TesterClass = Tester
    RulesClass = Rules
# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = RulesDialog()
    d.rules = [
        {'match_type':'xpath', 'query':'//h:h2', 'actions':[{'type': 'remove'}]},
    ]
    d.exec()
    from pprint import pprint
    pprint(d.rules)
    del d, app
