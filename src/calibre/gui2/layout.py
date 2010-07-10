#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QIcon, Qt, QWidget, QAction, QToolBar, QSize, QVariant, \
    QAbstractListModel, QFont, QApplication, QPalette, pyqtSignal, QToolButton, \
    QModelIndex, QListView, QAbstractButton, QPainter, QPixmap, QColor, \
    QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout, QComboBox

from calibre.constants import __appname__, filesystem_encoding
from calibre.gui2.search_box import SearchBox2, SavedSearchBox
from calibre.gui2.throbber import ThrobbingButton
from calibre.gui2 import NONE
from calibre import human_readable

class ToolBar(QToolBar): # {{{

    def __init__(self, parent=None):
        QToolBar.__init__(self, parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea)
        self.setIconSize(QSize(48, 48))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

    def add_actions(self, *args):
        self.left_space = QWidget(self)
        self.left_space.setSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Minimum)
        self.addWidget(self.left_space)
        for action in args:
            if action is None:
                self.addSeparator()
            else:
                self.addAction(action)
        self.right_space = QWidget(self)
        self.right_space.setSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Minimum)
        self.addWidget(self.right_space)

    def contextMenuEvent(self, *args):
        pass

# }}}

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
        self.setIconSize(QSize(40, 40))
        self.setMovement(self.Static)
        self.setFlow(self.LeftToRight)
        self.setGridSize(QSize(175, 90))
        self.setViewMode(self.ListMode)
        self.setWordWrap(True)
        self.setObjectName("location_view")
        self.setMaximumHeight(74)

    def eject_clicked(self, *args):
        self.unmount_device.emit()

    def count_changed(self, new_count):
        self.model().count = new_count
        self.model().reset()

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

    def enterEvent(self, event):
        self.mouse_over = True

    def leaveEvent(self, event):
        self.mouse_over = False

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

        self.restriction_label = QLabel(_("&Restrict to:"))
        l.addWidget(self.restriction_label)
        self.restriction_label.setSizePolicy(QSizePolicy.Minimum,
                QSizePolicy.Minimum)

        x = QComboBox(self)
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
        self.restriction_label.setBuddy(parent.search_restriction)


# }}}

class LocationBar(ToolBar): # {{{

    def __init__(self, actions, donate, location_view, parent=None):
        ToolBar.__init__(self, parent)

        for ac in actions:
            self.addAction(ac)

        self.addWidget(location_view)
        self.w = QWidget()
        self.w.setLayout(QVBoxLayout())
        self.w.layout().addWidget(donate)
        donate.setAutoRaise(True)
        donate.setCursor(Qt.PointingHandCursor)
        self.addWidget(self.w)
        self.setIconSize(QSize(50, 50))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

    def button_for_action(self, ac):
        b = QToolButton(self)
        b.setDefaultAction(ac)
        for x in ('ToolTip', 'StatusTip', 'WhatsThis'):
            getattr(b, 'set'+x)(b.text())

        return b
# }}}

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
        self.donate_button.set_normal_icon_size(64, 64)

        # Actions {{{

        def ac(name, text, icon, shortcut=None, tooltip=None):
            action = QAction(QIcon(I(icon)), text, self)
            text = tooltip if tooltip else text
            action.setToolTip(text)
            action.setStatusTip(text)
            action.setWhatsThis(text)
            action.setAutoRepeat(False)
            action.setObjectName('action_'+name)
            if shortcut:
                action.setShortcut(shortcut)
            setattr(self, 'action_'+name, action)

        ac('add', _('Add books'), 'add_book.svg', _('A'))
        ac('del', _('Remove books'), 'trash.svg', _('Del'))
        ac('edit', _('Edit meta info'), 'edit_input.svg', _('E'))
        ac('merge', _('Merge book records'), 'merge_books.svg', _('M'))
        ac('sync', _('Send to device'), 'sync.svg')
        ac('save', _('Save to disk'), 'save.svg', _('S'))
        ac('news', _('Fetch news'), 'news.svg', _('F'))
        ac('convert', _('Convert books'), 'convert.svg', _('C'))
        ac('view', _('View'), 'view.svg', _('V'))
        ac('open_containing_folder', _('Open containing folder'),
                'document_open.svg')
        ac('show_book_details', _('Show book details'),
                'dialog_information.svg')
        ac('books_by_same_author', _('Books by same author'),
                'user_profile.svg')
        ac('books_in_this_series', _('Books in this series'),
                'books_in_series.svg')
        ac('books_by_this_publisher', _('Books by this publisher'),
                'publisher.png')
        ac('books_with_the_same_tags', _('Books with the same tags'),
                'tags.svg')
        ac('preferences', _('Preferences'), 'config.svg', _('Ctrl+P'))
        ac('help', _('Help'), 'help.svg', _('F1'), _("Browse the calibre User Manual"))

        # }}}

        self.tool_bar = ToolBar(self)
        self.addToolBar(Qt.BottomToolBarArea, self.tool_bar)
        self.tool_bar.add_actions(self.action_convert, self.action_view,
                None, self.action_edit, None,
                self.action_save, self.action_del,
                None,
                self.action_help, None, self.action_preferences)

        self.location_view = LocationView(self.centralwidget)
        self.search_bar = SearchBar(self)
        self.location_bar = LocationBar([self.action_add, self.action_sync,
            self.action_news], self.donate_button, self.location_view, self)
        self.addToolBar(Qt.TopToolBarArea, self.location_bar)

        l = self.centralwidget.layout()
        l.addWidget(self.search_bar)

        for ch in list(self.tool_bar.children()) + list(self.location_bar.children()):
            if isinstance(ch, QToolButton):
                ch.setCursor(Qt.PointingHandCursor)
                ch.setAutoRaise(True)
                if ch is not self.donate_button:
                    ch.setPopupMode(ch.MenuButtonPopup)



