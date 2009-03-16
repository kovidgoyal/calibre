'''
UI for adding books to the database
'''
import os

from PyQt4.Qt import QThread, SIGNAL, QMutex, QWaitCondition, Qt

from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.constants import preferred_encoding
from calibre.gui2.widgets import WarningDialog

class Add(QThread):
    
    def __init__(self):
        QThread.__init__(self)
        self._lock = QMutex()
        self._waiting = QWaitCondition()
    
    def is_canceled(self):
        if self.pd.canceled:
            self.canceled = True
        return self.canceled
    
    def wait_for_condition(self):
        self._lock.lock()
        self._waiting.wait(self._lock)
        self._lock.unlock()
        
    def wake_up(self):
        self._waiting.wakeAll()
 
class AddFiles(Add):
    
    def __init__(self, paths, default_thumbnail, get_metadata, db=None):
        Add.__init__(self)
        self.paths = paths
        self.get_metadata = get_metadata
        self.default_thumbnail = default_thumbnail
        self.db = db
        self.formats, self.metadata, self.names, self.infos = [], [], [], []
        self.duplicates = []
        self.number_of_books_added = 0
        self.connect(self.get_metadata, 
                     SIGNAL('metadata(PyQt_PyObject, PyQt_PyObject)'),
                     self.metadata_delivered)
    
    def metadata_delivered(self, id, mi):
        if self.is_canceled():
            self.wake_up()
            return
        if not mi.title:
            mi.title = os.path.splitext(self.names[id])[0]
        mi.title = mi.title if isinstance(mi.title, unicode) else \
                   mi.title.decode(preferred_encoding, 'replace')
        self.metadata.append(mi)
        self.infos.append({'title':mi.title, 
                           'authors':', '.join(mi.authors),
                           'cover':self.default_thumbnail, 'tags':[]})
        if self.db is not None:
            duplicates, num = self.db.add_books(self.paths[id:id+1], 
                                self.formats[id:id+1], [mi], 
                                add_duplicates=False)
            self.number_of_books_added += num
            if duplicates:
                if not self.duplicates:
                    self.duplicates = [[], [], [], []]
                for i in range(4):
                    self.duplicates[i] += duplicates[i]
        self.emit(SIGNAL('processed(PyQt_PyObject,PyQt_PyObject)'), 
                      mi.title, id)
        self.wake_up()
    
    def create_progress_dialog(self, title, msg, parent):
        self._parent = parent
        self.pd = ProgressDialog(title, msg, -1, len(self.paths)-1, parent)
        self.connect(self, SIGNAL('processed(PyQt_PyObject,PyQt_PyObject)'),
                     self.update_progress_dialog)
        self.pd.setModal(True)
        self.pd.show()
        self.connect(self, SIGNAL('finished()'), self.pd.hide)
        return self.pd
        
       
    def update_progress_dialog(self, title, count):
        self.pd.set_value(count)
        if self.db is not None:
            self.pd.set_msg(_('Added %s to library')%title)
        else:
            self.pd.set_msg(_('Read metadata from ')+title)
        
        
    def run(self):
        try:
            self.canceled = False
            for c, book in enumerate(self.paths):
                if self.pd.canceled:
                    self.canceled = True
                    break
                format = os.path.splitext(book)[1]
                format = format[1:] if format else None
                stream = open(book, 'rb')
                self.formats.append(format)
                self.names.append(os.path.basename(book))
                self.get_metadata(c, stream, stream_type=format, 
                                      use_libprs_metadata=True)
                self.wait_for_condition()
        finally:
            self.disconnect(self.get_metadata, 
                            SIGNAL('metadata(PyQt_PyObject, PyQt_PyObject)'), 
                            self.metadata_delivered)
            self.get_metadata = None
        
                    
    def process_duplicates(self):
        if self.duplicates:
            files = _('<p>Books with the same title as the following already '
                      'exist in the database. Add them anyway?<ul>')
            for mi in self.duplicates[2]:
                files += '<li>'+mi.title+'</li>\n'
            d = WarningDialog (_('Duplicates found!'), 
                              _('Duplicates found!'), 
                              files+'</ul></p>', parent=self._parent)
            if d.exec_() == d.Accepted:
                num = self.db.add_books(*self.duplicates, 
                                  **dict(add_duplicates=True))[1]
                self.number_of_books_added += num
                
            
