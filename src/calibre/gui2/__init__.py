

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

""" The GUI """

import glob
import os
import signal
import sys
import threading
from contextlib import contextmanager
from threading import Lock, RLock

from PyQt5.Qt import (
    QT_VERSION, QApplication, QBuffer, QByteArray, QCoreApplication, QDateTime,
    QDesktopServices, QDialog, QEvent, QFileDialog, QFileIconProvider, QFileInfo, QPalette,
    QFont, QFontDatabase, QFontInfo, QFontMetrics, QIcon, QLocale, QColor,
    QNetworkProxyFactory, QObject, QSettings, QSocketNotifier, QStringListModel, Qt,
    QThread, QTimer, QTranslator, QUrl, pyqtSignal
)
from PyQt5.QtWidgets import QStyle  # Gives a nicer error message than import from Qt

from calibre import as_unicode, prints
from calibre.constants import (
    DEBUG, __appname__ as APP_UID, __version__, config_dir, filesystem_encoding,
    is_running_from_develop, isbsd, isfrozen, islinux, ismacos, iswindows, isxp,
    plugins_loc
)
from calibre.ebooks.metadata import MetaInformation
from calibre.gui2.linux_file_dialogs import (
    check_for_linux_native_dialogs, linux_native_dialog
)
from calibre.gui2.qt_file_dialogs import FileDialog
from calibre.ptempfile import base_dir
from calibre.utils.config import Config, ConfigProxy, JSONConfig, dynamic
from calibre.utils.date import UNDEFINED_DATE
from calibre.utils.file_type_icons import EXT_MAP
from calibre.utils.localization import get_lang
from polyglot import queue
from polyglot.builtins import (
    iteritems, itervalues, range, string_or_bytes, unicode_type, map
)

try:
    NO_URL_FORMATTING = QUrl.None_
