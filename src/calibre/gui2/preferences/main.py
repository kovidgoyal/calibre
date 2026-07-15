#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
import textwrap
from collections import OrderedDict
from functools import partial

from qt.core import (
    QAction,
    QDialog,
    QDialogButtonBox,
    QFont,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QPainter,
    QPalette,
    QPointF,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QStackedWidget,
    QStatusTipEvent,
    Qt,
    QTabWidget,
    QTextLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.constants import __appname__, __version__
from calibre.customize.ui import preferences_plugins
from calibre.gui2 import gprefs, show_restart_warning
from calibre.gui2.dialogs.message_box import Icon
from calibre.gui2.preferences import AbortCommit, AbortInitialize, ConfigWidgetBase, get_plugin, init_gui
from calibre.utils.localization import _

ICON_SIZE = 32
PREFERENCE_BUTTON_WIDTH = 112
PREFERENCE_BUTTON_TEXT_PADDING = 12
PREFERENCE_CATEGORY_VERTICAL_SHIFT = 4


def wrap_preference_button_text(text, max_width=0, font_metrics=None):
    if font_metrics is None or max_width <= 0:
        return textwrap.fill(text, 13, break_long_words=False)
    lines, line = [], ''
    for word in text.split():
        candidate = word if not line else line + ' ' + word
        if line and font_metrics.horizontalAdvance(candidate) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return '\n'.join(lines) or text


# Title Bar {{{

class Message(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.text_layout = QTextLayout()
        self.text_layout.setFont(self.font())
        self.text_layout.setCacheEnabled(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.last_layout_rect = None

    def setText(self, text):
        self.text_layout.setText(text)
        self.last_layout_rect = None
        self.update()

    def sizeHint(self):
        return QSize(10, 10)

    def do_layout(self):
        ly = self.text_layout
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

    def paintEvent(self, a0):
        if self.last_layout_rect != self.rect():
            self.do_layout()
        p = QPainter(self)
        br = self.text_layout.boundingRect()
        y = 0
        if br.height() < self.height():
            y = (self.height() - br.height()) / 2
        self.text_layout.draw(p, QPointF(0, y))


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


class SectionSeparator(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(1, 1)

    def paintEvent(self, a0):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Mid))


class Category(QWidget):  # {{{

    plugin_activated = pyqtSignal(object)

    def __init__(self, name, plugins, gui_name, parent=None, add_separator=True, columns=1):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        margins = self._layout.contentsMargins()
        self._layout.setContentsMargins(
            margins.left(), margins.top(), margins.right(), max(0, margins.bottom() - PREFERENCE_CATEGORY_VERTICAL_SHIFT))
        if add_separator:
            self._layout.addWidget(SectionSeparator(self))
        self.label = QLabel(gui_name)
        self.bf = QFont()
        self.bf.setBold(True)
        self.label.setFont(self.bf)
        self._layout.addWidget(self.label)

        self.plugins = plugins
        self.columns = max(1, columns)

        self.bar = QWidget(self)
        self.bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(0, PREFERENCE_CATEGORY_VERTICAL_SHIFT, 0, 0)
        self.bar_layout.setSpacing(0)
        self._layout.addWidget(self.bar)
        self._actions = []
        self.buttons = []
        from calibre.gui2.ui import get_gui
        iac = get_gui(fail_if_absent=True).iactions['Preferences']
        for p in plugins:
            sc = iac.action_map.get(p.name).shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            target = partial(self.triggered, p)
            ac = QAction(QIcon.ic(p.icon), p.gui_name.replace('&', '&&'), self)
            ac.triggered.connect(target)
            tt = '<p>' + p.description
            if sc:
                tt += '<br>' + _('Shortcut: <i>{}').format(sc)
            ac.setToolTip(tt)
            ac.setWhatsThis(textwrap.fill(p.description))
            ac.setStatusTip(p.description)
            self._actions.append(ac)
            w = QToolButton(self.bar)
            w.setDefaultAction(ac)
            w.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            w.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button_text = p.gui_name.replace('&', '&&')
            self.buttons.append((w, button_text))
            self.bar_layout.addWidget(w)
            w.setText(wrap_preference_button_text(button_text))
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            w.setAutoRaise(True)
            w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.bar_layout.addStretch(1)
        self.update_button_widths()

    def resizeEvent(self, a0):
        QWidget.resizeEvent(self, a0)
        self.update_button_widths()

    def update_button_widths(self, available_width=None):
        if not self.buttons:
            return
        # Keep every category on the same grid; empty columns remain blank instead of creating overflow buttons.
        available = self.bar.contentsRect().width() if available_width is None else available_width
        width = PREFERENCE_BUTTON_WIDTH if available_width is None and available <= 0 else max(1, available // self.columns)
        for button, button_text in self.buttons:
            button.setFixedWidth(width)
            button.setText(wrap_preference_button_text(
                button_text, width - PREFERENCE_BUTTON_TEXT_PADDING, button.fontMetrics()))

    def triggered(self, plugin, *args):
        self.plugin_activated.emit(plugin)

# }}}


class Browser(QScrollArea):  # {{{

    show_plugin = pyqtSignal(object)

    def __init__(self, parent=None):
        QScrollArea.__init__(self, parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        category_map, category_names = {}, {}
        for plugin in preferences_plugins():
            if plugin.category not in category_map:
                category_map[plugin.category] = plugin.category_order
            category_map[plugin.category] = max(category_map[plugin.category], plugin.category_order)
            if plugin.category not in category_names:
                category_names[plugin.category] = (plugin.gui_category or plugin.category)

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
        self.columns = max(map(len, self.category_map.values()), default=1)
        self._layout = QVBoxLayout()
        self.container = QWidget(self)
        self.container.setLayout(self._layout)
        self.setWidget(self.container)

        for i, (name, plugins) in enumerate(self.category_map.items()):
            w = Category(name, plugins, self.category_names[name], parent=self, add_separator=i > 0, columns=self.columns)
            self.widgets.append(w)
            self._layout.addWidget(w)
            w.plugin_activated.connect(self.show_plugin.emit)
        self._layout.addStretch(1)
        self.update_category_widths()

    def resizeEvent(self, a0):
        QScrollArea.resizeEvent(self, a0)
        self.update_category_widths()

    def update_category_widths(self):
        margins = self._layout.contentsMargins()
        available = self.viewport().width() - margins.left() - margins.right()
        for widget in self.widgets:
            category_margins = widget._layout.contentsMargins()
            widget.update_button_widths(available - category_margins.left() - category_margins.right())

# }}}


must_restart_message = _('The changes you have made require calibre be '
                         'restarted immediately. You will not be allowed to '
                         'set any more preferences, until you restart.')


class Preferences(QDialog):

    run_wizard_requested = pyqtSignal()
    showing_widget: ConfigWidgetBase

    def __init__(self, gui, initial_plugin=None, close_after_initial=False):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.must_restart = False
        self.do_restart = False
        self.committed = False
        self.close_after_initial = close_after_initial

        self.geometry_restored = self.restore_geometry(gprefs, 'preferences dialog geometry')

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(__appname__ + ' — ' + _('Preferences'))
        self.setWindowIcon(QIcon.ic('config.png'))
        self.l = l = QVBoxLayout(self)

        self.stack = QStackedWidget(self)
        self.bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close | QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = self.bb.button(QDialogButtonBox.StandardButton.Apply)
        assert apply_button is not None
        apply_button.clicked.connect(self.accept)
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
            btn = self.bb.button(ac)
            assert btn is not None
            btn.setToolTip(tt)

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
                                    try:
                                        self.showing_widget.initial_tab_changed()
                                    except Exception:
                                        pass
                                    break
        else:
            self.hide_plugin()
            if not self.geometry_restored:
                # Keep the first-run overview size at the original dialog default; saved user geometry still wins.
                self.resize(self.sizeHint())

    def sizeHint(self):
        return QSize(930, 720)

    def event(self, a0):
        if isinstance(a0, QStatusTipEvent):
            msg = re.sub(r'</?[a-z1-6]+>', ' ', a0.tip())
            self.title_bar.show_msg(msg)
        return QDialog.event(self, a0)

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
        self.showing_widget.do_on_child_tabs('genesis', self.gui)
        try:
            self.showing_widget.initialize()
            self.showing_widget.do_on_child_tabs('initialize')
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

        close_btn = self.bb.button(QDialogButtonBox.StandardButton.Close)
        assert close_btn is not None
        close_btn.setVisible(False)
        self.wizard_button.setVisible(False)
        for button in (QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Cancel):
            button = self.bb.button(button)
            assert button is not None
            button.setVisible(True)

        apply_btn = self.bb.button(QDialogButtonBox.StandardButton.Apply)
        assert apply_btn is not None
        apply_btn.setEnabled(False)
        apply_btn.setDefault(False), apply_btn.setDefault(True)
        self.restore_defaults_button.setEnabled(self.showing_widget.supports_restoring_to_defaults)
        self.restore_defaults_button.setVisible(self.showing_widget.supports_restoring_to_defaults)
        self.restore_defaults_button.setToolTip(
            self.showing_widget.restore_defaults_desc if self.showing_widget.supports_restoring_to_defaults else
            (_('Restoring to defaults not supported for') + ' ' + plugin.gui_name))
        self.restore_defaults_button.setText(_('Restore &defaults'))
        self.showing_widget.changed_signal.connect(self.changed_signal)
        self.showing_widget.do_on_child_tabs('set_changed_signal', self.changed_signal)

    def changed_signal(self):
        b = self.bb.button(QDialogButtonBox.StandardButton.Apply)
        assert b is not None
        b.setEnabled(True)

    def hide_plugin(self):
        for sig in 'changed_signal restart_now'.split():
            try:
                getattr(self.showing_widget, sig).disconnect(getattr(self, sig))
            except Exception:
                pass
        self.stack.setCurrentIndex(0)
        self.showing_widget_placeholder = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.showing_widget_placeholder)
        self.setWindowTitle(__appname__ + ' - ' + _('Preferences'))
        self.title_bar.show_plugin()
        self.setWindowIcon(QIcon.ic('config.png'))

        for button in (QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Cancel):
            button = self.bb.button(button)
            assert button is not None
            button.setVisible(False)
        self.restore_defaults_button.setVisible(False)

        close_button = self.bb.button(QDialogButtonBox.StandardButton.Close)
        assert close_button is not None
        close_button.setVisible(True)
        close_button.setDefault(False), close_button.setDefault(True)
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
        # Commit the child widgets first in case the main widget uses the information
        must_restart = bool(self.showing_widget.do_on_child_tabs('commit')) | bool(self.showing_widget.commit())
        rc = self.showing_widget.restart_critical
        self.committed = True
        do_restart = False
        if must_restart:
            self.must_restart = True
            if rc:
                msg = must_restart_message
            else:
                msg = _('Some of the changes you made require a restart.'
                        ' Please restart calibre as soon as possible.')
            do_restart = show_restart_warning(msg, parent=self)

        # Same with refresh -- do the child widgets first so the main widget has the info
        self.showing_widget.do_on_child_tabs('refresh_gui', self.gui)
        self.showing_widget.refresh_gui(self.gui)
        if do_restart:
            self.do_restart = True
        return self.close_after_initial or (must_restart and rc) or do_restart

    def restore_defaults(self, *args):
        self.showing_widget.do_on_child_tabs('restore_defaults')
        self.showing_widget.restore_defaults()

    def on_shutdown(self):
        self.save_geometry(gprefs, 'preferences dialog geometry')
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
