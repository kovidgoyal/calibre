#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import numbers
from operator import attrgetter, methodcaller
from functools import partial
from collections import namedtuple
from polyglot.builtins import iteritems, itervalues
from itertools import product
from copy import copy, deepcopy

from qt.core import (
    QDialog, QGridLayout, QStackedWidget, QDialogButtonBox, QListWidget,
    QListWidgetItem, QIcon, QWidget, QSize, QFormLayout, Qt, QSpinBox, QListView,
    QCheckBox, pyqtSignal, QDoubleSpinBox, QComboBox, QLabel, QFont, QApplication,
    QFontComboBox, QPushButton, QSizePolicy, QHBoxLayout, QGroupBox, QAbstractItemView,
    QToolButton, QVBoxLayout, QSpacerItem, QTimer, QRadioButton)

from calibre import prepare_string_for_xml
from calibre.utils.localization import get_lang
from calibre.gui2 import info_dialog
from calibre.gui2.keyboard import ShortcutConfig
from calibre.gui2.tweak_book import tprefs, toolbar_actions, editor_toolbar_actions, actions
from calibre.gui2.tweak_book.editor.themes import default_theme, all_theme_names, ThemeEditor
from calibre.gui2.tweak_book.spell import ManageDictionaries
from calibre.gui2.font_family_chooser import FontFamilyChooser
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets2 import ColorButton


class BasicSettings(QWidget):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.settings = {}
        self._prevent_changed = False
        self.Setting = namedtuple('Setting', 'name prefs widget getter setter initial_value')

    def __call__(self, name, widget=None, getter=None, setter=None, prefs=None):
        prefs = prefs or tprefs
        defval = prefs.defaults[name]
        inval = prefs[name]
        if widget is None:
            if isinstance(defval, bool):
                widget = QCheckBox(self)
                getter = getter or methodcaller('isChecked')
                setter = setter or (lambda x, v: x.setChecked(v))
                widget.toggled.connect(self.emit_changed)
            elif isinstance(defval, numbers.Number):
                widget = (QSpinBox if isinstance(defval, numbers.Integral) else QDoubleSpinBox)(self)
                getter = getter or methodcaller('value')
                setter = setter or (lambda x, v:x.setValue(v))
                widget.valueChanged.connect(self.emit_changed)
            else:
                raise TypeError('Unknown setting type for setting: %s' % name)
        else:
            if getter is None or setter is None:
                raise ValueError("getter or setter not provided for: %s" % name)
        self._prevent_changed = True
        setter(widget, inval)
        self._prevent_changed = False

        self.settings[name] = self.Setting(name, prefs, widget, getter, setter, inval)
        return widget

    def choices_widget(self, name, choices, fallback_val, none_val, prefs=None):
        prefs = prefs or tprefs
        widget = QComboBox(self)
        widget.currentIndexChanged.connect(self.emit_changed)
        for key, human in sorted(iteritems(choices), key=lambda key_human: key_human[1] or key_human[0]):
            widget.addItem(human or key, key)

        def getter(w):
            ans = str(w.itemData(w.currentIndex()) or '')
            return {none_val:None}.get(ans, ans)

        def setter(w, val):
            val = {None:none_val}.get(val, val)
            idx = w.findData(val, flags=Qt.MatchFlag.MatchFixedString|Qt.MatchFlag.MatchCaseSensitive)
            if idx == -1:
                idx = w.findData(fallback_val, flags=Qt.MatchFlag.MatchFixedString|Qt.MatchFlag.MatchCaseSensitive)
            w.setCurrentIndex(idx)

        return self(name, widget=widget, getter=getter, setter=setter, prefs=prefs)

    def order_widget(self, name, prefs=None):
        prefs = prefs or tprefs
        widget = QListWidget(self)
        widget.addItems(prefs.defaults[name])
        widget.setDragEnabled(True)
        widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        widget.viewport().setAcceptDrops(True)
        widget.setDropIndicatorShown(True)
        widget.indexesMoved.connect(self.emit_changed)
        widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        widget.setMovement(QListView.Movement.Snap)
        widget.setSpacing(5)
        widget.defaults = prefs.defaults[name]

        def getter(w):
            return list(map(str, (w.item(i).text() for i in range(w.count()))))

        def setter(w, val):
            order_map = {x:i for i, x in enumerate(val)}
            items = list(w.defaults)
            limit = len(items)
            items.sort(key=lambda x:order_map.get(x, limit))
            w.clear()
            for x in items:
                i = QListWidgetItem(w)
                i.setText(x)
                i.setFlags(i.flags() | Qt.ItemFlag.ItemIsDragEnabled)

        return self(name, widget=widget, getter=getter, setter=setter, prefs=prefs)

    def emit_changed(self, *args):
        if not self._prevent_changed:
            self.changed_signal.emit()

    def commit(self):
        with tprefs:
            for name in self.settings:
                cv = self.current_value(name)
                if self.initial_value(name) != cv:
                    prefs = self.settings[name].prefs
                    if cv == self.default_value(name):
                        del prefs[name]
                    else:
                        prefs[name] = cv

    def restore_defaults(self):
        for setting in itervalues(self.settings):
            setting.setter(setting.widget, self.default_value(setting.name))

    def initial_value(self, name):
        return self.settings[name].initial_value

    def current_value(self, name):
        s = self.settings[name]
        return s.getter(s.widget)

    def default_value(self, name):
        s = self.settings[name]
        return s.prefs.defaults[name]

    def setting_changed(self, name):
        return self.current_value(name) != self.initial_value(name)
