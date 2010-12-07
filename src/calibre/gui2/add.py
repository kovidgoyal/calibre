'''
UI for adding books to the database and saving books to disk
'''
import os, shutil, time
from Queue import Queue, Empty
from threading import Thread

from PyQt4.Qt import QThread, SIGNAL, QObject, QTimer, Qt, \
        QProgressDialog

from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2 import question_dialog, error_dialog, info_dialog
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata import MetaInformation
from calibre.constants import preferred_encoding, filesystem_encoding
from calibre.utils.config import prefs

class DuplicatesAdder(QThread): # {{{
    # Add duplicate books
    def __init__(self, parent, db, duplicates, db_adder):
        QThread.__init__(self, parent)
        self.db, self.db_adder = db, db_adder
        self.duplicates = duplicates

    def run(self):
        count = 1
        for mi, cover, formats in self.duplicates:
            formats = [f for f in formats if not f.lower().endswith('.opf')]
            id = self.db.create_book_entry(mi, cover=cover,
                    add_duplicates=True)
            # here we add all the formats for dupe book record created above
            self.db_adder.add_formats(id, formats)
            self.db_adder.number_of_books_added += 1
            self.emit(SIGNAL('added(PyQt_PyObject)'), count)
            count += 1
        self.emit(SIGNAL('adding_done()'))
# }}}

class RecursiveFind(QThread): # {{{

    def __init__(self, parent, db, root, single):
        QThread.__init__(self, parent)
        self.db = db
        self.path = root
        self.single_book_per_directory = single
        self.canceled = False

    def walk(self, root):
        self.books = []
        for dirpath in os.walk(root):
            if self.canceled:
                return
            self.emit(SIGNAL('update(PyQt_PyObject)'),
                        _('Searching in')+' '+dirpath[0])
            self.books += list(self.db.find_books_in_directory(dirpath[0],
                                            self.single_book_per_directory))

    def run(self):
        root = os.path.abspath(self.path)
        try:
            self.walk(root)
        except:
            try:
                if isinstance(root, unicode):
                    root = root.encode(filesystem_encoding)
                self.walk(root)
            except Exception, err:
                import traceback
                traceback.print_exc()
                try:
                    msg = unicode(err)
                except:
                    msg = repr(err)
                self.emit(SIGNAL('found(PyQt_PyObject)'), msg)
                return

        self.books = [formats for formats in self.books if formats]

        if not self.canceled:
            self.emit(SIGNAL('found(PyQt_PyObject)'), self.books)

# }}}

class DBAdder(Thread): # {{{

    def __init__(self, db, ids, nmap):
        self.db, self.ids, self.nmap = db, dict(**ids), dict(**nmap)
        self.end = False
        self.critical = {}
        self.number_of_books_added = 0
        self.duplicates = []
        self.names, self.paths, self.infos = [], [], []
        Thread.__init__(self)
        self.daemon = True
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.merged_books = set([])

    def run(self):
        while not self.end:
            try:
                id, opf, cover = self.input_queue.get(True, 0.2)
            except Empty:
                continue
            name = self.nmap.pop(id)
            title = None
            try:
                title = self.add(id, opf, cover, name)
            except:
                import traceback
                self.critical[name] = traceback.format_exc()
                title = name
            self.output_queue.put(title)

    def process_formats(self, opf, formats):
        imp = opf[:-4]+'.import'
        if not os.access(imp, os.R_OK):
            return formats
        fmt_map = {}
        for line in open(imp, 'rb').readlines():
            if ':' not in line:
                continue
            f, _, p = line.partition(':')
            fmt_map[f] = p.rstrip()
        fmts = []
        for fmt in formats:
            e = os.path.splitext(fmt)[1].replace('.', '').lower()
            fmts.append(fmt_map.get(e, fmt))
            if not os.access(fmts[-1], os.R_OK):
                fmts[-1] = fmt
        return fmts


    def add(self, id, opf, cover, name):
        formats = self.ids.pop(id)
        if opf.endswith('.error'):
            mi = MetaInformation('', [_('Unknown')])
            self.critical[name] = open(opf, 'rb').read().decode('utf-8', 'replace')
        else:
            try:
                mi = OPF(opf).to_book_metadata()
            except:
                import traceback
                mi = MetaInformation('', [_('Unknown')])
                self.critical[name] = traceback.format_exc()
        formats = self.process_formats(opf, formats)
        if not mi.title:
            mi.title = os.path.splitext(name)[0]
        mi.title = mi.title if isinstance(mi.title, unicode) else \
                   mi.title.decode(preferred_encoding, 'replace')
        if mi.application_id == '__calibre_dummy__':
            mi.application_id = None
        if self.db is not None:
            if cover:
                with open(cover, 'rb') as f:
                    cover = f.read()
            orig_formats = formats
            formats = [f for f in formats if not f.lower().endswith('.opf')]
            if prefs['add_formats_to_existing']:
                identical_book_list = self.db.find_identical_books(mi)

                if identical_book_list: # books with same author and nearly same title exist in db
                    self.merged_books.add(mi.title)
                    for identical_book in identical_book_list:
                        self.add_formats(identical_book, formats, replace=False)
                else:
                    id = self.db.create_book_entry(mi, cover=cover, add_duplicates=True)
                    self.number_of_books_added += 1
                    self.add_formats(id, formats)
            else:
                id = self.db.create_book_entry(mi, cover=cover, add_duplicates=False)
                if id is None:
                    self.duplicates.append((mi, cover, orig_formats))
                else:
                    self.add_formats(id, formats)
                    self.number_of_books_added += 1
        else:
            self.names.append(name)
            self.paths.append(formats[0])
            self.infos.append(mi)
        return mi.title

    def add_formats(self, id, formats, replace=True):
        for path in formats:
            fmt = os.path.splitext(path)[-1].replace('.', '').upper()
            with open(path, 'rb') as f:
                self.db.add_format(id, fmt, f, index_is_id=True,
                        notify=False, replace=replace)

