#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

"""Read CBZ comics page by page using Readium Divina manifests."""

import hashlib
import json
import zlib
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache, partial
from typing import TypedDict
from urllib.parse import urlencode

from lxml import etree

from calibre.db.errors import NoSuchFormat
from calibre.ebooks.comic.input import find_pages
from calibre.srv.content import create_file_copy
from calibre.srv.errors import BookNotFound, HTTPNotFound
from calibre.srv.handler import Context
from calibre.srv.http_response import ETaggedDynamicOutput, RequestData, StaticOutput, parse_if_none_match
from calibre.srv.opds import DIVINA_MIME, RequestContext, opds2_metadata
from calibre.srv.routes import endpoint
from calibre.utils.img import image_from_data, image_to_data
from calibre.utils.imghdr import what
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.utils.zipfile import BadZipfile, ZipFile

DIVINA_PROFILE = 'https://readium.org/webpub-manifest/profiles/divina'
IMAGE_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'avif': 'image/avif',
    'jxl': 'image/jxl',
}
WIDELY_SUPPORTED = frozenset(('image/jpeg', 'image/png', 'image/gif', 'image/webp'))
# Pages are read into memory to serve or transcode them. Refuse larger ones, as
# the sizes in ZIP headers cannot be trusted to limit decompression.
MAX_PAGE_SIZE = 128 * 1024 * 1024
MAX_COMICINFO_SIZE = 1024 * 1024


class Link(TypedDict):
    href: str
    type: str


class PageLink(Link, total=False):
    alternate: list[Link]


@lru_cache(maxsize=1)
def convertible_types() -> tuple[str, ...]:
    from qt.core import QImageWriter

    supported = {bytes(x).decode('ascii').lower() for x in QImageWriter.supportedImageFormats()}
    return tuple(IMAGE_TYPES[x] for x in ('jpeg', 'webp', 'jxl') if x in supported)


@lru_cache(maxsize=1)
def readable_types() -> frozenset[str]:
    from qt.core import QImageReader

    return frozenset(IMAGE_TYPES[ext] for name in QImageReader.supportedImageFormats() if (ext := bytes(name).decode('ascii').lower()) in IMAGE_TYPES)


def page_types(name: str) -> tuple[str, tuple[str, ...]]:
    native = IMAGE_TYPES[name.rpartition('.')[-1].lower()]
    # GIFs may be animated, and transcoding would keep only the first frame
    if native == 'image/gif' or native not in readable_types():
        return native, (native,)
    primary = native if native in WIDELY_SUPPORTED else 'image/jpeg'
    types = dict.fromkeys((primary, native, *convertible_types()))
    return native, tuple(types)


@contextmanager
def open_comic(ctx: Context, rd: RequestData, book_id: int) -> Generator[tuple[RequestContext, ZipFile, str]]:
    c = RequestContext(ctx, rd, strict_library_id=True)
    with c.db.safe_read_lock:
        if not ctx.has_id(rd, c.db, book_id):
            raise BookNotFound(book_id, c.db)
        fm = c.db.format_metadata(book_id, 'CBZ', allow_cache=False)
        if not fm:
            raise HTTPNotFound(f'No CBZ format for book {book_id}')
        # Version page URLs by the library file, not by its copy in the
        # download cache, which is recreated when the server restarts.
        revision = hashlib.sha256(f'{c.db.library_id}:{fm["mtime"].isoformat()}:{fm["size"]}'.encode()).hexdigest()[:24]
        try:
            # Share the normal download cache, rather than accessing the library
            # path directly or holding its lock while serving page images.
            source = create_file_copy(
                ctx,
                rd,
                'fmt',
                c.library_id,
                book_id,
                'cbz',
                fm['mtime'],
                partial(c.db.copy_format_to, book_id, 'CBZ'),
            ).output
        except NoSuchFormat:
            raise HTTPNotFound(f'No CBZ format for book {book_id}')
    with source:
        try:
            archive = ZipFile(source)
        except BadZipfile:
            raise HTTPNotFound('The CBZ file is not a valid ZIP archive')
        with archive:
            yield c, archive, revision


def comic_pages(archive: ZipFile) -> list[str]:
    return find_pages([x.filename for x in archive.infolist() if not x.filename.endswith('/')])


def comic_is_right_to_left(archive: ZipFile) -> bool:
    info = next((x for x in archive.infolist() if x.filename.lower() == 'comicinfo.xml'), None)
    if info is None:
        return False
    try:
        with archive.open(info) as f:
            raw = f.read(MAX_COMICINFO_SIZE + 1)
        if len(raw) > MAX_COMICINFO_SIZE:
            return False
        root = safe_xml_fromstring(raw, recover=False)
    except BadZipfile, RuntimeError, NotImplementedError, zlib.error, EOFError, etree.XMLSyntaxError:
        # ComicInfo is optional. Broken or unreadable metadata must not prevent
        # opening a comic whose page images can still be read.
        return False
    return root.tag == 'ComicInfo' and (root.findtext('Manga') or '').strip() == 'YesAndRightToLeft'


