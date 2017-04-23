#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, errno
from datetime import datetime

from PyQt5.Qt import (Qt, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
        QGridLayout, pyqtSignal, QDialogButtonBox, QScrollArea, QFont, QCoreApplication,
        QTabWidget, QIcon, QToolButton, QSplitter, QGroupBox, QSpacerItem,
        QSizePolicy, QFrame, QSize, QKeySequence, QMenu, QShortcut, QDialog)

from calibre.constants import isosx
from calibre.ebooks.metadata import authors_to_string, string_to_authors
from calibre.gui2 import error_dialog, gprefs, pixmap_to_data
from calibre.gui2.metadata.basic_widgets import (TitleEdit, AuthorsEdit,
    AuthorSortEdit, TitleSortEdit, SeriesEdit, SeriesIndexEdit, IdentifiersEdit,
    RatingEdit, PublisherEdit, TagsEdit, FormatsManager, Cover, CommentsEdit,
    BuddyLabel, DateEdit, PubdateEdit, LanguagesEdit, RightClickButton)
from calibre.gui2.metadata.single_download import FullFetch
from calibre.gui2.custom_column_widgets import populate_metadata_page, Comments
from calibre.utils.config import tweaks
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.localization import canonicalize_lang
from calibre.utils.date import local_tz
from calibre.library.comments import merge_comments as merge_two_comments

BASE_TITLE = _('Edit Metadata')
fetched_fields = ('title', 'title_sort', 'authors', 'author_sort', 'series',
                  'series_index', 'languages', 'publisher', 'tags', 'rating',
                  'comments', 'pubdate')


class ScrollArea(QScrollArea):

    def __init__(self, widget=None, parent=None):
        QScrollArea.__init__(self, parent)
        self.setFrameShape(self.NoFrame)
        self.setWidgetResizable(True)
        if widget is not None:
            self.setWidget(widget)


