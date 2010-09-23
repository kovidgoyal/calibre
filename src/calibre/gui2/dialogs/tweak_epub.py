#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil
from contextlib import closing
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

from PyQt4.Qt import QDialog

from calibre.gui2 import open_local_file
from calibre.gui2.dialogs.tweak_epub_ui import Ui_Dialog
from calibre.libunzip import extract as zipextract
from calibre.ptempfile import PersistentTemporaryDirectory

class TweakEpub(QDialog, Ui_Dialog):
    '''
    Display controls for tweaking ePubs

    '''

    def __init__(self, parent, epub):
        QDialog.__init__(self, parent)

        self._epub = epub
        self._exploded = None
        self._output = None

        # Run the dialog setup generated from tweak_epub.ui
        self.setupUi(self)

        self.cancel_button.clicked.connect(self.reject)
        self.explode_button.clicked.connect(self.explode)
        self.rebuild_button.clicked.connect(self.rebuild)

        # Position update dialog overlaying top left of app window
        parent_loc = parent.pos()
        self.move(parent_loc.x(),parent_loc.y())

    def cleanup(self):
        # Delete directory containing exploded ePub
        if self._exploded is not None:
            shutil.rmtree(self._exploded, ignore_errors=True)


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

    def rebuild(self, *args):
        self._output = os.path.join(self._exploded, 'rebuilt.epub')
        with closing(ZipFile(self._output, 'w', compression=ZIP_DEFLATED)) as zf:
            # Write mimetype
            zf.write(os.path.join(self._exploded,'mimetype'), 'mimetype', compress_type=ZIP_STORED)
            # Write everything else
            exclude_files = ['.DS_Store','mimetype','iTunesMetadata.plist','rebuilt.epub']
            for root, dirs, files in os.walk(self._exploded):
                for fn in files:
                    if fn in exclude_files:
                        continue
                    absfn = os.path.join(root, fn)
                    zfn = os.path.relpath(absfn,
                            self._exploded).replace(os.sep, '/')
                    zf.write(absfn, zfn)
        return QDialog.accept(self)

