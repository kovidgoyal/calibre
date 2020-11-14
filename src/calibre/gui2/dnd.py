#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import posixpath
import re
from PyQt5.Qt import (
    QDialog, QDialogButtonBox, QImageReader, QLabel, QPixmap, QProgressBar, Qt,
    QTimer, QUrl, QVBoxLayout
)
from threading import Thread

from calibre import as_unicode, browser, prints
from calibre.constants import DEBUG, iswindows
from calibre.gui2 import error_dialog
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.imghdr import what
from polyglot.builtins import unicode_type
from polyglot.queue import Empty, Queue
from polyglot.urllib import unquote, urlparse


def image_extensions():
    if not hasattr(image_extensions, 'ans'):
        image_extensions.ans = [x.data().decode('utf-8') for x in QImageReader.supportedImageFormats()]
    return image_extensions.ans


# This is present for compatibility with old plugins, do not use
IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'gif', 'png', 'bmp']


class Worker(Thread):  # {{{

    def __init__(self, url, fpath, rq):
        Thread.__init__(self)
        self.url, self.fpath = url, fpath
        self.daemon = True
        self.rq = rq
        self.err = self.tb = None

    def run(self):
        try:
            br = browser()
            br.retrieve(self.url, self.fpath, self.callback)
        except Exception as e:
            self.err = as_unicode(e)
            import traceback
            self.tb = traceback.format_exc()

    def callback(self, a, b, c):
        self.rq.put((a, b, c))
# }}}


class DownloadDialog(QDialog):  # {{{

    def __init__(self, url, fname, parent):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Download %s')%fname)
        self.l = QVBoxLayout(self)
        self.purl = urlparse(url)
        self.msg = QLabel(_('Downloading <b>%(fname)s</b> from %(url)s')%dict(
            fname=fname, url=self.purl.netloc))
        self.msg.setWordWrap(True)
        self.l.addWidget(self.msg)
        self.pb = QProgressBar(self)
        self.pb.setMinimum(0)
        self.pb.setMaximum(0)
        self.l.addWidget(self.pb)
        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.l.addWidget(self.bb)
        self.bb.rejected.connect(self.reject)
        sz = self.sizeHint()
        self.resize(max(sz.width(), 400), sz.height())

        fpath = PersistentTemporaryFile(os.path.splitext(fname)[1])
        fpath.close()
        self.fpath = fpath.name

        self.worker = Worker(url, self.fpath, Queue())
        self.rejected = False

    def reject(self):
        self.rejected = True
        QDialog.reject(self)

    def start_download(self):
        self.worker.start()
        QTimer.singleShot(50, self.update)
        self.exec_()
        if self.worker.err is not None:
            error_dialog(self.parent(), _('Download failed'),
                _('Failed to download from %(url)r with error: %(err)s')%dict(
                    url=self.worker.url, err=self.worker.err),
                det_msg=self.worker.tb, show=True)

    def update(self):
        if self.rejected:
            return

        try:
            progress = self.worker.rq.get_nowait()
        except Empty:
            pass
        else:
            self.update_pb(progress)

        if not self.worker.is_alive():
            return self.accept()
        QTimer.singleShot(50, self.update)

    def update_pb(self, progress):
        transferred, block_size, total = progress
        if total == -1:
            self.pb.setMaximum(0)
            self.pb.setMinimum(0)
            self.pb.setValue(0)
        else:
            so_far = transferred * block_size
            self.pb.setMaximum(max(total, so_far))
            self.pb.setValue(so_far)

    @property
    def err(self):
        return self.worker.err

# }}}


def dnd_has_image(md):
    # Chromium puts image data into application/octet-stream
    return md.hasImage() or md.hasFormat('application/octet-stream') and what(None, bytes(md.data('application/octet-stream'))) in image_extensions()


