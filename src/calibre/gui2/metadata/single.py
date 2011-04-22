#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import (Qt, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
        QGridLayout, pyqtSignal, QDialogButtonBox, QScrollArea, QFont,
        QTabWidget, QIcon, QToolButton, QSplitter, QGroupBox, QSpacerItem,
        QSizePolicy, QPalette, QFrame, QSize, QKeySequence, QMenu)

from calibre.ebooks.metadata import authors_to_string, string_to_authors
from calibre.gui2 import ResizableDialog, error_dialog, gprefs, pixmap_to_data
from calibre.gui2.metadata.basic_widgets import (TitleEdit, AuthorsEdit,
    AuthorSortEdit, TitleSortEdit, SeriesEdit, SeriesIndexEdit, IdentifiersEdit,
    RatingEdit, PublisherEdit, TagsEdit, FormatsManager, Cover, CommentsEdit,
    BuddyLabel, DateEdit, PubdateEdit)
from calibre.gui2.metadata.single_download import FullFetch
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre.utils.config import tweaks
from calibre.ebooks.metadata.book.base import Metadata

class MetadataSingleDialogBase(ResizableDialog):

    view_format = pyqtSignal(object, object)
    cc_two_column = tweaks['metadata_single_use_2_cols_for_custom_fields']
    one_line_comments_toolbar = False

    def __init__(self, db, parent=None):
        self.db = db
        self.changed = set()
        self.books_to_refresh = set()
        self.rows_to_refresh = set()
        ResizableDialog.__init__(self, parent)

    def setupUi(self, *args): # {{{
        self.resize(990, 650)

        self.button_box = QDialogButtonBox(
                QDialogButtonBox.Ok|QDialogButtonBox.Cancel, Qt.Horizontal,
                self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.next_button = QPushButton(QIcon(I('forward.png')), _('Next'),
                self)
        self.next_button.setShortcut(QKeySequence('Alt+Right'))
        self.next_button.clicked.connect(partial(self.do_one, delta=1))
        self.prev_button = QPushButton(QIcon(I('back.png')), _('Previous'),
                self)
        self.prev_button.setShortcut(QKeySequence('Alt+Left'))

        self.button_box.addButton(self.prev_button, self.button_box.ActionRole)
        self.button_box.addButton(self.next_button, self.button_box.ActionRole)
        self.prev_button.clicked.connect(partial(self.do_one, delta=-1))

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.central_widget = QTabWidget(self)
        self.scroll_area.setWidget(self.central_widget)

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)
        self.l.setMargin(0)
        self.l.addWidget(self.scroll_area)
        self.l.addWidget(self.button_box)

        self.setWindowIcon(QIcon(I('edit_input.png')))
        self.setWindowTitle(_('Edit Metadata'))

        self.create_basic_metadata_widgets()

        if len(self.db.custom_column_label_map):
            self.create_custom_metadata_widgets()


        self.do_layout()
        geom = gprefs.get('metasingle_window_geometry3', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))
    # }}}

    def create_basic_metadata_widgets(self): # {{{
        self.basic_metadata_widgets = []

        self.title = TitleEdit(self)
        self.title.textChanged.connect(self.update_window_title)
        self.deduce_title_sort_button = QToolButton(self)
        self.deduce_title_sort_button.setToolTip(
            _('Automatically create the title sort entry based on the current '
                'title entry.\nUsing this button to create title sort will '
                'change title sort from red to green.'))
        self.deduce_title_sort_button.setWhatsThis(
                self.deduce_title_sort_button.toolTip())
        self.title_sort = TitleSortEdit(self, self.title,
                self.deduce_title_sort_button)
        self.basic_metadata_widgets.extend([self.title, self.title_sort])

        self.deduce_author_sort_button = b = QToolButton(self)
        b.setToolTip(_(
        'Automatically create the author sort entry based on the current'
        ' author entry.\n'
        'Using this button to create author sort will change author sort from'
        ' red to green.'))
        b.m = m = QMenu()
        ac = m.addAction(QIcon(I('forward.png')), _('Set author sort from author'))
        ac2 = m.addAction(QIcon(I('back.png')), _('Set author from author sort'))
        b.setMenu(m)
        self.authors = AuthorsEdit(self)
        self.author_sort = AuthorSortEdit(self, self.authors, b, self.db, ac,
                ac2)
        self.basic_metadata_widgets.extend([self.authors, self.author_sort])

        self.swap_title_author_button = QToolButton(self)
        self.swap_title_author_button.setIcon(QIcon(I('swap.png')))
        self.swap_title_author_button.setToolTip(_(
            'Swap the author and title'))
        self.swap_title_author_button.clicked.connect(self.swap_title_author)

        self.series = SeriesEdit(self)
        self.remove_unused_series_button = QToolButton(self)
        self.remove_unused_series_button.setToolTip(
               _('Remove unused series (Series that have no books)') )
        self.remove_unused_series_button.clicked.connect(self.remove_unused_series)
        self.series_index = SeriesIndexEdit(self, self.series)
        self.basic_metadata_widgets.extend([self.series, self.series_index])

        self.formats_manager = FormatsManager(self)
        self.basic_metadata_widgets.append(self.formats_manager)
        self.formats_manager.metadata_from_format_button.clicked.connect(
                self.metadata_from_format)
        self.formats_manager.cover_from_format_button.clicked.connect(
                self.cover_from_format)
        self.cover = Cover(self)
        self.cover.download_cover.connect(self.download_cover)
        self.basic_metadata_widgets.append(self.cover)

        self.comments = CommentsEdit(self, self.one_line_comments_toolbar)
        self.basic_metadata_widgets.append(self.comments)

        self.rating = RatingEdit(self)
        self.basic_metadata_widgets.append(self.rating)

        self.tags = TagsEdit(self)
        self.tags_editor_button = QToolButton(self)
        self.tags_editor_button.setToolTip(_('Open Tag Editor'))
        self.tags_editor_button.setIcon(QIcon(I('chapters.png')))
        self.tags_editor_button.clicked.connect(self.tags_editor)
        self.basic_metadata_widgets.append(self.tags)

        self.identifiers = IdentifiersEdit(self)
        self.basic_metadata_widgets.append(self.identifiers)
        self.clear_identifiers_button = QToolButton(self)
        self.clear_identifiers_button.setIcon(QIcon(I('trash.png')))
        self.clear_identifiers_button.clicked.connect(self.identifiers.clear)

        self.publisher = PublisherEdit(self)
        self.basic_metadata_widgets.append(self.publisher)

        self.timestamp = DateEdit(self)
        self.pubdate = PubdateEdit(self)
        self.basic_metadata_widgets.extend([self.timestamp, self.pubdate])

        self.fetch_metadata_button = QPushButton(
                _('&Download metadata'), self)
        self.fetch_metadata_button.clicked.connect(self.fetch_metadata)
        font = self.fmb_font = QFont()
        font.setBold(True)
        self.fetch_metadata_button.setFont(font)

        self.config_metadata_button = QToolButton(self)
        self.config_metadata_button.setIcon(QIcon(I('config.png')))
        self.config_metadata_button.clicked.connect(self.configure_metadata)
        self.config_metadata_button.setToolTip(
            _('Change how calibre downloads metadata'))

    # }}}

    def create_custom_metadata_widgets(self): # {{{
        self.custom_metadata_widgets_parent = w = QWidget(self)
        layout = QGridLayout()
        w.setLayout(layout)
        self.custom_metadata_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, None, parent=w, bulk=False,
                two_column=self.cc_two_column)
        self.__custom_col_layouts = [layout]
    # }}}

    def set_custom_metadata_tab_order(self, before=None, after=None): # {{{
        sto = QWidget.setTabOrder
        if getattr(self, 'custom_metadata_widgets', []):
            ans = self.custom_metadata_widgets
            for i in range(len(ans)-1):
                if before is not None and i == 0:
                    pass# Do something
                if len(ans[i+1].widgets) == 2:
                    sto(ans[i].widgets[-1], ans[i+1].widgets[1])
                else:
                    sto(ans[i].widgets[-1], ans[i+1].widgets[0])
                for c in range(2, len(ans[i].widgets), 2):
                    sto(ans[i].widgets[c-1], ans[i].widgets[c+1])
            if after is not None:
                pass # Do something
    # }}}

    def do_view_format(self, path, fmt):
        if path:
            self.view_format.emit(None, path)
        else:
            self.view_format.emit(self.book_id, fmt)


    def do_layout(self):
        raise NotImplementedError()

    def __call__(self, id_):
        self.book_id = id_
        self.books_to_refresh = set([])
        for widget in self.basic_metadata_widgets:
            widget.initialize(self.db, id_)
        for widget in getattr(self, 'custom_metadata_widgets', []):
            widget.initialize(id_)
        if callable(self.set_current_callback):
            self.set_current_callback(id_)
        # Commented out as it doesn't play nice with Next, Prev buttons
        #self.fetch_metadata_button.setFocus(Qt.OtherFocusReason)


    # Miscellaneous interaction methods {{{
    def update_window_title(self, *args):
        title = self.title.current_val
        if len(title) > 50:
            title = title[:50] + u'\u2026'
        self.setWindowTitle(_('Edit Metadata') + ' - ' +
                title)

    def swap_title_author(self, *args):
        title = self.title.current_val
        self.title.current_val = authors_to_string(self.authors.current_val)
        self.authors.current_val = string_to_authors(title)
        self.title_sort.auto_generate()
        self.author_sort.auto_generate()

    def remove_unused_series(self, *args):
        self.db.remove_unused_series()
        idx = self.series.current_val
        self.series.clear()
        self.series.initialize(self.db, self.book_id)
        if idx:
            for i in range(self.series.count()):
                if unicode(self.series.itemText(i)) == idx:
                    self.series.setCurrentIndex(i)
                    break

    def tags_editor(self, *args):
        self.tags.edit(self.db, self.book_id)

    def metadata_from_format(self, *args):
        mi, ext = self.formats_manager.get_selected_format_metadata(self.db,
                self.book_id)
        if mi is not None:
            self.update_from_mi(mi)

    def cover_from_format(self, *args):
        mi, ext = self.formats_manager.get_selected_format_metadata(self.db,
                self.book_id)
        if mi is None:
            return
        cdata = None
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover).read()
        elif mi.cover_data[1] is not None:
            cdata = mi.cover_data[1]
        if cdata is None:
            error_dialog(self, _('Could not read cover'),
                         _('Could not read cover from %s format')%ext).exec_()
            return
        orig = self.cover.current_val
        self.cover.current_val = cdata
        if self.cover.current_val is None:
            self.cover.current_val = orig
            return error_dialog(self, _('Could not read cover'),
                         _('The cover in the %s format is invalid')%ext,
                         show=True)
            return

    def update_from_mi(self, mi):
        if not mi.is_null('title'):
            self.title.current_val = mi.title
        if not mi.is_null('authors'):
            self.authors.current_val = mi.authors
        if not mi.is_null('author_sort'):
            self.author_sort.current_val = mi.author_sort
        if not mi.is_null('rating'):
            try:
                self.rating.current_val = mi.rating
            except:
                pass
        if not mi.is_null('publisher'):
            self.publisher.current_val = mi.publisher
        if not mi.is_null('tags'):
            self.tags.current_val = mi.tags
        if not mi.is_null('identifiers'):
            self.identifiers.current_val = mi.identifiers
        if not mi.is_null('pubdate'):
            self.pubdate.current_val = mi.pubdate
        if not mi.is_null('series') and mi.series.strip():
            self.series.current_val = mi.series
            if mi.series_index is not None:
                self.series_index.current_val = float(mi.series_index)
        if mi.comments and mi.comments.strip():
            self.comments.current_val = mi.comments

    def fetch_metadata(self, *args):
        d = FullFetch(self.cover.pixmap(), self)
        ret = d.start(title=self.title.current_val, authors=self.authors.current_val,
                identifiers=self.identifiers.current_val)
        if ret == d.Accepted:
            from calibre.ebooks.metadata.sources.base import msprefs
            mi = d.book
            dummy = Metadata(_('Unknown'))
            for f in msprefs['ignore_fields']:
                if ':' not in f:
                    setattr(mi, f, getattr(dummy, f))
            if mi is not None:
                self.update_from_mi(mi)
            if d.cover_pixmap is not None:
                self.cover.current_val = pixmap_to_data(d.cover_pixmap)

    def configure_metadata(self):
        from calibre.gui2.preferences import show_config_widget
        gui = self.parent()
        show_config_widget('Sharing', 'Metadata download', parent=self,
                gui=gui, never_shutdown=True)

    def download_cover(self, *args):
        from calibre.gui2.metadata.single_download import CoverFetch
        d = CoverFetch(self.cover.pixmap(), self)
        ret = d.start(self.title.current_val, self.authors.current_val,
                self.identifiers.current_val)
        if ret == d.Accepted:
            if d.cover_pixmap is not None:
                self.cover.current_val = pixmap_to_data(d.cover_pixmap)


    # }}}

    def apply_changes(self):
        self.changed.add(self.book_id)
        for widget in self.basic_metadata_widgets:
            try:
                if not widget.commit(self.db, self.book_id):
                    return False
                self.books_to_refresh |= getattr(widget, 'books_to_refresh',
                        set([]))
            except IOError as err:
                if err.errno == 13: # Permission denied
                    import traceback
                    fname = err.filename if err.filename else 'file'
                    error_dialog(self, _('Permission denied'),
                            _('Could not open %s. Is it being used by another'
                            ' program?')%fname, det_msg=traceback.format_exc(),
                            show=True)
                    return False
                raise
        for widget in getattr(self, 'custom_metadata_widgets', []):
            self.books_to_refresh |= widget.commit(self.book_id)

        self.db.commit()
        rows = self.db.refresh_ids(list(self.books_to_refresh))
        if rows:
            self.rows_to_refresh |= set(rows)

        return True

    def accept(self):
        self.save_state()
        if not self.apply_changes():
            return
        ResizableDialog.accept(self)

    def reject(self):
        self.save_state()
        ResizableDialog.reject(self)

    def save_state(self):
        gprefs['metasingle_window_geometry3'] = bytearray(self.saveGeometry())

    # Dialog use methods {{{
    def start(self, row_list, current_row, view_slot=None,
            set_current_callback=None):
        self.row_list = row_list
        self.current_row = current_row
        if view_slot is not None:
            self.view_format.connect(view_slot)
        self.set_current_callback = set_current_callback
        self.do_one(apply_changes=False)
        ret = self.exec_()
        self.break_cycles()
        return ret

    def do_one(self, delta=0, apply_changes=True):
        if apply_changes:
            self.apply_changes()
        self.current_row += delta
        prev = next_ = None
        if self.current_row > 0:
            prev = self.db.title(self.row_list[self.current_row-1])
        if self.current_row < len(self.row_list) - 1:
            next_ = self.db.title(self.row_list[self.current_row+1])

        if next_ is not None:
            tip = (_('Save changes and edit the metadata of %s')+
                    ' [Alt+Right]')%next_
            self.next_button.setToolTip(tip)
        self.next_button.setVisible(next_ is not None)
        if prev is not None:
            tip = (_('Save changes and edit the metadata of %s')+
                    ' [Alt+Left]')%prev
            self.prev_button.setToolTip(tip)
        self.prev_button.setVisible(prev is not None)
        self(self.db.id(self.row_list[self.current_row]))


    def break_cycles(self):
        # Break any reference cycles that could prevent python
        # from garbage collecting this dialog
        self.set_current_callback = self.db = None
        def disconnect(signal):
            try:
                signal.disconnect()
            except:
                pass # Fails if view format was never connected
        disconnect(self.view_format)
        for b in ('next_button', 'prev_button'):
            x = getattr(self, b, None)
            if x is not None:
                disconnect(x.clicked)
    # }}}