# }}}


class EditorSettings(BasicSettings):  # {{{

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.dictionaries_changed = self.snippets_changed = False
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        fc = FontFamilyChooser(self)
        self('editor_font_family', widget=fc, getter=attrgetter('font_family'), setter=lambda x, val: setattr(x, 'font_family', val))
        fc.family_changed.connect(self.emit_changed)
        l.addRow(_('Editor font &family:'), fc)

        fs = self('editor_font_size')
        fs.setMinimum(8), fs.setSuffix(' pt'), fs.setMaximum(50)
        l.addRow(_('Editor font &size:'), fs)

        choices = self.theme_choices()
        theme = self.choices_widget('editor_theme', choices, 'auto', 'auto')
        self.custom_theme_button = b = QPushButton(_('Create/edit &custom color schemes'))
        b.clicked.connect(self.custom_theme)
        h = QHBoxLayout()
        h.addWidget(theme), h.addWidget(b)
        l.addRow(_('&Color scheme:'), h)
        l.labelForField(h).setBuddy(theme)

        tw = self('editor_tab_stop_width')
        tw.setMinimum(2), tw.setSuffix(_(' characters')), tw.setMaximum(20)
        l.addRow(_('W&idth of tabs:'), tw)

        self.tb = b = QPushButton(_('Change &templates'))
        l.addRow(_('Templates for new files:'), b)
        connect_lambda(b.clicked, self, lambda self: TemplatesDialog(self).exec())

        lw = self('editor_line_wrap')
        lw.setText(_('&Wrap long lines in the editor'))
        l.addRow(lw)

        lw = self('replace_entities_as_typed')
        lw.setText(_('&Replace HTML entities as they are typed'))
        lw.setToolTip('<p>' + _(
            'With this option, every time you type in a complete html entity, such as &amp;hellip;'
            ' it is automatically replaced by its corresponding character. The replacement'
            ' happens only when the trailing semi-colon is typed.'))
        l.addRow(lw)

        lw = self('auto_close_tags')
        lw.setText(_('Auto close t&ags when typing </'))
        lw.setToolTip('<p>' + prepare_string_for_xml(_(
            'With this option, every time you type </ the current HTML closing tag is auto-completed')))
        l.addRow(lw)

        lw = self('editor_show_char_under_cursor')
        lw.setText(_('Show the &name of the current character before the cursor along with the line and column number'))
        l.addRow(lw)

        lw = self('pretty_print_on_open')
        lw.setText(_('Beautify individual &files automatically when they are opened'))
        lw.setToolTip('<p>' + _(
            'This will cause the beautify current file action to be performed automatically every'
            ' time you open a HTML/CSS/etc. file for editing.'))
        l.addRow(lw)

        lw = self('inline_spell_check')
        lw.setText(_('Show &misspelled words underlined in the code view'))
        lw.setToolTip('<p>' + _(
            'This will cause spelling errors to be highlighted in the code view'
            ' for easy correction as you type.'))
        l.addRow(lw)

        lw = self('editor_accepts_drops')
        lw.setText(_('Allow drag and drop &editing of text'))
        lw.setToolTip('<p>' + _(
            'Allow using drag and drop to move text around in the editor.'
            ' It can be useful to turn this off if you have a misbehaving touchpad.'))
        l.addRow(lw)

        self.dictionaries = d = QPushButton(_('Manage &spelling dictionaries'), self)
        d.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        d.clicked.connect(self.manage_dictionaries)
        l.addRow(d)

        self.snippets = s = QPushButton(_('Manage sni&ppets'), self)
        s.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        s.clicked.connect(self.manage_snippets)
        l.addRow(s)

    def manage_dictionaries(self):
        d = ManageDictionaries(self)
        d.exec()
        self.dictionaries_changed = True

    def manage_snippets(self):
        from calibre.gui2.tweak_book.editor.snippets import UserSnippets
        d = UserSnippets(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.snippets_changed = True

    def theme_choices(self):
        choices = {k:k for k in all_theme_names()}
        choices['auto'] = _('Automatic (%s)') % default_theme()
        return choices

    def custom_theme(self):
        d = ThemeEditor(parent=self)
        d.exec()
        choices = self.theme_choices()
        s = self.settings['editor_theme']
        current_val = s.getter(s.widget)
        s.widget.clear()
        for key, human in sorted(iteritems(choices), key=lambda key_human1: key_human1[1] or key_human1[0]):
            s.widget.addItem(human or key, key)
        s.setter(s.widget, current_val)
        if d.theme_name:
            s.setter(s.widget, d.theme_name)
# }}}


class IntegrationSettings(BasicSettings):  # {{{

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        um = self('update_metadata_from_calibre')
        um.setText(_('Update &metadata embedded in the book when opening'))
        um.setToolTip('<p>' + _(
            'When the file is opened, update the metadata embedded in the book file to the current metadata'
            ' in the calibre library.'))
        l.addRow(um)

        ask = self('choose_tweak_fmt')
        ask.setText(_('Ask which &format to edit if more than one format is available for the book'))
        l.addRow(ask)

        order = self.order_widget('tweak_fmt_order')
        order.setToolTip(_('When auto-selecting the format to edit for a book with'
                           ' multiple formats, this is the preference order.'))
        l.addRow(_('Preferred format order (drag and drop to change)'), order)
# }}}


class MainWindowSettings(BasicSettings):  # {{{

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        nd = self('nestable_dock_widgets')
        nd.setText(_('Allow dockable &windows to be nested inside the dock areas'))
        nd.setToolTip('<p>' + _(
            'By default, you can have only a single row or column of windows in the dock'
            ' areas (the areas around the central editors). This option allows'
            ' for more flexible window layout, but is a little more complex to use.'))
        l.addRow(nd)

        l.addRow(QLabel(_('Choose which windows will occupy the corners of the dockable areas')))
        for v, h in product(('top', 'bottom'), ('left', 'right')):
            choices = {'vertical':{'left':_('Left'), 'right':_('Right')}[h],
                       'horizontal':{'top':_('Top'), 'bottom':_('Bottom')}[v]}
            name = f'dock_{v}_{h}'
            w = self.choices_widget(name, choices, 'horizontal', 'horizontal')
            cn = {('top', 'left'): _('The &top-left corner'), ('top', 'right'):_('The top-&right corner'),
                  ('bottom', 'left'):_('The &bottom-left corner'), ('bottom', 'right'):_('The bottom-ri&ght corner')}[(v, h)]
            l.addRow(cn + ':', w)
        nd = self('restore_book_state')
        nd.setText(_('Restore &state of previously edited book when opening it again'))
        nd.setToolTip('<p>' + _(
            'When opening a previously edited book again, restore its state. That means all open'
            ' files are automatically re-opened and the cursor is positioned at its previous location.'
        ))
        l.addRow(nd)

        nd = self('file_list_shows_full_pathname')
        nd.setText(_('Show full &file paths in the File browser'))
        nd.setToolTip('<p>' + _(
            'Showing the full file paths is useful when editing books that contain'
            ' multiple files with the same file name.'
        ))
        l.addRow(nd)
# }}}


class PreviewSettings(BasicSettings):  # {{{

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.default_font_settings = {}

        def default_font(which):
            if not self.default_font_settings:
                from qt.webengine import QWebEngineSettings, QWebEnginePage
                page = QWebEnginePage()
                s = page.settings()
                self.default_font_settings = {
                    'serif': s.fontFamily(QWebEngineSettings.FontFamily.SerifFont),
                    'sans': s.fontFamily(QWebEngineSettings.FontFamily.SansSerifFont),
                    'mono': s.fontFamily(QWebEngineSettings.FontFamily.FixedFont),
                }
            return self.default_font_settings[which]

        def family_getter(which, w):
            ans = str(w.currentFont().family())
            if ans == default_font(which):
                ans = None
            return ans

        def family_setter(which, w, val):
            w.setCurrentFont(QFont(val or default_font(which)))

        families = {'serif':_('Serif text'), 'sans':_('Sans-serif text'), 'mono':_('Monospaced text')}
        for fam in sorted(families):
            text = families[fam]
            w = QFontComboBox(self)
            self('engine_preview_%s_family' % fam, widget=w, getter=partial(family_getter, fam), setter=partial(family_setter, fam))
            l.addRow(_('Font family for &%s:') % text, w)

        w = self.choices_widget('preview_standard_font_family', families, 'serif', 'serif')
        l.addRow(_('Style for standard &text:'), w)

        w = self('preview_base_font_size')
        w.setMinimum(8), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('&Default font size:'), w)
        w = self('preview_mono_font_size')
        w.setMinimum(8), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('&Monospace font size:'), w)
        w = self('preview_minimum_font_size')
        w.setMinimum(4), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('Mi&nimum font size:'), w)
        w = self('preview_sync_context')
        w.setMinimum(0), w.setMaximum(10), w.setSuffix(' ' + _('lines'))
        w.setToolTip('<p>' + _(
            'Number of lines that are shown above the current line when syncing the text shown in the preview panel to the cursor position in the code view'))
        l.addRow(_('Visible lines above s&ync point:'), w)
        l.addRow(_('Background color:'), self.color_override('preview_background'))
        l.addRow(_('Foreground color:'), self.color_override('preview_foreground'))
        l.addRow(_('Link color:'), self.color_override('preview_link_color'))

    def color_override(self, name):
        w = QWidget(self)
        l = QHBoxLayout(w)

        def b(name, text, tt):
            ans = QRadioButton(text, w)
            l.addWidget(ans)
            ans.setToolTip(tt)
            setattr(w, name, ans)
            ans.setObjectName(name)
            return ans

        b('unset', _('No change'), _('Use the colors from the book styles, defaulting to black-on-white'))
        b('auto', _('Theme based'), _('When using a dark theme force dark colors, otherwise same as "No change"'))
        b('manual', _('Custom'), _('Choose a custom color'))

        c = w.color_button = ColorButton(parent=w)
        l.addWidget(c)
        connect_lambda(c.clicked, w, lambda w: w.manual.setChecked(True))

        def getter(w):
            if w.unset.isChecked():
                return 'unset'
            if w.auto.isChecked():
                return 'auto'
            return w.color_button.color or 'auto'

        def setter(w, val):
            val = val or 'auto'
            if val == 'unset':
                w.unset.setChecked(True)
            elif val == 'auto':
                w.auto.setChecked(True)
            else:
                w.manual.setChecked(True)
                w.color_button.color = val
        self(name, widget=w, getter=getter, setter=setter)
        l.setContentsMargins(0, 0, 0, 0)
        return w
