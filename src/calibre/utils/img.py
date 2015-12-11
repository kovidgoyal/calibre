#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, subprocess, errno, shutil, tempfile
from threading import Thread

from PyQt5.Qt import QImage, QByteArray, QBuffer, Qt, QPainter

from calibre import fit_image, force_unicode
from calibre.constants import iswindows
from calibre.utils.filenames import atomic_rename

def get_exe_path(name):
    from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
    base = os.path.dirname(PDFTOHTML)
    if iswindows:
        name += '-calibre.exe'
    if not base:
        return name
    return os.path.join(base, name)

def image_from_data(data):
    i = QImage()
    if not i.loadFromData(data):
        raise ValueError('Not a valid image')
    return i

def scale_image(data, width=60, height=80, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    ''' Scale an image, returning it as either JPEG or PNG data (bytestring).
    Transparency is alpha blended with white when converting to JPEG. Is thread
    safe and does not require a QApplication. '''
    # We use Qt instead of ImageMagick here because ImageMagick seems to use
    # some kind of memory pool, causing memory consumption to sky rocket.
    if isinstance(data, QImage):
        img = data
    else:
        img = QImage()
        if not img.loadFromData(data):
            raise ValueError('Could not load image for thumbnail generation')
    if preserve_aspect_ratio:
        scaled, nwidth, nheight = fit_image(img.width(), img.height(), width, height)
        if scaled:
            img = img.scaled(nwidth, nheight, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        if img.width() != width or img.height() != height:
            img = img.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if not as_png and img.hasAlphaChannel():
        nimg = QImage(img.size(), QImage.Format_RGB32)
        nimg.fill(Qt.white)
        p = QPainter(nimg)
        p.drawImage(0, 0, img)
        p.end()
        img = nimg
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    fmt = 'PNG' if as_png else 'JPEG'
    if not img.save(buf, fmt, quality=compression_quality):
        raise ValueError('Failed to export thumbnail image to: ' + fmt)
    return img.width(), img.height(), ba.data()


def run_optimizer(file_path, cmd, as_filter=False, input_data=None):
    file_path = os.path.abspath(file_path)
    cwd = os.path.dirname(file_path)
    fd, outfile = tempfile.mkstemp(dir=cwd)
    try:
        if as_filter:
            outf = os.fdopen(fd, 'wb')
        else:
            os.close(fd)
        iname, oname = os.path.basename(file_path), os.path.basename(outfile)
        def repl(q, r):
            cmd[cmd.index(q)] = r
        if not as_filter:
            repl(True, iname), repl(False, oname)
        if iswindows:
            # subprocess in python 2 cannot handle unicode strings that are not
            # encodeable in mbcs, so we fail here, where it is more explicit,
            # instead.
            cmd = [x.encode('mbcs') if isinstance(x, type('')) else x for x in cmd]
            if isinstance(cwd, type('')):
                cwd = cwd.encode('mbcs')
        stdin = subprocess.PIPE if as_filter else None
        stderr = subprocess.PIPE if as_filter else subprocess.STDOUT
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=stderr, stdin=stdin)
        stderr = p.stderr if as_filter else p.stdout
        if as_filter:
            src = input_data or open(file_path, 'rb')
            def copy(src, dest):
                try:
                    shutil.copyfileobj(src, dest)
                finally:
                    src.close(), dest.close()
            inw = Thread(name='CopyInput', target=copy, args=(src, p.stdin))
            inw.daemon = True
            inw.start()
            outw = Thread(name='CopyOutput', target=copy, args=(p.stdout, outf))
            outw.daemon = True
            outw.start()
        raw = force_unicode(stderr.read())
        if p.wait() != 0:
            return raw
        else:
            try:
                sz = os.path.getsize(outfile)
            except EnvironmentError:
                sz = 0
            if sz < 1:
                return raw
            shutil.copystat(file_path, outfile)
            atomic_rename(outfile, file_path)
    finally:
        try:
            os.remove(outfile)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise

def optimize_jpeg(file_path):
    exe = get_exe_path('jpegtran')
    cmd = [exe] + '-copy none -optimize -progressive -maxmemory 100M -outfile'.split() + [False, True]
    return run_optimizer(file_path, cmd)

def optimize_png(file_path):
    exe = get_exe_path('optipng')
    cmd = [exe] + '-fix -clobber -strip all -o7 -out'.split() + [False, True]
    return run_optimizer(file_path, cmd)

def encode_jpeg(file_path, quality=80):
    from calibre.srv.utils import ReadOnlyFileBuffer
    quality = max(0, min(100, int(quality)))
    exe = get_exe_path('cjpeg')
    cmd = [exe] + '-optimize -progressive -maxmemory 100M -quality'.split() + [str(quality)]
    img = QImage()
    if not img.load(file_path):
        raise ValueError('%s is not a valid image file' % file_path)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    if not img.save(buf, 'PPM'):
        raise ValueError('Failed to export image to PPM')
    return run_optimizer(file_path, cmd, as_filter=True, input_data=ReadOnlyFileBuffer(ba.data()))