class Splitter(QSplitter):

    frame_resized = pyqtSignal(object)

    def resizeEvent(self, ev):
        self.frame_resized.emit(ev)
        return QSplitter.resizeEvent(self, ev)

class MetadataSingleDialog(MetadataSingleDialogBase): # {{{

    def do_layout(self):
        if len(self.db.custom_column_label_map) == 0:
            self.central_widget.tabBar().setVisible(False)
        self.central_widget.clear()
        self.tabs = []
        self.labels = []
        self.tabs.append(QWidget(self))
        self.central_widget.addTab(self.tabs[0], _("&Basic metadata"))
        self.tabs[0].l = l = QVBoxLayout()
        self.tabs[0].tl = tl = QGridLayout()
        self.tabs[0].setLayout(l)
        w = getattr(self, 'custom_metadata_widgets_parent', None)
        if w is not None:
            self.tabs.append(w)
            self.central_widget.addTab(w, _('&Custom metadata'))
        l.addLayout(tl)
        l.addItem(QSpacerItem(10, 15, QSizePolicy.Expanding,
            QSizePolicy.Fixed))

        sto = QWidget.setTabOrder
        sto(self.button_box, self.fetch_metadata_button)
        sto(self.fetch_metadata_button, self.config_metadata_button)
        sto(self.config_metadata_button, self.title)

        def create_row(row, one, two, three, col=1, icon='forward.png'):
            ql = BuddyLabel(one)
            tl.addWidget(ql, row, col+0, 1, 1)
            self.labels.append(ql)
            tl.addWidget(one, row, col+1, 1, 1)
            if two is not None:
                tl.addWidget(two, row, col+2, 1, 1)
                two.setIcon(QIcon(I(icon)))
            ql = BuddyLabel(three)
            tl.addWidget(ql, row, col+3, 1, 1)
            self.labels.append(ql)
            tl.addWidget(three, row, col+4, 1, 1)
            sto(one, two)
            sto(two, three)

        tl.addWidget(self.swap_title_author_button, 0, 0, 2, 1)

        create_row(0, self.title, self.deduce_title_sort_button, self.title_sort)
        sto(self.title_sort, self.authors)
        create_row(1, self.authors, self.deduce_author_sort_button, self.author_sort)
        sto(self.author_sort, self.series)
        create_row(2, self.series, self.remove_unused_series_button,
                self.series_index, icon='trash.png')
        sto(self.series_index, self.swap_title_author_button)

        tl.addWidget(self.formats_manager, 0, 6, 3, 1)

        self.splitter = Splitter(Qt.Horizontal, self)
        self.splitter.addWidget(self.cover)
        self.splitter.frame_resized.connect(self.cover.frame_resized)
        l.addWidget(self.splitter)
        self.tabs[0].gb = gb = QGroupBox(_('Change cover'), self)
        gb.l = l = QGridLayout()
        gb.setLayout(l)
        sto(self.swap_title_author_button, self.cover.buttons[0])
        for i, b in enumerate(self.cover.buttons[:3]):
            l.addWidget(b, 0, i, 1, 1)
            sto(b, self.cover.buttons[i+1])
        gb.hl = QHBoxLayout()
        for b in self.cover.buttons[3:]:
            gb.hl.addWidget(b)
        sto(self.cover.buttons[-2], self.cover.buttons[-1])
        l.addLayout(gb.hl, 1, 0, 1, 3)
        self.tabs[0].middle = w = QWidget(self)
        w.l = l = QGridLayout()
        w.setLayout(w.l)
        l.setMargin(0)
        self.splitter.addWidget(w)
        def create_row2(row, widget, button=None):
            row += 1
            ql = BuddyLabel(widget)
            l.addWidget(ql, row, 0, 1, 1)
            l.addWidget(widget, row, 1, 1, 2 if button is None else 1)
            if button is not None:
                l.addWidget(button, row, 2, 1, 1)
            if button is not None:
                sto(widget, button)

        l.addWidget(gb, 0, 0, 1, 3)
        self.tabs[0].spc_one = QSpacerItem(10, 10, QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        l.addItem(self.tabs[0].spc_one, 1, 0, 1, 3)
        sto(self.cover.buttons[-1], self.rating)
        create_row2(1, self.rating)
        sto(self.rating, self.tags)
        create_row2(2, self.tags, self.tags_editor_button)
        sto(self.tags_editor_button, self.identifiers)
        create_row2(3, self.identifiers, self.clear_identifiers_button)
        sto(self.clear_identifiers_button, self.timestamp)
        create_row2(4, self.timestamp, self.timestamp.clear_button)
        sto(self.timestamp.clear_button, self.pubdate)
        create_row2(5, self.pubdate, self.pubdate.clear_button)
        sto(self.pubdate.clear_button, self.publisher)
        create_row2(6, self.publisher)
        self.tabs[0].spc_two = QSpacerItem(10, 10, QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        l.addItem(self.tabs[0].spc_two, 8, 0, 1, 3)
        l.addWidget(self.fetch_metadata_button, 9, 0, 1, 2)
        l.addWidget(self.config_metadata_button, 9, 2, 1, 1)

        self.tabs[0].gb2 = gb = QGroupBox(_('Co&mments'), self)
        gb.l = l = QVBoxLayout()
        gb.setLayout(l)
        l.addWidget(self.comments)
        self.splitter.addWidget(gb)

        self.set_custom_metadata_tab_order()

# }}}

class DragTrackingWidget(QWidget): # {{{

    def __init__(self, parent, on_drag_enter):
        QWidget.__init__(self, parent)
        self.on_drag_enter = on_drag_enter

    def dragEnterEvent(self, ev):
        self.on_drag_enter.emit()

# }}}

class MetadataSingleDialogAlt1(MetadataSingleDialogBase): # {{{

    cc_two_column = False
    one_line_comments_toolbar = True

    on_drag_enter = pyqtSignal()

    def handle_drag_enter(self):
        self.central_widget.setCurrentIndex(1)

    def do_layout(self):
        self.central_widget.clear()
        self.tabs = []
        self.labels = []
        sto = QWidget.setTabOrder

        self.on_drag_enter.connect(self.handle_drag_enter)
        self.tabs.append(DragTrackingWidget(self, self.on_drag_enter))
        self.central_widget.addTab(self.tabs[0], _("&Metadata"))
        self.tabs[0].l = QGridLayout()
        self.tabs[0].setLayout(self.tabs[0].l)

        self.tabs.append(QWidget(self))
        self.central_widget.addTab(self.tabs[1], _("&Cover and formats"))
        self.tabs[1].l = QGridLayout()
        self.tabs[1].setLayout(self.tabs[1].l)

        # accept drop events so we can automatically switch to the second tab to
        # drop covers and formats
        self.tabs[0].setAcceptDrops(True)

        # Tab 0
        tab0 = self.tabs[0]

        tl = QGridLayout()
        gb = QGroupBox(_('&Basic metadata'), self.tabs[0])
        self.tabs[0].l.addWidget(gb, 0, 0, 1, 1)
        gb.setLayout(tl)

        self.button_box.addButton(self.fetch_metadata_button,
                                  QDialogButtonBox.ActionRole)
        self.config_metadata_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.config_metadata_button.setText(_('Configure metadata downloading'))
        self.button_box.addButton(self.config_metadata_button,
                                  QDialogButtonBox.ActionRole)
        sto(self.button_box, self.title)

        def create_row(row, widget, tab_to, button=None, icon=None, span=1):
            ql = BuddyLabel(widget)
            tl.addWidget(ql, row, 1, 1, 1)
            tl.addWidget(widget, row, 2, 1, 1)
            if button is not None:
                tl.addWidget(button, row, 3, span, 1)
                if icon is not None:
                    button.setIcon(QIcon(I(icon)))
            if tab_to is not None:
                if button is not None:
                    sto(widget, button)
                    sto(button, tab_to)
                else:
                    sto(widget, tab_to)

        tl.addWidget(self.swap_title_author_button, 0, 0, 2, 1)

        create_row(0, self.title, self.title_sort,
                   button=self.deduce_title_sort_button, span=2,
                   icon='auto_author_sort.png')
        create_row(1, self.title_sort, self.authors)
        create_row(2, self.authors, self.author_sort,
                   button=self.deduce_author_sort_button,
                   span=2, icon='auto_author_sort.png')
        create_row(3, self.author_sort, self.series)
        create_row(4, self.series, self.series_index,
                   button=self.remove_unused_series_button, icon='trash.png')
        create_row(5, self.series_index, self.tags)
        create_row(6, self.tags, self.rating, button=self.tags_editor_button)
        create_row(7, self.rating, self.pubdate)
        create_row(8, self.pubdate, self.publisher,
                   button=self.pubdate.clear_button, icon='trash.png')
        create_row(9, self.publisher, self.timestamp)
        create_row(10, self.timestamp, self.identifiers,
                   button=self.timestamp.clear_button, icon='trash.png')
        create_row(11, self.identifiers, self.comments,
                   button=self.clear_identifiers_button, icon='trash.png')
        tl.addItem(QSpacerItem(1, 1, QSizePolicy.Fixed, QSizePolicy.Expanding),
                   12, 1, 1 ,1)

        w = getattr(self, 'custom_metadata_widgets_parent', None)
        if w is not None:
            gb = QGroupBox(_('C&ustom metadata'), tab0)
            gbl = QVBoxLayout()
            gb.setLayout(gbl)
            sr = QScrollArea(tab0)
            sr.setWidgetResizable(True)
            sr.setBackgroundRole(QPalette.Base)
            sr.setFrameStyle(QFrame.NoFrame)
            sr.setWidget(w)
            gbl.addWidget(sr)
            self.tabs[0].l.addWidget(gb, 0, 1, 1, 1)
            sto(self.identifiers, gb)

        w = QGroupBox(_('&Comments'), tab0)
        sp = QSizePolicy()
        sp.setVerticalStretch(10)
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        sp.setVerticalPolicy(QSizePolicy.Expanding)
        w.setSizePolicy(sp)
        l = QHBoxLayout()
        w.setLayout(l)
        l.addWidget(self.comments)
        tab0.l.addWidget(w, 1, 0, 1, 2)

        # Tab 1
        tab1 = self.tabs[1]

        wsp = QWidget(tab1)
        wgl = QVBoxLayout()
        wsp.setLayout(wgl)

        # right-hand side of splitter
        gb = QGroupBox(_('Change cover'), tab1)
        l = QGridLayout()
        gb.setLayout(l)
        sto(self.swap_title_author_button, self.cover.buttons[0])
        for i, b in enumerate(self.cover.buttons[:3]):
            l.addWidget(b, 0, i, 1, 1)
            sto(b, self.cover.buttons[i+1])
        hl = QHBoxLayout()
        for b in self.cover.buttons[3:]:
            hl.addWidget(b)
        sto(self.cover.buttons[-2], self.cover.buttons[-1])
        l.addLayout(hl, 1, 0, 1, 3)
        wgl.addWidget(gb)
        wgl.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding,
            QSizePolicy.Expanding))
        wgl.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding,
            QSizePolicy.Expanding))
        wgl.addWidget(self.formats_manager)

        self.splitter = QSplitter(Qt.Horizontal, tab1)
        tab1.l.addWidget(self.splitter)
        self.splitter.addWidget(self.cover)
        self.splitter.addWidget(wsp)

        self.formats_manager.formats.setMaximumWidth(10000)
        self.formats_manager.formats.setIconSize(QSize(64, 64))

# }}}

editors = {'default': MetadataSingleDialog, 'alt1': MetadataSingleDialogAlt1}

def edit_metadata(db, row_list, current_row, parent=None, view_slot=None,
        set_current_callback=None):
    cls = gprefs.get('edit_metadata_single_layout', '')
    if cls not in editors:
        cls = 'default'
    d = editors[cls](db, parent)
    d.start(row_list, current_row, view_slot=view_slot,
            set_current_callback=set_current_callback)
    return d.changed, d.rows_to_refresh

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    from calibre.library import db as db_
    db = db_()
    row_list = list(range(len(db.data)))
    edit_metadata(db, row_list, 0)

