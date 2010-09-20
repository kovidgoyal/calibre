#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, sys
from contextlib import closing
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

from PyQt4 import QtGui
from PyQt4.Qt import QDialog, SIGNAL

from calibre import prints
from calibre.constants import iswindows, isosx, DEBUG
from calibre.gui2.dialogs.tweak_epub_ui import Ui_Dialog
from calibre.libunzip import extract as zipextract
from calibre.ptempfile import PersistentTemporaryDirectory

class TweakEpub(QDialog, Ui_Dialog):
    '''
    Display controls for tweaking ePubs

    To do:
        - need way to kill file browser proc in cleanup()
        - Windows file browser launch
        - linux file browser launch
    '''

    def __init__(self, parent, epub):
        QDialog.__init__(self, parent)

        self._epub = epub
        self._exploded = None
        self._file_browser_proc = None
        self._output = None

        # Run the dialog setup generated from tweak_epub.ui
        self.setupUi(self)

        self.connect(self.cancel_button,
                     SIGNAL("clicked()"),
                     self.cancel)
        self.connect(self.explode_button,
                     SIGNAL("clicked()"),
                     self.explode)
        self.connect(self.rebuild_button,
                     SIGNAL("clicked()"),
                     self.rebuild)

        # Position update dialog overlaying top left of app window
        parent_loc = parent.pos()
        self.move(parent_loc.x(),parent_loc.y())

    def cancel(self):
        if DEBUG:
            prints("gui2.dialogs.tweak_epub:TweakEpub.cancel()")
        return QDialog.reject(self)

    def cleanup(self):
        '''
        Kill the file browser
        '''
        if DEBUG:
            prints("gui2.dialogs.tweak_epub:TweakEpub.cleanup()")
        # Kill file browser proc
        if self._file_browser_proc:
            if DEBUG:
                prints(" killing file browser proc")
            #self._file_browser_proc.terminate()
            #self._file_browser_proc.kill()
            #self._file_browser_send_signal()
            #self._file_browser_proc = None

        # Delete directory containing exploded ePub
        if self._exploded is not None:
            if DEBUG:
                prints(" removing exploded dir\n %s" % self._exploded)
            shutil.rmtree(self._exploded, ignore_errors=True)


    def display_exploded(self):
        '''
        Generic subprocess launch of native file browser
        User can use right-click to 'Open with ...'
        '''
        if DEBUG:
            prints("gui2.dialogs.tweak_epub:TweakEpub.display_exploded()")
        if isosx:
            cmd = 'open %s' % self._exploded
        elif iswindows:
            cmd = 'start explorer.exe /e,/root,%s' % self._exploded
        else:
            cmd = '<linux command to open native file browser>'

        # *** Kovid - need a way of launching this process than can be killed in cleanup() ***
        self._file_browser_proc = subprocess.Popen(cmd, shell=True)

    def explode(self):
        if DEBUG:
            prints("gui2.dialogs.tweak_epub:TweakEpub.explode()")
        if self._exploded is None:
            if DEBUG:
                prints(" exploding %s" % self._epub)
            self._exploded = PersistentTemporaryDirectory("_exploded", prefix='')
            zipextract(self._epub, self._exploded)
            self.display_exploded()
            self.rebuild_button.setEnabled(True)

    def rebuild(self):
        if DEBUG:
            prints("gui2.dialogs.tweak_epub:TweakEpub.rebuild()")
        self._output = os.path.join(self._exploded, 'rebuilt.epub')
        with closing(ZipFile(self._output, 'w', compression=ZIP_DEFLATED)) as zf:
            # Write mimetype
            zf.write(os.path.join(self._exploded,'mimetype'), 'mimetype', compress_type=ZIP_STORED)
            # Write everything else
            exclude_files = ['.DS_Store','mimetype','iTunesMetadata.plist']
            for root, dirs, files in os.walk(self._exploded):
                for fn in files:
                    if fn in exclude_files:
                        continue
                    absfn = os.path.join(root, fn)
                    zfn = absfn[len(self._exploded) + len(os.sep):]
                    zf.write(absfn, zfn)
        return QDialog.accept(self)

