__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" The GUI """
import os, sys, Queue, threading, glob, signal
from contextlib import contextmanager
from threading import RLock, Lock
from urllib import unquote
from PyQt5.QtWidgets import QStyle  # Gives a nicer error message than import from Qt
from PyQt5.Qt import (
    QFileInfo, QObject, QBuffer, Qt, QByteArray, QTranslator, QSocketNotifier,
    QCoreApplication, QThread, QEvent, QTimer, pyqtSignal, QDateTime, QFontMetrics,
    QDesktopServices, QFileDialog, QFileIconProvider, QSettings, QIcon, QStringListModel,
    QApplication, QDialog, QUrl, QFont, QFontDatabase, QLocale, QFontInfo)

from calibre import prints
from calibre.constants import (islinux, iswindows, isbsd, isfrozen, isosx,
        plugins, config_dir, filesystem_encoding, isxp, DEBUG, __version__, __appname__ as APP_UID)
from calibre.ptempfile import base_dir
from calibre.utils.config import Config, ConfigProxy, dynamic, JSONConfig
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.date import UNDEFINED_DATE
from calibre.utils.localization import get_lang
from calibre.utils.filenames import expanduser
from calibre.utils.file_type_icons import EXT_MAP

try:
    NO_URL_FORMATTING = QUrl.None_
except AttributeError:
    NO_URL_FORMATTING = QUrl.None

# Setup gprefs {{{
gprefs = JSONConfig('gui')


native_menubar_defaults = {
    'action-layout-menubar': (
        'Add Books', 'Edit Metadata', 'Convert Books',
        'Choose Library', 'Save To Disk', 'Preferences',
        'Help',
        ),
    'action-layout-menubar-device': (
        'Add Books', 'Edit Metadata', 'Convert Books',
        'Location Manager', 'Send To Device',
        'Save To Disk', 'Preferences', 'Help',
        )
}


def create_defs():
    defs = gprefs.defaults
    if isosx:
        defs['action-layout-menubar'] = native_menubar_defaults['action-layout-menubar']
        defs['action-layout-menubar-device'] = native_menubar_defaults['action-layout-menubar-device']
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
    defs['auto_convert_same_fmt'] = False
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
    defs['tag_browser_hide_empty_categories'] = False
    defs['book_list_tooltips'] = True
    defs['bd_show_cover'] = True
    defs['bd_overlay_cover_size'] = False
    defs['tags_browser_category_icons'] = {}
    defs['cover_browser_reflections'] = True
    defs['book_list_extra_row_spacing'] = 0
    defs['refresh_book_list_on_bulk_edit'] = True
    defs['cover_grid_width'] = 0
    defs['cover_grid_height'] = 0
    defs['cover_grid_spacing'] = 0
    defs['cover_grid_color'] = (80, 80, 80)
    defs['cover_grid_cache_size_multiple'] = 5
    defs['cover_grid_disk_cache_size'] = 2500
    defs['cover_grid_show_title'] = False
    defs['cover_grid_texture'] = None
    defs['show_vl_tabs'] = False
    defs['show_highlight_toggle_button'] = False
    defs['add_comments_to_email'] = False
    defs['cb_preserve_aspect_ratio'] = False
    defs['gpm_template_editor_font_size'] = 10
    defs['show_emblems'] = False
    defs['emblem_size'] = 32
    defs['emblem_position'] = 'left'
    defs['metadata_diff_mark_rejected'] = False
    defs['tag_browser_show_counts'] = True
    defs['row_numbers_in_book_list'] = True


create_defs()
del create_defs
# }}}

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
              help=_('Main window geometry'))
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
              help=_('Options for the LRF e-book viewer'))
    c.add_opt('internally_viewed_formats', default=['LRF', 'EPUB', 'LIT',
        'MOBI', 'PRC', 'POBI', 'AZW', 'AZW3', 'HTML', 'FB2', 'PDB', 'RB',
        'SNB', 'HTMLZ', 'KEPUB'], help=_(
            'Formats that are viewed using the internal viewer'))
    c.add_opt('column_map', default=ALL_COLUMNS,
              help=_('Columns to be displayed in the book list'))
    c.add_opt('autolaunch_server', default=False, help=_('Automatically launch Content server on application startup'))
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
            help=_('Default action to perform when the "Send to device" button is '
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
        help='Search history for the e-book viewer')
    c.add_opt('viewer_toc_search_history', default=[],
        help='Search history for the ToC in the e-book viewer')
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
                'Book details panel on the right and narrow has '
                'it at the bottom.'), default='wide')
    c.add_opt('show_avg_rating', default=True,
            help=_('Show the average rating per item indication in the Tag browser'))
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
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, config_dir)
QSettings.setDefaultFormat(QSettings.IniFormat)


