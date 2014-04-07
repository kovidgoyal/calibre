#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from operator import attrgetter, methodcaller
from collections import namedtuple
from future_builtins import map
from itertools import product

from PyQt4.Qt import (
    QDialog, QGridLayout, QStackedWidget, QDialogButtonBox, QListWidget,
    QListWidgetItem, QIcon, QWidget, QSize, QFormLayout, Qt, QSpinBox,
    QCheckBox, pyqtSignal, QDoubleSpinBox, QComboBox, QLabel, QFont,
    QFontComboBox, QPushButton, QSizePolicy)

from calibre.gui2.keyboard import ShortcutConfig
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.editor.themes import default_theme, THEMES
from calibre.gui2.tweak_book.spell import ManageDictionaries
from calibre.gui2.font_family_chooser import FontFamilyChooser

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
            elif isinstance(defval, (int, float)):
                widget = (QSpinBox if isinstance(defval, int) else QDoubleSpinBox)(self)
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
        widget.currentIndexChanged[int].connect(self.emit_changed)
        for key, human in choices.iteritems():
            widget.addItem(human or key, key)

        def getter(w):
            ans = unicode(w.itemData(w.currentIndex()).toString())
            return {none_val:None}.get(ans, ans)

        def setter(w, val):
            val = {None:none_val}.get(val, val)
            idx = w.findData(val, flags=Qt.MatchFixedString|Qt.MatchCaseSensitive)
            if idx == -1:
                idx = w.findData(fallback_val, flags=Qt.MatchFixedString|Qt.MatchCaseSensitive)
            w.setCurrentIndex(idx)

        return self(name, widget=widget, getter=getter, setter=setter, prefs=prefs)

    def order_widget(self, name, prefs=None):
        prefs = prefs or tprefs
        widget = QListWidget(self)
        widget.addItems(prefs.defaults[name])
        widget.setDragEnabled(True)
        widget.setDragDropMode(widget.InternalMove)
        widget.viewport().setAcceptDrops(True)
        widget.setDropIndicatorShown(True)
        widget.indexesMoved.connect(self.emit_changed)
        widget.setDefaultDropAction(Qt.MoveAction)
        widget.setMovement(widget.Snap)
        widget.setSpacing(5)
        widget.defaults = prefs.defaults[name]

        def getter(w):
            return list(map(unicode, (w.item(i).text() for i in xrange(w.count()))))

        def setter(w, val):
            order_map = {x:i for i, x in enumerate(val)}
            items = list(w.defaults)
            limit = len(items)
            items.sort(key=lambda x:order_map.get(x, limit))
            w.clear()
            for x in items:
                i = QListWidgetItem(w)
                i.setText(x)
                i.setFlags(i.flags() | Qt.ItemIsDragEnabled)

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
        for setting in self.settings.itervalues():
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

class EditorSettings(BasicSettings):

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.dictionaries_changed = False
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        fc = FontFamilyChooser(self)
        self('editor_font_family', widget=fc, getter=attrgetter('font_family'), setter=lambda x, val: setattr(x, 'font_family', val))
        fc.family_changed.connect(self.emit_changed)
        l.addRow(_('Editor font &family:'), fc)

        fs = self('editor_font_size')
        fs.setMinimum(8), fs.setSuffix(' pt'), fs.setMaximum(50)
        l.addRow(_('Editor font &size:'), fs)

        auto_theme = _('Automatic (%s)') % default_theme()
        choices = {k:k for k in THEMES}
        choices['auto'] = auto_theme
        theme = self.choices_widget('editor_theme', choices, 'auto', 'auto')
        l.addRow(_('&Color scheme:'), theme)

        tw = self('editor_tab_stop_width')
        tw.setMinimum(2), tw.setSuffix(_(' characters')), tw.setMaximum(20)
        l.addRow(_('Width of &tabs:'), tw)

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

        lw = self('editor_show_char_under_cursor')
        lw.setText(_('Show the name of the current character before the cursor along with the line and column number'))
        l.addRow(lw)

        lw = self('pretty_print_on_open')
        lw.setText(_('Beautify individual files automatically when they are opened'))
        lw.setToolTip('<p>' + _(
            'This will cause the beautify current file action to be performed automatically every'
            ' time you open a HTML/CSS/etc. file for editing.'))
        l.addRow(lw)

        self.dictionaries = d = QPushButton(_('Manage &spelling dictionaries'), self)
        d.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        d.clicked.connect(self.manage_dictionaries)
        l.addRow(d)

    def manage_dictionaries(self):
        d = ManageDictionaries(self)
        d.exec_()
        self.dictionaries_changed = True

class IntegrationSettings(BasicSettings):

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        um = self('update_metadata_from_calibre')
        um.setText(_('Update metadata embedded in the book when opening'))
        um.setToolTip('<p>' + _(
            'When the file is opened, update the metadata embedded in the book file to the current metadata'
            ' in the calibre library.'))
        l.addRow(um)

        ask = self('choose_tweak_fmt')
        ask.setText(_('Ask which format to edit if more than one format is available for the book'))
        l.addRow(ask)

        order = self.order_widget('tweak_fmt_order')
        order.setToolTip(_('When auto-selecting the format to edit for a book with'
                           ' multiple formats, this is the preference order.'))
        l.addRow(_('Preferred format order (drag and drop to change)'), order)

