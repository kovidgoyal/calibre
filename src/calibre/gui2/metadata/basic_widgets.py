#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, re, os, shutil, weakref
from datetime import date, datetime

from PyQt5.Qt import (
    Qt, QDateTimeEdit, pyqtSignal, QMessageBox, QIcon, QToolButton, QWidget,
    QLabel, QGridLayout, QApplication, QDoubleSpinBox, QListWidgetItem, QSize,
    QPixmap, QDialog, QMenu, QLineEdit, QSizePolicy, QKeySequence,
    QDialogButtonBox, QAction, QCalendarWidget, QDate, QDateTime, QUndoCommand,
    QUndoStack, QVBoxLayout, QPlainTextEdit)

from calibre.gui2.widgets import EnLineEdit, FormatList as _FormatList, ImageView
from calibre.gui2.widgets2 import access_key, populate_standard_spinbox_context_menu, RightClickButton, Dialog, RatingEditor
from calibre.utils.icu import sort_key
from calibre.utils.config import tweaks, prefs
from calibre.ebooks.metadata import (
    title_sort, string_to_authors, check_isbn, authors_to_sort_string)
from calibre.ebooks.metadata.meta import get_metadata
from calibre.gui2 import (file_icon_provider, UNDEFINED_QDATETIME,
        choose_files, error_dialog, choose_images)
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.date import (
    local_tz, qt_to_dt, as_local_time, UNDEFINED_DATE, is_date_undefined,
    utcfromtimestamp, parse_only_date)
from calibre import strftime
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.customize.ui import run_plugins_on_import
from calibre.gui2.comments_editor import Editor
from calibre.library.comments import comments_to_html
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.utils.icu import strcmp
from calibre.ptempfile import PersistentTemporaryFile, SpooledTemporaryFile
from calibre.gui2.languages import LanguagesEdit as LE
from calibre.db import SPOOL_SIZE

OK_COLOR = 'rgba(0, 255, 0, 12%)'
ERR_COLOR = 'rgba(255, 0, 0, 12%)'
INDICATOR_SHEET = 'QLineEdit { color: black; background-color: %s }'


def save_dialog(parent, title, msg, det_msg=''):
    d = QMessageBox(parent)
    d.setWindowTitle(title)
    d.setText(msg)
    d.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
    return d.exec_()


def clean_text(x):
    return re.sub(r'\s', ' ', x.strip())


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


class ToMetadataMixin(object):

    FIELD_NAME = None
    allow_undo = False

    def apply_to_metadata(self, mi):
        mi.set(self.FIELD_NAME, self.current_val)

    def set_value(self, val, allow_undo=True):
        self.allow_undo = allow_undo
        try:
            self.current_val = val
        finally:
            self.allow_undo = False

    def set_text(self, text):
        if self.allow_undo:
            self.selectAll(), self.insert(text)
        else:
            self.setText(text)

    def set_edit_text(self, text):
        if self.allow_undo:
            orig, self.disable_popup = self.disable_popup, True
            try:
                self.lineEdit().selectAll(), self.lineEdit().insert(text)
            finally:
                self.disable_popup = orig
        else:
            self.setEditText(text)


def make_undoable(spinbox):
    'Add a proper undo/redo capability to spinbox which must be a sub-class of QAbstractSpinBox'

    class UndoCommand(QUndoCommand):

        def __init__(self, widget, val):
            QUndoCommand.__init__(self)
            self.widget = weakref.ref(widget)
            if hasattr(widget, 'dateTime'):
                self.undo_val = widget.dateTime()
            elif hasattr(widget, 'value'):
                self.undo_val = widget.value()
            if isinstance(val, date) and not isinstance(val, datetime):
                val = parse_only_date(val.isoformat(), assume_utc=False, as_utc=False)
            self.redo_val = val

        def undo(self):
            w = self.widget()
            if hasattr(w, 'setDateTime'):
                w.setDateTime(self.undo_val)
            elif hasattr(w, 'setValue'):
                w.setValue(self.undo_val)

        def redo(self):
            w = self.widget()
            if hasattr(w, 'setDateTime'):
                w.setDateTime(self.redo_val)
            elif hasattr(w, 'setValue'):
                w.setValue(self.redo_val)

    class UndoableSpinbox(spinbox):

        def __init__(self, parent=None):
            spinbox.__init__(self, parent)
            self.undo_stack = QUndoStack(self)
            self.undo, self.redo = self.undo_stack.undo, self.undo_stack.redo

        def keyPressEvent(self, ev):
            if ev == QKeySequence.Undo:
                self.undo()
                return ev.accept()
            if ev == QKeySequence.Redo:
                self.redo()
                return ev.accept()
            return spinbox.keyPressEvent(self, ev)

        def contextMenuEvent(self, ev):
            m = QMenu(self)
            if hasattr(self, 'setDateTime'):
                m.addAction(_('Set date to undefined') + '\t' + QKeySequence(Qt.Key_Minus).toString(QKeySequence.NativeText),
                            lambda : self.setDateTime(self.minimumDateTime()))
            m.addAction(_('&Undo') + access_key(QKeySequence.Undo), self.undo).setEnabled(self.undo_stack.canUndo())
            m.addAction(_('&Redo') + access_key(QKeySequence.Redo), self.redo).setEnabled(self.undo_stack.canRedo())
            m.addSeparator()
            populate_standard_spinbox_context_menu(self, m)
            m.popup(ev.globalPos())

        def set_spinbox_value(self, val):
            if self.allow_undo:
                cmd = UndoCommand(self, val)
                self.undo_stack.push(cmd)
            else:
                self.undo_stack.clear()
            if hasattr(self, 'setDateTime'):
                if isinstance(val, date) and not isinstance(val, datetime) and not is_date_undefined(val):
                    val = parse_only_date(val.isoformat(), assume_utc=False, as_utc=False)
                self.setDateTime(val)
            elif hasattr(self, 'setValue'):
                self.setValue(val)

    return UndoableSpinbox

