'''
UI for adding books to the database and saving books to disk
'''
import os, shutil, time
from Queue import Queue, Empty
from functools import partial

from PyQt4.Qt import QThread, QObject, Qt, QProgressDialog, pyqtSignal, QTimer

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2 import (error_dialog, info_dialog, gprefs,
        warning_dialog, available_width)
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata import MetaInformation
from calibre.constants import preferred_encoding, filesystem_encoding, DEBUG
from calibre.utils.config import prefs
from calibre import prints, force_unicode, as_unicode

single_shot = partial(QTimer.singleShot, 75)

class DuplicatesAdder(QObject):  # {{{

    added = pyqtSignal(object)
    adding_done = pyqtSignal()

    def __init__(self, parent, db, duplicates, db_adder):
        QObject.__init__(self, parent)
        self.db, self.db_adder = db, db_adder
        self.duplicates = list(duplicates)
        self.count = 0
        single_shot(self.add_one)

    def add_one(self):
        if not self.duplicates:
            self.adding_done.emit()
            return

        mi, cover, formats = self.duplicates.pop()
        formats = [f for f in formats if not f.lower().endswith('.opf')]
        id = self.db.create_book_entry(mi, cover=cover,
                add_duplicates=True)
        # here we add all the formats for dupe book record created above
        self.db_adder.add_formats(id, formats)
        self.db_adder.number_of_books_added += 1
        self.db_adder.auto_convert_books.add(id)
        self.count += 1
        self.added.emit(self.count)
        single_shot(self.add_one)

# }}}

class RecursiveFind(QThread):  # {{{

    update = pyqtSignal(object)
    found  = pyqtSignal(object)

    def __init__(self, parent, db, root, single, tdir=None):
        QThread.__init__(self, parent)
        self.db = db
        self.path = root
        self.tdir = tdir
        self.single_book_per_directory = single
        self.canceled = False

    def walk(self, root):
        self.books = []
        for dirpath in os.walk(root):
            if self.canceled:
                return
            self.update.emit(
                    _('Searching in')+' '+force_unicode(dirpath[0],
                        filesystem_encoding))
            self.books += list(self.db.find_books_in_directory(dirpath[0],
                                            self.single_book_per_directory))

    def extract(self):
        if self.path.lower().endswith('.zip'):
            from calibre.utils.zipfile import ZipFile
            try:
                with ZipFile(self.path) as zf:
                    zf.extractall(self.tdir)
            except Exception:
                prints('Corrupt ZIP file, trying to use local headers')
                from calibre.utils.localunzip import extractall
                extractall(self.path, self.tdir)
        elif self.path.lower().endswith('.rar'):
            from calibre.utils.unrar import extract
            extract(self.path, self.tdir)
        else:
            raise ValueError('Can only process ZIP or RAR archives')

    def run(self):
        if self.tdir is not None:
            try:
                self.extract()
            except Exception as err:
                import traceback
                traceback.print_exc()
                msg = as_unicode(err)
                self.found.emit(msg)
                return
            self.path = self.tdir

        root = os.path.abspath(self.path)
        try:
            self.walk(root)
        except:
            try:
                if isinstance(root, unicode):
                    root = root.encode(filesystem_encoding)
                self.walk(root)
            except Exception as err:
                import traceback
                traceback.print_exc()
                msg = as_unicode(err)
                self.found.emit(msg)
                return

        self.books = [formats for formats in self.books if formats]

        if not self.canceled:
            self.found.emit(self.books)

# }}}

