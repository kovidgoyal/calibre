#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QIcon, Qt, QWidget, QToolBar, QSize, \
    pyqtSignal, QToolButton, QPushButton, \
    QObject, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout, QActionGroup, \
    QMenu

from calibre.constants import __appname__
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2 import gprefs
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre import human_readable

class LocationManager(QObject): # {{{

    locations_changed = pyqtSignal()
    unmount_device = pyqtSignal()
    location_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.free = [-1, -1, -1]
        self.count = 0
        self.location_actions = QActionGroup(self)
        self.location_actions.setExclusive(True)
        self.current_location = 'library'
        self._mem = []
        self.tooltips = {}

        def ac(name, text, icon, tooltip):
            icon = QIcon(I(icon))
            ac = self.location_actions.addAction(icon, text)
            setattr(self, 'location_'+name, ac)
            ac.setAutoRepeat(False)
            ac.setCheckable(True)
            receiver = partial(self._location_selected, name)
            ac.triggered.connect(receiver)
            self.tooltips[name] = tooltip
            if name != 'library':
                m = QMenu(parent)
                self._mem.append(m)
                a = m.addAction(icon, tooltip)
                a.triggered.connect(receiver)
                self._mem.append(a)
                a = m.addAction(QIcon(I('eject.png')), _('Eject this device'))
                a.triggered.connect(self._eject_requested)
                ac.setMenu(m)
                self._mem.append(a)
            else:
                ac.setToolTip(tooltip)
            ac.calibre_name = name

            return ac

        self.library_action = ac('library', _('Library'), 'lt.png',
                _('Show books in calibre library'))
        ac('main', _('Device'), 'reader.png',
                _('Show books in the main memory of the device'))
        ac('carda', _('Card A'), 'sd.png',
                _('Show books in storage card A'))
        ac('cardb', _('Card B'), 'sd.png',
                _('Show books in storage card B'))

    def set_switch_actions(self, quick_actions, rename_actions, delete_actions,
            switch_actions, choose_action):
        self.switch_menu = QMenu()
        self.switch_menu.addAction(choose_action)
        self.cs_menus = []
        for t, acs in [(_('Quick switch'), quick_actions),
                (_('Rename library'), rename_actions),
                (_('Delete library'), delete_actions)]:
            if acs:
                self.cs_menus.append(QMenu(t))
                for ac in acs:
                    self.cs_menus[-1].addAction(ac)
                self.switch_menu.addMenu(self.cs_menus[-1])
        self.switch_menu.addSeparator()
        for ac in switch_actions:
            self.switch_menu.addAction(ac)
        self.library_action.setMenu(self.switch_menu)

    def _location_selected(self, location, *args):
        if location != self.current_location and hasattr(self,
                'location_'+location):
            self.current_location = location
            self.location_selected.emit(location)
            getattr(self, 'location_'+location).setChecked(True)

    def _eject_requested(self, *args):
        self.unmount_device.emit()

    def update_devices(self, cp=(None, None), fs=[-1, -1, -1], icon=None):
        if icon is None:
            icon = I('reader.png')
        self.location_main.setIcon(QIcon(icon))
        had_device = self.has_device
        if cp is None:
            cp = (None, None)
        if isinstance(cp, (str, unicode)):
            cp = (cp, None)
        if len(fs) < 3:
            fs = list(fs) + [0]
        self.free[0] = fs[0]
        self.free[1] = fs[1]
        self.free[2] = fs[2]
        cpa, cpb = cp
        self.free[1] = fs[1] if fs[1] is not None and cpa is not None else -1
        self.free[2] = fs[2] if fs[2] is not None and cpb is not None else -1
        self.update_tooltips()
        if self.has_device != had_device:
            self.location_library.setChecked(True)
            self.locations_changed.emit()
            if not self.has_device:
                self.location_library.trigger()

    def update_tooltips(self):
        for i, loc in enumerate(('main', 'carda', 'cardb')):
            t = self.tooltips[loc]
            if self.free[i] > -1:
                t += u'\n\n%s '%human_readable(self.free[i]) + _('available')
            ac = getattr(self, 'location_'+loc)
            ac.setToolTip(t)
            ac.setWhatsThis(t)
            ac.setStatusTip(t)

    @property
    def has_device(self):
        return max(self.free) > -1

    @property
    def available_actions(self):
        ans = [self.location_library]
        for i, loc in enumerate(('main', 'carda', 'cardb')):
            if self.free[i] > -1:
                ans.append(getattr(self, 'location_'+loc))
        return ans

