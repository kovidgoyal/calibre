#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import Qt, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, \
        QGridLayout, pyqtSignal, QDialogButtonBox, QScrollArea, QFont, \
        QTabWidget, QIcon, QToolButton, QSplitter, QGroupBox, QSpacerItem, \
        QSizePolicy

from calibre.ebooks.metadata import authors_to_string, string_to_authors
from calibre.gui2 import ResizableDialog
from calibre.gui2.metadata.basic_widgets import TitleEdit, AuthorsEdit, \
    AuthorSortEdit, TitleSortEdit, SeriesEdit, SeriesIndexEdit, ISBNEdit, \
    RatingEdit, PublisherEdit, TagsEdit, FormatsManager, Cover, CommentsEdit, \
    BuddyLabel, DateEdit, PubdateEdit

class MetadataSingleDialog(ResizableDialog):

    view_format = pyqtSignal(object)

    def __init__(self, db, parent=None):
        self.db = db
        ResizableDialog.__init__(self, parent)

    def setupUi(self, *args): # {{{
        self.resize(990, 650)

        self.button_box = QDialogButtonBox(
                QDialogButtonBox.Ok|QDialogButtonBox.Cancel, Qt.Horizontal,
                self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

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
        self.setWindowTitle(_('Edit Meta Information'))

        self.create_basic_metadata_widgets()

        self.do_layout()
    # }}}

    def create_basic_metadata_widgets(self): # {{{
        self.basic_metadata_widgets = []

        self.title = TitleEdit(self)
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

        self.authors = AuthorsEdit(self)
        self.deduce_author_sort_button = QToolButton(self)
        self.deduce_author_sort_button.setToolTip(_(
        'Automatically create the author sort entry based on the current'
        ' author entry.\n'
        'Using this button to create author sort will change author sort from'
        ' red to green.'))
        self.author_sort = AuthorSortEdit(self, self.authors,
                self.deduce_author_sort_button, db)
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

        self.cover = Cover(self)
        self.basic_metadata_widgets.append(self.cover)

        self.comments = CommentsEdit(self)
        self.basic_metadata_widgets.append(self.comments)

        self.rating = RatingEdit(self)
        self.basic_metadata_widgets.append(self.rating)

        self.tags = TagsEdit(self)
        self.tags_editor_button = QToolButton(self)
        self.tags_editor_button.setToolTip(_('Open Tag Editor'))
        self.tags_editor_button.setIcon(QIcon(I('chapters.png')))
        self.tags_editor_button.clicked.connect(self.tags_editor)
        self.basic_metadata_widgets.append(self.tags)

        self.isbn = ISBNEdit(self)
        self.basic_metadata_widgets.append(self.isbn)

        self.publisher = PublisherEdit(self)
        self.basic_metadata_widgets.append(self.publisher)

        self.timestamp = DateEdit(self)
        self.pubdate = PubdateEdit(self)
        self.basic_metadata_widgets.extend([self.timestamp, self.pubdate])

        self.fetch_metadata_button = QPushButton(
                _('&Fetch metadata from server'), self)
        self.fetch_metadata_button.clicked.connect(self.fetch_metadata)
        font = self.fmb_font = QFont()
        font.setBold(True)
        self.fetch_metadata_button.setFont(font)

    # }}}

    def do_layout(self): # {{{
        self.central_widget.clear()
        self.tabs = []
        self.labels = []
        self.tabs.append(QWidget(self))
        self.central_widget.addTab(self.tabs[0], _("&Basic metadata"))
        self.tabs[0].l = l = QVBoxLayout()
        self.tabs[0].tl = tl = QGridLayout()
        self.tabs[0].setLayout(l)
        l.addLayout(tl)

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

        tl.addWidget(self.swap_title_author_button, 0, 0, 2, 1)

        create_row(0, self.title, self.deduce_title_sort_button, self.title_sort)
        create_row(1, self.authors, self.deduce_author_sort_button, self.author_sort)
        create_row(2, self.series, self.remove_unused_series_button,
                self.series_index, icon='trash.png')

        tl.addWidget(self.formats_manager, 0, 6, 3, 1)

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.addWidget(self.cover)
        l.addWidget(self.splitter)
        self.tabs[0].gb = gb = QGroupBox(_('Change cover'), self)
        gb.l = l = QGridLayout()
        gb.setLayout(l)
        for i, b in enumerate(self.cover.buttons[:3]):
            l.addWidget(b, 0, i, 1, 1)
        gb.hl = QHBoxLayout()
        for b in self.cover.buttons[3:]:
            gb.hl.addWidget(b)
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

        l.addWidget(gb, 0, 0, 1, 3)
        self.tabs[0].spc_one = QSpacerItem(10, 10, QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        l.addItem(self.tabs[0].spc_one, 1, 0, 1, 3)
        create_row2(1, self.rating)
        create_row2(2, self.tags, self.tags_editor_button)
        create_row2(3, self.isbn)
        create_row2(4, self.timestamp, self.timestamp.clear_button)
        create_row2(5, self.pubdate, self.pubdate.clear_button)
        create_row2(6, self.publisher)
        self.tabs[0].spc_two = QSpacerItem(10, 10, QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        l.addItem(self.tabs[0].spc_two, 8, 0, 1, 3)
        l.addWidget(self.fetch_metadata_button, 9, 0, 1, 3)

        self.tabs[0].gb2 = gb = QGroupBox(_('&Comments'), self)
        gb.l = l = QVBoxLayout()
        gb.setLayout(l)
        l.addWidget(self.comments)
        self.splitter.addWidget(gb)

    # }}}

    def __call__(self, id_, has_next=False, has_previous=False):
        # TODO: Next and previous buttons
        self.book_id = id_
        for widget in self.basic_metadata_widgets:
            widget.initialize(self.db, id_)

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

    def fetch_metadata(self, *args):
        pass # TODO: fetch metadata


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    from calibre.library import db
    db = db()
    d = MetadataSingleDialog(db)
    d(db.data[0][0])
    d.exec_()

