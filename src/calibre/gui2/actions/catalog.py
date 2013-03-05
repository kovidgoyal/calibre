#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, shutil

from PyQt4.Qt import QModelIndex

from calibre.gui2 import choose_dir, error_dialog, warning_dialog
from calibre.gui2.tools import generate_catalog
from calibre.utils.config import dynamic
from calibre.gui2.actions import InterfaceAction
from calibre import sanitize_file_name_unicode

class GenerateCatalogAction(InterfaceAction):

    name = 'Generate Catalog'
    action_spec = (_('Create catalog'), 'catalog.png',
                   _('Create a catalog of the books in your calibre library in different formats'), ())
    dont_add_to = frozenset(['context-menu-device'])

    def genesis(self):
        self.qaction.triggered.connect(self.generate_catalog)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def generate_catalog(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) < 2:
            rows = xrange(self.gui.library_view.model().rowCount(QModelIndex()))
        ids = map(self.gui.library_view.model().id, rows)

        if not ids:
            return error_dialog(self.gui, _('No books selected'),
                    _('No books selected for catalog generation'),
                    show=True)

        db = self.gui.library_view.model().db
        dbspec = {}
        for id in ids:
            dbspec[id] = {'ondevice': db.ondevice(id, index_is_id=True)}

        # Calling gui2.tools:generate_catalog()
        ret = generate_catalog(self.gui, dbspec, ids, self.gui.device_manager,
                db)
        if ret is None:
            return

        func, args, desc, out, sync, title = ret

        fmt = os.path.splitext(out)[1][1:].upper()
        job = self.gui.job_manager.run_job(
                self.Dispatcher(self.catalog_generated), func, args=args,
                    description=desc)
        job.catalog_file_path = out
        job.fmt = fmt
        job.catalog_sync, job.catalog_title = sync, title
        self.gui.status_bar.show_message(_('Generating %s catalog...')%fmt)

    def catalog_generated(self, job):
        if job.result:
            # Problems during catalog generation
            # jobs.results is a list - the first entry is the intended title for the dialog
            # Subsequent strings are error messages
            dialog_title = job.result.pop(0)
            if re.search('warning', job.result[0].lower()):
                msg = _("Catalog generation complete, with warnings.")
                warning_dialog(self.gui, dialog_title, msg, det_msg='\n'.join(job.result), show=True)
            else:
                job.result.append("Catalog generation terminated.")
                error_dialog(self.gui, dialog_title,'\n'.join(job.result),show=True)
                return

        if job.failed:
            return self.gui.job_exception(job)
        id = self.gui.library_view.model().add_catalog(job.catalog_file_path, job.catalog_title)
        self.gui.library_view.model().reset()
        if job.catalog_sync:
            sync = dynamic.get('catalogs_to_be_synced', set([]))
            sync.add(id)
            dynamic.set('catalogs_to_be_synced', sync)
        self.gui.status_bar.show_message(_('Catalog generated.'), 3000)
        self.gui.sync_catalogs()
        if job.fmt not in {'EPUB','MOBI', 'AZW3'}:
            export_dir = choose_dir(self.gui, _('Export Catalog Directory'),
                    _('Select destination for %(title)s.%(fmt)s') % dict(
                        title=job.catalog_title, fmt=job.fmt.lower()))
            if export_dir:
                destination = os.path.join(export_dir, '%s.%s' % (
                    sanitize_file_name_unicode(job.catalog_title), job.fmt.lower()))
                shutil.copyfile(job.catalog_file_path, destination)


