#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
from collections import defaultdict
from threading import Thread

from qt.core import (
    QApplication, QFont, QFontInfo, QFontDialog, QColorDialog, QPainter, QDialog,
    QAbstractListModel, Qt, QIcon, QKeySequence, QColor, pyqtSignal, QHeaderView, QListWidgetItem,
    QWidget, QSizePolicy, QBrush, QPixmap, QSize, QPushButton, QVBoxLayout, QItemSelectionModel,
    QTableWidget, QTableWidgetItem, QLabel, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
)

from calibre import human_readable
from calibre.ebooks.metadata.book.render import DEFAULT_AUTHOR_LINK
from calibre.constants import ismacos, iswindows
from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.gui2.custom_column_widgets import get_field_list as em_get_field_list
from calibre.gui2 import default_author_link, icon_resource_manager, choose_save_file, choose_files
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget, CommaSeparatedList
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2 import config, gprefs, qt_app, open_local_file, question_dialog, error_dialog
from calibre.utils.localization import (available_translations,
    get_language, get_lang)
from calibre.utils.config import prefs
from calibre.utils.icu import sort_key
from calibre.gui2.book_details import get_field_list
from calibre.gui2.dialogs.quickview import get_qv_field_list
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.library.alternate_views import auto_height, CM_TO_INCH
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.utils.resources import set_data
from polyglot.builtins import iteritems


class DefaultAuthorLink(QWidget):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = QVBoxLayout(parent)
        l.addWidget(self)
        l.setContentsMargins(0, 0, 0, 0)
        l = QFormLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.choices = c = QComboBox()
        c.setMinimumContentsLength(30)
        for text, data in [
                (_('Search for the author on Goodreads'), 'search-goodreads'),
                (_('Search for the author on Amazon'), 'search-amzn'),
                (_('Search for the author in your calibre library'), 'search-calibre'),
                (_('Search for the author on Wikipedia'), 'search-wikipedia'),
                (_('Search for the author on Google Books'), 'search-google'),
                (_('Search for the book on Goodreads'), 'search-goodreads-book'),
                (_('Search for the book on Amazon'), 'search-amzn-book'),
                (_('Search for the book on Google Books'), 'search-google-book'),
                (_('Use a custom search URL'), 'url'),
        ]:
            c.addItem(text, data)
        l.addRow(_('Clicking on &author names should:'), c)
        self.custom_url = u = QLineEdit(self)
        u.setToolTip(_(
            'Enter the URL to search. It should contain the string {0}'
            '\nwhich will be replaced by the author name. For example,'
            '\n{1}').format('{author}', 'https://en.wikipedia.org/w/index.php?search={author}'))
        u.textChanged.connect(self.changed_signal)
        u.setPlaceholderText(_('Enter the URL'))
        c.currentIndexChanged.connect(self.current_changed)
        l.addRow(u)
        self.current_changed()
        c.currentIndexChanged.connect(self.changed_signal)

    @property
    def value(self):
        k = self.choices.currentData()
        if k == 'url':
            return self.custom_url.text()
        return k if k != DEFAULT_AUTHOR_LINK else None

    @value.setter
    def value(self, val):
        i = self.choices.findData(val)
        if i < 0:
            i = self.choices.findData('url')
            self.custom_url.setText(val)
        self.choices.setCurrentIndex(i)

    def current_changed(self):
        k = self.choices.currentData()
        self.custom_url.setVisible(k == 'url')
# }}}

# IdLinksEditor {{{


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
        items.sort(key=lambda x:sort_key(x[1]))
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
            key, name, template = map(lambda c: self.table.item(r, c).text(), range(3))
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
# }}}