class DBAdder(QObject):  # {{{

    def __init__(self, parent, db, ids, nmap):
        QObject.__init__(self, parent)

        self.db, self.ids, self.nmap = db, dict(**ids), dict(**nmap)
        self.critical = {}
        self.number_of_books_added = 0
        self.duplicates = []
        self.names, self.paths, self.infos = [], [], []
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.merged_books = set([])
        self.auto_convert_books = set()

    def end(self):
        if (gprefs['manual_add_auto_convert'] and
                self.auto_convert_books):
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            gui.iactions['Convert Books'].auto_convert_auto_add(
                self.auto_convert_books)

        self.input_queue.put((None, None, None))

    def start(self):
        try:
            id, opf, cover = self.input_queue.get_nowait()
        except Empty:
            single_shot(self.start)
            return
        if id is None and opf is None and cover is None:
            return
        name = self.nmap.pop(id)
        title = None
        if DEBUG:
            st = time.time()
        try:
            title = self.add(id, opf, cover, name)
        except:
            import traceback
            self.critical[name] = traceback.format_exc()
            title = name
        self.output_queue.put(title)
        if DEBUG:
            prints('Added', title, 'to db in:', time.time() - st, 'seconds')
        single_shot(self.start)

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
            formats = [f2 for f2 in formats if not f2.lower().endswith('.opf')]
            if prefs['add_formats_to_existing']:  # automerge is on
                identical_book_list = self.db.find_identical_books(mi)
                if identical_book_list:  # books with same author and nearly same title exist in db
                    self.merged_books.add((mi.title, ' & '.join(mi.authors)))
                    seen_fmts = set([])

                    for identical_book in identical_book_list:
                        ib_fmts = self.db.formats(identical_book, index_is_id=True)
                        if ib_fmts:
                            seen_fmts |= set(ib_fmts.split(','))
                        replace = gprefs['automerge'] == 'overwrite'
                        self.add_formats(identical_book, formats,
                                replace=replace)
                    if gprefs['automerge'] == 'new record':
                        incoming_fmts = \
                            set([os.path.splitext(path)[-1].replace('.',
                                '').upper() for path in formats])
                        if incoming_fmts.intersection(seen_fmts):
                            # There was at least one duplicate format
                            # so create a new record and put the
                            # incoming formats into it
                            # We should arguably put only the duplicate
                            # formats, but no real harm is done by having
                            # all formats
                            id_ = self.db.create_book_entry(mi, cover=cover,
                                    add_duplicates=True)
                            self.number_of_books_added += 1
                            self.add_formats(id_, formats)

                else:
                    # books with same author and nearly same title do not exist in db
                    id_ = self.db.create_book_entry(mi, cover=cover, add_duplicates=True)
                    self.number_of_books_added += 1
                    self.add_formats(id_, formats)

            else:  # automerge is off
                id_ = self.db.create_book_entry(mi, cover=cover, add_duplicates=False)
                if id_ is None:
                    self.duplicates.append((mi, cover, orig_formats))
                else:
                    self.add_formats(id_, formats)
                    self.auto_convert_books.add(id_)
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

class Adder(QObject):  # {{{

    ADD_TIMEOUT = 900  # seconds (15 minutes)

    def __init__(self, parent, db, callback, spare_server=None):
        QObject.__init__(self, parent)
        self.pd = ProgressDialog(_('Adding...'), parent=parent)
        self.pd.setMaximumWidth(min(600, int(available_width()*0.75)))
        self.spare_server = spare_server
        self.db = db
        self.pd.setModal(True)
        self.pd.show()
        self._parent = parent
        self.rfind = self.worker = None
        self.callback = callback
        self.callback_called = False
        self.pd.canceled_signal.connect(self.canceled)

    def add_recursive(self, root, single=True):
        if os.path.exists(root) and os.path.isfile(root) and root.lower().rpartition('.')[-1] in {'zip', 'rar'}:
            self.path = tdir = PersistentTemporaryDirectory('_arcv_')
        else:
            self.path = root
            tdir = None
        self.pd.set_msg(_('Searching in all sub-directories...'))
        self.pd.set_min(0)
        self.pd.set_max(0)
        self.pd.value = 0
        self.rfind = RecursiveFind(self, self.db, root, single, tdir=tdir)
        self.rfind.update.connect(self.pd.set_msg, type=Qt.QueuedConnection)
        self.rfind.found.connect(self.add, type=Qt.QueuedConnection)
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
        restricted = set()
        for i in xrange(len(books)):
            files = books[i]
            restrictedi = set(f for f in files if not os.access(f, os.R_OK))
            if restrictedi:
                files = [f for f in files if os.access(f, os.R_OK)]
                books[i] = files
            restricted |= restrictedi
        if restrictedi:
            det_msg = u'\n'.join(restrictedi)
            warning_dialog(self.pd, _('No permission'),
                    _('Cannot add some files as you do not have '
                        ' permission to access them. Click Show'
                        ' Details to see the list of such files.'),
                    det_msg=det_msg, show=True)
        books = list(filter(None, books))
        if not books:
            return self.canceled()
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
        self.db_adder = DBAdder(self, self.db, self.ids, self.nmap)
        self.db_adder.start()
        self.last_added_at = time.time()
        self.entry_count = len(self.ids)
        self.continue_updating = True
        single_shot(self.update)

    def canceled(self):
        self.continue_updating = False
        if self.rfind is not None:
            self.rfind.canceled = True
        if self.worker is not None:
            self.worker.canceled = True
        if hasattr(self, 'db_adder'):
            self.db_adder.end()
        self.pd.hide()
        if not self.callback_called:
            self.callback(self.paths, self.names, self.infos)
            self.callback_called = True

    def duplicates_processed(self):
        self.db_adder.end()
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
            self.db_adder.end()
            if not self.callback_called:
                self.callback([], [], [])
                self.callback_called = True
            error_dialog(self._parent, _('Adding failed'),
                    _('The add books process seems to have hung.'
                        ' Try restarting calibre and adding the '
                        'books in smaller increments, until you '
                        'find the problem book.'), show=True)

        if self.continue_updating:
            single_shot(self.update)

    def process_duplicates(self):
        duplicates = self.db_adder.duplicates
        if not duplicates:
            return self.duplicates_processed()
        self.pd.hide()
        from calibre.gui2.dialogs.duplicates import DuplicatesQuestion
        self.__d_q = d = DuplicatesQuestion(self.db, duplicates, self._parent)
        duplicates = tuple(d.duplicates)
        if duplicates:
            pd = QProgressDialog(_('Adding duplicates...'), '', 0, len(duplicates),
                    self._parent)
            pd.setCancelButton(None)
            pd.setValue(0)
            pd.show()
            self.__p_d = pd
            self.__d_a = DuplicatesAdder(self._parent, self.db, duplicates,
                    self.db_adder)
            self.__d_a.added.connect(pd.setValue)
            self.__d_a.adding_done.connect(self.duplicates_processed)
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
        self._parent = None
        self.pd.setParent(None)
        del self.pd
        self.pd = None
        if hasattr(self, 'db_adder'):
            self.db_adder.setParent(None)
            del self.db_adder
            self.db_adder = None

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

