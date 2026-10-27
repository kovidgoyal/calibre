#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Access to the individual pages of comic book archives, used to stream comics
# page by page with the OPDS Page Streaming Extension, see
# https://github.com/anansi-project/opds-pse

import os
from collections import OrderedDict
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


def page_as_jpeg(data: bytes, max_width: int = 0) -> bytes:
    "Return the page as JPEG data, no wider than max_width, if specified"
    from calibre.utils.imghdr import identify

    fmt, width, height = identify(data)
    if fmt == 'jpeg' and (max_width <= 0 or 0 < width <= max_width):
        return data
    from calibre.utils.img import image_from_data, image_to_data, scale_image

    if max_width > 0:
        img = image_from_data(data)
        if img.width() > max_width:
            # Only the width is limited, so use a height that does not
            # constrain the scaling
            return scale_image(img, width=max_width, height=img.height() * 10, compression_quality=90)[-1]
        return image_to_data(img, compression_quality=90)
    return image_to_data(image_from_data(data), compression_quality=90)