class AddRecursive(Add):
    
    def __init__(self, path, db, get_metadata, single_book_per_directory, parent):
        self.path = path
        self.db = db
        self.get_metadata = get_metadata
        self.single_book_per_directory = single_book_per_directory
        self.duplicates, self.books, self.metadata = [], [], []
        self.number_of_books_added = 0
        self.canceled = False
        Add.__init__(self)
        self.connect(self.get_metadata, 
                     SIGNAL('metadataf(PyQt_PyObject, PyQt_PyObject)'),
                     self.metadata_delivered, Qt.QueuedConnection)
        self.connect(self, SIGNAL('searching_done()'), self.searching_done,
                     Qt.QueuedConnection)    
        self._parent = parent
        self.pd = ProgressDialog(_('Adding books recursively...'),
                                 _('Searching for books in all sub-directories...'), 
                                 0, 0, parent)
        self.connect(self, SIGNAL('processed(PyQt_PyObject,PyQt_PyObject)'),
                     self.update_progress_dialog)
        self.connect(self, SIGNAL('update(PyQt_PyObject)'), self.pd.set_msg,
                     Qt.QueuedConnection)
        self.connect(self, SIGNAL('pupdate(PyQt_PyObject)'), self.pd.set_value,
                     Qt.QueuedConnection)
        self.pd.setModal(True)
        self.pd.show()
        self.connect(self, SIGNAL('finished()'), self.pd.hide)
        
    def update_progress_dialog(self, title, count):
        self.pd.set_value(count)
        if title:
            self.pd.set_msg(_('Read metadata from ')+title)
    
    def metadata_delivered(self, id, mi):
        if self.is_canceled():
            self.wake_up()
            return
        self.emit(SIGNAL('processed(PyQt_PyObject,PyQt_PyObject)'),
                          mi.title, id)
        self.metadata.append((mi if mi.title else None, self.books[id]))
        if len(self.metadata) >= len(self.books):
            self.metadata = [x for x in self.metadata if x[0] is not None]
            self.pd.set_min(-1)
            self.pd.set_max(len(self.metadata)-1)
            self.pd.set_value(-1)
            self.pd.set_msg(_('Adding books to database...'))
        self.wake_up()
    
    def searching_done(self):
        self.pd.set_min(-1)
        self.pd.set_max(len(self.books)-1)
        self.pd.set_value(-1)
        self.pd.set_msg(_('Reading metadata...'))
    
   
    def run(self):
        try:
            root = os.path.abspath(self.path)
            for dirpath in os.walk(root):
                if self.is_canceled():
                    return
                self.emit(SIGNAL('update(PyQt_PyObject)'), 
                          _('Searching in')+' '+dirpath[0])
                self.books += list(self.db.find_books_in_directory(dirpath[0], 
                                                self.single_book_per_directory))
            self.books = [formats for formats in self.books if formats]
            # Reset progress bar
            self.emit(SIGNAL('searching_done()'))
            
            for c, formats in enumerate(self.books):
                self.get_metadata.from_formats(c, formats)
                self.wait_for_condition()
                
            # Add books to database
            for c, x in enumerate(self.metadata):
                mi, formats = x
                if self.is_canceled():
                    break
                if self.db.has_book(mi):
                    self.duplicates.append((mi, formats))
                else:
                    self.db.import_book(mi, formats, notify=False)
                    self.number_of_books_added += 1
                self.emit(SIGNAL('pupdate(PyQt_PyObject)'), c)
        finally:
            self.disconnect(self.get_metadata, 
                            SIGNAL('metadataf(PyQt_PyObject, PyQt_PyObject)'), 
                            self.metadata_delivered)
            self.get_metadata = None
            
        
    def process_duplicates(self):
        if self.duplicates:
            files = _('<p>Books with the same title as the following already '
                      'exist in the database. Add them anyway?<ul>')
            for mi in self.duplicates:
                title = mi[0].title
                if not isinstance(title, unicode):
                    title = title.decode(preferred_encoding, 'replace')
                files += '<li>'+title+'</li>\n'
            d = WarningDialog (_('Duplicates found!'), 
                              _('Duplicates found!'), 
                              files+'</ul></p>', parent=self._parent)
            if d.exec_() == d.Accepted:
                for mi, formats in self.duplicates:
                    self.db.import_book(mi, formats, notify=False)
                    self.number_of_books_added += 1
        
        