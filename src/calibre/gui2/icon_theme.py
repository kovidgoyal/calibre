#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, errno, json, importlib, math, httplib, bz2, shutil, sys
from itertools import count
from io import BytesIO
from future_builtins import map
from Queue import Queue, Empty
from threading import Thread, Event
from multiprocessing.pool import ThreadPool

from PyQt5.Qt import (
    QImageReader, QFormLayout, QVBoxLayout, QSplitter, QGroupBox, QListWidget,
    QLineEdit, QSpinBox, QTextEdit, QSize, QListWidgetItem, QIcon, QImage,
    pyqtSignal, QStackedLayout, QWidget, QLabel, Qt, QComboBox, QPixmap,
    QGridLayout, QStyledItemDelegate, QApplication, QStaticText,
    QStyle, QPen, QProgressDialog
)

from calibre import walk, fit_image, human_readable, detect_ncpus as cpu_count
from calibre.constants import cache_dir, config_dir
from calibre.customize.ui import interface_actions
from calibre.gui2 import must_use_qt, gprefs, choose_dir, error_dialog, choose_save_file, question_dialog, empty_index
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import utcnow
from calibre.utils.filenames import ascii_filename
from calibre.utils.https import get_https_resource_securely, HTTPError
from calibre.utils.icu import numeric_sort_key as sort_key
from calibre.utils.img import image_from_data, Canvas, optimize_png, optimize_jpeg
from calibre.utils.zipfile import ZipFile, ZIP_STORED
from calibre.utils.filenames import atomic_rename
from lzma.xz import compress, decompress

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
THEME_COVER = 'icon-theme-cover.jpg'
THEME_METADATA = 'metadata.json'
BASE_URL = 'https://code.calibre-ebook.com/icon-themes/'

# Theme creation {{{

COVER_SIZE = (340, 272)


def render_svg(filepath):
    must_use_qt(headless=False)
    pngpath = filepath[:-4] + '.png'
    i = QImage(filepath)
    i.save(pngpath)


def read_images_from_folder(path):
    name_map = {}
    path = os.path.abspath(path)
    for filepath in walk(path):
        name = os.path.relpath(filepath, path).replace(os.sep, '/')
        ext = name.rpartition('.')[-1]
        bname = os.path.basename(name)
        if bname.startswith('.') or bname.startswith('_'):
            continue
        if ext == 'svg':
            render_svg(filepath)
            ext = 'png'
            filepath = filepath[:-4] + '.png'
            name = name[:-4] + '.png'
        if ext in IMAGE_EXTENSIONS:
            name_map[name] = filepath
    return name_map


class Theme(object):

    def __init__(self, title='', author='', version=-1, description='', license='Unknown', url=None, cover=None):
        self.title, self.author, self.version, self.description = title, author, version, description
        self.license, self.cover, self.url = license, cover, url


class Report(object):

    def __init__(self, path, name_map, extra, missing, theme):
        self.path, self.name_map, self.extra, self.missing, self.theme = path, name_map, extra, missing, theme
        self.bad = {}

    @property
    def name(self):
        return ascii_filename(self.theme.title).replace(' ', '_').replace('.', '_').lower()


def read_theme_from_folder(path):
    path = os.path.abspath(path)
    current_image_map = read_images_from_folder(P('images', allow_user_override=False))
    name_map = read_images_from_folder(path)
    name_map.pop(THEME_COVER, None)
    name_map.pop('blank.png', None)
    current_names = frozenset(current_image_map)
    names = frozenset(name_map)
    extra = names - current_names
    missing = current_names - names
    try:
        with open(os.path.join(path, THEME_METADATA), 'rb') as f:
            metadata = json.load(f)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        metadata = {}
    except ValueError:
        # Corrupted metadata file
        metadata = {}

    def safe_int(x):
        try:
            return int(x)
        except Exception:
            return -1
    g = lambda x, defval='': metadata.get(x, defval)
    theme = Theme(g('title'), g('author'), safe_int(g('version', -1)), g('description'), g('license', 'Unknown'), g('url', None))

    ans = Report(path, name_map, extra, missing, theme)
    try:
        with open(os.path.join(path, THEME_COVER), 'rb') as f:
            theme.cover = f.read()
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        theme.cover = create_cover(ans)
    return ans


