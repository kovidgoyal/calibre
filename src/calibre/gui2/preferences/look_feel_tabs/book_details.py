#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from collections import defaultdict
from functools import partial

from qt.core import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QIcon,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.gui2 import config, default_author_link, error_dialog, gprefs
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import DisplayedFields, move_field_down, move_field_up
from calibre.gui2.preferences.look_feel_tabs.book_details_ui import Ui_Form
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import Dialog
from calibre.startup import connect_lambda
from calibre.utils.icu import sort_key
from calibre.utils.resources import set_data
from polyglot.builtins import iteritems


class IdLinksRuleEdit(Dialog):

    def __init__(self, key='', name='', template='', parent=None):
        title = _('Edit rule') if key else _('Create a new rule')
        Dialog.__init__(self, title=title, name='id-links-rule-editor', parent=parent)
        self.key.setText(key), self.nw.setText(name), self.template.setText(template or 'https://example.com/{id}')
        if self.size().height() < self.sizeHint().height():
            self.resize(self.sizeHint())

    @property
    def rule(self):
        return self.key.text().lower(), self.nw.text(), self.template.text()

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        l.addRow(QLabel(_(
            'The key of the identifier, for example, in isbn:XXX, the key is "isbn"')))
        self.key = k = QLineEdit(self)
        l.addRow(_('&Key:'), k)
        l.addRow(QLabel(_(
            'The name that will appear in the Book details panel')))
        self.nw = n = QLineEdit(self)
        l.addRow(_('&Name:'), n)
        la = QLabel(_(
            'The template used to create the link.'
            ' The placeholder {0} in the template will be replaced'
            ' with the actual identifier value. Use {1} to avoid the value'
            ' being quoted.').format('{id}', '{id_unquoted}'))
        la.setWordWrap(True)
        l.addRow(la)
        self.template = t = QLineEdit(self)
        l.addRow(_('&Template:'), t)
        t.selectAll()
        t.setFocus(Qt.FocusReason.OtherFocusReason)
        l.addWidget(self.bb)

    def accept(self):
        r = self.rule
        for i, which in enumerate([_('Key'), _('Name'), _('Template')]):
            if not r[i]:
                return error_dialog(self, _('Value needed'), _(
                    'The %s field cannot be empty') % which, show=True)
        Dialog.accept(self)