class MetadataSingleDialogBase(QDialog):

    view_format = pyqtSignal(object, object)
    cc_two_column = tweaks['metadata_single_use_2_cols_for_custom_fields']
    one_line_comments_toolbar = False
    use_toolbutton_for_config_metadata = True

    def __init__(self, db, parent=None, editing_multiple=False):
        self.db = db
        self.changed = set()
        self.books_to_refresh = set()
        self.rows_to_refresh = set()
        self.metadata_before_fetch = None
        self.editing_multiple = editing_multiple
        self.comments_edit_state_at_apply = {}
        QDialog.__init__(self, parent)
        self.setupUi()

    def setupUi(self, *args):  # {{{
        self.download_shortcut = QShortcut(self)
        self.download_shortcut.setKey(QKeySequence('Ctrl+D',
            QKeySequence.PortableText))
        p = self.parent()
        if hasattr(p, 'keyboard'):
            kname = u'Interface Action: Edit Metadata (Edit Metadata) : menu action : download'
            sc = p.keyboard.keys_map.get(kname, None)
            if sc:
                self.download_shortcut.setKey(sc[0])
        self.swap_title_author_shortcut = s = QShortcut(self)
        s.setKey(QKeySequence('Alt+Down', QKeySequence.PortableText))

        self.button_box = bb = QDialogButtonBox(self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.next_button = QPushButton(QIcon(I('forward.png')), _('Next'),
                self)
        self.next_button.setShortcut(QKeySequence('Alt+Right'))
        self.next_button.clicked.connect(self.next_clicked)
        self.prev_button = QPushButton(QIcon(I('back.png')), _('Previous'),
                self)
        self.prev_button.setShortcut(QKeySequence('Alt+Left'))

        self.button_box.addButton(self.prev_button, bb.ActionRole)
        self.button_box.addButton(self.next_button, bb.ActionRole)
        self.prev_button.clicked.connect(self.prev_clicked)
        bb.setStandardButtons(bb.Ok|bb.Cancel)
        bb.button(bb.Ok).setDefault(True)

        self.central_widget = QTabWidget(self)

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)
        self.l.addWidget(self.central_widget)
        ll = self.button_box_layout = QHBoxLayout()
        self.l.addLayout(ll)
        ll.addSpacing(10)
        ll.addWidget(self.button_box)

        self.setWindowIcon(QIcon(I('edit_input.png')))
        self.setWindowTitle(BASE_TITLE)

        self.create_basic_metadata_widgets()

        if len(self.db.custom_column_label_map):
            self.create_custom_metadata_widgets()
        self.comments_edit_state_at_apply = {self.comments:None}

        self.do_layout()
        geom = gprefs.get('metasingle_window_geometry3', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))
        else:
            self.resize(self.sizeHint())
    # }}}

    def sizeHint(self):
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = max(300, geom.height()-50), max(400, geom.width()-70)
        return QSize(nw, nh)

    def create_basic_metadata_widgets(self):  # {{{
        self.basic_metadata_widgets = []

        self.languages = LanguagesEdit(self)
        self.basic_metadata_widgets.append(self.languages)

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
                self.deduce_title_sort_button, self.languages)
        self.basic_metadata_widgets.extend([self.title, self.title_sort])

        self.deduce_author_sort_button = b = RightClickButton(self)
        b.setToolTip('<p>' +
            _('Automatically create the author sort entry based on the current '
              'author entry. Using this button to create author sort will '
              'change author sort from red to green.  There is a menu of '
              'functions available under this button. Click and hold '
              'on the button to see it.') + '</p>')
        if isosx:
            # Workaround for https://bugreports.qt-project.org/browse/QTBUG-41017
            class Menu(QMenu):

                def mouseReleaseEvent(self, ev):
                    ac = self.actionAt(ev.pos())
                    if ac is not None:
                        ac.trigger()
                    return QMenu.mouseReleaseEvent(self, ev)
            b.m = m = Menu()
        else:
            b.m = m = QMenu()
        ac = m.addAction(QIcon(I('forward.png')), _('Set author sort from author'))
        ac2 = m.addAction(QIcon(I('back.png')), _('Set author from author sort'))
        ac3 = m.addAction(QIcon(I('user_profile.png')), _('Manage authors'))
        ac4 = m.addAction(QIcon(I('next.png')),
                _('Copy author to author sort'))
        ac5 = m.addAction(QIcon(I('previous.png')),
                _('Copy author sort to author'))

        b.setMenu(m)
        self.authors = AuthorsEdit(self, ac3)
        self.author_sort = AuthorSortEdit(self, self.authors, b, self.db, ac,
                ac2, ac4, ac5)
        self.basic_metadata_widgets.extend([self.authors, self.author_sort])

        self.swap_title_author_button = QToolButton(self)
        self.swap_title_author_button.setIcon(QIcon(I('swap.png')))
        self.swap_title_author_button.setToolTip(_(
            'Swap the author and title') + ' [%s]' % self.swap_title_author_shortcut.key().toString(QKeySequence.NativeText))
        self.swap_title_author_button.clicked.connect(self.swap_title_author)
        self.swap_title_author_shortcut.activated.connect(self.swap_title_author_button.click)

        self.manage_authors_button = QToolButton(self)
        self.manage_authors_button.setIcon(QIcon(I('user_profile.png')))
        self.manage_authors_button.setToolTip('<p>' + _(
            'Manage authors. Use to rename authors and correct '
            'individual author\'s sort values') + '</p>')
        self.manage_authors_button.clicked.connect(self.authors.manage_authors)

        self.series = SeriesEdit(self)
        self.clear_series_button = QToolButton(self)
        self.clear_series_button.setToolTip(
               _('Clear series'))
        self.clear_series_button.clicked.connect(self.series.clear)
        self.series_index = SeriesIndexEdit(self, self.series)
        self.basic_metadata_widgets.extend([self.series, self.series_index])

        self.formats_manager = FormatsManager(self, self.copy_fmt)
        # We want formats changes to be committed before title/author, as
        # otherwise we could have data loss if the title/author changed and the
        # user was trying to add an extra file from the old books directory.
        self.basic_metadata_widgets.insert(0, self.formats_manager)
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
        self.clear_ratings_button = QToolButton(self)
        self.clear_ratings_button.setToolTip(_('Clear rating'))
        self.clear_ratings_button.setIcon(QIcon(I('trash.png')))
        self.clear_ratings_button.clicked.connect(self.rating.zero)

        self.basic_metadata_widgets.append(self.rating)

        self.tags = TagsEdit(self)
        self.tags_editor_button = QToolButton(self)
        self.tags_editor_button.setToolTip(_('Open Tag Editor'))
        self.tags_editor_button.setIcon(QIcon(I('chapters.png')))
        self.tags_editor_button.clicked.connect(self.tags_editor)
        self.clear_tags_button = QToolButton(self)
        self.clear_tags_button.setToolTip(_('Clear all tags'))
        self.clear_tags_button.setIcon(QIcon(I('trash.png')))
        self.clear_tags_button.clicked.connect(self.tags.clear)
        self.basic_metadata_widgets.append(self.tags)

        self.identifiers = IdentifiersEdit(self)
        self.basic_metadata_widgets.append(self.identifiers)
        self.clear_identifiers_button = QToolButton(self)
        self.clear_identifiers_button.setIcon(QIcon(I('trash.png')))
        self.clear_identifiers_button.setToolTip(_('Clear Ids'))
        self.clear_identifiers_button.clicked.connect(self.identifiers.clear)
        self.paste_isbn_button = QToolButton(self)
        self.paste_isbn_button.setToolTip('<p>' +
                    _('Paste the contents of the clipboard into the '
                      'identifiers box prefixed with isbn:') + '</p>')
        self.paste_isbn_button.setIcon(QIcon(I('edit-paste.png')))
        self.paste_isbn_button.clicked.connect(self.identifiers.paste_isbn)

        self.publisher = PublisherEdit(self)
        self.basic_metadata_widgets.append(self.publisher)

        self.timestamp = DateEdit(self)
        self.pubdate = PubdateEdit(self)
        self.basic_metadata_widgets.extend([self.timestamp, self.pubdate])

        self.fetch_metadata_button = b = RightClickButton(self)
        # The following rigmarole is needed so that Qt gives the button the
        # same height as the other buttons in the dialog. There is no way to
        # center the text in a QToolButton with an icon, so we cant just set an
        # icon
        b.setIcon(QIcon(I('download-metadata.png')))
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setMinimumHeight(b.sizeHint().height())
        b.setIcon(QIcon())
        b.setText(_('&Download metadata')), b.setPopupMode(b.DelayedPopup)
        b.setToolTip(_('Download metadata for this book [%s]') % self.download_shortcut.key().toString(QKeySequence.NativeText))
        b.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.fetch_metadata_button.clicked.connect(self.fetch_metadata)
        self.fetch_metadata_menu = m = QMenu(self.fetch_metadata_button)
        m.addAction(QIcon(I('edit-undo.png')), _('Undo last metadata download'), self.undo_fetch_metadata)
        self.fetch_metadata_button.setMenu(m)
        self.download_shortcut.activated.connect(self.fetch_metadata_button.click)
        font = self.fmb_font = QFont()
        font.setBold(True)
        self.fetch_metadata_button.setFont(font)

        if self.use_toolbutton_for_config_metadata:
            self.config_metadata_button = QToolButton(self)
            self.config_metadata_button.setIcon(QIcon(I('config.png')))
        else:
            self.config_metadata_button = QPushButton(self)
            self.config_metadata_button.setText(_('Configure download metadata'))
        self.config_metadata_button.setIcon(QIcon(I('config.png')))
        self.config_metadata_button.clicked.connect(self.configure_metadata)
        self.config_metadata_button.setToolTip(
            _('Change how calibre downloads metadata'))

    # }}}

    def create_custom_metadata_widgets(self):  # {{{
        self.custom_metadata_widgets_parent = w = QWidget(self)
        layout = QGridLayout()
        w.setLayout(layout)
        self.custom_metadata_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, None, parent=w, bulk=False,
                two_column=self.cc_two_column)
        self.__custom_col_layouts = [layout]
        for widget in self.custom_metadata_widgets:
            if isinstance(widget, Comments):
                self.comments_edit_state_at_apply[widget] = None
    # }}}

    def set_custom_metadata_tab_order(self, before=None, after=None):  # {{{
        sto = QWidget.setTabOrder
        if getattr(self, 'custom_metadata_widgets', []):
            ans = self.custom_metadata_widgets
            for i in range(len(ans)-1):
                if before is not None and i == 0:
                    pass
                if len(ans[i+1].widgets) == 2:
                    sto(ans[i].widgets[-1], ans[i+1].widgets[1])
                else:
                    sto(ans[i].widgets[-1], ans[i+1].widgets[0])
                for c in range(2, len(ans[i].widgets), 2):
                    sto(ans[i].widgets[c-1], ans[i].widgets[c+1])
            if after is not None:
                pass
    # }}}

    def do_view_format(self, path, fmt):
        if path:
            self.view_format.emit(None, path)
        else:
            self.view_format.emit(self.book_id, fmt)

    def copy_fmt(self, fmt, f):
        self.db.copy_format_to(self.book_id, fmt, f, index_is_id=True)

    def do_layout(self):
        raise NotImplementedError()

    def __call__(self, id_):
        self.book_id = id_
        self.books_to_refresh = set([])
        self.metadata_before_fetch = None
        for widget in self.basic_metadata_widgets:
            widget.initialize(self.db, id_)
        for widget in getattr(self, 'custom_metadata_widgets', []):
            widget.initialize(id_)
        if callable(self.set_current_callback):
            self.set_current_callback(id_)
        # Commented out as it doesn't play nice with Next, Prev buttons
        # self.fetch_metadata_button.setFocus(Qt.OtherFocusReason)

    # Miscellaneous interaction methods {{{
    def update_window_title(self, *args):
        title = self.title.current_val
        if len(title) > 50:
            title = title[:50] + u'\u2026'
        self.setWindowTitle(BASE_TITLE + ' - ' +
                title + ' - ' +
                _(' [%(num)d of %(tot)d]')%dict(num=self.current_row+1,
                tot=len(self.row_list)))

    def swap_title_author(self, *args):
        title = self.title.current_val
        self.title.current_val = authors_to_string(self.authors.current_val)
        self.authors.current_val = string_to_authors(title)
        self.title_sort.auto_generate()
        self.author_sort.auto_generate()

    def tags_editor(self, *args):
        self.tags.edit(self.db, self.book_id)

    def metadata_from_format(self, *args):
        mi, ext = self.formats_manager.get_selected_format_metadata(self.db,
                self.book_id)
        if mi is not None:
            self.update_from_mi(mi)

    def get_pdf_cover(self):
        pdfpath = self.formats_manager.get_format_path(self.db, self.book_id,
                                                       'pdf')
        from calibre.gui2.metadata.pdf_covers import PDFCovers
        d = PDFCovers(pdfpath, parent=self)
        if d.exec_() == d.Accepted:
            cpath = d.cover_path
            if cpath:
                with open(cpath, 'rb') as f:
                    self.update_cover(f.read(), 'PDF')
        d.cleanup()

    def cover_from_format(self, *args):
        ext = self.formats_manager.get_selected_format()
        if ext is None:
            return
        if ext == 'pdf':
            return self.get_pdf_cover()
        try:
            mi, ext = self.formats_manager.get_selected_format_metadata(self.db,
                    self.book_id)
        except (IOError, OSError) as err:
            if getattr(err, 'errno', None) == errno.EACCES:  # Permission denied
                import traceback
                fname = err.filename if err.filename else 'file'
                error_dialog(self, _('Permission denied'),
                        _('Could not open %s. Is it being used by another'
                        ' program?')%fname, det_msg=traceback.format_exc(),
                        show=True)
                return
            raise
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
        self.update_cover(cdata, ext)

    def update_cover(self, cdata, fmt):
        orig = self.cover.current_val
        self.cover.current_val = cdata
        if self.cover.current_val is None:
            self.cover.current_val = orig
            return error_dialog(self, _('Could not read cover'),
                         _('The cover in the %s format is invalid')%fmt,
                         show=True)
            return

    def update_from_mi(self, mi, update_sorts=True, merge_tags=True, merge_comments=False):
        fw = self.focusWidget()
        if not mi.is_null('title'):
            self.title.set_value(mi.title)
            if update_sorts:
                self.title_sort.auto_generate()
        if not mi.is_null('authors'):
            self.authors.set_value(mi.authors)
        if not mi.is_null('author_sort'):
            self.author_sort.set_value(mi.author_sort)
        elif update_sorts and not mi.is_null('authors'):
            self.author_sort.auto_generate()
        if not mi.is_null('rating'):
            self.rating.set_value(mi.rating * 2)
        if not mi.is_null('publisher'):
            self.publisher.set_value(mi.publisher)
        if not mi.is_null('tags'):
            old_tags = self.tags.current_val
            tags = mi.tags if mi.tags else []
            if old_tags and merge_tags:
                ltags, lotags = {t.lower() for t in tags}, {t.lower() for t in
                        old_tags}
                tags = [t for t in tags if t.lower() in ltags-lotags] + old_tags
            self.tags.set_value(tags)
        if not mi.is_null('identifiers'):
            current = self.identifiers.current_val
            current.update(mi.identifiers)
            self.identifiers.set_value(current)
        if not mi.is_null('pubdate'):
            self.pubdate.set_value(mi.pubdate)
        if not mi.is_null('series') and mi.series.strip():
            self.series.set_value(mi.series)
            if mi.series_index is not None:
                self.series_index.reset_original()
                self.series_index.set_value(float(mi.series_index))
        if not mi.is_null('languages'):
            langs = [canonicalize_lang(x) for x in mi.languages]
            langs = [x for x in langs if x is not None]
            if langs:
                self.languages.set_value(langs)
        if mi.comments and mi.comments.strip():
            val = mi.comments
            if val and merge_comments:
                cval = self.comments.current_val
                if cval:
                    val = merge_two_comments(cval, val)
            self.comments.set_value(val)
        if fw is not None:
            fw.setFocus(Qt.OtherFocusReason)

    def fetch_metadata(self, *args):
        from calibre.ebooks.metadata.sources.update import update_sources
        update_sources()
        d = FullFetch(self.cover.pixmap(), self)
        ret = d.start(title=self.title.current_val, authors=self.authors.current_val,
                identifiers=self.identifiers.current_val)
        if ret == d.Accepted:
            self.metadata_before_fetch = {f:getattr(self, f).current_val for f in fetched_fields}
            from calibre.ebooks.metadata.sources.prefs import msprefs
            mi = d.book
            dummy = Metadata(_('Unknown'))
            for f in msprefs['ignore_fields']:
                if ':' not in f:
                    setattr(mi, f, getattr(dummy, f))
            if mi is not None:
                pd = mi.pubdate
                if pd is not None:
                    # Put the downloaded published date into the local timezone
                    # as we discard time info and the date is timezone
                    # invariant. This prevents the as_local_timezone() call in
                    # update_from_mi from changing the pubdate
                    mi.pubdate = datetime(pd.year, pd.month, pd.day,
                            tzinfo=local_tz)
                self.update_from_mi(mi, merge_comments=msprefs['append_comments'])
            if d.cover_pixmap is not None:
                self.metadata_before_fetch['cover'] = self.cover.current_val
                self.cover.current_val = pixmap_to_data(d.cover_pixmap)

    def undo_fetch_metadata(self):
        if self.metadata_before_fetch is None:
            return error_dialog(self, _('No downloaded metadata'), _(
                'There is no downloaded metadata to undo'), show=True)
        for field, val in self.metadata_before_fetch.iteritems():
            getattr(self, field).current_val = val
        self.metadata_before_fetch = None

    def configure_metadata(self):
        from calibre.gui2.preferences import show_config_widget
        gui = self.parent()
        show_config_widget('Sharing', 'Metadata download', parent=self,
                gui=gui, never_shutdown=True)

    def download_cover(self, *args):
        from calibre.ebooks.metadata.sources.update import update_sources
        update_sources()
        from calibre.gui2.metadata.single_download import CoverFetch
        d = CoverFetch(self.cover.pixmap(), self)
        ret = d.start(self.title.current_val, self.authors.current_val,
                self.identifiers.current_val)
        if ret == d.Accepted:
            if d.cover_pixmap is not None:
                self.cover.current_val = pixmap_to_data(d.cover_pixmap)

    # }}}

    def to_book_metadata(self):
        mi = Metadata(_('Unknown'))
        if self.db is None:
            return mi
        mi.set_all_user_metadata(self.db.field_metadata.custom_field_metadata())
        for widget in self.basic_metadata_widgets:
            widget.apply_to_metadata(mi)
        for widget in getattr(self, 'custom_metadata_widgets', []):
            widget.apply_to_metadata(mi)
        return mi

    def apply_changes(self):
        self.changed.add(self.book_id)
        if self.db is None:
            # break_cycles has already been called, don't know why this should
            # happen but a user reported it
            return True
        self.comments_edit_state_at_apply = {w:w.tab for w in self.comments_edit_state_at_apply}
        for widget in self.basic_metadata_widgets:
            try:
                if hasattr(widget, 'validate_for_commit'):
                    title, msg, det_msg = widget.validate_for_commit()
                    if title is not None:
                        error_dialog(self, title, msg, det_msg=det_msg, show=True)
                        return False
                widget.commit(self.db, self.book_id)
                self.books_to_refresh |= getattr(widget, 'books_to_refresh', set())
            except (IOError, OSError) as err:
                if getattr(err, 'errno', None) == errno.EACCES:  # Permission denied
                    import traceback
                    fname = getattr(err, 'filename', None)
                    p = 'Locked file: %s\n\n'%fname if fname else ''
                    error_dialog(self, _('Permission denied'),
                            _('Could not change the on disk location of this'
                                ' book. Is it open in another program?'),
                            det_msg=p+traceback.format_exc(), show=True)
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
        if self.editing_multiple and self.current_row != len(self.row_list) - 1:
            num = len(self.row_list) - 1 - self.current_row
            from calibre.gui2 import question_dialog
            pm = ngettext('There is another book to edit in this set.',
                          'There are still {} more books to edit in this set.', num).format(num)
            if not question_dialog(
                    self, _('Are you sure?'), pm + _(
                      ' Are you sure you want to stop? Use the "Next" button'
                      ' instead of the "OK" button to move through books in the set.'),
                    yes_text=_('&Stop editing'), no_text=_('&Continue editing'),
                    yes_icon='dot_red.png', no_icon='dot_green.png',
                    default_yes=False, skip_dialog_name='edit-metadata-single-confirm-ok-on-multiple'):
                return self.do_one(delta=1, apply_changes=False)
        QDialog.accept(self)

    def reject(self):
        self.save_state()
        QDialog.reject(self)

    def save_state(self):
        try:
            gprefs['metasingle_window_geometry3'] = bytearray(self.saveGeometry())
        except:
            # Weird failure, see https://bugs.launchpad.net/bugs/995271
            import traceback
            traceback.print_exc()

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

    def next_clicked(self):
        if not self.apply_changes():
            return
        self.do_one(delta=1, apply_changes=False)

    def prev_clicked(self):
        if not self.apply_changes():
            return
        self.do_one(delta=-1, apply_changes=False)

    def do_one(self, delta=0, apply_changes=True):
        if apply_changes:
            self.apply_changes()
        self.current_row += delta
        self.update_window_title()
        prev = next_ = None
        if self.current_row > 0:
            prev = self.db.title(self.row_list[self.current_row-1])
        if self.current_row < len(self.row_list) - 1:
            next_ = self.db.title(self.row_list[self.current_row+1])

        if next_ is not None:
            tip = (_('Save changes and edit the metadata of %s')+
                    ' [Alt+Right]')%next_
            self.next_button.setToolTip(tip)
        self.next_button.setEnabled(next_ is not None)
        if prev is not None:
            tip = (_('Save changes and edit the metadata of %s')+
                    ' [Alt+Left]')%prev
            self.prev_button.setToolTip(tip)
        self.prev_button.setEnabled(prev is not None)
        self.button_box.button(self.button_box.Ok).setDefault(True)
        self.button_box.button(self.button_box.Ok).setFocus(Qt.OtherFocusReason)
        self(self.db.id(self.row_list[self.current_row]))
        for w, state in self.comments_edit_state_at_apply.iteritems():
            if state == 'code':
                w.tab = 'code'

    def break_cycles(self):
        # Break any reference cycles that could prevent python
        # from garbage collecting this dialog
        self.set_current_callback = self.db = None
        self.metadata_before_fetch = None

        def disconnect(signal):
            try:
                signal.disconnect()
            except:
                pass  # Fails if view format was never connected
        disconnect(self.view_format)
        for b in ('next_button', 'prev_button'):
            x = getattr(self, b, None)
            if x is not None:
                disconnect(x.clicked)
        for widget in self.basic_metadata_widgets:
            bc = getattr(widget, 'break_cycles', None)
            if bc is not None and callable(bc):
                bc()
        for widget in getattr(self, 'custom_metadata_widgets', []):
            widget.break_cycles()

    # }}}