def available_heights():
    desktop  = QCoreApplication.instance().desktop()
    return map(lambda x: x.height(), map(desktop.availableGeometry, range(desktop.screenCount())))


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
        # Override icon (QIcon to be used as the icon for this dialog or string for I())
        override_icon=None,
        # Change the text/icons of the yes and no buttons.
        # The icons must be QIcon objects or strings for I()
        yes_text=None, no_text=None, yes_icon=None, no_icon=None,
    ):
    from calibre.gui2.dialogs.message_box import MessageBox

    auto_skip = set(gprefs.get('questions_to_auto_skip', []))
    if (skip_dialog_name is not None and skip_dialog_name in auto_skip):
        return bool(skip_dialog_skipped_value)

    d = MessageBox(MessageBox.QUESTION, title, msg, det_msg, parent=parent,
                   show_copy_button=show_copy_button, default_yes=default_yes,
                   q_icon=override_icon, yes_text=yes_text, no_text=no_text,
                   yes_icon=yes_icon, no_icon=no_icon)

    if skip_dialog_name is not None and skip_dialog_msg:
        tc = d.toggle_checkbox
        tc.setVisible(True)
        tc.setText(skip_dialog_msg)
        tc.setChecked(bool(skip_dialog_skip_precheck))
        d.resize_needed.emit()

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
    b = d.bb.addButton(_('&Restart calibre now'), d.bb.AcceptRole)
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

    ICONS = EXT_MAP

    def __init__(self):
        QFileIconProvider.__init__(self)
        upath, bpath = I('mimetypes'), I('mimetypes', allow_user_override=False)
        if upath != bpath:
            # User has chosen to override mimetype icons
            path_map = {v:I('mimetypes/%s.png' % v) for v in set(self.ICONS.itervalues())}
            icons = self.ICONS.copy()
            for uicon in glob.glob(os.path.join(upath, '*.png')):
                ukey = os.path.basename(uicon).rpartition('.')[0].lower()
                if ukey not in path_map:
                    path_map[ukey] = uicon
                    icons[ukey] = ukey
        else:
            path_map = {v:os.path.join(bpath, v + '.png') for v in set(self.ICONS.itervalues())}
            icons = self.ICONS
        self.icons = {k:path_map[v] for k, v in icons.iteritems()}
        self.icons['calibre'] = I('lt.png', allow_user_override=False)
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
        with sanitize_env_vars():
            opts = QFileDialog.Option()
            if not use_native_dialog:
                opts |= QFileDialog.DontUseNativeDialog
            if mode == QFileDialog.AnyFile:
                f = QFileDialog.getSaveFileName(parent, title,
                    initial_dir, ftext, "", opts)
                if f and f[0]:
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.ExistingFile:
                f = QFileDialog.getOpenFileName(parent, title,
                    initial_dir, ftext, "", opts)
                if f and f[0] and os.path.exists(f[0]):
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.ExistingFiles:
                fs = QFileDialog.getOpenFileNames(parent, title, initial_dir,
                        ftext, "", opts)
                if fs and fs[0]:
                    for f in fs[0]:
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


has_windows_file_dialog_helper = False
if iswindows and 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ:
    from calibre.gui2.win_file_dialogs import is_ok as has_windows_file_dialog_helper
    has_windows_file_dialog_helper = has_windows_file_dialog_helper()
if has_windows_file_dialog_helper:
    from calibre.gui2.win_file_dialogs import choose_files, choose_images, choose_dir, choose_save_file
