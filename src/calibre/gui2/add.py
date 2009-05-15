'''
UI for adding books to the database
'''
import os
from Queue import Queue, Empty

from PyQt4.Qt import QThread, SIGNAL, QObject, QTimer, Qt

from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2 import question_dialog
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata import MetaInformation
from calibre.constants import preferred_encoding

class RecursiveFind(QThread):

    def __init__(self, parent, db, root, single):
        QThread.__init__(self, parent)
        self.db = db
        self.path = root
        self.single_book_per_directory = single
        self.canceled = False

    def run(self):
        root = os.path.abspath(self.path)
        self.books = []
        for dirpath in os.walk(root):
            if self.canceled:
                return
            self.emit(SIGNAL('update(PyQt_PyObject)'),
                        _('Searching in')+' '+dirpath[0])
            self.books += list(self.db.find_books_in_directory(dirpath[0],
                                            self.single_book_per_directory))
        self.books = [formats for formats in self.books if formats]

        if not self.canceled:
            self.emit(SIGNAL('found(PyQt_PyObject)'), self.books)


class Adder(QObject):

    def __init__(self, parent, db, callback):
        QObject.__init__(self, parent)
        self.pd = ProgressDialog(_('Add books'), parent=parent)
        self.db = db
        self.pd.setModal(True)
        self.pd.show()
        self._parent = parent
        self.number_of_books_added = 0
        self.rfind = self.worker = self.timer = None
        self.callback = callback
        self.callback_called = False
        self.infos, self.paths, self.names = [], [], []
        self.connect(self.pd, SIGNAL('canceled()'), self.canceled)

    def add_recursive(self, root, single=True):
        self.path = root
        self.pd.set_msg(_('Searching for books in all sub-directories...'))
        self.pd.set_min(0)
        self.pd.set_max(0)
        self.pd.value = 0
        self.rfind = RecursiveFind(self, self.db, root, single)
        self.connect(self.rfind, SIGNAL('update(PyQt_PyObject)'),
                self.pd.set_msg, Qt.QueuedConnection)
        self.connect(self.rfind, SIGNAL('found(PyQt_PyObject)'),
                self.add, Qt.QueuedConnection)
        self.rfind.start()

    def add(self, books):
        books = [[b] if isinstance(b, basestring) else b for b in books]
        self.rfind = None
        from calibre.ebooks.metadata.worker import read_metadata
        self.rq = Queue()
        tasks = []
        self.ids = {}
        self.nmap = {}
        self.duplicates = []
        for i, b in enumerate(books):
            tasks.append((i, b))
            self.ids[i] = b
            self.nmap[i] = os.path.basename(b[0])
        self.worker = read_metadata(tasks, self.rq)
        self.pd.set_min(0)
        self.pd.set_max(len(self.ids))
        self.pd.value = 0
        self.timer = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.update)
        self.timer.start(200)

    def add_formats(self, id, formats):
        for path in formats:
            fmt = os.path.splitext(path)[-1].replace('.', '').upper()
            self.db.add_format(id, fmt, open(path, 'rb'), index_is_id=True,
                    notify=False)

    def canceled(self):
        if self.rfind is not None:
            self.rfind.cenceled = True
        if self.timer is not None:
            self.timer.stop()
        if self.worker is not None:
            self.worker.canceled = True
        self.pd.hide()
        if not self.callback_called:
            self.callback(self.paths, self.names, self.infos)
            self.callback_called = True



    def update(self):
        if not self.ids:
            self.timer.stop()
            self.process_duplicates()
            self.pd.hide()
            if not self.callback_called:
               self.callback(self.paths, self.names, self.infos)
               self.callback_called = True
            return

        try:
            id, opf, cover = self.rq.get_nowait()
        except Empty:
            return
        self.pd.value += 1
        formats = self.ids.pop(id)
        mi = MetaInformation(OPF(opf))
        name = self.nmap.pop(id)
        if not mi.title:
            mi.title = os.path.splitext(name)[0]
        mi.title = mi.title if isinstance(mi.title, unicode) else \
                   mi.title.decode(preferred_encoding, 'replace')
        self.pd.set_msg(_('Added')+' '+mi.title)

        if self.db is not None:
            if cover:
                cover = open(cover, 'rb').read()
            id = self.db.create_book_entry(mi, cover=cover, add_duplicates=False)
            self.number_of_books_added += 1
            if id is None:
                self.duplicates.append((mi, cover, formats))
            else:
                self.add_formats(id, formats)
        else:
            self.names.append(name)
            self.paths.append(formats[0])
            self.infos.append({'title':mi.title,
                           'authors':', '.join(mi.authors),
                           'cover':None,
                           'tags':mi.tags if mi.tags else []})

    def process_duplicates(self):
        if not self.duplicates:
            return
        files = [x[0].title for x in self.duplicates]
        if question_dialog(self._parent, _('Duplicates found!'),
                        _('Books with the same title as the following already '
                        'exist in the database. Add them anyway?'),
                        '\n'.join(files)):
            for mi, cover, formats in self.duplicates:
                id = self.db.create_book_entry(mi, cover=cover,
                        add_duplicates=True)
                self.add_formats(id, formats)
                self.number_of_books_added += 1

