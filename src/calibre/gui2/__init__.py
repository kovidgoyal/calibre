__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" The GUI """
import os, sys, Queue, threading, glob
from threading import RLock
from urllib import unquote
from PyQt4.Qt import (QVariant, QFileInfo, QObject, QBuffer, Qt,
                    QByteArray, QTranslator, QCoreApplication, QThread,
                    QEvent, QTimer, pyqtSignal, QDateTime, QDesktopServices,
                    QFileDialog, QFileIconProvider, QSettings, QColor,
                    QIcon, QApplication, QDialog, QUrl, QFont, QPalette,
                    QFontDatabase, QLocale)

ORG_NAME = 'KovidsBrain'
APP_UID  = 'libprs500'
from calibre import prints
from calibre.constants import (islinux, iswindows, isbsd, isfrozen, isosx,
        plugins, config_dir, filesystem_encoding, DEBUG)
from calibre.utils.config import Config, ConfigProxy, dynamic, JSONConfig
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.date import UNDEFINED_DATE
from calibre.utils.localization import get_lang
from calibre.utils.filenames import expanduser

# Setup gprefs {{{
gprefs = JSONConfig('gui')
defs = gprefs.defaults

if isosx:
    defs['action-layout-menubar'] = (
        'Add Books', 'Edit Metadata', 'Convert Books',
        'Choose Library', 'Save To Disk', 'Preferences',
        'Help',
        )
    defs['action-layout-menubar-device'] = (
        'Add Books', 'Edit Metadata', 'Convert Books',
        'Location Manager', 'Send To Device',
        'Save To Disk', 'Preferences', 'Help',
        )
    defs['action-layout-toolbar'] = (
        'Add Books', 'Edit Metadata', None, 'Convert Books', 'View', None,
        'Choose Library', 'Donate', None, 'Fetch News', 'Store', 'Save To Disk',
        'Connect Share', None, 'Remove Books', 'Tweak ePub'
        )
    defs['action-layout-toolbar-device'] = (
        'Add Books', 'Edit Metadata', None, 'Convert Books', 'View',
        'Send To Device', None, None, 'Location Manager', None, None,
        'Fetch News', 'Store', 'Save To Disk', 'Connect Share', None,
        'Remove Books',
        )
else:
    defs['action-layout-menubar'] = ()
    defs['action-layout-menubar-device'] = ()
    defs['action-layout-toolbar'] = (
        'Add Books', 'Edit Metadata', None, 'Convert Books', 'View', None,
        'Store', 'Donate', 'Fetch News', 'Help', None,
        'Remove Books', 'Choose Library', 'Save To Disk',
        'Connect Share', 'Tweak ePub', 'Preferences',
        )
    defs['action-layout-toolbar-device'] = (
        'Add Books', 'Edit Metadata', None, 'Convert Books', 'View',
        'Send To Device', None, None, 'Location Manager', None, None,
        'Fetch News', 'Save To Disk', 'Store', 'Connect Share', None,
        'Remove Books', None, 'Help', 'Preferences',
        )

defs['action-layout-toolbar-child'] = ()

defs['action-layout-context-menu'] = (
        'Edit Metadata', 'Send To Device', 'Save To Disk',
        'Connect Share', 'Copy To Library', None,
        'Convert Books', 'View', 'Open Folder', 'Show Book Details',
        'Similar Books', 'Tweak ePub', None, 'Remove Books',
        )

defs['action-layout-context-menu-device'] = (
        'View', 'Save To Disk', None, 'Remove Books', None,
        'Add To Library', 'Edit Collections', 'Match Books'
        )

defs['action-layout-context-menu-cover-browser'] = (
        'Edit Metadata', 'Send To Device', 'Save To Disk',
        'Connect Share', 'Copy To Library', None,
        'Convert Books', 'View', 'Open Folder', 'Show Book Details',
        'Similar Books', 'Tweak ePub', None, 'Remove Books',
        )

defs['show_splash_screen'] = True
defs['toolbar_icon_size'] = 'medium'
defs['automerge'] = 'ignore'
defs['toolbar_text'] = 'always'
defs['font'] = None
defs['tags_browser_partition_method'] = 'first letter'
defs['tags_browser_collapse_at'] = 100
defs['tag_browser_dont_collapse'] = []
defs['edit_metadata_single_layout'] = 'default'
defs['default_author_link'] = 'https://en.wikipedia.org/w/index.php?search={author}'
defs['preserve_date_on_ctl'] = True
defs['manual_add_auto_convert'] = False
defs['cb_fullscreen'] = False
defs['worker_max_time'] = 0
defs['show_files_after_save'] = True
defs['auto_add_path'] = None
defs['auto_add_check_for_duplicates'] = False
defs['blocked_auto_formats'] = []
defs['auto_add_auto_convert'] = True
defs['auto_add_everything'] = False
defs['ui_style'] = 'calibre' if iswindows or isosx else 'system'
defs['tag_browser_old_look'] = False
defs['book_list_tooltips'] = True
defs['bd_show_cover'] = True
defs['bd_overlay_cover_size'] = False
defs['tags_browser_category_icons'] = {}
defs['cover_browser_reflections'] = True
defs['extra_row_spacing'] = 0
defs['refresh_book_list_on_bulk_edit'] = True
defs['cover_grid_width'] = 0
defs['cover_grid_height'] = 0
defs['cover_grid_spacing'] = 0
defs['cover_grid_color'] = (80, 80, 80)
defs['cover_grid_cache_size'] = 100
defs['cover_grid_disk_cache_size'] = 2500
defs['cover_grid_show_title'] = False
defs['cover_grid_texture'] = None
defs['show_vl_tabs'] = False
defs['show_highlight_toggle_button'] = False
defs['add_comments_to_email'] = False
defs['cb_preserve_aspect_ratio'] = False
defs['show_rating_in_cover_browser'] = True
defs['gpm_template_editor_font_size'] = 10
del defs
# }}}