# Title {{{


class TitleEdit(EnLineEdit, ToMetadataMixin):

    TITLE_ATTR = FIELD_NAME = 'title'
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

    @property
    def changed(self):
        return self.original_val != self.current_val

    def commit(self, db, id_):
        title = self.current_val
        if self.changed:
            # Only try to commit if changed. This allow setting of other fields
            # to work even if some of the book files are opened in windows.
            getattr(db, 'set_'+ self.TITLE_ATTR)(id_, title, notify=False)

    @dynamic_property
    def current_val(self):

        def fget(self):
            title = clean_text(unicode(self.text()))
            if not title:
                title = self.get_default()
            return title.strip()

        def fset(self, val):
            if hasattr(val, 'strip'):
                val = val.strip()
            if not val:
                val = self.get_default()
            self.set_text(val)
            self.setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def break_cycles(self):
        self.dialog = None


class TitleSortEdit(TitleEdit, ToMetadataMixin):

    TITLE_ATTR = FIELD_NAME = 'title_sort'
    TOOLTIP = _('Specify how this book should be sorted when by title.'
            ' For example, The Exorcist might be sorted as Exorcist, The.')
    LABEL = _('Title &sort:')

    def __init__(self, parent, title_edit, autogen_button, languages_edit):
        TitleEdit.__init__(self, parent)
        self.title_edit = title_edit
        self.languages_edit = languages_edit

        base = self.TOOLTIP
        ok_tooltip = '<p>' + textwrap.fill(base+'<br><br>'+
                            _(' The green color indicates that the current '
                              'title sort matches the current title'))
        bad_tooltip = '<p>'+textwrap.fill(base + '<br><br>'+
                _(' The red color warns that the current '
                  'title sort does not match the current title. '
                  'No action is required if this is what you want.'))
        self.tooltips = (ok_tooltip, bad_tooltip)

        self.title_edit.textChanged.connect(self.update_state_and_val, type=Qt.QueuedConnection)
        self.textChanged.connect(self.update_state)

        self.autogen_button = autogen_button
        autogen_button.clicked.connect(self.auto_generate)
        languages_edit.editTextChanged.connect(self.update_state)
        languages_edit.currentIndexChanged.connect(self.update_state)
        self.update_state()

    @property
    def changed(self):
        return self.title_edit.changed or self.original_val != self.current_val

    @property
    def book_lang(self):
        try:
            book_lang = self.languages_edit.lang_codes[0]
        except:
            book_lang = None
        return book_lang

    def update_state_and_val(self):
        # Handle case change if the title's case and nothing else was changed
        ts = title_sort(self.title_edit.current_val, lang=self.book_lang)
        if strcmp(ts, self.current_val) == 0:
            self.current_val = ts
        self.update_state()

    def update_state(self, *args):
        ts = title_sort(self.title_edit.current_val, lang=self.book_lang)
        normal = ts == self.current_val
        col = OK_COLOR if normal else ERR_COLOR
        self.setStyleSheet(INDICATOR_SHEET % col)
        tt = self.tooltips[0 if normal else 1]
        self.setToolTip(tt)
        self.setWhatsThis(tt)

    def auto_generate(self, *args):
        self.current_val = title_sort(self.title_edit.current_val,
                lang=self.book_lang)

    def break_cycles(self):
        try:
            self.title_edit.textChanged.disconnect()
        except:
            pass
        try:
            self.textChanged.disconnect()
        except:
            pass
        try:
            self.autogen_button.clicked.disconnect()
        except:
            pass

# }}}

# Authors {{{


