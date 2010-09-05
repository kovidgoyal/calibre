#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QMainWindow, Qt, QIcon, QStatusBar, QFont, QWidget, \
        QScrollArea, QStackedWidget, QVBoxLayout, QLabel, QFrame, \
        QToolBar, QSize, pyqtSignal

from calibre.constants import __appname__, __version__
from calibre.gui2 import gprefs
from calibre.gui2.preferences import init_gui
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
            ac.setToolTip(p.description)
            ac.setWhatsThis(p.description)
            ac.setStatusTip(p.description)
            self.actions.append(ac)
            w = self.bar.widgetForAction(ac)
            w.setStyleSheet('QToolButton { margin-right: 20px; min-width: 100px }')
            w.setCursor(Qt.PointingHandCursor)

    def triggered(self, plugin, *args):
        self.plugin_activated.emit(plugin)


class Browser(QScrollArea):

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



class Preferences(QMainWindow):

    def __init__(self, gui):
        QMainWindow.__init__(self, gui)

        self.resize(780, 665)
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
        self.stack.addWidget(self.browser)
        self.scroll_area = QScrollArea(self)
        self.stack.addWidget(self.scroll_area)
        self.scroll_area.setWidgetResizable(True)

        self.stack.setCurrentIndex(0)

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
