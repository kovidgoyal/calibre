#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, subprocess, errno, shutil, tempfile
from threading import Thread

from PyQt5.Qt import QImage, QByteArray, QBuffer, Qt, QPainter, QImageReader, QColor

from calibre import fit_image, force_unicode
from calibre.constants import iswindows, plugins
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import atomic_rename
imageops, imageops_err = plugins['imageops']

def get_exe_path(name):
    from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
    base = os.path.dirname(PDFTOHTML)
    if iswindows:
        name += '-calibre.exe'
    if not base:
        return name
    return os.path.join(base, name)

_qimage_pixel_map = None

def get_pixel_map():
    ' Get the order of pixels in QImage (RGBA or BGRA usually) '
    global _qimage_pixel_map
    if _qimage_pixel_map is None:
        i = QImage(1, 1, QImage.Format_ARGB32)
        i.fill(QColor(0, 1, 2, 3))
        raw = bytearray(i.constBits().asstring(4))
        _qimage_pixel_map = {c:raw.index(x) for c, x in zip('RGBA', b'\x00\x01\x02\x03')}
        _qimage_pixel_map = ''.join(sorted(_qimage_pixel_map, key=_qimage_pixel_map.get))
    return _qimage_pixel_map

def image_from_data(data):
    if isinstance(data, QImage):
        return data
    i = QImage()
    if not i.loadFromData(data):
        raise ValueError('Not a valid image')
    return i

def image_and_format_from_data(data):
    ba = QByteArray(data)
    buf = QBuffer(ba)
    buf.open(QBuffer.ReadOnly)
    r = QImageReader(buf)
    fmt = bytes(r.format()).decode('utf-8')
    return r.read(), fmt

def add_borders(img, left=0, top=0, right=0, bottom=0, border_color='#ffffff'):
    nimg = QImage(img.width() + left + right, img.height() + top + bottom, QImage.Format_RGB32)
    nimg.fill(QColor(border_color))
    p = QPainter(nimg)
    p.drawImage(left, top, img)
    p.end()
    return nimg

def blend_image(img, bgcolor='#ffffff'):
    nimg = QImage(img.size(), QImage.Format_RGB32)
    nimg.fill(QColor(bgcolor))
    p = QPainter(nimg)
    p.drawImage(0, 0, img)
    p.end()
    return nimg

def image_to_data(img, compression_quality=95, fmt='JPEG'):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    fmt = fmt.upper()
    if img.hasAlphaChannel() and fmt in 'JPEG JPG'.split():
        img = blend_image(img)
    if not img.save(buf, fmt, quality=compression_quality):
        raise ValueError('Failed to export image as ' + fmt)
    return ba.data()

