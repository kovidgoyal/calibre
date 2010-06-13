#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil, os, datetime, sys, time
from functools import partial

from PyQt4.Qt import QInputDialog, pyqtSignal, QModelIndex, QThread, Qt, \
        SIGNAL, QPixmap, QTimer, QDesktopServices, QUrl, QDialog

from calibre import strftime
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import prefs, dynamic
from calibre.gui2 import error_dialog, Dispatcher, gprefs, choose_files, \
    choose_dir, warning_dialog, info_dialog, question_dialog, config
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
from calibre.utils.filenames import ascii_filename
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebook, \
    fetch_scheduled_recipe, generate_catalog
from calibre.constants import preferred_encoding, filesystem_encoding, \
        isosx, isfrozen, islinux
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2.dialogs.confirm_delete import confirm

class AnnotationsAction(object): # {{{

    def fetch_annotations(self, *args):
        # Generate a path_map from selected ids
        def get_ids_from_selected_rows():
            rows = self.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 2:
                rows = xrange(self.library_view.model().rowCount(QModelIndex()))
            ids = map(self.library_view.model().id, rows)
            return ids

        def get_formats(id):
            formats = db.formats(id, index_is_id=True)
            fmts = []
            if formats:
                for format in formats.split(','):
                    fmts.append(format.lower())
            return fmts

        def generate_annotation_paths(ids, db, device):
            # Generate path templates
            # Individual storage mount points scanned/resolved in driver.get_annotations()
            path_map = {}
            for id in ids:
                mi = db.get_metadata(id, index_is_id=True)
                a_path = device.create_upload_path(os.path.abspath('/<storage>'), mi, 'x.bookmark', create_dirs=False)
                path_map[id] = dict(path=a_path, fmts=get_formats(id))
            return path_map

        device = self.device_manager.device

        if self.current_view() is not self.library_view:
            return error_dialog(self, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.library_view.model().db

        # Get the list of ids
        ids = get_ids_from_selected_rows()
        if not ids:
            return error_dialog(self, _('No books selected'),
                    _('No books selected to fetch annotations from'),
                    show=True)

        # Map ids to paths
        path_map = generate_annotation_paths(ids, db, device)

        # Dispatch to devices.kindle.driver.get_annotations()
        self.device_manager.annotations(Dispatcher(self.annotations_fetched),
                path_map)

    def annotations_fetched(self, job):
        from calibre.devices.usbms.device import Device
        from calibre.ebooks.metadata import MetaInformation
        from calibre.gui2.dialogs.progress import ProgressDialog
        from calibre.library.cli import do_add_format

        class Updater(QThread):

            update_progress = pyqtSignal(int)
            update_done     = pyqtSignal()
            FINISHED_READING_PCT_THRESHOLD = 96

            def __init__(self, parent, db, annotation_map, done_callback):
                QThread.__init__(self, parent)
                self.db = db
                self.pd = ProgressDialog(_('Merging user annotations into database'), '',
                        0, len(job.result), parent=parent)

                self.am = annotation_map
                self.done_callback = done_callback
                self.connect(self.pd, SIGNAL('canceled()'), self.canceled)
                self.pd.setModal(True)
                self.pd.show()
                self.update_progress.connect(self.pd.set_value,
                        type=Qt.QueuedConnection)
                self.update_done.connect(self.pd.hide, type=Qt.QueuedConnection)

            def generate_annotation_html(self, bookmark):
                # Returns <div class="user_annotations"> ... </div>
                last_read_location = bookmark.last_read_location
                timestamp = datetime.datetime.utcfromtimestamp(bookmark.timestamp)
                percent_read = bookmark.percent_read

                ka_soup = BeautifulSoup()
                dtc = 0
                divTag = Tag(ka_soup,'div')
                divTag['class'] = 'user_annotations'

                # Add the last-read location
                spanTag = Tag(ka_soup, 'span')
                spanTag['style'] = 'font-weight:bold'
                if bookmark.book_format == 'pdf':
                    spanTag.insert(0,NavigableString(
                        _("%s<br />Last Page Read: %d (%d%%)") % \
                                    (strftime(u'%x', timestamp.timetuple()),
                                    last_read_location,
                                    percent_read)))
                else:
                    spanTag.insert(0,NavigableString(
                        _("%s<br />Last Page Read: Location %d (%d%%)") % \
                                    (strftime(u'%x', timestamp.timetuple()),
                                    last_read_location,
                                    percent_read)))

                divTag.insert(dtc, spanTag)
                dtc += 1
                divTag.insert(dtc, Tag(ka_soup,'br'))
                dtc += 1

                if bookmark.user_notes:
                    user_notes = bookmark.user_notes
                    annotations = []

                    # Add the annotations sorted by location
                    # Italicize highlighted text
                    for location in sorted(user_notes):
                        if user_notes[location]['text']:
                            annotations.append(
                                    _('<b>Location %d &bull; %s</b><br />%s<br />') % \
                                                (user_notes[location]['displayed_location'],
                                                    user_notes[location]['type'],
                                                    user_notes[location]['text'] if \
                                                    user_notes[location]['type'] == 'Note' else \
                                                    '<i>%s</i>' % user_notes[location]['text']))
                        else:
                            if bookmark.book_format == 'pdf':
                                annotations.append(
                                        _('<b>Page %d &bull; %s</b><br />') % \
                                                    (user_notes[location]['displayed_location'],
                                                     user_notes[location]['type']))
                            else:
                                annotations.append(
                                        _('<b>Location %d &bull; %s</b><br />') % \
                                                    (user_notes[location]['displayed_location'],
                                                     user_notes[location]['type']))

                    for annotation in annotations:
                        divTag.insert(dtc, annotation)
                        dtc += 1

                ka_soup.insert(0,divTag)
                return ka_soup

            def mark_book_as_read(self,id):
                read_tag = gprefs.get('catalog_epub_mobi_read_tag')
                self.db.set_tags(id, [read_tag], append=True)

            def canceled(self):
                self.pd.hide()

            def run(self):
                ignore_tags = set(['Catalog','Clippings'])
                for (i, id) in enumerate(self.am):
                    bm = Device.UserAnnotation(self.am[id][0],self.am[id][1])
                    if bm.type == 'kindle_bookmark':
                        mi = self.db.get_metadata(id, index_is_id=True)
                        user_notes_soup = self.generate_annotation_html(bm.value)
                        if mi.comments:
                            a_offset = mi.comments.find('<div class="user_annotations">')
                            ad_offset = mi.comments.find('<hr class="annotations_divider" />')

                            if a_offset >= 0:
                                mi.comments = mi.comments[:a_offset]
                            if ad_offset >= 0:
                                mi.comments = mi.comments[:ad_offset]
                            if set(mi.tags).intersection(ignore_tags):
                                continue
                            if mi.comments:
                                hrTag = Tag(user_notes_soup,'hr')
                                hrTag['class'] = 'annotations_divider'
                                user_notes_soup.insert(0,hrTag)

                            mi.comments += user_notes_soup.prettify()
                        else:
                            mi.comments = unicode(user_notes_soup.prettify())
                        # Update library comments
                        self.db.set_comment(id, mi.comments)

                        # Update 'read' tag except for Catalogs/Clippings
                        if bm.value.percent_read >= self.FINISHED_READING_PCT_THRESHOLD:
                            if not set(mi.tags).intersection(ignore_tags):
                                self.mark_book_as_read(id)

                        # Add bookmark file to id
                        self.db.add_format_with_hooks(id, bm.value.bookmark_extension,
                                                      bm.value.path, index_is_id=True)
                        self.update_progress.emit(i)
                    elif bm.type == 'kindle_clippings':
                        # Find 'My Clippings' author=Kindle in database, or add
                        last_update = 'Last modified %s' % strftime(u'%x %X',bm.value['timestamp'].timetuple())
                        mc_id = list(db.data.parse('title:"My Clippings"'))
                        if mc_id:
                            do_add_format(self.db, mc_id[0], 'TXT', bm.value['path'])
                            mi = self.db.get_metadata(mc_id[0], index_is_id=True)
                            mi.comments = last_update
                            self.db.set_metadata(mc_id[0], mi)
                        else:
                            mi = MetaInformation('My Clippings', authors = ['Kindle'])
                            mi.tags = ['Clippings']
                            mi.comments = last_update
                            self.db.add_books([bm.value['path']], ['txt'], [mi])

                self.update_done.emit()
                self.done_callback(self.am.keys())

        if not job.result: return

        if self.current_view() is not self.library_view:
            return error_dialog(self, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.library_view.model().db

        self.__annotation_updater = Updater(self, db, job.result,
                Dispatcher(self.library_view.model().refresh_ids))
        self.__annotation_updater.start()

    # }}}

class AddAction(object): # {{{

    def __init__(self):
        self._add_filesystem_book = Dispatcher(self.__add_filesystem_book)

    def add_recursive(self, single):
        root = choose_dir(self, 'recursive book import root dir dialog',
                          'Select root folder')
        if not root:
            return
        from calibre.gui2.add import Adder
        self._adder = Adder(self,
                self.library_view.model().db,
                Dispatcher(self._files_added), spare_server=self.spare_server)
        self._adder.add_recursive(root, single)

    def add_recursive_single(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming one book per folder.
        '''
        self.add_recursive(True)

    def add_recursive_multiple(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming multiple books per folder.
        '''
        self.add_recursive(False)

    def add_empty(self, *args):
        '''
        Add an empty book item to the library. This does not import any formats
        from a book file.
        '''
        num, ok = QInputDialog.getInt(self, _('How many empty books?'),
                _('How many empty books should be added?'), 1, 1, 100)
        if ok:
            from calibre.ebooks.metadata import MetaInformation
            for x in xrange(num):
                self.library_view.model().db.import_book(MetaInformation(None), [])
            self.library_view.model().books_added(num)

    def files_dropped(self, paths):
        to_device = self.stack.currentIndex() != 0
        self._add_books(paths, to_device)

    def files_dropped_on_book(self, event, paths):
        accept = False
        if self.current_view() is not self.library_view:
            return
        db = self.library_view.model().db
        current_idx = self.library_view.currentIndex()
        if not current_idx.isValid(): return
        cid = db.id(current_idx.row())
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext:
                ext = ext[1:]
            if ext in IMAGE_EXTENSIONS:
                pmap = QPixmap()
                pmap.load(path)
                if not pmap.isNull():
                    accept = True
                    db.set_cover(cid, pmap)
            elif ext in BOOK_EXTENSIONS:
                db.add_format_with_hooks(cid, ext, path, index_is_id=True)
                accept = True
        if accept:
            event.accept()
            self.cover_cache.refresh([cid])
            self.library_view.model().current_changed(current_idx, current_idx)

    def __add_filesystem_book(self, paths, allow_device=True):
        if isinstance(paths, basestring):
            paths = [paths]
        books = [path for path in map(os.path.abspath, paths) if os.access(path,
            os.R_OK)]

        if books:
            to_device = allow_device and self.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.status_bar.show_message(\
                        _('Uploading books to device.'), 2000)


    def add_filesystem_book(self, paths, allow_device=True):
        self._add_filesystem_book(paths, allow_device=allow_device)

    def add_books(self, *args):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        filters = [
                        (_('Books'), BOOK_EXTENSIONS),
                        (_('EPUB Books'), ['epub']),
                        (_('LRF Books'), ['lrf']),
                        (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
                        (_('LIT Books'), ['lit']),
                        (_('MOBI Books'), ['mobi', 'prc', 'azw']),
                        (_('Topaz books'), ['tpz','azw1']),
                        (_('Text books'), ['txt', 'rtf']),
                        (_('PDF Books'), ['pdf']),
                        (_('Comics'), ['cbz', 'cbr', 'cbc']),
                        (_('Archives'), ['zip', 'rar']),
                        ]
        to_device = self.stack.currentIndex() != 0
        if to_device:
            filters = [(_('Supported books'), self.device_manager.device.FORMATS)]

        books = choose_files(self, 'add books dialog dir', 'Select books',
                             filters=filters)
        if not books:
            return
        self._add_books(books, to_device)

    def _add_books(self, paths, to_device, on_card=None):
        if on_card is None:
            on_card = 'carda' if self.stack.currentIndex() == 2 else 'cardb' if self.stack.currentIndex() == 3 else None
        if not paths:
            return
        from calibre.gui2.add import Adder
        self.__adder_func = partial(self._files_added, on_card=on_card)
        self._adder = Adder(self,
                None if to_device else self.library_view.model().db,
                Dispatcher(self.__adder_func), spare_server=self.spare_server)
        self._adder.add(paths)

    def _files_added(self, paths=[], names=[], infos=[], on_card=None):
        if paths:
            self.upload_books(paths,
                                list(map(ascii_filename, names)),
                                infos, on_card=on_card)
            self.status_bar.show_message(
                    _('Uploading books to device.'), 2000)
        if getattr(self._adder, 'number_of_books_added', 0) > 0:
            self.library_view.model().books_added(self._adder.number_of_books_added)
            if hasattr(self, 'db_images'):
                self.db_images.reset()
        if getattr(self._adder, 'merged_books', False):
            books = u'\n'.join([x if isinstance(x, unicode) else
                    x.decode(preferred_encoding, 'replace') for x in
                    self._adder.merged_books])
            info_dialog(self, _('Merged some books'),
                    _('Some duplicates were found and merged into the '
                        'following existing books:'), det_msg=books, show=True)
        if getattr(self._adder, 'critical', None):
            det_msg = []
            for name, log in self._adder.critical.items():
                if isinstance(name, str):
                    name = name.decode(filesystem_encoding, 'replace')
                det_msg.append(name+'\n'+log)

            warning_dialog(self, _('Failed to read metadata'),
                    _('Failed to read metadata from the following')+':',
                    det_msg='\n\n'.join(det_msg), show=True)

        if hasattr(self._adder, 'cleanup'):
            self._adder.cleanup()
        self._adder = None
    # }}}

class DeleteAction(object): # {{{

    def _get_selected_formats(self, msg):
        from calibre.gui2.dialogs.select_formats import SelectFormats
        fmts = self.library_view.model().db.all_formats()
        d = SelectFormats([x.lower() for x in fmts], msg, parent=self)
        if d.exec_() != d.Accepted:
            return None
        return d.selected_formats

    def _get_selected_ids(self, err_title=_('Cannot delete')):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, err_title, _('No book selected'))
            d.exec_()
            return set([])
        return set(map(self.library_view.model().id, rows))

    def delete_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            _('Choose formats to be deleted'))
        if not fmts:
            return
        for id in ids:
            for fmt in fmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())
        if ids:
            self.tags_view.recount()

    def delete_all_but_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            '<p>'+_('Choose formats <b>not</b> to be deleted'))
        if fmts is None:
            return
        for id in ids:
            bfmts = self.library_view.model().db.formats(id, index_is_id=True)
            if bfmts is None:
                continue
            bfmts = set([x.lower() for x in bfmts.split(',')])
            rfmts = bfmts - set(fmts)
            for fmt in rfmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())
        if ids:
            self.tags_view.recount()


    def delete_covers(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        for id in ids:
            self.library_view.model().db.remove_cover(id)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())

    def delete_books(self, *args):
        '''
        Delete selected books from device or library.
        '''
        view = self.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        if self.stack.currentIndex() == 0:
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> and the files '
                                   'removed from your computer. Are you sure?')
                                +'</p>', 'library_delete_books', self):
                return
            ci = view.currentIndex()
            row = None
            if ci.isValid():
                row = ci.row()
            ids_deleted = view.model().delete_books(rows)
            for v in (self.memory_view, self.card_a_view, self.card_b_view):
                if v is None:
                    continue
                v.model().clear_ondevice(ids_deleted)
            if row is not None:
                ci = view.model().index(row, 0)
                if ci.isValid():
                    view.setCurrentIndex(ci)
                    sm = view.selectionModel()
                    sm.select(ci, sm.Select)
        else:
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> '
                                   'from your device. Are you sure?')
                                +'</p>', 'device_delete_books', self):
                return
            if self.stack.currentIndex() == 1:
                view = self.memory_view
            elif self.stack.currentIndex() == 2:
                view = self.card_a_view
            else:
                view = self.card_b_view
            paths = view.model().paths(rows)
            job = self.remove_paths(paths)
            self.delete_memory[job] = (paths, view.model())
            view.model().mark_for_deletion(job, rows)
            self.status_bar.show_message(_('Deleting books from device.'), 1000)

    # }}}

