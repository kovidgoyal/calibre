__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" The GUI """
import sys, os, re, StringIO, traceback
from PyQt4.QtCore import QVariant, QFileInfo, QObject, SIGNAL, QBuffer, \
                         QByteArray, QLocale, QTranslator, QUrl
from PyQt4.QtGui import QFileDialog, QMessageBox, QPixmap, QFileIconProvider, \
                        QIcon, QTableView

ORG_NAME = 'KovidsBrain'
APP_UID  = 'libprs500'
from calibre import __author__, islinux, iswindows, Settings

NONE = QVariant() #: Null value to return from the data function of item models


# Turn off DeprecationWarnings in windows GUI
if iswindows:
    import warnings
    warnings.simplefilter('ignore', DeprecationWarning)


def extension(path):
    return os.path.splitext(path)[1][1:].lower()

def warning_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Warning, 'WARNING: '+title, msg, QMessageBox.Ok,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
    return d

def error_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Critical, 'ERROR: '+title, msg, QMessageBox.Ok,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_error.svg'))
    return d

def question_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Question, title, msg, QMessageBox.Yes|QMessageBox.No,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_information.svg'))
    return d

def info_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Information, title, msg, QMessageBox.NoButton,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_information.svg'))
    return d

def qstring_to_unicode(q):
    return unicode(q)

def human_readable(size):
    """ Convert a size in bytes into a human readable form """
    if size < 1024: 
        divisor, suffix = 1, "B"
    elif size < 1024*1024: 
        divisor, suffix = 1024., "KB"
    elif size < 1024*1024*1024: 
        divisor, suffix = 1024*1024, "MB"
    elif size < 1024*1024*1024*1024: 
        divisor, suffix = 1024*1024*1024, "GB"
    size = str(float(size)/divisor)
    if size.find(".") > -1: 
        size = size[:size.find(".")+2]
    return size + " " + suffix


class TableView(QTableView):
    def __init__(self, parent):
        QTableView.__init__(self, parent)
        self.read_settings()
        
    
    def read_settings(self):
        self.cw = str(Settings().value(self.__class__.__name__ + ' column widths', QVariant('')).toString())
        try:
            self.cw = tuple(int(i) for i in self.cw.split(','))
        except ValueError:
            self.cw = None
    
    def write_settings(self):
        settings = Settings()
        settings.setValue(self.__class__.__name__ + ' column widths',
                          QVariant(','.join(str(self.columnWidth(i))
                             for i in range(self.model().columnCount(None)))))
    
    def restore_column_widths(self):
        if self.cw and len(self.cw):
            for i in range(len(self.cw)):
                self.setColumnWidth(i, self.cw[i])
            return True
        
    def set_visible_columns(self, cols=None):
        '''
        @param cols: A list of booleans or None. If an entry is False the corresponding column
        is hidden, if True it is shown. 
        '''
        if cols:
            Settings().setValue(self.__class__.__name__ + ' visible columns',
                             QVariant(repr(cols)))
        else:
            cols = qstring_to_unicode(Settings().value(self.__class__.__name__ + ' visible columns', 
                                        QVariant('')).toString())
            if cols:
                cols = eval(cols)
            else:
                cols = [True for i in range(self.model().columnCount(self))]
        
        for i in range(len(cols)):
            hidden = self.isColumnHidden(i)
            self.setColumnHidden(i, not cols[i])
            if hidden and cols[i]:
                self.resizeColumnToContents(i)
    

class FileIconProvider(QFileIconProvider):
    
    ICONS = {
             'default' : 'unknown',
             'dir'     : 'dir',
             'zero'    : 'zero',
             
             'jpeg'    : 'jpeg',
             'jpg'     : 'jpeg',
             'gif'     : 'gif',
             'png'     : 'png',
             'bmp'     : 'bmp',
             'svg'     : 'svg',
             'html'    : 'html',
             'htm'     : 'html',
             'xhtml'   : 'html',
             'xhtm'    : 'html',
             'lit'     : 'lit',
             'lrf'     : 'lrf',
             'lrx'     : 'lrx',
             'pdf'     : 'pdf',
             'rar'     : 'rar',
             'zip'     : 'zip',
             'txt'     : 'txt',
             'prc'     : 'mobi',
             'azw'     : 'mobi',
             'mobi'    : 'mobi',
             }
    
    def __init__(self):
        QFileIconProvider.__init__(self)
        self.icons = {}
        for key in self.__class__.ICONS.keys():
            self.icons[key] = ':/images/mimetypes/'+self.__class__.ICONS[key]+'.svg'
        for i in ('dir', 'default', 'zero'):
            self.icons[i] = QIcon(self.icons[i])
    
    def key_from_ext(self, ext):
        key = ext if ext in self.icons.keys() else 'default'
        if key == 'default' and ext.count('.') > 0:
            ext = ext.rpartition('.')[2]
            key = ext if ext in self.icons.keys() else 'default'
        return key
    
    def cached_icon(self, key):
        candidate = self.icons[key]
        if isinstance(candidate, QIcon):
            return candidate
        icon = QIcon(candidate)
        self.icons[key] = icon
        return icon
    
    def icon_from_ext(self, ext):
        key = self.key_from_ext(ext)
        return self.cached_icon(key)
    
    def load_icon(self, fileinfo):
        key = 'default'
        icons = self.icons
        if fileinfo.isSymLink():
            if not fileinfo.exists():
                return icons['zero']
            fileinfo = QFileInfo(fileinfo.readLink())
        if fileinfo.isDir():
            key = 'dir'
        else:
            ext = qstring_to_unicode(fileinfo.completeSuffix()).lower()
            key = self.key_from_ext(ext)
        return self.cached_icon(key)
    
    def icon(self, arg):
        if isinstance(arg, QFileInfo):
            return self.load_icon(arg)
        if arg == QFileIconProvider.Folder:
            return self.icons['dir']
        if arg == QFileIconProvider.File:
            return self.icons['default']
        return QFileIconProvider.icon(self, arg)
        
