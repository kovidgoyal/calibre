#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import pyqtSignal, QModelIndex, QThread, Qt

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.devices.usbms.device import Device
from calibre.gui2.dialogs.progress import ProgressDialog
from polyglot.builtins import iteritems, range, map


class Updater(QThread):  # {{{

    update_progress = pyqtSignal(int)
    update_done     = pyqtSignal()

    def __init__(self, parent, db, device, annotation_map, done_callback):
        QThread.__init__(self, parent)
        self.errors = {}
        self.db = db
        self.keep_going = True
        self.pd = ProgressDialog(_('Merging user annotations into database'), '',
                0, len(annotation_map), parent=parent)

        self.device = device
        self.annotation_map = annotation_map
        self.done_callback = done_callback
        self.pd.canceled_signal.connect(self.canceled)
        self.pd.setModal(True)
        self.pd.show()
        self.update_progress.connect(self.pd.set_value,
                type=Qt.QueuedConnection)
        self.update_done.connect(self.pd.hide, type=Qt.QueuedConnection)

    def canceled(self):
        self.keep_going = False
        self.pd.hide()

    def run(self):
        for i, id_ in enumerate(self.annotation_map):
            if not self.keep_going:
                break
            bm = Device.UserAnnotation(self.annotation_map[id_][0],
                    self.annotation_map[id_][1])
            try:
                self.device.add_annotation_to_library(self.db, id_, bm)
            except:
                import traceback
                self.errors[id_] = traceback.format_exc()
            self.update_progress.emit(i)
        self.update_done.emit()
        self.done_callback(list(self.annotation_map.keys()), self.errors)

# }}}


class FetchAnnotationsAction(InterfaceAction):

    name = 'Fetch Annotations'
    action_spec = (_('Fetch annotations (experimental)'), None, None, ())
    dont_add_to = frozenset(('menubar', 'toolbar', 'context-menu', 'toolbar-child'))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.fetch_annotations)

    def fetch_annotations(self, *args):
        # Generate a path_map from selected ids
        def get_ids_from_selected_rows():
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 2:
                rows = range(self.gui.library_view.model().rowCount(QModelIndex()))
            ids = list(map(self.gui.library_view.model().id, rows))
            return ids

        def get_formats(id):
            formats = db.formats(id, index_is_id=True)
            fmts = []
            if formats:
                for format in formats.split(','):
                    fmts.append(format.lower())
            return fmts

        def get_device_path_from_id(id_):
            paths = []
            for x in ('memory', 'card_a', 'card_b'):
                x = getattr(self.gui, x+'_view').model()
                paths += x.paths_for_db_ids({id_}, as_map=True)[id_]
            return paths[0].path if paths else None

        def generate_annotation_paths(ids, db, device):
            # Generate path templates
            # Individual storage mount points scanned/resolved in driver.get_annotations()
            path_map = {}
            for id in ids:
                path = get_device_path_from_id(id)
                mi = db.get_metadata(id, index_is_id=True)
                a_path = device.create_annotations_path(mi, device_path=path)
                path_map[id] = dict(path=a_path, fmts=get_formats(id))
            return path_map

        device = self.gui.device_manager.device
        if not getattr(device, 'SUPPORTS_ANNOTATIONS', False):
            return error_dialog(self.gui, _('Not supported'),
                    _('Fetching annotations is not supported for this device'),
                    show=True)

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

        if not job.result:
            return

        if self.gui.current_view() is not self.gui.library_view:
            return error_dialog(self.gui, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.gui.library_view.model().db
        device = self.gui.device_manager.device

        self.__annotation_updater = Updater(self.gui, db, device, job.result,
                self.Dispatcher(self.annotations_updated))
        self.__annotation_updater.start()

    def annotations_updated(self, ids, errors):
        self.gui.library_view.model().refresh_ids(ids)
        if errors:
            db = self.gui.library_view.model().db
            entries = []
            for id_, tb in iteritems(errors):
                title = id_
                if isinstance(id_, type(1)):
                    title = db.title(id_, index_is_id=True)
                entries.extend([title, tb, ''])
            error_dialog(self.gui, _('Some errors'),
                    _('Could not fetch annotations for some books. Click '
                        'show details to see which ones.'),
                    det_msg='\n'.join(entries), show=True)
