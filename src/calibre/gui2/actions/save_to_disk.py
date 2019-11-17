#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, numbers
from functools import partial

from calibre.utils.config import prefs
from calibre.gui2 import error_dialog, Dispatcher, choose_dir
from calibre.gui2.actions import InterfaceAction
from polyglot.builtins import itervalues, map


class SaveToDiskAction(InterfaceAction):

    name = "Save To Disk"
    action_spec = (_('Save to disk'), 'save.png',
                   _('Export e-book files from the calibre library'), _('S'))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = True

    def genesis(self):
        self.qaction.triggered.connect(self.save_to_disk)
        self.save_menu = self.qaction.menu()
        cm = partial(self.create_menu_action, self.save_menu)
        cm('single dir', _('Save to disk in a single directory'),
                triggered=partial(self.save_to_single_dir, False))
        cm('single format', _('Save only %s format to disk')%
                prefs['output_format'].upper(),
                triggered=partial(self.save_single_format_to_disk, False))
        cm('single dir and format',
                _('Save only %s format to disk in a single directory')%
                prefs['output_format'].upper(),
                triggered=partial(self.save_single_fmt_to_single_dir, False))
        cm('specific format', _('Save single format to disk...'),
                triggered=self.save_specific_format_disk)

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.save_menu.actions())[1:]:
            action.setEnabled(enabled)

    def reread_prefs(self):
        self.save_menu.actions()[2].setText(
            _('Save only %s format to disk')%
            prefs['output_format'].upper())
        self.save_menu.actions()[3].setText(
            _('Save only %s format to disk in a single directory')%
            prefs['output_format'].upper())

    def save_single_format_to_disk(self, checked):
        self.save_to_disk(checked, False, prefs['output_format'])

    def save_specific_format_disk(self):
        rb = self.gui.iactions['Remove Books']
        ids = rb._get_selected_ids(err_title=_('Cannot save to disk'))
        if not ids:
            return
        fmts = rb._get_selected_formats(
                _('Choose format to save to disk'), ids,
                single=True)
        if not fmts:
            return
        self.save_to_disk(False, False, list(fmts)[0])

    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_single_fmt_to_single_dir(self, *args):
        self.save_to_disk(False, single_dir=True,
                single_format=prefs['output_format'])

    def save_to_disk(self, checked, single_dir=False, single_format=None,
            rows=None, write_opf=None, save_cover=None):
        if rows is None:
            rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot save to disk'),
                    _('No books selected'), show=True)
        path = choose_dir(self.gui, 'save to disk dialog',
                _('Choose destination directory'))
        if not path:
            return
        dpath = os.path.abspath(path).replace('/', os.sep)+os.sep
        lpath = self.gui.library_view.model().db.library_path.replace('/',
                os.sep)+os.sep
        if dpath.startswith(lpath):
            return error_dialog(self.gui, _('Not allowed'),
                    _('You are trying to save files into the calibre '
                      'library. This can cause corruption of your '
                      'library. Save to disk is meant to export '
                      'files from your calibre library elsewhere.'), show=True)

        if self.gui.current_view() is self.gui.library_view:
            from calibre.gui2.save import Saver
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
            opts.single_dir = single_dir
            if write_opf is not None:
                opts.write_opf = write_opf
            if save_cover is not None:
                opts.save_cover = save_cover
            book_ids = set(map(self.gui.library_view.model().id, rows))
            Saver(book_ids, self.gui.current_db, opts, path, parent=self.gui, pool=self.gui.spare_pool())
        else:
            paths = self.gui.current_view().model().paths(rows)
            self.gui.device_manager.save_books(
                    Dispatcher(self.books_saved), paths, path)

    def save_library_format_by_ids(self, book_ids, fmt, single_dir=True):
        if isinstance(book_ids, numbers.Integral):
            book_ids = [book_ids]
        rows = list(itervalues(self.gui.library_view.ids_to_rows(book_ids)))
        rows = [self.gui.library_view.model().index(r, 0) for r in rows]
        self.save_to_disk(True, single_dir=single_dir, single_format=fmt,
                rows=rows, write_opf=False, save_cover=False)

    def books_saved(self, job):
        if job.failed:
            return self.gui.device_job_exception(job)
