#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, re, os

from PyQt4.Qt import QDialogButtonBox, Qt, QTabWidget, QScrollArea, \
    QVBoxLayout, QIcon, QToolButton, QWidget, QLabel, QGridLayout, \
    QDoubleSpinBox, QListWidgetItem, QSize, pyqtSignal, QPixmap, \
    QSplitter, QPushButton, QGroupBox, QHBoxLayout, QSpinBox, \
    QMessageBox

from calibre.gui2 import ResizableDialog, file_icon_provider, \
        choose_files, error_dialog, choose_images, question_dialog
from calibre.utils.icu import sort_key
from calibre.utils.config import tweaks
from calibre.gui2.widgets import EnLineEdit, CompleteComboBox, \
        EnComboBox, FormatList, ImageView, CompleteLineEdit
from calibre.ebooks.metadata import title_sort, authors_to_string, \
        string_to_authors
from calibre.utils.date import local_tz
from calibre import strftime
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.customize.ui import run_plugins_on_import
from calibre.utils.date import utcfromtimestamp
from calibre.gui2.comments_editor import Editor
from calibre.library.comments import comments_to_html
from calibre.gui2.dialogs.tag_editor import TagEditor

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
        # Present in most but not all basic metadata widgets
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

class BuddyLabel(QLabel): # {{{

    def __init__(self, buddy):
        QLabel.__init__(self, buddy.LABEL)
        self.setBuddy(buddy)
        self.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
# }}}

class Format(QListWidgetItem): # {{{

    def __init__(self, parent, ext, size, path=None, timestamp=None):
        self.path = path
        self.ext = ext
        self.size = float(size)/(1024*1024)
        text = '%s (%.2f MB)'%(self.ext.upper(), self.size)
        QListWidgetItem.__init__(self, file_icon_provider().icon_from_ext(ext),
                                 text, parent, QListWidgetItem.UserType)
        if timestamp is not None:
            ts = timestamp.astimezone(local_tz)
            t = strftime('%a, %d %b %Y [%H:%M:%S]', ts.timetuple())
            text = _('Last modified: %s')%t
            self.setToolTip(text)
            self.setStatusTip(text)

# }}}