def data_as_string(f, md):
    raw = bytes(md.data(f))
    if '/x-moz' in f:
        try:
            raw = raw.decode('utf-16')
        except:
            pass
    return raw


remote_protocols = {'http', 'https', 'ftp'}


def urls_from_md(md):
    ans = list(md.urls())
    if md.hasText():
        # Chromium returns the url as text/plain on drag and drop of image
        text = md.text()
        if text and text.lstrip().partition(':')[0] in remote_protocols:
            u = QUrl(text.strip())
            if u.isValid():
                ans.append(u)
    return ans


def path_from_qurl(qurl, allow_remote=False):
    lf = qurl.toLocalFile()
    if lf:
        if iswindows:
            from calibre_extensions.winutil import get_long_path_name
            lf = get_long_path_name(lf)
            lf = make_long_path_useable(lf)
        return lf
    if not allow_remote:
        return ''
    if qurl.scheme() in remote_protocols:
        path = qurl.path()
        if path and '.' in path:
            return path.rpartition('.')[-1]
    return ''


def remote_urls_from_qurl(qurls, allowed_exts):
    for qurl in qurls:
        if qurl.scheme() in remote_protocols and posixpath.splitext(
                qurl.path())[1][1:].lower() in allowed_exts:
            yield bytes(qurl.toEncoded()).decode('utf-8'), posixpath.basename(qurl.path())


def extension(path):
    return path.rpartition('.')[-1].lower()


def dnd_has_extension(md, extensions, allow_all_extensions=False, allow_remote=False):
    if DEBUG:
        prints('\nDebugging DND event')
        for f in md.formats():
            f = unicode_type(f)
            raw = data_as_string(f, md)
            prints(f, len(raw), repr(raw[:300]), '\n')
        print()
    if has_firefox_ext(md, extensions):
        return True
    urls = urls_from_md(md)
    paths = [path_from_qurl(u, allow_remote=allow_remote) for u in urls]
    exts = frozenset(filter(None, (extension(u) for u in paths if u)))
    if DEBUG:
        repr_urls = [bytes(u.toEncoded()).decode('utf-8') for u in urls]
        prints('URLS:', repr(repr_urls))
        prints('Paths:', paths)
        prints('Extensions:', exts)

    if allow_all_extensions:
        return bool(exts)
    return bool(exts.intersection(frozenset(extensions)))


def dnd_get_local_image_and_pixmap(md, image_exts=None):
    if md.hasImage():
        for x in md.formats():
            x = unicode_type(x)
            if x.startswith('image/'):
                cdata = bytes(md.data(x))
                pmap = QPixmap()
                pmap.loadFromData(cdata)
                if not pmap.isNull():
                    return pmap, cdata
    if md.hasFormat('application/octet-stream'):
        cdata = bytes(md.data('application/octet-stream'))
        pmap = QPixmap()
        pmap.loadFromData(cdata)
        if not pmap.isNull():
            return pmap, cdata

    if image_exts is None:
        image_exts = image_extensions()

    # No image, look for an URL pointing to an image
    urls = urls_from_md(md)
    paths = [path_from_qurl(u) for u in urls]
    # Look for a local file
    images = [xi for xi in paths if extension(xi) in image_exts]
    images = [xi for xi in images if os.path.exists(xi)]
    for path in images:
        try:
            with open(path, 'rb') as f:
                cdata = f.read()
        except Exception:
            continue
        p = QPixmap()
        p.loadFromData(cdata)
        if not p.isNull():
            return p, cdata

    return None, None


def dnd_get_image(md, image_exts=None):
    '''
    Get the image in the QMimeData object md.

    :return: None, None if no image is found
             QPixmap, None if an image is found, the pixmap is guaranteed not null
             url, filename if a URL that points to an image is found
    '''
    if image_exts is None:
        image_exts = image_extensions()
    pmap, data = dnd_get_local_image_and_pixmap(md, image_exts)
    if pmap is not None:
        return pmap, None
    # Look for a remote image
    urls = urls_from_md(md)
    # First, see if this is from Firefox
    rurl, fname = get_firefox_rurl(md, image_exts)

    if rurl and fname:
        return rurl, fname
    # Look through all remaining URLs
    for remote_url, filename in remote_urls_from_qurl(urls, image_exts):
        return remote_url, filename

    return None, None


