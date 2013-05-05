#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import (QIcon, Qt, QWidget, QSize,
    pyqtSignal, QToolButton, QMenu, QAction,
    QObject, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout, QActionGroup)


from calibre.constants import __appname__
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2.bars import BarsManager
from calibre.utils.config_base import tweaks
from calibre import human_readable

class LocationManager(QObject):  # {{{

    locations_changed = pyqtSignal()
    unmount_device = pyqtSignal()
    location_selected = pyqtSignal(object)
    configure_device = pyqtSignal()

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.free = [-1, -1, -1]
        self.count = 0
        self.location_actions = QActionGroup(self)
        self.location_actions.setExclusive(True)
        self.current_location = 'library'
        self._mem = []
        self.tooltips = {}

        self.all_actions = []

        def ac(name, text, icon, tooltip):
            icon = QIcon(I(icon))
            ac = self.location_actions.addAction(icon, text)
            setattr(self, 'location_'+name, ac)
            ac.setAutoRepeat(False)
            ac.setCheckable(True)
            receiver = partial(self._location_selected, name)
            ac.triggered.connect(receiver)
            self.tooltips[name] = tooltip

            m = QMenu(parent)
            self._mem.append(m)
            a = m.addAction(icon, tooltip)
            a.triggered.connect(receiver)
            if name != 'library':
                self._mem.append(a)
                a = m.addAction(QIcon(I('eject.png')), _('Eject this device'))
                a.triggered.connect(self._eject_requested)
                self._mem.append(a)
                a = m.addAction(QIcon(I('config.png')), _('Configure this device'))
                a.triggered.connect(self._configure_requested)
                self._mem.append(a)

            else:
                ac.setToolTip(tooltip)
            ac.setMenu(m)
            ac.calibre_name = name

            self.all_actions.append(ac)
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
        self.switch_menu = self.library_action.menu()
        if self.switch_menu:
            self.switch_menu.addSeparator()
        else:
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

        if self.switch_menu != self.library_action.menu():
            self.library_action.setMenu(self.switch_menu)

    def _location_selected(self, location, *args):
        if location != self.current_location and hasattr(self,
                'location_'+location):
            self.current_location = location
            self.location_selected.emit(location)
            getattr(self, 'location_'+location).setChecked(True)

    def _eject_requested(self, *args):
        self.unmount_device.emit()

    def _configure_requested(self):
        self.configure_device.emit()

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

class SearchBar(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self._layout = l = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0,5,0,0)

        x = QToolButton(self)
        x.setText(_('Vi&rtual Library'))
        x.setIcon(QIcon(I('lt.png')))
        x.setObjectName("virtual_library")
        x.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(x)
        parent.virtual_library = x

        x = QLabel(self)
        x.setObjectName("search_count")
        l.addWidget(x)
        parent.search_count = x
        x.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        parent.advanced_search_button = x = QToolButton(self)
        parent.advanced_search_toggle_action = ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('advanced search toggle',
                _('Advanced search'), default_keys=(_("Shift+Ctrl+F"),),
                action=ac)
        ac.triggered.connect(x.click)
        x.setIcon(QIcon(I('search.png')))
        l.addWidget(x)
        x.setToolTip(_("Advanced search"))

        x = parent.search = SearchBox2(self)
        x.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        x.setObjectName("search")
        x.setToolTip(_("<p>Search the list of books by title, author, publisher, "
                       "tags, comments, etc.<br><br>Words separated by spaces are ANDed"))
        x.setMinimumContentsLength(10)
        l.addWidget(x)

        self.search_button = QToolButton()
        self.search_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.search_button.setText(_('&Go!'))
        l.addWidget(self.search_button)
        self.search_button.setSizePolicy(QSizePolicy.Minimum,
                QSizePolicy.Minimum)
        self.search_button.clicked.connect(parent.do_search_button)
        self.search_button.setToolTip(
            _('Do Quick Search (you can also press the Enter key)'))

        x = parent.clear_button = QToolButton(self)
        x.setIcon(QIcon(I('clear_left.png')))
        x.setObjectName("clear_button")
        l.addWidget(x)
        x.setToolTip(_("Reset Quick Search"))

        x = parent.highlight_only_button = QToolButton(self)
        x.setIcon(QIcon(I('arrow-down.png')))
        l.addWidget(x)

        x = parent.saved_search = SavedSearchBox(self)
        x.setMaximumSize(QSize(150, 16777215))
        x.setMinimumContentsLength(10)
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

# }}}

class Spacer(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = QHBoxLayout()
        self.setLayout(self.l)
        self.l.addStretch(10)
# }}}

class MainWindowMixin(object):  # {{{

    def __init__(self, db):
        self.setObjectName('MainWindow')
        self.setWindowIcon(QIcon(I('lt.png')))
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
        self.bars_manager = BarsManager(self.donate_button,
                self.location_manager, self)
        for bar in self.bars_manager.main_bars:
            self.addToolBar(Qt.TopToolBarArea, bar)
        for bar in self.bars_manager.child_bars:
            self.addToolBar(Qt.BottomToolBarArea, bar)
        self.bars_manager.update_bars()
        # This is disabled because it introduces various toolbar related bugs
        # The width of the toolbar becomes the sum of both toolbars
        if tweaks['unified_title_toolbar_on_osx']:
            self.setUnifiedTitleAndToolBarOnMac(True)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)

# }}}