NONE = QVariant()  # : Null value to return from the data function of item models
UNDEFINED_QDATETIME = QDateTime(UNDEFINED_DATE)

ALL_COLUMNS = ['title', 'ondevice', 'authors', 'size', 'timestamp', 'rating', 'publisher',
        'tags', 'series', 'pubdate']

def _config():  # {{{
    c = Config('gui', 'preferences for the calibre GUI')
    c.add_opt('send_to_storage_card_by_default', default=False,
              help=_('Send file to storage card instead of main memory by default'))
    c.add_opt('confirm_delete', default=False,
              help=_('Confirm before deleting'))
    c.add_opt('main_window_geometry', default=None,
              help=_('Main window geometry'))  # value QVariant.toByteArray
    c.add_opt('new_version_notification', default=True,
              help=_('Notify when a new version is available'))
    c.add_opt('use_roman_numerals_for_series_number', default=True,
              help=_('Use Roman numerals for series number'))
    c.add_opt('sort_tags_by', default='name',
              help=_('Sort tags list by name, popularity, or rating'))
    c.add_opt('match_tags_type', default='any',
              help=_('Match tags by any or all.'))
    c.add_opt('cover_flow_queue_length', default=6,
              help=_('Number of covers to show in the cover browsing mode'))
    c.add_opt('LRF_conversion_defaults', default=[],
              help=_('Defaults for conversion to LRF'))
    c.add_opt('LRF_ebook_viewer_options', default=None,
              help=_('Options for the LRF ebook viewer'))
    c.add_opt('internally_viewed_formats', default=['LRF', 'EPUB', 'LIT',
        'MOBI', 'PRC', 'POBI', 'AZW', 'AZW3', 'HTML', 'FB2', 'PDB', 'RB',
        'SNB', 'HTMLZ', 'KEPUB'], help=_(
            'Formats that are viewed using the internal viewer'))
    c.add_opt('column_map', default=ALL_COLUMNS,
              help=_('Columns to be displayed in the book list'))
    c.add_opt('autolaunch_server', default=False, help=_('Automatically launch content server on application startup'))
    c.add_opt('oldest_news', default=60, help=_('Oldest news kept in database'))
    c.add_opt('systray_icon', default=False, help=_('Show system tray icon'))
    c.add_opt('upload_news_to_device', default=True,
              help=_('Upload downloaded news to device'))
    c.add_opt('delete_news_from_library_on_upload', default=False,
              help=_('Delete news books from library after uploading to device'))
    c.add_opt('separate_cover_flow', default=False,
              help=_('Show the cover flow in a separate window instead of in the main calibre window'))
    c.add_opt('disable_tray_notification', default=False,
              help=_('Disable notifications from the system tray icon'))
    c.add_opt('default_send_to_device_action', default=None,
            help=_('Default action to perform when send to device button is '
                'clicked'))
    c.add_opt('asked_library_thing_password', default=False,
            help='Asked library thing password at least once.')
    c.add_opt('search_as_you_type', default=False,
            help=_('Start searching as you type. If this is disabled then search will '
            'only take place when the Enter or Return key is pressed.'))
    c.add_opt('highlight_search_matches', default=False,
            help=_('When searching, show all books with search results '
            'highlighted instead of showing only the matches. You can use the '
            'N or F3 keys to go to the next match.'))
    c.add_opt('save_to_disk_template_history', default=[],
        help='Previously used Save to Disk templates')
    c.add_opt('send_to_device_template_history', default=[],
        help='Previously used Send to Device templates')
    c.add_opt('main_search_history', default=[],
        help='Search history for the main GUI')
    c.add_opt('viewer_search_history', default=[],
        help='Search history for the ebook viewer')
    c.add_opt('lrf_viewer_search_history', default=[],
        help='Search history for the LRF viewer')
    c.add_opt('scheduler_search_history', default=[],
        help='Search history for the recipe scheduler')
    c.add_opt('plugin_search_history', default=[],
        help='Search history for the plugin preferences')
    c.add_opt('shortcuts_search_history', default=[],
        help='Search history for the keyboard preferences')
    c.add_opt('jobs_search_history', default=[],
        help='Search history for the tweaks preferences')
    c.add_opt('tweaks_search_history', default=[],
        help='Search history for tweaks')
    c.add_opt('worker_limit', default=6,
            help=_(
        'Maximum number of simultaneous conversion/news download jobs. '
        'This number is twice the actual value for historical reasons.'))
    c.add_opt('get_social_metadata', default=True,
            help=_('Download social metadata (tags/rating/etc.)'))
    c.add_opt('overwrite_author_title_metadata', default=True,
            help=_('Overwrite author and title with new metadata'))
    c.add_opt('auto_download_cover', default=False,
            help=_('Automatically download the cover, if available'))
    c.add_opt('enforce_cpu_limit', default=True,
            help=_('Limit max simultaneous jobs to number of CPUs'))
    c.add_opt('gui_layout', choices=['wide', 'narrow'],
            help=_('The layout of the user interface. Wide has the '
                'book details panel on the right and narrow has '
                'it at the bottom.'), default='wide')
    c.add_opt('show_avg_rating', default=True,
            help=_('Show the average rating per item indication in the tag browser'))
    c.add_opt('disable_animations', default=False,
            help=_('Disable UI animations'))

    # This option is no longer used. It remains for compatibility with upgrades
    # so the value can be migrated
    c.add_opt('tag_browser_hidden_categories', default=set(),
            help=_('tag browser categories not to display'))

    c.add_opt
    return ConfigProxy(c)

