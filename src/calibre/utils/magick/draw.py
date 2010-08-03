#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.utils.magick import Image, create_canvas

def save_cover_data_to(data, path, bgcolor='white', resize_to=None):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Composes the image onto a blank canvas so as to
    properly convert transparent images.
    '''
    img = Image()
    img.load(data)
    if resize_to is not None:
        img.size = (resize_to[0], resize_to[1])
    canvas = create_canvas(img.size[0], img.size[1], bgcolor)
    canvas.compose(img)
    canvas.save(path)

def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    img = Image()
    img.load(data)
    width, height = img.size
    fmt = img.format
    return (width, height, fmt)

def identify(path):
    '''
    Identify the image at path. Returns a 3-tuple
    (width, height, format)
    or raises an Exception.
    '''
    data = open(path, 'rb').read()
    return identify_data(data)


