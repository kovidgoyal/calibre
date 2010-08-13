#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter
from functools import partial

from PyQt4.Qt import QIcon, Qt, QWidget, QAction, QToolBar, QSize, \
    pyqtSignal, QToolButton, \
    QObject, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout, QActionGroup, \
    QMenu

from calibre.constants import __appname__
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2 import config, gprefs
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
                a = m.addAction(QIcon(I('eject.svg')), _('Eject this device'))
                a.triggered.connect(self._eject_requested)
                ac.setMenu(m)
                self._mem.append(a)
            else:
                ac.setToolTip(tooltip)

            return ac

        ac('library', _('Library'), 'lt.png',
                _('Show books in calibre library'))
        ac('main', _('Reader'), 'reader.svg',
                _('Show books in the main memory of the device'))
        ac('carda', _('Card A'), 'sd.svg',
                _('Show books in storage card A'))
        ac('cardb', _('Card B'), 'sd.svg',
                _('Show books in storage card B'))

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
            icon = I('reader.svg')
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
        x.setIcon(QIcon(I('search.svg')))
        l.addWidget(x)
        x.setToolTip(_("Advanced search"))

        self.label = x = QLabel('&Search:')
        l.addWidget(self.label)
        x.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        x = parent.search = SearchBox2(self)
        x.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        x.setObjectName("search")
        x.setToolTip(_("<p>Search the list of books by title, author, publisher, tags, comments, etc.<br><br>Words separated by spaces are ANDed"))
        l.addWidget(x)

        x = parent.clear_button = QToolButton(self)
        x.setIcon(QIcon(I('clear_left.svg')))
        x.setObjectName("clear_button")
        l.addWidget(x)
        x.setToolTip(_("Reset Quick Search"))

        x = parent.saved_search = SavedSearchBox(self)
        x.setMaximumSize(QSize(150, 16777215))
        x.setMinimumContentsLength(15)
        x.setObjectName("saved_search")
        l.addWidget(x)

        x = parent.copy_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_copy_saved.svg")))
        x.setObjectName("copy_search_button")
        l.addWidget(x)
        x.setToolTip(_("Copy current search text (instead of search name)"))

        x = parent.save_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_add_saved.svg")))
        x.setObjectName("save_search_button")
        l.addWidget(x)
        x.setToolTip(_("Save current search under the name shown in the box"))

        x = parent.delete_search_button = QToolButton(self)
        x.setIcon(QIcon(I("search_delete_saved.svg")))
        x.setObjectName("delete_search_button")
        l.addWidget(x)
        x.setToolTip(_("Delete current saved search"))

        self.label.setBuddy(parent.search)


# }}}

class ToolBar(QToolBar): # {{{

    def __init__(self, actions, donate, location_manager, parent=None):
        QToolBar.__init__(self, parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setStyleSheet('QToolButton:checked { font-weight: bold }')
        self.donate = donate
        self.apply_settings()

        self.all_actions = actions
        self.location_manager = location_manager
        self.location_manager.locations_changed.connect(self.build_bar)
        self.d_widget = QWidget()
        self.d_widget.setLayout(QVBoxLayout())
        self.d_widget.layout().addWidget(donate)
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.build_bar()
        self.preferred_width = self.sizeHint().width()

    def apply_settings(self):
        sz = gprefs.get('toolbar_icon_size', 'medium')
        sz = {'small':24, 'medium':48, 'large':64}[sz]
        self.setIconSize(QSize(sz, sz))
        style = Qt.ToolButtonTextUnderIcon
        if gprefs.get('toolbar_text', 'auto') == 'never':
            style = Qt.ToolButtonIconOnly
        self.setToolButtonStyle(style)
        self.donate.set_normal_icon_size(sz, sz)

    def contextMenuEvent(self, *args):
        pass

    def build_bar(self):
        showing_device = self.location_manager.has_device
        order_field = 'device' if showing_device else 'normal'
        o = attrgetter(order_field+'_order')
        sepvals = [2] if showing_device else [1]
        sepvals += [3]
        actions = [x for x in self.all_actions if o(x) > -1]
        actions.sort(cmp=lambda x,y : cmp(o(x), o(y)))
        self.clear()


        def setup_tool_button(ac):
            ch = self.widgetForAction(ac)
            ch.setCursor(Qt.PointingHandCursor)
            ch.setAutoRaise(True)
            if ac.menu() is not None:
                name = getattr(ac, 'action_name', None)
                ch.setPopupMode(ch.InstantPopup if name == 'conn_share'
                        else ch.MenuButtonPopup)

        for x in actions:
            self.addAction(x)
            setup_tool_button(x)

            if x.action_name == 'choose_library':
                self.choose_action = x
                if showing_device:
                    self.addSeparator()
                    for ac in self.location_manager.available_actions:
                        self.addAction(ac)
                        setup_tool_button(ac)
                    self.addSeparator()
                    self.location_manager.location_library.trigger()
                elif config['show_donate_button']:
                    self.addWidget(self.d_widget)

        for x in actions:
            if x.separator_before in sepvals:
                self.insertSeparator(x)

        self.choose_action.setVisible(not showing_device)


    def resizeEvent(self, ev):
        QToolBar.resizeEvent(self, ev)
        style = Qt.ToolButtonTextUnderIcon
        p = gprefs.get('toolbar_text', 'auto')
        if p == 'never':
            style = Qt.ToolButtonIconOnly

        if p == 'auto' and self.preferred_width > self.width()+35:
            style = Qt.ToolButtonIconOnly

        self.setToolButtonStyle(style)

    def database_changed(self, db):
        pass

# }}}

class Action(QAction):
    pass

class MainWindowMixin(object):

    def __init__(self, db):
        self.device_connected = None
        self.setObjectName('MainWindow')
        self.setWindowIcon(QIcon(I('library.png')))
        self.setWindowTitle(__appname__)

        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self._central_widget_layout = QVBoxLayout()
        self.centralwidget.setLayout(self._central_widget_layout)
        self.resize(1012, 740)
        self.donate_button = ThrobbingButton(self.centralwidget)
        self.location_manager = LocationManager(self)

        self.iactions['Fetch News'].init_scheduler(db)

        self.search_bar = SearchBar(self)
        self.tool_bar = ToolBar(all_actions, self.donate_button,
                self.location_manager, self)
        self.addToolBar(Qt.TopToolBarArea, self.tool_bar)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)






