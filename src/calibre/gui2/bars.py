#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (Qt, QAction, QLabel, QMenu, QMenuBar, QObject,
    QToolBar, QToolButton, QSize, QVBoxLayout, QWidget)

from calibre.constants import isosx
from calibre.gui2 import gprefs

class ToolBar(QToolBar): # {{{

    def __init__(self, donate, location_manager, parent):
        QToolBar.__init__(self, parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setStyleSheet('QToolButton:checked { font-weight: bold }')
        self.preferred_width = self.sizeHint().width()
        self.gui = parent
        self.donate_button = donate
        self.added_actions = []

        self.location_manager = location_manager
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.showing_donate = False

    def resizeEvent(self, ev):
        QToolBar.resizeEvent(self, ev)
        style = self.get_text_style()
        self.setToolButtonStyle(style)
        if hasattr(self, 'd_widget') and hasattr(self.d_widget, 'filler'):
            self.d_widget.filler.setVisible(style != Qt.ToolButtonIconOnly)

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
        if ac is None: return
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
                self.d_widget = QWidget()
                self.d_widget.setLayout(QVBoxLayout())
                self.d_widget.layout().addWidget(self.donate_button)
                if isosx:
                    self.d_widget.setStyleSheet('QWidget, QToolButton {background-color: none; border: none; }')
                    self.d_widget.layout().setContentsMargins(0,0,0,0)
                    self.d_widget.setContentsMargins(0,0,0,0)
                    self.d_widget.filler = QLabel(u'\u00a0')
                    self.d_widget.layout().addWidget(self.d_widget.filler)
                bar.addWidget(self.d_widget)
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
        if ac.menu() is not None and menu_mode is not None:
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
                    func = getattr(iac, func)
                    if (( (w is not None and w.geometry().contains(pos)) or
                          (m is not None and m.geometry().contains(pos)) ) and
                         func(event, md)):
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
                if ( md.hasFormat("application/calibre+from_library") or \
                     md.hasFormat("application/calibre+from_device") ) and \
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

class MenuAction(QAction): # {{{

    def __init__(self, clone, parent):
        QAction.__init__(self, clone.text(), parent)
        self.clone = clone
        clone.changed.connect(self.clone_changed)

    def clone_changed(self):
        self.setText(self.clone.text())
# }}}

class MenuBar(QMenuBar): # {{{

    def __init__(self, location_manager, parent):
        QMenuBar.__init__(self, parent)
        self.gui = parent
        self.setNativeMenuBar(True)

        self.location_manager = location_manager
        self.added_actions = []

        self.donate_action = QAction(_('Donate'), self)
        self.donate_menu = QMenu()
        self.donate_menu.addAction(self.gui.donate_action)
        self.donate_action.setMenu(self.donate_menu)

    def update_lm_actions(self):
        for ac in self.added_actions:
            clone = getattr(ac, 'clone', None)
            if clone is not None and clone in self.location_manager.all_actions:
                ac.setVisible(clone in self.location_manager.available_actions)

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

# }}}

class BarsManager(QObject):

    def __init__(self, donate_button, location_manager, parent):
        QObject.__init__(self, parent)
        self.donate_button, self.location_manager = (donate_button,
                location_manager)

        bars = [ToolBar(donate_button, location_manager, parent) for i in
                range(3)]
        self.main_bars = tuple(bars[:2])
        self.child_bars = tuple(bars[2:])

        self.menu_bar = MenuBar(self.location_manager, self.parent())
        self.parent().setMenuBar(self.menu_bar)

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

    def init_bars(self):
        self.bar_actions = tuple(
            [gprefs['action-layout-toolbar'+x] for x in ('', '-device')] +
            [gprefs['action-layout-toolbar-child']] +
            [gprefs['action-layout-menubar']] +
            [gprefs['action-layout-menubar-device']]
        )

        for bar, actions in zip(self.bars, self.bar_actions[:3]):
            bar.init_bar(actions)

    def update_bars(self):
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
        self.donate_button.set_normal_icon_size(sz, sz)