config = _config()
# }}}

QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, config_dir)
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope,
        config_dir)
QSettings.setDefaultFormat(QSettings.IniFormat)

# Turn off DeprecationWarnings in windows GUI
if iswindows:
    import warnings
    warnings.simplefilter('ignore', DeprecationWarning)

def available_heights():
    desktop  = QCoreApplication.instance().desktop()
    return map(lambda x: x.height(), map(desktop.availableGeometry, range(desktop.numScreens())))

def available_height():
    desktop  = QCoreApplication.instance().desktop()
    return desktop.availableGeometry().height()

def max_available_height():
    return max(available_heights())

def min_available_height():
    return min(available_heights())

def available_width():
    desktop       = QCoreApplication.instance().desktop()
    return desktop.availableGeometry().width()

def get_windows_color_depth():
    import win32gui, win32con, win32print
    hwin = win32gui.GetDesktopWindow()
    hwindc = win32gui.GetWindowDC(hwin)
    ans = win32print.GetDeviceCaps(hwindc, win32con.BITSPIXEL)
    win32gui.ReleaseDC(hwin, hwindc)
    return ans

def get_screen_dpi():
    d = QApplication.desktop()
    return (d.logicalDpiX(), d.logicalDpiY())

_is_widescreen = None

def is_widescreen():
    global _is_widescreen
    if _is_widescreen is None:
        try:
            _is_widescreen = float(available_width())/available_height() > 1.4
        except:
            _is_widescreen = False
    return _is_widescreen

def extension(path):
    return os.path.splitext(path)[1][1:].lower()


def warning_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    from calibre.gui2.dialogs.message_box import MessageBox
    d = MessageBox(MessageBox.WARNING, _('WARNING:')+ ' ' +
            title, msg, det_msg, parent=parent,
            show_copy_button=show_copy_button)
    if show:
        return d.exec_()
    return d

def error_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    from calibre.gui2.dialogs.message_box import MessageBox
    d = MessageBox(MessageBox.ERROR, _('ERROR:')+ ' ' +
            title, msg, det_msg, parent=parent,
                    show_copy_button=show_copy_button)
    if show:
        return d.exec_()
    return d

def question_dialog(parent, title, msg, det_msg='', show_copy_button=False,
        default_yes=True,
        # Skippable dialogs
        # Set skip_dialog_name to a unique name for this dialog
        # Set skip_dialog_msg to a message displayed to the user
        skip_dialog_name=None, skip_dialog_msg=_('Show this confirmation again'),
        skip_dialog_skipped_value=True, skip_dialog_skip_precheck=True,
        # Override icon (QIcon to be used as the icon for this dialog)
        override_icon=None):
    from calibre.gui2.dialogs.message_box import MessageBox

    auto_skip = set(gprefs.get('questions_to_auto_skip', []))
    if (skip_dialog_name is not None and skip_dialog_name in auto_skip):
        return bool(skip_dialog_skipped_value)

    d = MessageBox(MessageBox.QUESTION, title, msg, det_msg, parent=parent,
                    show_copy_button=show_copy_button, default_yes=default_yes,
                    q_icon=override_icon)

    if skip_dialog_name is not None and skip_dialog_msg:
        tc = d.toggle_checkbox
        tc.setVisible(True)
        tc.setText(skip_dialog_msg)
        tc.setChecked(bool(skip_dialog_skip_precheck))

    ret = d.exec_() == d.Accepted

    if skip_dialog_name is not None and not d.toggle_checkbox.isChecked():
        auto_skip.add(skip_dialog_name)
        gprefs.set('questions_to_auto_skip', list(auto_skip))

    return ret

def info_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    from calibre.gui2.dialogs.message_box import MessageBox
    d = MessageBox(MessageBox.INFO, title, msg, det_msg, parent=parent,
                    show_copy_button=show_copy_button)

    if show:
        return d.exec_()
    return d

