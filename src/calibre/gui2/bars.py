#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sip
from PyQt5.Qt import (
    Qt, QAction, QMenu, QObject, QToolBar, QToolButton, QSize, pyqtSignal,
    QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPainter, QWidget)

from calibre.constants import isosx
from calibre.gui2 import gprefs, native_menubar_defaults, config
from calibre.gui2.throbber import ThrobbingButton


class RevealBar(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setVisible(False)
        self._animated_size = 1.0
        self.animation = QPropertyAnimation(self, b'animated_size', self)
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.setDuration(1000), self.animation.setStartValue(0.0), self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self.animation_value_changed)
        self.animation.finished.connect(self.animation_done)

    @pyqtProperty(float)
    def animated_size(self):
        return self._animated_size

    @animated_size.setter
    def animated_size(self, val):
        self._animated_size = val

    def animation_value_changed(self, *args):
        self.update()

    def animation_done(self):
        self.setVisible(False)
        self.update()

    def start(self, bar):
        self.setGeometry(bar.geometry())
        self.setVisible(True)
        self.animation.start()

    def paintEvent(self, ev):
        if self._animated_size < 1.0:
            rect = self.rect()
            painter = QPainter(self)
            pal = self.palette()
            col = pal.color(pal.Button)
            rect.setLeft(rect.left() + (rect.width() * self._animated_size))
            painter.setClipRect(rect)
            painter.fillRect(self.rect(), col)
# }}}


def create_donate_button(action):
    ans = ThrobbingButton()
    ans.setAutoRaise(True)
    ans.setCursor(Qt.PointingHandCursor)
    ans.clicked.connect(action.trigger)
    ans.setToolTip(action.text().replace('&', ''))
    ans.setIcon(action.icon())
    ans.setStatusTip(ans.toolTip())
    return ans