else:

    def choose_dir(window, name, title, default_dir='~', no_save_dir=False):
        fd = FileDialog(title=title, filters=[], add_all_files_filter=False,
                parent=window, name=name, mode=QFileDialog.Directory,
                default_dir=default_dir, no_save_dir=no_save_dir)
        dir = fd.get_files()
        fd.setParent(None)
        if dir:
            return dir[0]

    def choose_files(window, name, title,
                    filters=[], all_files=True, select_only_single_file=False, default_dir=u'~'):
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
        fd = FileDialog(title=title, name=name, filters=filters, default_dir=default_dir,
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

    def choose_images(window, name, title, select_only_single_file=True, formats=None):
        mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
        if formats is None:
            from calibre.gui2.dnd import image_extensions
            formats = image_extensions()
        fd = FileDialog(title=title, name=name,
                        filters=[(_('Images'), list(formats))],
                        parent=window, add_all_files_filter=False, mode=mode,
                        )
        fd.setParent(None)
        if fd.accepted:
            return fd.get_files()
        return None


def choose_osx_app(window, name, title, default_dir='/Applications'):
    fd = FileDialog(title=title, parent=window, name=name, mode=QFileDialog.ExistingFile,
            default_dir=default_dir)
    app = fd.get_files()
    fd.setParent(None)
    if app:
        return app


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


_gui_prefs = gprefs


def gui_prefs():
    return _gui_prefs


def set_gui_prefs(prefs):
    global _gui_prefs
    _gui_prefs = prefs


class ResizableDialog(QDialog):

    # This class is present only for backwards compat with third party plugins
    # that might use it. Do not use it in new code.

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = max(550, geom.height()-25), max(700, geom.width()-10)
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

builtin_fonts_loaded = False


def load_builtin_fonts():
    global _rating_font, builtin_fonts_loaded
    # Load the builtin fonts and any fonts added to calibre by the user to
    # Qt
    if builtin_fonts_loaded:
        return
    builtin_fonts_loaded = True
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
                          help=_('Detach from the controlling terminal, if any (Linux only)'))


def show_temp_dir_error(err):
    import traceback
    extra = _('Click "Show details" for more information.')
    if 'CALIBRE_TEMP_DIR' in os.environ:
        extra = _('The %s environment variable is set. Try unsetting it.') % 'CALIBRE_TEMP_DIR'
    error_dialog(None, _('Could not create temporary directory'), _(
        'Could not create temporary directory, calibre cannot start.') + ' ' + extra, det_msg=traceback.format_exc(), show=True)