def show_restart_warning(msg, parent=None):
    d = warning_dialog(parent, _('Restart needed'), msg,
            show_copy_button=False)
    b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
    b.setIcon(QIcon(I('lt.png')))
    d.do_restart = False
    def rf():
        d.do_restart = True
    b.clicked.connect(rf)
    d.set_details('')
    d.exec_()
    b.clicked.disconnect()
    return d.do_restart


class Dispatcher(QObject):
    '''
    Convenience class to use Qt signals with arbitrary python callables.
    By default, ensures that a function call always happens in the
    thread this Dispatcher was created in.

    Note that if you create the Dispatcher in a thread without an event loop of
    its own, the function call will happen in the GUI thread (I think).
    '''
    dispatch_signal = pyqtSignal(object, object)

    def __init__(self, func, queued=True, parent=None):
        QObject.__init__(self, parent)
        self.func = func
        typ = Qt.QueuedConnection
        if not queued:
            typ = Qt.AutoConnection if queued is None else Qt.DirectConnection
        self.dispatch_signal.connect(self.dispatch, type=typ)

    def __call__(self, *args, **kwargs):
        self.dispatch_signal.emit(args, kwargs)

    def dispatch(self, args, kwargs):
        self.func(*args, **kwargs)

class FunctionDispatcher(QObject):
    '''
    Convenience class to use Qt signals with arbitrary python functions.
    By default, ensures that a function call always happens in the
    thread this FunctionDispatcher was created in.

    Note that you must create FunctionDispatcher objects in the GUI thread.
    '''
    dispatch_signal = pyqtSignal(object, object, object)

    def __init__(self, func, queued=True, parent=None):
        global gui_thread
        if gui_thread is None:
            gui_thread = QThread.currentThread()
        if not is_gui_thread():
            raise ValueError(
                'You can only create a FunctionDispatcher in the GUI thread')

        QObject.__init__(self, parent)
        self.func = func
        typ = Qt.QueuedConnection
        if not queued:
            typ = Qt.AutoConnection if queued is None else Qt.DirectConnection
        self.dispatch_signal.connect(self.dispatch, type=typ)
        self.q = Queue.Queue()
        self.lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        if is_gui_thread():
            return self.func(*args, **kwargs)
        with self.lock:
            self.dispatch_signal.emit(self.q, args, kwargs)
            res = self.q.get()
        return res

    def dispatch(self, q, args, kwargs):
        try:
            res = self.func(*args, **kwargs)
        except:
            res = None
        q.put(res)

class GetMetadata(QObject):
    '''
    Convenience class to ensure that metadata readers are used only in the
    GUI thread. Must be instantiated in the GUI thread.
    '''

    edispatch = pyqtSignal(object, object, object)
    idispatch = pyqtSignal(object, object, object)
    metadataf = pyqtSignal(object, object)
    metadata  = pyqtSignal(object, object)

    def __init__(self):
        QObject.__init__(self)
        self.edispatch.connect(self._get_metadata, type=Qt.QueuedConnection)
        self.idispatch.connect(self._from_formats, type=Qt.QueuedConnection)

    def __call__(self, id, *args, **kwargs):
        self.edispatch.emit(id, args, kwargs)

    def from_formats(self, id, *args, **kwargs):
        self.idispatch.emit(id, args, kwargs)

    def _from_formats(self, id, args, kwargs):
        from calibre.ebooks.metadata.meta import metadata_from_formats
        try:
            mi = metadata_from_formats(*args, **kwargs)
        except:
            mi = MetaInformation('', [_('Unknown')])
        self.metadataf.emit(id, mi)

    def _get_metadata(self, id, args, kwargs):
        from calibre.ebooks.metadata.meta import get_metadata
        try:
            mi = get_metadata(*args, **kwargs)
        except:
            mi = MetaInformation('', [_('Unknown')])
        self.metadata.emit(id, mi)

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
             'cbz'     : 'cbz',
             'cbr'     : 'cbr',
             'svg'     : 'svg',
             'html'    : 'html',
             'htmlz'   : 'html',
             'htm'     : 'html',
             'xhtml'   : 'html',
             'xhtm'    : 'html',
             'lit'     : 'lit',
             'lrf'     : 'lrf',
             'lrx'     : 'lrx',
             'pdf'     : 'pdf',
             'pdr'     : 'zero',
             'rar'     : 'rar',
             'zip'     : 'zip',
             'txt'     : 'txt',
             'text'    : 'txt',
             'prc'     : 'mobi',
             'azw'     : 'mobi',
             'mobi'    : 'mobi',
             'pobi'    : 'mobi',
             'mbp'     : 'zero',
             'azw1'    : 'tpz',
             'azw2'    : 'azw2',
             'azw3'    : 'azw3',
             'azw4'    : 'pdf',
             'tpz'     : 'tpz',
             'tan'     : 'zero',
             'epub'    : 'epub',
             'fb2'     : 'fb2',
             'rtf'     : 'rtf',
             'odt'     : 'odt',
             'snb'     : 'snb',
             'djv'     : 'djvu',
             'djvu'    : 'djvu',
             'xps'     : 'xps',
             'oxps'    : 'xps',
             'docx'    : 'docx',
             'opml'    : 'opml',
             }

    def __init__(self):
        QFileIconProvider.__init__(self)
        self.icons = {}
        for key in self.__class__.ICONS.keys():
            self.icons[key] = I('mimetypes/')+self.__class__.ICONS[key]+'.png'
        self.icons['calibre'] = I('lt.png')
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
        key = self.key_from_ext(ext.lower() if ext else '')
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
            ext = unicode(fileinfo.completeSuffix()).lower()
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
    initialize_file_icon_provider()
    return _file_icon_provider

