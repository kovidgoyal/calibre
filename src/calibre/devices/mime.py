# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from calibre import guess_type


def _mt(path: str) -> str:
    mt = guess_type(path)[0]
    if not mt:
        mt = 'application/octet-stream'
    return mt


def mime_type_ext(ext: str) -> str:
    if not ext.startswith('.'):
        ext = '.' + ext
    return _mt('a' + ext)


def mime_type_path(path: str) -> str:
    return _mt(path)