class Application(QApplication):

    shutdown_signal_received = pyqtSignal()

    def __init__(self, args, force_calibre_style=False, override_program_name=None, headless=False, color_prefs=gprefs):
        self.file_event_hook = None
        if override_program_name:
            args = [override_program_name] + args[1:]
        if headless:
            if not args:
                args = sys.argv[:1]
            args.extend(['-platformpluginpath', sys.extensions_location, '-platform', 'headless'])
        self.headless = headless
        qargs = [i.encode('utf-8') if isinstance(i, unicode) else i for i in args]
        self.pi = plugins['progress_indicator'][0]
        if not isosx and not headless and hasattr(Qt, 'AA_EnableHighDpiScaling'):
            # On OS X high dpi scaling is turned on automatically by the OS, so we dont need to set it explicitly
            # This requires Qt >= 5.6
            for v in ('QT_AUTO_SCREEN_SCALE_FACTOR', 'QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'QT_DEVICE_PIXEL_RATIO'):
                if os.environ.get(v):
                    break
            else:
                # Should probably make a preference to allow the user to
                # control this, if needed.
                # Could have options: auto, off, 1.25, 1.5, 1.75, 2, 2.25, 2.5
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setOrganizationName('calibre-ebook.com')
        QApplication.setOrganizationDomain(QApplication.organizationName())
        QApplication.setApplicationVersion(__version__)
        QApplication.setApplicationName(APP_UID)
        QApplication.__init__(self, qargs)
        self.setAttribute(Qt.AA_UseHighDpiPixmaps)
        try:
            base_dir()
        except EnvironmentError as err:
            if not headless:
                show_temp_dir_error(err)
            raise SystemExit('Failed to create temporary directory')
        if DEBUG and not headless:
            prints('devicePixelRatio:', self.devicePixelRatio())
            s = self.primaryScreen()
            if s:
                prints('logicalDpi:', s.logicalDotsPerInchX(), 'x', s.logicalDotsPerInchY())
                prints('physicalDpi:', s.physicalDotsPerInchX(), 'x', s.physicalDotsPerInchY())
        if not iswindows:
            self.setup_unix_signals()
        if islinux or isbsd:
            self.setAttribute(Qt.AA_DontUseNativeMenuBar, 'CALIBRE_NO_NATIVE_MENUBAR' in os.environ)
        self.setup_styles(force_calibre_style)
        f = QFont(QApplication.font())
        if (f.family(), f.pointSize()) == ('Sans Serif', 9):  # Hard coded Qt settings, no user preference detected
            f.setPointSize(10)
            QApplication.setFont(f)
        f = QFontInfo(f)
        self.original_font = (f.family(), f.pointSize(), f.weight(), f.italic(), 100)
        if not self.using_calibre_style and self.style().objectName() == 'fusion':
            # Since Qt is using the fusion style anyway, specialize it
            self.load_calibre_style()
        fi = gprefs['font']
        if fi is not None:
            font = QFont(*(fi[:4]))
            s = gprefs.get('font_stretch', None)
            if s is not None:
                font.setStretch(s)
            QApplication.setFont(font)
        self.line_height = max(12, QFontMetrics(self.font()).lineSpacing())

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

        if not isosx:
            # OS X uses a native color dialog that does not support custom
            # colors
            self.color_prefs = color_prefs
            self.read_custom_colors()
            self.lastWindowClosed.connect(self.save_custom_colors)

        if isxp:
            error_dialog(None, _('Windows XP not supported'), '<p>' + _(
                'calibre versions newer than 2.0 do not run on Windows XP. This is'
                ' because the graphics toolkit calibre uses (Qt 5) crashes a lot'
                ' on Windows XP. We suggest you stay with <a href="%s">calibre 1.48</a>'
                ' which works well on Windows XP.') % 'http://download.calibre-ebook.com/1.48.0/', show=True)
            raise SystemExit(1)

        if iswindows:
            # On windows the highlighted colors for inactive widgets are the
            # same as non highlighted colors. This is a regression from Qt 4.
            # https://bugreports.qt-project.org/browse/QTBUG-41060
            p = self.palette()
            for role in (p.Highlight, p.HighlightedText, p.Base, p.AlternateBase):
                p.setColor(p.Inactive, role, p.color(p.Active, role))
            self.setPalette(p)

            # Prevent text copied to the clipboard from being lost on quit due to
            # Qt 5 bug: https://bugreports.qt-project.org/browse/QTBUG-41125
            self.aboutToQuit.connect(self.flush_clipboard)

    def flush_clipboard(self):
        try:
            if self.clipboard().ownsClipboard():
                import ctypes
                ctypes.WinDLL('ole32.dll').OleFlushClipboard()
        except Exception:
            import traceback
            traceback.print_exc()

    def load_builtin_fonts(self, scan_for_fonts=False):
        if scan_for_fonts:
            from calibre.utils.fonts.scanner import font_scanner
            # Start scanning the users computer for fonts
            font_scanner

        load_builtin_fonts()

    def setup_styles(self, force_calibre_style):
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

        self.using_calibre_style = force_calibre_style or 'CALIBRE_IGNORE_SYSTEM_THEME' in os.environ or (
            depth_ok and gprefs['ui_style'] != 'system')
        if self.using_calibre_style:
            self.load_calibre_style()

    def load_calibre_style(self):
        icon_map = self.__icon_map_memory_ = {}
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
        }.iteritems():
            if v not in pcache:
                p = I(v)
                if isinstance(p, bytes):
                    p = p.decode(filesystem_encoding)
                # if not os.path.exists(p): raise ValueError(p)
                pcache[v] = p
            v = pcache[v]
            icon_map[getattr(QStyle, 'SP_'+k)] = v
        self.pi.load_style(icon_map)

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

    @dynamic_property
    def current_custom_colors(self):
        from PyQt5.Qt import QColorDialog, QColor

        def fget(self):
            return [col.getRgb() for col in
                    (QColorDialog.customColor(i) for i in xrange(QColorDialog.customCount()))]

        def fset(self, colors):
            num = min(len(colors), QColorDialog.customCount())
            for i in xrange(num):
                QColorDialog.setCustomColor(i, QColor(*colors[i]))
        return property(fget=fget, fset=fset)

    def read_custom_colors(self):
        colors = self.color_prefs.get('custom_colors_for_color_dialog', None)
        if colors is not None:
            self.current_custom_colors = colors

    def save_custom_colors(self):
        # Qt 5 regression, it no longer saves custom colors
        colors = self.current_custom_colors
        if colors != self.color_prefs.get('custom_colors_for_color_dialog', None):
            self.color_prefs.set('custom_colors_for_color_dialog', colors)

    def __enter__(self):
        self.setQuitOnLastWindowClosed(False)

    def __exit__(self, *args):
        self.setQuitOnLastWindowClosed(True)

    def setup_unix_signals(self):
        import fcntl
        read_fd, write_fd = os.pipe()
        cloexec_flag = getattr(fcntl, 'FD_CLOEXEC', 1)
        for fd in (read_fd, write_fd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            fcntl.fcntl(fd, fcntl.F_SETFD, flags | cloexec_flag | os.O_NONBLOCK)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda x, y: None)
            signal.siginterrupt(sig, False)
        signal.set_wakeup_fd(write_fd)
        self.signal_notifier = QSocketNotifier(read_fd, QSocketNotifier.Read, self)
        self.signal_notifier.setEnabled(True)
        self.signal_notifier.activated.connect(self.signal_received, type=Qt.QueuedConnection)

    def signal_received(self, read_fd):
        try:
            os.read(read_fd, 1024)
        except EnvironmentError:
            return
        self.shutdown_signal_received.emit()