def select_initial_dir(q):
    while q:
        c = os.path.dirname(q)
        if c == q:
            break
        if os.path.exists(c):
            return c
        q = c
    return expanduser(u'~')

class FileDialog(QObject):
    def __init__(self, title=_('Choose Files'),
                       filters=[],
                       add_all_files_filter=True,
                       parent=None,
                       modal=True,
                       name='',
                       mode=QFileDialog.ExistingFiles,
                       default_dir=u'~',
                       no_save_dir=False,
                       combine_file_and_saved_dir=False
                       ):
        QObject.__init__(self)
        ftext = ''
        if filters:
            for filter in filters:
                text, extensions = filter
                extensions = ['*'+(i if i.startswith('.') else '.'+i) for i in
                        extensions]
                ftext += '%s (%s);;'%(text, ' '.join(extensions))
        if add_all_files_filter or not ftext:
            ftext += 'All files (*)'
        if ftext.endswith(';;'):
            ftext = ftext[:-2]

        self.dialog_name = name if name else 'dialog_' + title
        self.selected_files = None
        self.fd = None

        if combine_file_and_saved_dir:
            bn = os.path.basename(default_dir)
            prev = dynamic.get(self.dialog_name,
                    expanduser(u'~'))
            if os.path.exists(prev):
                if os.path.isfile(prev):
                    prev = os.path.dirname(prev)
            else:
                prev = expanduser(u'~')
            initial_dir = os.path.join(prev, bn)
        elif no_save_dir:
            initial_dir = expanduser(default_dir)
        else:
            initial_dir = dynamic.get(self.dialog_name,
                    expanduser(default_dir))
        if not isinstance(initial_dir, basestring):
            initial_dir = expanduser(default_dir)
        if not initial_dir or (not os.path.exists(initial_dir) and not (
                mode == QFileDialog.AnyFile and (no_save_dir or combine_file_and_saved_dir))):
            initial_dir = select_initial_dir(initial_dir)
        self.selected_files = []
        use_native_dialog = 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ
        with SanitizeLibraryPath():
            opts = QFileDialog.Option()
            if not use_native_dialog:
                opts |= QFileDialog.DontUseNativeDialog
            if mode == QFileDialog.AnyFile:
                f = unicode(QFileDialog.getSaveFileName(parent, title,
                    initial_dir, ftext, "", opts))
                if f:
                    self.selected_files.append(f)
            elif mode == QFileDialog.ExistingFile:
                f = unicode(QFileDialog.getOpenFileName(parent, title,
                    initial_dir, ftext, "", opts))
                if f and os.path.exists(f):
                    self.selected_files.append(f)
            elif mode == QFileDialog.ExistingFiles:
                fs = QFileDialog.getOpenFileNames(parent, title, initial_dir,
                        ftext, "", opts)
                for f in fs:
                    f = unicode(f)
                    if not f:
                        continue
                    if not os.path.exists(f):
                        # QFileDialog for some reason quotes spaces
                        # on linux if there is more than one space in a row
                        f = unquote(f)
                    if f and os.path.exists(f):
                        self.selected_files.append(f)
            else:
                if mode == QFileDialog.Directory:
                    opts |= QFileDialog.ShowDirsOnly
                f = unicode(QFileDialog.getExistingDirectory(parent, title, initial_dir, opts))
                if os.path.exists(f):
                    self.selected_files.append(f)
        if self.selected_files:
            self.selected_files = [unicode(q) for q in self.selected_files]
            saved_loc = self.selected_files[0]
            if os.path.isfile(saved_loc):
                saved_loc = os.path.dirname(saved_loc)
            if not no_save_dir:
                dynamic[self.dialog_name] = saved_loc
        self.accepted = bool(self.selected_files)

    def get_files(self):
        if self.selected_files is None:
            return tuple(os.path.abspath(unicode(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)


def choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    fd = FileDialog(title=title, filters=[], add_all_files_filter=False,
            parent=window, name=name, mode=QFileDialog.Directory,
            default_dir=default_dir, no_save_dir=no_save_dir)
    dir = fd.get_files()
    fd.setParent(None)
    if dir:
        return dir[0]

def choose_osx_app(window, name, title, default_dir='/Applications'):
    fd = FileDialog(title=title, parent=window, name=name, mode=QFileDialog.ExistingFile,
            default_dir=default_dir)
    app = fd.get_files()
    fd.setParent(None)
    if app:
        return app

def choose_files(window, name, title,
                 filters=[], all_files=True, select_only_single_file=False):
    '''
    Ask user to choose a bunch of files.
    :param name: Unique dialog name used to store the opened directory
    :param title: Title to show in dialogs titlebar
    :param filters: list of allowable extensions. Each element of the list
                    must be a 2-tuple with first element a string describing
                    the type of files to be filtered and second element a list
                    of extensions.
    :param all_files: If True add All files to filters.
    :param select_only_single_file: If True only one file can be selected
    '''
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name, filters=filters,
                    parent=window, add_all_files_filter=all_files, mode=mode,
                    )
    fd.setParent(None)
    if fd.accepted:
        return fd.get_files()
    return None

def choose_save_file(window, name, title, filters=[], all_files=True, initial_path=None, initial_filename=None):
    '''
    Ask user to choose a file to save to. Can be a non-existent file.
    :param filters: list of allowable extensions. Each element of the list
                     must be a 2-tuple with first element a string describing
                     the type of files to be filtered and second element a list
                     of extensions.
    :param all_files: If True add All files to filters.
    :param initial_path: The initially selected path (does not need to exist). Cannot be used with initial_filename.
    :param initial_filename: If specified, the initially selected path is this filename in the previously used directory. Cannot be used with initial_path.
    '''
    kwargs = dict(title=title, name=name, filters=filters,
                    parent=window, add_all_files_filter=all_files, mode=QFileDialog.AnyFile)
    if initial_path is not None:
        kwargs['no_save_dir'] = True
        kwargs['default_dir'] = initial_path
    elif initial_filename is not None:
        kwargs['combine_file_and_saved_dir'] = True
        kwargs['default_dir'] = initial_filename
    fd = FileDialog(**kwargs)
    fd.setParent(None)
    ans = None
    if fd.accepted:
        ans = fd.get_files()
        if ans:
            ans = ans[0]
    return ans

def choose_images(window, name, title, select_only_single_file=True,
                  formats=('png', 'gif', 'jpg', 'jpeg', 'svg')):
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name,
                    filters=[('Images', list(formats))],
                    parent=window, add_all_files_filter=False, mode=mode,
                    )
    fd.setParent(None)
    if fd.accepted:
        return fd.get_files()
    return None

