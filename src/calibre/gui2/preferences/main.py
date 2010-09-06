#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap
from functools import partial

from PyQt4.Qt import QMainWindow, Qt, QIcon, QStatusBar, QFont, QWidget, \
        QScrollArea, QStackedWidget, QVBoxLayout, QLabel, QFrame, \
        QToolBar, QSize, pyqtSignal, QSizePolicy, QToolButton

from calibre.constants import __appname__, __version__
from calibre.gui2 import gprefs, min_available_height, available_width, \
    warning_dialog
from calibre.gui2.preferences import init_gui, AbortCommit, get_plugin
from calibre.customize.ui import preferences_plugins
from calibre.utils.ordered_dict import OrderedDict

class StatusBar(QStatusBar): # {{{

    def __init__(self, parent=None):
        QStatusBar.__init__(self, parent)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                __version__ + ' ' + _('created by Kovid Goyal')
        self.device_string = ''
        self._font = QFont()
        self._font.setBold(True)
        self.setFont(self._font)

        self.messageChanged.connect(self.message_changed,
                type=Qt.QueuedConnection)
        self.message_changed('')

    def message_changed(self, msg):
        if not msg or msg.isEmpty() or msg.isNull() or \
                not unicode(msg).strip():
            self.showMessage(self.default_message)

# }}}

class Category(QWidget):

    plugin_activated = pyqtSignal(object)

    def __init__(self, name, plugins, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.label = QLabel(name)
        self.sep = QFrame(self)
        self.bf = QFont()
        self.bf.setBold(True)
        self.label.setFont(self.bf)
        self.sep.setFrameShape(QFrame.HLine)
        self._layout.addWidget(self.label)
        self._layout.addWidget(self.sep)

        self.plugins = plugins

        self.bar = QToolBar(self)
        self.bar.setIconSize(QSize(48, 48))
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
            w.setStyleSheet('QToolButton { margin-right: 20px; min-width: 100px }')
            w.setCursor(Qt.PointingHandCursor)
            w.setAutoRaise(True)

    def triggered(self, plugin, *args):
        self.plugin_activated.emit(plugin)


class Browser(QScrollArea):

    show_plugin = pyqtSignal(object)

    def __init__(self, parent=None):
        QScrollArea.__init__(self, parent)
        self.setWidgetResizable(True)

        category_map = {}
        for plugin in preferences_plugins():
            if plugin.category not in category_map:
                category_map[plugin.category] = plugin.category_order
            if category_map[plugin.category] < plugin.category_order:
                category_map[plugin.category] = plugin.category_order

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
            w = Category(name, plugins, self)
            self.widgets.append(w)
            self._layout.addWidget(w)
            w.plugin_activated.connect(self.show_plugin.emit)



class Preferences(QMainWindow):

    def __init__(self, gui, initial_plugin=None):
        QMainWindow.__init__(self, gui)
        self.gui = gui
        self.must_restart = False
        self.committed = False

        self.resize(900, 700)
        nh, nw = min_available_height()-25, available_width()-10
        if nh < 0:
            nh = 800
        if nw < 0:
            nw = 600
        nh = min(self.height(), nh)
        nw = min(self.width(), nw)
        self.resize(nw, nh)

        geom = gprefs.get('preferences_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)

        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.setWindowIcon(QIcon(I('config.png')))

        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)
        self.browser = Browser(self)
        self.browser.show_plugin.connect(self.show_plugin)
        self.stack.addWidget(self.browser)
        self.scroll_area = QScrollArea(self)
        self.stack.addWidget(self.scroll_area)
        self.scroll_area.setWidgetResizable(True)

        self.bar = QToolBar(self)
        self.addToolBar(self.bar)
        self.bar.setVisible(False)
        self.bar.setIconSize(QSize(32, 32))
        self.bar.setMovable(False)
        self.bar.setFloatable(False)
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.apply_action = self.bar.addAction(QIcon(I('ok.png')), _('&Apply'),
                self.commit)
        self.cancel_action = self.bar.addAction(QIcon(I('window-close.png')),
                _('&Cancel'),                self.cancel)
        self.bar_filler = QLabel('')
        self.bar_filler.setSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Preferred)
        self.bar_filler.setStyleSheet(
            'QLabel { font-weight: bold }')
        self.bar_filler.setAlignment(Qt.AlignHCenter | Qt.AlignCenter)
        self.bar.addWidget(self.bar_filler)
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


    def show_plugin(self, plugin):
        self.showing_widget = plugin.create_widget(self.scroll_area)
        self.showing_widget.genesis(self.gui)
        self.showing_widget.initialize()
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
        self.bar_filler.setText(plugin.gui_name)
        self.setWindowIcon(QIcon(plugin.icon))
        self.bar.setVisible(True)


    def hide_plugin(self):
        self.showing_widget = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.showing_widget)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.bar.setVisible(False)
        self.stack.setCurrentIndex(0)
        self.setWindowIcon(QIcon(I('config.png')))

    def commit(self, *args):
        try:
            must_restart = self.showing_widget.commit()
        except AbortCommit:
            return
        self.committed = True
        if must_restart:
            self.must_restart = True
            warning_dialog(self, _('Restart needed'),
                    _('Some of the changes you made require a restart.'
                        ' Please restart calibre as soon as possible.'),
                    show=True)
        self.showing_widget.refresh_gui(self.gui)
        self.hide_plugin()


    def cancel(self, *args):
        self.hide_plugin()

    def restore_defaults(self, *args):
        self.showing_widget.restore_defaults()

    def closeEvent(self, *args):
        gprefs.set('preferences_window_geometry',
                bytearray(self.saveGeometry()))
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