class Saver(QObject):  # {{{

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
        self.pd.set_msg(_('Collecting data, please wait...'))
        self._parent = parent
        self.callback = callback
        self.callback_called = False
        self.rq = Queue()
        self.ids = [x for x in map(db.id, [r.row() for r in rows]) if x is not None]
        self.pd_max = len(self.ids)
        self.pd.set_max(0)
        self.pd.value = 0
        self.failures = set([])

        from calibre.ebooks.metadata.worker import SaveWorker
        self.worker = SaveWorker(self.rq, db, self.ids, path, self.opts,
                spare_server=self.spare_server)
        self.pd.canceled_signal.connect(self.canceled)
        self.continue_updating = True
        single_shot(self.update)

    def canceled(self):
        self.continue_updating = False
        if self.worker is not None:
            self.worker.canceled = True
        self.pd.hide()
        if not self.callback_called:
            self.callback(self.worker.path, self.failures, self.worker.error)
            self.callback_called = True

    def update(self):
        if not self.continue_updating:
            return
        if not self.worker.is_alive():
            # Check that all ids were processed
            while self.ids:
                # Get all queued results since worker is dead
                before = len(self.ids)
                self.get_result()
                if before == len(self.ids):
                    # No results available => worker died unexpectedly
                    for i in list(self.ids):
                        self.failures.add(('id:%d'%i, 'Unknown error'))
                        self.ids.remove(i)

        if not self.ids:
            self.continue_updating = False
            self.pd.hide()
            if not self.callback_called:
                try:
                    # Give the worker time to clean up and set worker.error
                    self.worker.join(2)
                except:
                    pass  # The worker was not yet started
                self.callback_called = True
                self.callback(self.worker.path, self.failures, self.worker.error)

        if self.continue_updating:
            self.get_result()
            single_shot(self.update)

    def get_result(self):
        try:
            id, title, ok, tb = self.rq.get_nowait()
        except Empty:
            return
        if self.pd.max != self.pd_max:
            self.pd.max = self.pd_max
        self.pd.value += 1
        self.ids.remove(id)
        if not isinstance(title, unicode):
            title = str(title).decode(preferred_encoding, 'replace')
        self.pd.set_msg(_('Saved')+' '+title)

        if not ok:
            self.failures.add((title, tb))
# }}}