def pixmap_to_data(pixmap, format='JPEG', quality=90):
    '''
    Return the QPixmap pixmap as a string saved in the specified format.
    '''
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, format, quality=quality)
    return bytes(ba.data())

def decouple(prefix):
    ' Ensure that config files used by utility code are not the same as those used by the main calibre GUI '
    dynamic.decouple(prefix)
    from calibre.gui2.widgets import history
    history.decouple(prefix)

class ResizableDialog(QDialog):

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = geom.height()-25, geom.width()-10
        if nh < 0:
            nh = max(800, self.height())
        if nw < 0:
            nw = max(600, self.height())
        nh = min(self.height(), nh)
        nw = min(self.width(), nw)
        self.resize(nw, nh)

class Translator(QTranslator):
    '''
    Translator to load translations for strings in Qt from the calibre
    translations. Does not support advanced features of Qt like disambiguation
    and plural forms.
    '''

    def translate(self, *args, **kwargs):
        try:
            src = unicode(args[1])
        except:
            return u''
        t = _
        return t(src)


gui_thread = None

qt_app = None

def load_builtin_fonts():
    global _rating_font
    # Load the builtin fonts and any fonts added to calibre by the user to
    # Qt
    for ff in glob.glob(P('fonts/liberation/*.?tf')) + \
            [P('fonts/calibreSymbols.otf')] + \
            glob.glob(os.path.join(config_dir, 'fonts', '*.?tf')):
        if ff.rpartition('.')[-1].lower() in {'ttf', 'otf'}:
            with open(ff, 'rb') as s:
                # Windows requires font files to be executable for them to be
                # loaded successfully, so we use the in memory loader
                fid = QFontDatabase.addApplicationFontFromData(s.read())
                if fid > -1:
                    fam = QFontDatabase.applicationFontFamilies(fid)
                    fam = set(map(unicode, fam))
                    if u'calibre Symbols' in fam:
                        _rating_font = u'calibre Symbols'

def setup_gui_option_parser(parser):
    if islinux:
        parser.add_option('--detach', default=False, action='store_true',
                          help='Detach from the controlling terminal, if any (linux only)')

def detach_gui():
    if islinux and not DEBUG:
        # Detach from the controlling process.
        if os.fork() != 0:
            raise SystemExit(0)
        os.setsid()
        so, se = file(os.devnull, 'a+'), file(os.devnull, 'a+', 0)
        os.dup2(so.fileno(), sys.__stdout__.fileno())
        os.dup2(se.fileno(), sys.__stderr__.fileno())

