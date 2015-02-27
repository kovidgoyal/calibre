#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from threading import Thread
from functools import partial

from PyQt5.Qt import (
    QApplication, QStackedLayout, QVBoxLayout, QWidget, QLabel, Qt,
    QListWidget, QSize, pyqtSignal, QListWidgetItem, QIcon, QByteArray,
    QBuffer, QPixmap)

from calibre import as_unicode
from calibre.constants import iswindows, isosx
from calibre.gui2 import error_dialog, choose_files
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.config import JSONConfig

DESC_ROLE = Qt.UserRole
ENTRY_ROLE = DESC_ROLE + 1

def pixmap_to_data(pixmap):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytearray(ba.data())

def run_program(entry, path, parent):
    import subprocess
    cmdline = entry_to_cmdline(entry, path)
    print('Running Open With commandline:', repr(cmdline))
    try:
        process = subprocess.Popen(cmdline)
    except Exception as err:
        return error_dialog(
            parent, _('Failed to run'), _(
            'Failed to run program, click "Show Details" for more information'),
            det_msg='Command line: %r\n%s' %(cmdline, as_unicode(err)))
    t = Thread(name='WaitProgram', target=process.wait)
    t.daemon = True
    t.start()

if iswindows:
    oprefs = JSONConfig('windows_open_with')
    run_program
    def run_program(entry, path, parent):
        raise NotImplementedError()

elif isosx:
    oprefs = JSONConfig('osx_open_with')
else:
    # XDG {{{
    oprefs = JSONConfig('xdg_open_with')
    from calibre.utils.open_with.linux import entry_to_cmdline, find_programs, entry_sort_key

    def entry_to_icon_text(entry):
        data = entry.get('icon_data')
        if data is None:
            icon = QIcon(I('blank.png'))
        else:
            pmap = QPixmap()
            pmap.loadFromData(bytes(data))
            icon = QIcon(pmap)
        return icon, entry['Name']

    def entry_to_item(entry, parent):
        icon_path = entry.get('Icon') or I('blank.png')
        ans = QListWidgetItem(QIcon(icon_path), entry.get('Name') or _('Unknown'), parent)
        ans.setData(DESC_ROLE, entry.get('Comment') or '')
        ans.setData(ENTRY_ROLE, entry)
        comment = (entry.get('Comment') or '')
        if comment:
            comment += '\n'
        ans.setToolTip(comment + _('Command line:') + '\n' + (' '.join(entry['Exec'])))

    def choose_manually(filetype, parent):
        ans = choose_files(parent, 'choose-open-with-program-manually', _('Choose a program to open %s files') % filetype.upper(), select_only_single_file=True)
        if ans:
            ans = ans[0]
            if not os.access(ans, os.X_OK):
                return error_dialog(parent, _('Cannot execute'), _(
                    'The program %s is not an executable file') % ans, show=True)
            return {'Exec':[ans, '%f'], 'Name':os.path.basename(ans)}

    def finalize_entry(entry):
        icon_path = entry.get('Icon')
        if icon_path:
            ic = QIcon(icon_path)
            if not ic.isNull():
                pmap = ic.pixmap(48, 48)
                if not pmap.isNull():
                    entry['icon_data'] = pixmap_to_data(pmap)
        entry['MimeType'] = tuple(entry['MimeType'])
        return entry
# }}}

class ChooseProgram(Dialog):  # {{{

    found = pyqtSignal()

    def __init__(self, file_type='jpeg', parent=None, prefs=oprefs):
        self.file_type = file_type
        self.programs = self.find_error = self.selected_entry = None
        self.select_manually = False
        Dialog.__init__(self, _('Choose a program'), 'choose-open-with-program-dialog', parent=parent, prefs=prefs)
        self.found.connect(self.programs_found, type=Qt.QueuedConnection)
        self.pi.startAnimation()
        t = Thread(target=self.find_programs)
        t.daemon = True
        t.start()

    def setup_ui(self):
        self.stacks = s = QStackedLayout(self)
        self.w = w = QWidget(self)
        self.w.l = l = QVBoxLayout(w)
        self.pi = pi = ProgressIndicator(self, 256)
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        w.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter), l.addStretch(1)
        s.addWidget(w)

        self.w2 = w = QWidget(self)
        self.l = l = QVBoxLayout(w)
        s.addWidget(w)

        self.la = la = QLabel(_('Choose a program to open %s files') % self.file_type.upper())
        self.plist = pl = QListWidget(self)
        pl.setIconSize(QSize(48, 48)), pl.setSpacing(5)
        pl.doubleClicked.connect(self.accept)
        l.addWidget(la), l.addWidget(pl)
        la.setBuddy(pl)

        b = self.bb.addButton(_('&Browse computer for program'), self.bb.ActionRole)
        b.clicked.connect(self.manual)
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(600, 500)

    def find_programs(self):
        try:
            self.programs = find_programs(self.file_type.split())
        except Exception:
            import traceback
            self.find_error = traceback.print_exc()
        self.found.emit()

    def programs_found(self):
        if self.find_error is not None:
            error_dialog(self, _('Error finding programs'), _(
                'Failed to find programs on your computer, click "Show details" for'
                ' more information'), det_msg=self.find_error, show=True)
            self.select_manually = True
            return self.reject()
        if not self.programs:
            self.select_manually = True
            return self.reject()
        for entry in self.programs:
            entry_to_item(entry, self.plist)
        self.stacks.setCurrentIndex(1)

    def accept(self):
        ci = self.plist.currentItem()
        if ci is not None:
            self.selected_entry = ci.data(ENTRY_ROLE)
        return Dialog.accept(self)

    def manual(self):
        self.select_manually = True
        self.reject()

oprefs.defaults['entries'] = {}

def choose_program(file_type='jpeg', parent=None, prefs=oprefs):
    d = ChooseProgram(file_type, parent, prefs)
    d.exec_()
    entry = choose_manually(file_type, parent) if d.select_manually else d.selected_entry
    if entry is not None:
        entry = finalize_entry(entry)
        entry['keyboard_shortcut'] = None
        entries = oprefs['entries']
        if file_type not in entries:
            entries[file_type] = []
        entries[file_type].append(entry)
        entries[file_type].sort(key=entry_sort_key)
        oprefs['entries'] = entries
    return entry

def populate_menu(menu, receiver, file_type):
    for entry in oprefs['entries'].get(file_type, ()):
        ac = menu.addAction(*entry_to_icon_text(entry))
        ac.triggered.connect(partial(receiver, entry))
    return menu

# }}}

if __name__ == '__main__':
    from pprint import pprint
    app = QApplication([])
    pprint(choose_program('pdf'))
    del app
