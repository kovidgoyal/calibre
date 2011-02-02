#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import glob

from calibre.constants import plugins, iswindows, filesystem_encoding
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir
from calibre.utils.magick import Image, PixelWand

class Unavailable(Exception):
    pass

class NoRaster(Exception):
    pass

def extract_raster_image(wmf_data):
    try:
        wmf, wmf_err = plugins['wmf']
    except KeyError:
        raise Unavailable('libwmf not available on this platform')
    if wmf_err:
        raise Unavailable(wmf_err)

    if iswindows:
        import sys, os
        appdir = sys.app_dir
        if isinstance(appdir, unicode):
            appdir = appdir.encode(filesystem_encoding)
        fdir = os.path.join(appdir, 'wmffonts')
        wmf.set_font_dir(fdir)

    data = ''

    with TemporaryDirectory('wmf2png') as tdir:
        with CurrentDir(tdir):
            wmf.render(wmf_data)

            images = list(sorted(glob.glob('*.png')))
            if not images:
                raise NoRaster('No raster images in WMF')
            data = open(images[0], 'rb').read()

    im = Image()
    im.load(data)
    pw = PixelWand()
    pw.color = '#ffffff'
    im.rotate(pw, 180)

    return im.export('png')