class Application(QApplication):

    def __init__(self, args, force_calibre_style=False,
            override_program_name=None):
        self.file_event_hook = None
        if override_program_name:
            args = [override_program_name] + args[1:]
        qargs = [i.encode('utf-8') if isinstance(i, unicode) else i for i in args]
        self.pi = plugins['progress_indicator'][0]
        if DEBUG:
            self.redirect_notify = True
        QApplication.__init__(self, qargs)
        dl = QLocale(get_lang())
        if unicode(dl.bcp47Name()) != u'C':
            QLocale.setDefault(dl)
        global gui_thread, qt_app
        gui_thread = QThread.currentThread()
        self._translator = None
        self.load_translations()
        qt_app = self
        self._file_open_paths = []
        self._file_open_lock = RLock()
        self.setup_styles(force_calibre_style)
    if DEBUG:
        def notify(self, receiver, event):
            if self.redirect_notify:
                self.redirect_notify = False
                return self.pi.do_notify(receiver, event)
            else:
                ret = QApplication.notify(self, receiver, event)
                self.redirect_notify = True
                return ret

    def load_builtin_fonts(self, scan_for_fonts=False):
        if scan_for_fonts:
            from calibre.utils.fonts.scanner import font_scanner
            # Start scanning the users computer for fonts
            font_scanner

        load_builtin_fonts()

    def load_calibre_style(self):
        # On OS X QtCurve resets the palette, so we preserve it explicitly
        orig_pal = QPalette(self.palette())

        path = os.path.join(sys.extensions_location, 'calibre_style.'+(
            'pyd' if iswindows else 'so'))
        if not self.pi.load_style(path, 'Calibre'):
            prints('Failed to load calibre style')
        # On OSX, on some machines, colors can be invalid. See https://bugs.launchpad.net/bugs/1014900
        for role in (orig_pal.Button, orig_pal.Window):
            c = orig_pal.brush(role).color()
            if not c.isValid() or not c.toRgb().isValid():
                orig_pal.setColor(role, QColor(u'lightgray'))

        self.setPalette(orig_pal)
        style = self.style()
        icon_map = {}
        pcache = {}
        for k, v in {
            'DialogYesButton': u'ok.png',
            'DialogNoButton': u'window-close.png',
            'DialogCloseButton': u'window-close.png',
            'DialogOkButton': u'ok.png',
            'DialogCancelButton': u'window-close.png',
            'DialogHelpButton': u'help.png',
            'DialogOpenButton': u'document_open.png',
            'DialogSaveButton': u'save.png',
            'DialogApplyButton': u'ok.png',
            'DialogDiscardButton': u'trash.png',
            'MessageBoxInformation': u'dialog_information.png',
            'MessageBoxWarning': u'dialog_warning.png',
            'MessageBoxCritical': u'dialog_error.png',
            'MessageBoxQuestion': u'dialog_question.png',
            'BrowserReload': u'view-refresh.png',
            # These two are used to calculate the sizes for the doc widget
            # title bar buttons, therefore, they have to exist. The actual
            # icon is not used.
            'TitleBarCloseButton': u'window-close.png',
            'TitleBarNormalButton': u'window-close.png',
            'DockWidgetCloseButton': u'window-close.png',
        }.iteritems():
            if v not in pcache:
                p = I(v)
                if isinstance(p, bytes):
                    p = p.decode(filesystem_encoding)
                # if not os.path.exists(p): raise ValueError(p)
                pcache[v] = p
            v = pcache[v]
            icon_map[type('')(getattr(style, 'SP_'+k))] = v
        style.setProperty(u'calibre_icon_map', icon_map)
        self.__icon_map_memory_ = icon_map

    def setup_styles(self, force_calibre_style):
        self.original_font = QFont(QApplication.font())
        fi = gprefs['font']
        if fi is not None:
            font = QFont(*(fi[:4]))
            s = gprefs.get('font_stretch', None)
            if s is not None:
                font.setStretch(s)
            QApplication.setFont(font)

        depth_ok = True
        if iswindows:
            # There are some people that still run 16 bit winxp installs. The
            # new style does not render well on 16bit machines.
            try:
                depth_ok = get_windows_color_depth() >= 32
            except:
                import traceback
                traceback.print_exc()
            if not depth_ok:
                prints('Color depth is less than 32 bits disabling modern look')

        if force_calibre_style or (depth_ok and gprefs['ui_style'] !=
                'system'):
            self.load_calibre_style()
        else:
            st = self.style()
            if st is not None:
                st = unicode(st.objectName()).lower()
            if (islinux or isbsd) and st in ('windows', 'motif', 'cde'):
                from PyQt4.Qt import QStyleFactory
                styles = set(map(unicode, QStyleFactory.keys()))
                if os.environ.get('KDE_FULL_SESSION', False):
                    self.load_calibre_style()
                elif 'Cleanlooks' in styles:
                    self.setStyle('Cleanlooks')

    def _send_file_open_events(self):
        with self._file_open_lock:
            if self._file_open_paths:
                self.file_event_hook(self._file_open_paths)
                self._file_open_paths = []

    def load_translations(self):
        if self._translator is not None:
            self.removeTranslator(self._translator)
        self._translator = Translator(self)
        self.installTranslator(self._translator)

    def event(self, e):
        if callable(self.file_event_hook) and e.type() == QEvent.FileOpen:
            path = unicode(e.file())
            if os.access(path, os.R_OK):
                with self._file_open_lock:
                    self._file_open_paths.append(path)
                QTimer.singleShot(1000, self._send_file_open_events)
            return True
        else:
            return QApplication.event(self, e)

