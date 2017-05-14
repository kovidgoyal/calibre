#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import errno
import os
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from threading import Thread

from PyQt5.Qt import (
    QBuffer, QByteArray, QColor, QImage, QImageReader, QImageWriter, QPixmap, Qt,
    QTransform
)

from calibre import fit_image, force_unicode
from calibre.constants import iswindows, plugins
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import atomic_rename
from calibre.utils.imghdr import what

# Utilities {{{
imageops, imageops_err = plugins['imageops']
if imageops is None:
    raise RuntimeError(imageops_err)


class NotImage(ValueError):
    pass


def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpg':
        fmt = 'jpeg'
    return fmt


def get_exe_path(name):
    from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
    base = os.path.dirname(PDFTOHTML)
    if iswindows:
        name += '-calibre.exe'
    if not base:
        return name
    return os.path.join(base, name)


def load_jxr_data(data):
    with TemporaryDirectory() as tdir:
        if iswindows and isinstance(tdir, type('')):
            tdir = tdir.encode('mbcs')
        with lopen(os.path.join(tdir, 'input.jxr'), 'wb') as f:
            f.write(data)
        cmd = [get_exe_path('JxrDecApp'), '-i', 'input.jxr', '-o', 'output.tif', '-c', '0']
        creationflags = 0x08 if iswindows else 0
        subprocess.Popen(cmd, cwd=tdir, stdout=lopen(os.devnull, 'wb'), stderr=subprocess.STDOUT, creationflags=creationflags).wait()
        i = QImage()
        if not i.load(os.path.join(tdir, 'output.tif')):
            raise NotImage('Failed to convert JPEG-XR image')
        return i

# }}}

# Loading images {{{


def null_image():
    ' Create an invalid image. For internal use. '
    return QImage()


def image_from_data(data):
    ' Create an image object from data, which should be a bytestring. '
    if isinstance(data, QImage):
        return data
    i = QImage()
    if not i.loadFromData(data):
        if what(None, data) == 'jxr':
            return load_jxr_data(data)
        raise NotImage('Not a valid image')
    return i


def image_from_path(path):
    ' Load an image from the specified path. '
    with lopen(path, 'rb') as f:
        return image_from_data(f.read())


def image_from_x(x):
    ' Create an image from a bytestring or a path or a file like object. '
    if isinstance(x, type('')):
        return image_from_path(x)
    if hasattr(x, 'read'):
        return image_from_data(x.read())
    if isinstance(x, (bytes, QImage)):
        return image_from_data(x)
    if isinstance(x, bytearray):
        return image_from_data(bytes(x))
    if isinstance(x, QPixmap):
        return x.toImage()
    raise TypeError('Unknown image src type: %s' % type(x))


def image_and_format_from_data(data):
    ' Create an image object from the specified data which should be a bytestring and also return the format of the image '
    ba = QByteArray(data)
    buf = QBuffer(ba)
    buf.open(QBuffer.ReadOnly)
    r = QImageReader(buf)
    fmt = bytes(r.format()).decode('utf-8')
    return r.read(), fmt
# }}}

# Saving images {{{


def image_to_data(img, compression_quality=95, fmt='JPEG', png_compression_level=9, jpeg_optimized=True, jpeg_progressive=False):
    '''
    Serialize image to bytestring in the specified format.

    :param compression_quality: is for JPEG and goes from 0 to 100. 100 being lowest compression, highest image quality
    :param png_compression_level: is for PNG and goes from 0-9. 9 being highest compression.
    :param jpeg_optimized: Turns on the 'optimize' option for libjpeg which losslessly reduce file size
    :param jpeg_progressive: Turns on the 'progressive scan' option for libjpeg which allows JPEG images to be downloaded in streaming fashion
    '''
    fmt = fmt.upper()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    if fmt == 'GIF':
        w = QImageWriter(buf, b'PNG')
        w.setQuality(90)
        if not w.write(img):
            raise ValueError('Failed to export image as ' + fmt + ' with error: ' + w.errorString())
        from PIL import Image
        im = Image.open(BytesIO(ba.data()))
        buf = BytesIO()
        im.save(buf, 'gif')
        return buf.getvalue()
    is_jpeg = fmt in ('JPG', 'JPEG')
    w = QImageWriter(buf, fmt.encode('ascii'))
    if is_jpeg:
        if img.hasAlphaChannel():
            img = blend_image(img)
        # QImageWriter only gained the following options in Qt 5.5
        if jpeg_optimized and hasattr(QImageWriter, 'setOptimizedWrite'):
            w.setOptimizedWrite(True)
        if jpeg_progressive and hasattr(QImageWriter, 'setProgressiveScanWrite'):
            w.setProgressiveScanWrite(True)
        w.setQuality(compression_quality)
    elif fmt == 'PNG':
        cl = min(9, max(0, png_compression_level))
        w.setQuality(10 * (9-cl))
    if not w.write(img):
        raise ValueError('Failed to export image as ' + fmt + ' with error: ' + w.errorString())
    return ba.data()