class FormatsManager(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.dialog = parent
        self.changed = False

        self.l = l = QGridLayout()
        self.setLayout(l)
        self.cover_from_format_button = QToolButton(self)
        self.cover_from_format_button.setToolTip(
                _('Set the cover for the book from the selected format'))
        self.cover_from_format_button.setIcon(QIcon(I('book.png')))
        self.cover_from_format_button.setIconSize(QSize(32, 32))

        self.metadata_from_format_button = QToolButton(self)
        self.metadata_from_format_button.setIcon(QIcon(I('edit_input.png')))
        self.metadata_from_format_button.setIconSize(QSize(32, 32))
        # TODO: Implement the *_from_format buttons

        self.add_format_button = QToolButton(self)
        self.add_format_button.setIcon(QIcon(I('add_book.png')))
        self.add_format_button.setIconSize(QSize(32, 32))
        self.add_format_button.clicked.connect(self.add_format)

        self.remove_format_button = QToolButton(self)
        self.remove_format_button.setIcon(QIcon(I('trash.png')))
        self.remove_format_button.setIconSize(QSize(32, 32))
        self.remove_format_button.clicked.connect(self.remove_format)

        self.formats = FormatList(self)
        self.formats.setAcceptDrops(True)
        self.formats.formats_dropped.connect(self.formats_dropped)
        self.formats.delete_format.connect(self.remove_format)
        self.formats.itemDoubleClicked.connect(self.show_format)
        self.formats.setDragDropMode(self.formats.DropOnly)
        self.formats.setIconSize(QSize(32, 32))
        self.formats.setMaximumWidth(200)

        l.addWidget(self.cover_from_format_button,    0, 0, 1, 1)
        l.addWidget(self.metadata_from_format_button, 2, 0, 1, 1)
        l.addWidget(self.add_format_button,           0, 2, 1, 1)
        l.addWidget(self.remove_format_button,        2, 2, 1, 1)
        l.addWidget(self.formats,                     0, 1, 3, 1)



    def initialize(self, db, id_):
        self.changed = False
        exts = db.formats(id_, index_is_id=True)
        if exts:
            exts = exts.split(',')
            for ext in exts:
                if not ext:
                    ext = ''
                size = db.sizeof_format(id_, ext, index_is_id=True)
                timestamp = db.format_last_modified(id_, ext)
                if size is None:
                    continue
                Format(self.formats, ext, size, timestamp=timestamp)

    def commit(self, db, id_):
        if not self.changed:
            return True
        old_extensions, new_extensions, paths = set(), set(), {}
        for row in range(self.formats.count()):
            fmt = self.formats.item(row)
            ext, path = fmt.ext.lower(), fmt.path
            if 'unknown' in ext.lower():
                ext = None
            if path:
                new_extensions.add(ext)
                paths[ext] = path
            else:
                old_extensions.add(ext)
        for ext in new_extensions:
            db.add_format(id_, ext, open(paths[ext], 'rb'), notify=False,
                    index_is_id=True)
        db_extensions = set([f.lower() for f in db.formats(id_,
            index_is_id=True).split(',')])
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions:
                db.remove_format(id_, ext, notify=False, index_is_id=True)

        self.changed = False
        return True

    def add_format(self, *args):
        files = choose_files(self, 'add formats dialog',
                             _("Choose formats for ") +
                             self.dialog.title.current_val,
                             [(_('Books'), BOOK_EXTENSIONS)])
        self._add_formats(files)

    def _add_formats(self, paths):
        added = False
        if not paths:
            return added
        bad_perms = []
        for _file in paths:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                bad_perms.append(_file)
                continue

            nfile = run_plugins_on_import(_file)
            if nfile is not None:
                _file = nfile
            stat = os.stat(_file)
            size = stat.st_size
            ext = os.path.splitext(_file)[1].lower().replace('.', '')
            timestamp = utcfromtimestamp(stat.st_mtime)
            for row in range(self.formats.count()):
                fmt = self.formats.item(row)
                if fmt.ext.lower() == ext:
                    self.formats.takeItem(row)
                    break
            Format(self.formats, ext, size, path=_file, timestamp=timestamp)
            self.changed = True
            added = True
        if bad_perms:
            error_dialog(self, _('No permission'),
                    _('You do not have '
                'permission to read the following files:'),
                det_msg='\n'.join(bad_perms), show=True)

        return added

    def formats_dropped(self, event, paths):
        if self._add_formats(paths):
            event.accept()

    def remove_format(self, *args):
        rows = self.formats.selectionModel().selectedRows(0)
        for row in rows:
            self.formats.takeItem(row.row())
            self.changed = True

    def show_format(self, item, *args):
        fmt = item.ext
        self.dialog.view_format.emit(fmt)

# }}}

class Cover(ImageView): # {{{

    def __init__(self, parent):
        ImageView.__init__(self, parent)
        self.dialog = parent
        self._cdata = None
        self.cover_changed.connect(self.set_pixmap_from_data)

        self.select_cover_button = QPushButton(QIcon(I('document_open.png')),
                _('&Browse'), parent)
        self.trim_cover_button = QPushButton(QIcon(I('trim.png')),
                _('T&rim'), parent)
        self.remove_cover_button = QPushButton(QIcon(I('trash.png')),
            _('&Remove'), parent)

        self.select_cover_button.clicked.connect(self.select_cover)
        self.remove_cover_button.clicked.connect(self.remove_cover)
        self.trim_cover_button.clicked.connect(self.trim_cover)

        self.download_cover_button = QPushButton(_('Download co&ver'), parent)
        self.generate_cover_button = QPushButton(_('&Generate cover'), parent)

        self.download_cover_button.clicked.connect(self.download_cover)
        self.generate_cover_button.clicked.connect(self.generate_cover)

        self.buttons = [self.select_cover_button, self.remove_cover_button,
                self.trim_cover_button, self.download_cover_button,
                self.generate_cover_button]

    def select_cover(self, *args):
        files = choose_images(self, 'change cover dialog',
                             _('Choose cover for ') +
                             self.dialog.title.current_val)
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self, _('Cannot read'),
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e:
                d = error_dialog(self, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>")
                        + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                orig = self.current_val
                self.current_val = cover
                if self.current_val is None:
                    self.current_val = orig
                    error_dialog(self,
                        _("Not a valid picture"),
                            _file + _(" is not a valid picture"), show=True)

    def remove_cover(self, *args):
        self.current_val = None

    def trim_cover(self, *args):
        from calibre.utils.magick import Image
        cdata = self.current_val
        if not cdata:
            return
        im = Image()
        im.load(cdata)
        im.trim(10)
        cdata = im.export('png')
        self.current_val = cdata

    def download_cover(self, *args):
        pass # TODO: Implement this

    def generate_cover(self, *args):
        from calibre.ebooks import calibre_cover
        from calibre.ebooks.metadata import fmt_sidx
        from calibre.gui2 import config
        title = self.dialog.title.current_val
        author = authors_to_string(self.dialog.authors.current_val)
        if not title or not author:
            return error_dialog(self, _('Specify title and author'),
                    _('You must specify a title and author before generating '
                        'a cover'), show=True)
        series = self.dialog.series.current_val
        series_string = None
        if series:
            series_string = _('Book %s of %s')%(
                    fmt_sidx(self.dialog.series_index.current_val,
                    use_roman=config['use_roman_numerals_for_series_number']), series)
        self.current_val = calibre_cover(title, author,
                series_string=series_string)

    def set_pixmap_from_data(self, data):
        if not data:
            self.current_val = None
            return
        orig = self.current_val
        self.current_val = data
        if self.current_val is None:
            error_dialog(self, _('Invalid cover'),
                    _('Could not change cover as the image is invalid.'),
                    show=True)
            self.current_val = orig

    def initialize(self, db, id_):
        self._cdata = None
        self.current_val = db.cover(id_, index_is_id=True)
        self.original_val = self.current_val

    @property
    def changed(self):
        return self.current_val != self.original_val

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self._cdata
        def fset(self, cdata):
            self._cdata = None
            pm = QPixmap()
            if cdata:
                pm.loadFromData(cdata)
            if pm.isNull():
                pm = QPixmap(I('default_cover.png'))
            else:
                self._cdata = cdata
            self.setPixmap(pm)
            tt = _('This book has no cover')
            if self._cdata:
                tt = _('Cover size: %dx%d pixels') % \
                (pm.width(), pm.height())
            self.setToolTip(tt)

        return property(fget=fget, fset=fset)

    def commit(self, db, id_):
        if self.changed:
            if self.current_val:
                db.set_cover(id_, self.current_val, notify=False, commit=False)
            else:
                db.remove_cover(id_, notify=False, commit=False)
        return True

# }}}

class CommentsEdit(Editor): # {{{

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.html
        def fset(self, val):
            if not val or not val.strip():
                val = ''
            else:
                val = comments_to_html(val)
            self.html = val
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.current_val = db.comments(id_, index_is_id=True)
        self.original_val = self.current_val

    def commit(self, db, id_):
        db.set_comment(id_, self.current_val, notify=False, commit=False)
        return True
# }}}

class RatingEdit(QSpinBox): # {{{
    LABEL = _('&Rating:')
    TOOLTIP = _('Rating of this book. 0-5 stars')

    def __init__(self, parent):
        QSpinBox.__init__(self, parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        self.setMaximum(5)
        self.setSuffix(' ' + _('stars'))

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.value()
        def fset(self, val):
            if val is None:
                val = 0
            val = int(val)
            if val < 0:
                val = 0
            if val > 5:
                val = 5
            self.setValue(val)
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        val = db.rating(id_, index_is_id=True)
        if val > 0:
            val = int(val/2.)
        else:
            val = 0
        self.current_val = val
        self.original_val = self.current_val

    def commit(self, db, id_):
        db.set_rating(id_, 2*self.current_val, notify=False, commit=False)
        return True

# }}}

class TagsEdit(CompleteLineEdit): # {{{
    LABEL = _('Ta&gs:')
    TOOLTIP = '<p>'+_('Tags categorize the book. This is particularly '
            'useful while searching. <br><br>They can be any words'
            'or phrases, separated by commas.')

    def __init__(self, parent):
        CompleteLineEdit.__init__(self, parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return [x.strip() for x in unicode(self.text()).split(',')]
        def fset(self, val):
            if not val:
                val = []
            self.setText(', '.join([x.strip() for x in val]))
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        tags = db.tags(id_, index_is_id=True)
        tags = tags.split(',') if tags else []
        self.current_val = tags
        self.update_items_cache(db.all_tags())
        self.original_val = self.current_val

    @property
    def changed(self):
        return self.current_val != self.original_val

    def edit(self, db, id_):
        if self.changed:
            if question_dialog(self, _('Tags changed'),
                    _('You have changed the tags. In order to use the tags'
                       ' editor, you must either discard or apply these '
                       'changes'), show_copy_button=False,
                    buttons=QMessageBox.Apply|QMessageBox.Discard,
                    yes_button=QMessageBox.Apply):
                self.commit(db, id_)
                db.commit()
                self.original_val = self.current_val
            else:
                self.current_val = self.original_val
        d = TagEditor(self, db, id_)
        if d.exec_() == TagEditor.Accepted:
            self.current_val = d.tags
            self.update_items_cache(db.all_tags())


    def commit(self, db, id_):
        db.set_tags(id_, self.current_val, notify=False, commit=False)
        return True

# }}}

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
            ql = BuddyLabel(widget)
            l.addWidget(ql, row, 0, 1, 1)
            l.addWidget(widget, row, 1, 1, 2 if button is None else 1)
            if button is not None:
                l.addWidget(button, row, 2, 1, 1)

        l.addWidget(gb, 0, 0, 1, 3)
        create_row2(1, self.rating)
        create_row2(2, self.tags, self.tags_editor_button)

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


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    from calibre.library import db
    db = db()
    d = MetadataSingleDialog(db)
    d(db.data[0][0])
    d.exec_()

