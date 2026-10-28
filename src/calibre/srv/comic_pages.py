#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Access to the individual pages of comic book archives, used to read comics
# page by page from the OPDS 2.0 catalog of the Content server

import os
from collections import OrderedDict
from functools import lru_cache
from threading import Lock

COMIC_FORMATS = ('CBZ', 'CBR', 'CB7')
MAX_CACHED_BOOKS = 512
cache_lock = Lock()
page_names_cache: OrderedDict[tuple[str, float, int], tuple[str, ...]] = OrderedDict()


def archive_type(path: str) -> str:
    # Comic files are often misnamed, so use the contents to find the type
    with open(path, 'rb') as f:
        magic = f.read(8)
    if magic.startswith(b'PK'):
        return 'zip'
    if magic.startswith(b'Rar!'):
        return 'rar'
    if magic.startswith(b"7z\xbc\xaf'\x1c"):
        return '7z'
    raise ValueError(f'{path} is not a supported comic archive')


def archive_names(path: str) -> list[str]:
    typ = archive_type(path)
    if typ == 'zip':
        from calibre.utils.zipfile import ZipFile

        with ZipFile(path) as zf:
            return [i.filename for i in zf.infolist() if not i.filename.endswith('/')]
    if typ == 'rar':
        from calibre.utils.unrar import names

        return list(names(path))
    from calibre.utils.seven_zip import names

    return list(names(path))


def page_names(path: str) -> tuple[str, ...]:
    "The names of the page images in the archive, in reading order, as for the Comic Input conversion"
    st = os.stat(path)
    key = path, st.st_mtime, st.st_size
    with cache_lock:
        if (ans := page_names_cache.get(key)) is not None:
            page_names_cache.move_to_end(key)
            return ans
    from calibre.ebooks.comic.input import find_pages

    ans = tuple(find_pages(archive_names(path)))
    with cache_lock:
        page_names_cache[key] = ans
        while len(page_names_cache) > MAX_CACHED_BOOKS:
            page_names_cache.popitem(last=False)
    return ans


def read_page(path: str, name: str) -> bytes:
    typ = archive_type(path)
    if typ == 'zip':
        from calibre.utils.zipfile import ZipFile

        with ZipFile(path) as zf:
            return zf.read(name)
    if typ == 'rar':
        from calibre.utils.unrar import extract_member

        ans = extract_member(path, match=None, name=name)
        if ans is None:
            raise KeyError(name)
        return ans[1]
    from calibre.utils.seven_zip import open_archive, read_file

    with open_archive(path) as ar:
        return read_file(ar, name)


# The media types of the image formats of pages, keyed by file extension
MEDIA_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'avif': 'image/avif',
    'jxl': 'image/jxl',
}
# The types of pages that all clients can be expected to display, pages in
# other types are also offered converted to JPEG
WIDELY_SUPPORTED = frozenset(('image/jpeg', 'image/png', 'image/gif', 'image/webp'))


def page_media_type(name: str) -> str:
    return MEDIA_TYPES.get(name.rpartition('.')[-1].lower(), 'image/jpeg')


@lru_cache(maxsize=2)
def convertible_types() -> tuple[str, ...]:
    "The media types pages can be converted to"
    from qt.core import QImageWriter

    supported = {bytes(x).decode('ascii').lower() for x in QImageWriter.supportedImageFormats()}
    # PNG and GIF are not used, as they are much larger for the photographic
    # images in most comics, or have too few colors
    return tuple(MEDIA_TYPES[fmt] for fmt in ('jpeg', 'webp', 'jxl') if fmt in supported)


def page_types(name: str) -> tuple[str, list[str]]:
    """
    The media type of the page as stored in the archive, followed by the
    media types it is available in, the first of which all clients can be
    expected to display.
    """
    native = page_media_type(name)
    primary = native if native in WIDELY_SUPPORTED else 'image/jpeg'
    ans = [primary]
    if native != primary:
        ans.append(native)
    ans.extend(t for t in convertible_types() if t not in ans)
    return native, ans


def convert_page(data: bytes, media_type: str) -> bytes:
    "Convert the page to the specified image type, which must be one of convertible_types()"
    from calibre.utils.img import image_from_data, image_to_data

    fmt = next(ext for ext, t in MEDIA_TYPES.items() if t == media_type)
    return image_to_data(image_from_data(data), compression_quality=90, fmt=fmt)
