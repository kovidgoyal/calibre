#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.constants import plugins

_magick, _merr = plugins['magick']

if _magick is None:
    raise RuntimeError('Failed to load ImageMagick: '+_merr)

# class ImageMagick {{{
_initialized = False
def initialize():
    global _initialized
    if not _initialized:
        _magick.genesis()
        _initialized = True

def finalize():
    global _initialized
    if _initialized:
        _magick.terminus()
        _initialized = False

class ImageMagick(object):

    def __enter__(self):
        initialize()

    def __exit__(self, *args):
        finalize()
# }}}

class Image(_magick.Image):

    def open(self, path_or_file):
        data = path_or_file
        if hasattr(data, 'read'):
            data = data.read()
        else:
            data = open(data, 'rb').read()
        self.load(data)

    @dynamic_property
    def format(self):
        def fget(self):
            ans = super(Image, self).format
            return ans.decode('utf-8', 'ignore').lower()
        def fset(self, val):
            super(Image, self).format = str(val)
        return property(fget=fget, fset=fset, doc=_magick.Image.format.__doc__)


    @dynamic_property
    def size(self):
        def fget(self):
            return super(Image, self).size
        def fset(self, val):
            filter = 'CatromFilter'
            if len(val) > 2:
                filter = val[2]
            filter = int(getattr(_magick, filter))
            blur = 1.0
            if len(val) > 3:
                blur = float(val[3])
            super(Image, self).format = (int(val[0]), int(val[1]), filter,
                    blur)
        return property(fget=fget, fset=fset, doc=_magick.Image.size.__doc__)


    def save(self, path, format=None):
        if format is None:
            ext = os.path.splitext(path)[1]
            if len(ext) < 2:
                raise ValueError('No format specified')
            format = ext[1:]

        with open(path, 'wb') as f:
            f.write(self.export(format))
