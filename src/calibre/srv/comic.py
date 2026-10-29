#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

"""Read CBZ comics page by page using Readium Divina manifests."""

import hashlib
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache, partial
from typing import Any
from urllib.parse import urlencode

from calibre.db.errors import NoSuchFormat
from calibre.ebooks.comic.input import find_pages
from calibre.srv.content import create_file_copy
from calibre.srv.errors import BookNotFound, HTTPNotFound
from calibre.srv.handler import Context
from calibre.srv.http_response import ETaggedDynamicOutput, RequestData, StaticOutput
from calibre.srv.opds import DIVINA_MIME, RequestContext, opds2_metadata
from calibre.srv.routes import endpoint
from calibre.utils.img import image_from_data, image_to_data
from calibre.utils.imghdr import what
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


@lru_cache(maxsize=1)
def convertible_types() -> tuple[str, ...]:
    from qt.core import QImageWriter

    supported = {bytes(x).decode('ascii').lower() for x in QImageWriter.supportedImageFormats()}
    return tuple(IMAGE_TYPES[x] for x in ('jpeg', 'webp', 'avif', 'jxl') if x in supported)


@lru_cache(maxsize=1)
def readable_types() -> frozenset[str]:
    from qt.core import QImageReader

    return frozenset(IMAGE_TYPES[ext] for name in QImageReader.supportedImageFormats() if (ext := bytes(name).decode('ascii').lower()) in IMAGE_TYPES)


def page_types(name: str) -> tuple[str, tuple[str, ...]]:
    native = IMAGE_TYPES[name.rpartition('.')[-1].lower()]
    if native not in readable_types():
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
        st = os.fstat(source.fileno())
        revision = hashlib.sha256(f'{c.db.library_id}:{st.st_mtime_ns}:{st.st_size}'.encode()).hexdigest()[:24]
        try:
            archive = ZipFile(source)
        except BadZipfile:
            raise HTTPNotFound('The CBZ file is not a valid ZIP archive')
        with archive:
            yield c, archive, revision


def comic_pages(archive: ZipFile) -> list[str]:
    return find_pages([x.filename for x in archive.infolist() if not x.filename.endswith('/')])


@endpoint('/comic-manifest/{book_id}', types={'book_id': int})
def comic_manifest(ctx: Context, rd: RequestData, book_id: int) -> StaticOutput:
    with open_comic(ctx, rd, book_id) as (c, archive, revision):
        names = comic_pages(archive)
        if not names:
            raise HTTPNotFound('The comic has no page images')
        metadata = opds2_metadata(c.db.get_metadata(book_id), c)
        metadata.pop('@type', None)
        metadata.update(conformsTo=DIVINA_PROFILE, numberOfPages=len(names))
        reading_order = []

        def link(page: int, native: str, media_type: str) -> dict[str, str]:
            href = c.url_for('/comic-page', book_id=book_id, page=page)
            query = {'v': revision}
            if media_type != native:
                query['type'] = media_type
            return {'href': href + '&' + urlencode(query), 'type': media_type}

        for page, name in enumerate(names):
            native, types = page_types(name)
            resource: dict[str, Any] = link(page, native, types[0])
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
            data = archive.read(name)
        except (BadZipfile, RuntimeError, NotImplementedError) as err:
            raise HTTPNotFound(f'Cannot read page {page}: {err}')
        actual_type = IMAGE_TYPES.get(what(None, data))
        if actual_type is None:
            raise HTTPNotFound(f'Page {page} is not a supported image')
        if media_type != actual_type and actual_type not in readable_types():
            raise HTTPNotFound(f'Page {page} cannot be converted to {media_type}')

    def render() -> bytes:
        if media_type == actual_type:
            return data
        fmt = next(ext for ext, mt in IMAGE_TYPES.items() if mt == media_type)
        return image_to_data(image_from_data(data), compression_quality=90, fmt=fmt)

    # The image representation has its own ETag. Conditional requests can skip
    # transcoding, and replacing the archive invalidates every page URL.
    etag = hashlib.sha256(f'comic-page-v1:{revision}:{page}:{media_type}'.encode()).hexdigest()
    rd.outheaders['Cache-Control'] = 'private, must-revalidate'
    return rd.etagged_dynamic_response(etag, render, content_type=media_type)