def icon_for_action(name):
    for plugin in interface_actions():
        if plugin.name == name:
            module, class_name = plugin.actual_plugin.partition(':')[::2]
            mod = importlib.import_module(module)
            cls = getattr(mod, class_name)
            icon = cls.action_spec[1]
            if icon:
                return icon


def default_cover_icons(cols=5):
    count = 0
    for ac in gprefs.defaults['action-layout-toolbar']:
        if ac:
            icon = icon_for_action(ac)
            if icon:
                count += 1
                yield icon
    for x in 'user_profile plus minus series sync tags default_cover'.split():
        yield x + '.png'
        count += 1
    extra = 'search donate cover_flow reader publisher back forward'.split()
    while count < 15 or count % cols != 0:
        yield extra[0] + '.png'
        del extra[0]
        count += 1


def create_cover(report, icons=(), cols=5, size=120, padding=16):
    icons = icons or tuple(default_cover_icons(cols))
    rows = int(math.ceil(len(icons) / cols))
    with Canvas(cols * (size + padding), rows * (size + padding), bgcolor='#eee') as canvas:
        y = -size - padding // 2
        x = 0
        for i, icon in enumerate(icons):
            if i % cols == 0:
                y += padding + size
                x = padding // 2
            else:
                x += size + padding
            if report and icon in report.name_map:
                ipath = os.path.join(report.path, report.name_map[icon])
            else:
                ipath = I(icon, allow_user_override=False)
            with lopen(ipath, 'rb') as f:
                img = image_from_data(f.read())
            scaled, nwidth, nheight = fit_image(img.width(), img.height(), size, size)
            img = img.scaled(nwidth, nheight, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            dx = (size - nwidth) // 2
            canvas.compose(img, x + dx, y)
    return canvas.export()


def verify_theme(report):
    must_use_qt()
    report.bad = bad = {}
    for name, path in report.name_map.iteritems():
        reader = QImageReader(os.path.join(report.path, path))
        img = reader.read()
        if img.isNull():
            bad[name] = reader.errorString()
    return bool(bad)


class ThemeCreateDialog(Dialog):

    def __init__(self, parent, report):
        self.report = report
        Dialog.__init__(self, _('Create an icon theme'), 'create-icon-theme', parent)

    def setup_ui(self):
        self.splitter = QSplitter(self)
        self.l = l = QVBoxLayout(self)
        l.addWidget(self.splitter)
        l.addWidget(self.bb)
        self.w = w = QGroupBox(_('Theme Metadata'), self)
        self.splitter.addWidget(w)
        l = w.l = QFormLayout(w)
        l.setFieldGrowthPolicy(l.ExpandingFieldsGrow)
        self.missing_icons_group = mg = QGroupBox(self)
        self.mising_icons = mi = QListWidget(mg)
        mi.setSelectionMode(mi.NoSelection)
        mg.l = QVBoxLayout(mg)
        mg.l.addWidget(mi)
        self.splitter.addWidget(mg)
        self.title = QLineEdit(self)
        l.addRow(_('&Title:'), self.title)
        self.author = QLineEdit(self)
        l.addRow(_('&Author:'), self.author)
        self.version = v = QSpinBox(self)
        v.setMinimum(1), v.setMaximum(1000000)
        l.addRow(_('&Version:'), v)
        self.license = lc = QLineEdit(self)
        l.addRow(_('&License:'), lc)
        self.url = QLineEdit(self)
        l.addRow(_('&URL:'), self.url)
        lc.setText(_(
            'The license for the icons in this theme. Common choices are'
            ' Creative Commons or Public Domain.'))
        self.description = QTextEdit(self)
        l.addRow(self.description)
        self.refresh_button = rb = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        rb.setIcon(QIcon(I('view-refresh.png')))
        rb.clicked.connect(self.refresh)

        self.apply_report()

    def sizeHint(self):
        return QSize(900, 670)

    @property
    def metadata(self):
        self.report.theme.title = self.title.text().strip()  # Needed for report.name to work
        return {
            'title': self.title.text().strip(),
            'author': self.author.text().strip(),
            'version': self.version.value(),
            'description': self.description.toPlainText().strip(),
            'number': len(self.report.name_map) - len(self.report.extra),
            'date': utcnow().date().isoformat(),
            'name': self.report.name,
            'license': self.license.text().strip() or 'Unknown',
            'url': self.url.text().strip() or None,
        }

    def save_metadata(self):
        with open(os.path.join(self.report.path, THEME_METADATA), 'wb') as f:
            json.dump(self.metadata, f, indent=2)

    def refresh(self):
        self.save_metadata()
        self.report = read_theme_from_folder(self.report.path)
        self.apply_report()

    def apply_report(self):
        theme = self.report.theme
        self.title.setText((theme.title or '').strip())
        self.author.setText((theme.author or '').strip())
        self.version.setValue(theme.version or 1)
        self.description.setText((theme.description or '').strip())
        self.license.setText((theme.license or 'Unknown').strip())
        self.url.setText((theme.url or '').strip())
        if self.report.missing:
            title =  _('%d icons missing in this theme') % len(self.report.missing)
        else:
            title = _('No missing icons')
        self.missing_icons_group.setTitle(title)
        mi = self.mising_icons
        mi.clear()
        for name in sorted(self.report.missing):
            QListWidgetItem(QIcon(I(name, allow_user_override=False)), name, mi)

    def accept(self):
        mi = self.metadata
        if not mi.get('title'):
            return error_dialog(self, _('No title specified'), _(
                'You must specify a title for this icon theme'), show=True)
        if not mi.get('author'):
            return error_dialog(self, _('No author specified'), _(
                'You must specify an author for this icon theme'), show=True)
        return Dialog.accept(self)


class Compress(QProgressDialog):

    update_signal = pyqtSignal(object, object)

    def __init__(self, report, parent=None):
        total = 2 + len(report.name_map)
        QProgressDialog.__init__(self, _('Losslessly optimizing images, please wait...'), _('&Abort'), 0, total, parent)
        self.setWindowTitle(self.labelText())
        self.setWindowIcon(QIcon(I('lt.png')))
        self.setMinimumDuration(0)
        self.update_signal.connect(self.do_update, type=Qt.QueuedConnection)
        self.raw = self.prefix = None
        self.abort = Event()
        self.canceled.connect(self.abort.set)
        self.t = Thread(name='CompressIcons', target=self.run_compress, args=(report,))
        self.t.daemon = False
        self.t.start()

    def do_update(self, num, message):
        if num < 0:
            return self.onerror(_('Optimizing images failed, click "Show details" for more information'), message)
        self.setValue(num)
        self.setLabelText(message)

    def onerror(self, msg, details):
        error_dialog(self, _('Compression failed'), msg, det_msg=details, show=True)
        self.close()

    def onprogress(self, num, msg):
        self.update_signal.emit(num, msg)
        return not self.wasCanceled()

    def run_compress(self, report):
        try:
            self.raw, self.prefix = create_themeball(report, self.onprogress, self.abort)
        except Exception:
            import traceback
            self.update_signal.emit(-1, traceback.format_exc())
        else:
            self.update_signal.emit(self.maximum(), '')


def create_themeball(report, progress=None, abort=None):
    pool = ThreadPool(processes=cpu_count())
    buf = BytesIO()
    num = count()
    error_occurred = Event()

    def optimize(name):
        if abort is not None and abort.is_set():
            return
        if error_occurred.is_set():
            return
        try:
            i = next(num)
            if progress is not None:
                progress(i, _('Optimizing %s') % name)
            srcpath = os.path.join(report.path, name)
            ext = srcpath.rpartition('.')[-1].lower()
            if ext == 'png':
                optimize_png(srcpath)
            elif ext in ('jpg', 'jpeg'):
                optimize_jpeg(srcpath)
        except Exception:
            return sys.exc_info()

    errors = tuple(filter(None, pool.map(optimize, tuple(report.name_map.iterkeys()))))
    pool.close(), pool.join()
    if abort is not None and abort.is_set():
        return
    if errors:
        e = errors[0]
        raise e[0], e[1], e[2]

    if progress is not None:
        progress(next(num), _('Creating theme file'))
    with ZipFile(buf, 'w') as zf:
        for name in report.name_map:
            srcpath = os.path.join(report.path, name)
            with lopen(srcpath, 'rb') as f:
                zf.writestr(name, f.read(), compression=ZIP_STORED)
    buf.seek(0)
    out = BytesIO()
    if abort is not None and abort.is_set():
        return None, None
    if progress is not None:
        progress(next(num), _('Compressing theme file'))
    compress(buf, out, level=9)
    buf = BytesIO()
    prefix = report.name
    if abort is not None and abort.is_set():
        return None, None
    with ZipFile(buf, 'w') as zf:
        with lopen(os.path.join(report.path, THEME_METADATA), 'rb') as f:
            zf.writestr(prefix + '/' + THEME_METADATA, f.read())
        zf.writestr(prefix + '/' + THEME_COVER, create_cover(report))
        zf.writestr(prefix + '/' + 'icons.zip.xz', out.getvalue(), compression=ZIP_STORED)
    if progress is not None:
        progress(next(num), _('Finished'))
    return buf.getvalue(), prefix


def create_theme(folder=None, parent=None):
    if folder is None:
        folder = choose_dir(parent, 'create-icon-theme-folder', _(
            'Choose a folder from which to read the icons'))
        if not folder:
            return
    report = read_theme_from_folder(folder)
    d = ThemeCreateDialog(parent, report)
    if d.exec_() != d.Accepted:
        return
    d.save_metadata()
    d = Compress(d.report, parent=parent)
    d.exec_()
    if d.wasCanceled() or d.raw is None:
        return
    raw, prefix = d.raw, d.prefix
    dest = choose_save_file(parent, 'create-icon-theme-dest', _(
        'Choose destination for icon theme'),
        [(_('ZIP files'), ['zip'])], initial_filename=prefix + '.zip')
    if dest:
        with lopen(dest, 'wb') as f:
            f.write(raw)

# }}}

# Choose Theme  {{{


def download_cover(cover_url, etag=None, cached=b''):
    url = BASE_URL + cover_url
    headers = {}
    if etag:
        if etag[0] != '"':
            etag = '"' + etag + '"'
        headers['If-None-Match'] = etag
    try:
        response = get_https_resource_securely(url, headers=headers, get_response=True)
        cached = response.read()
        etag = response.getheader('ETag', None) or None
        return cached, etag
    except HTTPError as e:
        if etag and e.code == httplib.NOT_MODIFIED:
            return cached, etag
        raise


def get_cover(metadata):
    cdir = os.path.join(cache_dir(), 'icon-theme-covers')
    try:
        os.makedirs(cdir)
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise

    def path(ext):
        return os.path.join(cdir, metadata['name'] + '.' + ext)
    etag_file, cover_file = map(path, 'etag jpg'.split())

    def safe_read(path):
        try:
            with open(path, 'rb') as f:
                return f.read()
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
        return b''
    etag, cached = safe_read(etag_file), safe_read(cover_file)
    cached, etag = download_cover(metadata['cover-url'], etag, cached)
    if cached:
        with open(cover_file, 'wb') as f:
            f.write(cached)
    if etag:
        with open(etag_file, 'wb') as f:
            f.write(etag)
    return cached or b''


def get_covers(themes, callback, num_of_workers=8):
    items = Queue()
    tuple(map(items.put, themes))

    def run():
        while True:
            try:
                metadata = items.get_nowait()
            except Empty:
                return
            try:
                cdata = get_cover(metadata)
            except Exception as e:
                import traceback
                traceback.print_exc()
                callback(metadata, e)
            else:
                callback(metadata, cdata)

    for w in xrange(num_of_workers):
        t = Thread(name='IconThemeCover', target=run)
        t.daemon = True
        t.start()


class Delegate(QStyledItemDelegate):

    SPACING = 10

    def sizeHint(self, option, index):
        return QSize(COVER_SIZE[0] * 2, COVER_SIZE[1] + 2 * self.SPACING)

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        theme = index.data(Qt.UserRole)
        if not theme:
            return
        painter.save()
        pixmap = index.data(Qt.DecorationRole)
        if pixmap and not pixmap.isNull():
            rect = option.rect.adjusted(0, self.SPACING, COVER_SIZE[0] - option.rect.width(), - self.SPACING)
            painter.drawPixmap(rect, pixmap)
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(QApplication.instance().palette().highlightedText().color()))
        bottom = option.rect.bottom() - 2
        painter.drawLine(0, bottom, option.rect.right(), bottom)
        if 'static-text' not in theme:
            theme['static-text'] = QStaticText(_(
                '''
            <h1>{title}</h1>
            <p>by <i>{author}</i> with <b>{number}</b> icons [{size}]</p>
            <p>{description}</p>
            <p>Version: {version} Number of users: {usage}</p>
            '''.format(title=theme.get('title', _('Unknown')), author=theme.get('author', _('Unknown')),
                       number=theme.get('number', 0), description=theme.get('description', ''),
                       size=human_readable(theme.get('compressed-size', 0)), version=theme.get('version', 1),
                       usage=theme.get('usage', 0),
        )))
        painter.drawStaticText(COVER_SIZE[0] + self.SPACING, option.rect.top() + self.SPACING, theme['static-text'])
        painter.restore()