class MainWindowSettings(BasicSettings):

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        nd = self('nestable_dock_widgets')
        nd.setText(_('Allow dockable windows to be nested inside the dock areas'))
        nd.setToolTip('<p>' + _(
            'By default, you can have only a single row or column of windows in the dock'
            ' areas (the areas around the central editors). This option allows'
            ' for more flexible window layout, but is a little more complex to use.'))
        l.addRow(nd)

        l.addRow(QLabel(_('Choose which windows will occupy the corners of the dockable areas')))
        for v, h in product(('top', 'bottom'), ('left', 'right')):
            choices = {'vertical':{'left':_('Left'), 'right':_('Right')}[h],
                       'horizontal':{'top':_('Top'), 'bottom':_('Bottom')}[v]}
            name = 'dock_%s_%s' % (v, h)
            w = self.choices_widget(name, choices, 'horizontal', 'horizontal')
            cn = {('top', 'left'): _('The top-left corner'), ('top', 'right'):_('The top-right corner'),
                  ('bottom', 'left'):_('The bottom-left corner'), ('bottom', 'right'):_('The bottom-right corner')}[(v, h)]
            l.addRow(cn + ':', w)

class PreviewSettings(BasicSettings):

    def __init__(self, parent=None):
        BasicSettings.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        def family_getter(w):
            return unicode(w.currentFont().family())

        def family_setter(w, val):
            w.setCurrentFont(QFont(val))

        families = {'serif':_('Serif text'), 'sans':_('Sans-serif text'), 'mono':_('Monospaced text')}
        for fam, text in families.iteritems():
            w = QFontComboBox(self)
            self('preview_%s_family' % fam, widget=w, getter=family_getter, setter=family_setter)
            l.addRow(_('Font family for &%s:') % text, w)

        w = self.choices_widget('preview_standard_font_family', families, 'serif', 'serif')
        l.addRow(_('&Style for standard text:'), w)

        w = self('preview_base_font_size')
        w.setMinimum(8), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('&Default font size:'), w)
        w = self('preview_mono_font_size')
        w.setMinimum(8), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('&Monospace font size:'), w)
        w = self('preview_minimum_font_size')
        w.setMinimum(4), w.setMaximum(100), w.setSuffix(' px')
        l.addRow(_('Mi&nimum font size:'), w)

class Preferences(QDialog):

    def __init__(self, gui, initial_panel=None):
        QDialog.__init__(self, gui)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.setWindowTitle(_('Preferences for Edit Book'))
        self.setWindowIcon(QIcon(I('config.png')))

        self.stacks = QStackedWidget(self)
        l.addWidget(self.stacks, 0, 1, 1, 1)

        self.categories_list = cl = QListWidget(self)
        cl.currentRowChanged.connect(self.stacks.setCurrentIndex)
        cl.clearPropertyFlags()
        cl.setViewMode(cl.IconMode)
        cl.setFlow(cl.TopToBottom)
        cl.setMovement(cl.Static)
        cl.setWrapping(False)
        cl.setSpacing(15)
        cl.setWordWrap(True)
        l.addWidget(cl, 0, 0, 1, 1)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.rdb = b = bb.addButton(_('Restore all defaults'), bb.ResetRole)
        b.setToolTip(_('Restore defaults for all preferences'))
        b.clicked.connect(self.restore_all_defaults)
        self.rcdb = b = bb.addButton(_('Restore current defaults'), bb.ResetRole)
        b.setToolTip(_('Restore defaults for currently displayed preferences'))
        b.clicked.connect(self.restore_current_defaults)
        l.addWidget(bb, 1, 0, 1, 2)

        self.resize(800, 600)
        geom = tprefs.get('preferences_geom', None)
        if geom is not None:
            self.restoreGeometry(geom)

        self.keyboard_panel = ShortcutConfig(self)
        self.keyboard_panel.initialize(gui.keyboard)
        self.editor_panel = EditorSettings(self)
        self.integration_panel = IntegrationSettings(self)
        self.main_window_panel = MainWindowSettings(self)
        self.preview_panel = PreviewSettings(self)

        for name, icon, panel in [
            (_('Main window'), 'page.png', 'main_window'),
            (_('Editor settings'), 'modified.png', 'editor'),
            (_('Preview settings'), 'viewer.png', 'preview'),
            (_('Keyboard shortcuts'), 'keyboard-prefs.png', 'keyboard'),
            (_('Integration with calibre'), 'lt.png', 'integration'),
        ]:
            i = QListWidgetItem(QIcon(I(icon)), name, cl)
            cl.addItem(i)
            self.stacks.addWidget(getattr(self, panel + '_panel'))

        cl.setCurrentRow(0)
        cl.item(0).setSelected(True)
        w, h = cl.sizeHintForColumn(0), 0
        for i in xrange(cl.count()):
            h = max(h, cl.sizeHintForRow(i))
            cl.item(i).setSizeHint(QSize(w, h))

        cl.setMaximumWidth(cl.sizeHintForColumn(0) + 35)
        cl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    @property
    def dictionaries_changed(self):
        return self.editor_panel.dictionaries_changed

    def restore_all_defaults(self):
        for i in xrange(self.stacks.count()):
            w = self.stacks.widget(i)
            w.restore_defaults()

    def restore_current_defaults(self):
        self.stacks.currentWidget().restore_defaults()

    def accept(self):
        tprefs.set('preferences_geom', bytearray(self.saveGeometry()))
        for i in xrange(self.stacks.count()):
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
    d.exec_()

