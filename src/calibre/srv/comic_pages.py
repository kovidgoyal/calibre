#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Access to the individual pages of comic book archives, used to stream comics
# page by page with the OPDS Page Streaming Extension, see
# https://github.com/anansi-project/opds-pse

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


# The media types of the image formats pages can be sent in, keyed by the
# format names used by identify()
MEDIA_TYPES = {
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'avif': 'image/avif',
    'jxl': 'image/jxl',
}
# The type pages are sent in to clients that do not ask for one, it is the
# type in the stream link in the OPDS feed
DEFAULT_MEDIA_TYPE = 'image/jpeg'


def parse_accept(header: str | None) -> dict[str, float]:
    "The media types in an HTTP Accept header, mapped to their quality values"
    ans = {}
    for item in (header or '').split(','):
        mt, *params = (x.strip() for x in item.split(';'))
        if not mt:
            continue
        q = 1.0
        for param in params:
            name, _, value = param.partition('=')
            if name.strip().lower() == 'q':
                try:
                    q = min(1.0, max(0.0, float(value)))
                except ValueError:
                    q = 0.0
        ans[mt.lower()] = q
    return ans


def acceptable_types(header: str | None) -> dict[str, float]:
    """
    The media types of the image formats the client accepts, mapped to their
    quality values. Clients that do not list specific image types get the
    default type, as specified by OPDS-PSE 1.3.
    """
    accept = parse_accept(header)
    if not any(mt in accept for mt in MEDIA_TYPES.values()):
        if not accept or any(accept.get(x, 0) > 0 for x in ('*/*', 'image/*')):
            return {DEFAULT_MEDIA_TYPE: 1.0}
        return {}
    wildcard = max(accept.get('*/*', 0), accept.get('image/*', 0))
    ans = {mt: accept.get(mt, wildcard) for mt in MEDIA_TYPES.values()}
    return {mt: q for mt, q in ans.items() if q > 0}


@lru_cache(maxsize=2)
def writable_types() -> tuple[str, ...]:
    "The media types pages can be converted to, in the order they are preferred when the client has no preference"
    from qt.core import QImageWriter

    supported = {bytes(x).decode('ascii').lower() for x in QImageWriter.supportedImageFormats()}
    # JPEG first as it is fast to encode, GIF is not used as it has too few colors
    return tuple(MEDIA_TYPES[fmt] for fmt in ('jpeg', 'webp', 'jxl', 'png') if fmt in supported)


def page_for_client(data: bytes, max_width: int = 0, accept: str | None = None) -> tuple[bytes, str]:
    """
    Return the page as an image in one of the formats the client accepts, as
    specified by its Accept header, no wider than max_width, if specified.
    Raise NotAcceptable if the page cannot be sent in any of the formats.
    """
    from calibre.utils.imghdr import identify

    acceptable = acceptable_types(accept)
    fmt, width, height = identify(data)
    mt = MEDIA_TYPES.get(fmt)
    if mt in acceptable and (max_width <= 0 or 0 < width <= max_width):
        # Send the image as it is stored, without converting it
        return data, mt
    writable = writable_types()
    candidates = sorted((t for t in writable if t in acceptable), key=lambda t: (-acceptable[t], writable.index(t)))
    if not candidates:
        raise NotAcceptable(f'Cannot send the page in any of the formats: {", ".join(acceptable) or accept}')
    mt = candidates[0]
    from qt.core import Qt

    from calibre.utils.img import image_from_data, image_to_data

    img = image_from_data(data)
    if 0 < max_width < img.width():
        img = img.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    out_fmt = next(f for f, t in MEDIA_TYPES.items() if t == mt)
    return image_to_data(img, compression_quality=90, fmt=out_fmt), mt


class NotAcceptable(ValueError):
    pass
