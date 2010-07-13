#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt4.Qt import QIcon, Qt, QWidget, QAction, QToolBar, QSize, QVariant, \
    QAbstractListModel, QFont, QApplication, QPalette, pyqtSignal, QToolButton, \
    QModelIndex, QListView, QAbstractButton, QPainter, QPixmap, QColor, \
    QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout

from calibre.constants import __appname__, filesystem_encoding
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2 import NONE, config
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre import human_readable

ICON_SIZE = 48

# Location View {{{

class LocationModel(QAbstractListModel): # {{{

    devicesChanged = pyqtSignal()

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.icons = [QVariant(QIcon(I('library.png'))),
                      QVariant(QIcon(I('reader.svg'))),
                      QVariant(QIcon(I('sd.svg'))),
                      QVariant(QIcon(I('sd.svg')))]
        self.text = [_('Library\n%d books'),
                     _('Reader\n%s'),
                     _('Card A\n%s'),
                     _('Card B\n%s')]
        self.free = [-1, -1, -1]
        self.count = 0
        self.highlight_row = 0
        self.library_tooltip = _('Click to see the books available on your computer')
        self.tooltips = [
                         self.library_tooltip,
                         _('Click to see the books in the main memory of your reader'),
                         _('Click to see the books on storage card A in your reader'),
                         _('Click to see the books on storage card B in your reader')
                         ]

    def database_changed(self, db):
        lp = db.library_path
        if not isinstance(lp, unicode):
            lp = lp.decode(filesystem_encoding, 'replace')
        self.tooltips[0] = self.library_tooltip + '\n\n' + \
                _('Books located at') + ' ' + lp
        self.dataChanged.emit(self.index(0), self.index(0))

    def rowCount(self, *args):
        return 1 + len([i for i in self.free if i >= 0])

    def get_device_row(self, row):
        if row == 2 and self.free[1] == -1 and self.free[2] > -1:
            row = 3
        return row

    def get_tooltip(self, row, drow):
        ans = self.tooltips[row]
        if row > 0:
            fs = self.free[drow-1]
            if fs > -1:
                ans += '\n\n%s '%(human_readable(fs)) + _('free')
        return ans

    def data(self, index, role):
        row = index.row()
        drow = self.get_device_row(row)
        data = NONE
        if role == Qt.DisplayRole:
            text = self.text[drow]%(human_readable(self.free[drow-1])) if row > 0 \
                            else self.text[drow]%self.count
            data = QVariant(text)
        elif role == Qt.DecorationRole:
            data = self.icons[drow]
        elif role in (Qt.ToolTipRole, Qt.StatusTipRole):
            ans = self.get_tooltip(row, drow)
            data = QVariant(ans)
        elif role == Qt.SizeHintRole:
            data = QVariant(QSize(155, 90))
        elif role == Qt.FontRole:
            font = QFont('monospace')
            font.setBold(row == self.highlight_row)
            data = QVariant(font)
        elif role == Qt.ForegroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.HighlightedText))
        elif role == Qt.BackgroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.Highlight))

        return data

    def device_connected(self, dev):
        self.icons[1] = QIcon(dev.icon)
        self.dataChanged.emit(self.index(1), self.index(1))

    def headerData(self, section, orientation, role):
        return NONE

    def update_devices(self, cp=(None, None), fs=[-1, -1, -1]):
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
        self.reset()
        self.devicesChanged.emit()

    def location_changed(self, row):
        self.highlight_row = row
        self.dataChanged.emit(
                self.index(0), self.index(self.rowCount(QModelIndex())-1))

    def location_for_row(self, row):
        if row == 0: return 'library'
        if row == 1: return 'main'
        if row == 3: return 'cardb'
        return 'carda' if self.free[1] > -1 else 'cardb'

# }}}