except AttributeError:
    NO_URL_FORMATTING = getattr(QUrl, 'None')


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
    if ismacos:
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

    defs['action-layout-context-menu-split'] = (
            'Edit Metadata', 'Send To Device', 'Save To Disk',
            'Connect Share', 'Copy To Library', None,
            'Convert Books', 'View', 'Open Folder', 'Show Book Details',
            'Similar Books', 'Tweak ePub', None, 'Remove Books',
            )

    defs['action-layout-context-menu-device'] = (
            'View', 'Save To Disk', None, 'Remove Books', None,
            'Add To Library', 'Edit Collections', 'Match Books',
            'Show Matched Book In Library'
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
    defs['tags_browser_collapse_fl_at'] = 5
    defs['tag_browser_dont_collapse'] = []
    defs['edit_metadata_single_layout'] = 'default'
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
    defs['ui_style'] = 'calibre' if iswindows or ismacos else 'system'
    defs['tag_browser_old_look'] = False
    defs['tag_browser_hide_empty_categories'] = False
    defs['tag_browser_always_autocollapse'] = False
    defs['tag_browser_allow_keyboard_focus'] = False
    defs['book_list_tooltips'] = True
    defs['show_layout_buttons'] = False
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
    defs['vl_tabs_closable'] = True
    defs['show_highlight_toggle_button'] = False
    defs['add_comments_to_email'] = False
    defs['cb_preserve_aspect_ratio'] = False
    defs['gpm_template_editor_font_size'] = 10
    defs['show_emblems'] = False
    defs['emblem_size'] = 32
    defs['emblem_position'] = 'left'
    defs['metadata_diff_mark_rejected'] = False
    defs['tag_browser_show_counts'] = True
    defs['tag_browser_show_tooltips'] = True
    defs['row_numbers_in_book_list'] = True
    defs['hidpi'] = 'auto'
    defs['tag_browser_item_padding'] = 0.5
    defs['paste_isbn_prefixes'] = ['isbn', 'url', 'amazon', 'google']
    defs['qv_respects_vls'] = True
    defs['qv_dclick_changes_column'] = True
    defs['qv_retkey_changes_column'] = True
    defs['qv_follows_column'] = False
    defs['book_details_comments_heading_pos'] = 'hide'
    defs['book_list_split'] = False
    defs['wrap_toolbar_text'] = False
    defs['dnd_merge'] = True
    defs['booklist_grid'] = False
    defs['browse_annots_restrict_to_user'] = None
    defs['browse_annots_restrict_to_type'] = None
    defs['browse_annots_use_stemmer'] = True
    defs['annots_export_format'] = 'txt'


create_defs()
del create_defs
# }}}

UNDEFINED_QDATETIME = QDateTime(UNDEFINED_DATE)
QT_HIDDEN_CLEAR_ACTION = '_q_qlineeditclearaction'
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


def default_author_link():
    from calibre.ebooks.metadata.book.render import DEFAULT_AUTHOR_LINK
    ans = gprefs.get('default_author_link')
    if ans == 'https://en.wikipedia.org/w/index.php?search={author}':
        # The old default value for this setting
        ans = DEFAULT_AUTHOR_LINK
    return ans or DEFAULT_AUTHOR_LINK


def available_heights():
    desktop  = QCoreApplication.instance().desktop()
    return list(map(lambda x: x.height(), map(desktop.availableGeometry, range(desktop.screenCount()))))


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


def get_screen_dpi():
    d = QApplication.desktop()
    return (d.logicalDpiX(), d.logicalDpiY())


_is_widescreen = None


def is_widescreen():
    global _is_widescreen
    if _is_widescreen is None:
        try:
            _is_widescreen = available_width()/available_height() > 1.4
        except:
            _is_widescreen = False
    return _is_widescreen


def extension(path):
    return os.path.splitext(path)[1][1:].lower()


def warning_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    from calibre.gui2.dialogs.message_box import MessageBox
    d = MessageBox(MessageBox.WARNING, _('WARNING:'
        )+ ' ' + title, msg, det_msg, parent=parent,
        show_copy_button=show_copy_button)
    if show:
        return d.exec_()
    return d


def error_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    from calibre.gui2.dialogs.message_box import MessageBox
    d = MessageBox(MessageBox.ERROR, _('ERROR:'
        ) + ' ' + title, msg, det_msg, parent=parent,
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

    if not isinstance(skip_dialog_name, unicode_type):
        skip_dialog_name = None
    try:
        auto_skip = set(gprefs.get('questions_to_auto_skip', ()))
    except Exception:
        auto_skip = set()
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
        self.q = queue.Queue()
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
            path_map = {v:I('mimetypes/%s.png' % v) for v in set(itervalues(self.ICONS))}
            icons = self.ICONS.copy()
            for uicon in glob.glob(os.path.join(upath, '*.png')):
                ukey = os.path.basename(uicon).rpartition('.')[0].lower()
                if ukey not in path_map:
                    path_map[ukey] = uicon
                    icons[ukey] = ukey
        else:
            path_map = {v:os.path.join(bpath, v + '.png') for v in set(itervalues(self.ICONS))}
            icons = self.ICONS
        self.icons = {k:path_map[v] for k, v in iteritems(icons)}
        self.icons['calibre'] = I('lt.png', allow_user_override=False)
        for i in ('dir', 'default', 'zero'):
            self.icons[i] = QIcon(self.icons[i])

    def key_from_ext(self, ext):
        key = ext if ext in list(self.icons.keys()) else 'default'
        if key == 'default' and ext.count('.') > 0:
            ext = ext.rpartition('.')[2]
            key = ext if ext in list(self.icons.keys()) else 'default'
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
            ext = unicode_type(fileinfo.completeSuffix()).lower()
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


has_windows_file_dialog_helper = False
if iswindows and 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ:
    from calibre.gui2.win_file_dialogs import is_ok as has_windows_file_dialog_helper
    has_windows_file_dialog_helper = has_windows_file_dialog_helper()
has_linux_file_dialog_helper = False
if not iswindows and not ismacos and 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ and getattr(sys, 'frozen', False):
    has_linux_file_dialog_helper = check_for_linux_native_dialogs()

if has_windows_file_dialog_helper:
    from calibre.gui2.win_file_dialogs import choose_files, choose_images, choose_dir, choose_save_file
elif has_linux_file_dialog_helper:
    choose_dir, choose_files, choose_save_file, choose_images = map(
        linux_native_dialog, 'dir files save_file images'.split())
else:
    from calibre.gui2.qt_file_dialogs import choose_files, choose_images, choose_dir, choose_save_file
    choose_files, choose_images, choose_dir, choose_save_file


def is_dark_theme():
    pal = QApplication.instance().palette()
    col = pal.color(pal.Window)
    return max(col.getRgb()[:3]) < 115


def choose_osx_app(window, name, title, default_dir='/Applications'):
    fd = FileDialog(title=title, parent=window, name=name, mode=QFileDialog.ExistingFile,
            default_dir=default_dir)
    app = fd.get_files()
    fd.setParent(None)
    if app:
        return app


def pixmap_to_data(pixmap, format='JPEG', quality=None):
    '''
    Return the QPixmap pixmap as a string saved in the specified format.
    '''
    if quality is None:
        if format.upper() == "PNG":
            # For some reason on windows with Qt 5.6 using a quality of 90
            # generates invalid PNG data. Many other quality values work
            # but we use -1 for the default quality which is most likely to
            # work
            quality = -1
        else:
            quality = 90
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, format, quality=quality)
    return ba.data()


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
            src = unicode_type(args[1])
        except:
            return ''
        t = _
        return t(src)


gui_thread = None
qt_app = None


def calibre_font_files():
    return glob.glob(P('fonts/liberation/*.?tf')) + [P('fonts/calibreSymbols.otf')] + \
            glob.glob(os.path.join(config_dir, 'fonts', '*.?tf'))


def load_builtin_fonts():
    global _rating_font, builtin_fonts_loaded
    # Load the builtin fonts and any fonts added to calibre by the user to
    # Qt
    if hasattr(load_builtin_fonts, 'done'):
        return
    load_builtin_fonts.done = True
    for ff in calibre_font_files():
        if ff.rpartition('.')[-1].lower() in {'ttf', 'otf'}:
            with open(ff, 'rb') as s:
                # Windows requires font files to be executable for them to be
                # loaded successfully, so we use the in memory loader
                fid = QFontDatabase.addApplicationFontFromData(s.read())
                if fid > -1:
                    fam = QFontDatabase.applicationFontFamilies(fid)
                    fam = set(map(unicode_type, fam))
                    if 'calibre Symbols' in fam:
                        _rating_font = 'calibre Symbols'


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


def setup_hidpi():
    # This requires Qt >= 5.6
    has_env_setting = False
    env_vars = ('QT_AUTO_SCREEN_SCALE_FACTOR', 'QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'QT_DEVICE_PIXEL_RATIO')
    for v in env_vars:
        if os.environ.get(v):
            has_env_setting = True
            break
    hidpi = gprefs['hidpi']
    if hidpi == 'on' or (hidpi == 'auto' and not has_env_setting):
        if DEBUG:
            prints('Turning on automatic hidpi scaling')
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    elif hidpi == 'off':
        if DEBUG:
            prints('Turning off automatic hidpi scaling')
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
        for p in env_vars:
            os.environ.pop(p, None)
    elif DEBUG:
        prints('Not controlling automatic hidpi scaling')


def setup_unix_signals(self):
    if hasattr(os, 'pipe2'):
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    else:
        import fcntl
        read_fd, write_fd = os.pipe()
        cloexec_flag = getattr(fcntl, 'FD_CLOEXEC', 1)
        for fd in (read_fd, write_fd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            if flags != -1:
                fcntl.fcntl(fd, fcntl.F_SETFD, flags | cloexec_flag)
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            if flags != -1:
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    original_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        original_handlers[sig] = signal.signal(sig, lambda x, y: None)
        signal.siginterrupt(sig, False)
    signal.set_wakeup_fd(write_fd)
    self.signal_notifier = QSocketNotifier(read_fd, QSocketNotifier.Read, self)
    self.signal_notifier.setEnabled(True)
    self.signal_notifier.activated.connect(self.signal_received, type=Qt.QueuedConnection)
    return original_handlers


class Application(QApplication):

    shutdown_signal_received = pyqtSignal()
    palette_changed = pyqtSignal()

    def __init__(self, args, force_calibre_style=False, override_program_name=None, headless=False, color_prefs=gprefs, windows_app_uid=None):
        self.ignore_palette_changes = False
        QNetworkProxyFactory.setUseSystemConfiguration(True)
        if iswindows:
            self.windows_app_uid = None
            if windows_app_uid:
                windows_app_uid = unicode_type(windows_app_uid)
                if set_app_uid(windows_app_uid):
                    self.windows_app_uid = windows_app_uid
        self.file_event_hook = None
        if isfrozen and QT_VERSION <= 0x050700 and 'wayland' in os.environ.get('QT_QPA_PLATFORM', ''):
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
        if override_program_name:
            args = [override_program_name] + args[1:]
        if headless:
            if not args:
                args = sys.argv[:1]
            args.extend(['-platformpluginpath', plugins_loc, '-platform', 'headless'])
        self.headless = headless
        qargs = [i.encode('utf-8') if isinstance(i, unicode_type) else i for i in args]
        from calibre_extensions import progress_indicator
        self.pi = progress_indicator
        if not ismacos and not headless:
            # On OS X high dpi scaling is turned on automatically by the OS, so we dont need to set it explicitly
            setup_hidpi()
        QApplication.setOrganizationName('calibre-ebook.com')
        QApplication.setOrganizationDomain(QApplication.organizationName())
        QApplication.setApplicationVersion(__version__)
        QApplication.setApplicationName(APP_UID)
        if override_program_name and hasattr(QApplication, 'setDesktopFileName'):
            QApplication.setDesktopFileName(override_program_name)
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)  # needed for webengine
        QApplication.__init__(self, qargs)
        sh = self.styleHints()
        if hasattr(sh, 'setShowShortcutsInContextMenus'):
            sh.setShowShortcutsInContextMenus(True)
        if ismacos:
            from calibre_extensions.cocoa import disable_cocoa_ui_elements
            disable_cocoa_ui_elements()
        self.setAttribute(Qt.AA_UseHighDpiPixmaps)
        self.setAttribute(Qt.AA_SynthesizeTouchForUnhandledMouseEvents, False)
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
        self.setup_ui_font()
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
        if not ismacos and not iswindows:
            # Qt 5.10.1 on Linux resets the global font on first event loop tick.
            # So workaround it by setting the font once again in a timer.
            font_from_prefs = self.font()
            QTimer.singleShot(0, lambda : QApplication.setFont(font_from_prefs))
        self.line_height = max(12, QFontMetrics(self.font()).lineSpacing())

        dl = QLocale(get_lang())
        if unicode_type(dl.bcp47Name()) != 'C':
            QLocale.setDefault(dl)
        global gui_thread, qt_app
        gui_thread = QThread.currentThread()
        self._translator = None
        self.load_translations()
        qt_app = self
        self._file_open_paths = []
        self._file_open_lock = RLock()

        if not ismacos:
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
                ' which works well on Windows XP.') % 'https://download.calibre-ebook.com/1.48.0/', show=True)
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

        if ismacos:
            from calibre_extensions.cocoa import cursor_blink_time
            cft = cursor_blink_time()
            if cft >= 0:
                self.setCursorFlashTime(int(cft))

    def safe_restore_geometry(self, widget, geom):
        # See https://bugreports.qt.io/browse/QTBUG-77385
        if not geom:
            return
        restored = widget.restoreGeometry(geom)
        self.ensure_window_on_screen(widget)
        return restored

    def ensure_window_on_screen(self, widget):
        screen_rect = self.desktop().availableGeometry(widget)
        if not widget.geometry().intersects(screen_rect):
            w = min(widget.width(), screen_rect.width() - 10)
            h = min(widget.height(), screen_rect.height() - 10)
            widget.resize(w, h)
            widget.move((screen_rect.width() - w) // 2, (screen_rect.height() - h) // 2)

    def setup_ui_font(self):
        f = QFont(QApplication.font())
        q = (f.family(), f.pointSize())
        if iswindows:
            if q == ('MS Shell Dlg 2', 8):  # Qt default setting
                # Microsoft recommends the default font be Segoe UI at 9 pt
                # https://msdn.microsoft.com/en-us/library/windows/desktop/dn742483(v=vs.85).aspx
                f.setFamily('Segoe UI')
                f.setPointSize(9)
                QApplication.setFont(f)
        else:
            if q == ('Sans Serif', 9):  # Hard coded Qt settings, no user preference detected
                f.setPointSize(10)
                QApplication.setFont(f)
        f = QFontInfo(f)
        self.original_font = (f.family(), f.pointSize(), f.weight(), f.italic(), 100)

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

    def set_dark_mode_palette(self):
        from calibre.gui2.palette import dark_palette
        self.set_palette(dark_palette())

    def setup_styles(self, force_calibre_style):
        if iswindows or ismacos:
            using_calibre_style = gprefs['ui_style'] != 'system'
        else:
            using_calibre_style = os.environ.get('CALIBRE_USE_SYSTEM_THEME', '0') == '0'
        if force_calibre_style:
            using_calibre_style = True
        if using_calibre_style:
            use_dark_palette = False
            if 'CALIBRE_USE_DARK_PALETTE' in os.environ:
                if not ismacos:
                    use_dark_palette = os.environ['CALIBRE_USE_DARK_PALETTE'] != '0'
            else:
                if iswindows:
                    use_dark_palette = windows_is_system_dark_mode_enabled()
            if use_dark_palette:
                self.set_dark_mode_palette()

        self.using_calibre_style = using_calibre_style
        if DEBUG:
            prints('Using calibre Qt style:', self.using_calibre_style)
        if self.using_calibre_style:
            self.load_calibre_style()
        self.paletteChanged.connect(self.on_palette_change)
        self.on_palette_change()

    def fix_combobox_text_color(self):
        # Workaround for https://bugreports.qt.io/browse/QTBUG-75321
        # Buttontext is set to black for some reason
        pal = QPalette(self.palette())
        pal.setColor(pal.ButtonText, pal.color(pal.WindowText))
        self.ignore_palette_changes = True
        self.setPalette(pal, 'QComboBox')
        self.ignore_palette_changes = False

    def set_palette(self, pal):
        self.ignore_palette_changes = True
        self.setPalette(pal)
        # Needed otherwise Qt does not emit the paletteChanged signal when
        # appearance is changed. And it has to be after current event
        # processing finishes as of Qt 5.14 otherwise the palette change is
        # ignored.
        QTimer.singleShot(1000, lambda: QApplication.instance().setAttribute(Qt.AA_SetPalette, False))
        self.ignore_palette_changes = False

    def on_palette_change(self):
        if self.ignore_palette_changes:
            return
        self.is_dark_theme = is_dark_theme()
        self.setProperty('is_dark_theme', self.is_dark_theme)
        if ismacos and self.is_dark_theme and self.using_calibre_style:
            QTimer.singleShot(0, self.fix_combobox_text_color)
        if self.using_calibre_style:
            ss = 'QTabBar::tab:selected { font-style: italic }\n\n'
            if self.is_dark_theme:
                ss += 'QMenu { border: 1px solid palette(shadow); }'
            self.setStyleSheet(ss)
        self.palette_changed.emit()

    def stylesheet_for_line_edit(self, is_error=False):
        return 'QLineEdit { border: 2px solid %s; border-radius: 3px }' % (
            '#FF2400' if is_error else '#50c878')

    def load_calibre_style(self):
        icon_map = self.__icon_map_memory_ = {}
        pcache = {}
        for k, v in iteritems({
            'DialogYesButton': 'ok.png',
            'DialogNoButton': 'window-close.png',
            'DialogCloseButton': 'window-close.png',
            'DialogOkButton': 'ok.png',
            'DialogCancelButton': 'window-close.png',
            'DialogHelpButton': 'help.png',
            'DialogOpenButton': 'document_open.png',
            'DialogSaveButton': 'save.png',
            'DialogApplyButton': 'ok.png',
            'DialogDiscardButton': 'trash.png',
            'MessageBoxInformation': 'dialog_information.png',
            'MessageBoxWarning': 'dialog_warning.png',
            'MessageBoxCritical': 'dialog_error.png',
            'MessageBoxQuestion': 'dialog_question.png',
            'BrowserReload': 'view-refresh.png',
            'LineEditClearButton': 'clear_left.png',
            'ToolBarHorizontalExtensionButton': 'v-ellipsis.png',
            'ToolBarVerticalExtensionButton': 'h-ellipsis.png',
        }):
            if v not in pcache:
                p = I(v)
                if isinstance(p, bytes):
                    p = p.decode(filesystem_encoding)
                # if not os.path.exists(p): raise ValueError(p)
                pcache[v] = p
            v = pcache[v]
            icon_map[getattr(QStyle, 'SP_'+k)] = v
        transient_scroller = 0
        if ismacos:
            from calibre_extensions.cocoa import transient_scroller
            transient_scroller = transient_scroller()
        icon_map[QStyle.SP_CustomBase + 1] = I('close-for-light-theme.png')
        icon_map[QStyle.SP_CustomBase + 2] = I('close-for-dark-theme.png')
        self.pi.load_style(icon_map, transient_scroller)

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
            url = e.url().toString(QUrl.FullyEncoded)
            if url and url.startswith('calibre://'):
                with self._file_open_lock:
                    self._file_open_paths.append(url)
                QTimer.singleShot(1000, self._send_file_open_events)
                return True
            path = unicode_type(e.file())
            if os.access(path, os.R_OK):
                with self._file_open_lock:
                    self._file_open_paths.append(path)
                QTimer.singleShot(1000, self._send_file_open_events)
            return True
        else:
            return QApplication.event(self, e)

    @property
    def current_custom_colors(self):
        from PyQt5.Qt import QColorDialog

        return [col.getRgb() for col in
                    (QColorDialog.customColor(i) for i in range(QColorDialog.customCount()))]

    @current_custom_colors.setter
    def current_custom_colors(self, colors):
        from PyQt5.Qt import QColorDialog
        num = min(len(colors), QColorDialog.customCount())
        for i in range(num):
            QColorDialog.setCustomColor(i, QColor(*colors[i]))

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
        setup_unix_signals(self)

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
        env_vars = {'LD_LIBRARY_PATH':'/lib'}
    elif iswindows:
        env_vars = {}
    elif ismacos:
        env_vars = {k:None for k in (
                    'FONTCONFIG_FILE FONTCONFIG_PATH SSL_CERT_FILE').split()}
    else:
        env_vars = {}

    originals = {x:os.environ.get(x, '') for x in env_vars}
    changed = {x:False for x in env_vars}
    for var, suffix in iteritems(env_vars):
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
        for var, orig in iteritems(originals):
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
    if isinstance(qurl, string_or_bytes):
        qurl = QUrl(qurl)
    with sanitize_env_vars():
        QDesktopServices.openUrl(qurl)


def safe_open_url(qurl):
    if isinstance(qurl, string_or_bytes):
        qurl = QUrl(qurl)
    if qurl.scheme() in ('', 'file'):
        path = qurl.toLocalFile()
        ext = os.path.splitext(path)[-1].lower()[1:]
        if ext in ('exe', 'com', 'cmd', 'bat', 'sh', 'psh', 'ps1', 'vbs', 'js', 'wsf', 'vba', 'py', 'rb', 'pl', 'app'):
            prints('Refusing to open file:', path)
            return
    open_url(qurl)


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
            has_headless = ismacos or islinux or isbsd
            if headless and has_headless:
                args += ['-platformpluginpath', plugins_loc, '-platform', 'headless']
                if ismacos:
                    os.environ['QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM'] = '1'
            if headless and iswindows:
                QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
            _store_app = QApplication(args)
            if headless and has_headless:
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
    return _store_app


def destroy_app():
    global _store_app
    _store_app = None


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
    ellipsis = '\u2026'

    def remove_middle(x):
        mid = len(x) // 2
        return x[:max(0, mid - (delta//2))] + ellipsis + x[mid + (delta//2):]

    chomp = {'middle':remove_middle, 'left':lambda x:(ellipsis + x[delta:]), 'right':lambda x:(x[:-delta] + ellipsis)}[pos]
    while len(text) > delta and fm.width(text) > width:
        text = chomp(text)
    return unicode_type(text)


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
    import re
    from PyQt5.uic import compileUi
    from polyglot.io import PolyglotStringIO
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
            buf = PolyglotStringIO()
            compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('import images_rc', '')
            dat = transdef_pat.sub('', dat)
            dat = transpat.sub(r'_("\1")', dat)
            dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')
            dat = dat.replace('_("d MMM yyyy")', '"d MMM yyyy"')
            dat = pat.sub(sub, dat)
            if not isinstance(dat, bytes):
                dat = dat.encode('utf-8')
            open(compiled_form, 'wb').write(dat)
            num += 1
    if num:
        info('Compiled %d forms' % num)
    if force_compile:
        gprefs.set('migrated_forms_to_qt5', True)


if is_running_from_develop:
    build_forms(os.environ['CALIBRE_DEVELOP_FROM'], check_for_migration=True)


def event_type_name(ev_or_etype):
    from PyQt5.QtCore import QEvent
    etype = ev_or_etype.type() if isinstance(ev_or_etype, QEvent) else ev_or_etype
    for name, num in iteritems(vars(QEvent)):
        if num == etype:
            return name
    return 'UnknownEventType'


empty_model = QStringListModel([''])
empty_index = empty_model.index(0)


def set_app_uid(val):
    import ctypes
    from ctypes import wintypes
    from ctypes import HRESULT
    try:
        AppUserModelID = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    except Exception:  # Vista has no app uids
        return False
    AppUserModelID.argtypes = [wintypes.LPCWSTR]
    AppUserModelID.restype = HRESULT
    try:
        AppUserModelID(unicode_type(val))
    except Exception as err:
        prints('Failed to set app uid with error:', as_unicode(err))
        return False
    return True


def add_to_recent_docs(path):
    from calibre_extensions import winutil
    app = QApplication.instance()
    winutil.add_to_recent_docs(unicode_type(path), app.windows_app_uid)


def windows_is_system_dark_mode_enabled():
    s = QSettings(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", QSettings.NativeFormat)
    if s.status() == QSettings.NoError:
        return s.value("AppsUseLightTheme") == 0
    return False


def make_view_use_window_background(view):
    p = view.palette()
    p.setColor(p.Base, p.color(p.Window))
    p.setColor(p.AlternateBase, p.color(p.Window))
    view.setPalette(p)
    return view