class EditMetadataAction(object): # {{{

    def download_metadata(self, checked, covers=True, set_metadata=True,
            set_social_metadata=None):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot download metadata'),
                             _('No books selected'))
            d.exec_()
            return
        db = self.library_view.model().db
        ids = [db.id(row.row()) for row in rows]
        if set_social_metadata is None:
            get_social_metadata = config['get_social_metadata']
        else:
            get_social_metadata = set_social_metadata
        from calibre.gui2.metadata import DownloadMetadata
        self._download_book_metadata = DownloadMetadata(db, ids,
                get_covers=covers, set_metadata=set_metadata,
                get_social_metadata=get_social_metadata)
        self._download_book_metadata.start()
        if set_social_metadata is not None and set_social_metadata:
            x = _('social metadata')
        else:
            x = _('covers') if covers and not set_metadata else _('metadata')
        self.progress_indicator.start(
            _('Downloading %s for %d book(s)')%(x, len(ids)))
        self._book_metadata_download_check = QTimer(self)
        self.connect(self._book_metadata_download_check,
                SIGNAL('timeout()'), self.book_metadata_download_check,
                Qt.QueuedConnection)
        self._book_metadata_download_check.start(100)

    def book_metadata_download_check(self):
        if self._download_book_metadata.is_alive():
            return
        self._book_metadata_download_check.stop()
        self.progress_indicator.stop()
        cr = self.library_view.currentIndex().row()
        x = self._download_book_metadata
        self._download_book_metadata = None
        if x.exception is None:
            self.library_view.model().refresh_ids(
                x.updated, cr)
            if x.failures:
                details = ['%s: %s'%(title, reason) for title,
                        reason in x.failures.values()]
                details = '%s\n'%('\n'.join(details))
                warning_dialog(self, _('Failed to download some metadata'),
                    _('Failed to download metadata for the following:'),
                    det_msg=details).exec_()
        else:
            err = _('Failed to download metadata:')
            error_dialog(self, _('Error'), err, det_msg=x.tb).exec_()


    def edit_metadata(self, checked, bulk=None):
        '''
        Edit metadata of selected books in library.
        '''
        rows = self.library_view.selectionModel().selectedRows()
        previous = self.library_view.currentIndex()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'),
                             _('No books selected'))
            d.exec_()
            return

        if bulk or (bulk is None and len(rows) > 1):
            return self.edit_bulk_metadata(checked)

        def accepted(id):
            self.library_view.model().refresh_ids([id])

        for row in rows:
            self._metadata_view_id = self.library_view.model().db.id(row.row())
            d = MetadataSingleDialog(self, row.row(),
                                    self.library_view.model().db,
                                    accepted_callback=accepted,
                                    cancel_all=rows.index(row) < len(rows)-1)
            self.connect(d, SIGNAL('view_format(PyQt_PyObject)'),
                    self.metadata_view_format)
            d.exec_()
            if d.cancel_all:
                break
        if rows:
            current = self.library_view.currentIndex()
            m = self.library_view.model()
            m.refresh_cover_cache(map(m.id, rows))
            if self.cover_flow:
                self.cover_flow.dataChanged()
            m.current_changed(current, previous)
            self.tags_view.recount()

    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in \
                self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'),
                    _('No books selected'))
            d.exec_()
            return
        if MetadataBulkDialog(self, rows,
                self.library_view.model().db).changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
            self.tags_view.recount()

    # Merge books {{{
    def merge_books(self, safe_merge=False):
        '''
        Merge selected books in library.
        '''
        if self.stack.currentIndex() != 0:
            return
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self, _('Cannot merge books'),
                                _('No books selected'), show=True)
        if len(rows) < 2:
            return error_dialog(self, _('Cannot merge books'),
                        _('At least two books must be selected for merging'),
                        show=True)
        dest_id, src_books, src_ids = self.books_to_merge(rows)
        if safe_merge:
            if not confirm('<p>'+_(
                'All book formats and metadata from the selected books '
                'will be added to the <b>first selected book.</b><br><br> '
                'The second and subsequently selected books will not '
                'be deleted or changed.<br><br>'
                'Please confirm you want to proceed.')
            +'</p>', 'merge_books_safe', self):
                return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
        else:
            if not confirm('<p>'+_(
                'All book formats and metadata from the selected books will be merged '
                'into the <b>first selected book</b>.<br><br>'
                'After merger the second and '
                'subsequently selected books will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your computer.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')
            +'</p>', 'merge_books', self):
                return
            if len(rows)>5:
                if not confirm('<p>'+_('You are about to merge more than 5 books.  '
                                        'Are you <b>sure</b> you want to proceed?')
                                    +'</p>', 'merge_too_many_books', self):
                    return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
            self.delete_books_after_merge(src_ids)
            # leave the selection highlight on first selected book
            dest_row = rows[0].row()
            for row in rows:
                if row.row() < rows[0].row():
                    dest_row -= 1
            ci = self.library_view.model().index(dest_row, 0)
            if ci.isValid():
                self.library_view.setCurrentIndex(ci)

    def add_formats(self, dest_id, src_books, replace=False):
        for src_book in src_books:
            if src_book:
                fmt = os.path.splitext(src_book)[-1].replace('.', '').upper()
                with open(src_book, 'rb') as f:
                    self.library_view.model().db.add_format(dest_id, fmt, f, index_is_id=True,
                            notify=False, replace=replace)

    def books_to_merge(self, rows):
        src_books = []
        src_ids = []
        m = self.library_view.model()
        for i, row in enumerate(rows):
            id_ = m.id(row)
            if i == 0:
                dest_id = id_
            else:
                src_ids.append(id_)
                dbfmts = m.db.formats(id_, index_is_id=True)
                if dbfmts:
                    for fmt in dbfmts.split(','):
                        src_books.append(m.db.format_abspath(id_, fmt,
                            index_is_id=True))
        return [dest_id, src_books, src_ids]

    def delete_books_after_merge(self, ids_to_delete):
        self.library_view.model().delete_books_by_id(ids_to_delete)

    def merge_metadata(self, dest_id, src_ids):
        db = self.library_view.model().db
        dest_mi = db.get_metadata(dest_id, index_is_id=True, get_cover=True)
        orig_dest_comments = dest_mi.comments
        for src_id in src_ids:
            src_mi = db.get_metadata(src_id, index_is_id=True, get_cover=True)
            if src_mi.comments and orig_dest_comments != src_mi.comments:
                if not dest_mi.comments or len(dest_mi.comments) == 0:
                    dest_mi.comments = src_mi.comments
                else:
                    dest_mi.comments = unicode(dest_mi.comments) + u'\n\n' + unicode(src_mi.comments)
            if src_mi.title and src_mi.title and (not dest_mi.title or
                    dest_mi.title == _('Unknown')):
                dest_mi.title = src_mi.title
            if src_mi.title and (not dest_mi.authors or dest_mi.authors[0] ==
                    _('Unknown')):
                dest_mi.authors = src_mi.authors
                dest_mi.author_sort = src_mi.author_sort
            if src_mi.tags:
                if not dest_mi.tags:
                    dest_mi.tags = src_mi.tags
                else:
                    for tag in src_mi.tags:
                        dest_mi.tags.append(tag)
            if src_mi.cover and not dest_mi.cover:
                dest_mi.cover = src_mi.cover
            if not dest_mi.publisher:
                dest_mi.publisher = src_mi.publisher
            if not dest_mi.rating:
                dest_mi.rating = src_mi.rating
            if not dest_mi.series:
                dest_mi.series = src_mi.series
                dest_mi.series_index = src_mi.series_index
        db.set_metadata(dest_id, dest_mi, ignore_errors=False)
        # }}}

    # }}}