class DownloadProgress(ProgressDialog):

    ds = pyqtSignal(object)
    acc = pyqtSignal()
    rej = pyqtSignal()

    def __init__(self, parent, size):
        ProgressDialog.__init__(self, _('Downloading icons...'), _(
            'Downloading icons, please wait...'), max=size, parent=parent, icon='download_metadata.png')
        self.ds.connect(self.bar.setValue, type=Qt.QueuedConnection)
        self.acc.connect(self.accept, type=Qt.QueuedConnection)
        self.rej.connect(self.reject, type=Qt.QueuedConnection)

    def downloaded(self, byte_count):
        self.ds.emit(byte_count)

    def queue_accept(self):
        self.acc.emit()

    def queue_reject(self):
        self.rej.emit()


class ChooseTheme(Dialog):

    cover_downloaded = pyqtSignal(object, object)
    themes_downloaded = pyqtSignal()

    def __init__(self, parent=None):
        try:
            self.current_theme = json.loads(I('icon-theme.json', data=True))['title']
        except Exception:
            self.current_theme = None
        Dialog.__init__(self, _('Choose an icon theme'), 'choose-icon-theme-dialog', parent)
        self.themes_downloaded.connect(self.show_themes, type=Qt.QueuedConnection)
        self.cover_downloaded.connect(self.set_cover, type=Qt.QueuedConnection)
        self.keep_downloading = True
        self.commit_changes = None
        self.new_theme_title = None

    def sizeHint(self):
        desktop  = QApplication.instance().desktop()
        h = desktop.availableGeometry(self).height()
        return QSize(900, h - 75)

    def setup_ui(self):
        self.vl = vl = QVBoxLayout(self)
        self.stack = l = QStackedLayout()
        self.pi = pi = ProgressIndicator(self, 256)
        vl.addLayout(l), vl.addWidget(self.bb)
        self.restore_defs_button = b = self.bb.addButton(_('Restore &default icons'), self.bb.ActionRole)
        b.clicked.connect(self.restore_defaults)
        b.setIcon(QIcon(I('view-refresh.png')))
        self.c = c = QWidget(self)
        self.c.v = v = QVBoxLayout(self.c)
        v.addStretch(), v.addWidget(pi, 0, Qt.AlignCenter)
        self.wait_msg = m = QLabel(self)
        v.addWidget(m, 0, Qt.AlignCenter), v.addStretch()
        f = m.font()
        f.setBold(True), f.setPointSize(28), m.setFont(f)
        self.start_spinner()

        l.addWidget(c)
        self.w = w = QWidget(self)
        l.addWidget(w)
        w.l = l = QGridLayout(w)

        def add_row(x, y=None):
            if isinstance(x, type('')):
                x = QLabel(x)
            row = l.rowCount()
            if y is None:
                if isinstance(x, QLabel):
                    x.setWordWrap(True)
                l.addWidget(x, row, 0, 1, 2)
            else:
                if isinstance(x, QLabel):
                    x.setBuddy(y)
                l.addWidget(x, row, 0), l.addWidget(y, row, 1)
        add_row(_(
            'Choose an icon theme below. You will need to restart'
            ' calibre to see the new icons.'))
        add_row(_('Current icon theme:') + '\xa0<b>' + (self.current_theme or 'None'))
        self.sort_by = sb = QComboBox(self)
        add_row(_('&Sort by:'), sb)
        sb.addItems([_('Number of icons'), _('Popularity'), _('Name'),])
        sb.setEditable(False), sb.setCurrentIndex(gprefs.get('choose_icon_theme_sort_by', 1))
        sb.currentIndexChanged[int].connect(self.re_sort)
        sb.currentIndexChanged[int].connect(lambda : gprefs.set('choose_icon_theme_sort_by', sb.currentIndex()))
        self.theme_list = tl = QListWidget(self)
        tl.setVerticalScrollMode(tl.ScrollPerPixel)
        self.delegate = Delegate(tl)
        tl.setItemDelegate(self.delegate)
        tl.itemDoubleClicked.connect(self.accept)
        add_row(tl)

        t = Thread(name='GetIconThemes', target=self.get_themes)
        t.daemon = True
        t.start()

    def start_spinner(self, msg=None):
        self.pi.startAnimation()
        self.stack.setCurrentIndex(0)
        self.wait_msg.setText(msg or _('Downloading, please wait...'))

    def end_spinner(self):
        self.pi.stopAnimation()
        self.stack.setCurrentIndex(1)

    @property
    def sort_on(self):
        return {0:'number', 1:'usage', 2:'title'}[self.sort_by.currentIndex()]

    def re_sort(self):
        self.themes.sort(key=lambda x:sort_key(x.get('title', '')))
        field = self.sort_on
        if field == 'number':
            self.themes.sort(key=lambda x:x.get('number', 0), reverse=True)
        elif field == 'usage':
            self.themes.sort(key=lambda x:self.usage.get(x.get('name'), 0), reverse=True)
        self.theme_list.clear()
        for theme in self.themes:
            i = QListWidgetItem(theme.get('title', '') + ' %s %s' % (theme.get('number'), self.usage.get(theme.get('name'))), self.theme_list)
            i.setData(Qt.UserRole, theme)
            if 'cover-pixmap' in theme:
                i.setData(Qt.DecorationRole, theme['cover-pixmap'])

    def get_themes(self):

        self.usage = {}

        def get_usage():
            try:
                self.usage = json.loads(bz2.decompress(get_https_resource_securely(BASE_URL + '/usage.json.bz2')))
            except Exception:
                import traceback
                traceback.print_exc()

        t = Thread(name='IconThemeUsage', target=get_usage)
        t.daemon = True
        t.start()

        try:
            self.themes = json.loads(bz2.decompress(get_https_resource_securely(BASE_URL + '/themes.json.bz2')))
        except Exception:
            import traceback
            self.themes = traceback.format_exc()
        t.join()
        self.themes_downloaded.emit()

    def show_themes(self):
        self.end_spinner()
        if not isinstance(self.themes, list):
            error_dialog(self, _('Failed to download list of themes'), _(
                'Failed to download list of themes, click "Show Details" for more information'),
                         det_msg=self.themes, show=True)
            self.reject()
            return
        for theme in self.themes:
            theme['usage'] = self.usage.get(theme['name'], 0)
        self.re_sort()
        get_covers(self.themes, self.cover_downloaded.emit)

    def __iter__(self):
        for i in xrange(self.theme_list.count()):
            yield self.theme_list.item(i)

    def item_from_name(self, name):
        for item in self:
            if item.data(Qt.UserRole)['name'] == name:
                return item

    def set_cover(self, theme, cdata):
        theme['cover-pixmap'] = p = QPixmap()
        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()
        if isinstance(cdata, bytes):
            p.loadFromData(cdata)
            p.setDevicePixelRatio(dpr)
        item = self.item_from_name(theme['name'])
        if item is not None:
            item.setData(Qt.DecorationRole, p)

    def restore_defaults(self):
        if self.current_theme is not None:
            if not question_dialog(self, _('Are you sure?'), _(
                    'Are you sure you want to remove the <b>%s</b> icon theme'
                    ' and return to the stock icons?') % self.current_theme):
                return
        self.commit_changes = remove_icon_theme
        Dialog.accept(self)

    def accept(self):
        if self.theme_list.currentIndex() < 0:
            return error_dialog(self, _('No theme selected'), _(
                'You must first select an icon theme'), show=True)
        theme = self.theme_list.currentItem().data(Qt.UserRole)
        url = BASE_URL + theme['icons-url']
        size = theme['compressed-size']
        theme = {k:theme.get(k, '') for k in 'name title version'.split()}
        self.keep_downloading = True
        d = DownloadProgress(self, size)
        d.canceled_signal.connect(lambda : setattr(self, 'keep_downloading', False))

        self.downloaded_theme = None

        def download():
            self.downloaded_theme = buf = BytesIO()
            try:
                response = get_https_resource_securely(url, get_response=True)
                while self.keep_downloading:
                    raw = response.read(1024)
                    if not raw:
                        break
                    buf.write(raw)
                    d.downloaded(buf.tell())
                d.queue_accept()
            except Exception:
                import traceback
                self.downloaded_theme = traceback.format_exc()
                d.queue_reject()

        t = Thread(name='DownloadIconTheme', target=download)
        t.daemon = True
        t.start()
        ret = d.exec_()

        if self.downloaded_theme and not isinstance(self.downloaded_theme, BytesIO):
            return error_dialog(self, _('Download failed'), _(
                'Failed to download icon theme, click "Show Details" for more information.'), show=True, det_msg=self.downloaded_theme)
        if ret == d.Rejected or not self.keep_downloading or d.canceled or self.downloaded_theme is None:
            return
        dt = self.downloaded_theme

        def commit_changes():
            dt.seek(0)
            f = decompress(dt)
            f.seek(0)
            remove_icon_theme()
            install_icon_theme(theme, f)
        self.commit_changes = commit_changes
        self.new_theme_title = theme['title']
        return Dialog.accept(self)

