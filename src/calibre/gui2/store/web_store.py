#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import shutil

from PyQt5.Qt import (
    QHBoxLayout, QIcon, QLabel, QProgressBar, QPushButton, QSize, QUrl, QVBoxLayout,
    QWidget, pyqtSignal, QApplication
)
from PyQt5.QtWebEngineWidgets import QWebEngineProfile, QWebEngineView

from calibre import random_user_agent, url_slash_cleaner
from calibre.constants import STORE_DIALOG_APP_UID, cache_dir, islinux, iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import (
    Application, choose_save_file, error_dialog, gprefs, info_dialog, set_app_uid
)
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.main_window import MainWindow
from calibre.ptempfile import PersistentTemporaryDirectory, reset_base_dir
from calibre.utils.ipc import RC
from polyglot.builtins import string_or_bytes
from polyglot.binary import from_base64_bytes, as_base64_bytes


class DownloadItem(QWidget):

    def __init__(self, download_id, filename, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.la = la = QLabel('{}:\xa0'.format(filename))
        la.setMaximumWidth(400)
        l.addWidget(la)

        self.pb = pb = QProgressBar(self)
        pb.setRange(0, 0)
        l.addWidget(pb)

        self.download_id = download_id

    def __call__(self, done, total):
        self.pb.setRange(0, total)
        self.pb.setValue(done)


class DownloadProgress(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setVisible(False)
        self.l = QVBoxLayout(self)
        self.items = {}

    def add_item(self, download_id, filename):
        self.setVisible(True)
        item = DownloadItem(download_id, filename, self)
        self.l.addWidget(item)
        self.items[download_id] = item

    def update_item(self, download_id, done, total):
        item = self.items.get(download_id)
        if item is not None:
            item(done, total)

    def remove_item(self, download_id):
        item = self.items.pop(download_id, None)
        if item is not None:
            self.l.removeWidget(item)
            item.setVisible(False)
            item.setParent(None)
            item.deleteLater()
        if not self.items:
            self.setVisible(False)


class Central(QWidget):

    home = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.view = v = QWebEngineView(self)
        v.loadStarted.connect(self.load_started)
        v.loadProgress.connect(self.load_progress)
        v.loadFinished.connect(self.load_finished)
        l.addWidget(v)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.download_progress = d = DownloadProgress(self)
        h.addWidget(d)

        self.home_button = b = QPushButton(_('Home'))
        b.clicked.connect(self.home)
        h.addWidget(b)
        self.back_button = b = QPushButton(_('Back'))
        b.clicked.connect(v.back)
        h.addWidget(b)
        self.forward_button = b = QPushButton(_('Forward'))
        b.clicked.connect(v.forward)
        h.addWidget(b)

        self.progress_bar = b = QProgressBar(self)
        h.addWidget(b)

        self.reload_button = b = QPushButton(_('Reload'))
        b.clicked.connect(v.reload)
        h.addWidget(b)

    def load_started(self):
        self.progress_bar.setValue(0)

    def load_progress(self, amt):
        self.progress_bar.setValue(amt)

    def load_finished(self, ok):
        self.progress_bar.setValue(100)


class Main(MainWindow):

    def __init__(self, data):
        MainWindow.__init__(self, None)
        self.setWindowIcon(QIcon(I('store.png')))
        self.setWindowTitle(data['window_title'])
        self.download_data = {}
        profile = QWebEngineProfile.defaultProfile()
        profile.setCachePath(os.path.join(cache_dir(), 'web_store', 'hc'))
        profile.setPersistentStoragePath(os.path.join(cache_dir(), 'web_store', 'ps'))
        profile.setHttpUserAgent(random_user_agent(allow_ie=False))
        profile.downloadRequested.connect(self.download_requested)
        self.data = data
        self.central = c = Central(self)
        c.home.connect(self.go_home)
        self.setCentralWidget(c)
        geometry = gprefs.get('store_dialog_main_window_geometry')
        if geometry is not None:
            QApplication.instance().safe_restore_geometry(self, geometry)
        self.go_to(data['detail_url'] or None)

    def sizeHint(self):
        return QSize(1024, 740)

    def closeEvent(self, e):
        gprefs.set('store_dialog_main_window_geometry', bytearray(self.saveGeometry()))
        MainWindow.closeEvent(self, e)

    @property
    def view(self):
        return self.central.view

    def go_home(self):
        self.go_to()

    def go_to(self, url=None):
        url = url or self.data['base_url']
        url = url_slash_cleaner(url)
        self.view.load(QUrl(url))

    def download_requested(self, download_item):
        path = download_item.path()
        fname = os.path.basename(path)
        download_id = download_item.id()
        tdir = PersistentTemporaryDirectory()
        self.download_data[download_id] = download_item
        path = os.path.join(tdir, fname)
        download_item.setPath(path)
        connect_lambda(download_item.downloadProgress, self, lambda self, done, total: self.download_progress(download_id, done, total))
        connect_lambda(download_item.finished, self, lambda self: self.download_finished(download_id))
        download_item.accept()
        self.central.download_progress.add_item(download_id, fname)

    def download_progress(self, download_id, done, total):
        self.central.download_progress.update_item(download_id, done, total)

    def download_finished(self, download_id):
        self.central.download_progress.remove_item(download_id)
        download_item = self.download_data.pop(download_id)
        path = download_item.path()
        fname = os.path.basename(path)
        if download_item.state() == download_item.DownloadInterrupted:
            error_dialog(self, _('Download failed'), _(
                'Download of {0} failed with error: {1}').format(fname, download_item.interruptReasonString()), show=True)
            return
        ext = fname.rpartition('.')[-1].lower()
        if ext not in BOOK_EXTENSIONS:
            if ext == 'acsm':
                if not confirm('<p>' + _(
                    'This e-book is a DRMed EPUB file.  '
                    'You will be prompted to save this file to your '
                    'computer. Once it is saved, open it with '
                    '<a href="https://www.adobe.com/solutions/ebook/digital-editions.html">'
                    'Adobe Digital Editions</a> (ADE).<p>ADE, in turn '
                    'will download the actual e-book, which will be a '
                    '.epub file. You can add this book to calibre '
                    'using "Add Books" and selecting the file from '
                    'the ADE library folder.'),
                    'acsm_download', self):
                    return
            name = choose_save_file(self, 'web-store-download-unknown', _(
                'File is not a supported e-book type. Save to disk?'), initial_filename=fname)
            if name:
                shutil.copyfile(path, name)
                os.remove(path)
            return
        t = RC(print_error=False)
        t.start()
        t.join(3.0)
        if t.conn is None:
            error_dialog(self, _('No running calibre'), _(
                'No running calibre instance found. Please start calibre before trying to'
                ' download books.'), show=True)
            return
        tags = self.data['tags']
        if isinstance(tags, string_or_bytes):
            tags = list(filter(None, [x.strip() for x in tags.split(',')]))
        data = json.dumps({'path': path, 'tags': tags})
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        t.conn.send(b'web-store:' + data)
        t.conn.close()

        info_dialog(self, _('Download completed'), _(
            'Download of {0} has been completed, the book was added to'
            ' your calibre library').format(fname), show=True)


def main(args):
    # Ensure we can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    if iswindows:
        # Ensure that all instances are grouped together in the task bar. This
        # prevents them from being grouped with viewer/editor process when
        # launched from within calibre, as both use calibre-parallel.exe
        set_app_uid(STORE_DIALOG_APP_UID)

    data = args[-1]
    data = json.loads(from_base64_bytes(data))
    override = 'calibre-gui' if islinux else None
    app = Application(args, override_program_name=override)
    m = Main(data)
    m.show(), m.raise_()
    app.exec_()
    del m
    del app


if __name__ == '__main__':
    sample_data = as_base64_bytes(
        json.dumps({
            'window_title': 'MobileRead',
            'base_url': 'https://www.mobileread.com/',
            'detail_url': 'http://www.mobileread.com/forums/showthread.php?t=54477',
            'id':1,
            'tags': '',
        })
    )
    main(['store-dialog', sample_data])