class DisplayedFields(QAbstractListModel):  # {{{

    def __init__(self, db, parent=None, pref_name=None):
        self.pref_name = pref_name or 'book_display_fields'
        QAbstractListModel.__init__(self, parent)

        self.fields = []
        self.db = db
        self.changed = False

    def get_field_list(self, use_defaults=False):
        return get_field_list(self.db.field_metadata, use_defaults=use_defaults, pref_name=self.pref_name)

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in self.get_field_list(use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def rowCount(self, *args):
        return len(self.fields)

    def data(self, index, role):
        try:
            field, visible = self.fields[index.row()]
        except:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            name = field
            try:
                name = self.db.field_metadata[field]['name']
            except:
                pass
            if not name:
                return field
            return f'{name} ({field})'
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DecorationRole and field.startswith('#'):
            return QIcon.ic('column.png')
        return None

    def toggle_all(self, show=True):
        for i in range(self.rowCount()):
            idx = self.index(i)
            if idx.isValid():
                self.setData(idx, Qt.CheckState.Checked if show else Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, val, role):
        ret = False
        if role == Qt.ItemDataRole.CheckStateRole:
            self.fields[index.row()][1] = val in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            self.changed = True
            ret = True
            self.dataChanged.emit(index, index)
        return ret

    def restore_defaults(self):
        self.initialize(use_defaults=True)

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref(self.pref_name, self.fields)

    def move(self, idx, delta):
        row = idx.row() + delta
        if row >= 0 and row < len(self.fields):
            t = self.fields[row]
            self.fields[row] = self.fields[row-delta]
            self.fields[row-delta] = t
            self.dataChanged.emit(idx, idx)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)
            self.changed = True
            return idx


def move_field_up(widget, model):
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, -1)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)


def move_field_down(widget, model):
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, 1)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)

# }}}


class EMDisplayedFields(DisplayedFields):  # {{{
    def __init__(self, db, parent=None):
        DisplayedFields.__init__(self, db, parent)

    def initialize(self, use_defaults=False, pref_data_override=None):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in
                em_get_field_list(self.db, use_defaults=use_defaults, pref_data_override=pref_data_override)]
        self.endResetModel()
        self.changed = True

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref('edit_metadata_custom_columns_to_display', self.fields)
# }}}