class SaveToDiskAction(object): # {{{

    def save_single_format_to_disk(self, checked):
        self.save_to_disk(checked, False, prefs['output_format'])

    def save_specific_format_disk(self, fmt):
        self.save_to_disk(False, False, fmt)

    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_single_fmt_to_single_dir(self, *args):
        self.save_to_disk(False, single_dir=True,
                single_format=prefs['output_format'])

    def save_to_disk(self, checked, single_dir=False, single_format=None):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self, _('Cannot save to disk'),
                    _('No books selected'), show=True)
        path = choose_dir(self, 'save to disk dialog',
                _('Choose destination directory'))
        if not path:
            return

        if self.current_view() is self.library_view:
            from calibre.gui2.add import Saver
            from calibre.library.save_to_disk import config
            opts = config().parse()
            if single_format is not None:
                opts.formats = single_format
                # Special case for Kindle annotation files
                if single_format.lower() in ['mbp','pdr','tan']:
                    opts.to_lowercase = False
                    opts.save_cover = False
                    opts.write_opf = False
                    opts.template = opts.send_template
            if single_dir:
                opts.template = opts.template.split('/')[-1].strip()
                if not opts.template:
                    opts.template = '{title} - {authors}'
            self._saver = Saver(self, self.library_view.model().db,
                    Dispatcher(self._books_saved), rows, path, opts,
                    spare_server=self.spare_server)

        else:
            paths = self.current_view().model().paths(rows)
            self.device_manager.save_books(
                    Dispatcher(self.books_saved), paths, path)


    def _books_saved(self, path, failures, error):
        self._saver = None
        if error:
            return error_dialog(self, _('Error while saving'),
                    _('There was an error while saving.'),
                    error, show=True)
        if failures:
            failures = [u'%s\n\t%s'%
                    (title, '\n\t'.join(err.splitlines())) for title, err in
                    failures]

            warning_dialog(self, _('Could not save some books'),
            _('Could not save some books') + ', ' +
            _('Click the show details button to see which ones.'),
            u'\n\n'.join(failures), show=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def books_saved(self, job):
        if job.failed:
            return self.device_job_exception(job)

    # }}}

class GenerateCatalogAction(object): # {{{

    def generate_catalog(self):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) < 2:
            rows = xrange(self.library_view.model().rowCount(QModelIndex()))
        ids = map(self.library_view.model().id, rows)

        dbspec = None
        if not ids:
            return error_dialog(self, _('No books selected'),
                    _('No books selected to generate catalog for'),
                    show=True)

        # Calling gui2.tools:generate_catalog()
        ret = generate_catalog(self, dbspec, ids, self.device_manager.device)
        if ret is None:
            return

        func, args, desc, out, sync, title = ret

        fmt = os.path.splitext(out)[1][1:].upper()
        job = self.job_manager.run_job(
                Dispatcher(self.catalog_generated), func, args=args,
                    description=desc)
        job.catalog_file_path = out
        job.fmt = fmt
        job.catalog_sync, job.catalog_title = sync, title
        self.status_bar.show_message(_('Generating %s catalog...')%fmt)

    def catalog_generated(self, job):
        if job.result:
            # Search terms nulled catalog results
            return error_dialog(self, _('No books found'),
                    _("No books to catalog\nCheck exclude tags"),
                    show=True)
        if job.failed:
            return self.job_exception(job)
        id = self.library_view.model().add_catalog(job.catalog_file_path, job.catalog_title)
        self.library_view.model().reset()
        if job.catalog_sync:
            sync = dynamic.get('catalogs_to_be_synced', set([]))
            sync.add(id)
            dynamic.set('catalogs_to_be_synced', sync)
        self.status_bar.show_message(_('Catalog generated.'), 3000)
        self.sync_catalogs()
        if job.fmt not in ['EPUB','MOBI']:
            export_dir = choose_dir(self, _('Export Catalog Directory'),
                    _('Select destination for %s.%s') % (job.catalog_title, job.fmt.lower()))
            if export_dir:
                destination = os.path.join(export_dir, '%s.%s' % (job.catalog_title, job.fmt.lower()))
                shutil.copyfile(job.catalog_file_path, destination)

    # }}}

