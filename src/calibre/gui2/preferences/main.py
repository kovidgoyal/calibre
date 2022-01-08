#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
import textwrap
from collections import OrderedDict
from functools import partial
from qt.core import (
    QApplication, QDialog, QDialogButtonBox, QFont, QFrame, QHBoxLayout, QIcon,
    QLabel, QPainter, QPointF, QPushButton, QScrollArea, QSize, QSizePolicy,
    QStackedWidget, QStatusTipEvent, Qt, QTabWidget, QTextLayout, QToolBar,
    QVBoxLayout, QWidget, pyqtSignal
)

from calibre.constants import __appname__, __version__, islinux
from calibre.customize.ui import preferences_plugins
from calibre.gui2 import (
    available_width, gprefs, min_available_height, show_restart_warning
)
from calibre.gui2.dialogs.message_box import Icon
from calibre.gui2.preferences import (
    AbortCommit, AbortInitialize, get_plugin, init_gui
)

ICON_SIZE = 32

# Title Bar {{{


class Message(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.layout = QTextLayout()
        self.layout.setFont(self.font())
        self.layout.setCacheEnabled(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.last_layout_rect = None

    def setText(self, text):
        self.layout.setText(text)
        self.last_layout_rect = None
        self.update()

    def sizeHint(self):
        return QSize(10, 10)

    def do_layout(self):
        ly = self.layout
        ly.beginLayout()
        w = self.width() - 5
        height = 0
        leading = self.fontMetrics().leading()
        while True:
            line = ly.createLine()
            if not line.isValid():
                break
            line.setLineWidth(w)
            height += leading
            line.setPosition(QPointF(5, height))
            height += line.height()
        ly.endLayout()

    def paintEvent(self, ev):
        if self.last_layout_rect != self.rect():
            self.do_layout()
        p = QPainter(self)
        br = self.layout.boundingRect()
        y = 0
        if br.height() < self.height():
            y = (self.height() - br.height()) / 2
        self.layout.draw(p, QPointF(0, y))


class TitleBar(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.icon = Icon(self, size=ICON_SIZE)
        l.addWidget(self.icon)
        self.title = QLabel('')
        self.title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        l.addWidget(self.title)
        l.addStrut(25)
        self.msg = la = Message(self)
        l.addWidget(la)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                __version__ + ' ' + _('created by Kovid Goyal')
        self.show_plugin()
        self.show_msg()

    def show_plugin(self, plugin=None):
        self.icon.set_icon(QIcon.ic('lt.png' if plugin is None else plugin.icon))
        self.title.setText('<h1>' + (_('Preferences') if plugin is None else plugin.gui_name))

    def show_msg(self, msg=None):
        msg = msg or self.default_message
        self.msg.setText(' '.join(msg.splitlines()).strip())

# }}}


class Category(QWidget):  # {{{

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
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self._layout.addWidget(self.label)
        self._layout.addWidget(self.sep)

        self.plugins = plugins

        self.bar = QToolBar(self)
        self.bar.setStyleSheet(
                'QToolBar { border: none; background: none }')
        lh = QApplication.instance().line_height
        self.bar.setIconSize(QSize(2*lh, 2*lh))
        self.bar.setMovable(False)
        self.bar.setFloatable(False)
        self.bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._layout.addWidget(self.bar)
        self.actions = []
        for p in plugins:
            target = partial(self.triggered, p)
            ac = self.bar.addAction(QIcon.ic(p.icon), p.gui_name.replace('&', '&&'), target)
            ac.setToolTip(textwrap.fill(p.description))
            ac.setWhatsThis(textwrap.fill(p.description))
            ac.setStatusTip(p.description)
            self.actions.append(ac)
            w = self.bar.widgetForAction(ac)
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            if hasattr(w, 'setAutoRaise'):
                w.setAutoRaise(True)
            w.setMinimumWidth(100)

    def triggered(self, plugin, *args):
        self.plugin_activated.emit(plugin)

# }}}


class Browser(QScrollArea):  # {{{

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
        categories.sort(key=lambda x: category_map[x])

        self.category_map = OrderedDict()
        for c in categories:
            self.category_map[c] = []

        for plugin in preferences_plugins():
            self.category_map[plugin.category].append(plugin)

        for plugins in self.category_map.values():
            plugins.sort(key=lambda x: x.name_order)

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
        self._layout.addStretch(1)


# }}}

class Preferences(QDialog):

    run_wizard_requested = pyqtSignal()

    def __init__(self, gui, initial_plugin=None, close_after_initial=False):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.must_restart = False
        self.do_restart = False
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

        geom = gprefs.get('preferences dialog geometry', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

        # Center
        if islinux:
            self.move(gui.rect().center() - self.rect().center())

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(__appname__ + ' — ' + _('Preferences'))
        self.setWindowIcon(QIcon.ic('config.png'))
        self.l = l = QVBoxLayout(self)

        self.stack = QStackedWidget(self)
        self.bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close | QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.accept)
        self.wizard_button = QPushButton(QIcon.ic('wizard.png'), _('Run Welcome &wizard'))
        self.wizard_button.clicked.connect(self.run_wizard, type=Qt.ConnectionType.QueuedConnection)
        self.wizard_button.setAutoDefault(False)
        self.restore_defaults_button = rdb = QPushButton(QIcon.ic('clear_left.png'), _('Restore &defaults'))
        rdb.clicked.connect(self.restore_defaults, type=Qt.ConnectionType.QueuedConnection)
        rdb.setAutoDefault(False)
        rdb.setVisible(False)
        self.bb.rejected.connect(self.reject)
        self.browser = Browser(self)
        self.browser.show_plugin.connect(self.show_plugin)
        self.stack.addWidget(self.browser)
        self.scroll_area = QScrollArea(self)
        self.stack.addWidget(self.scroll_area)
        self.scroll_area.setWidgetResizable(True)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.title_bar = TitleBar(self)
        for ac, tt in [(QDialogButtonBox.StandardButton.Apply, _('Save changes')),
                (QDialogButtonBox.StandardButton.Cancel, _('Cancel and return to overview'))]:
            self.bb.button(ac).setToolTip(tt)

        l.addWidget(self.title_bar), l.addWidget(self.stack)
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.wizard_button), h.addWidget(self.restore_defaults_button), h.addStretch(10), h.addWidget(self.bb)

        if initial_plugin is not None:
            category, name = initial_plugin[:2]
            plugin = get_plugin(category, name)
            if plugin is not None:
                self.show_plugin(plugin)
                if len(initial_plugin) > 2:
                    w = self.findChild(QWidget, initial_plugin[2])
                    if w is not None:
                        for c in self.showing_widget.children():
                            if isinstance(c, QTabWidget):
                                idx = c.indexOf(w)
                                if idx > -1:
                                    c.setCurrentIndex(idx)
                                    break
        else:
            self.hide_plugin()

    def event(self, ev):
        if isinstance(ev, QStatusTipEvent):
            msg = re.sub(r'</?[a-z1-6]+>', ' ', ev.tip())
            self.title_bar.show_msg(msg)
        return QDialog.event(self, ev)

    def run_wizard(self):
        self.run_wizard_requested.emit()
        self.accept()

    def set_tooltips_for_labels(self):

        def process_child(child):
            for g in child.children():
                if isinstance(g, QLabel):
                    buddy = g.buddy()
                    if buddy is not None and hasattr(buddy, 'toolTip'):
                        htext = str(buddy.toolTip()).strip()
                        etext = str(g.toolTip()).strip()
                        if htext and not etext:
                            g.setToolTip(htext)
                            g.setWhatsThis(htext)
                else:
                    process_child(g)

        process_child(self.showing_widget)

    def show_plugin(self, plugin):
        self.showing_widget = plugin.create_widget(self.scroll_area)
        self.showing_widget.genesis(self.gui)
        try:
            self.showing_widget.initialize()
        except AbortInitialize:
            return
        self.set_tooltips_for_labels()
        self.scroll_area.setWidget(self.showing_widget)
        self.stack.setCurrentIndex(1)
        self.showing_widget.show()
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences') + ' - ' + plugin.gui_name)
        self.showing_widget.restart_now.connect(self.restart_now)
        self.title_bar.show_plugin(plugin)
        self.setWindowIcon(QIcon.ic(plugin.icon))

        self.bb.button(QDialogButtonBox.StandardButton.Close).setVisible(False)
        self.wizard_button.setVisible(False)
        for button in (QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Cancel):
            button = self.bb.button(button)
            button.setVisible(True)

        self.bb.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        self.bb.button(QDialogButtonBox.StandardButton.Apply).setDefault(False), self.bb.button(QDialogButtonBox.StandardButton.Apply).setDefault(True)
        self.restore_defaults_button.setEnabled(self.showing_widget.supports_restoring_to_defaults)
        self.restore_defaults_button.setVisible(self.showing_widget.supports_restoring_to_defaults)
        self.restore_defaults_button.setToolTip(
            self.showing_widget.restore_defaults_desc if self.showing_widget.supports_restoring_to_defaults else
            (_('Restoring to defaults not supported for') + ' ' + plugin.gui_name))
        self.restore_defaults_button.setText(_('Restore &defaults'))
        self.showing_widget.changed_signal.connect(self.changed_signal)

    def changed_signal(self):
        b = self.bb.button(QDialogButtonBox.StandardButton.Apply)
        b.setEnabled(True)

    def hide_plugin(self):
        for sig in 'changed_signal restart_now'.split():
            try:
                getattr(self.showing_widget, sig).disconnect(getattr(self, sig))
            except Exception:
                pass
        self.showing_widget = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.showing_widget)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.stack.setCurrentIndex(0)
        self.title_bar.show_plugin()
        self.setWindowIcon(QIcon.ic('config.png'))

        for button in (QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Cancel):
            button = self.bb.button(button)
            button.setVisible(False)
        self.restore_defaults_button.setVisible(False)

        self.bb.button(QDialogButtonBox.StandardButton.Close).setVisible(True)
        self.bb.button(QDialogButtonBox.StandardButton.Close).setDefault(False), self.bb.button(QDialogButtonBox.StandardButton.Close).setDefault(True)
        self.wizard_button.setVisible(True)

    def restart_now(self):
        try:
            self.showing_widget.commit()
        except AbortCommit:
            return
        self.do_restart = True
        self.hide_plugin()
        self.accept()

    def commit(self, *args):
        must_restart = self.showing_widget.commit()
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

            do_restart = show_restart_warning(msg, parent=self)

        self.showing_widget.refresh_gui(self.gui)
        if do_restart:
            self.do_restart = True
        return self.close_after_initial or (must_restart and rc) or do_restart

    def restore_defaults(self, *args):
        self.showing_widget.restore_defaults()

    def on_shutdown(self):
        gprefs.set('preferences dialog geometry', bytearray(self.saveGeometry()))
        if self.committed:
            self.gui.must_restart_before_config = self.must_restart
            self.gui.tags_view.recount()
            self.gui.create_device_menu()
            self.gui.set_device_menu_items_state(bool(self.gui.device_connected))
            self.gui.bars_manager.apply_settings()
            self.gui.bars_manager.update_bars()
            self.gui.build_context_menus()

    def accept(self):
        if self.stack.currentIndex() == 0:
            self.on_shutdown()
            return QDialog.accept(self)
        try:
            close = self.commit()
        except AbortCommit:
            return
        if close:
            self.on_shutdown()
            return QDialog.accept(self)
        self.hide_plugin()

    def reject(self):
        if self.stack.currentIndex() == 0 or self.close_after_initial:
            self.on_shutdown()
            return QDialog.reject(self)
        self.hide_plugin()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    app
    gui = init_gui()

    p = Preferences(gui)
    p.exec()
    gui.shutdown()
