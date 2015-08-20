#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, errno, json, importlib, math
from io import BytesIO

from PyQt5.Qt import (
    QImageReader, QFormLayout, QVBoxLayout, QSplitter, QGroupBox, QListWidget,
    QLineEdit, QSpinBox, QTextEdit, QSize, QListWidgetItem, QIcon, QImage,
)

from calibre import walk, fit_image
from calibre.customize.ui import interface_actions
from calibre.gui2 import must_use_qt, gprefs, choose_dir, error_dialog, choose_save_file
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import utcnow
from calibre.utils.filenames import ascii_filename
from calibre.utils.magick import create_canvas, Image
from calibre.utils.zipfile import ZipFile, ZIP_STORED
from lzma.xz import compress

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
THEME_COVER = 'icon-theme-cover.jpg'
THEME_METADATA = 'metadata.json'

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
        return ascii_filename(self.theme.title).replace(' ', '_').lower()

def read_theme_from_folder(path):
    path = os.path.abspath(path)
    current_image_map = read_images_from_folder(P('images', allow_user_override=False))
    name_map = read_images_from_folder(path)
    name_map.pop(THEME_COVER, None)
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

def create_cover(report, icons=(), cols=5, size=60, padding=8):
    icons = icons or tuple(default_cover_icons(cols))
    rows = int(math.ceil(len(icons) / cols))
    canvas = create_canvas(cols * (size + padding), rows * (size + padding), '#eeeeee')
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
        img = Image()
        with open(ipath, 'rb') as f:
            img.load(f.read())
        scaled, nwidth, nheight = fit_image(img.size[0], img.size[1], size, size)
        img.size = nwidth, nheight
        dx = (size - nwidth) // 2
        canvas.compose(img, x + dx, y)

    return canvas.export('JPEG')

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
        return QSize(900, 600)

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

def create_themeball(report):
    buf = BytesIO()
    with ZipFile(buf, 'w') as zf:
        for name, path in report.name_map.iteritems():
            with open(os.path.join(report.path, name), 'rb') as f:
                zf.writestr(name, f.read(), compression=ZIP_STORED)
    buf.seek(0)
    out = BytesIO()
    compress(buf, out, level=9)
    buf = BytesIO()
    prefix = report.name
    with ZipFile(buf, 'w') as zf:
        with open(os.path.join(report.path, THEME_METADATA), 'rb') as f:
            zf.writestr(prefix + '/' + THEME_METADATA, f.read())
        zf.writestr(prefix + '/' + THEME_COVER, create_cover(report))
        zf.writestr(prefix + '/' + 'icons.zip.xz', out.getvalue(), compression=ZIP_STORED)
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
    raw, prefix = create_themeball(d.report)
    dest = choose_save_file(parent, 'create-icon-theme-dest', _(
        'Choose destination for icon theme'),
        [(_('ZIP files'), ['zip'])], initial_filename=prefix + '.zip')
    if dest:
        with open(dest, 'wb') as f:
            f.write(raw)

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    create_theme('.')
    del app