# }}}

class Adder(QObject): # {{{

    ADD_TIMEOUT = 600 # seconds

    def __init__(self, parent, db, callback, spare_server=None):
        QObject.__init__(self, parent)
        self.pd = ProgressDialog(_('Adding...'), parent=parent)
        self.spare_server = spare_server
        self.db = db
        self.pd.setModal(True)
        self.pd.show()
        self._parent = parent
        self.rfind = self.worker = self.timer = None
        self.callback = callback
        self.callback_called = False
        self.connect(self.pd, SIGNAL('canceled()'), self.canceled)

    def add_recursive(self, root, single=True):
        self.path = root
        self.pd.set_msg(_('Searching in all sub-directories...'))
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
        if isinstance(books, basestring):
            error_dialog(self.pd, _('Path error'),
                    _('The specified directory could not be processed.'),
                    det_msg=books, show=True)
            return self.canceled()
        if not books:
            info_dialog(self.pd, _('No books'),
                    _('No books found'), show=True)
            return self.canceled()
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
        self.worker = read_metadata(tasks, self.rq,
                spare_server=self.spare_server)
        self.pd.set_min(0)
        self.pd.set_max(len(self.ids))
        self.pd.value = 0
        self.db_adder = DBAdder(self.db, self.ids, self.nmap)
        self.db_adder.start()
        self.last_added_at = time.time()
        self.entry_count = len(self.ids)
        self.continue_updating = True
        QTimer.singleShot(200, self.update)

    def canceled(self):
        self.continue_updating = False
        if self.rfind is not None:
            self.rfind.canceled = True
        if self.worker is not None:
            self.worker.canceled = True
        if hasattr(self, 'db_adder'):
            self.db_adder.end = True
        self.pd.hide()
        if not self.callback_called:
            self.callback(self.paths, self.names, self.infos)
            self.callback_called = True

    def duplicates_processed(self):
        self.db_adder.end = True
        if not self.callback_called:
            self.callback(self.paths, self.names, self.infos)
            self.callback_called = True
        if hasattr(self, '__p_d'):
            self.__p_d.hide()

    def update(self):
        if self.entry_count <= 0:
            self.continue_updating = False
            self.pd.hide()
            self.process_duplicates()
            return

        try:
            id, opf, cover = self.rq.get_nowait()
            self.db_adder.input_queue.put((id, opf, cover))
            self.last_added_at = time.time()
        except Empty:
            pass

        try:
            title = self.db_adder.output_queue.get_nowait()
            self.pd.value += 1
            self.pd.set_msg(_('Added')+' '+title)
            self.last_added_at = time.time()
            self.entry_count -= 1
        except Empty:
            pass

        if (time.time() - self.last_added_at) > self.ADD_TIMEOUT:
            self.continue_updating = False
            self.pd.hide()
            self.db_adder.end = True
            if not self.callback_called:
                self.callback([], [], [])
                self.callback_called = True
            error_dialog(self._parent, _('Adding failed'),
                    _('The add books process seems to have hung.'
                        ' Try restarting calibre and adding the '
                        'books in smaller increments, until you '
                        'find the problem book.'), show=True)

        if self.continue_updating:
            QTimer.singleShot(200, self.update)


    def process_duplicates(self):
        duplicates = self.db_adder.duplicates
        if not duplicates:
            return self.duplicates_processed()
        self.pd.hide()
        files = [x[0].title for x in duplicates]
        if question_dialog(self._parent, _('Duplicates found!'),
                        _('Books with the same title as the following already '
                        'exist in the database. Add them anyway?'),
                        '\n'.join(files)):
            pd = QProgressDialog(_('Adding duplicates...'), '', 0, len(duplicates),
                    self._parent)
            pd.setCancelButton(None)
            pd.setValue(0)
            pd.show()
            self.__p_d = pd
            self.__d_a = DuplicatesAdder(self._parent, self.db, duplicates,
                    self.db_adder)
            self.connect(self.__d_a, SIGNAL('added(PyQt_PyObject)'),
                    pd.setValue)
            self.connect(self.__d_a, SIGNAL('adding_done()'),
                    self.duplicates_processed)
            self.__d_a.start()
        else:
            return self.duplicates_processed()

    def cleanup(self):
        if hasattr(self, 'pd'):
            self.pd.hide()
        if hasattr(self, 'worker') and hasattr(self.worker, 'tdir') and \
                self.worker.tdir is not None:
            if os.path.exists(self.worker.tdir):
                try:
                    shutil.rmtree(self.worker.tdir)
                except:
                    pass

    @property
    def number_of_books_added(self):
        return getattr(getattr(self, 'db_adder', None), 'number_of_books_added',
                0)

    @property
    def merged_books(self):
        return getattr(getattr(self, 'db_adder', None), 'merged_books',
                set([]))

    @property
    def critical(self):
        return getattr(getattr(self, 'db_adder', None), 'critical',
                {})
    @property
    def paths(self):
        return getattr(getattr(self, 'db_adder', None), 'paths',
                [])

    @property
    def names(self):
        return getattr(getattr(self, 'db_adder', None), 'names',
                [])

    @property
    def infos(self):
        return getattr(getattr(self, 'db_adder', None), 'infos',
                [])

