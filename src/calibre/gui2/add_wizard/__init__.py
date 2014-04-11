#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt5.Qt import QWizard, QWizardPage, QIcon, QPixmap, Qt, QThread, \
        pyqtSignal

from calibre.gui2 import error_dialog, choose_dir, gprefs
from calibre.library.add_to_library import find_folders_under, \
    find_books_in_folder, hash_merge_format_collections

class WizardPage(QWizardPage): # {{{

    def __init__(self, db, parent):
        QWizardPage.__init__(self, parent)
        self.db = db
        self.register = parent.register
        self.setupUi(self)

        self.do_init()

    def do_init(self):
        pass

# }}}

# Scan root folder Page {{{

from calibre.gui2.add_wizard.scan_ui import Ui_WizardPage as ScanWidget

class RecursiveFinder(QThread):

    activity_changed = pyqtSignal(object, object) # description and total count
    activity_iterated = pyqtSignal(object, object) # item desc, progress number

    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.canceled = False
        self.cancel_callback = lambda : self.canceled
        self.folders = set([])
        self.books = []

    def cancel(self, *args):
        self.canceled = True

    def set_params(self, root, db, one_per_folder):
        self.root, self.db = root, db
        self.one_per_folder = one_per_folder

    def run(self):
        self.activity_changed.emit(_('Searching for sub-folders'), 0)
        self.folders = find_folders_under(self.root, self.db,
                cancel_callback=self.cancel_callback)
        if self.canceled:
            return
        self.activity_changed.emit(_('Searching for books'), len(self.folders))
        for i, folder in enumerate(self.folders):
            if self.canceled:
                break
            books_in_folder = find_books_in_folder(folder, self.one_per_folder,
                    cancel_callback=self.cancel_callback)
            if self.canceled:
                break
            self.books.extend(books_in_folder)
            self.activity_iterated.emit(folder, i)

        self.activity_changed.emit(
                _('Looking for duplicates based on file hash'), 0)

        self.books = hash_merge_format_collections(self.books,
                cancel_callback=self.cancel_callback)



class ScanPage(WizardPage, ScanWidget):

    ID = 2

# }}}

# Welcome Page {{{

from calibre.gui2.add_wizard.welcome_ui import Ui_WizardPage as WelcomeWidget

class WelcomePage(WizardPage, WelcomeWidget):

    ID = 1

    def do_init(self):
        # Root folder must be filled
        self.registerField('root_folder*', self.opt_root_folder)

        self.register['root_folder'] = self.get_root_folder
        self.register['one_per_folder'] = self.get_one_per_folder

        self.button_choose_root_folder.clicked.connect(self.choose_root_folder)

    def choose_root_folder(self, *args):
        x = self.get_root_folder()
        if x is None:
            x = '~'
        x = choose_dir(self, 'add wizard choose root folder',
                _('Choose root folder'), default_dir=x)
        if x is not None:
            self.opt_root_folder.setText(os.path.abspath(x))

    def initializePage(self):
        opf = gprefs.get('add wizard one per folder', True)
        self.opt_one_per_folder.setChecked(opf)
        self.opt_many_per_folder.setChecked(not opf)
        add_dir = gprefs.get('add wizard root folder', None)
        if add_dir is not None:
            self.opt_root_folder.setText(add_dir)

    def get_root_folder(self):
        x = unicode(self.opt_root_folder.text()).strip()
        if not x:
            return None
        return os.path.abspath(x)

    def get_one_per_folder(self):
        return self.opt_one_per_folder.isChecked()

    def validatePage(self):
        x = self.get_root_folder()
        if x and os.access(x, os.R_OK) and os.path.isdir(x):
            gprefs['add wizard root folder'] = x
            gprefs['add wizard one per folder'] = self.get_one_per_folder()
            return True
        error_dialog(self, _('Invalid root folder'),
                x + _('is not a valid root folder'), show=True)
        return False

# }}}

class Wizard(QWizard): # {{{

    def __init__(self, db, parent=None):
        QWizard.__init__(self, parent)
        self.setModal(True)
        self.setWindowTitle(_('Add books to calibre'))
        self.setWindowIcon(QIcon(I('add_book.png')))
        self.setPixmap(self.LogoPixmap, QPixmap(P('content_server/calibre.png')).scaledToHeight(80,
            Qt.SmoothTransformation))
        self.setPixmap(self.WatermarkPixmap,
            QPixmap(I('welcome_wizard.png')))

        self.register = {}

        for attr, cls in [
                ('welcome_page', WelcomePage),
                ('scan_page', ScanPage),
                ]:
            setattr(self, attr, cls(db, self))
            self.setPage(getattr(cls, 'ID'), getattr(self, attr))

# }}}

# Test Wizard {{{
if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    from calibre.library import db
    app = QApplication([])
    w = Wizard(db())
    w.exec_()
# }}}