class AuthorsEdit(EditWithComplete, ToMetadataMixin):

    TOOLTIP = ''
    LABEL = _('&Author(s):')
    FIELD_NAME = 'authors'

    def __init__(self, parent, manage_authors):
        self.dialog = parent
        self.books_to_refresh = set()
        EditWithComplete.__init__(self, parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        self.setEditable(True)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.manage_authors_signal = manage_authors
        manage_authors.triggered.connect(self.manage_authors)
        self.lineEdit().createStandardContextMenu = self.createStandardContextMenu

    def createStandardContextMenu(self):
        menu = QLineEdit.createStandardContextMenu(self.lineEdit())
        menu.addSeparator()
        menu.addAction(_('&Edit authors'), self.edit_authors)
        return menu

    def edit_authors(self):
        all_authors = self.lineEdit().all_items
        current_authors = self.current_val
        from calibre.gui2.dialogs.authors_edit import AuthorsEdit
        d = AuthorsEdit(all_authors, current_authors, self)
        if d.exec_() == d.Accepted:
            self.current_val = d.authors

    def manage_authors(self):
        if self.original_val != self.current_val:
            d = save_dialog(self, _('Authors changed'),
                    _('You have changed the authors for this book. You must save '
                      'these changes before you can use Manage authors. Do you '
                      'want to save these changes?'))
            if d == QMessageBox.Cancel:
                return
            if d == QMessageBox.Yes:
                self.commit(self.db, self.id_)
                self.db.commit()
                self.original_val = self.current_val
            else:
                self.current_val = self.original_val
        first_author = self.current_val[0] if len(self.current_val) else None
        first_author_id = self.db.get_author_id(first_author) if first_author else None
        self.dialog.parent().do_author_sort_edit(self, first_author_id,
                                        select_sort=False)
        self.initialize(self.db, self.id_)
        self.dialog.author_sort.initialize(self.db, self.id_)
        self.dialog.author_sort.update_state()

    def get_default(self):
        return _('Unknown')

    @property
    def changed(self):
        return self.original_val != self.current_val

    def initialize(self, db, id_):
        self.books_to_refresh = set([])
        self.set_separator('&')
        self.set_space_before_sep(True)
        self.set_add_separator(tweaks['authors_completer_append_separator'])
        self.update_items_cache(db.all_author_names())

        au = db.authors(id_, index_is_id=True)
        if not au:
            au = _('Unknown')
        self.current_val = [a.strip().replace('|', ',') for a in au.split(',')]
        self.original_val = self.current_val
        self.id_ = id_
        self.db = db

    def commit(self, db, id_):
        authors = self.current_val
        if authors != self.original_val:
            # Only try to commit if changed. This allow setting of other fields
            # to work even if some of the book files are opened in windows.
            self.books_to_refresh |= db.set_authors(id_, authors, notify=False,
                allow_case_change=True)

    @dynamic_property
    def current_val(self):

        def fget(self):
            au = clean_text(unicode(self.text()))
            if not au:
                au = self.get_default()
            return string_to_authors(au)

        def fset(self, val):
            if not val:
                val = [self.get_default()]
            self.set_edit_text(' & '.join([x.strip() for x in val]))
            self.lineEdit().setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def break_cycles(self):
        self.db = self.dialog = None
        try:
            self.manage_authors_signal.triggered.disconnect()
        except:
            pass


class AuthorSortEdit(EnLineEdit, ToMetadataMixin):

    TOOLTIP = _('Specify how the author(s) of this book should be sorted. '
            'For example Charles Dickens should be sorted as Dickens, '
            'Charles.\nIf the box is colored green, then text matches '
            'the individual author\'s sort strings. If it is colored '
            'red, then the authors and this text do not match.')
    LABEL = _('Author s&ort:')
    FIELD_NAME = 'author_sort'

    def __init__(self, parent, authors_edit, autogen_button, db,
            copy_a_to_as_action, copy_as_to_a_action, a_to_as, as_to_a):
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

        self.authors_edit.editTextChanged.connect(self.update_state_and_val, type=Qt.QueuedConnection)
        self.textChanged.connect(self.update_state)

        self.autogen_button = autogen_button
        self.copy_a_to_as_action = copy_a_to_as_action
        self.copy_as_to_a_action = copy_as_to_a_action

        autogen_button.clicked.connect(self.auto_generate)
        copy_a_to_as_action.triggered.connect(self.auto_generate)
        copy_as_to_a_action.triggered.connect(self.copy_to_authors)
        a_to_as.triggered.connect(self.author_to_sort)
        as_to_a.triggered.connect(self.sort_to_author)
        self.original_val = ''
        self.first_time = True
        self.update_state()

    @dynamic_property
    def current_val(self):

        def fget(self):
            return clean_text(unicode(self.text()))

        def fset(self, val):
            if not val:
                val = ''
            self.set_text(val.strip())
            self.setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def update_state_and_val(self):
        # Handle case change if the authors box changed
        aus = authors_to_sort_string(self.authors_edit.current_val)
        if not self.first_time and strcmp(aus, self.current_val) == 0:
            self.current_val = aus
        self.first_time = False
        self.update_state()

    def author_sort_from_authors(self, authors):
        return self.db.new_api.author_sort_from_authors(authors, key_func=lambda x: x)

    def update_state(self, *args):
        au = unicode(self.authors_edit.text())
        au = re.sub(r'\s+et al\.$', '', au)
        au = self.author_sort_from_authors(string_to_authors(au))

        normal = au == self.current_val
        col = OK_COLOR if normal else ERR_COLOR
        self.setStyleSheet(INDICATOR_SHEET % col)
        tt = self.tooltips[0 if normal else 1]
        self.setToolTip(tt)
        self.setWhatsThis(tt)

    def copy_to_authors(self):
        aus = self.current_val
        meth = tweaks['author_sort_copy_method']
        if aus:
            ans = []
            for one in [a.strip() for a in aus.split('&')]:
                if not one:
                    continue
                ln, _, rest = one.partition(',')
                if rest:
                    if meth in ('invert', 'nocomma', 'comma'):
                        one = rest.strip() + ' ' + ln.strip()
                ans.append(one)
            self.authors_edit.current_val = ans

    def auto_generate(self, *args):
        au = unicode(self.authors_edit.text())
        au = re.sub(r'\s+et al\.$', '', au).strip()
        authors = string_to_authors(au)
        self.current_val = self.author_sort_from_authors(authors)

    def author_to_sort(self, *args):
        au = unicode(self.authors_edit.text())
        au = re.sub(r'\s+et al\.$', '', au).strip()
        if au:
            self.current_val = au

    def sort_to_author(self, *args):
        aus = self.current_val
        if aus:
            self.authors_edit.current_val = [aus]

    def initialize(self, db, id_):
        self.current_val = db.author_sort(id_, index_is_id=True)
        self.original_val = self.current_val
        self.first_time = True

    def commit(self, db, id_):
        aus = self.current_val
        if aus != self.original_val or self.authors_edit.original_val != self.authors_edit.current_val:
            db.set_author_sort(id_, aus, notify=False, commit=False)
        return True

    def break_cycles(self):
        self.db = None
        try:
            self.authors_edit.editTextChanged.disconnect()
        except:
            pass
        try:
            self.textChanged.disconnect()
        except:
            pass
        try:
            self.autogen_button.clicked.disconnect()
        except:
            pass
        try:
            self.copy_a_to_as_action.triggered.disconnect()
        except:
            pass
        try:
            self.copy_as_to_a_action.triggered.disconnect()
        except:
            pass
        self.authors_edit = None

# }}}

# Series {{{


class SeriesEdit(EditWithComplete, ToMetadataMixin):

    TOOLTIP = _('List of known series. You can add new series.')
    LABEL = _('&Series:')
    FIELD_NAME = 'series'

    def __init__(self, parent):
        EditWithComplete.__init__(self, parent)
        self.set_separator(None)
        self.dialog = parent
        self.setSizeAdjustPolicy(
                self.AdjustToMinimumContentsLengthWithIcon)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        self.setEditable(True)
        self.books_to_refresh = set([])

    @dynamic_property
    def current_val(self):

        def fget(self):
            return clean_text(unicode(self.currentText()))

        def fset(self, val):
            if not val:
                val = ''
            self.set_edit_text(val.strip())
            self.lineEdit().setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.books_to_refresh = set([])
        all_series = db.all_series()
        all_series.sort(key=lambda x: sort_key(x[1]))
        self.update_items_cache([x[1] for x in all_series])
        series_id = db.series_id(id_, index_is_id=True)
        inval = ''
        for i in all_series:
            if i[0] == series_id:
                inval = i[1]
                break
        self.current_val = inval
        self.original_val = self.current_val

    def commit(self, db, id_):
        series = self.current_val
        if series != self.original_val:
            self.books_to_refresh |= db.set_series(id_, series, notify=False, commit=True, allow_case_change=True)

    def break_cycles(self):
        self.dialog = None


class SeriesIndexEdit(make_undoable(QDoubleSpinBox), ToMetadataMixin):

    TOOLTIP = ''
    LABEL = _('&Number:')
    FIELD_NAME = 'series_index'

    def __init__(self, parent, series_edit):
        super(SeriesIndexEdit, self).__init__(parent)
        self.dialog = parent
        self.db = self.original_series_name = None
        self.setMaximum(10000000)
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
            self.set_spinbox_value(val)

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
        if self.series_edit.original_val != self.series_edit.current_val or self.current_val != self.original_val:
            db.set_series_index(id_, self.current_val, notify=False, commit=False)

    def increment(self):
        if tweaks['series_index_auto_increment'] != 'no_change' and self.db is not None:
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

    def reset_original(self):
        self.original_series_name = self.series_edit.current_val

    def break_cycles(self):
        try:
            self.series_edit.currentIndexChanged.disconnect()
        except:
            pass
        try:
            self.series_edit.editTextChanged.disconnect()
        except:
            pass
        try:
            self.series_edit.lineEdit().editingFinished.disconnect()
        except:
            pass
        self.db = self.series_edit = self.dialog = None

# }}}


class BuddyLabel(QLabel):  # {{{

    def __init__(self, buddy):
        QLabel.__init__(self, buddy.LABEL)
        self.setBuddy(buddy)
        self.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
# }}}

# Formats {{{


class Format(QListWidgetItem):

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
            text = _('Last modified: %s\n\nDouble click to view')%t
            self.setToolTip(text)
            self.setStatusTip(text)


class OrigAction(QAction):

    restore_fmt = pyqtSignal(object)

    def __init__(self, fmt, parent):
        self.fmt = fmt.replace('ORIGINAL_', '')
        QAction.__init__(self, _('Restore %s from the original')%self.fmt, parent)
        self.triggered.connect(self._triggered)

    def _triggered(self):
        self.restore_fmt.emit(self.fmt)


class FormatList(_FormatList):

    restore_fmt = pyqtSignal(object)

    def __init__(self, parent):
        _FormatList.__init__(self, parent)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def contextMenuEvent(self, event):
        originals = [self.item(x).ext.upper() for x in range(self.count())]
        originals = [x for x in originals if x.startswith('ORIGINAL_')]
        if not originals:
            return
        self.cm = cm = QMenu(self)
        for fmt in originals:
            action = OrigAction(fmt, cm)
            action.restore_fmt.connect(self.restore_fmt)
            cm.addAction(action)
        cm.popup(event.globalPos())
        event.accept()

    def remove_format(self, fmt):
        for i in range(self.count()):
            f = self.item(i)
            if f.ext.upper() == fmt.upper():
                self.takeItem(i)
                break


class FormatsManager(QWidget):

    def __init__(self, parent, copy_fmt):
        QWidget.__init__(self, parent)
        self.dialog = parent
        self.copy_fmt = copy_fmt
        self.changed = False

        self.l = l = QGridLayout()
        self.setLayout(l)
        self.cover_from_format_button = QToolButton(self)
        self.cover_from_format_button.setToolTip(
                _('Set the cover for the book from the selected format'))
        self.cover_from_format_button.setIcon(QIcon(I('default_cover.png')))
        self.cover_from_format_button.setIconSize(QSize(32, 32))

        self.metadata_from_format_button = QToolButton(self)
        self.metadata_from_format_button.setIcon(QIcon(I('edit_input.png')))
        self.metadata_from_format_button.setIconSize(QSize(32, 32))
        self.metadata_from_format_button.setToolTip(
                _('Set metadata for the book from the selected format'))

        self.add_format_button = QToolButton(self)
        self.add_format_button.setIcon(QIcon(I('add_book.png')))
        self.add_format_button.setIconSize(QSize(32, 32))
        self.add_format_button.clicked.connect(self.add_format)
        self.add_format_button.setToolTip(
                _('Add a format to this book'))

        self.remove_format_button = QToolButton(self)
        self.remove_format_button.setIcon(QIcon(I('trash.png')))
        self.remove_format_button.setIconSize(QSize(32, 32))
        self.remove_format_button.clicked.connect(self.remove_format)
        self.remove_format_button.setToolTip(
                _('Remove the selected format from this book'))

        self.formats = FormatList(self)
        self.formats.setAcceptDrops(True)
        self.formats.formats_dropped.connect(self.formats_dropped)
        self.formats.restore_fmt.connect(self.restore_fmt)
        self.formats.delete_format.connect(self.remove_format)
        self.formats.itemDoubleClicked.connect(self.show_format)
        self.formats.setDragDropMode(self.formats.DropOnly)
        self.formats.setIconSize(QSize(32, 32))
        self.formats.setMaximumWidth(200)

        l.addWidget(self.cover_from_format_button, 0, 0, 1, 1)
        l.addWidget(self.metadata_from_format_button, 2, 0, 1, 1)
        l.addWidget(self.add_format_button, 0, 2, 1, 1)
        l.addWidget(self.remove_format_button, 2, 2, 1, 1)
        l.addWidget(self.formats, 0, 1, 3, 1)

        self.temp_files = []

    def initialize(self, db, id_):
        self.changed = False
        self.formats.clear()
        exts = db.formats(id_, index_is_id=True)
        self.original_val = set([])
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
                self.original_val.add(ext.lower())

    def apply_to_metadata(self, mi):
        pass

    def commit(self, db, id_):
        if not self.changed:
            return
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
            with SpooledTemporaryFile(SPOOL_SIZE) as spool:
                with open(paths[ext], 'rb') as f:
                    shutil.copyfileobj(f, spool)
                spool.seek(0)
                db.add_format(id_, ext, spool, notify=False,
                        index_is_id=True)
        dbfmts = db.formats(id_, index_is_id=True)
        db_extensions = set([fl.lower() for fl in (dbfmts.split(',') if dbfmts
            else [])])
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions and ext in self.original_val:
                db.remove_format(id_, ext, notify=False, index_is_id=True)

        self.changed = False
        return

    def add_format(self, *args):
        files = choose_files(self, 'add formats dialog',
                             _("Choose formats for ") +
                             self.dialog.title.current_val,
                             [(_('Books'), BOOK_EXTENSIONS)])
        self._add_formats(files)

    def restore_fmt(self, fmt):
        pt = PersistentTemporaryFile(suffix='_restore_fmt.'+fmt.lower())
        ofmt = 'ORIGINAL_'+fmt
        with pt:
            self.copy_fmt(ofmt, pt)
        self._add_formats((pt.name,))
        self.temp_files.append(pt.name)
        self.changed = True
        self.formats.remove_format(ofmt)

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
        self.dialog.do_view_format(item.path, item.ext)

    def get_selected_format(self):
        row = self.formats.currentRow()
        fmt = self.formats.item(row)
        if fmt is None:
            if self.formats.count() == 1:
                fmt = self.formats.item(0)
            if fmt is None:
                error_dialog(self, _('No format selected'),
                    _('No format selected')).exec_()
                return None
        return fmt.ext.lower()

    def get_format_path(self, db, id_, fmt):
        for i in xrange(self.formats.count()):
            f = self.formats.item(i)
            ext = f.ext.lower()
            if ext == fmt:
                if f.path is None:
                    return db.format(id_, ext, as_path=True, index_is_id=True)
                return f.path

    def get_selected_format_metadata(self, db, id_):
        old = prefs['read_file_metadata']
        if not old:
            prefs['read_file_metadata'] = True
        try:
            row = self.formats.currentRow()
            fmt = self.formats.item(row)
            if fmt is None:
                if self.formats.count() == 1:
                    fmt = self.formats.item(0)
                if fmt is None:
                    error_dialog(self, _('No format selected'),
                        _('No format selected')).exec_()
                    return None, None
            ext = fmt.ext.lower()
            if fmt.path is None:
                stream = db.format(id_, ext, as_file=True, index_is_id=True)
            else:
                stream = open(fmt.path, 'rb')
            try:
                with stream:
                    mi = get_metadata(stream, ext)
                return mi, ext
            except:
                import traceback
                error_dialog(self, _('Could not read metadata'),
                            _('Could not read metadata from %s format')%ext.upper(),
                             det_msg=traceback.format_exc(), show=True)
            return None, None
        finally:
            if old != prefs['read_file_metadata']:
                prefs['read_file_metadata'] = old

    def break_cycles(self):
        self.dialog = None
        self.copy_fmt = None
        for name in self.temp_files:
            try:
                os.remove(name)
            except:
                pass
        self.temp_files = []
# }}}


class Cover(ImageView):  # {{{

    download_cover = pyqtSignal()

    def __init__(self, parent):
        ImageView.__init__(self, parent, show_size_pref_name='edit_metadata_cover_widget', default_show_size=True)
        self.dialog = parent
        self._cdata = None
        self.cdata_before_trim = None
        self.cover_changed.connect(self.set_pixmap_from_data)

        class CB(RightClickButton):

            def __init__(self, text, icon=None, action=None):
                RightClickButton.__init__(self, parent)
                self.setText(text)
                if icon is not None:
                    self.setIcon(QIcon(I(icon)))
                self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
                self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                if action is not None:
                    self.clicked.connect(action)

        self.select_cover_button = CB(_('&Browse'), 'document_open.png', self.select_cover)
        self.trim_cover_button = b = CB(_('Trim bord&ers'), 'trim.png')
        b.setToolTip(_(
            'Automatically detect and remove extra space at the cover\'s edges.\n'
            'Pressing it repeatedly can sometimes remove stubborn borders.'))
        b.m = m = QMenu()
        b.setPopupMode(QToolButton.InstantPopup)
        m.addAction(QIcon(I('trim.png')), _('Automatically trim borders'), self.trim_cover)
        m.addSeparator()
        m.addAction(_('Trim borders manually'), self.manual_trim_cover)
        m.addAction(QIcon(I('edit-undo.png')), _('Undo last trim'), self.undo_trim)
        b.setMenu(m)
        self.remove_cover_button = CB(_('&Remove'), 'trash.png', self.remove_cover)

        self.download_cover_button = CB(_('Download co&ver'), 'arrow-down.png', self.download_cover)
        self.generate_cover_button = b = CB(_('&Generate cover'), 'default_cover.png', self.generate_cover)
        b.m = m = QMenu()
        b.setMenu(m)
        m.addAction(QIcon(I('config.png')), _('Customize the styles and colors of the generated cover'), self.custom_cover)
        b.setPopupMode(b.DelayedPopup)
        self.buttons = [self.select_cover_button, self.remove_cover_button,
                self.trim_cover_button, self.download_cover_button,
                self.generate_cover_button]

        self.frame_size = (300, 400)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred,
            QSizePolicy.Preferred))

    def undo_trim(self):
        if self.cdata_before_trim:
            self.current_val = self.cdata_before_trim
            self.cdata_before_trim = None

    def frame_resized(self, ev):
        sz = ev.size()
        self.frame_size = (sz.width()//3, sz.height())

    def sizeHint(self):
        sz = QSize(self.frame_size[0], self.frame_size[1])
        return sz

    def select_cover(self, *args):
        files = choose_images(
            self, 'change cover dialog', _('Choose cover for ') + self.dialog.title.current_val)
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
            except IOError as e:
                d = error_dialog(self, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") +
                                 _file + "</b></p><br />"+str(e))
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
        cdata = self.current_val
        if not cdata:
            return
        from calibre.utils.img import remove_borders_from_image, image_to_data, image_from_data
        img = image_from_data(cdata)
        nimg = remove_borders_from_image(img)
        if nimg is not img:
            self.cdata_before_trim = cdata
            self.current_val = image_to_data(nimg, fmt='png')

    def manual_trim_cover(self):
        cdata = self.current_val
        from calibre.gui2.dialogs.trim_image import TrimImage
        d = TrimImage(cdata, parent=self)
        if d.exec_() == d.Accepted and d.image_data is not None:
            self.current_val = d.image_data
            self.cdata_before_trim = cdata

    def generate_cover(self, *args):
        from calibre.ebooks.covers import generate_cover
        mi = self.dialog.to_book_metadata()
        self.current_val = generate_cover(mi)

    def custom_cover(self):
        from calibre.ebooks.covers import generate_cover
        from calibre.gui2.covers import CoverSettingsDialog
        mi = self.dialog.to_book_metadata()
        d = CoverSettingsDialog(mi=mi, parent=self)
        if d.exec_() == d.Accepted:
            self.current_val = generate_cover(mi, prefs=d.prefs_for_rendering)

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
        self.cdata_before_trim = None
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
            self.cdata_before_trim = None
            pm = QPixmap()
            if cdata:
                pm.loadFromData(cdata)
            if pm.isNull():
                pm = QPixmap(I('default_cover.png'))
            else:
                self._cdata = cdata
            pm.setDevicePixelRatio(getattr(self, 'devicePixelRatioF', self.devicePixelRatio)())
            self.setPixmap(pm)
            tt = _('This book has no cover')
            if self._cdata:
                tt = _('Cover size: %(width)d x %(height)d pixels') % \
                dict(width=pm.width(), height=pm.height())
            self.setToolTip(tt)

        return property(fget=fget, fset=fset)

    def commit(self, db, id_):
        if self.changed:
            if self.current_val:
                db.set_cover(id_, self.current_val, notify=False, commit=False)
            else:
                db.remove_cover(id_, notify=False, commit=False)

    def break_cycles(self):
        try:
            self.cover_changed.disconnect()
        except:
            pass
        self.dialog = self._cdata = self.current_val = self.original_val = None

    def apply_to_metadata(self, mi):
        from calibre.utils.imghdr import what
        cdata = self.current_val
        if cdata:
            mi.cover_data = (what(None, cdata), cdata)

# }}}


class CommentsEdit(Editor, ToMetadataMixin):  # {{{

    FIELD_NAME = 'comments'
    toolbar_prefs_name = 'metadata-comments-editor-widget-hidden-toolbars'

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.html

        def fset(self, val):
            if not val or not val.strip():
                val = ''
            else:
                val = comments_to_html(val)
            self.set_html(val, self.allow_undo)
            self.wyswyg_dirtied()
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.current_val = db.comments(id_, index_is_id=True)
        self.original_val = self.current_val

    def commit(self, db, id_):
        val = self.current_val
        if val != self.original_val:
            db.set_comment(id_, self.current_val, notify=False, commit=False)
# }}}


class RatingEdit(RatingEditor, ToMetadataMixin):  # {{{
    LABEL = _('&Rating:')
    TOOLTIP = _('Rating of this book. 0-5 stars')
    FIELD_NAME = 'rating'

    def __init__(self, parent):
        super(RatingEdit, self).__init__(parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.rating_value

        def fset(self, val):
            self.rating_value = val
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        val = db.rating(id_, index_is_id=True)
        self.current_val = val
        self.original_val = self.current_val

    def commit(self, db, id_):
        db.set_rating(id_, self.current_val, notify=False, commit=False)
        return True

    def zero(self):
        self.setCurrentIndex(0)

# }}}


class TagsEdit(EditWithComplete, ToMetadataMixin):  # {{{
    LABEL = _('Ta&gs:')
    TOOLTIP = '<p>'+_('Tags categorize the book. This is particularly '
            'useful while searching. <br><br>They can be any words '
            'or phrases, separated by commas.')
    FIELD_NAME = 'tags'

    def __init__(self, parent):
        EditWithComplete.__init__(self, parent)
        self.lineEdit().setMaxLength(655360)  # see https://bugs.launchpad.net/bugs/1630944
        self.books_to_refresh = set([])
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return [clean_text(x) for x in unicode(self.text()).split(',')]

        def fset(self, val):
            if not val:
                val = []
            self.set_edit_text(', '.join([x.strip() for x in val]))
            self.setCursorPosition(0)
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.books_to_refresh = set([])
        tags = db.tags(id_, index_is_id=True)
        tags = tags.split(',') if tags else []
        self.current_val = tags
        self.all_items = db.all_tag_names()
        self.original_val = self.current_val

    @property
    def changed(self):
        return self.current_val != self.original_val

    def edit(self, db, id_):
        if self.changed:
            d = save_dialog(self, _('Tags changed'),
                    _('You have changed the tags. In order to use the tags'
                       ' editor, you must either discard or apply these '
                       'changes. Apply changes?'))
            if d == QMessageBox.Cancel:
                return
            if d == QMessageBox.Yes:
                self.commit(db, id_)
                db.commit()
                self.original_val = self.current_val
            else:
                self.current_val = self.original_val
        d = TagEditor(self, db, id_)
        if d.exec_() == TagEditor.Accepted:
            self.current_val = d.tags
            self.all_items = db.all_tags()

    def commit(self, db, id_):
        self.books_to_refresh |= db.set_tags(
                id_, self.current_val, notify=False, commit=False,
                allow_case_change=True)
        return True

# }}}


class LanguagesEdit(LE, ToMetadataMixin):  # {{{

    LABEL = _('&Languages:')
    TOOLTIP = _('A comma separated list of languages for this book')
    FIELD_NAME = 'languages'

    def __init__(self, *args, **kwargs):
        LE.__init__(self, *args, **kwargs)
        self.setToolTip(self.TOOLTIP)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.lang_codes

        def fset(self, val):
            self.set_lang_codes(val, self.allow_undo)
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.init_langs(db)
        lc = []
        langs = db.languages(id_, index_is_id=True)
        if langs:
            lc = [x.strip() for x in langs.split(',')]
        self.current_val = lc
        self.original_val = self.current_val

    def validate_for_commit(self):
        bad = self.validate()
        if bad:
            msg = ngettext('The language %s is not recognized', 'The languages %s are not recognized', len(bad)) % (', '.join(bad))
            return _('Unknown language'), msg, ''
        return None, None, None

    def commit(self, db, id_):
        cv = self.current_val
        if cv != self.original_val:
            db.set_languages(id_, cv)
        self.update_recently_used()
# }}}

# Identifiers {{{


class Identifiers(Dialog):

    def __init__(self, identifiers, parent=None):
        Dialog.__init__(self, _('Edit Identifiers'), 'edit-identifiers-dialog', parent=parent)
        self.text.setPlainText('\n'.join('%s:%s' % (k, identifiers[k]) for k in sorted(identifiers, key=sort_key)))

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)

        self.la = la = QLabel(_(
            'Edit the book\'s identifiers. Every identifier must be on a separate line, and have the form type:value'))
        la.setWordWrap(True)
        self.text = t = QPlainTextEdit(self)
        l.addWidget(la), l.addWidget(t)

        l.addWidget(self.bb)

    def get_identifiers(self, validate=False):
        from calibre.ebooks.metadata.book.base import Metadata
        mi = Metadata('xxx')
        ans = {}
        for line in self.text.toPlainText().splitlines():
            if line.strip():
                k, v = line.partition(':')[0::2]
                k, v = mi._clean_identifier(k.strip(), v.strip())
                if k and v:
                    if validate and k in ans:
                        error_dialog(self, _('Duplicate identifier'), _(
                            'The identifier of type: %s occurs more than once. Each type of identifier must be unique') % k, show=True)
                        return
                    ans[k] = v
                elif validate:
                    error_dialog(self, _('Invalid identifier'), _(
                        'The identifier %s is invalid. Identifiers must be of the form type:value') % line.strip(), show=True)
                    return
        return ans

    def sizeHint(self):
        return QSize(500, 400)

    def accept(self):
        if self.get_identifiers(validate=True) is None:
            return
        Dialog.accept(self)


class IdentifiersEdit(QLineEdit, ToMetadataMixin):
    LABEL = _('&Ids:')
    BASE_TT = _('Edit the identifiers for this book. '
            'For example: \n\n%s')%(
            'isbn:1565927249, doi:10.1000/182, amazon:1565927249')
    FIELD_NAME = 'identifiers'

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        self.pat = re.compile(r'[^0-9a-zA-Z]')
        self.textChanged.connect(self.validate)

    def contextMenuEvent(self, ev):
        m = self.createStandardContextMenu()
        first = m.actions()[0]
        ac = m.addAction(_('Edit identifiers in a dedicated window'), self.edit_identifiers)
        m.insertAction(first, ac)
        m.insertSeparator(first)
        m.exec_(ev.globalPos())

    def edit_identifiers(self):
        d = Identifiers(self.current_val, self)
        if d.exec_() == d.Accepted:
            self.current_val = d.get_identifiers()

    @dynamic_property
    def current_val(self):
        def fget(self):
            raw = unicode(self.text()).strip()
            parts = [clean_text(x) for x in raw.split(',')]
            ans = {}
            for x in parts:
                c = x.split(':')
                if len(c) > 1:
                    itype = c[0].lower()
                    c = ':'.join(c[1:])
                    if itype == 'isbn':
                        v = check_isbn(c)
                        if v is not None:
                            c = v
                    ans[itype] = c
            return ans

        def fset(self, val):
            if not val:
                val = {}

            def keygen(x):
                x = x[0]
                if x == 'isbn':
                    x = '00isbn'
                return x
            for k in list(val):
                if k == 'isbn':
                    v = check_isbn(k)
                    if v is not None:
                        val[k] = v
            ids = sorted(val.iteritems(), key=keygen)
            txt = ', '.join(['%s:%s'%(k.lower(), vl) for k, vl in ids])
            # Use selectAll + insert instead of setText so that undo works
            self.selectAll(), self.insert(txt.strip())
            self.setCursorPosition(0)
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.original_val = db.get_identifiers(id_, index_is_id=True)
        self.current_val = self.original_val

    def commit(self, db, id_):
        if self.original_val != self.current_val:
            db.set_identifiers(id_, self.current_val, notify=False, commit=False)

    def validate(self, *args):
        identifiers = self.current_val
        isbn = identifiers.get('isbn', '')
        tt = self.BASE_TT
        extra = ''
        if not isbn:
            col = 'none'
        elif check_isbn(isbn) is not None:
            col = OK_COLOR
            extra = '\n\n'+_('This ISBN number is valid')
        else:
            col = ERR_COLOR
            extra = '\n\n' + _('This ISBN number is invalid')
        self.setToolTip(tt+extra)
        self.setStyleSheet(INDICATOR_SHEET % col)

    def paste_isbn(self):
        text = unicode(QApplication.clipboard().text()).strip()
        if not text or not check_isbn(text):
            d = ISBNDialog(self, text)
            if not d.exec_():
                return
            text = d.text()
            if not text:
                return
        text = check_isbn(text)
        if text:
            vals = self.current_val
            vals['isbn'] = text
            self.current_val = vals

# }}}


class ISBNDialog(QDialog):  # {{{

    def __init__(self, parent, txt):
        QDialog.__init__(self, parent)
        l = QGridLayout()
        self.setLayout(l)
        self.setWindowTitle(_('Invalid ISBN'))
        w = QLabel(_('Enter an ISBN'))
        l.addWidget(w, 0, 0, 1, 2)
        w = QLabel(_('ISBN:'))
        l.addWidget(w, 1, 0, 1, 1)
        self.line_edit = w = QLineEdit()
        w.setText(txt)
        w.selectAll()
        w.textChanged.connect(self.checkText)
        l.addWidget(w, 1, 1, 1, 1)
        w = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(w, 2, 0, 1, 2)
        w.accepted.connect(self.accept)
        w.rejected.connect(self.reject)
        self.checkText(self.text())
        sz = self.sizeHint()
        sz.setWidth(sz.width()+50)
        self.resize(sz)

    def accept(self):
        isbn = unicode(self.line_edit.text())
        if not check_isbn(isbn):
            return error_dialog(self, _('Invalid ISBN'),
                    _('The ISBN you entered is not valid. Try again.'),
                    show=True)
        QDialog.accept(self)

    def checkText(self, txt):
        isbn = unicode(txt)
        if not isbn:
            col = 'none'
            extra = ''
        elif check_isbn(isbn) is not None:
            col = OK_COLOR
            extra = _('This ISBN number is valid')
        else:
            col = ERR_COLOR
            extra = _('This ISBN number is invalid')
        self.line_edit.setToolTip(extra)
        self.line_edit.setStyleSheet(INDICATOR_SHEET % col)

    def text(self):
        return check_isbn(unicode(self.line_edit.text()))

# }}}


class PublisherEdit(EditWithComplete, ToMetadataMixin):  # {{{
    LABEL = _('&Publisher:')
    FIELD_NAME = 'publisher'

    def __init__(self, parent):
        EditWithComplete.__init__(self, parent)
        self.set_separator(None)
        self.setSizeAdjustPolicy(
                self.AdjustToMinimumContentsLengthWithIcon)
        self.books_to_refresh = set([])
        self.clear_button = QToolButton(parent)
        self.clear_button.setIcon(QIcon(I('trash.png')))
        self.clear_button.setToolTip(_('Clear publisher'))
        self.clear_button.clicked.connect(self.clearEditText)

    @dynamic_property
    def current_val(self):

        def fget(self):
            return clean_text(unicode(self.currentText()))

        def fset(self, val):
            if not val:
                val = ''
            self.set_edit_text(val.strip())
            self.lineEdit().setCursorPosition(0)

        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.books_to_refresh = set([])
        all_publishers = db.all_publishers()
        all_publishers.sort(key=lambda x: sort_key(x[1]))
        self.update_items_cache([x[1] for x in all_publishers])
        publisher_id = db.publisher_id(id_, index_is_id=True)
        inval = ''
        for pid, name in all_publishers:
            if pid == publisher_id:
                inval = name
                break
        self.original_val = self.current_val = inval

    def commit(self, db, id_):
        self.books_to_refresh |= db.set_publisher(id_, self.current_val,
                            notify=False, commit=False, allow_case_change=True)
        return True

# }}}

# DateEdit {{{


class CalendarWidget(QCalendarWidget):

    def showEvent(self, ev):
        if self.selectedDate().year() == UNDEFINED_DATE.year:
            self.setSelectedDate(QDate.currentDate())


class DateEdit(make_undoable(QDateTimeEdit), ToMetadataMixin):

    TOOLTIP = ''
    LABEL = _('&Date:')
    FMT = 'dd MMM yyyy hh:mm:ss'
    ATTR = FIELD_NAME = 'timestamp'
    TWEAK = 'gui_timestamp_display_format'

    def __init__(self, parent, create_clear_button=True):
        super(DateEdit, self).__init__(parent)
        self.setToolTip(self.TOOLTIP)
        self.setWhatsThis(self.TOOLTIP)
        fmt = tweaks[self.TWEAK]
        if fmt is None:
            fmt = self.FMT
        self.setDisplayFormat(fmt)
        self.setCalendarPopup(True)
        self.cw = CalendarWidget(self)
        self.cw.setVerticalHeaderFormat(self.cw.NoVerticalHeader)
        self.setCalendarWidget(self.cw)
        self.setMinimumDateTime(UNDEFINED_QDATETIME)
        self.setSpecialValueText(_('Undefined'))
        if create_clear_button:
            self.clear_button = QToolButton(parent)
            self.clear_button.setIcon(QIcon(I('trash.png')))
            self.clear_button.setToolTip(_('Clear date'))
            self.clear_button.clicked.connect(self.reset_date)

    def reset_date(self, *args):
        self.current_val = None

    @dynamic_property
    def current_val(self):
        def fget(self):
            return qt_to_dt(self.dateTime(), as_utc=False)

        def fset(self, val):
            if val is None or is_date_undefined(val):
                val = UNDEFINED_DATE
            else:
                val = as_local_time(val)
            self.set_spinbox_value(val)
        return property(fget=fget, fset=fset)

    def initialize(self, db, id_):
        self.current_val = getattr(db, self.ATTR)(id_, index_is_id=True)
        self.original_val = self.current_val

    def commit(self, db, id_):
        if self.changed:
            getattr(db, 'set_'+self.ATTR)(id_, self.current_val, commit=False,
                notify=False)
        return True

    @property
    def changed(self):
        o, c = self.original_val, self.current_val
        return o != c

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Minus:
            ev.accept()
            self.setDateTime(self.minimumDateTime())
        elif ev.key() == Qt.Key_Equal:
            ev.accept()
            self.setDateTime(QDateTime.currentDateTime())
        elif ev.key() == Qt.Key_Up and is_date_undefined(self.current_val):
            self.setDateTime(QDateTime.currentDateTime())
        elif ev.key() == Qt.Key_Tab and is_date_undefined(self.current_val):
            ev.ignore()
        else:
            return super(DateEdit, self).keyPressEvent(ev)


class PubdateEdit(DateEdit):
    LABEL = _('P&ublished:')
    FMT = 'MMM yyyy'
    ATTR = FIELD_NAME = 'pubdate'
    TWEAK = 'gui_pubdate_display_format'

# }}}