def resize_image(img, width, height):
    return img.scaled(int(width), int(height), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

def resize_to_fit(img, width, height):
    img = image_from_data(img)
    resize_needed, nw, nh = fit_image(img.width(), img.height(), width, height)
    if resize_needed:
        resize_image(img, nw, nh)
    return resize_needed, img

def scale_image(data, width=60, height=80, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    ''' Scale an image, returning it as either JPEG or PNG data (bytestring).
    Transparency is alpha blended with white when converting to JPEG. Is thread
    safe and does not require a QApplication. '''
    # We use Qt instead of ImageMagick here because ImageMagick seems to use
    # some kind of memory pool, causing memory consumption to sky rocket.
    img = image_from_data(data)
    if preserve_aspect_ratio:
        scaled, nwidth, nheight = fit_image(img.width(), img.height(), width, height)
        if scaled:
            img = img.scaled(nwidth, nheight, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        if img.width() != width or img.height() != height:
            img = img.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    fmt = 'PNG' if as_png else 'JPEG'
    w, h = img.width(), img.height()
    return w, h, image_to_data(img, compression_quality=compression_quality, fmt=fmt)

def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpg':
        fmt = 'jpeg'
    return fmt

def add_borders_to_image(img_data, left=0, top=0, right=0, bottom=0,
        border_color='#ffffff', fmt='jpg'):
    img = image_from_data(img_data)
    img = add_borders(img, left=left, top=top, right=right, bottom=bottom, border_color=border_color)
    return image_to_data(img, fmt=fmt)

def save_cover_data_to(data, path=None, bgcolor='#ffffff', resize_to=None, compression_quality=90, minify_to=None, grayscale=False):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Removes any transparency. If there is no transparency and no
    resize and the input and output image formats are the same, no changes are
    made.

    :param data: Image data as bytestring
    :param path: If None img data is returned, in JPEG format
    :param compression_quality: The quality of the image after compression.
        Number between 1 and 100. 1 means highest compression, 100 means no
        compression (lossless).
    :param bgcolor: The color for transparent pixels. Must be specified in hex.
    :param resize_to: A tuple (width, height) or None for no resizing
    :param minify_to: A tuple (width, height) to specify maximum target size.
        The image will be resized to fit into this target size. If None the
        value from the tweak is used.
    '''
    img, fmt = image_and_format_from_data(data)
    orig_fmt = normalize_format_name(fmt)
    fmt = normalize_format_name('jpeg' if path is None else os.path.splitext(path)[1][1:])
    changed = fmt != orig_fmt
    if resize_to is not None:
        changed = True
        img = img.scaled(resize_to[0], resize_to[1], Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    owidth, oheight = img.width(), img.height()
    nwidth, nheight = tweaks['maximum_cover_size'] if minify_to is None else minify_to
    scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
    if scaled:
        changed = True
        img = img.scaled(nwidth, nheight, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if img.hasAlphaChannel():
        changed = True
        img = blend_image(img, bgcolor)
    if grayscale:
        changed = True
        if not img.allGray():
            img = img.convertToFormat(QImage.Format_Grayscale8)
    if path is None:
        return image_to_data(img, compression_quality, fmt) if changed else data
    with lopen(path, 'wb') as f:
        f.write(image_to_data(img, compression_quality, fmt) if changed else data)

def blend_on_canvas(img, width, height, bgcolor='#ffffff'):
    w, h = img.width(), img.height()
    scaled, nw, nh = fit_image(w, h, width, height)
    if scaled:
        img = img.scaled(nw, nh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        w, h = nw, nh
    nimg = QImage(width, height, QImage.Format_RGB32)
    nimg.fill(QColor(bgcolor))
    p = QPainter(nimg)
    p.drawImage((width - w)//2, (height - h)//2, img)
    p.end()
    return nimg

class Canvas(object):

    def __init__(self, width, height, bgcolor='#ffffff'):
        self.img = QImage(width, height, QImage.Format_RGB32)
        self.img.fill(QColor(bgcolor))

    def __enter__(self):
        self.painter = QPainter(self.img)
        return self

    def __exit__(self, *args):
        self.painter.end()

    def compose(self, img, x=0, y=0):
        img = image_from_data(img)
        self.painter.drawImage(x, y, img)

    def export(self, fmt='JPEG', compression_quality=95):
        return image_to_data(self.img, compression_quality=compression_quality, fmt=fmt)

def flip_image(img, horizontal=False, vertical=False):
    return image_from_data(img).mirrored(horizontal, vertical)

def remove_borders(img, fuzz=None):
    if imageops is None:
        raise RuntimeError(imageops_err)
    fuzz = tweaks['cover_trim_fuzz_value'] if fuzz is None else fuzz
    return imageops.remove_borders(image_from_data(img), max(0, fuzz))

def run_optimizer(file_path, cmd, as_filter=False, input_data=None):
    file_path = os.path.abspath(file_path)
    cwd = os.path.dirname(file_path)
    ext = os.path.splitext(file_path)[1]
    if not ext or len(ext) > 10 or not ext.startswith('.'):
        ext = '.jpg'
    fd, outfile = tempfile.mkstemp(dir=cwd, suffix=ext)
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
        creationflags = 0x08 if iswindows else 0
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=stderr, stdin=stdin, creationflags=creationflags)
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
            if as_filter:
                outw.join(60.0), inw.join(60.0)
            try:
                sz = os.path.getsize(outfile)
            except EnvironmentError:
                sz = 0
            if sz < 1:
                return '%s returned a zero size image' % cmd[0]
            shutil.copystat(file_path, outfile)
            atomic_rename(outfile, file_path)
    finally:
        try:
            os.remove(outfile)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        try:
            os.remove(outfile + '.bak')  # optipng creates these files
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

def test():
    from calibre.ptempfile import TemporaryDirectory
    from calibre import CurrentDir
    from glob import glob
    with TemporaryDirectory() as tdir, CurrentDir(tdir):
        shutil.copyfile(I('devices/kindle.jpg'), 'test.jpg')
        ret = optimize_jpeg('test.jpg')
        if ret is not None:
            raise SystemExit('optimize_jpeg failed: %s' % ret)
        ret = encode_jpeg('test.jpg')
        if ret is not None:
            raise SystemExit('encode_jpeg failed: %s' % ret)
        shutil.copyfile(I('lt.png'), 'test.png')
        ret = optimize_png('test.png')
        if ret is not None:
            raise SystemExit('optimize_png failed: %s' % ret)
        if glob('*.bak'):
            raise SystemExit('Spurious .bak files left behind')
