#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, re

from PyQt4.Qt import QDialogButtonBox, Qt, QTabWidget, QScrollArea, \
    QVBoxLayout, QIcon, QToolButton, QWidget, QLabel, QGridLayout, \
    QDoubleSpinBox

from calibre.gui2 import ResizableDialog
from calibre.utils.icu import sort_key
from calibre.utils.config import tweaks
from calibre.gui2.widgets import EnLineEdit, CompleteComboBox, \
        EnComboBox
from calibre.ebooks.metadata import title_sort, authors_to_string, \
        string_to_authors

'''
The interface common to all widgets used to set basic metadata
class BasicMetadataWidget(object):

    LABEL = "label text"

    def initialize(self, db, id_):
        pass

    def commit(self, db, id_):
        return True

    @dynamic_property
    def current_val(self):
        def fget(self):
            return None
        def fset(self, val):
            pass
        return property(fget=fget, fset=fset)
'''

# Title {{{
class TitleEdit(EnLineEdit):

    TITLE_ATTR = 'title'
    COMMIT = True
    TOOLTIP = _('Change the title of this book')
    LABEL = _('&Title:')

    def __init__(self, parent):
        self.dialog = parent
        EnLineEdit.__init__(self, parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)

    def get_default(self):
        return _('Unknown')

    def initialize(self, db, id_):
        title = getattr(db, self.TITLE_ATTR)(id_, index_is_id=True)
        self.current_val = title
        self.original_val = self.current_val

    def commit(self, db, id_):
        title = self.current_val
        if self.COMMIT:
            getattr(db, 'set_', self.TITLE_ATTR)(id_, title, notify=False)
        else:
            getattr(db, 'set_', self.TITLE_ATTR)(id_, title, notify=False,
                    commit=False)
        return True

    @dynamic_property
    def current_val(self):

        def fget(self):
            title = unicode(self.text()).strip()
            if not title:
                title = self.get_default()
            return title

        def fset(self, val):
            if hasattr(val, 'strip'):
                val = val.strip()
            if not val:
                val = self.get_default()
            self.setText(val)
            self.setCursorPosition(0)

        return property(fget=fget, fset=fset)

class TitleSortEdit(TitleEdit):

    TITLE_ATTR = 'title_sort'
    COMMIT = False
    TOOLTIP = _('Specify how this book should be sorted when by title.'
            ' For example, The Exorcist might be sorted as Exorcist, The.')
    LABEL = _('Title &sort:')

    def __init__(self, parent, title_edit, autogen_button):
        TitleEdit.__init__(self, parent)
        self.title_edit = title_edit

        base = self.TOOLTIP
        ok_tooltip = '<p>' + textwrap.fill(base+'<br><br>'+
                            _(' The green color indicates that the current '
                              'title sort matches the current title'))
        bad_tooltip = '<p>'+textwrap.fill(base + '<br><br>'+
                _(' The red color warns that the current '
                  'title sort does not match the current title. '
                  'No action is required if this is what you want.'))
        self.tooltips = (ok_tooltip, bad_tooltip)

        self.title_edit.textChanged.connect(self.update_state)
        self.textChanged.connect(self.update_state)

        autogen_button.clicked.connect(self.auto_generate)
        self.update_state()

    def update_state(self, *args):
        ts = title_sort(self.title_edit.current_val)
        normal = ts == self.current_val
        if normal:
            col = 'rgb(0, 255, 0, 20%)'
        else:
            col = 'rgb(255, 0, 0, 20%)'
        self.setStyleSheet('QLineEdit { color: black; '
                              'background-color: %s; }'%col)
        tt = self.tooltips[0 if normal else 1]
        self.setToolTip(tt)
        self.setWhatsThis(tt)

    def auto_generate(self, *args):
        self.current_val = title_sort(self.title_edit.current_val)

# }}}

# Authors {{{
class AuthorsEdit(CompleteComboBox):

    TOOLTIP = ''
    LABEL = _('&Author(s):')

    def __init__(self, parent):
        self.dialog = parent
        CompleteComboBox.__init__(self, parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        self.setEditable(True)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)

    def get_default(self):
        return _('Unknown')

    def initialize(self, db, id_):
        all_authors = db.all_authors()
        all_authors.sort(key=lambda x : sort_key(x[1]))
        for i in all_authors:
            id, name = i
            name = [name.strip().replace('|', ',') for n in name.split(',')]
            self.addItem(authors_to_string(name))

        self.set_separator('&')
        self.set_space_before_sep(True)
        self.update_items_cache(db.all_author_names())

        au = db.authors(id_, index_is_id=True)
        if not au:
            au = _('Unknown')
        self.current_val = [a.strip().replace('|', ',') for a in au.split(',')]
        self.original_val = self.current_val

    def commit(self, db, id_):
        authors = self.current_val
        db.set_authors(id_, authors, notify=False)
        return True

    @dynamic_property
    def current_val(self):

        def fget(self):
            au = unicode(self.text()).strip()
            if not au:
                au = self.get_default()
            return string_to_authors(au)

        def fset(self, val):
            if not val:
                val = [self.get_default()]
            self.setEditText(' & '.join([x.strip() for x in val]))
            self.lineEdit().setCursorPosition(0)


        return property(fget=fget, fset=fset)

