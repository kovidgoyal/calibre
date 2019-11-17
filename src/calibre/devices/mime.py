
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre import guess_type


def _mt(path):
    mt = guess_type(path)[0]
    if not mt:
        mt = 'application/octet-stream'
    return mt


def mime_type_ext(ext):
    if not ext.startswith('.'):
        ext = '.'+ext
    return _mt('a'+ext)


def mime_type_path(path):
    return _mt(path)