# }}}


def remove_icon_theme():
    icdir = os.path.join(config_dir, 'resources', 'images')
    metadata_file = os.path.join(icdir, 'icon-theme.json')
    try:
        with open(metadata_file, 'rb') as f:
            metadata = json.load(f)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        return
    for name in metadata['files']:
        try:
            os.remove(os.path.join(icdir, *name.split('/')))
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
    os.remove(metadata_file)


def safe_copy(src, destpath):
    tpath = destpath + '-temp'
    with open(tpath, 'wb') as dest:
        shutil.copyfileobj(src, dest)
    atomic_rename(tpath, destpath)


def install_icon_theme(theme, f):
    icdir = os.path.abspath(os.path.join(config_dir, 'resources', 'images'))
    if not os.path.exists(icdir):
        os.makedirs(icdir)
    theme['files'] = set()
    metadata_file = os.path.join(icdir, 'icon-theme.json')
    with ZipFile(f) as zf:
        for name in zf.namelist():
            if '..' in name or name == 'blank.png':
                continue
            base = icdir
            if '/' in name:
                base = os.path.join(icdir, os.path.dirname(name))
                if not os.path.exists(base):
                    os.makedirs(base)
            destpath = os.path.abspath(os.path.join(base, os.path.basename(name)))
            if not destpath.startswith(icdir):
                continue
            with zf.open(name) as src:
                safe_copy(src, destpath)
            theme['files'].add(name)

    theme['files'] = tuple(theme['files'])
    buf = BytesIO()
    json.dump(theme, buf, indent=2)
    buf.seek(0)
    safe_copy(buf, metadata_file)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    # create_theme('.')
    d = ChooseTheme()
    if d.exec_() == d.Accepted and d.commit_changes is not None:
        d.commit_changes()
    del app