class Splitter(QSplitter):

    frame_resized = pyqtSignal(object)

    def resizeEvent(self, ev):
        self.frame_resized.emit(ev)
        return QSplitter.resizeEvent(self, ev)


class MetadataSingleDialog(MetadataSingleDialogBase):  # {{{

    def do_layout(self):
        if len(self.db.custom_column_label_map) == 0:
            self.central_widget.tabBar().setVisible(False)
        self.central_widget.clear()
        self.tabs = []
        self.labels = []
        self.tabs.append(QWidget(self))
        self.central_widget.addTab(ScrollArea(self.tabs[0], self), _("&Basic metadata"))
        self.tabs[0].l = l = QVBoxLayout()
        self.tabs[0].tl = tl = QGridLayout()
        self.tabs[0].setLayout(l)
        w = getattr(self, 'custom_metadata_widgets_parent', None)
        if w is not None:
            self.tabs.append(w)
            self.central_widget.addTab(ScrollArea(w, self), _('&Custom metadata'))
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

        tl.addWidget(self.swap_title_author_button, 0, 0, 1, 1)
        tl.addWidget(self.manage_authors_button, 1, 0, 1, 1)

        create_row(0, self.title, self.deduce_title_sort_button, self.title_sort)
        sto(self.title_sort, self.authors)
        create_row(1, self.authors, self.deduce_author_sort_button, self.author_sort)
        sto(self.author_sort, self.series)
        create_row(2, self.series, self.clear_series_button,
                self.series_index, icon='trash.png')
        sto(self.series_index, self.swap_title_author_button)
        sto(self.swap_title_author_button, self.manage_authors_button)

        tl.addWidget(self.formats_manager, 0, 6, 3, 1)

        self.splitter = Splitter(Qt.Horizontal, self)
        self.splitter.addWidget(self.cover)
        self.splitter.frame_resized.connect(self.cover.frame_resized)
        l.addWidget(self.splitter)
        self.tabs[0].gb = gb = QGroupBox(_('Change cover'), self)
        gb.l = l = QGridLayout()
        gb.setLayout(l)
        sto(self.manage_authors_button, self.cover.buttons[0])
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
        self.splitter.addWidget(w)

        def create_row2(row, widget, button=None, front_button=None):
            row += 1
            ql = BuddyLabel(widget)
            if front_button:
                ltl = QHBoxLayout()
                ltl.addWidget(front_button)
                ltl.addWidget(ql)
                l.addLayout(ltl, row, 0, 1, 1)
            else:
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
        create_row2(1, self.rating, self.clear_ratings_button)
        sto(self.rating, self.clear_ratings_button)
        sto(self.clear_ratings_button, self.tags_editor_button)
        sto(self.tags_editor_button, self.tags)
        create_row2(2, self.tags, self.clear_tags_button, front_button=self.tags_editor_button)
        sto(self.clear_tags_button, self.paste_isbn_button)
        sto(self.paste_isbn_button, self.identifiers)
        create_row2(3, self.identifiers, self.clear_identifiers_button,
                                        front_button=self.paste_isbn_button)
        sto(self.clear_identifiers_button, self.timestamp)
        create_row2(4, self.timestamp, self.timestamp.clear_button)
        sto(self.timestamp.clear_button, self.pubdate)
        create_row2(5, self.pubdate, self.pubdate.clear_button)
        sto(self.pubdate.clear_button, self.publisher)
        create_row2(6, self.publisher, self.publisher.clear_button)
        sto(self.publisher.clear_button, self.languages)
        create_row2(7, self.languages)
        self.tabs[0].spc_two = QSpacerItem(10, 10, QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        l.addItem(self.tabs[0].spc_two, 9, 0, 1, 3)
        l.addWidget(self.fetch_metadata_button, 10, 0, 1, 2)
        l.addWidget(self.config_metadata_button, 10, 2, 1, 1)

        self.tabs[0].gb2 = gb = QGroupBox(_('Co&mments'), self)
        gb.l = l = QVBoxLayout()
        gb.setLayout(l)
        l.addWidget(self.comments)
        self.splitter.addWidget(gb)

        self.set_custom_metadata_tab_order()

# }}}


class DragTrackingWidget(QWidget):  # {{{

    def __init__(self, parent, on_drag_enter):
        QWidget.__init__(self, parent)
        self.on_drag_enter = on_drag_enter

    def dragEnterEvent(self, ev):
        self.on_drag_enter.emit()

# }}}


class MetadataSingleDialogAlt1(MetadataSingleDialogBase):  # {{{

    cc_two_column = False
    one_line_comments_toolbar = True
    use_toolbutton_for_config_metadata = False

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
        self.central_widget.addTab(ScrollArea(self.tabs[0], self), _("&Metadata"))
        self.tabs[0].l = QGridLayout()
        self.tabs[0].setLayout(self.tabs[0].l)

        self.tabs.append(QWidget(self))
        self.central_widget.addTab(ScrollArea(self.tabs[1], self), _("&Cover and formats"))
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

        self.button_box_layout.insertWidget(1, self.fetch_metadata_button)
        self.button_box_layout.insertWidget(2, self.config_metadata_button)
        sto(self.button_box, self.fetch_metadata_button)
        sto(self.fetch_metadata_button, self.config_metadata_button)
        sto(self.config_metadata_button, self.title)

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
        tl.addWidget(self.manage_authors_button, 2, 0, 1, 1)
        tl.addWidget(self.paste_isbn_button, 12, 0, 1, 1)
        tl.addWidget(self.tags_editor_button, 6, 0, 1, 1)

        create_row(0, self.title, self.title_sort,
                   button=self.deduce_title_sort_button, span=2,
                   icon='auto_author_sort.png')
        create_row(1, self.title_sort, self.authors)
        create_row(2, self.authors, self.author_sort,
                   button=self.deduce_author_sort_button,
                   span=2, icon='auto_author_sort.png')
        create_row(3, self.author_sort, self.series)
        create_row(4, self.series, self.series_index,
                   button=self.clear_series_button, icon='trash.png')
        create_row(5, self.series_index, self.tags)
        create_row(6, self.tags, self.rating, button=self.clear_tags_button)
        create_row(7, self.rating, self.pubdate, button=self.clear_ratings_button)
        create_row(8, self.pubdate, self.publisher,
                   button=self.pubdate.clear_button, icon='trash.png')
        create_row(9, self.publisher, self.languages, button=self.publisher.clear_button, icon='trash.png')
        create_row(10, self.languages, self.timestamp)
        create_row(11, self.timestamp, self.identifiers,
                   button=self.timestamp.clear_button, icon='trash.png')
        create_row(12, self.identifiers, self.comments,
                   button=self.clear_identifiers_button, icon='trash.png')
        sto(self.clear_identifiers_button, self.swap_title_author_button)
        sto(self.swap_title_author_button, self.manage_authors_button)
        sto(self.manage_authors_button, self.tags_editor_button)
        sto(self.tags_editor_button, self.paste_isbn_button)
        tl.addItem(QSpacerItem(1, 1, QSizePolicy.Fixed, QSizePolicy.Expanding),
                   13, 1, 1 ,1)

        w = getattr(self, 'custom_metadata_widgets_parent', None)
        if w is not None:
            gb = QGroupBox(_('C&ustom metadata'), tab0)
            gbl = QVBoxLayout()
            gb.setLayout(gbl)
            sr = QScrollArea(tab0)
            sr.setWidgetResizable(True)
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


class MetadataSingleDialogAlt2(MetadataSingleDialogBase):  # {{{

    cc_two_column = False
    one_line_comments_toolbar = True
    use_toolbutton_for_config_metadata = False

    def do_layout(self):
        self.central_widget.clear()
        self.labels = []
        sto = QWidget.setTabOrder

        self.central_widget.tabBar().setVisible(False)
        tab0 = QWidget(self)
        self.central_widget.addTab(ScrollArea(tab0, self), _("&Metadata"))
        l = QGridLayout()
        tab0.setLayout(l)

        # Basic metadata in col 0
        tl = QGridLayout()
        gb = QGroupBox(_('Basic metadata'), tab0)
        l.addWidget(gb, 0, 0, 1, 1)
        gb.setLayout(tl)

        self.button_box_layout.insertWidget(1, self.fetch_metadata_button)
        self.button_box_layout.insertWidget(2, self.config_metadata_button)
        sto(self.button_box, self.fetch_metadata_button)
        sto(self.fetch_metadata_button, self.config_metadata_button)
        sto(self.config_metadata_button, self.title)

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
        tl.addWidget(self.manage_authors_button, 2, 0, 2, 1)
        tl.addWidget(self.paste_isbn_button, 12, 0, 1, 1)
        tl.addWidget(self.tags_editor_button, 6, 0, 1, 1)

        create_row(0, self.title, self.title_sort,
                   button=self.deduce_title_sort_button, span=2,
                   icon='auto_author_sort.png')
        create_row(1, self.title_sort, self.authors)
        create_row(2, self.authors, self.author_sort,
                   button=self.deduce_author_sort_button,
                   span=2, icon='auto_author_sort.png')
        create_row(3, self.author_sort, self.series)
        create_row(4, self.series, self.series_index,
                   button=self.clear_series_button, icon='trash.png')
        create_row(5, self.series_index, self.tags)
        create_row(6, self.tags, self.rating, button=self.clear_tags_button)
        create_row(7, self.rating, self.pubdate, button=self.clear_ratings_button)
        create_row(8, self.pubdate, self.publisher,
                   button=self.pubdate.clear_button, icon='trash.png')
        create_row(9, self.publisher, self.languages,
                   button=self.publisher.clear_button, icon='trash.png')
        create_row(10, self.languages, self.timestamp)
        create_row(11, self.timestamp, self.identifiers,
                   button=self.timestamp.clear_button, icon='trash.png')
        create_row(12, self.identifiers, self.comments,
                   button=self.clear_identifiers_button, icon='trash.png')
        sto(self.clear_identifiers_button, self.swap_title_author_button)
        sto(self.swap_title_author_button, self.manage_authors_button)
        sto(self.manage_authors_button, self.tags_editor_button)
        sto(self.tags_editor_button, self.paste_isbn_button)
        tl.addItem(QSpacerItem(1, 1, QSizePolicy.Fixed, QSizePolicy.Expanding),
                   13, 1, 1 ,1)

        # Custom metadata in col 1
        w = getattr(self, 'custom_metadata_widgets_parent', None)
        if w is not None:
            gb = QGroupBox(_('Custom metadata'), tab0)
            gbl = QVBoxLayout()
            gb.setLayout(gbl)
            sr = QScrollArea(gb)
            sr.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sr.setWidgetResizable(True)
            sr.setFrameStyle(QFrame.NoFrame)
            sr.setWidget(w)
            gbl.addWidget(sr)
            l.addWidget(gb, 0, 1, 1, 1)
            sp = QSizePolicy()
            sp.setVerticalStretch(10)
            sp.setHorizontalPolicy(QSizePolicy.Minimum)
            sp.setVerticalPolicy(QSizePolicy.Expanding)
            gb.setSizePolicy(sp)
            self.set_custom_metadata_tab_order()

        # comments span col 0 & 1
        w = QGroupBox(_('Comments'), tab0)
        sp = QSizePolicy()
        sp.setVerticalStretch(10)
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        sp.setVerticalPolicy(QSizePolicy.Expanding)
        w.setSizePolicy(sp)
        lb = QHBoxLayout()
        w.setLayout(lb)
        lb.addWidget(self.comments)
        l.addWidget(w, 1, 0, 1, 2)

        # Cover & formats in col 3
        gb = QGroupBox(_('Cover'), tab0)
        lb = QGridLayout()
        gb.setLayout(lb)
        lb.addWidget(self.cover, 0, 0, 1, 3, alignment=Qt.AlignCenter)
        sto(self.manage_authors_button, self.cover.buttons[0])
        for i, b in enumerate(self.cover.buttons[:3]):
            lb.addWidget(b, 1, i, 1, 1)
            sto(b, self.cover.buttons[i+1])
        hl = QHBoxLayout()
        for b in self.cover.buttons[3:]:
            hl.addWidget(b)
        sto(self.cover.buttons[-2], self.cover.buttons[-1])
        lb.addLayout(hl, 2, 0, 1, 3)
        l.addWidget(gb, 0, 2, 1, 1)
        l.addWidget(self.formats_manager, 1, 2, 1, 1)
        sto(self.cover.buttons[-1], self.formats_manager)

        self.formats_manager.formats.setMaximumWidth(10000)
        self.formats_manager.formats.setIconSize(QSize(32, 32))

# }}}


editors = {'default': MetadataSingleDialog, 'alt1': MetadataSingleDialogAlt1,
           'alt2': MetadataSingleDialogAlt2}


def edit_metadata(db, row_list, current_row, parent=None, view_slot=None,
        set_current_callback=None, editing_multiple=False):
    cls = gprefs.get('edit_metadata_single_layout', '')
    if cls not in editors:
        cls = 'default'
    d = editors[cls](db, parent, editing_multiple=editing_multiple)
    try:
        d.start(row_list, current_row, view_slot=view_slot,
                set_current_callback=set_current_callback)
        return d.changed, d.rows_to_refresh
    finally:
        # possible workaround for bug reports of occasional ghost edit metadata dialog on windows
        d.deleteLater()


if __name__ == '__main__':
    from calibre.gui2 import Application as QApplication
    app = QApplication([])
    from calibre.library import db
    db = db()
    row_list = list(range(len(db.data)))
    edit_metadata(db, row_list, 0)