_store_app = None


@contextmanager
def sanitize_env_vars():
    '''Unset various environment variables that calibre uses. This
    is needed to prevent library conflicts when launching external utilities.'''

    if islinux and isfrozen:
        env_vars = {'LD_LIBRARY_PATH':'/lib', 'QT_PLUGIN_PATH':'/lib/qt_plugins'}
    elif iswindows:
        env_vars = {k:None for k in 'QT_PLUGIN_PATH'.split()}
    elif isosx:
        env_vars = {k:None for k in (
                    'FONTCONFIG_FILE FONTCONFIG_PATH QT_PLUGIN_PATH SSL_CERT_FILE').split()}
    else:
        env_vars = {}

    originals = {x:os.environ.get(x, '') for x in env_vars}
    changed = {x:False for x in env_vars}
    for var, suffix in env_vars.iteritems():
        paths = [x for x in originals[var].split(os.pathsep) if x]
        npaths = [] if suffix is None else [x for x in paths if x != (sys.frozen_path + suffix)]
        if len(npaths) < len(paths):
            if npaths:
                os.environ[var] = os.pathsep.join(npaths)
            else:
                del os.environ[var]
            changed[var] = True

    try:
        yield
    finally:
        for var, orig in originals.iteritems():
            if changed[var]:
                if orig:
                    os.environ[var] = orig
                elif var in os.environ:
                    del os.environ[var]


SanitizeLibraryPath = sanitize_env_vars  # For old plugins


def open_url(qurl):
    # Qt 5 requires QApplication to be constructed before trying to use
    # QDesktopServices::openUrl()
    ensure_app()
    if isinstance(qurl, basestring):
        qurl = QUrl(qurl)
    with sanitize_env_vars():
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
        with sanitize_env_vars():
            os.startfile(os.path.normpath(path))
    else:
        url = QUrl.fromLocalFile(path)
        open_url(url)


_ea_lock = Lock()


def ensure_app(headless=True):
    global _store_app
    with _ea_lock:
        if _store_app is None and QApplication.instance() is None:
            args = sys.argv[:1]
            if headless and (islinux or isbsd):
                args += ['-platformpluginpath', sys.extensions_location, '-platform', 'headless']
            _store_app = QApplication(args)
            if headless and (islinux or isbsd):
                _store_app.headless = True
            import traceback
            # This is needed because as of PyQt 5.4 if sys.execpthook ==
            # sys.__excepthook__ PyQt will abort the application on an
            # unhandled python exception in a slot or virtual method. Since ensure_app()
            # is used in worker processes for background work like rendering html
            # or running a headless browser, we circumvent this as I really
            # dont feel like going through all the code and making sure no
            # unhandled exceptions ever occur. All the actual GUI apps already
            # override sys.except_hook with a proper error handler.

            def eh(t, v, tb):
                try:
                    traceback.print_exception(t, v, tb, file=sys.stderr)
                except:
                    pass
            sys.excepthook = eh