def save_image(img, path, **kw):
    ''' Save image to the specified path. Image format is taken from the file
    extension. You can pass the same keyword arguments as for the
    `image_to_data()` function. '''
    fmt = path.rpartition('.')[-1]
    kw['fmt'] = kw.get('fmt', fmt)
    with lopen(path, 'wb') as f:
        f.write(image_to_data(image_from_data(img), **kw))


def save_cover_data_to(data, path=None, bgcolor='#ffffff', resize_to=None, compression_quality=90, minify_to=None, grayscale=False, data_fmt='jpeg'):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Removes any transparency. If there is no transparency and no
    resize and the input and output image formats are the same, no changes are
    made.

    :param data: Image data as bytestring
    :param path: If None img data is returned, in JPEG format
    :param data_fmt: The fmt to return data in when path is None. Defaults to JPEG
    :param compression_quality: The quality of the image after compression.
        Number between 1 and 100. 1 means highest compression, 100 means no
        compression (lossless).
    :param bgcolor: The color for transparent pixels. Must be specified in hex.
    :param resize_to: A tuple (width, height) or None for no resizing
    :param minify_to: A tuple (width, height) to specify maximum target size.
        The image will be resized to fit into this target size. If None the
        value from the tweak is used.
    '''
    fmt = normalize_format_name(data_fmt if path is None else os.path.splitext(path)[1][1:])
    if isinstance(data, QImage):
        img = data
        changed = True
    else:
        img, orig_fmt = image_and_format_from_data(data)
        orig_fmt = normalize_format_name(orig_fmt)
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
        if not img.allGray():
            changed = True
            img = grayscale_image(img)
    if path is None:
        return image_to_data(img, compression_quality, fmt) if changed else data
    with lopen(path, 'wb') as f:
        f.write(image_to_data(img, compression_quality, fmt) if changed else data)
# }}}

# Overlaying images {{{


def blend_on_canvas(img, width, height, bgcolor='#ffffff'):
    ' Blend the `img` onto a canvas with the specified background color and size '
    w, h = img.width(), img.height()
    scaled, nw, nh = fit_image(w, h, width, height)
    if scaled:
        img = img.scaled(nw, nh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        w, h = nw, nh
    canvas = QImage(width, height, QImage.Format_RGB32)
    canvas.fill(QColor(bgcolor))
    overlay_image(img, canvas, (width - w)//2, (height - h)//2)
    return canvas


class Canvas(object):

    def __init__(self, width, height, bgcolor='#ffffff'):
        self.img = QImage(width, height, QImage.Format_RGB32)
        self.img.fill(QColor(bgcolor))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def compose(self, img, x=0, y=0):
        img = image_from_data(img)
        overlay_image(img, self.img, x, y)

    def export(self, fmt='JPEG', compression_quality=95):
        return image_to_data(self.img, compression_quality=compression_quality, fmt=fmt)


def create_canvas(width, height, bgcolor='#ffffff'):
    'Create a blank canvas of the specified size and color '
    img = QImage(width, height, QImage.Format_RGB32)
    img.fill(QColor(bgcolor))
    return img


def overlay_image(img, canvas=None, left=0, top=0):
    ' Overlay the `img` onto the canvas at the specified position '
    if canvas is None:
        canvas = QImage(img.size(), QImage.Format_RGB32)
        canvas.fill(Qt.white)
    left, top = int(left), int(top)
    imageops.overlay(img, canvas, left, top)
    return canvas


def texture_image(canvas, texture):
    ' Repeatedly tile the image `texture` across and down the image `canvas` '
    if canvas.hasAlphaChannel():
        canvas = blend_image(canvas)
    return imageops.texture_image(canvas, texture)


def blend_image(img, bgcolor='#ffffff'):
    ' Used to convert images that have semi-transparent pixels to opaque by blending with the specified color '
    canvas = QImage(img.size(), QImage.Format_RGB32)
    canvas.fill(QColor(bgcolor))
    overlay_image(img, canvas)
    return canvas
# }}}

# Image borders {{{


def add_borders_to_image(img, left=0, top=0, right=0, bottom=0, border_color='#ffffff'):
    img = image_from_data(img)
    if not (left > 0 or right > 0 or top > 0 or bottom > 0):
        return img
    canvas = QImage(img.width() + left + right, img.height() + top + bottom, QImage.Format_RGB32)
    canvas.fill(QColor(border_color))
    overlay_image(img, canvas, left, top)
    return canvas


def remove_borders_from_image(img, fuzz=None):
    ''' Try to auto-detect and remove any borders from the image. Returns
    the image itself if no borders could be removed. `fuzz` is a measure of
    what colors are considered identical (must be a number between 0 and 255 in
    absolute intensity units). Default is from a tweak whose default value is 10. '''
    fuzz = tweaks['cover_trim_fuzz_value'] if fuzz is None else fuzz
    img = image_from_data(img)
    ans = imageops.remove_borders(img, max(0, fuzz))
    return ans if ans.size() != img.size() else img
# }}}

# Cropping/scaling of images {{{


def resize_image(img, width, height):
    return img.scaled(int(width), int(height), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def resize_to_fit(img, width, height):
    img = image_from_data(img)
    resize_needed, nw, nh = fit_image(img.width(), img.height(), width, height)
    if resize_needed:
        resize_image(img, nw, nh)
    return resize_needed, img


def clone_image(img):
    ''' Returns a shallow copy of the image. However, the underlying data buffer
    will be automatically copied-on-write '''
    return QImage(img)


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


def crop_image(img, x, y, width, height):
    '''
    Return the specified section of the image.

    :param x, y: The top left corner of the crop box
    :param width, height: The width and height of the crop box. Note that if
    the crop box exceeds the source images dimensions, width and height will be
    auto-truncated.
    '''
    img = image_from_data(img)
    width = min(width, img.width() - x)
    height = min(height, img.height() - y)
    return img.copy(x, y, width, height)

# }}}

# Image transformations {{{


def grayscale_image(img):
    return imageops.grayscale(image_from_data(img))


def set_image_opacity(img, alpha=0.5):
    ''' Change the opacity of `img`. Note that the alpha value is multiplied to
    any existing alpha values, so you cannot use this function to convert a
    semi-transparent image to an opaque one. For that use `blend_image()`. '''
    return imageops.set_opacity(image_from_data(img), alpha)


def flip_image(img, horizontal=False, vertical=False):
    return image_from_data(img).mirrored(horizontal, vertical)


def image_has_transparent_pixels(img):
    ' Return True iff the image has at least one semi-transparent pixel '
    img = image_from_data(img)
    if img.isNull():
        return False
    return imageops.has_transparent_pixels(img)


def rotate_image(img, degrees):
    t = QTransform()
    t.rotate(degrees)
    return image_from_data(img).transformed(t)


def gaussian_sharpen_image(img, radius=0, sigma=3, high_quality=True):
    return imageops.gaussian_sharpen(image_from_data(img), max(0, radius), sigma, high_quality)


def gaussian_blur_image(img, radius=-1, sigma=3):
    return imageops.gaussian_blur(image_from_data(img), max(0, radius), sigma)


def despeckle_image(img):
    return imageops.despeckle(image_from_data(img))


def oil_paint_image(img, radius=-1, high_quality=True):
    return imageops.oil_paint(image_from_data(img), radius, high_quality)


def normalize_image(img):
    return imageops.normalize(image_from_data(img))


def quantize_image(img, max_colors=256, dither=True, palette=''):
    ''' Quantize the image to contain a maximum of `max_colors` colors. By
    default a palette is chosen automatically, if you want to use a fixed
    palette, then pass in a list of color names in the `palette` variable. If
    you, specify a palette `max_colors` is ignored. Note that it is possible
    for the actual number of colors used to be less than max_colors.

    :param max_colors: Max. number of colors in the auto-generated palette. Must be between 2 and 256.
    :param dither: Whether to use dithering or not. dithering is almost always a good thing.
    :param palette: Use a manually specified palette instead. For example: palette='red green blue #eee'
    '''
    img = image_from_data(img)
    if img.hasAlphaChannel():
        img = blend_image(img)
    if palette and isinstance(palette, basestring):
        palette = palette.split()
    return imageops.quantize(img, max_colors, dither, [QColor(x).rgb() for x in palette])

# }}}

# Optimization of images {{{


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
    from calibre.utils.speedups import ReadOnlyFileBuffer
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
# }}}


def test():  # {{{
    from calibre.ptempfile import TemporaryDirectory
    from calibre import CurrentDir
    from glob import glob
    img = image_from_data(I('lt.png', data=True, allow_user_override=False))
    with TemporaryDirectory() as tdir, CurrentDir(tdir):
        save_image(img, 'test.jpg')
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
    quantize_image(img)
    oil_paint_image(img)
    gaussian_sharpen_image(img)
    gaussian_blur_image(img)
    despeckle_image(img)
    remove_borders_from_image(img)
    image_to_data(img, fmt='GIF')
    raw = subprocess.Popen([get_exe_path('JxrDecApp'), '-h'], creationflags=0x08 if iswindows else 0, stdout=subprocess.PIPE).stdout.read()
    if b'JPEG XR Decoder Utility' not in raw:
        raise SystemExit('Failed to run JxrDecApp')
# }}}


if __name__ == '__main__':  # {{{
    args = sys.argv[1:]
    infile = args.pop(0)
    img = image_from_data(lopen(infile, 'rb').read())
    func = globals()[args[0]]
    kw = {}
    args.pop(0)
    outf = None
    while args:
        k = args.pop(0)
        if '=' in k:
            n, v = k.partition('=')[::2]
            if v in ('True', 'False'):
                v = True if v == 'True' else False
            try:
                v = int(v)
            except Exception:
                try:
                    v = float(v)
                except Exception:
                    pass
            kw[n] = v
        else:
            outf = k
    if outf is None:
        bn = os.path.basename(infile)
        outf = bn.rpartition('.')[0] + '.' + '-output' + bn.rpartition('.')[-1]
    img = func(img, **kw)
    with lopen(outf, 'wb') as f:
        f.write(image_to_data(img, fmt=outf.rpartition('.')[-1]))
# }}}