_store_app = None

class SanitizeLibraryPath(object):
    '''Remove the bundled calibre libraries from LD_LIBRARY_PATH on linux. This
    is needed to prevent library conflicts when launching external utilities.'''

    def __enter__(self):
        self.orig = os.environ.get('LD_LIBRARY_PATH', '')
        self.changed = False
        paths = [x for x in self.orig.split(os.pathsep) if x]
        if isfrozen and islinux and paths:
            npaths = [x for x in paths if x != sys.frozen_path+'/lib']
            os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(npaths)
            self.changed = True

    def __exit__(self, *args):
        if self.changed:
            os.environ['LD_LIBRARY_PATH'] = self.orig

def open_url(qurl):
    if isinstance(qurl, basestring):
        qurl = QUrl(qurl)
    with SanitizeLibraryPath():
        QDesktopServices.openUrl(qurl)

def get_current_db():
    '''
    This method will try to return the current database in use by the user as
    efficiently as possible, i.e. without constructing duplicate
    LibraryDatabase objects.
    '''
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    if gui is not None and gui.current_db is not None:
        return gui.current_db
    from calibre.library import db
    return db()

def open_local_file(path):
    if iswindows:
        os.startfile(os.path.normpath(path))
    else:
        url = QUrl.fromLocalFile(path)
        open_url(url)

def must_use_qt():
    global gui_thread, _store_app
    if (islinux or isbsd) and ':' not in os.environ.get('DISPLAY', ''):
        raise RuntimeError('X server required. If you are running on a'
                ' headless machine, use xvfb')
    if _store_app is None and QApplication.instance() is None:
        _store_app = QApplication([])
    if gui_thread is None:
        gui_thread = QThread.currentThread()
    if gui_thread is not QThread.currentThread():
        raise RuntimeError('Cannot use Qt in non GUI thread')

def is_ok_to_use_qt():
    try:
        must_use_qt()
    except RuntimeError:
        return False
    return True

def is_gui_thread():
    global gui_thread
    return gui_thread is QThread.currentThread()

_rating_font = 'Arial Unicode MS' if iswindows else 'sans-serif'
def rating_font():
    global _rating_font
    return _rating_font

def elided_text(text, font=None, width=300, pos='middle'):
    ''' Return a version of text that is no wider than width pixels when
    rendered, replacing characters from the left, middle or right (as per pos)
    of the string with an ellipsis. Results in a string much closer to the
    limit than Qt's elidedText().'''
    from PyQt4.Qt import QFontMetrics, QApplication
    fm = QApplication.fontMetrics() if font is None else QFontMetrics(font)
    delta = 4
    ellipsis = u'\u2026'

    def remove_middle(x):
        mid = len(x) // 2
        return x[:max(0, mid - (delta//2))] + ellipsis + x[mid + (delta//2):]

    chomp = {'middle':remove_middle, 'left':lambda x:(ellipsis + x[delta:]), 'right':lambda x:(x[:-delta] + ellipsis)}[pos]
    while len(text) > delta and fm.width(text) > width:
        text = chomp(text)
    return unicode(text)

def find_forms(srcdir):
    base = os.path.join(srcdir, 'calibre', 'gui2')
    forms = []
    for root, _, files in os.walk(base):
        for name in files:
            if name.endswith('.ui'):
                forms.append(os.path.abspath(os.path.join(root, name)))

    return forms

def form_to_compiled_form(form):
    return form.rpartition('.')[0]+'_ui.py'

def build_forms(srcdir, info=None, summary=False):
    import re, cStringIO
    from PyQt4.uic import compileUi
    forms = find_forms(srcdir)
    if info is None:
        from calibre import prints
        info = prints
    pat = re.compile(r'''(['"]):/images/([^'"]+)\1''')
    def sub(match):
        ans = 'I(%s%s%s)'%(match.group(1), match.group(2), match.group(1))
        return ans

    num = 0
    for form in forms:
        compiled_form = form_to_compiled_form(form)
        if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
            if not summary:
                info('\tCompiling form', form)
            buf = cStringIO.StringIO()
            compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('import images_rc', '')
            dat = re.sub(r'^ {4}def _translate\(context, text, disambig\):\s+return.*$', '    pass', dat,
                         flags=re.M)
            dat = re.compile(r'(?:QtGui.QApplication.translate|(?<!def )_translate)\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
            dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')
            dat = dat.replace('_("d MMM yyyy")', '"d MMM yyyy"')
            dat = pat.sub(sub, dat)
            dat = dat.replace('from QtWebKit.QWebView import QWebView',
                    'from PyQt4 import QtWebKit\nfrom PyQt4.QtWebKit import QWebView')

            open(compiled_form, 'wb').write(dat)
            num += 1
    if num:
        info('Compiled %d forms' % num)

_df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
if _df and os.path.exists(_df):
    build_forms(_df)


