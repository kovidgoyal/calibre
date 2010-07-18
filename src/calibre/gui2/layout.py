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
    QMenu, QUrl

from calibre.constants import __appname__, isosx
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2 import config, open_url
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre import human_readable
from calibre.utils.config import prefs
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2.dialogs.scheduler import Scheduler

ICON_SIZE = 48

class SaveMenu(QMenu): # {{{

    save_fmt = pyqtSignal(object)

    def __init__(self, parent):
        QMenu.__init__(self, _('Save single format to disk...'), parent)
        for ext in sorted(BOOK_EXTENSIONS):
            action = self.addAction(ext.upper())
            setattr(self, 'do_'+ext, partial(self.do, ext))
            action.triggered.connect(
                    getattr(self, 'do_'+ext))

    def do(self, ext, *args):
        self.save_fmt.emit(ext)

# }}}

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
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setStyleSheet('QToolButton:checked { font-weight: bold }')

        self.all_actions = actions
        self.donate = donate
        self.location_manager = location_manager
        self.location_manager.locations_changed.connect(self.build_bar)
        self.d_widget = QWidget()
        self.d_widget.setLayout(QVBoxLayout())
        self.d_widget.layout().addWidget(donate)
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.build_bar()

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
                ch.setPopupMode(ch.MenuButtonPopup)

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

    def count_changed(self, new_count):
        text = _('%d books')%new_count
        a = self.choose_action
        a.setText(text)

    def resizeEvent(self, ev):
        style = Qt.ToolButtonTextUnderIcon
        if self.size().width() < 1260:
            style = Qt.ToolButtonIconOnly
        self.setToolButtonStyle(style)
        QToolBar.resizeEvent(self, ev)

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
        self.donate_button.set_normal_icon_size(ICON_SIZE, ICON_SIZE)
        self.location_manager = LocationManager(self)

        self.init_scheduler(db)
        all_actions = self.setup_actions()

        self.search_bar = SearchBar(self)
        self.tool_bar = ToolBar(all_actions, self.donate_button,
                self.location_manager, self)
        self.addToolBar(Qt.TopToolBarArea, self.tool_bar)
        self.tool_bar.choose_action.triggered.connect(self.choose_library)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)

    def init_scheduler(self, db):
        self.scheduler = Scheduler(self, db)
        self.scheduler.start_recipe_fetch.connect(
                self.download_scheduled_recipe, type=Qt.QueuedConnection)


    def read_toolbar_settings(self):
        pass

    def choose_library(self, *args):
        from calibre.gui2.dialogs.choose_library import ChooseLibrary
        db = self.library_view.model().db
        c = ChooseLibrary(db, self.library_moved, self)
        c.exec_()

    def setup_actions(self): # {{{
        all_actions = []

        def ac(normal_order, device_order, separator_before,
                name, text, icon, shortcut=None, tooltip=None):
            action = Action(QIcon(I(icon)), text, self)
            action.normal_order = normal_order
            action.device_order = device_order
            action.separator_before = separator_before
            action.action_name = name
            text = tooltip if tooltip else text
            action.setToolTip(text)
            action.setStatusTip(text)
            action.setWhatsThis(text)
            action.setAutoRepeat(False)
            action.setObjectName('action_'+name)
            if shortcut:
                action.setShortcut(shortcut)
            setattr(self, 'action_'+name, action)
            all_actions.append(action)

        ac(0,  7,  0, 'add', _('Add books'), 'add_book.svg', _('A'))
        ac(1,  1,  0, 'edit', _('Edit metadata'), 'edit_input.svg', _('E'))
        ac(2,  2,  3, 'convert', _('Convert books'), 'convert.svg', _('C'))
        ac(3,  3,  0, 'view', _('View'), 'view.svg', _('V'))
        ac(4,  4,  3, 'choose_library', _('%d books')%0, 'lt.png',
                tooltip=_('Choose calibre library to work with'))
        ac(5,  5,  3, 'news', _('Fetch news'), 'news.svg', _('F'))
        ac(6,  6,  0, 'save', _('Save to disk'), 'save.svg', _('S'))
        ac(7,  0,  0, 'sync', _('Send to device'), 'sync.svg')
        ac(8,  8,  3, 'del', _('Remove books'), 'trash.svg', _('Del'))
        ac(9,  9,  3, 'help', _('Help'), 'help.svg', _('F1'), _("Browse the calibre User Manual"))
        ac(10, 10, 0, 'preferences', _('Preferences'), 'config.svg', _('Ctrl+P'))

        ac(-1, -1, 0, 'merge', _('Merge book records'), 'merge_books.svg', _('M'))
        ac(-1, -1, 0, 'open_containing_folder', _('Open containing folder'),
                'document_open.svg')
        ac(-1, -1, 0, 'show_book_details', _('Show book details'),
                'dialog_information.svg')
        ac(-1, -1, 0, 'books_by_same_author', _('Books by same author'),
                'user_profile.svg')
        ac(-1, -1, 0, 'books_in_this_series', _('Books in this series'),
                'books_in_series.svg')
        ac(-1, -1, 0, 'books_by_this_publisher', _('Books by this publisher'),
                'publisher.png')
        ac(-1, -1, 0, 'books_with_the_same_tags', _('Books with the same tags'),
                'tags.svg')

        self.action_news.setMenu(self.scheduler.news_menu)
        self.action_news.triggered.connect(
                self.scheduler.show_dialog)

        self.action_help.triggered.connect(self.show_help)
        md = QMenu()
        md.addAction(_('Edit metadata individually'),
                partial(self.edit_metadata, False, bulk=False))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'),
                partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        md.addAction(_('Download metadata and covers'),
                partial(self.download_metadata, False, covers=True),
                Qt.ControlModifier+Qt.Key_D)
        md.addAction(_('Download only metadata'),
                partial(self.download_metadata, False, covers=False))
        md.addAction(_('Download only covers'),
                partial(self.download_metadata, False, covers=True,
                    set_metadata=False, set_social_metadata=False))
        md.addAction(_('Download only social metadata'),
                partial(self.download_metadata, False, covers=False,
                    set_metadata=False, set_social_metadata=True))
        self.metadata_menu = md

        mb = QMenu()
        mb.addAction(_('Merge into first selected book - delete others'),
                self.merge_books)
        mb.addSeparator()
        mb.addAction(_('Merge into first selected book - keep others'),
                partial(self.merge_books, safe_merge=True))
        self.merge_menu = mb
        self.action_merge.setMenu(mb)
        md.addSeparator()
        md.addAction(self.action_merge)

        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'),
                self.add_books)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub-directories (One book per directory, assumes every ebook '
            'file is the same book in a different format)'),
            self.add_recursive_single)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub directories (Multiple books per directory, assumes every '
            'ebook file is a different book)'), self.add_recursive_multiple)
        self.add_menu.addAction(_('Add Empty book. (Book entry with no '
            'formats)'), self.add_empty)
        self.action_add.setMenu(self.add_menu)
        self.action_add.triggered.connect(self.add_books)
        self.action_del.triggered.connect(self.delete_books)
        self.action_edit.triggered.connect(self.edit_metadata)
        self.action_merge.triggered.connect(self.merge_books)

        self.action_save.triggered.connect(self.save_to_disk)
        self.save_menu = QMenu()
        self.save_menu.addAction(_('Save to disk'), partial(self.save_to_disk,
            False))
        self.save_menu.addAction(_('Save to disk in a single directory'),
                partial(self.save_to_single_dir, False))
        self.save_menu.addAction(_('Save only %s format to disk')%
                prefs['output_format'].upper(),
                partial(self.save_single_format_to_disk, False))
        self.save_menu.addAction(
                _('Save only %s format to disk in a single directory')%
                prefs['output_format'].upper(),
                partial(self.save_single_fmt_to_single_dir, False))
        self.save_sub_menu = SaveMenu(self)
        self.save_menu.addMenu(self.save_sub_menu)
        self.save_sub_menu.save_fmt.connect(self.save_specific_format_disk)

        self.action_view.triggered.connect(self.view_book)
        self.view_menu = QMenu()
        self.view_menu.addAction(_('View'), partial(self.view_book, False))
        ac = self.view_menu.addAction(_('View specific format'))
        ac.setShortcut((Qt.ControlModifier if isosx else Qt.AltModifier)+Qt.Key_V)
        self.action_view.setMenu(self.view_menu)
        ac.triggered.connect(self.view_specific_format, type=Qt.QueuedConnection)

        self.delete_menu = QMenu()
        self.delete_menu.addAction(_('Remove selected books'), self.delete_books)
        self.delete_menu.addAction(
                _('Remove files of a specific format from selected books..'),
                self.delete_selected_formats)
        self.delete_menu.addAction(
                _('Remove all formats from selected books, except...'),
                self.delete_all_but_selected_formats)
        self.delete_menu.addAction(
                _('Remove covers from selected books'), self.delete_covers)
        self.delete_menu.addSeparator()
        self.delete_menu.addAction(
                _('Remove matching books from device'),
                self.remove_matching_books_from_device)
        self.action_del.setMenu(self.delete_menu)

        self.action_open_containing_folder.setShortcut(Qt.Key_O)
        self.addAction(self.action_open_containing_folder)
        self.action_open_containing_folder.triggered.connect(self.view_folder)
        self.action_sync.setShortcut(Qt.Key_D)
        self.action_sync.setEnabled(True)
        self.create_device_menu()
        self.action_sync.triggered.connect(
                self._sync_action_triggered)

        self.action_edit.setMenu(md)
        self.action_save.setMenu(self.save_menu)

        cm = QMenu()
        cm.addAction(_('Convert individually'), partial(self.convert_ebook,
            False, bulk=False))
        cm.addAction(_('Bulk convert'),
                partial(self.convert_ebook, False, bulk=True))
        cm.addSeparator()
        ac = cm.addAction(
                _('Create catalog of books in your calibre library'))
        ac.triggered.connect(self.generate_catalog)
        self.action_convert.setMenu(cm)
        self.action_convert.triggered.connect(self.convert_ebook)
        self.convert_menu = cm

        pm = QMenu()
        pm.addAction(QIcon(I('config.svg')), _('Preferences'), self.do_config)
        pm.addAction(QIcon(I('wizard.svg')), _('Run welcome wizard'),
                self.run_wizard)
        self.action_preferences.setMenu(pm)
        self.preferences_menu = pm
        for x in (self.preferences_action, self.action_preferences):
            x.triggered.connect(self.do_config)

        return all_actions
    # }}}

    def show_help(self, *args):
        open_url(QUrl('http://calibre-ebook.com/user_manual'))