def dnd_get_files(md, exts, allow_all_extensions=False, filter_exts=()):
    '''
    Get the file in the QMimeData object md with an extension that is one of
    the extensions in exts.

    :return: None, None if no file is found
             [paths], None if a local file is found
             [urls], [filenames] if URLs that point to a files are found
    '''
    # Look for a URL pointing to a file
    urls = urls_from_md(md)
    # First look for a local file
    local_files = [path_from_qurl(x) for x in urls]

    def is_ok(path):
        ext = extension(path)
        if allow_all_extensions and ext and ext not in filter_exts:
            return True
        return ext in exts and ext not in filter_exts
    local_files = [p for p in local_files if is_ok(unquote(p))]
    local_files = [x for x in local_files if os.path.exists(x)]
    if local_files:
        return local_files, None

    # No local files, look for remote ones

    # First, see if this is from Firefox
    rurl, fname = get_firefox_rurl(md, exts)
    if rurl and fname:
        return [rurl], [fname]

    # Look through all remaining URLs
    rurls, filenames = [], []
    for rurl, fname in remote_urls_from_qurl(urls, exts):
        rurls.append(rurl), filenames.append(fname)
    if rurls:
        return rurls, filenames

    return None, None


def _get_firefox_pair(md, exts, url, fname):
    url = bytes(md.data(url)).decode('utf-16')
    fname = bytes(md.data(fname)).decode('utf-16')
    while url.endswith('\x00'):
        url = url[:-1]
    while fname.endswith('\x00'):
        fname = fname[:-1]
    if not url or not fname:
        return None, None
    ext = posixpath.splitext(fname)[1][1:].lower()
    # Weird firefox bug on linux
    ext = {'jpe':'jpg', 'epu':'epub', 'mob':'mobi'}.get(ext, ext)
    fname = os.path.splitext(fname)[0] + '.' + ext
    if DEBUG:
        prints('Firefox file promise:', url, fname)
    if ext not in exts:
        fname = url = None
    return url, fname


def get_firefox_rurl(md, exts):
    formats = frozenset([unicode_type(x) for x in md.formats()])
    url = fname = None
    if 'application/x-moz-file-promise-url' in formats and \
            'application/x-moz-file-promise-dest-filename' in formats:
        try:
            url, fname = _get_firefox_pair(md, exts,
                    'application/x-moz-file-promise-url',
                    'application/x-moz-file-promise-dest-filename')
        except:
            if DEBUG:
                import traceback
                traceback.print_exc()
    if url is None and 'text/x-moz-url-data' in formats and \
            'text/x-moz-url-desc' in formats:
        try:
            url, fname = _get_firefox_pair(md, exts,
                    'text/x-moz-url-data', 'text/x-moz-url-desc')
        except:
            if DEBUG:
                import traceback
                traceback.print_exc()

    if url is None and '_NETSCAPE_URL' in formats:
        try:
            raw = bytes(md.data('_NETSCAPE_URL'))
            raw = raw.decode('utf-8')
            lines = raw.splitlines()
            if len(lines) > 1 and re.match(r'[a-z]+://', lines[1]) is None:
                url, fname = lines[:2]
                ext = posixpath.splitext(fname)[1][1:].lower()
                if ext not in exts:
                    fname = url = None
        except:
            if DEBUG:
                import traceback
                traceback.print_exc()
    if DEBUG:
        prints('Firefox rurl:', url, fname)
    return url, fname


def has_firefox_ext(md, exts):
    return bool(get_firefox_rurl(md, exts)[0])