class ToolBar(QToolBar):  # {{{

    def __init__(self, donate_action, location_manager, parent):
        QToolBar.__init__(self, parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setStyleSheet('QToolButton:checked { font-weight: bold }')
        self.preferred_width = self.sizeHint().width()
        self.gui = parent
        self.donate_action = donate_action
        self.donate_button = None
        self.added_actions = []

        self.location_manager = location_manager
        self.setAcceptDrops(True)
        self.showing_donate = False

    def resizeEvent(self, ev):
        QToolBar.resizeEvent(self, ev)
        style = self.get_text_style()
        self.setToolButtonStyle(style)
        if self.showing_donate:
            self.donate_button.setToolButtonStyle(style)

    def get_text_style(self):
        style = Qt.ToolButtonTextUnderIcon
        s = gprefs['toolbar_icon_size']
        if s != 'off':
            p = gprefs['toolbar_text']
            if p == 'never':
                style = Qt.ToolButtonIconOnly
            elif p == 'auto' and self.preferred_width > self.width()+35:
                style = Qt.ToolButtonIconOnly
        return style

    def contextMenuEvent(self, ev):
        ac = self.actionAt(ev.pos())
        if ac is None:
            return
        ch = self.widgetForAction(ac)
        sm = getattr(ch, 'showMenu', None)
        if callable(sm):
            ev.accept()
            sm()

    def update_lm_actions(self):
        for ac in self.added_actions:
            if ac in self.location_manager.all_actions:
                ac.setVisible(ac in self.location_manager.available_actions)

    def init_bar(self, actions):
        self.showing_donate = False
        for ac in self.added_actions:
            m = ac.menu()
            if m is not None:
                m.setVisible(False)

        self.clear()
        self.added_actions = []
        self.donate_button = None

        bar = self

        for what in actions:
            if what is None:
                bar.addSeparator()
            elif what == 'Location Manager':
                for ac in self.location_manager.all_actions:
                    bar.addAction(ac)
                    bar.added_actions.append(ac)
                    bar.setup_tool_button(bar, ac, QToolButton.MenuButtonPopup)
                    ac.setVisible(False)
            elif what == 'Donate':
                self.donate_button = create_donate_button(self.donate_action)
                bar.addWidget(self.donate_button)
                self.donate_button.setIconSize(bar.iconSize())
                self.donate_button.setToolButtonStyle(self.toolButtonStyle())
                self.showing_donate = True
            elif what in self.gui.iactions:
                action = self.gui.iactions[what]
                bar.addAction(action.qaction)
                self.added_actions.append(action.qaction)
                self.setup_tool_button(bar, action.qaction, action.popup_type)
        self.preferred_width = self.sizeHint().width()

    def setup_tool_button(self, bar, ac, menu_mode=None):
        ch = bar.widgetForAction(ac)
        if ch is None:
            ch = self.child_bar.widgetForAction(ac)
        ch.setCursor(Qt.PointingHandCursor)
        ch.setAutoRaise(True)
        m = ac.menu()
        if m is not None:
            if menu_mode is not None:
                ch.setPopupMode(menu_mode)
        return ch

    # support drag&drop from/to library, from/to reader/card, enabled plugins
    def check_iactions_for_drag(self, event, md, func):
        if self.added_actions:
            pos = event.pos()
            for iac in self.gui.iactions.itervalues():
                if iac.accepts_drops:
                    aa = iac.qaction
                    w = self.widgetForAction(aa)
                    m = aa.menu()
                    if (((w is not None and w.geometry().contains(pos)) or
                          (m is not None and m.isVisible() and m.geometry().contains(pos))) and
                         getattr(iac, func)(event, md)):
                        return True
        return False

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/calibre+from_library") or \
           md.hasFormat("application/calibre+from_device"):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return

        if self.check_iactions_for_drag(event, md, 'accept_enter_event'):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        allowed = False
        md = event.mimeData()
        # Drop is only allowed in the location manager widget's different from the selected one
        for ac in self.location_manager.available_actions:
            w = self.widgetForAction(ac)
            if w is not None:
                if (md.hasFormat("application/calibre+from_library") or
                     md.hasFormat("application/calibre+from_device")) and \
                        w.geometry().contains(event.pos()) and \
                        isinstance(w, QToolButton) and not w.isChecked():
                    allowed = True
                    break
        if allowed:
            event.acceptProposedAction()
            return

        if self.check_iactions_for_drag(event, md, 'accept_drag_move_event'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        data = event.mimeData()
        mime = 'application/calibre+from_library'
        if data.hasFormat(mime):
            ids = list(map(int, str(data.data(mime)).split()))
            tgt = None
            for ac in self.location_manager.available_actions:
                w = self.widgetForAction(ac)
                if w is not None and w.geometry().contains(event.pos()):
                    tgt = ac.calibre_name
            if tgt is not None:
                if tgt == 'main':
                    tgt = None
                self.gui.sync_to_device(tgt, False, send_ids=ids)
                event.accept()
                return

        mime = 'application/calibre+from_device'
        if data.hasFormat(mime):
            paths = [unicode(u.toLocalFile()) for u in data.urls()]
            if paths:
                self.gui.iactions['Add Books'].add_books_from_device(
                        self.gui.current_view(), paths=paths)
                event.accept()
                return

        # Give added_actions an opportunity to process the drag&drop event
        if self.check_iactions_for_drag(event, data, 'drop_event'):
            event.accept()
        else:
            event.ignore()

# }}}


class MenuAction(QAction):  # {{{

    def __init__(self, clone, parent):
        QAction.__init__(self, clone.text(), parent)
        self.clone = clone
        clone.changed.connect(self.clone_changed)

    def clone_changed(self):
        self.setText(self.clone.text())
# }}}

# MenuBar {{{


if isosx:
    # On OS X we need special handling for the application global menu bar and
    # the context menus, since Qt does not handle dynamic menus or menus in
    # which the same action occurs in more than one place.

    class CloneAction(QAction):

        text_changed = pyqtSignal()
        visibility_changed = pyqtSignal()

        def __init__(self, clone, parent, is_top_level=False, clone_shortcuts=True):
            QAction.__init__(self, clone.text().replace('&&', '&'), parent)
            self.setMenuRole(QAction.NoRole)  # ensure this action is not moved around by Qt
            self.is_top_level = is_top_level
            self.clone_shortcuts = clone_shortcuts
            self.clone = clone
            clone.changed.connect(self.clone_changed)
            self.clone_changed()
            self.triggered.connect(self.do_trigger)

        def clone_menu(self):
            m = self.menu()
            m.clear()
            for ac in QMenu.actions(self.clone.menu()):
                if ac.isSeparator():
                    m.addSeparator()
                else:
                    m.addAction(CloneAction(ac, self.parent(), clone_shortcuts=self.clone_shortcuts))

        def clone_changed(self):
            otext = self.text()
            self.setText(self.clone.text())
            if otext != self.text:
                self.text_changed.emit()
            ov = self.isVisible()
            self.setVisible(self.clone.isVisible())
            if ov != self.isVisible():
                self.visibility_changed.emit()
            self.setEnabled(self.clone.isEnabled())
            self.setCheckable(self.clone.isCheckable())
            self.setChecked(self.clone.isChecked())
            self.setIcon(self.clone.icon())
            if self.clone_shortcuts:
                self.setShortcuts(self.clone.shortcuts())
            if self.clone.menu() is None:
                if not self.is_top_level:
                    self.setMenu(None)
            else:
                m = QMenu(self.text(), self.parent())
                m.aboutToShow.connect(self.about_to_show)
                self.setMenu(m)
                self.clone_menu()

        def about_to_show(self):
            cm = self.clone.menu()
            before = list(QMenu.actions(cm))
            cm.aboutToShow.emit()
            after = list(QMenu.actions(cm))
            if before != after:
                self.clone_menu()

        def do_trigger(self, checked=False):
            if not sip.isdeleted(self.clone):
                self.clone.trigger()

    def populate_menu(m, items, iactions):
        for what in items:
            if what is None:
                m.addSeparator()
            elif what in iactions:
                m.addAction(CloneAction(iactions[what].qaction, m))

    class MenuBar(QObject):

        is_native_menubar = True

        @property
        def native_menubar(self):
            return self.gui.native_menubar

        def __init__(self, location_manager, parent):
            QObject.__init__(self, parent)
            self.gui = parent

            self.location_manager = location_manager
            self.added_actions = []
            self.last_actions = []

            self.donate_action = QAction(_('Donate'), self)
            self.donate_menu = QMenu()
            self.donate_menu.addAction(self.gui.donate_action)
            self.donate_action.setMenu(self.donate_menu)
            self.refresh_timer = t = QTimer(self)
            t.setInterval(200), t.setSingleShot(True), t.timeout.connect(self.refresh_bar)

        def init_bar(self, actions):
            mb = self.native_menubar
            if mb.parent() is None:
                # Without this the menubar does not update correctly with Qt >=
                # 5.6. See the last couple of lines in updateMenuBarImmediately
                # in qcocoamenubar.mm
                mb.setParent(self.gui)
            self.last_actions = actions
            for ac in self.added_actions:
                m = ac.menu()
                if m is not None:
                    m.setVisible(False)

            for ac in self.added_actions:
                mb.removeAction(ac)
                if ac is not self.donate_action:
                    ac.setMenu(None)
                    ac.deleteLater()
            self.added_actions = []

            for what in actions:
                if what is None:
                    continue
                elif what == 'Location Manager':
                    for ac in self.location_manager.available_actions:
                        self.build_menu(ac)
                elif what == 'Donate':
                    mb.addAction(self.donate_action)
                elif what in self.gui.iactions:
                    action = self.gui.iactions[what]
                    self.build_menu(action.qaction)

        def build_menu(self, ac):
            ans = CloneAction(ac, self.native_menubar, is_top_level=True)
            if ans.menu() is None:
                m = QMenu()
                m.addAction(CloneAction(ac, self.native_menubar))
                ans.setMenu(m)
            # Qt (as of 5.3.0) does not update global menubar entries
            # correctly, so we have to rebuild the global menubar.
            # Without this the Choose Library action shows the text
            # 'Untitled' and the Location Manager items do not work.
            ans.text_changed.connect(self.refresh_timer.start)
            ans.visibility_changed.connect(self.refresh_timer.start)
            self.native_menubar.addAction(ans)
            self.added_actions.append(ans)
            return ans

        def setVisible(self, yes):
            pass  # no-op on OS X since menu bar is always visible

        def update_lm_actions(self):
            pass  # no-op as this is taken care of by init_bar()

        def refresh_bar(self):
            self.init_bar(self.last_actions)

else:

    def populate_menu(m, items, iactions):
        for what in items:
            if what is None:
                m.addSeparator()
            elif what in iactions:
                m.addAction(iactions[what].qaction)

    from calibre.gui2.dbus_export.widgets import factory

    class MenuBar(QObject):

        is_native_menubar = False

        def __init__(self, location_manager, parent):
            QObject.__init__(self, parent)
            f = factory(app_id='com.calibre-ebook.gui')
            self.menu_bar = f.create_window_menubar(parent)
            self.is_native_menubar = self.menu_bar.is_native_menubar
            self.gui = parent

            self.location_manager = location_manager
            self.added_actions = []

            self.donate_action = QAction(_('Donate'), self)
            self.donate_menu = QMenu()
            self.donate_menu.addAction(self.gui.donate_action)
            self.donate_action.setMenu(self.donate_menu)

        def addAction(self, *args):
            self.menu_bar.addAction(*args)

        def setVisible(self, visible):
            self.menu_bar.setVisible(visible)

        def clear(self):
            self.menu_bar.clear()

        def init_bar(self, actions):
            for ac in self.added_actions:
                m = ac.menu()
                if m is not None:
                    m.setVisible(False)

            self.clear()
            self.added_actions = []

            for what in actions:
                if what is None:
                    continue
                elif what == 'Location Manager':
                    for ac in self.location_manager.all_actions:
                        ac = self.build_menu(ac)
                        self.addAction(ac)
                        self.added_actions.append(ac)
                        ac.setVisible(False)
                elif what == 'Donate':
                    self.addAction(self.donate_action)
                elif what in self.gui.iactions:
                    action = self.gui.iactions[what]
                    ac = self.build_menu(action.qaction)
                    self.addAction(ac)
                    self.added_actions.append(ac)

        def build_menu(self, action):
            m = action.menu()
            ac = MenuAction(action, self)
            if m is None:
                m = QMenu()
                m.addAction(action)
            ac.setMenu(m)
            return ac

        def update_lm_actions(self):
            for ac in self.added_actions:
                clone = getattr(ac, 'clone', None)
                if clone is not None and clone in self.location_manager.all_actions:
                    ac.setVisible(clone in self.location_manager.available_actions)

# }}}


class BarsManager(QObject):

    def __init__(self, donate_action, location_manager, parent):
        QObject.__init__(self, parent)
        self.location_manager = location_manager

        bars = [ToolBar(donate_action, location_manager, parent) for i in
                range(3)]
        self.main_bars = tuple(bars[:2])
        self.child_bars = tuple(bars[2:])
        self.reveal_bar = RevealBar(parent)

        self.menu_bar = MenuBar(self.location_manager, self.parent())
        is_native_menubar = self.menu_bar.is_native_menubar
        self.menubar_fallback = native_menubar_defaults['action-layout-menubar'] if is_native_menubar else ()
        self.menubar_device_fallback = native_menubar_defaults['action-layout-menubar-device'] if is_native_menubar else ()

        self.apply_settings()
        self.init_bars()

    def database_changed(self, db):
        pass

    @property
    def bars(self):
        for x in self.main_bars + self.child_bars:
            yield x

    @property
    def showing_donate(self):
        for b in self.bars:
            if b.isVisible() and b.showing_donate:
                return True
        return False

    def start_animation(self):
        for b in self.bars:
            if b.isVisible() and b.showing_donate:
                b.donate_button.start_animation()
                return True

    def init_bars(self):
        self.bar_actions = tuple(
            [gprefs['action-layout-toolbar'+x] for x in ('', '-device')] +
            [gprefs['action-layout-toolbar-child']] +
            [gprefs['action-layout-menubar'] or self.menubar_fallback] +
            [gprefs['action-layout-menubar-device'] or self.menubar_device_fallback]
        )

        for bar, actions in zip(self.bars, self.bar_actions[:3]):
            bar.init_bar(actions)

    def update_bars(self, reveal_bar=False):
        '''
        This shows the correct main toolbar and rebuilds the menubar based on
        whether a device is connected or not. Note that the toolbars are
        explicitly not rebuilt, this is to workaround a Qt limitation iwth
        QToolButton's popup menus and modal dialogs. If you want the toolbars
        rebuilt, call init_bars().
        '''
        showing_device = self.location_manager.has_device
        main_bar = self.main_bars[1 if showing_device else 0]
        child_bar = self.child_bars[0]
        for bar in self.bars:
            bar.setVisible(False)
            bar.update_lm_actions()
        if main_bar.added_actions:
            main_bar.setVisible(True)
            if reveal_bar and not config['disable_animations']:
                self.reveal_bar.start(main_bar)
        if child_bar.added_actions:
            child_bar.setVisible(True)

        self.menu_bar.init_bar(self.bar_actions[4 if showing_device else 3])
        self.menu_bar.update_lm_actions()
        self.menu_bar.setVisible(bool(self.menu_bar.added_actions))

    def apply_settings(self):
        sz = gprefs['toolbar_icon_size']
        sz = {'off':0, 'small':24, 'medium':48, 'large':64}[sz]
        style = Qt.ToolButtonTextUnderIcon
        if sz > 0 and gprefs['toolbar_text'] == 'never':
            style = Qt.ToolButtonIconOnly

        for bar in self.bars:
            bar.setIconSize(QSize(sz, sz))
            bar.setToolButtonStyle(style)
            if bar.showing_donate:
                bar.donate_button.setIconSize(bar.iconSize())
                bar.donate_button.setToolButtonStyle(style)