class LocationView(QListView):

    unmount_device = pyqtSignal()
    location_selected = pyqtSignal(object)

    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setModel(LocationModel(self))
        self.reset()
        self.currentChanged = self.current_changed

        self.eject_button = EjectButton(self)
        self.eject_button.hide()

        self.entered.connect(self.item_entered)
        self.viewportEntered.connect(self.viewport_entered)
        self.eject_button.clicked.connect(self.eject_clicked)
        self.model().devicesChanged.connect(self.eject_button.hide)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
            QSizePolicy.Expanding))
        self.setMouseTracking(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setEditTriggers(self.NoEditTriggers)
        self.setTabKeyNavigation(True)
        self.setProperty("showDropIndicator", True)
        self.setSelectionMode(self.SingleSelection)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setMovement(self.Static)
        self.setFlow(self.LeftToRight)
        self.setGridSize(QSize(175, ICON_SIZE))
        self.setViewMode(self.ListMode)
        self.setWordWrap(True)
        self.setObjectName("location_view")
        self.setMaximumSize(QSize(600, ICON_SIZE+16))
        self.setMinimumWidth(400)

    def eject_clicked(self, *args):
        self.unmount_device.emit()

    def count_changed(self, new_count):
        self.model().count = new_count
        self.model().reset()

    @property
    def book_count(self):
        return self.model().count

    def current_changed(self, current, previous):
        if current.isValid():
            i = current.row()
            location = self.model().location_for_row(i)
            self.location_selected.emit(location)
            self.model().location_changed(i)

    def location_changed(self, row):
        if 0 <= row and row <= 3:
            self.model().location_changed(row)

    def leaveEvent(self, event):
        self.unsetCursor()
        self.eject_button.hide()

    def item_entered(self, location):
        self.setCursor(Qt.PointingHandCursor)
        self.eject_button.hide()

        if location.row() == 1:
            rect = self.visualRect(location)

            self.eject_button.resize(rect.height()/2, rect.height()/2)

            x, y = rect.left(), rect.top()
            x = x + (rect.width() - self.eject_button.width() - 2)
            y += 6

            self.eject_button.move(x, y)
            self.eject_button.show()

    def viewport_entered(self):
        self.unsetCursor()
        self.eject_button.hide()


class EjectButton(QAbstractButton):

    def __init__(self, parent):
        QAbstractButton.__init__(self, parent)
        self.mouse_over = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.mouse_over = True
        QAbstractButton.enterEvent(self, event)

    def leaveEvent(self, event):
        self.mouse_over = False
        QAbstractButton.leaveEvent(self, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        image = QPixmap(I('eject')).scaledToHeight(event.rect().height(),
            Qt.SmoothTransformation)

        if not self.mouse_over:
            alpha_mask = QPixmap(image.width(), image.height())
            color = QColor(128, 128, 128)
            alpha_mask.fill(color)
            image.setAlphaChannel(alpha_mask)

        painter.drawPixmap(0, 0, image)




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

    def __init__(self, actions, donate, location_view, parent=None):
        QToolBar.__init__(self, parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        self.showing_device = False
        self.all_actions = actions
        self.donate = donate
        self.location_view = location_view
        self.d_widget = QWidget()
        self.d_widget.setLayout(QVBoxLayout())
        self.d_widget.layout().addWidget(donate)
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.build_bar()

    def contextMenuEvent(self, *args):
        pass

    def device_status_changed(self, connected):
        self.showing_device = connected
        self.build_bar()

    def build_bar(self):
        order_field = 'device' if self.showing_device else 'normal'
        o = attrgetter(order_field+'_order')
        sepvals = [2] if self.showing_device else [1]
        sepvals += [3]
        actions = [x for x in self.all_actions if o(x) > -1]
        actions.sort(cmp=lambda x,y : cmp(o(x), o(y)))
        self.clear()
        for x in actions:
            self.addAction(x)
            ch = self.widgetForAction(x)
            ch.setCursor(Qt.PointingHandCursor)
            ch.setAutoRaise(True)

            if x.action_name == 'choose_library':
                self.location_action = self.addWidget(self.location_view)
                self.choose_action = x
                if config['show_donate_button']:
                    self.addWidget(self.d_widget)
            if x.action_name not in ('choose_library', 'help'):
                ch.setPopupMode(ch.MenuButtonPopup)


        for x in actions:
            if x.separator_before in sepvals:
                self.insertSeparator(x)


        self.location_action.setVisible(self.showing_device)
        self.choose_action.setVisible(not self.showing_device)

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

# }}}

class Action(QAction):
    pass

class MainWindowMixin(object):

    def __init__(self):
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

        # Actions {{{

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

        # }}}

        self.location_view = LocationView(self.centralwidget)
        self.search_bar = SearchBar(self)
        self.tool_bar = ToolBar(all_actions, self.donate_button, self.location_view, self)
        self.addToolBar(Qt.TopToolBarArea, self.tool_bar)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)


    def read_toolbar_settings(self):
        pass

