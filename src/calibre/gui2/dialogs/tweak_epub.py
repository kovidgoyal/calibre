#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil
from itertools import repeat, izip
from calibre.utils.zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

from PyQt4.Qt import QDialog

from calibre.constants import isosx
from calibre.gui2 import open_local_file, error_dialog
from calibre.gui2.dialogs.tweak_epub_ui import Ui_Dialog
from calibre.libunzip import extract as zipextract
from calibre.ptempfile import (PersistentTemporaryDirectory,
        PersistentTemporaryFile)

class TweakEpub(QDialog, Ui_Dialog):
    '''
    Display controls for tweaking ePubs

    '''

    def __init__(self, parent, epub):
        QDialog.__init__(self, parent)

        self._epub = epub
        self._exploded = None
        self._output = None
        self.ishtmlz = epub.lower().endswith('.htmlz')
        self.rebuilt_name = 'rebuilt.' + ('htmlz' if self.ishtmlz else 'epub')

        # Run the dialog setup generated from tweak_epub.ui
        self.setupUi(self)
        for x, props in [(self, ['windowTitle']), (self.label, ['text'])]+\
                list(izip([self.cancel_button, self.explode_button,
                    self.rebuild_button, self.preview_button],
                    repeat(['text', 'statusTip', 'toolTip']))):
            for prop in props:
                val = unicode(getattr(x, prop)())
                val = val.format('HTMLZ' if self.ishtmlz else 'ePub')
                prop = 'set' + prop[0].upper() + prop[1:]
                getattr(x, prop)(val)

        self.cancel_button.clicked.connect(self.reject)
        self.explode_button.clicked.connect(self.explode)
        self.rebuild_button.clicked.connect(self.rebuild)
        self.preview_button.clicked.connect(self.preview)

        # Position update dialog overlaying top left of app window
        parent_loc = parent.pos()
        self.move(parent_loc.x(),parent_loc.y())

        self.gui = parent
        self._preview_files = []

    def cleanup(self):
        if isosx:
            try:
                import appscript
                self.finder = appscript.app('Finder')
                self.finder.Finder_windows[os.path.basename(self._exploded)].close()
            except:
                # appscript fails to load on 10.4
                pass

        # Delete directory containing exploded ePub
        if self._exploded is not None:
            shutil.rmtree(self._exploded, ignore_errors=True)
        for x in self._preview_files:
            try:
                os.remove(x)
            except:
                pass

    def display_exploded(self):
        '''
        Generic subprocess launch of native file browser
        User can use right-click to 'Open with ...'
        '''
        open_local_file(self._exploded)

    def explode(self, *args):
        if self._exploded is None:
            self._exploded = PersistentTemporaryDirectory("_exploded", prefix='')
            zipextract(self._epub, self._exploded)
            self.display_exploded()
            self.rebuild_button.setEnabled(True)
            self.explode_button.setEnabled(False)

    def do_rebuild(self, src):
        with ZipFile(src, 'w', compression=ZIP_DEFLATED) as zf:
            # Write mimetype
            mt = os.path.join(self._exploded, 'mimetype')
            if os.path.exists(mt):
                zf.write(mt, 'mimetype', compress_type=ZIP_STORED)
            # Write everything else
            exclude_files = ['.DS_Store','mimetype','iTunesMetadata.plist',self.rebuilt_name]
            for root, dirs, files in os.walk(self._exploded):
                for fn in files:
                    if fn in exclude_files:
                        continue
                    absfn = os.path.join(root, fn)
                    zfn = os.path.relpath(absfn,
                            self._exploded).replace(os.sep, '/')
                    zf.write(absfn, zfn)

    def preview(self):
        if not self._exploded:
            msg = _('You must first explode the %s before previewing.')
            msg = msg%('HTMLZ' if self.ishtmlz else 'ePub')
            return error_dialog(self, _('Cannot preview'), msg, show=True)

        tf = PersistentTemporaryFile('.htmlz' if self.ishtmlz else '.epub')
        tf.close()
        self._preview_files.append(tf.name)

        self.do_rebuild(tf.name)

        self.gui.iactions['View']._view_file(tf.name)

    def rebuild(self, *args):
        self._output = os.path.join(self._exploded, self.rebuilt_name)
        self.do_rebuild(self._output)
        return QDialog.accept(self)