# }}}

class SearchBar(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self._layout = l = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0,5,0,0)

        x = ComboBoxWithHelp(self)
        x.setMaximumSize(QSize(150, 16777215))
        x.setObjectName("search_restriction")
        x.setToolTip(_("Books display will be restricted to those matching the selected saved search"))
        l.addWidget(x)
        parent.search_restriction = x

        x = QLabel(self)
        x.setObjectName("search_count")
        l.addWidget(x)
        parent.search_count = x
        x.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        parent.advanced_search_button = x = QToolButton(self)
        parent.advanced_search_button.setShortcut(_("Shift+Ctrl+F"))
        x.setIcon(QIcon(I('search.png')))
        l.addWidget(x)
        x.setToolTip(_("Advanced search"))

        x = parent.search = SearchBox2(self)
        x.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        x.setObjectName("search")
        x.setToolTip(_("<p>Search the list of books by title, author, publisher, tags, comments, etc.<br><br>Words separated by spaces are ANDed"))
        l.addWidget(x)

        self.search_button = QPushButton(_('&Go!'))
        l.addWidget(self.search_button)
        self.search_button.setSizePolicy(QSizePolicy.Minimum,
                QSizePolicy.Minimum)
        self.search_button.clicked.connect(parent.search.do_search)
        self.search_button.setToolTip(
            _('Do Quick Search (you can also press the Enter key)'))

        x = parent.clear_button = QToolButton(self)
        x.setIcon(QIcon(I('clear_left.png')))
        x.setObjectName("clear_button")
        l.addWidget(x)
        x.setToolTip(_("Reset Quick Search"))

        x = parent.saved_search = SavedSearchBox(self)
        x.setMaximumSize(QSize(150, 16777215))
        x.setMinimumContentsLength(15)
        x.setObjectName("saved_search")
        l.addWidget(x)

        x = parent.copy_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_copy_saved.png")))
        x.setObjectName("copy_search_button")
        l.addWidget(x)
        x.setToolTip(_("Copy current search text (instead of search name)"))

        x = parent.save_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_add_saved.png")))
        x.setObjectName("save_search_button")
        l.addWidget(x)
        x.setToolTip(_("Save current search under the name shown in the box"))

        x = parent.delete_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_delete_saved.png")))
        x.setObjectName("delete_search_button")
        l.addWidget(x)
        x.setToolTip(_("Delete current saved search"))



# }}}