class FetchNewsAction(object): # {{{

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                           description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.failed:
            self.scheduler.recipe_download_failed(arg)
            return self.job_exception(job)
        id = self.library_view.model().add_news(pt.name, arg)
        self.library_view.model().reset()
        sync = dynamic.get('news_to_be_synced', set([]))
        sync.add(id)
        dynamic.set('news_to_be_synced', sync)
        self.scheduler.recipe_downloaded(arg)
        self.status_bar.show_message(arg['title'] + _(' fetched.'), 3000)
        self.email_news(id)
        self.sync_news()

    # }}}

class ConvertAction(object): # {{{

    def auto_convert(self, book_ids, on_card, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted, extra_job_args=[on_card])

    def auto_convert_mail(self, to, fmts, delete_from_library, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_mail,
                extra_job_args=[delete_from_library, to, fmts])

    def auto_convert_news(self, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_news)

    def auto_convert_catalogs(self, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_catalogs)

    def get_books_for_conversion(self):
        rows = [r.row() for r in \
                self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot convert'),
                    _('No books selected'))
            d.exec_()
            return None
        return [self.library_view.model().db.id(r) for r in rows]

    def convert_ebook(self, checked, bulk=None):
        book_ids = self.get_books_for_conversion()
        if book_ids is None: return
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        num = 0
        if bulk or (bulk is None and len(book_ids) > 1):
            self.__bulk_queue = convert_bulk_ebook(self, self.queue_convert_jobs,
                self.library_view.model().db, book_ids,
                out_format=prefs['output_format'], args=(rows, previous,
                    self.book_converted))
            if self.__bulk_queue is None:
                return
            num = len(self.__bulk_queue.book_ids)
        else:
            jobs, changed, bad = convert_single_ebook(self,
                self.library_view.model().db, book_ids, out_format=prefs['output_format'])
            self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                    self.book_converted)
            num = len(jobs)

        if num > 0:
            self.status_bar.show_message(_('Starting conversion of %d book(s)') %
                num, 2000)

    def queue_convert_jobs(self, jobs, changed, bad, rows, previous,
            converted_func, extra_job_args=[]):
        for func, args, desc, fmt, id, temp_files in jobs:
            if id not in bad:
                job = self.job_manager.run_job(Dispatcher(converted_func),
                                            func, args=args, description=desc)
                args = [temp_files, fmt, id]+extra_job_args
                self.conversion_jobs[job] = tuple(args)

        if changed:
            self.library_view.model().refresh_rows(rows)
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, previous)

    def book_auto_converted(self, job):
        temp_files, fmt, book_id, on_card = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_to_device(on_card, False, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_mail(self, job):
        temp_files, fmt, book_id, delete_from_library, to, fmts = self.conversion_jobs[job]
        self.book_converted(job)
        self.send_by_mail(to, fmts, delete_from_library, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_news(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_news(send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_catalogs(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_catalogs(send_ids=[book_id], do_auto_convert=False)

    def book_converted(self, job):
        temp_files, fmt, book_id = self.conversion_jobs.pop(job)[:3]
        try:
            if job.failed:
                self.job_exception(job)
                return
            data = open(temp_files[-1].name, 'rb')
            self.library_view.model().db.add_format(book_id, \
                    fmt, data, index_is_id=True)
            data.close()
            self.status_bar.show_message(job.description + \
                    (' completed'), 2000)
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f.name):
                        os.remove(f.name)
                except:
                    pass
        self.tags_view.recount()
        if self.current_view() is self.library_view:
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, QModelIndex())

    # }}}

class ViewAction(object): # {{{

    def view_format(self, row, format):
        fmt_path = self.library_view.model().db.format_abspath(row, format)
        if fmt_path:
            self._view_file(fmt_path)

    def view_format_by_id(self, id_, format):
        fmt_path = self.library_view.model().db.format_abspath(id_, format,
                index_is_id=True)
        if fmt_path:
            self._view_file(fmt_path)

    def metadata_view_format(self, fmt):
        fmt_path = self.library_view.model().db.\
                format_abspath(self._metadata_view_id,
                        fmt, index_is_id=True)
        if fmt_path:
            self._view_file(fmt_path)


    def book_downloaded_for_viewing(self, job):
        if job.failed:
            self.device_job_exception(job)
            return
        self._view_file(job.result)

    def _launch_viewer(self, name=None, viewer='ebook-viewer', internal=True):
        self.setCursor(Qt.BusyCursor)
        try:
            if internal:
                args = [viewer]
                if isosx and 'ebook' in viewer:
                    args.append('--raise-window')
                if name is not None:
                    args.append(name)
                self.job_manager.launch_gui_app(viewer,
                        kwargs=dict(args=args))
            else:
                paths = os.environ.get('LD_LIBRARY_PATH',
                            '').split(os.pathsep)
                paths = [x for x in paths if x]
                if isfrozen and islinux and paths:
                    npaths = [x for x in paths if x != sys.frozen_path]
                    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(npaths)
                QDesktopServices.openUrl(QUrl.fromLocalFile(name))#launch(name)
                if isfrozen and islinux and paths:
                    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(paths)
                time.sleep(2) # User feedback
        finally:
            self.unsetCursor()

    def _view_file(self, name):
        ext = os.path.splitext(name)[1].upper().replace('.', '')
        viewer = 'lrfviewer' if ext == 'LRF' else 'ebook-viewer'
        internal = ext in config['internally_viewed_formats']
        self._launch_viewer(name, viewer, internal)

    def view_specific_format(self, triggered):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot view'), _('No book selected'))
            d.exec_()
            return

        row = rows[0].row()
        formats = self.library_view.model().db.formats(row).upper().split(',')
        d = ChooseFormatDialog(self, _('Choose the format to view'), formats)
        if d.exec_() == QDialog.Accepted:
            format = d.format()
            self.view_format(row, format)

    def _view_check(self, num, max_=3):
        if num <= max_:
            return True
        return question_dialog(self, _('Multiple Books Selected'),
                _('You are attempting to open %d books. Opening too many '
                'books at once can be slow and have a negative effect on the '
                'responsiveness of your computer. Once started the process '
                'cannot be stopped until complete. Do you wish to continue?'
                ) % num)

    def view_folder(self, *args):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot open folder'),
                    _('No book selected'))
            d.exec_()
            return
        if not self._view_check(len(rows)):
            return
        for row in rows:
            path = self.library_view.model().db.abspath(row.row())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def view_folder_for_id(self, id_):
        path = self.library_view.model().db.abspath(id_, index_is_id=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def view_book(self, triggered):
        rows = self.current_view().selectionModel().selectedRows()
        self._view_books(rows)

    def view_specific_book(self, index):
        self._view_books([index])

    def _view_books(self, rows):
        if not rows or len(rows) == 0:
            self._launch_viewer()
            return

        if not self._view_check(len(rows)):
            return

        if self.current_view() is self.library_view:
            for row in rows:
                if hasattr(row, 'row'):
                    row = row.row()

                formats = self.library_view.model().db.formats(row)
                title   = self.library_view.model().db.title(row)
                if not formats:
                    error_dialog(self, _('Cannot view'),
                        _('%s has no available formats.')%(title,), show=True)
                    continue

                formats = formats.upper().split(',')


                in_prefs = False
                for format in prefs['input_format_order']:
                    if format in formats:
                        in_prefs = True
                        self.view_format(row, format)
                        break
                if not in_prefs:
                    self.view_format(row, formats[0])
        else:
            paths = self.current_view().model().paths(rows)
            for path in paths:
                pt = PersistentTemporaryFile('_viewer_'+\
                        os.path.splitext(path)[1])
                self.persistent_files.append(pt)
                pt.close()
                self.device_manager.view_book(\
                        Dispatcher(self.book_downloaded_for_viewing),
                                              path, pt.name)

    # }}}

