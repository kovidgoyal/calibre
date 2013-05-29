#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import posixpath, os, urllib, re
from urlparse import urlparse, urlunparse
from threading import Thread
from Queue import Queue, Empty

from PyQt4.Qt import QPixmap, Qt, QDialog, QLabel, QVBoxLayout, \
        QDialogButtonBox, QProgressBar, QTimer

from calibre.constants import DEBUG, iswindows
from calibre.ptempfile import PersistentTemporaryFile
from calibre import browser, as_unicode, prints
from calibre.gui2 import error_dialog

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
    return md.hasImage()

def data_as_string(f, md):
    raw = bytes(md.data(f))
    if '/x-moz' in f:
        try:
            raw = raw.decode('utf-16')
        except:
            pass
    return raw

def path_from_qurl(qurl):
    raw = bytes(bytearray(qurl.encodedPath()))
    return urllib.unquote(raw).decode('utf-8')

def dnd_has_extension(md, extensions):
    if DEBUG:
        prints('Debugging DND event')
        for f in md.formats():
            f = unicode(f)
            raw = data_as_string(f, md)
            prints(f, len(raw), repr(raw[:300]), '\n')
        print ()
    if has_firefox_ext(md, extensions):
        return True
    if md.hasUrls():
        urls = [unicode(u.toString()) for u in
                md.urls()]
        paths = [path_from_qurl(u) for u in md.urls()]
        exts = frozenset([posixpath.splitext(u)[1][1:].lower() for u in
            paths if u])
        if DEBUG:
            prints('URLS:', urls)
            prints('Paths:', paths)
            prints('Extensions:', exts)

        return bool(exts.intersection(frozenset(extensions)))
    return False

def _u2p(raw):
    path = raw
    if iswindows and path.startswith('/'):
        path = path[1:]
    return path.replace('/', os.sep)

def u2p(url):
    path = url.path
    ans = _u2p(path)
    if not os.path.exists(ans):
        ans = _u2p(url.path + '#' + url.fragment)
    if os.path.exists(ans):
        return ans
    # Try unquoting the URL
    return urllib.unquote(ans)

def dnd_get_image(md, image_exts=IMAGE_EXTENSIONS):
    '''
    Get the image in the QMimeData object md.

    :return: None, None if no image is found
             QPixmap, None if an image is found, the pixmap is guaranteed not
             null
             url, filename if a URL that points to an image is found
    '''
    if dnd_has_image(md):
        for x in md.formats():
            x = unicode(x)
            if x.startswith('image/'):
                cdata = bytes(md.data(x))
                pmap = QPixmap()
                pmap.loadFromData(cdata)
                if not pmap.isNull():
                    return pmap, None
                break

    # No image, look for a URL pointing to an image
    if md.hasUrls():
        urls = [unicode(u.toString()) for u in
                md.urls()]
        purls = [urlparse(u) for u in urls]
        # First look for a local file
        images = [u2p(x) for x in purls if x.scheme in ('', 'file')]
        images = [x for x in images if
                posixpath.splitext(urllib.unquote(x))[1][1:].lower() in
                image_exts]
        images = [x for x in images if os.path.exists(x)]
        p = QPixmap()
        for path in images:
            try:
                with open(path, 'rb') as f:
                    p.loadFromData(f.read())
            except:
                continue
            if not p.isNull():
                return p, None

        # No local images, look for remote ones

        # First, see if this is from Firefox
        rurl, fname = get_firefox_rurl(md, image_exts)

        if rurl and fname:
            return rurl, fname
        # Look through all remaining URLs
        remote_urls = [x for x in purls if x.scheme in ('http', 'https',
            'ftp') and posixpath.splitext(x.path)[1][1:].lower() in image_exts]
        if remote_urls:
            rurl = remote_urls[0]
            fname = posixpath.basename(urllib.unquote(rurl.path))
            return urlunparse(rurl), fname

        return None, None

def dnd_get_files(md, exts):
    '''
    Get the file in the QMimeData object md with an extension that is one of
    the extensions in exts.

    :return: None, None if no file is found
             [paths], None if a local file is found
             [urls], [filenames] if URLs that point to a files are found
    '''
    # Look for a URL pointing to a file
    if md.hasUrls():
        urls = [unicode(u.toString()) for u in
                md.urls()]
        purls = [urlparse(u) for u in urls]
        # First look for a local file
        local_files = [u2p(x) for x in purls if x.scheme in ('', 'file')]
        local_files = [p for p in local_files if
                posixpath.splitext(urllib.unquote(p))[1][1:].lower() in
                exts]
        local_files = [x for x in local_files if os.path.exists(x)]
        if local_files:
            return local_files, None

        # No local files, look for remote ones

        # First, see if this is from Firefox
        rurl, fname = get_firefox_rurl(md, exts)
        if rurl and fname:
            return [rurl], [fname]

        # Look through all remaining URLs
        remote_urls = [x for x in purls if x.scheme in ('http', 'https',
            'ftp') and posixpath.splitext(x.path)[1][1:].lower() in exts]
        if remote_urls:
            filenames = [posixpath.basename(urllib.unquote(rurl2.path)) for rurl2 in
                    remote_urls]
            return [urlunparse(x) for x in remote_urls], filenames

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
    formats = frozenset([unicode(x) for x in md.formats()])
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


