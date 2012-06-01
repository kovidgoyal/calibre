#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap
from functools import partial
from collections import OrderedDict

from PyQt4.Qt import QMainWindow, Qt, QIcon, QStatusBar, QFont, QWidget, \
        QScrollArea, QStackedWidget, QVBoxLayout, QLabel, QFrame, QKeySequence, \
        QToolBar, QSize, pyqtSignal, QPixmap, QToolButton, QAction, \
        QDialogButtonBox, QHBoxLayout

from calibre.constants import __appname__, __version__, islinux
from calibre.gui2 import gprefs, min_available_height, available_width, \
    warning_dialog
from calibre.gui2.preferences import init_gui, AbortCommit, get_plugin
from calibre.customize.ui import preferences_plugins

ICON_SIZE = 32

class StatusBar(QStatusBar): # {{{

    def __init__(self, parent=None):
        QStatusBar.__init__(self, parent)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                __version__ + ' ' + _('created by Kovid Goyal')
        self.device_string = ''
        self._font = QFont()
        self._font.setBold(True)
        self.setFont(self._font)

        self.w = QLabel(self.default_message)
        self.w.setFont(self._font)
        self.addWidget(self.w)

# }}}

class BarTitle(QWidget): # {{{

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.addStretch(10)
        self.icon = QLabel('')
        self._layout.addWidget(self.icon)
        self.title = QLabel('')
        self.title.setStyleSheet('QLabel { font-weight: bold }')
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
        self._layout.addWidget(self.title)
        self._layout.addStretch(10)

    def show_plugin(self, plugin):
        self.pmap = QPixmap(plugin.icon).scaled(ICON_SIZE, ICON_SIZE,
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon.setPixmap(self.pmap)
        self.title.setText(plugin.gui_name)
        tt = plugin.description
        self.setStatusTip(tt)
        tt = textwrap.fill(tt)
        self.setToolTip(tt)
        self.setWhatsThis(tt)

# }}}

class Category(QWidget): # {{{

    plugin_activated = pyqtSignal(object)

    def __init__(self, name, plugins, gui_name, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.label = QLabel(gui_name)
        self.sep = QFrame(self)
        self.bf = QFont()
        self.bf.setBold(True)
        self.label.setFont(self.bf)
        self.sep.setFrameShape(QFrame.HLine)
        self._layout.addWidget(self.label)
        self._layout.addWidget(self.sep)

        self.plugins = plugins

        self.bar = QToolBar(self)
        self.bar.setStyleSheet(
                'QToolBar { border: none; background: none }')
        self.bar.setIconSize(QSize(32, 32))
        self.bar.setMovable(False)
        self.bar.setFloatable(False)
        self.bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self._layout.addWidget(self.bar)
        self.actions = []
        for p in plugins:
            target = partial(self.triggered, p)
            ac = self.bar.addAction(QIcon(p.icon), p.gui_name, target)
            ac.setToolTip(textwrap.fill(p.description))
            ac.setWhatsThis(textwrap.fill(p.description))
            ac.setStatusTip(p.description)
            self.actions.append(ac)
            w = self.bar.widgetForAction(ac)
            w.setCursor(Qt.PointingHandCursor)
            w.setAutoRaise(True)
            w.setMinimumWidth(100)

    def triggered(self, plugin, *args):
        self.plugin_activated.emit(plugin)

# }}}

class Browser(QScrollArea): # {{{

    show_plugin = pyqtSignal(object)

    def __init__(self, parent=None):
        QScrollArea.__init__(self, parent)
        self.setWidgetResizable(True)

        category_map, category_names = {}, {}
        for plugin in preferences_plugins():
            if plugin.category not in category_map:
                category_map[plugin.category] = plugin.category_order
            if category_map[plugin.category] < plugin.category_order:
                category_map[plugin.category] = plugin.category_order
            if plugin.category not in category_names:
                category_names[plugin.category] = (plugin.gui_category if
                    plugin.gui_category else plugin.category)

        self.category_names = category_names

        categories = list(category_map.keys())
        categories.sort(cmp=lambda x, y: cmp(category_map[x], category_map[y]))

        self.category_map = OrderedDict()
        for c in categories:
            self.category_map[c] = []

        for plugin in preferences_plugins():
            self.category_map[plugin.category].append(plugin)

        for plugins in self.category_map.values():
            plugins.sort(cmp=lambda x, y: cmp(x.name_order, y.name_order))

        self.widgets = []
        self._layout = QVBoxLayout()
        self.container = QWidget(self)
        self.container.setLayout(self._layout)
        self.setWidget(self.container)

        for name, plugins in self.category_map.items():
            w = Category(name, plugins, self.category_names[name], parent=self)
            self.widgets.append(w)
            self._layout.addWidget(w)
            w.plugin_activated.connect(self.show_plugin.emit)


# }}}

class Preferences(QMainWindow):

    run_wizard_requested = pyqtSignal()

    def __init__(self, gui, initial_plugin=None, close_after_initial=False):
        QMainWindow.__init__(self, gui)
        self.gui = gui
        self.must_restart = False
        self.committed = False
        self.close_after_initial = close_after_initial

        self.resize(930, 720)
        nh, nw = min_available_height()-25, available_width()-10
        if nh < 0:
            nh = 800
        if nw < 0:
            nw = 600
        nh = min(self.height(), nh)
        nw = min(self.width(), nw)
        self.resize(nw, nh)
        self.esc_action = QAction(self)
        self.addAction(self.esc_action)
        self.esc_action.setShortcut(QKeySequence(Qt.Key_Escape))
        self.esc_action.triggered.connect(self.esc)

        geom = gprefs.get('preferences_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)

        # Center
        if islinux:
            self.move(gui.rect().center() - self.rect().center())

        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.setWindowIcon(QIcon(I('config.png')))

        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        self.stack = QStackedWidget(self)
        self.cw = QWidget(self)
        self.cw.setLayout(QVBoxLayout())
        self.cw.layout().addWidget(self.stack)
        self.bb = QDialogButtonBox(QDialogButtonBox.Close)
        self.wizard_button = self.bb.addButton(_('Run welcome wizard'),
                self.bb.DestructiveRole)
        self.wizard_button.setIcon(QIcon(I('wizard.png')))
        self.wizard_button.clicked.connect(self.run_wizard,
                type=Qt.QueuedConnection)
        self.bb.button(self.bb.Close).setDefault(True)
        self.cw.layout().addWidget(self.bb)
        self.bb.rejected.connect(self.close, type=Qt.QueuedConnection)
        self.setCentralWidget(self.cw)
        self.browser = Browser(self)
        self.browser.show_plugin.connect(self.show_plugin)
        self.stack.addWidget(self.browser)
        self.scroll_area = QScrollArea(self)
        self.stack.addWidget(self.scroll_area)
        self.scroll_area.setWidgetResizable(True)

        self.bar = QToolBar(self)
        self.addToolBar(self.bar)
        self.bar.setVisible(False)
        self.bar.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.bar.setMovable(False)
        self.bar.setFloatable(False)
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.apply_action = self.bar.addAction(QIcon(I('ok.png')), _('&Apply'),
                self.commit)
        self.cancel_action = self.bar.addAction(QIcon(I('window-close.png')),
                _('&Cancel'),                self.cancel)
        self.bar_title = BarTitle(self.bar)
        self.bar.addWidget(self.bar_title)
        self.restore_action = self.bar.addAction(QIcon(I('clear_left.png')),
                _('Restore &defaults'), self.restore_defaults)
        for ac, tt in [('apply', _('Save changes')),
                ('cancel', _('Cancel and return to overview'))]:
            ac = getattr(self, ac+'_action')
            ac.setToolTip(tt)
            ac.setWhatsThis(tt)
            ac.setStatusTip(tt)

        for ch in self.bar.children():
            if isinstance(ch, QToolButton):
                ch.setCursor(Qt.PointingHandCursor)
                ch.setAutoRaise(True)

        self.stack.setCurrentIndex(0)

        if initial_plugin is not None:
            category, name = initial_plugin
            plugin = get_plugin(category, name)
            if plugin is not None:
                self.show_plugin(plugin)

    def run_wizard(self):
        self.close()
        self.run_wizard_requested.emit()

    def set_tooltips_for_labels(self):

        def process_child(child):
            for g in child.children():
                if isinstance(g, QLabel):
                    buddy = g.buddy()
                    if buddy is not None and hasattr(buddy, 'toolTip'):
                        htext = unicode(buddy.toolTip()).strip()
                        etext = unicode(g.toolTip()).strip()
                        if htext and not etext:
                            g.setToolTip(htext)
                            g.setWhatsThis(htext)
                else:
                    process_child(g)

        process_child(self.showing_widget)

    def show_plugin(self, plugin):
        self.showing_widget = plugin.create_widget(self.scroll_area)
        self.showing_widget.genesis(self.gui)
        self.showing_widget.initialize()
        self.set_tooltips_for_labels()
        self.scroll_area.setWidget(self.showing_widget)
        self.stack.setCurrentIndex(1)
        self.showing_widget.show()
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences') + ' - ' +
                plugin.gui_name)
        self.apply_action.setEnabled(False)
        self.showing_widget.changed_signal.connect(lambda :
                self.apply_action.setEnabled(True))
        self.restore_action.setEnabled(self.showing_widget.supports_restoring_to_defaults)
        tt = self.showing_widget.restore_defaults_desc
        if not self.restore_action.isEnabled():
            tt = _('Restoring to defaults not supported for') + ' ' + \
                plugin.gui_name
        self.restore_action.setToolTip(textwrap.fill(tt))
        self.restore_action.setWhatsThis(textwrap.fill(tt))
        self.restore_action.setStatusTip(tt)
        self.bar_title.show_plugin(plugin)
        self.setWindowIcon(QIcon(plugin.icon))
        self.bar.setVisible(True)
        self.bb.setVisible(False)


    def hide_plugin(self):
        self.showing_widget = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.showing_widget)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.bar.setVisible(False)
        self.stack.setCurrentIndex(0)
        self.setWindowIcon(QIcon(I('config.png')))
        self.bb.setVisible(True)

    def esc(self, *args):
        if self.stack.currentIndex() == 1:
            self.cancel()
        elif self.stack.currentIndex() == 0:
            self.close()

    def commit(self, *args):
        try:
            must_restart = self.showing_widget.commit()
        except AbortCommit:
            return
        rc = self.showing_widget.restart_critical
        self.committed = True
        do_restart = False
        if must_restart:
            self.must_restart = True
            msg = _('Some of the changes you made require a restart.'
                    ' Please restart calibre as soon as possible.')
            if rc:
                msg = _('The changes you have made require calibre be '
                        'restarted immediately. You will not be allowed to '
                        'set any more preferences, until you restart.')


            d = warning_dialog(self, _('Restart needed'), msg,
                    show_copy_button=False)
            b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
            b.setIcon(QIcon(I('lt.png')))
            d.do_restart = False
            def rf():
                d.do_restart = True
            b.clicked.connect(rf)
            d.set_details('')
            d.exec_()
            b.clicked.disconnect()
            do_restart = d.do_restart
        self.showing_widget.refresh_gui(self.gui)
        self.hide_plugin()
        if self.close_after_initial or (must_restart and rc) or do_restart:
            self.close()
        if do_restart:
            self.gui.quit(restart=True)


    def cancel(self, *args):
        if self.close_after_initial:
            self.close()
        else:
            self.hide_plugin()

    def restore_defaults(self, *args):
        self.showing_widget.restore_defaults()

    def closeEvent(self, *args):
        gprefs.set('preferences_window_geometry',
                bytearray(self.saveGeometry()))
        if self.committed:
            self.gui.must_restart_before_config = self.must_restart
            self.gui.tags_view.recount()
            self.gui.create_device_menu()
            self.gui.set_device_menu_items_state(bool(self.gui.device_connected))
            self.gui.bars_manager.apply_settings()
            self.gui.bars_manager.update_bars()
            self.gui.build_context_menus()

        return QMainWindow.closeEvent(self, *args)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    app
    gui = init_gui()

    p = Preferences(gui)
    p.show()
    app.exec_()
    gui.shutdown()