# }}}

class Saver(QObject): # {{{

    def __init__(self, parent, db, callback, rows, path, opts,
            spare_server=None):
        QObject.__init__(self, parent)
        self.pd = ProgressDialog(_('Saving...'), parent=parent)
        self.spare_server = spare_server
        self.db = db
        self.opts = opts
        self.pd.setModal(True)
        self.pd.show()
        self.pd.set_min(0)
        self._parent = parent
        self.callback = callback
        self.callback_called = False
        self.rq = Queue()
        self.ids = [x for x in map(db.id, [r.row() for r in rows]) if x is not None]
        self.pd.set_max(len(self.ids))
        self.pd.value = 0
        self.failures = set([])

        from calibre.ebooks.metadata.worker import SaveWorker
        self.worker = SaveWorker(self.rq, db, self.ids, path, self.opts,
                spare_server=self.spare_server)
        self.pd.canceled_signal.connect(self.canceled)
        self.timer = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.update)
        self.timer.start(200)


    def canceled(self):
        if self.timer is not None:
            self.timer.stop()
        if self.worker is not None:
            self.worker.canceled = True
        self.pd.hide()
        if not self.callback_called:
            self.callback(self.worker.path, self.failures, self.worker.error)
            self.callback_called = True


    def update(self):
        if not self.ids or not self.worker.is_alive():
            self.timer.stop()
            self.pd.hide()
            while self.ids:
                before = len(self.ids)
                self.get_result()
                if before == len(self.ids):
                    for i in list(self.ids):
                        self.failures.add(('id:%d'%i, 'Unknown error'))
                        self.ids.remove(i)
                    break
            if not self.callback_called:
                try:
                    self.worker.join(1.5)
                except:
                    pass # The worker was not yet started
                self.callback(self.worker.path, self.failures, self.worker.error)
                self.callback_called = True
            return

        self.get_result()


    def get_result(self):
        try:
            id, title, ok, tb = self.rq.get_nowait()
        except Empty:
            return
        self.pd.value += 1
        self.ids.remove(id)
        if not isinstance(title, unicode):
            title = str(title).decode(preferred_encoding, 'replace')
        self.pd.set_msg(_('Saved')+' '+title)

        if not ok:
            self.failures.add((title, tb))
# }}}

