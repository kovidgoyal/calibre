#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, uuid, re

from PyQt4.Qt import QPixmap, SIGNAL

from calibre.gui2 import choose_images, error_dialog
from calibre.gui2.convert.metadata_ui import Ui_Form
from calibre.ebooks.metadata import (string_to_authors, MetaInformation,
        title_sort)
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.convert import Widget
from calibre.utils.icu import sort_key
from calibre.library.comments import comments_to_html
from calibre.utils.config import tweaks

def create_opf_file(db, book_id):
    mi = db.get_metadata(book_id, index_is_id=True)
    mi.application_id = uuid.uuid4()
    old_cover = mi.cover
    mi.cover = None
    raw = metadata_to_opf(mi)
    mi.cover = old_cover
    opf_file = PersistentTemporaryFile('.opf')
    opf_file.write(raw)
    opf_file.close()
    return mi, opf_file

def create_cover_file(db, book_id):
    cover = db.cover(book_id, index_is_id=True)
    cf = None
    if cover:
        cf = PersistentTemporaryFile('.jpeg')
        cf.write(cover)
        cf.close()
    return cf

class MetadataWidget(Widget, Ui_Form):

    TITLE = _('Metadata')
    ICON  = I('dialog_information.png')
    HELP  = _('Set the metadata. The output file will contain as much of this '
            'metadata as possible.')
    COMMIT_NAME = 'metadata'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['prefer_metadata_cover'])
        self.db, self.book_id = db, book_id
        self.cover_changed = False
        self.cover_data = None
        if self.db is not None:
            self.initialize_metadata_options()
        self.initialize_options(get_option, get_help, db, book_id)
        self.connect(self.cover_button, SIGNAL("clicked()"), self.select_cover)
        self.comment.hide_toolbars()

    def deduce_author_sort(self, *args):
        au = unicode(self.author.currentText())
        au = re.sub(r'\s+et al\.$', '', au)
        authors = string_to_authors(au)
        self.author_sort.setText(self.db.author_sort_from_authors(authors))


    def initialize_metadata_options(self):
        self.initialize_combos()
        self.author.editTextChanged.connect(self.deduce_author_sort)

        mi = self.db.get_metadata(self.book_id, index_is_id=True)
        self.title.setText(mi.title)
        self.publisher.show_initial_value(mi.publisher if mi.publisher else '')
        self.author_sort.setText(mi.author_sort if mi.author_sort else '')
        self.tags.setText(', '.join(mi.tags if mi.tags else []))
        self.tags.update_items_cache(self.db.all_tags())
        self.comment.html = comments_to_html(mi.comments) if mi.comments else ''
        self.series.show_initial_value(mi.series if mi.series else '')
        if mi.series_index is not None:
            try:
                self.series_index.setValue(mi.series_index)
            except:
                self.series_index.setValue(1.0)

        cover = self.db.cover(self.book_id, index_is_id=True)
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull():
                self.cover.setPixmap(pm)
                self.cover_data = cover
                self.set_cover_tooltip(pm)
        else:
            self.cover.setPixmap(QPixmap(I('default_cover.png')))
            self.cover.setToolTip(_('This book has no cover'))

    def set_cover_tooltip(self, pm):
        tt = _('Cover size: %(width)d x %(height)d pixels') % dict(
                width=pm.width(), height=pm.height())
        self.cover.setToolTip(tt)

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(key=lambda x : sort_key(x[1]))
        self.author.set_separator('&')
        self.author.set_space_before_sep(True)
        self.author.set_add_separator(tweaks['authors_completer_append_separator'])
        self.author.update_items_cache(self.db.all_author_names())

        au = self.db.authors(self.book_id, True)
        if not au:
            au = _('Unknown')
        au = ' & '.join([a.strip().replace('|', ',') for a in au.split(',')])
        self.author.show_initial_value(au)

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(key=lambda x : sort_key(x[1]))
        self.series.set_separator(None)
        self.series.update_items_cache([x[1] for x in all_series])

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(key=lambda x : sort_key(x[1]))
        self.publisher.set_separator(None)
        self.publisher.update_items_cache([x[1] for x in all_publishers])

    def get_title_and_authors(self):
        title = unicode(self.title.text()).strip()
        if not title:
            title = _('Unknown')
        authors = unicode(self.author.text()).strip()
        authors = string_to_authors(authors) if authors else [_('Unknown')]
        return title, authors

    def get_metadata(self):
        title, authors = self.get_title_and_authors()
        mi = MetaInformation(title, authors)
        publisher = unicode(self.publisher.text()).strip()
        if publisher:
            mi.publisher = publisher
        author_sort = unicode(self.author_sort.text()).strip()
        if author_sort:
            mi.author_sort = author_sort
        comments = self.comment.html
        if comments:
            mi.comments = comments
        mi.series_index = float(self.series_index.value())
        series = unicode(self.series.currentText()).strip()
        if series:
            mi.series = series
        tags = [t.strip() for t in unicode(self.tags.text()).strip().split(',')]
        if tags:
            mi.tags = tags

        return mi

    def select_cover(self):
        files = choose_images(self, 'change cover dialog',
                             _('Choose cover for ') + unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self.parent(), _('Cannot read'),
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError as e:
                d = error_dialog(self.parent(), _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self.parent(), _('Error reading file'),
                                      _file + _(" is not a valid picture"))
                    d.exec_()
                else:
                    self.cover_path.setText(_file)
                    self.set_cover_tooltip(pix)
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix
                    self.cover_data = cover

    def get_recommendations(self):
        return {
                'prefer_metadata_cover':
                    bool(self.opt_prefer_metadata_cover.isChecked()),
                }


    def commit(self, save_defaults=False):
        '''
        Settings are stored in two attributes: `opf_file` and `cover_file`.
        Both may be None. Also returns a recommendation dictionary.
        '''
        recs = self.commit_options(save_defaults)
        self.user_mi = mi = self.get_metadata()
        self.cover_file = self.opf_file = None
        if self.db is not None:
            if mi.title == self.db.title(self.book_id, index_is_id=True):
                mi.title_sort = self.db.title_sort(self.book_id, index_is_id=True)
            else:
                # Regenerate title sort taking into account book language
                languages = self.db.languages(self.book_id, index_is_id=True)
                if languages:
                    lang = languages.split(',')[0]
                else:
                    lang = None
                mi.title_sort = title_sort(mi.title, lang=lang)
            self.db.set_metadata(self.book_id, self.user_mi)
            self.mi, self.opf_file = create_opf_file(self.db, self.book_id)
            if self.cover_changed and self.cover_data is not None:
                self.db.set_cover(self.book_id, self.cover_data)
            cover = self.db.cover(self.book_id, index_is_id=True)
            if cover:
                cf = PersistentTemporaryFile('.jpeg')
                cf.write(cover)
                cf.close()
                self.cover_file = cf
        return recs

