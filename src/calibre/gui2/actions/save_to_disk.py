#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QMenu, pyqtSignal

from calibre.utils.config import prefs
from calibre.gui2 import error_dialog, Dispatcher, \
    choose_dir, warning_dialog, open_local_file
from calibre.gui2.actions import InterfaceAction
from calibre.ebooks import BOOK_EXTENSIONS

class SaveMenu(QMenu): # {{{

    save_fmt = pyqtSignal(object)

    def __init__(self, parent):
        QMenu.__init__(self, _('Save single format to disk...'), parent)
        for ext in sorted(BOOK_EXTENSIONS):
            action = self.addAction(ext.upper())
            setattr(self, 'do_'+ext, partial(self.do, ext))
            action.triggered.connect(
                    getattr(self, 'do_'+ext))

    def do(self, ext, *args):
        self.save_fmt.emit(ext)

# }}}


class SaveToDiskAction(InterfaceAction):

    name = "Save To Disk"
    action_spec = (_('Save to disk'), 'save.png', None, _('S'))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.save_to_disk)
        self.save_menu = QMenu()
        self.save_menu.addAction(_('Save to disk'), partial(self.save_to_disk,
            False))
        self.save_menu.addAction(_('Save to disk in a single directory'),
                partial(self.save_to_single_dir, False))
        self.save_menu.addAction(_('Save only %s format to disk')%
                prefs['output_format'].upper(),
                partial(self.save_single_format_to_disk, False))
        self.save_menu.addAction(
                _('Save only %s format to disk in a single directory')%
                prefs['output_format'].upper(),
                partial(self.save_single_fmt_to_single_dir, False))
        self.save_sub_menu = SaveMenu(self.gui)
        self.save_sub_menu_action = self.save_menu.addMenu(self.save_sub_menu)
        self.save_sub_menu.save_fmt.connect(self.save_specific_format_disk)
        self.qaction.setMenu(self.save_menu)

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

    def save_specific_format_disk(self, fmt):
        self.save_to_disk(False, False, fmt)

    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_single_fmt_to_single_dir(self, *args):
        self.save_to_disk(False, single_dir=True,
                single_format=prefs['output_format'])

    def save_to_disk(self, checked, single_dir=False, single_format=None):
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
            self._saver = Saver(self.gui, self.gui.library_view.model().db,
                    Dispatcher(self._books_saved), rows, path, opts,
                    spare_server=self.gui.spare_server)

        else:
            paths = self.gui.current_view().model().paths(rows)
            self.gui.device_manager.save_books(
                    Dispatcher(self.books_saved), paths, path)


    def _books_saved(self, path, failures, error):
        self._saver = None
        if error:
            return error_dialog(self.gui, _('Error while saving'),
                    _('There was an error while saving.'),
                    error, show=True)
        if failures:
            failures = [u'%s\n\t%s'%
                    (title, '\n\t'.join(err.splitlines())) for title, err in
                    failures]

            warning_dialog(self.gui, _('Could not save some books'),
            _('Could not save some books') + ', ' +
            _('Click the show details button to see which ones.'),
            u'\n\n'.join(failures), show=True)
        open_local_file(path)

    def books_saved(self, job):
        if job.failed:
            return self.gui.device_job_exception(job)