class Spacer(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = QHBoxLayout()
        self.setLayout(self.l)
        self.l.addStretch(10)
# }}}

class ToolBar(QToolBar): # {{{

    def __init__(self, donate, location_manager, child_bar, parent):
        QToolBar.__init__(self, parent)
        self.gui = parent
        self.child_bar = child_bar
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setStyleSheet('QToolButton:checked { font-weight: bold }')
        self.donate_button = donate
        self.apply_settings()

        self.location_manager = location_manager
        self.location_manager.locations_changed.connect(self.build_bar)
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.added_actions = []
        self.build_bar()
        self.preferred_width = self.sizeHint().width()
        self.setAcceptDrops(True)

    def apply_settings(self):
        sz = gprefs['toolbar_icon_size']
        sz = {'small':24, 'medium':48, 'large':64}[sz]
        self.setIconSize(QSize(sz, sz))
        self.child_bar.setIconSize(QSize(sz, sz))
        style = Qt.ToolButtonTextUnderIcon
        if gprefs['toolbar_text'] == 'never':
            style = Qt.ToolButtonIconOnly
        self.setToolButtonStyle(style)
        self.child_bar.setToolButtonStyle(style)
        self.donate_button.set_normal_icon_size(sz, sz)

    def contextMenuEvent(self, *args):
        pass

    def build_bar(self):
        self.child_bar.setVisible(gprefs['show_child_bar'])
        self.showing_donate = False
        showing_device = self.location_manager.has_device
        actions = '-device' if showing_device else ''
        actions = gprefs['action-layout-toolbar'+actions]

        for ac in self.added_actions:
            m = ac.menu()
            if m is not None:
                m.setVisible(False)

        self.clear()
        self.child_bar.clear()
        self.added_actions = []
        self.spacers = [Spacer(self.child_bar), Spacer(self.child_bar),
                Spacer(self), Spacer(self)]
        self.child_bar.addWidget(self.spacers[0])
        if gprefs['show_child_bar']:
            self.addWidget(self.spacers[2])

        for what in actions:
            if what is None and not gprefs['show_child_bar']:
                self.addSeparator()
            elif what == 'Location Manager':
                for ac in self.location_manager.available_actions:
                    self.addAction(ac)
                    self.added_actions.append(ac)
                    self.setup_tool_button(ac, QToolButton.MenuButtonPopup)
            elif what == 'Donate':
                self.d_widget = QWidget()
                self.d_widget.setLayout(QVBoxLayout())
                self.d_widget.layout().addWidget(self.donate_button)
                self.addWidget(self.d_widget)
                self.showing_donate = True
            elif what in self.gui.iactions:
                action = self.gui.iactions[what]
                bar = self
                if action.action_type == 'current' and gprefs['show_child_bar']:
                    bar = self.child_bar
                bar.addAction(action.qaction)
                self.added_actions.append(action.qaction)
                self.setup_tool_button(action.qaction, action.popup_type)

        self.child_bar.addWidget(self.spacers[1])
        if gprefs['show_child_bar']:
            self.addWidget(self.spacers[3])
        else:
            for s in self.spacers[2:]:
                s.setVisible(False)

    def setup_tool_button(self, ac, menu_mode=None):
        ch = self.widgetForAction(ac)
        if ch is None:
            ch = self.child_bar.widgetForAction(ac)
        ch.setCursor(Qt.PointingHandCursor)
        ch.setAutoRaise(True)
        if ac.menu() is not None and menu_mode is not None:
            ch.setPopupMode(menu_mode)

    def resizeEvent(self, ev):
        QToolBar.resizeEvent(self, ev)
        style = Qt.ToolButtonTextUnderIcon
        p = gprefs['toolbar_text']
        if p == 'never':
            style = Qt.ToolButtonIconOnly

        if p == 'auto' and self.preferred_width > self.width()+35 and \
                not gprefs['show_child_bar']:
            style = Qt.ToolButtonIconOnly

        self.setToolButtonStyle(style)

    def database_changed(self, db):
        pass

    #support drag&drop from/to library from/to reader/card
    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/calibre+from_library") or \
           md.hasFormat("application/calibre+from_device"):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        allowed = False
        md = event.mimeData()
        #Drop is only allowed in the location manager widget's different from the selected one
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

        mime = 'application/calibre+from_device'
        if data.hasFormat(mime):
            paths = [unicode(u.toLocalFile()) for u in data.urls()]
            if paths:
                self.gui.iactions['Add Books'].add_books_from_device(
                        self.gui.current_view(), paths=paths)
                event.accept()

# }}}

class MainWindowMixin(object): # {{{

    def __init__(self, db):
        self.setObjectName('MainWindow')
        self.setWindowIcon(QIcon(I('library.png')))
        self.setWindowTitle(__appname__)

        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self._central_widget_layout = QVBoxLayout()
        self.centralwidget.setLayout(self._central_widget_layout)
        self.resize(1012, 740)
        self.donate_button = ThrobbingButton()
        self.location_manager = LocationManager(self)

        self.iactions['Fetch News'].init_scheduler(db)

        self.search_bar = SearchBar(self)
        self.child_bar = QToolBar(self)
        self.tool_bar = ToolBar(self.donate_button,
                self.location_manager, self.child_bar, self)
        self.addToolBar(Qt.TopToolBarArea, self.tool_bar)
        self.addToolBar(Qt.BottomToolBarArea, self.child_bar)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)

# }}}