class AuthorSortEdit(EnLineEdit):

    TOOLTIP = _('Specify how the author(s) of this book should be sorted. '
            'For example Charles Dickens should be sorted as Dickens, '
            'Charles.\nIf the box is colored green, then text matches '
            'the individual author\'s sort strings. If it is colored '
            'red, then the authors and this text do not match.')
    LABEL = _('Author s&ort:')

    def __init__(self, parent, authors_edit, autogen_button, db):
        EnLineEdit.__init__(self, parent)
        self.authors_edit = authors_edit
        self.db = db

        base = self.TOOLTIP
        ok_tooltip = '<p>' + textwrap.fill(base+'<br><br>'+
                _(' The green color indicates that the current '
                    'author sort matches the current author'))
        bad_tooltip = '<p>'+textwrap.fill(base + '<br><br>'+
                _(' The red color indicates that the current '
                    'author sort does not match the current author. '
                    'No action is required if this is what you want.'))
        self.tooltips = (ok_tooltip, bad_tooltip)

        self.authors_edit.editTextChanged.connect(self.update_state)
        self.textChanged.connect(self.update_state)

        autogen_button.clicked.connect(self.auto_generate)
        self.update_state()

    @dynamic_property
    def current_val(self):

        def fget(self):
            return unicode(self.text()).strip()

        def fset(self, val):
            if not val:
                val = ''
            self.setText(val.strip())
            self.setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def update_state(self, *args):
        au = unicode(self.authors_edit.text())
        au = re.sub(r'\s+et al\.$', '', au)
        au = self.db.author_sort_from_authors(string_to_authors(au))

        normal = au == self.current_val
        if normal:
            col = 'rgb(0, 255, 0, 20%)'
        else:
            col = 'rgb(255, 0, 0, 20%)'
        self.setStyleSheet('QLineEdit { color: black; '
                              'background-color: %s; }'%col)
        tt = self.tooltips[0 if normal else 1]
        self.setToolTip(tt)
        self.setWhatsThis(tt)

    def auto_generate(self, *args):
        au = unicode(self.authors_edit.text())
        au = re.sub(r'\s+et al\.$', '', au)
        authors = string_to_authors(au)
        self.current_val = self.db.author_sort_from_authors(authors)

    def initialize(self, db, id_):
        self.current_val = db.author_sort(id_, index_is_id=True)

    def commit(self, db, id_):
        aus = self.current_val
        db.set_author_sort(id_, aus, notify=False, commit=False)
        return True

# }}}

# Series {{{
class SeriesEdit(EnComboBox):

    TOOLTIP = _('List of known series. You can add new series.')
    LABEL = _('&Series:')

    def __init__(self, parent):
        EnComboBox.__init__(self, parent)
        self.dialog = parent
        self.setSizeAdjustPolicy(
                self.AdjustToMinimumContentsLengthWithIcon)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        self.setEditable(True)

    @dynamic_property
    def current_val(self):

        def fget(self):
            return unicode(self.currentText()).strip()

        def fset(self, val):
            if not val:
                val = ''
            self.setEditText(val.strip())
            self.setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        all_series = db.all_series()
        all_series.sort(key=lambda x : sort_key(x[1]))
        series_id = db.series_id(id_, index_is_id=True)
        idx, c = None, 0
        for i in all_series:
            id, name = i
            if id == series_id:
                idx = c
            self.addItem(name)
            c += 1

        self.lineEdit().setText('')
        if idx is not None:
            self.setCurrentIndex(idx)
        self.original_val = self.current_val

    def commit(self, db, id_):
        series = self.current_val
        db.set_series(id_, series, notify=False, commit=True)
        return True

class SeriesIndexEdit(QDoubleSpinBox):

    TOOLTIP = ''
    LABEL = _('&Number:')

    def __init__(self, parent, series_edit):
        QDoubleSpinBox.__init__(self, parent)
        self.dialog = parent
        self.db = self.original_series_name = None
        self.setMaximum(1000000)
        self.series_edit = series_edit
        series_edit.currentIndexChanged.connect(self.enable)
        series_edit.editTextChanged.connect(self.enable)
        series_edit.lineEdit().editingFinished.connect(self.increment)
        self.enable()

    def enable(self, *args):
        self.setEnabled(bool(self.series_edit.current_val))

    @dynamic_property
    def current_val(self):

        def fget(self):
            return self.value()

        def fset(self, val):
            if val is None:
                val = 1.0
            val = float(val)
            self.setValue(val)

        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.db = db
        if self.series_edit.current_val:
            val = db.series_index(id_, index_is_id=True)
        else:
            val = 1.0
        self.current_val = val
        self.original_val = self.current_val
        self.original_series_name = self.series_edit.original_val

    def commit(self, db, id_):
        db.set_series_index(id_, self.current_val, notify=False, commit=False)
        return True

    def increment(self):
        if self.db is not None:
            try:
                series = self.series_edit.current_val
                if series and series != self.original_series_name:
                    ns = 1.0
                    if tweaks['series_index_auto_increment'] != 'const':
                        ns = self.db.get_next_series_num_for(series)
                    self.current_val = ns
                    self.original_series_name = series
            except:
                import traceback
                traceback.print_exc()


# }}}

class BuddyLabel(QLabel):

    def __init__(self, buddy):
        QLabel.__init__(self, buddy.LABEL)
        self.setBuddy(buddy)
        self.setAlignment(Qt.AlignRight|Qt.AlignVCenter)

class MetadataSingleDialog(ResizableDialog):

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

    def create_basic_metadata_widgets(self):
        self.basic_metadata_widgets = []
        # Title
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

        # Authors
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

    def do_layout(self):
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


    def __call__(self, id_, has_next=False, has_previous=False):
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


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    from calibre.library import db
    db = db()
    d = MetadataSingleDialog(db)
    d(db.data[0][0])
    d.exec_()