def app_is_headless():
    return getattr(_store_app, 'headless', False)


def must_use_qt(headless=True):
    ''' This function should be called if you want to use Qt for some non-GUI
    task like rendering HTML/SVG or using a headless browser. It will raise a
    RuntimeError if using Qt is not possible, which will happen if the current
    thread is not the main GUI thread. On linux, it uses a special QPA headless
    plugin, so that the X server does not need to be running. '''
    global gui_thread
    ensure_app(headless=headless)
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
    from PyQt5.Qt import QFontMetrics, QApplication
    fm = QApplication.fontMetrics() if font is None else (font if isinstance(font, QFontMetrics) else QFontMetrics(font))
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


def build_forms(srcdir, info=None, summary=False, check_for_migration=False):
    import re, cStringIO
    from PyQt5.uic import compileUi
    forms = find_forms(srcdir)
    if info is None:
        from calibre import prints
        info = prints
    pat = re.compile(r'''(['"]):/images/([^'"]+)\1''')

    def sub(match):
        ans = 'I(%s%s%s)'%(match.group(1), match.group(2), match.group(1))
        return ans

    num = 0
    transdef_pat = re.compile(r'^\s+_translate\s+=\s+QtCore.QCoreApplication.translate$', flags=re.M)
    transpat = re.compile(r'_translate\s*\(.+?,\s+"(.+?)(?<!\\)"\)', re.DOTALL)

    # Ensure that people running from source have all their forms rebuilt for
    # the qt5 migration
    force_compile = check_for_migration and not gprefs.get('migrated_forms_to_qt5', False)

    for form in forms:
        compiled_form = form_to_compiled_form(form)
        if force_compile or not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
            if not summary:
                info('\tCompiling form', form)
            buf = cStringIO.StringIO()
            compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('import images_rc', '')
            dat = transdef_pat.sub('', dat)
            dat = transpat.sub(r'_("\1")', dat)
            dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')
            dat = dat.replace('_("d MMM yyyy")', '"d MMM yyyy"')
            dat = pat.sub(sub, dat)

            open(compiled_form, 'wb').write(dat)
            num += 1
    if num:
        info('Compiled %d forms' % num)
    if force_compile:
        gprefs.set('migrated_forms_to_qt5', True)


_df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
if _df and os.path.exists(_df):
    build_forms(_df, check_for_migration=True)


def event_type_name(ev_or_etype):
    from PyQt5.QtCore import QEvent
    etype = ev_or_etype.type() if isinstance(ev_or_etype, QEvent) else ev_or_etype
    for name, num in vars(QEvent).iteritems():
        if num == etype:
            return name
    return 'UnknownEventType'


def secure_web_page(qwebpage_or_qwebsettings):
    from PyQt5.QtWebKit import QWebSettings
    settings = qwebpage_or_qwebsettings if isinstance(qwebpage_or_qwebsettings, QWebSettings) else qwebpage_or_qwebsettings.settings()
    settings.setAttribute(QWebSettings.JavaEnabled, False)
    settings.setAttribute(QWebSettings.PluginsEnabled, False)
    settings.setAttribute(QWebSettings.JavascriptCanOpenWindows, False)
    settings.setAttribute(QWebSettings.JavascriptCanAccessClipboard, False)
    settings.setAttribute(QWebSettings.LocalContentCanAccessFileUrls, False)  # ensure javascript cannot read from local files
    settings.setAttribute(QWebSettings.NotificationsEnabled, False)
    settings.setThirdPartyCookiePolicy(QWebSettings.AlwaysBlockThirdPartyCookies)
    settings.setAttribute(QWebSettings.OfflineStorageDatabaseEnabled, False)
    settings.setAttribute(QWebSettings.LocalStorageEnabled, False)
    QWebSettings.setOfflineStorageDefaultQuota(0)
    QWebSettings.setOfflineStoragePath(None)
    return settings


empty_model = QStringListModel([''])
empty_index = empty_model.index(0)