@endpoint('/comic-manifest/{book_id}', types={'book_id': int})
def comic_manifest(ctx: Context, rd: RequestData, book_id: int) -> StaticOutput:
    with open_comic(ctx, rd, book_id) as (c, archive, revision):
        names = comic_pages(archive)
        if not names:
            raise HTTPNotFound('The comic has no page images')
        metadata = opds2_metadata(c.db.get_metadata(book_id), c)
        metadata.pop('@type', None)
        metadata.update(conformsTo=DIVINA_PROFILE, numberOfPages=len(names))
        if comic_is_right_to_left(archive):
            metadata['readingProgression'] = 'rtl'

        assert ctx.url_for is not None

        def link(page: int, native: str, media_type: str) -> Link:
            query = {'library_id': c.library_id, 'v': revision}
            if media_type != native:
                query['type'] = media_type
            href = ctx.url_for('/comic-page', book_id=book_id, page=page) + '?' + urlencode(query)
            return {'href': href, 'type': media_type}

        reading_order: list[PageLink] = []
        for page, name in enumerate(names):
            native, types = page_types(name)
            resource: PageLink = {**link(page, native, types[0])}
            if len(types) > 1:
                resource['alternate'] = [link(page, native, mt) for mt in types[1:]]
            reading_order.append(resource)
        manifest = {
            '@context': 'https://readium.org/webpub-manifest/context.jsonld',
            'metadata': metadata,
            'links': [{'rel': 'self', 'href': c.url_for('/comic-manifest', book_id=book_id), 'type': DIVINA_MIME}],
            'readingOrder': reading_order,
        }
    rd.outheaders['Content-Type'] = DIVINA_MIME
    rd.outheaders['Cache-Control'] = 'private, must-revalidate'
    return StaticOutput(json.dumps(manifest, ensure_ascii=False).encode('utf-8'))


@endpoint('/comic-page/{book_id}/{page}', types={'book_id': int, 'page': int})
def comic_page(ctx: Context, rd: RequestData, book_id: int, page: int) -> ETaggedDynamicOutput:
    with open_comic(ctx, rd, book_id) as (c, archive, revision):
        if rd.query.get('v', revision) != revision:
            raise HTTPNotFound('The comic has changed, reload its manifest')
        names = comic_pages(archive)
        if not 0 <= page < len(names):
            raise HTTPNotFound(f'Page {page} does not exist')
        name = names[page]
        native, types = page_types(name)
        media_type = rd.query.get('type') or native
        if media_type not in types:
            raise HTTPNotFound(f'Page {page} is not available as {media_type}')
        try:
            with archive.open(name) as f:
                data = f.read(MAX_PAGE_SIZE + 1)
        except (BadZipfile, RuntimeError, NotImplementedError, zlib.error) as err:
            raise HTTPNotFound(f'Cannot read page {page}: {err}')
        if len(data) > MAX_PAGE_SIZE:
            raise HTTPNotFound(f'Page {page} is too large')
        actual_type = IMAGE_TYPES.get(what(None, data))
        if actual_type is None:
            raise HTTPNotFound(f'Page {page} is not a supported image')
        if media_type != actual_type and actual_type not in readable_types():
            raise HTTPNotFound(f'Page {page} cannot be converted to {media_type}')

    # The image representation has its own ETag. Conditional requests can skip
    # transcoding, and replacing the archive invalidates every page URL.
    digest = hashlib.sha256(f'comic-page-v1:{revision}:{page}:{media_type}'.encode()).hexdigest()
    etag = f'"{digest}"'
    none_match = parse_if_none_match(rd.inheaders.get('If-None-Match', ''))
    if media_type != actual_type and etag not in none_match and '*' not in none_match:
        # Transcode here, in a worker thread, as the function passed to
        # etagged_dynamic_response() is called on the server's event loop
        fmt = next(ext for ext, mt in IMAGE_TYPES.items() if mt == media_type)
        try:
            data = image_to_data(image_from_data(data), compression_quality=90, fmt=fmt)
        except ValueError as err:
            raise HTTPNotFound(f'Cannot convert page {page} to {media_type}: {err}')
    # URLs with a revision always refer to the same image, so let clients cache
    # them instead of revalidating every page turn
    rd.outheaders['Cache-Control'] = 'private, max-age=31536000, immutable' if 'v' in rd.query else 'private, must-revalidate'
    return rd.etagged_dynamic_response(etag, lambda: data, content_type=media_type)