_file_icon_provider = None
def initialize_file_icon_provider():
    global _file_icon_provider
    if _file_icon_provider is None:
        _file_icon_provider = FileIconProvider()
        
def file_icon_provider():
    global _file_icon_provider
    return _file_icon_provider

_sidebar_directories = []
def set_sidebar_directories(dirs):
    global _sidebar_directories
    if dirs is None:
        dirs = Settings().value('frequently used directories', QVariant([])).toStringList()        
    _sidebar_directories = [QUrl.fromLocalFile(i) for i in dirs]
        
class FileDialog(QObject):
    def __init__(self, title='Choose Files', 
                       filters=[],
                       add_all_files_filter=True, 
                       parent=None,
                       modal = True,
                       name = '',
                       mode = QFileDialog.ExistingFiles,
                       ):
        QObject.__init__(self)
        initialize_file_icon_provider()
        ftext = ''
        if filters:
            for filter in filters:
                text, extensions = filter
                extensions = ['*.'+i if not i.startswith('.') else i for i in extensions]
                ftext += '%s (%s);;'%(text, ' '.join(extensions))
        if add_all_files_filter or not ftext:
            ftext += 'All files (*)'
        
        settings = Settings()
        self.dialog_name = name if name else 'dialog_' + title
        self.selected_files = None
        self.fd = None
        if islinux:
            self.fd = QFileDialog(parent)
            self.fd.setFileMode(mode)  
            self.fd.setIconProvider(_file_icon_provider)
            self.fd.setModal(modal)            
            self.fd.setFilter(ftext)
            self.fd.setWindowTitle(title)
            state = settings.value(name, QVariant()).toByteArray()
            if not self.fd.restoreState(state):
                self.fd.setDirectory(os.path.expanduser('~'))
            osu = [i for i in self.fd.sidebarUrls()]
            self.fd.setSidebarUrls(osu + _sidebar_directories)
            QObject.connect(self.fd, SIGNAL('accepted()'), self.save_dir)
            self.accepted = self.fd.exec_() == QFileDialog.Accepted
        else:
            dir = settings.value(self.dialog_name, QVariant(os.path.expanduser('~'))).toString()
            self.selected_files = []
            if mode == QFileDialog.AnyFile:
                f = qstring_to_unicode(
                    QFileDialog.getSaveFileName(parent, title, dir, ftext, ""))
                if os.path.exists(f):
                    self.selected_files.append(f)                
            elif mode == QFileDialog.ExistingFile:
                f = qstring_to_unicode(
                    QFileDialog.getOpenFileName(parent, title, dir, ftext, ""))
                if os.path.exists(f):
                    self.selected_files.append(f)
            elif mode == QFileDialog.ExistingFiles:
                fs = QFileDialog.getOpenFileNames(parent, title, dir, ftext, "")
                for f in fs:
                    if os.path.exists(qstring_to_unicode(f)):
                        self.selected_files.append(f)
            else:
                opts = QFileDialog.ShowDirsOnly if mode == QFileDialog.DirectoryOnly else QFileDialog.Option()
                f = qstring_to_unicode(
                        QFileDialog.getExistingDirectory(parent, title, dir, opts))
                if os.path.exists(f):
                    self.selected_files.append(f)
            if self.selected_files:
                self.selected_files = [qstring_to_unicode(q) for q in self.selected_files]
                settings.setValue(self.dialog_name, QVariant(os.path.dirname(self.selected_files[0])))
            self.accepted = bool(self.selected_files)        
        
        
    
    def get_files(self): 
        if self.selected_files is None:       
            return tuple(os.path.abspath(qstring_to_unicode(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)
    
    def save_dir(self):
        if self.fd:
            settings = Settings()
            settings.setValue(self.dialog_name, QVariant(self.fd.saveState()))
        

def choose_dir(window, name, title):
    fd = FileDialog(title, [], False, window, name=name, 
                    mode=QFileDialog.DirectoryOnly)
    dir = fd.get_files()
    if dir:
        return dir[0]

def choose_files(window, name, title,  
                 filters=[], all_files=True, select_only_single_file=False):
    '''
    Ask user to choose a bunch of files.
    @param name: Unique dialog name used to store the opened directory
    @param title: Title to show in dialogs titlebar
    @param filters: list of allowable extensions. Each element of the list
                     must be a 2-tuple with first element a string describing 
                     the type of files to be filtered and second element a list
                     of extensions. 
    @param all_files: If True add All files to filters.
    @param select_only_single_file: If True only one file can be selected  
    '''
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name, filters=filters, 
                    parent=window, add_all_files_filter=all_files, mode=mode,
                    )
    if fd.accepted:
        return fd.get_files()
    return None

def choose_images(window, name, title, select_only_single_file=True):
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name, 
                    filters=[('Images', ['png', 'gif', 'jpeg', 'jpg', 'svg'])], 
                    parent=window, add_all_files_filter=False, mode=mode,
                    )
    if fd.accepted:
        return fd.get_files()
    return None

def pixmap_to_data(pixmap, format='JPEG'):
    '''
    Return the QPixmap pixmap as a string saved in the specified format.
    '''
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, format)
    return str(ba.data())