# }}}


# ToolbarSettings  {{{


class ToolbarList(QListWidget):

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)


class ToolbarSettings(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = gl = QGridLayout(self)
        self.changed = False

        self.bars = b = QComboBox(self)
        b.addItem(_('Choose which toolbar you want to customize'))
        ft = _('Tools for %s editors')
        for name, text in (
                ('global_book_toolbar', _('Book wide actions'),),
                ('global_tools_toolbar', _('Book wide tools'),),
                ('global_plugins_toolbar', _('Book wide tools from third party plugins'),),
                ('editor_common_toolbar', _('Common tools for all editors')),
                ('editor_html_toolbar', ft % 'HTML',),
                ('editor_css_toolbar', ft % 'CSS',),
                ('editor_xml_toolbar', ft % 'XML',),
                ('editor_format_toolbar', _('Text formatting actions'),),
        ):
            b.addItem(text, name)
        self.la = la = QLabel(_('&Toolbar to customize:'))
        la.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        la.setBuddy(b)
        gl.addWidget(la), gl.addWidget(b, 0, 1)
        self.sl = l = QGridLayout()
        gl.addLayout(l, 1, 0, 1, -1)

        self.gb1 = gb1 = QGroupBox(_('A&vailable actions'), self)
        self.gb2 = gb2 = QGroupBox(_('&Current actions'), self)
        gb1.setFlat(True), gb2.setFlat(True)
        gb1.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        gb2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        l.addWidget(gb1, 0, 0, -1, 1), l.addWidget(gb2, 0, 2, -1, 1)
        self.available, self.current = ToolbarList(self), ToolbarList(self)
        self.available.itemDoubleClicked.connect(self.add_single_action)
        self.current.itemDoubleClicked.connect(self.remove_single_action)
        self.ub = b = QToolButton(self)
        connect_lambda(b.clicked, self, lambda self: self.move(up=True))
        b.setToolTip(_('Move selected action up')), b.setIcon(QIcon.ic('arrow-up.png'))
        self.db = b = QToolButton(self)
        connect_lambda(b.clicked, self, lambda self: self.move(up=False))
        b.setToolTip(_('Move selected action down')), b.setIcon(QIcon.ic('arrow-down.png'))
        self.gl1 = gl1 = QVBoxLayout()
        gl1.addWidget(self.available), gb1.setLayout(gl1)
        self.gl2 = gl2 = QGridLayout()
        gl2.addWidget(self.current, 0, 0, -1, 1)
        gl2.addWidget(self.ub, 0, 1), gl2.addWidget(self.db, 2, 1)
        gb2.setLayout(gl2)
        self.lb = b = QToolButton(self)
        b.setToolTip(_('Add selected actions to the toolbar')), b.setIcon(QIcon.ic('forward.png'))
        l.addWidget(b, 1, 1), b.clicked.connect(self.add_action)
        self.rb = b = QToolButton(self)
        b.setToolTip(_('Remove selected actions from the toolbar')), b.setIcon(QIcon.ic('back.png'))
        l.addWidget(b, 3, 1), b.clicked.connect(self.remove_action)
        self.si = QSpacerItem(20, 10, hPolicy=QSizePolicy.Policy.Preferred, vPolicy=QSizePolicy.Policy.Expanding)
        l.setRowStretch(0, 10), l.setRowStretch(2, 10), l.setRowStretch(4, 10)
        l.addItem(self.si, 4, 1)

        self.read_settings()
        self.toggle_visibility(False)
        self.bars.currentIndexChanged.connect(self.bar_changed)

        self.toolbar_icon_size = ics = QSpinBox(self)
        ics.setMinimum(16), ics.setMaximum(128), ics.setSuffix(' px'), ics.setValue(tprefs['toolbar_icon_size'])
        ics.setToolTip('<p>' + _('Adjust the size of icons on all toolbars'))
        self.h = h = QHBoxLayout()
        gl.addLayout(h, gl.rowCount(), 0, 1, -1)
        self.toolbar_icon_size_label = la = QLabel(_('Toolbar &icon size:'))
        la.setBuddy(ics)
        h.addWidget(la), h.addWidget(ics), h.addStretch(10)

    def read_settings(self, prefs=None):
        prefs = prefs or tprefs
        val = self.original_settings = {}
        for i in range(1, self.bars.count()):
            name = str(self.bars.itemData(i) or '')
            val[name] = copy(prefs[name])
        self.current_settings = deepcopy(val)

    @property
    def current_name(self):
        return str(self.bars.itemData(self.bars.currentIndex()) or '')

    def build_lists(self):
        from calibre.gui2.tweak_book.plugin import plugin_toolbar_actions
        self.available.clear(), self.current.clear()
        name = self.current_name
        if not name:
            return
        items = self.current_settings[name]
        applied = set(items)
        if name == 'global_plugins_toolbar':
            all_items = {x.sid:x for x in plugin_toolbar_actions}
        elif name.startswith('global_'):
            all_items = toolbar_actions
        elif name == 'editor_common_toolbar':
            all_items = {x:actions[x] for x in tprefs.defaults[name] if x}
        else:
            all_items = editor_toolbar_actions[name.split('_')[1]]
        blank = QIcon.ic('blank.png')

        def to_item(key, ac, parent):
            ic = ac.icon()
            if not ic or ic.isNull():
                ic = blank
            ans = QListWidgetItem(ic, str(ac.text()).replace('&', ''), parent)
            ans.setData(Qt.ItemDataRole.UserRole, key)
            ans.setToolTip(ac.toolTip())
            return ans

        for key, ac in sorted(iteritems(all_items), key=lambda k_ac: str(k_ac[1].text())):
            if key not in applied:
                to_item(key, ac, self.available)
        if name == 'global_book_toolbar' and 'donate' not in applied:
            QListWidgetItem(QIcon.ic('donate.png'), _('Donate'), self.available).setData(Qt.ItemDataRole.UserRole, 'donate')

        QListWidgetItem(blank, '--- %s ---' % _('Separator'), self.available)
        for key in items:
            if key is None:
                QListWidgetItem(blank, '--- %s ---' % _('Separator'), self.current)
            else:
                if key == 'donate':
                    QListWidgetItem(QIcon.ic('donate.png'), _('Donate'), self.current).setData(Qt.ItemDataRole.UserRole, 'donate')
                else:
                    try:
                        ac = all_items[key]
                    except KeyError:
                        pass
                    else:
                        to_item(key, ac, self.current)

    def bar_changed(self):
        name = self.current_name
        self.toggle_visibility(bool(name))
        self.build_lists()

    def toggle_visibility(self, visible):
        for x in ('gb1', 'gb2', 'lb', 'rb'):
            getattr(self, x).setVisible(visible)

    def move(self, up=True):
        r = self.current.currentRow()
        v = self.current
        if r < 0 or (r < 1 and up) or (r > v.count() - 2 and not up):
            return
        try:
            s = self.current_settings[self.current_name]
        except KeyError:
            return
        item = v.takeItem(r)
        nr = r + (-1 if up else 1)
        v.insertItem(nr, item)
        v.setCurrentItem(item)
        s[r], s[nr] = s[nr], s[r]
        self.changed_signal.emit()

    def add_action(self):
        self._add_action(self.available.selectedItems())

    def add_single_action(self, item):
        self._add_action([item])

    def _add_action(self, items):
        try:
            s = self.current_settings[self.current_name]
        except KeyError:
            return
        names = [str(i.data(Qt.ItemDataRole.UserRole) or '') for i in items]
        if not names:
            return
        for n in names:
            s.append(n or None)
        self.build_lists()
        self.changed_signal.emit()

    def remove_action(self):
        self._remove_action(self.current.selectedItems())

    def remove_single_action(self, item):
        self._remove_action([item])

    def _remove_action(self, items):
        try:
            s = self.current_settings[self.current_name]
        except KeyError:
            return
        rows = sorted({self.current.row(i) for i in items}, reverse=True)
        if not rows:
            return
        for r in rows:
            s.pop(r)
        self.build_lists()
        self.changed_signal.emit()

    def restore_defaults(self):
        o = self.original_settings
        self.read_settings(tprefs.defaults)
        self.original_settings = o
        self.build_lists()
        self.toolbar_icon_size.setValue(tprefs.defaults['toolbar_icon_size'])
        self.changed_signal.emit()

    def commit(self):
        if self.toolbar_icon_size.value() != tprefs['toolbar_icon_size']:
            tprefs['toolbar_icon_size'] = self.toolbar_icon_size.value()
        if self.original_settings != self.current_settings:
            self.changed = True
            with tprefs:
                tprefs.update(self.current_settings)

# }}}


class TemplatesDialog(Dialog):  # {{{

    def __init__(self, parent=None):
        self.ignore_changes = False
        Dialog.__init__(self, _('Customize templates'), 'customize-templates', parent=parent)

    def setup_ui(self):
        from calibre.gui2.tweak_book.templates import DEFAULT_TEMPLATES
        from calibre.gui2.tweak_book.editor.text import TextEdit
        # Cannot use QFormLayout as it does not play nice with TextEdit on windows
        self.l = l = QVBoxLayout(self)

        self.syntaxes = s = QComboBox(self)
        s.addItems(sorted(DEFAULT_TEMPLATES))
        s.setCurrentIndex(s.findText('html'))
        h = QHBoxLayout()
        l.addLayout(h)
        la = QLabel(_('Choose the &type of template to edit:'))
        la.setBuddy(s)
        h.addWidget(la), h.addWidget(s), h.addStretch(10)
        s.currentIndexChanged.connect(self.show_template)

        self.helpl = la = QLabel(_(
            'The variables {0} and {1} will be replaced with the title and author of the book. {2}'
            ' is where the cursor will be positioned. If you want to include braces in your template,'
            ' for example for CSS rules, you have to escape them, like this: {3}').format(*('<code>%s</code>'%x for x in
                ['{TITLE}', '{AUTHOR}', '%CURSOR%', 'body {{ color: red }}'])))
        la.setWordWrap(True)
        l.addWidget(la)

        self.save_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(100)
        t.timeout.connect(self._save_syntax)

        self.editor = e = TextEdit(self)
        l.addWidget(e)
        e.textChanged.connect(self.save_syntax)

        self.show_template()

        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        self.rd = b = self.bb.addButton(QDialogButtonBox.StandardButton.RestoreDefaults)
        b.clicked.connect(self.restore_defaults)
        l.addWidget(self.bb)

    @property
    def current_syntax(self):
        return str(self.syntaxes.currentText())

    def show_template(self):
        from calibre.gui2.tweak_book.templates import raw_template_for
        syntax = self.current_syntax
        self.ignore_changes = True
        try:
            self.editor.load_text(raw_template_for(syntax), syntax=syntax)
        finally:
            self.ignore_changes = False

    def save_syntax(self):
        if self.ignore_changes:
            return
        self.save_timer.start()

    def _save_syntax(self):
        custom = tprefs['templates']
        custom[self.current_syntax] = str(self.editor.toPlainText())
        tprefs['templates'] = custom

    def restore_defaults(self):
        custom = tprefs['templates']
        custom.pop(self.current_syntax, None)
        tprefs['templates'] = custom
        self.show_template()
        self._save_syntax()
# }}}


class Preferences(QDialog):

    def __init__(self, gui, initial_panel=None):
        QDialog.__init__(self, gui)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.setWindowTitle(_('Preferences for Edit book'))
        self.setWindowIcon(QIcon.ic('config.png'))

        self.stacks = QStackedWidget(self)
        l.addWidget(self.stacks, 0, 1, 1, 1)

        self.categories_list = cl = QListWidget(self)
        cl.currentRowChanged.connect(self.stacks.setCurrentIndex)
        cl.clearPropertyFlags()
        cl.setViewMode(QListView.ViewMode.IconMode)
        cl.setFlow(QListView.Flow.TopToBottom)
        cl.setMovement(QListView.Movement.Static)
        cl.setWrapping(False)
        cl.setSpacing(15)
        if get_lang()[:2] not in ('zh', 'ja'):
            cl.setWordWrap(True)
        l.addWidget(cl, 0, 0, 1, 1)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.rdb = b = bb.addButton(_('Restore all &defaults'), QDialogButtonBox.ButtonRole.ResetRole)
        b.setToolTip(_('Restore defaults for all preferences'))
        b.clicked.connect(self.restore_all_defaults)
        self.rcdb = b = bb.addButton(_('Restore &current defaults'), QDialogButtonBox.ButtonRole.ResetRole)
        b.setToolTip(_('Restore defaults for currently displayed preferences'))
        b.clicked.connect(self.restore_current_defaults)
        self.rconfs = b = bb.addButton(_('Restore c&onfirmations'), QDialogButtonBox.ButtonRole.ResetRole)
        b.setToolTip(_('Restore all disabled confirmation prompts'))
        b.clicked.connect(self.restore_confirmations)

        l.addWidget(bb, 1, 0, 1, 2)

        self.resize(800, 600)
        geom = tprefs.get('preferences_geom', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

        self.keyboard_panel = ShortcutConfig(self)
        self.keyboard_panel.initialize(gui.keyboard)
        self.editor_panel = EditorSettings(self)
        self.integration_panel = IntegrationSettings(self)
        self.main_window_panel = MainWindowSettings(self)
        self.preview_panel = PreviewSettings(self)
        self.toolbars_panel = ToolbarSettings(self)

        for name, icon, panel in [
            (_('Main window'), 'page.png', 'main_window'),
            (_('Editor settings'), 'modified.png', 'editor'),
            (_('Preview settings'), 'viewer.png', 'preview'),
            (_('Keyboard shortcuts'), 'keyboard-prefs.png', 'keyboard'),
            (_('Toolbars'), 'wizard.png', 'toolbars'),
            (_('Integration with calibre'), 'lt.png', 'integration'),
        ]:
            i = QListWidgetItem(QIcon.ic(icon), name, cl)
            i.setToolTip(name)
            cl.addItem(i)
            self.stacks.addWidget(getattr(self, panel + '_panel'))

        cl.setCurrentRow(0)
        cl.item(0).setSelected(True)
        w, h = cl.sizeHintForColumn(0), 0
        for i in range(cl.count()):
            h = cl.sizeHintForRow(i)
            cl.item(i).setSizeHint(QSize(w, h))

        cl.setMaximumWidth(cl.sizeHintForColumn(0) + 35)
        cl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cl.setMinimumWidth(min(cl.maximumWidth(), cl.sizeHint().width()))

    @property
    def dictionaries_changed(self):
        return self.editor_panel.dictionaries_changed

    @property
    def snippets_changed(self):
        return self.editor_panel.snippets_changed

    @property
    def toolbars_changed(self):
        return self.toolbars_panel.changed

    def restore_all_defaults(self):
        for i in range(self.stacks.count()):
            w = self.stacks.widget(i)
            w.restore_defaults()

    def restore_current_defaults(self):
        self.stacks.currentWidget().restore_defaults()

    def restore_confirmations(self):
        changed = 0
        for key in tuple(tprefs):
            if key.endswith('_again') and tprefs.get(key) is False:
                del tprefs[key]
                changed += 1
            elif key.startswith('skip_ask_to_show_current_diff_for_'):
                del tprefs[key]
                changed += 1
            elif key == 'questions_to_auto_skip':
                changed += len(tprefs[key] or ())
                del tprefs[key]

        msg = _('There are no disabled confirmation prompts')
        if changed:
            msg = ngettext(
                'One disabled confirmation prompt was restored', '{} disabled confirmation prompts were restored', changed).format(changed)
        info_dialog(self, _('Disabled confirmations restored'), msg, show=True)

    def accept(self):
        tprefs.set('preferences_geom', bytearray(self.saveGeometry()))
        for i in range(self.stacks.count()):
            w = self.stacks.widget(i)
            w.commit()
        QDialog.accept(self)

    def reject(self):
        tprefs.set('preferences_geom', bytearray(self.saveGeometry()))
        QDialog.reject(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book.main import option_parser
    from calibre.gui2.tweak_book.ui import Main
    app = Application([])
    opts = option_parser().parse_args(['dev'])
    main = Main(opts)
    d = Preferences(main)
    d.exec()
