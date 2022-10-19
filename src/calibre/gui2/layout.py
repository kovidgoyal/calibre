#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from qt.core import (
    QActionGroup, QCoreApplication, QFrame, QHBoxLayout, QIcon, QLabel, QLineEdit,
    QMenu, QObject, QSizePolicy, Qt, QToolButton, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import human_readable
from calibre.constants import __appname__
from calibre.gui2.bars import BarsManager
from calibre.gui2.search_box import SearchBox2
from calibre.utils.config_base import tweaks


class LocationManager(QObject):  # {{{

    locations_changed = pyqtSignal()
    unmount_device = pyqtSignal()
    location_selected = pyqtSignal(object)
    configure_device = pyqtSignal()
    update_device_metadata = pyqtSignal()

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
            icon = QIcon.ic(icon)
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
                a = m.addAction(QIcon.ic('eject.png'), _('Eject this device'))
                a.triggered.connect(self._eject_requested)
                self._mem.append(a)
                a = m.addAction(QIcon.ic('config.png'), _('Configure this device'))
                a.triggered.connect(self._configure_requested)
                self._mem.append(a)
                a = m.addAction(QIcon.ic('sync.png'), _('Update cached metadata on device'))
                a.triggered.connect(lambda x : self.update_device_metadata.emit())
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
        self.location_main.setIcon(QIcon.ic(icon or 'reader.png'))
        had_device = self.has_device
        if cp is None:
            cp = (None, None)
        if isinstance(cp, (bytes, str)):
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
                t += '\n\n%s '%human_readable(self.free[i]) + _('available')
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


def search_as_url(text):
    if text:
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db
        lid = db.new_api.server_library_id
        lid = lid.encode('utf-8').hex()
        eq = text.encode('utf-8').hex()
        vl = db.data.get_base_restriction_name()
        ans = f'calibre://search/_hex_-{lid}?eq={eq}'
        if vl:
            vl = vl.encode('utf-8').hex()
            ans += '&encoded_virtual_library=' + vl
        return ans


class SearchBar(QFrame):  # {{{

    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setObjectName('search_bar')
        self._layout = l = QHBoxLayout(self)
        l.setContentsMargins(0, 4, 0, 4)

        x = parent.virtual_library = QToolButton(self)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        x.setText(_('Virtual library'))
        x.setAutoRaise(True)
        x.setIcon(QIcon.ic('vl.png'))
        x.setObjectName("virtual_library")
        x.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        l.addWidget(x)

        x = QToolButton(self)
        x.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        x.setAutoRaise(True)
        x.setIcon(QIcon.ic('minus.png'))
        x.setObjectName('clear_vl')
        l.addWidget(x)
        x.setVisible(False)
        x.setToolTip(_('Close the Virtual library'))
        parent.clear_vl = x

        parent.sort_button = self.sort_button = sb = QToolButton(self)
        sb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        sb.setToolTip(_('Change how the displayed books are sorted'))
        sb.setCursor(Qt.CursorShape.PointingHandCursor)
        sb.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        sb.setAutoRaise(True)
        sb.setText(_('Sort'))
        sb.setIcon(QIcon.ic('sort.png'))
        sb.setMenu(QMenu(sb))
        sb.menu().aboutToShow.connect(self.populate_sort_menu)
        sb.setVisible(False)
        l.addWidget(sb)

        x = parent.search = SearchBox2(self, as_url=search_as_url)
        x.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        x.setObjectName("search")
        x.setToolTip(_("<p>Search the list of books by title, author, publisher, "
                       "tags, comments, etc.<br><br>Words separated by spaces are ANDed"))
        x.setMinimumContentsLength(10)
        l.addWidget(x)

        parent.full_text_search_action = ac = parent.search.add_action('fts.png', QLineEdit.ActionPosition.LeadingPosition)
        ac.setToolTip('<p>' + _('Search the full text of all books in the library, not just their metadata'))
        ac.triggered.connect(self.do_fts)

        parent.advanced_search_toggle_action = ac = parent.search.add_action('gear.png', QLineEdit.ActionPosition.LeadingPosition)
        parent.addAction(ac)
        ac.setToolTip(_('Advanced search'))
        parent.keyboard.register_shortcut('advanced search toggle',
                _('Advanced search'), default_keys=("Shift+Ctrl+F",),
                action=ac)

        self.search_button = QToolButton()
        self.search_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.search_button.setIcon(QIcon.ic('search.png'))
        self.search_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.search_button.setText(_('Search'))
        self.search_button.setAutoRaise(True)
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        l.addWidget(self.search_button)
        self.search_button.setSizePolicy(QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Minimum)
        self.search_button.clicked.connect(parent.do_search_button)
        self.search_button.setToolTip(
            _('Do quick search (you can also press the Enter key)'))

        x = parent.highlight_only_button = QToolButton(self)
        x.setAutoRaise(True)
        x.setText(_('Highlight'))
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        x.setIcon(QIcon.ic('arrow-down.png'))
        l.addWidget(x)

        # Add the searchbar tool buttons to the bar
        l.addLayout(self.parent().bars_manager.search_tool_bar)

    def populate_sort_menu(self):
        from calibre.gui2.ui import get_gui
        get_gui().iactions['Sort By'].update_menu(self.sort_button.menu())

    def do_fts(self):
        from calibre.gui2.ui import get_gui
        get_gui().iactions['Full Text Search'].show_fts()

# }}}


class Spacer(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = QHBoxLayout()
        self.setLayout(self.l)
        self.l.addStretch(10)
# }}}


class MainWindowMixin:  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def init_main_window_mixin(self):
        self.setObjectName('MainWindow')
        self.setWindowIcon(QIcon.ic('lt.png'))
        self.setWindowTitle(__appname__)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self._central_widget_layout = l = QVBoxLayout(self.centralwidget)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        self.resize(1012, 740)
        self.location_manager = LocationManager(self)

        self.iactions['Fetch News'].init_scheduler()

        self.bars_manager = BarsManager(self.donate_action,
                self.location_manager, self)
        # instantiating SearchBar must happen after setting bars manager
        self.search_bar = SearchBar(self)
        for bar in self.bars_manager.main_bars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
            bar.setStyleSheet('QToolBar { border: 0px }')
        for bar in self.bars_manager.child_bars:
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bar)
            bar.setStyleSheet('QToolBar { border: 0px }')
        self.bars_manager.update_bars()
        # This is disabled because it introduces various toolbar related bugs
        # The width of the toolbar becomes the sum of both toolbars
        if tweaks['unified_title_toolbar_on_osx']:
            try:
                self.setUnifiedTitleAndToolBarOnMac(True)
            except AttributeError:
                pass  # PyQt seems to be missing this property

        # And now, start adding the real widgets
        l.addWidget(self.search_bar)

        # Add in the widget for the shutdown messages. It is invisible until a
        # message is shown
        smw = self.shutdown_message_widget = QLabel(self)
        smw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        smw.setVisible(False)
        smw.setAutoFillBackground(True)
        smw.setStyleSheet('QLabel { background-color: rgba(200, 200, 200, 200); color: black }')

    def show_shutdown_message(self, message=''):
        smw = self.shutdown_message_widget
        smw.setGeometry(0, 0, self.width(), self.height())
        smw.setVisible(True)
        smw.raise_()
        smw.setText(_('<h2>Shutting down</h2><div>') + message)
        # Force processing the events needed to show the message
        QCoreApplication.processEvents()
# }}}