class QVDisplayedFields(DisplayedFields):  # {{{

    def __init__(self, db, parent=None):
        DisplayedFields.__init__(self, db, parent)

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in
                get_qv_field_list(self.db.field_metadata, use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref('qv_display_fields', self.fields)

# }}}


class Background(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.bcol = QColor(*gprefs['cover_grid_color'])
        self.btex = gprefs['cover_grid_texture']
        self.update_brush()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def update_brush(self):
        self.brush = QBrush(self.bcol)
        if self.btex:
            from calibre.gui2.preferences.texture_chooser import texture_path
            path = texture_path(self.btex)
            if path:
                p = QPixmap(path)
                try:
                    dpr = self.devicePixelRatioF()
                except AttributeError:
                    dpr = self.devicePixelRatio()
                p.setDevicePixelRatio(dpr)
                self.brush.setTexture(p)
        self.update()

    def sizeHint(self):
        return QSize(200, 120)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.fillRect(ev.rect(), self.brush)
        painter.end()
# }}}


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    size_calculated = pyqtSignal(object)

    def genesis(self, gui):
        self.gui = gui
        if not ismacos and not iswindows:
            self.label_widget_style.setVisible(False)
            self.opt_ui_style.setVisible(False)

        db = gui.library_view.model().db

        r = self.register

        try:
            self.icon_theme_title = icon_resource_manager.user_theme_title
        except Exception:
            self.icon_theme_title = _('Default icons')
        self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
        self.commit_icon_theme = None
        self.icon_theme_button.clicked.connect(self.choose_icon_theme)
        self.default_author_link = DefaultAuthorLink(self.default_author_link_container)
        self.default_author_link.changed_signal.connect(self.changed_signal)
        r('gui_layout', config, restart_required=True, choices=[(_('Wide'), 'wide'), (_('Narrow'), 'narrow')])
        r('ui_style', gprefs, restart_required=True, choices=[(_('System default'), 'system'), (_('calibre style'), 'calibre')])
        r('book_list_tooltips', gprefs)
        r('dnd_merge', gprefs)
        r('wrap_toolbar_text', gprefs, restart_required=True)
        r('show_layout_buttons', gprefs, restart_required=True)
        r('row_numbers_in_book_list', gprefs)
        r('tag_browser_old_look', gprefs)
        r('tag_browser_hide_empty_categories', gprefs)
        r('tag_browser_always_autocollapse', gprefs)
        r('tag_browser_show_tooltips', gprefs)
        r('tag_browser_allow_keyboard_focus', gprefs)
        r('bd_show_cover', gprefs)
        r('bd_overlay_cover_size', gprefs)
        r('cover_grid_width', gprefs)
        r('cover_grid_height', gprefs)
        r('cover_grid_cache_size_multiple', gprefs)
        r('cover_grid_disk_cache_size', gprefs)
        r('cover_grid_spacing', gprefs)
        r('cover_grid_show_title', gprefs)
        r('tag_browser_show_counts', gprefs)
        r('tag_browser_item_padding', gprefs)
        r('books_autoscroll_time', gprefs)

        r('qv_respects_vls', gprefs)
        r('qv_dclick_changes_column', gprefs)
        r('qv_retkey_changes_column', gprefs)
        r('qv_follows_column', gprefs)

        r('cover_flow_queue_length', config, restart_required=True)
        r('cover_browser_reflections', gprefs)
        r('cover_browser_title_template', db.prefs)
        fm = db.field_metadata
        r('cover_browser_subtitle_field', db.prefs, choices=[(_('No subtitle'), 'none')] + sorted(
            (fm[k].get('name'), k) for k in fm.all_field_keys() if fm[k].get('name')
        ))
        r('emblem_size', gprefs)
        r('emblem_position', gprefs, choices=[
            (_('Left'), 'left'), (_('Top'), 'top'), (_('Right'), 'right'), (_('Bottom'), 'bottom')])
        r('book_list_extra_row_spacing', gprefs)
        r('booklist_grid', gprefs)
        r('book_details_comments_heading_pos', gprefs, choices=[
            (_('Never'), 'hide'), (_('Above text'), 'above'), (_('Beside text'), 'side')])
        self.cover_browser_title_template_button.clicked.connect(self.edit_cb_title_template)
        self.id_links_button.clicked.connect(self.edit_id_link_rules)

        def get_esc_lang(l):
            if l == 'en':
                return 'English'
            return get_language(l)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_esc_lang(l)) for l in available_translations()
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_esc_lang('en')))
        items.sort(key=lambda x: x[1].lower())
        choices = [(y, x) for x, y in items]
        # Default language is the autodetected one
        choices = [(get_language(lang), lang)] + choices
        r('language', prefs, choices=choices, restart_required=True)

        r('show_avg_rating', config)
        r('disable_animations', config)
        r('systray_icon', config, restart_required=True)
        r('show_splash_screen', gprefs)
        r('disable_tray_notification', config)
        r('use_roman_numerals_for_series_number', config)
        r('separate_cover_flow', config, restart_required=True)
        r('cb_fullscreen', gprefs)
        r('cb_preserve_aspect_ratio', gprefs)
        r('cb_double_click_to_activate', gprefs)

        choices = [(_('Off'), 'off'), (_('Small'), 'small'),
            (_('Medium'), 'medium'), (_('Large'), 'large')]
        r('toolbar_icon_size', gprefs, choices=choices)

        choices = [(_('If there is enough room'), 'auto'), (_('Always'), 'always'),
            (_('Never'), 'never')]
        r('toolbar_text', gprefs, choices=choices)

        choices = [(_('Disabled'), 'disable'), (_('By first letter'), 'first letter'),
                   (_('Partitioned'), 'partition')]
        r('tags_browser_partition_method', gprefs, choices=choices)
        r('tags_browser_collapse_at', gprefs)
        r('tags_browser_collapse_fl_at', gprefs)

        choices = {k for k in db.field_metadata.all_field_keys()
                if (db.field_metadata[k]['is_category'] and (
                    db.field_metadata[k]['datatype'] in ['text', 'series', 'enumeration'
                    ]) and not db.field_metadata[k]['display'].get('is_names', False)) or (
                    db.field_metadata[k]['datatype'] in ['composite'
                    ] and db.field_metadata[k]['display'].get('make_category', False))}
        choices |= {'search'}
        r('tag_browser_dont_collapse', gprefs, setting=CommaSeparatedList,
          choices=sorted(choices, key=sort_key))

        choices -= {'authors', 'publisher', 'formats', 'news', 'identifiers'}
        r('categories_using_hierarchy', db.prefs, setting=CommaSeparatedList,
          choices=sorted(choices, key=sort_key))

        fm = db.field_metadata
        choices = sorted(((fm[k]['name'], k) for k in fm.displayable_field_keys() if fm[k]['name']),
                         key=lambda x:sort_key(x[0]))
        r('field_under_covers_in_grid', db.prefs, choices=choices)

        choices = [(_('Default'), 'default'), (_('Compact metadata'), 'alt1'),
                   (_('All on 1 tab'), 'alt2')]
        r('edit_metadata_single_layout', gprefs,
          choices=[(_('Default'), 'default'), (_('Compact metadata'), 'alt1'),
                   (_('All on 1 tab'), 'alt2')])
        r('edit_metadata_ignore_display_order', db.prefs)
        r('edit_metadata_elision_point', gprefs,
          choices=[(_('Left'), 'left'), (_('Middle'), 'middle'),
                   (_('Right'), 'right')])
        r('edit_metadata_elide_labels', gprefs)
        r('edit_metadata_single_use_2_cols_for_custom_fields', gprefs)
        r('edit_metadata_bulk_cc_label_length', gprefs)
        r('edit_metadata_single_cc_label_length', gprefs)
        r('edit_metadata_templates_only_F2_on_booklist', gprefs)

        self.current_font = self.initial_font = None
        self.change_font_button.clicked.connect(self.change_font)

        self.display_model = DisplayedFields(self.gui.current_db,
                self.field_display_order)
        self.display_model.dataChanged.connect(self.changed_signal)
        self.field_display_order.setModel(self.display_model)
        connect_lambda(self.df_up_button.clicked, self,
                lambda self: move_field_up(self.field_display_order, self.display_model))
        connect_lambda(self.df_down_button.clicked, self,
                lambda self: move_field_down(self.field_display_order, self.display_model))

        self.em_display_model = EMDisplayedFields(self.gui.current_db,
                self.em_display_order)
        self.em_display_model.dataChanged.connect(self.changed_signal)
        self.em_display_order.setModel(self.em_display_model)
        connect_lambda(self.em_up_button.clicked, self,
                lambda self: move_field_up(self.em_display_order, self.em_display_model))
        connect_lambda(self.em_down_button.clicked, self,
                lambda self: move_field_down(self.em_display_order, self.em_display_model))
        self.em_export_layout_button.clicked.connect(self.em_export_layout)
        self.em_import_layout_button.clicked.connect(self.em_import_layout)
        self.em_reset_layout_button.clicked.connect(self.em_reset_layout)

        self.qv_display_model = QVDisplayedFields(self.gui.current_db,
                self.qv_display_order)
        self.qv_display_model.dataChanged.connect(self.changed_signal)
        self.qv_display_order.setModel(self.qv_display_model)
        connect_lambda(self.qv_up_button.clicked, self,
                lambda self: move_field_up(self.qv_display_order, self.qv_display_model))
        connect_lambda(self.qv_down_button.clicked, self,
                lambda self: move_field_down(self.qv_display_order, self.qv_display_model))

        self.edit_rules = EditRules(self.tabWidget)
        self.edit_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.edit_rules,
                QIcon.ic('format-fill-color.png'), _('Column &coloring'))

        self.icon_rules = EditRules(self.tabWidget)
        self.icon_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.icon_rules,
                QIcon.ic('icon_choose.png'), _('Column &icons'))

        self.grid_rules = EditRules(self.emblems_tab)
        self.grid_rules.changed.connect(self.changed_signal)
        self.emblems_tab.setLayout(QVBoxLayout())
        self.emblems_tab.layout().addWidget(self.grid_rules)

        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.tabBar().setVisible(False)
        keys = [QKeySequence('F11', QKeySequence.SequenceFormat.PortableText), QKeySequence(
            'Ctrl+Shift+F', QKeySequence.SequenceFormat.PortableText)]
        keys = [str(x.toString(QKeySequence.SequenceFormat.NativeText)) for x in keys]
        self.fs_help_msg.setText(self.fs_help_msg.text()%(
            QKeySequence(QKeySequence.StandardKey.FullScreen).toString(QKeySequence.SequenceFormat.NativeText)))
        self.size_calculated.connect(self.update_cg_cache_size, type=Qt.ConnectionType.QueuedConnection)
        self.tabWidget.currentChanged.connect(self.tab_changed)

        l = self.cg_background_box.layout()
        self.cg_bg_widget = w = Background(self)
        l.addWidget(w, 0, 0, 3, 1)
        self.cover_grid_color_button = b = QPushButton(_('Change &color'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 0, 1)
        b.clicked.connect(self.change_cover_grid_color)
        self.cover_grid_texture_button = b = QPushButton(_('Change &background image'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 1, 1)
        b.clicked.connect(self.change_cover_grid_texture)
        self.cover_grid_default_appearance_button = b = QPushButton(_('Restore default &appearance'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.restore_cover_grid_appearance)
        self.cover_grid_empty_cache.clicked.connect(self.empty_cache)
        self.cover_grid_open_cache.clicked.connect(self.open_cg_cache)
        connect_lambda(self.cover_grid_smaller_cover.clicked, self, lambda self: self.resize_cover(True))
        connect_lambda(self.cover_grid_larger_cover.clicked, self, lambda self: self.resize_cover(False))
        self.cover_grid_reset_size.clicked.connect(self.cg_reset_size)
        self.opt_cover_grid_disk_cache_size.setMinimum(self.gui.grid_view.thumbnail_cache.min_disk_cache)
        self.opt_cover_grid_disk_cache_size.setMaximum(self.gui.grid_view.thumbnail_cache.min_disk_cache * 100)
        self.opt_cover_grid_width.valueChanged.connect(self.update_aspect_ratio)
        self.opt_cover_grid_height.valueChanged.connect(self.update_aspect_ratio)
        self.opt_book_details_css.textChanged.connect(self.changed_signal)
        from calibre.gui2.tweak_book.editor.text import get_highlighter, get_theme
        self.css_highlighter = get_highlighter('css')()
        self.css_highlighter.apply_theme(get_theme(None))
        self.css_highlighter.set_document(self.opt_book_details_css.document())
        for i in range(self.tabWidget.count()):
            self.sections_view.addItem(QListWidgetItem(self.tabWidget.tabIcon(i), self.tabWidget.tabText(i).replace('&', '')))
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())
        self.sections_view.currentRowChanged.connect(self.tabWidget.setCurrentIndex)
        self.sections_view.setMaximumWidth(self.sections_view.sizeHintForColumn(0) + 16)
        self.sections_view.setSpacing(4)
        self.sections_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabWidget.currentWidget().setFocus(Qt.FocusReason.OtherFocusReason)

    def em_export_layout(self):
        filename = choose_save_file(self, 'em_import_export_field_list',
                _('Save column list to file'),
                filters=[(_('Column list'), ['json'])])
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.em_display_model.fields, f, indent=1)
            except Exception as err:
                error_dialog(self, _('Export field layout'),
                             _('<p>Could not write field list. Error:<br>%s')%err, show=True)

    def em_import_layout(self):
        filename = choose_files(self, 'em_import_export_field_list',
                _('Load column list from file'),
                filters=[(_('Column list'), ['json'])])
        if filename:
            try:
                with open(filename[0]) as f:
                    fields = json.load(f)
                self.em_display_model.initialize(pref_data_override=fields)
                self.changed_signal.emit()
            except Exception as err:
                error_dialog(self, _('Import layout'),
                             _('<p>Could not read field list. Error:<br>%s')%err, show=True)

    def em_reset_layout(self):
        self.em_display_model.initialize(use_defaults=True)
        self.changed_signal.emit()

    def choose_icon_theme(self):
        from calibre.gui2.icon_theme import ChooseTheme
        d = ChooseTheme(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.commit_icon_theme = d.commit_changes
            self.icon_theme_title = d.new_theme_title or _('Default icons')
            self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
            self.changed_signal.emit()

    def edit_id_link_rules(self):
        if IdLinksEditor(self).exec() == QDialog.DialogCode.Accepted:
            self.changed_signal.emit()

    @property
    def current_cover_size(self):
        cval = self.opt_cover_grid_height.value()
        wval = self.opt_cover_grid_width.value()
        if cval < 0.1:
            dpi = self.opt_cover_grid_height.logicalDpiY()
            cval = auto_height(self.opt_cover_grid_height) / dpi / CM_TO_INCH
        if wval < 0.1:
            wval = 0.75 * cval
        return wval, cval

    def update_aspect_ratio(self, *args):
        width, height = self.current_cover_size
        ar = width / height
        self.cover_grid_aspect_ratio.setText(_('Current aspect ratio (width/height): %.2g') % ar)

    def resize_cover(self, smaller):
        wval, cval = self.current_cover_size
        ar = wval / cval
        delta = 0.2 * (-1 if smaller else 1)
        cval += delta
        cval = max(0, cval)
        self.opt_cover_grid_height.setValue(cval)
        self.opt_cover_grid_width.setValue(cval * ar)

    def cg_reset_size(self):
        self.opt_cover_grid_width.setValue(0)
        self.opt_cover_grid_height.setValue(0)

    def edit_cb_title_template(self):
        t = TemplateDialog(self, self.opt_cover_browser_title_template.text(), fm=self.gui.current_db.field_metadata)
        t.setWindowTitle(_('Edit template for caption'))
        if t.exec():
            self.opt_cover_browser_title_template.setText(t.rule[1])

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.default_author_link.value = default_author_link()
        font = gprefs['font']
        if font is not None:
            font = list(font)
            font.append(gprefs.get('font_stretch', QFont.Stretch.Unstretched))
        self.current_font = self.initial_font = font
        self.update_font_display()
        self.display_model.initialize()
        self.em_display_model.initialize()
        self.qv_display_model.initialize()
        db = self.gui.current_db
        mi = []
        try:
            rows = self.gui.current_view().selectionModel().selectedRows()
            for row in rows:
                if row.isValid():
                    mi.append(db.new_api.get_proxy_metadata(db.data.index_to_id(row.row())))
        except:
            pass
        self.edit_rules.initialize(db.field_metadata, db.prefs, mi, 'column_color_rules')
        self.icon_rules.initialize(db.field_metadata, db.prefs, mi, 'column_icon_rules')
        self.grid_rules.initialize(db.field_metadata, db.prefs, mi, 'cover_grid_icon_rules')
        self.set_cg_color(gprefs['cover_grid_color'])
        self.set_cg_texture(gprefs['cover_grid_texture'])
        self.update_aspect_ratio()
        self.opt_book_details_css.blockSignals(True)
        self.opt_book_details_css.setPlainText(P('templates/book_details.css', data=True).decode('utf-8'))
        self.opt_book_details_css.blockSignals(False)
        self.tb_focus_label.setVisible(self.opt_tag_browser_allow_keyboard_focus.isChecked())

    def open_cg_cache(self):
        open_local_file(self.gui.grid_view.thumbnail_cache.location)

    def update_cg_cache_size(self, size):
        self.cover_grid_current_disk_cache.setText(
            _('Current space used: %s') % human_readable(size))

    def tab_changed(self, index):
        if self.tabWidget.currentWidget() is self.cover_grid_tab:
            self.show_current_cache_usage()

    def show_current_cache_usage(self):
        t = Thread(target=self.calc_cache_size)
        t.daemon = True
        t.start()

    def calc_cache_size(self):
        self.size_calculated.emit(self.gui.grid_view.thumbnail_cache.current_size)

    def set_cg_color(self, val):
        self.cg_bg_widget.bcol = QColor(*val)
        self.cg_bg_widget.update_brush()

    def set_cg_texture(self, val):
        self.cg_bg_widget.btex = val
        self.cg_bg_widget.update_brush()

    def empty_cache(self):
        self.gui.grid_view.thumbnail_cache.empty()
        self.calc_cache_size()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.default_author_link.value = DEFAULT_AUTHOR_LINK
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.update_font_display()
        self.display_model.restore_defaults()
        self.em_display_model.restore_defaults()
        self.qv_display_model.restore_defaults()
        self.edit_rules.clear()
        self.icon_rules.clear()
        self.grid_rules.clear()
        self.changed_signal.emit()
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])
        self.opt_book_details_css.setPlainText(P('templates/book_details.css', allow_user_override=False, data=True).decode('utf-8'))

    def change_cover_grid_color(self):
        col = QColorDialog.getColor(self.cg_bg_widget.bcol,
                              self.gui, _('Choose background color for the Cover grid'))
        if col.isValid():
            col = tuple(col.getRgb())[:3]
            self.set_cg_color(col)
            self.changed_signal.emit()
            if self.cg_bg_widget.btex:
                if question_dialog(
                    self, _('Remove background image?'),
                    _('There is currently a background image set, so the color'
                      ' you have chosen will not be visible. Remove the background image?')):
                    self.set_cg_texture(None)

    def change_cover_grid_texture(self):
        from calibre.gui2.preferences.texture_chooser import TextureChooser
        d = TextureChooser(parent=self, initial=self.cg_bg_widget.btex)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.set_cg_texture(d.texture)
            self.changed_signal.emit()

    def restore_cover_grid_appearance(self):
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])
        self.changed_signal.emit()

    def build_font_obj(self):
        font_info = qt_app.original_font if self.current_font is None else self.current_font
        font = QFont(*(font_info[:4]))
        font.setStretch(font_info[4])
        return font

    def update_font_display(self):
        font = self.build_font_obj()
        fi = QFontInfo(font)
        name = str(fi.family())

        self.font_display.setFont(font)
        self.font_display.setText(name + ' [%dpt]'%fi.pointSize())

    def change_font(self, *args):
        fd = QFontDialog(self.build_font_obj(), self)
        if fd.exec() == QDialog.DialogCode.Accepted:
            font = fd.selectedFont()
            fi = QFontInfo(font)
            self.current_font = [str(fi.family()), fi.pointSize(),
                    fi.weight(), fi.italic(), font.stretch()]
            self.update_font_display()
            self.changed_signal.emit()

    def commit(self, *args):
        with BusyCursor():
            rr = ConfigWidgetBase.commit(self, *args)
            if self.current_font != self.initial_font:
                gprefs['font'] = (self.current_font[:4] if self.current_font else
                        None)
                gprefs['font_stretch'] = (self.current_font[4] if self.current_font
                        is not None else QFont.Stretch.Unstretched)
                QApplication.setFont(self.font_display.font())
                rr = True
            self.display_model.commit()
            self.em_display_model.commit()
            self.qv_display_model.commit()
            self.edit_rules.commit(self.gui.current_db.prefs)
            self.icon_rules.commit(self.gui.current_db.prefs)
            self.grid_rules.commit(self.gui.current_db.prefs)
            gprefs['cover_grid_color'] = tuple(self.cg_bg_widget.bcol.getRgb())[:3]
            gprefs['cover_grid_texture'] = self.cg_bg_widget.btex
            if self.commit_icon_theme is not None:
                self.commit_icon_theme()
            gprefs['default_author_link'] = self.default_author_link.value
            bcss = self.opt_book_details_css.toPlainText().encode('utf-8')
            defcss = P('templates/book_details.css', data=True, allow_user_override=False)
            if defcss == bcss:
                bcss = None
            set_data('templates/book_details.css', bcss)

        return rr

    def refresh_gui(self, gui):
        gui.book_details.book_info.refresh_css()
        m = gui.library_view.model()
        m.beginResetModel(), m.endResetModel()
        self.update_font_display()
        gui.tags_view.set_look_and_feel()
        gui.tags_view.reread_collapse_parameters()
        gui.library_view.refresh_book_details(force=True)
        gui.library_view.refresh_grid()
        gui.library_view.refresh_composite_edit()
        gui.library_view.set_row_header_visibility()
        gui.cover_flow.setShowReflections(gprefs['cover_browser_reflections'])
        gui.cover_flow.setPreserveAspectRatio(gprefs['cb_preserve_aspect_ratio'])
        gui.cover_flow.setActivateOnDoubleClick(gprefs['cb_double_click_to_activate'])
        gui.update_cover_flow_subtitle_font()
        gui.cover_flow.template_inited = False
        for view in 'library memory card_a card_b'.split():
            getattr(gui, view + '_view').set_row_header_visibility()
        gui.library_view.refresh_row_sizing()
        gui.grid_view.refresh_settings()
        gui.update_auto_scroll_timeout()
        qv = get_quickview_action_plugin()
        if qv:
            qv.refill_quickview()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')