class IdLinksEditor(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, title=_('Create rules for identifiers'), name='id-links-rules-editor', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_(
            'Create rules to convert identifiers into links.'))
        la.setWordWrap(True)
        l.addWidget(la)
        items = []
        for k, lx in iteritems(msprefs['id_link_rules']):
            for n, t in lx:
                items.append((k, n, t))
        items.sort(key=lambda x: sort_key(x[1]))
        self.table = t = QTableWidget(len(items), 3, self)
        t.setHorizontalHeaderLabels([_('Key'), _('Name'), _('Template')])
        for r, (key, val, template) in enumerate(items):
            t.setItem(r, 0, QTableWidgetItem(key))
            t.setItem(r, 1, QTableWidgetItem(val))
            t.setItem(r, 2, QTableWidgetItem(template))
        l.addWidget(t)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.cb = b = QPushButton(QIcon.ic('plus.png'), _('&Add rule'), self)
        connect_lambda(b.clicked, self, lambda self: self.edit_rule())
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        self.rb = b = QPushButton(QIcon.ic('minus.png'), _('&Remove rule'), self)
        connect_lambda(b.clicked, self, lambda self: self.remove_rule())
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        self.eb = b = QPushButton(QIcon.ic('modified.png'), _('&Edit rule'), self)
        connect_lambda(b.clicked, self, lambda self: self.edit_rule(self.table.currentRow()))
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(700, 550)

    def accept(self):
        rules = defaultdict(list)
        for r in range(self.table.rowCount()):
            def item(c):
                return self.table.item(r, c).text()
            rules[item(0)].append([item(1), item(2)])
        msprefs['id_link_rules'] = dict(rules)
        Dialog.accept(self)

    def edit_rule(self, r=-1):
        key = name = template = ''
        if r > -1:
            key, name, template = (self.table.item(r, c).text() for c in range(3))
        d = IdLinksRuleEdit(key, name, template, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            if r < 0:
                self.table.setRowCount(self.table.rowCount() + 1)
                r = self.table.rowCount() - 1
            rule = d.rule
            for c in range(3):
                self.table.setItem(r, c, QTableWidgetItem(rule[c]))
            self.table.scrollToItem(self.table.item(r, 0))

    def remove_rule(self):
        r = self.table.currentRow()
        if r > -1:
            self.table.removeRow(r)


class BDVerticalCats(DisplayedFields):

    def __init__(self, db, parent=None, category_icons=None):
        DisplayedFields.__init__(self, db, parent, category_icons=category_icons)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()

    def initialize(self, use_defaults=False, pref_data_override=None):
        fm = self.db.field_metadata
        cats = [k for k in fm if fm[k]['name'] and fm[k]['is_multiple'] and not k.startswith('#')]
        cats.append('path')
        cats.extend([k for k in fm if fm[k]['name'] and fm[k]['is_multiple'] and k.startswith('#')])
        ans = []
        if use_defaults:
            ans = [[k, False] for k in cats]
            self.changed = True
        elif pref_data_override:
            ph = dict(pref_data_override)
            ans = [[k, ph.get(k, False)] for k in cats]
            self.changed = True
        else:
            vertical_cats = self.db.prefs.get('book_details_vertical_categories') or ()
            for key in cats:
                ans.append([key, key in vertical_cats])
        self.beginResetModel()
        self.fields = ans
        self.endResetModel()

    def commit(self):
        if self.changed:
            self.db.prefs.set('book_details_vertical_categories', [k for k,v in self.fields if v])


class BookDetailsTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register

        self.default_author_link.changed_signal.connect(self.changed_signal)
        r('bd_show_cover', gprefs)
        r('bd_overlay_cover_size', gprefs)
        r('book_details_comments_heading_pos', gprefs, choices=[
            (_('Never'), 'hide'), (_('Above text'), 'above'), (_('Beside text'), 'side')])
        r('book_details_note_link_icon_width', gprefs)
        self.id_links_button.clicked.connect(self.edit_id_link_rules)

        r('use_roman_numerals_for_series_number', config)

        self.bd_vertical_cats_model = BDVerticalCats(self.gui.current_db, parent=self)
        self.bd_vertical_cats_model.dataChanged.connect(self.changed_signal)
        self.bd_vertical_cats.setModel(self.bd_vertical_cats_model)

        self.display_model = DisplayedFields(self.gui.current_db, self.field_display_order)
        self.display_model.dataChanged.connect(self.changed_signal)
        self.field_display_order.setModel(self.display_model)
        mu = partial(move_field_up, self.field_display_order, self.display_model)
        md = partial(move_field_down, self.field_display_order, self.display_model)
        self.df_up_button.clicked.connect(mu)
        self.df_down_button.clicked.connect(md)
        self.field_display_order.set_movement_functions(mu, md)

        self.opt_book_details_css.textChanged.connect(self.changed_signal)
        from calibre.gui2.tweak_book.editor.text import get_highlighter, get_theme
        self.css_highlighter = get_highlighter('css')()
        self.css_highlighter.apply_theme(get_theme(None))
        self.css_highlighter.set_document(self.opt_book_details_css.document())

    def lazy_initialize(self):
        self.blockSignals(True)
        self.default_author_link.value = default_author_link()
        self.display_model.initialize()
        self.bd_vertical_cats_model.initialize()
        self.opt_book_details_css.setPlainText(P('templates/book_details.css', data=True).decode('utf-8'))
        self.blockSignals(False)

    def edit_id_link_rules(self):
        if IdLinksEditor(self).exec() == QDialog.DialogCode.Accepted:
            self.changed_signal.emit()

    def commit(self):
        with BusyCursor():
            self.display_model.commit()
            self.bd_vertical_cats_model.commit()
            gprefs['default_author_link'] = self.default_author_link.value
            bcss = self.opt_book_details_css.toPlainText().encode('utf-8')
            defcss = P('templates/book_details.css', data=True, allow_user_override=False)
            if defcss == bcss:
                bcss = None
            set_data('templates/book_details.css', bcss)
        return LazyConfigWidgetBase.commit(self)

    def restore_defaults(self):
        LazyConfigWidgetBase.restore_defaults(self)
        self.default_author_link.restore_defaults()
        self.display_model.restore_defaults()
        self.bd_vertical_cats_model.restore_defaults()
        self.opt_book_details_css.setPlainText(P('templates/book_details.css', allow_user_override=False, data=True).decode('utf-8'))
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        gui.book_details.book_info.refresh_css()
        gui.library_view.refresh_book_details(force=True)
        gui.library_view.refresh_composite_edit()
