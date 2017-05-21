#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from collections import OrderedDict
from functools import partial
import textwrap

from PyQt5.Qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QIcon,
    QSize, QComboBox, QLineEdit, QListWidgetItem, QStyledItemDelegate,
    QStaticText, Qt, QStyle, QToolButton, QInputDialog, QMenu, pyqtSignal
)

from calibre.ebooks.metadata.tag_mapper import map_tags, compile_pat
from calibre.gui2 import error_dialog, elided_text, Application, question_dialog
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets2 import Dialog
from calibre.utils.config import JSONConfig
from calibre.utils.localization import localize_user_manual_link

tag_maps = JSONConfig('tag-map-rules')


def intelligent_strip(action, val):
    ans = val.strip()
    if not ans and action == 'split':
        ans = ' '
    return ans


class QueryEdit(QLineEdit):

    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        self.parent().specialise_context_menu(menu)
        menu.exec_(ev.globalPos())


class RuleEdit(QWidget):

    ACTION_MAP = OrderedDict((
                ('remove', _('Remove')),
                ('replace', _('Replace')),
                ('keep', _('Keep')),
                ('capitalize', _('Capitalize')),
                ('lower', _('Lower-case')),
                ('upper', _('Upper-case')),
                ('split', _('Split')),
    ))

    MATCH_TYPE_MAP = OrderedDict((
                ('one_of', _('is one of')),
                ('not_one_of', _('is not one of')),
                ('matches', _('matches pattern')),
                ('not_matches', _('does not match pattern')),
                ('has', _('contains')),
    ))

    MSG = _('Create the rule below, the rule can be used to remove or replace tags')
    SUBJECT = _('the tag, if it')
    VALUE_ERROR = _('You must provide a value for the tag to match')
    REPLACE_TEXT = _('with the tag:')
    SPLIT_TEXT = _('on the character:')
    SPLIT_TOOLTIP = _(
        'The character on which to split tags. Note that technically you can specify'
        ' a sub-string, not just a single character. Then splitting will happen on the sub-string.')
    REPLACE_TOOLTIP = _(
        'What to replace the tag with. Note that if you use a pattern to match'
        ' tags, you can replace with parts of the matched pattern. See '
        ' the User Manual on how to use regular expressions for details.')
    REGEXP_HELP_TEXT = _('For help with regex pattern matching, see the <a href="%s">User Manual</a>')

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()

        self.la = la = QLabel(self.MSG)
        la.setWordWrap(True)
        l.addWidget(la)
        l.addLayout(h)
        self.action = a = QComboBox(self)
        h.addWidget(a)
        for action, text in self.ACTION_MAP.iteritems():
            a.addItem(text, action)
        a.currentIndexChanged.connect(self.update_state)
        self.la1 = la = QLabel('\xa0' + self.SUBJECT + '\xa0')
        h.addWidget(la)
        self.match_type = q = QComboBox(self)
        h.addWidget(q)
        for action, text in self.MATCH_TYPE_MAP.iteritems():
            q.addItem(text, action)
        q.currentIndexChanged.connect(self.update_state)
        self.la2 = la = QLabel(':\xa0')
        h.addWidget(la)
        self.query = q = QueryEdit(self)
        h.addWidget(q)
        self.tag_editor_button = b = QToolButton(self)
        b.setIcon(QIcon(I('chapters.png')))
        b.setToolTip(_('Edit the list of tags with the Tag editor'))
        h.addWidget(b), b.clicked.connect(self.edit_tags)
        b.setVisible(self.can_use_tag_editor)
        self.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.la3 = la = QLabel(self.REPLACE_TEXT + '\xa0')
        h.addWidget(la)
        self.replace = r = QLineEdit(self)
        h.addWidget(r)
        self.regex_help = la = QLabel('<p>' + self.REGEXP_HELP_TEXT % localize_user_manual_link(
        'https://manual.calibre-ebook.com/regexp.html'))
        la.setOpenExternalLinks(True)
        la.setWordWrap(True)
        l.addWidget(la)
        la.setVisible(False)
        l.addStretch(10)
        self.la3.setVisible(False), self.replace.setVisible(False)
        self.update_state()

    def sizeHint(self):
        a = QWidget.sizeHint(self)
        a.setHeight(a.height() + 75)
        a.setWidth(a.width() + 100)
        return a

    @property
    def can_use_tag_editor(self):
        return self.SUBJECT is RuleEdit.SUBJECT and 'matches' not in self.match_type.currentData() and get_gui() is not None

    def update_state(self):
        a = self.action.currentData()
        replace = a == 'replace'
        split = a == 'split'
        self.la3.setVisible(replace or split), self.replace.setVisible(replace or split)
        tt = _('A comma separated list of tags')
        m = self.match_type.currentData()
        is_match = 'matches' in m
        self.tag_editor_button.setVisible(self.can_use_tag_editor)
        if is_match:
            tt = _('A regular expression')
        elif m == 'has':
            tt = _('Tags that contain this string will match')
        self.regex_help.setVisible(is_match)
        self.la3.setText((self.SPLIT_TEXT if split else self.REPLACE_TEXT) + '\xa0')
        self.query.setToolTip(tt)
        self.replace.setToolTip(textwrap.fill(self.SPLIT_TOOLTIP if split else self.REPLACE_TOOLTIP))

    def specialise_context_menu(self, menu):
        if self.can_use_tag_editor:
            menu.addAction(_('Use the Tag editor to edit the list of tags'), self.edit_tags)

    def edit_tags(self):
        from calibre.gui2.dialogs.tag_editor import TagEditor
        d = TagEditor(self, get_gui().current_db, current_tags=filter(None, [x.strip() for x in self.query.text().split(',')]))
        if d.exec_() == d.Accepted:
            self.query.setText(', '.join(d.tags))

    @property
    def rule(self):
        ac = self.action.currentData()
        return {
            'action': ac,
            'match_type': self.match_type.currentData(),
            'query': intelligent_strip(ac, self.query.text()),
            'replace': intelligent_strip(ac, self.replace.text()),
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
        ac = self.action.currentData()
        self.query.setText(intelligent_strip(ac, unicode(rule.get('query', ''))))
        self.replace.setText(intelligent_strip(ac, unicode(rule.get('replace', ''))))

    def validate(self):
        rule = self.rule
        if not rule['query']:
            error_dialog(self, _('Query required'), self.VALUE_ERROR, show=True)
            return False
        if 'matches' in rule['match_type']:
            try:
                compile_pat(rule['query'])
            except Exception:
                error_dialog(self, _('Query invalid'), _(
                    '%s is not a valid regular expression') % rule['query'], show=True)
                return False
        return True


class RuleEditDialog(Dialog):

    PREFS_NAME = 'edit-tag-mapper-rule'
    DIALOG_TITLE = _('Edit rule')
    RuleEditClass = RuleEdit

    def __init__(self, parent=None):
        Dialog.__init__(self, self.DIALOG_TITLE, self.PREFS_NAME, parent=None)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.edit_widget = w = self.RuleEditClass(self)
        l.addWidget(w)
        l.addWidget(self.bb)

    def accept(self):
        if self.edit_widget.validate():
            Dialog.accept(self)


DATA_ROLE = Qt.UserRole
RENDER_ROLE = DATA_ROLE + 1


class RuleItem(QListWidgetItem):

    @staticmethod
    def text_from_rule(rule, parent):
        query = elided_text(rule['query'], font=parent.font(), width=200, pos='right')
        text = _(
            '<b>{action}</b> the tag, if it <i>{match_type}</i>: <b>{query}</b>').format(
                action=RuleEdit.ACTION_MAP[rule['action']], match_type=RuleEdit.MATCH_TYPE_MAP[rule['match_type']], query=query)
        if rule['action'] == 'replace':
            text += '<br>' + _('with the tag:') + ' <b>%s</b>' % rule['replace']
        if rule['action'] == 'split':
            text += '<br>' + _('on the character:') + ' <b>%s</b>' % rule['replace']
        return text

    def __init__(self, rule, parent):
        QListWidgetItem.__init__(self, '', parent)
        st = self.text_from_rule(rule, parent)
        self.setData(RENDER_ROLE, st)
        self.setData(DATA_ROLE, rule)


class Delegate(QStyledItemDelegate):

    MARGIN = 16

    def sizeHint(self, option, index):
        st = QStaticText(index.data(RENDER_ROLE))
        st.prepare(font=self.parent().font())
        width = max(option.rect.width(), self.parent().width() - 50)
        if width and width != st.textWidth():
            st.setTextWidth(width)
        br = st.size()
        return QSize(br.width(), br.height() + self.MARGIN)

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        pal = option.palette
        color = pal.color(pal.HighlightedText if option.state & QStyle.State_Selected else pal.Text).name()
        text = '<div style="color:%s">%s</div>' % (color, index.data(RENDER_ROLE))
        st = QStaticText(text)
        st.setTextWidth(option.rect.width())
        painter.drawStaticText(option.rect.left() + self.MARGIN // 2, option.rect.top() + self.MARGIN // 2, st)


class Rules(QWidget):

    RuleItemClass = RuleItem
    RuleEditDialogClass = RuleEditDialog
    changed = pyqtSignal()

    MSG = _('You can specify rules to filter/transform tags here. Click the "Add rule" button'
            ' below to get started. The rules will be processed in order for every tag until either a'
            ' "remove" or a "keep" rule matches.')

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.msg_label = la = QLabel(
            '<p>' + self.MSG + '<p>' + _(
            'You can <b>change an existing rule</b> by double clicking it')
        )
        la.setWordWrap(True)
        l.addWidget(la)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.add_button = b = QPushButton(QIcon(I('plus.png')), _('&Add rule'), self)
        b.clicked.connect(self.add_rule)
        h.addWidget(b)
        self.remove_button = b = QPushButton(QIcon(I('minus.png')), _('&Remove rule(s)'), self)
        b.clicked.connect(self.remove_rules)
        h.addWidget(b)
        self.h3 = h = QHBoxLayout()
        l.addLayout(h)
        self.rule_list = r = QListWidget(self)
        self.delegate = Delegate(self)
        r.setSelectionMode(r.ExtendedSelection)
        r.setItemDelegate(self.delegate)
        r.doubleClicked.connect(self.edit_rule)
        h.addWidget(r)
        r.setDragEnabled(True)
        r.viewport().setAcceptDrops(True)
        r.setDropIndicatorShown(True)
        r.setDragDropMode(r.InternalMove)
        r.setDefaultDropAction(Qt.MoveAction)
        self.l2 = l = QVBoxLayout()
        h.addLayout(l)
        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png'))), b.setToolTip(_('Move current rule up'))
        b.clicked.connect(self.move_up)
        l.addWidget(b)
        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png'))), b.setToolTip(_('Move current rule down'))
        b.clicked.connect(self.move_down)
        l.addStretch(10), l.addWidget(b)

    def sizeHint(self):
        return QSize(800, 600)

    def add_rule(self):
        d = self.RuleEditDialogClass(self)
        if d.exec_() == d.Accepted:
            i = self.RuleItemClass(d.edit_widget.rule, self.rule_list)
            self.rule_list.scrollToItem(i)
            self.changed.emit()

    def edit_rule(self):
        i = self.rule_list.currentItem()
        if i is not None:
            d = self.RuleEditDialogClass(self)
            d.edit_widget.rule = i.data(Qt.UserRole)
            if d.exec_() == d.Accepted:
                rule = d.edit_widget.rule
                i.setData(DATA_ROLE, rule)
                i.setData(RENDER_ROLE, self.RuleItemClass.text_from_rule(rule, self.rule_list))
                self.changed.emit()

    def remove_rules(self):
        changed = False
        for item in self.rule_list.selectedItems():
            self.rule_list.takeItem(self.rule_list.row(item))
            changed = True
        if changed:
            self.changed.emit()

    def move_up(self):
        i = self.rule_list.currentItem()
        if i is not None:
            row = self.rule_list.row(i)
            if row > 0:
                self.rule_list.takeItem(row)
                self.rule_list.insertItem(row - 1, i)
                self.rule_list.setCurrentItem(i)
                self.changed.emit()

    def move_down(self):
        i = self.rule_list.currentItem()
        if i is not None:
            row = self.rule_list.row(i)
            if row < self.rule_list.count() - 1:
                self.rule_list.takeItem(row)
                self.rule_list.insertItem(row + 1, i)
                self.rule_list.setCurrentItem(i)
                self.changed.emit()

    @property
    def rules(self):
        ans = []
        for r in xrange(self.rule_list.count()):
            ans.append(self.rule_list.item(r).data(DATA_ROLE))
        return ans

    @rules.setter
    def rules(self, rules):
        self.rule_list.clear()
        for rule in rules:
            if 'action' in rule and 'match_type' in rule and 'query' in rule:
                self.RuleItemClass(rule, self.rule_list)


class Tester(Dialog):

    DIALOG_TITLE = _('Test tag mapper rules')
    PREFS_NAME = 'test-tag-mapper-rules'
    LABEL = _('Enter a comma separated list of &tags to test:')
    PLACEHOLDER = _('Enter tags and click the "Test" button')
    EMPTY_RESULT = '<p>&nbsp;<br>&nbsp;</p>'

    def __init__(self, rules, parent=None):
        self.rules = rules
        Dialog.__init__(self, self.DIALOG_TITLE, self.PREFS_NAME, parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.bb.setStandardButtons(self.bb.Close)
        self.la = la = QLabel(self.LABEL)
        l.addWidget(la)
        self.tags = t = QLineEdit(self)
        la.setBuddy(t)
        t.setPlaceholderText(self.PLACEHOLDER)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(t)
        self.test_button = b = QPushButton(_('&Test'), self)
        b.clicked.connect(self.do_test)
        h.addWidget(b)
        self.result = la = QLabel(self)
        la.setWordWrap(True)
        la.setText(self.EMPTY_RESULT)
        l.addWidget(la)
        l.addWidget(self.bb)

    @property
    def value(self):
        return self.tags.text()

    def do_test(self):
        tags = [x.strip() for x in self.value.split(',')]
        tags = map_tags(tags, self.rules)
        self.result.setText(_('<b>Resulting tags:</b> %s') % ', '.join(tags))

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(ans.width() + 150)
        return ans


class SaveLoadMixin(object):

    def save_ruleset(self):
        if not self.rules:
            error_dialog(self, _('No rules'), _(
                'Cannot save as no rules have been created'), show=True)
            return
        text, ok = QInputDialog.getText(self, _('Save ruleset as'), _(
            'Enter a name for this ruleset:'), text=self.loaded_ruleset or '')
        if ok and text:
            if self.loaded_ruleset and text == self.loaded_ruleset:
                if not question_dialog(self, _('Are you sure?'), _(
                        'A ruleset with the name "%s" already exists, do you want to replace it?') % text):
                    return
                self.loaded_ruleset = text
            rules = self.rules
            if rules:
                self.PREFS_OBJECT[text] = self.rules
            elif text in self.PREFS_OBJECT:
                del self.PREFS_OBJECT[text]
            self.build_load_menu()

    def build_load_menu(self):
        self.load_menu.clear()
        if len(self.PREFS_OBJECT):
            for name, rules in self.PREFS_OBJECT.iteritems():
                self.load_menu.addAction(name).triggered.connect(partial(self.load_ruleset, name))
            self.load_menu.addSeparator()
            m = self.load_menu.addMenu(_('Delete saved rulesets'))
            for name, rules in self.PREFS_OBJECT.iteritems():
                m.addAction(name).triggered.connect(partial(self.delete_ruleset, name))
        else:
            self.load_menu.addAction(_('No saved rulesets available'))

    def load_ruleset(self, name):
        self.rules = self.PREFS_OBJECT[name]
        self.loaded_ruleset = name

    def delete_ruleset(self, name):
        del self.PREFS_OBJECT[name]
        self.build_load_menu()


class RulesDialog(Dialog, SaveLoadMixin):

    DIALOG_TITLE = _('Edit tag mapper rules')
    PREFS_NAME = 'edit-tag-mapper-rules'
    RulesClass = Rules
    TesterClass = Tester
    PREFS_OBJECT = tag_maps

    def __init__(self, parent=None):
        self.loaded_ruleset = None
        Dialog.__init__(self, self.DIALOG_TITLE, self.PREFS_NAME, parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.edit_widget = w = self.RulesClass(self)
        l.addWidget(w)
        l.addWidget(self.bb)
        self.save_button = b = self.bb.addButton(_('&Save'), self.bb.ActionRole)
        b.setToolTip(_('Save this ruleset for later re-use'))
        b.clicked.connect(self.save_ruleset)
        self.load_button = b = self.bb.addButton(_('&Load'), self.bb.ActionRole)
        b.setToolTip(_('Load a previously saved ruleset'))
        self.load_menu = QMenu(self)
        b.setMenu(self.load_menu)
        self.build_load_menu()
        self.test_button = b = self.bb.addButton(_('&Test rules'), self.bb.ActionRole)
        b.clicked.connect(self.test_rules)

    @property
    def rules(self):
        return self.edit_widget.rules

    @rules.setter
    def rules(self, rules):
        self.edit_widget.rules = rules

    def test_rules(self):
        self.TesterClass(self.rules, self).exec_()


if __name__ == '__main__':
    app = Application([])
    d = RulesDialog()
    d.rules = [
        {'action':'remove', 'query':'moose', 'match_type':'one_of', 'replace':''},
        {'action':'replace', 'query':'moose', 'match_type':'one_of', 'replace':'xxxx'},
        {'action':'split', 'query':'/', 'match_type':'has', 'replace':'/'},
    ]
    d.exec_()
    from pprint import pprint
    pprint(d.rules)
    del d, app
