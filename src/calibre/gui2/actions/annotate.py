#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, datetime

from PyQt4.Qt import pyqtSignal, QModelIndex, QThread, Qt

from calibre.gui2 import error_dialog, gprefs
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
from calibre import strftime
from calibre.gui2.actions import InterfaceAction

class FetchAnnotationsAction(InterfaceAction):

    name = 'Fetch Annotations'
    action_spec = (_('Fetch annotations (experimental)'), None, None, None)
    action_type = 'current'

    def genesis(self):
        pass

    def fetch_annotations(self, *args):
        # Generate a path_map from selected ids
        def get_ids_from_selected_rows():
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 2:
                rows = xrange(self.gui.library_view.model().rowCount(QModelIndex()))
            ids = map(self.gui.library_view.model().id, rows)
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

        device = self.gui.device_manager.device

        if self.gui.current_view() is not self.gui.library_view:
            return error_dialog(self.gui, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.gui.library_view.model().db

        # Get the list of ids
        ids = get_ids_from_selected_rows()
        if not ids:
            return error_dialog(self.gui, _('No books selected'),
                    _('No books selected to fetch annotations from'),
                    show=True)

        # Map ids to paths
        path_map = generate_annotation_paths(ids, db, device)

        # Dispatch to devices.kindle.driver.get_annotations()
        self.gui.device_manager.annotations(self.Dispatcher(self.annotations_fetched),
                path_map)

    def annotations_fetched(self, job):
        from calibre.devices.usbms.device import Device
        from calibre.ebooks.metadata import MetaInformation
        from calibre.gui2.dialogs.progress import ProgressDialog
        from calibre.library.cli import do_add_format

        class Updater(QThread): # {{{

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
                self.pd.canceled_signal.connect(self.canceled)
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
                if read_tag:
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

        # }}}

        if not job.result: return

        if self.gui.current_view() is not self.gui.library_view:
            return error_dialog(self.gui, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.gui.library_view.model().db

        self.__annotation_updater = Updater(self.gui, db, job.result,
                self.Dispatcher(self.gui.library_view.model().refresh_ids))
        self.__annotation_updater.start()


