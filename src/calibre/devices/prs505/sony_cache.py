#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import os
import time
from datetime import date
from typing import TYPE_CHECKING

from calibre import fsync, guess_type, prints
from calibre.constants import DEBUG, preferred_encoding
from calibre.devices.errors import DeviceError
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import authors_to_sort_string, authors_to_string, title_sort
from calibre.prints import debug_print
from calibre.utils.localization import _
from polyglot.binary import from_base64_bytes

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from lxml.etree import _Element

    from calibre.devices.interface import BookList
    from calibre.ebooks.metadata.book.base import Metadata

'''
cacheExt.xml

Periodical identifier sample from a PRS-650:

<?xml version="1.0" encoding="UTF-8"?>
<cacheExt xmlns="http://www.sony.com/xmlns/product/prs/device/1">
    <text conformsTo="http://xmlns.sony.net/e-book/prs/periodicals/1.0/newspaper/1.0" periodicalName="The Atlantic"
    description="Current affairs and politics focused on the US" publicationDate="Tue, 19 Oct 2010 00:00:00 GMT"
    path="database/media/books/calibre/Atlantic [Mon, 18 Oct 2010], The - calibre_1701.epub">
        <thumbnail width="167" height="217">main_thumbnail.jpg</thumbnail>
    </text>
</cacheExt>

'''

# Utility functions {{{
EMPTY_CARD_CACHE = b'''\
<?xml version="1.0" encoding="UTF-8"?>
<cache xmlns="http://www.kinoma.com/FskCache/1">
</cache>
'''

EMPTY_EXT_CACHE = b'''\
<?xml version="1.0" encoding="UTF-8"?>
<cacheExt xmlns="http://www.sony.com/xmlns/product/prs/device/1">
</cacheExt>
'''

MIME_MAP = {
    'lrf': 'application/x-sony-bbeb',
    'lrx': 'application/x-sony-bbeb',
    'rtf': 'application/rtf',
    'pdf': 'application/pdf',
    'txt': 'text/plain',
    'epub': 'application/epub+zip',
}

DAY_MAP = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
MONTH_MAP = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
INVERSE_DAY_MAP = dict(zip(DAY_MAP.values(), DAY_MAP.keys()))
INVERSE_MONTH_MAP = dict(zip(MONTH_MAP.values(), MONTH_MAP.keys()))


def strptime(src: str) -> time.struct_time:
    parts = src.strip().split()
    parts[0] = str(DAY_MAP[parts[0][:-1]]) + ','
    parts[2] = str(MONTH_MAP[parts[2]])
    return time.strptime(' '.join(parts), '%w, %d %m %Y %H:%M:%S %Z')


def strftime(epoch: float | time.struct_time, zone: Callable[..., time.struct_time] = time.localtime) -> str:
    try:
        src = time.strftime('%w, %d %m %Y %H:%M:%S GMT', zone(epoch)).split()
    except Exception:
        src = time.strftime('%w, %d %m %Y %H:%M:%S GMT', zone()).split()

    src[0] = INVERSE_DAY_MAP[int(src[0][:-1])] + ','
    src[2] = INVERSE_MONTH_MAP[int(src[2])]
    return ' '.join(src)


def uuid() -> str:
    from uuid import uuid4

    return str(uuid4()).replace('-', '', 1).upper()


# }}}


class XMLCache:
    def __init__(self, paths: dict[int, str], ext_paths: dict[int, str], prefixes: dict[int, str], use_author_sort: bool) -> None:
        from calibre.utils.xml_parse import safe_xml_fromstring

        if DEBUG:
            debug_print('Building XMLCache...', paths)
        self.paths = paths
        self.prefixes = prefixes
        self.use_author_sort = use_author_sort

        # Parse XML files {{{
        self.roots: dict[int, _Element] = {}
        for source_id, path in paths.items():
            if source_id == 0:
                if not os.path.exists(path):
                    raise DeviceError(f'The SONY XML cache {repr(path)!r} does not exist. Try disconnecting and reconnecting your reader.')
                with open(path, 'rb') as f:
                    raw = f.read()
            else:
                raw = EMPTY_CARD_CACHE
                if os.access(path, os.R_OK):
                    with open(path, 'rb') as f:
                        raw = f.read()

            self.roots[source_id] = safe_xml_fromstring(xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True, verbose=DEBUG)[0])
            if self.roots[source_id] is None:
                raise Exception(f'The SONY database at {path!r} is corrupted. Try  disconnecting and reconnecting your reader.')

        self.ext_paths: dict[int, str] = {}
        self.ext_roots: dict[int, _Element] = {}
        for source_id, path in ext_paths.items():
            if not os.path.exists(path):
                try:
                    with open(path, 'wb') as f:
                        f.write(EMPTY_EXT_CACHE)
                        fsync(f)
                except Exception:
                    pass
            if os.access(path, os.W_OK):
                try:
                    with open(path, 'rb') as f:
                        self.ext_roots[source_id] = safe_xml_fromstring(xml_to_unicode(f.read(), strip_encoding_pats=True, assume_utf8=True, verbose=DEBUG)[0])
                        self.ext_paths[source_id] = path
                except Exception:
                    pass

        # }}}

        recs = self.roots[0].xpath('//*[local-name()="records"]')
        if not recs:
            raise DeviceError('The SONY XML database is corrupted (no <records>). Try disconnecting an reconnecting your reader.')
        self.record_roots: dict[int, _Element] = {}
        self.record_roots.update(self.roots)
        self.record_roots[0] = recs[0]

        self.detect_namespaces()
        debug_print('Done building XMLCache...')

    # Playlist management {{{
    def purge_broken_playlist_items(self, root: _Element) -> None:
        id_map = self.build_id_map(root)
        for pl in root.xpath('//*[local-name()="playlist"]'):
            seen: set[str] = set()
            for item in list(pl):
                id_ = item.get('id', None)
                if id_ is None or id_ in seen or id_map.get(id_, None) is None:
                    if DEBUG:
                        if id_ is None:
                            cause = 'invalid id'
                        elif id_ in seen:
                            cause = 'duplicate item'
                        else:
                            cause = 'id not found'
                        prints(
                            'Purging broken playlist item:',
                            id_,
                            'from playlist:',
                            pl.get('title', None),
                            'because:',
                            cause,
                        )
                    item.getparent().remove(item)
                    continue
                seen.add(id_)

    def prune_empty_playlists(self) -> None:
        for i, root in self.record_roots.items():
            self.purge_broken_playlist_items(root)
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                if len(playlist) == 0 or not playlist.get('title', None):
                    if DEBUG:
                        debug_print('Removing playlist id:', playlist.get('id', None), playlist.get('title', None))
                    playlist.getparent().remove(playlist)

    def ensure_unique_playlist_titles(self) -> None:
        for i, root in self.record_roots.items():
            seen: set[str] = set()
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                title = playlist.get('title', None)
                if title is None:
                    title = _('Unnamed')
                    playlist.set('title', title)
                if title in seen:
                    for i in range(2, 1000):
                        if title + str(i) not in seen:
                            title = title + str(i)
                            playlist.set('title', title)
                            seen.add(title)
                            break
                else:
                    seen.add(title)

    def build_id_playlist_map(self, bl_index: int) -> dict[str, list[str]]:
        """
        Return a map of the collections in books: {lpaths: [collection names]}
        """
        debug_print('Start build_id_playlist_map')
        self.ensure_unique_playlist_titles()
        self.prune_empty_playlists()
        debug_print('after cleaning playlists')
        root = self.record_roots[bl_index]
        if root is None:
            return {}
        id_map = self.build_id_map(root)
        playlist_map: dict[str, list[str]] = {}
        # foreach playlist, get the lpaths for the ids in it, then add to dict
        for playlist in root.xpath('//*[local-name()="playlist"]'):
            name = playlist.get('title')
            if name is None:
                debug_print('build_id_playlist_map: unnamed playlist!')
                continue
            for item in playlist:
                # translate each id into its lpath
                id_ = item.get('id', None)
                if id_ is None:
                    debug_print('build_id_playlist_map: id_ is None!')
                    continue
                bk = id_map.get(id_, None)
                if bk is None:
                    debug_print('build_id_playlist_map: book is None!', id_)
                    continue
                lpath = bk.get('path', None)
                if lpath is None:
                    debug_print('build_id_playlist_map: lpath is None!', id_)
                    continue
                if lpath not in playlist_map:
                    playlist_map[lpath] = []
                playlist_map[lpath].append(name)
        debug_print('Finish build_id_playlist_map. Found', len(playlist_map))
        return playlist_map

    def reset_existing_playlists_map(self) -> None:
        """
        Call this method before calling get_or_create_playlist in the context of
        a given job. Call it again after deleting any playlists. The current
        implementation adds all new playlists before deleting any, so that
        constraint is respected.
        """
        self._playlist_to_playlist_id_map: dict[int, dict[str, _Element]] = {}

    def get_or_create_playlist(self, bl_idx: int, title: str) -> _Element:
        # maintain a private map of playlists to their ids. Don't check if it
        # exists, because reset_existing_playlist_map must be called before it
        # is used to ensure that deleted playlists are taken into account
        root = self.record_roots[bl_idx]
        if bl_idx not in self._playlist_to_playlist_id_map:
            self._playlist_to_playlist_id_map[bl_idx] = {}
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                pl_title = playlist.get('title', None)
                if pl_title is not None:
                    self._playlist_to_playlist_id_map[bl_idx][pl_title] = playlist
        if title in self._playlist_to_playlist_id_map[bl_idx]:
            return self._playlist_to_playlist_id_map[bl_idx][title]
        debug_print('Creating playlist:', title)
        ans = root.makeelement(
            f'{{{self.namespaces[bl_idx]}}}playlist',
            nsmap=root.nsmap,
            attrib={'uuid': uuid(), 'title': title, 'id': str(self.max_id(root) + 1), 'sourceid': '1'},
        )
        root.append(ans)
        self._playlist_to_playlist_id_map[bl_idx][title] = ans
        return ans

    # }}}

    def fix_ids(self) -> None:  # {{{
        debug_print('Running fix_ids()')

        def ensure_numeric_ids(root: _Element) -> dict[str, str]:
            idmap: dict[str, str] = {}
            for x in root.xpath('child::*[@id]'):
                id_ = x.get('id')
                try:
                    id_ = int(id_)
                except Exception:
                    x.set('id', '-1')
                    idmap[id_] = '-1'

            if DEBUG and idmap:
                debug_print('Found non numeric ids:')
                debug_print(list(idmap.keys()))
            return idmap

        def remap_playlist_references(root: _Element, idmap: dict[str, str]) -> None:
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                for item in playlist.xpath('descendant::*[@id and local-name()="item"]'):
                    id_ = item.get('id')
                    if id_ in idmap:
                        item.set('id', idmap[id_])
                        if DEBUG:
                            debug_print(f'Remapping id {id_} to {idmap[id_]}')

        def ensure_media_xml_base_ids(root: _Element) -> None:
            for num, tag in enumerate(('library', 'watchSpecial')):
                for x in root.xpath(f'//*[local-name()="{tag}"]'):
                    x.set('id', str(num))

        def rebase_ids(root: _Element, base: int, sourceid: int, pl_sourceid: int) -> dict[str, str]:
            "Rebase all ids and also make them consecutive"
            for item in root.xpath('//*[@sourceid]'):
                sid = pl_sourceid if item.tag.endswith('playlist') else sourceid
                item.set('sourceid', str(sid))
            # Only rebase ids of nodes that are immediate children of the
            # record root (that way playlist/itemnodes are unaffected
            items = root.xpath('child::*[@id]')
            items.sort(key=lambda x: int(x.get('id')))
            idmap: dict[str, str] = {}
            for i, item in enumerate(items):
                old = int(item.get('id'))
                new = base + i
                if old != new:
                    item.set('id', str(new))
                    idmap[str(old)] = str(new)
            return idmap

        self.prune_empty_playlists()

        for i in sorted(self.roots.keys()):
            root = self.record_roots[i]
            if i == 0:
                ensure_media_xml_base_ids(root)

            idmap = ensure_numeric_ids(root)
            if len(idmap) > 0:
                debug_print('fix_ids: found some non-numeric ids')
                remap_playlist_references(root, idmap)
            if i == 0:
                sourceid, playlist_sid = 1, 0
                base = 0
            else:
                previous = i - 1
                if previous not in self.roots:
                    previous = 0
                max_id = self.max_id(self.roots[previous])
                sourceid = playlist_sid = max_id + 1
                base = max_id + 2
            idmap = rebase_ids(root, base, sourceid, playlist_sid)
            remap_playlist_references(root, idmap)

        last_bl = max(self.roots.keys())
        max_id = self.max_id(self.roots[last_bl])
        self.roots[0].set('nextID', str(max_id + 1))
        debug_print('Finished running fix_ids()')

    # }}}

    # Update JSON from XML {{{
    def update_booklist(self, bl: BookList, bl_index: int) -> None:
        if bl_index not in self.record_roots:
            return
        debug_print('Updating JSON cache:', bl_index)
        playlist_map = self.build_id_playlist_map(bl_index)
        root = self.record_roots[bl_index]
        lpath_map = self.build_lpath_map(root)
        for book in bl:
            record = lpath_map.get(book.lpath, None)
            if record is not None:
                for thumbnail in record.xpath('descendant::*[local-name()="thumbnail"]'):
                    for img in thumbnail.xpath('descendant::*[local-name()="jpeg"]|descendant::*[local-name()="png"]'):
                        if img.text:
                            try:
                                raw = from_base64_bytes(img.text.strip())
                            except Exception:
                                continue
                            book.thumbnail = raw
                            break
                    break
                book.device_collections = playlist_map.get(book.lpath, [])
        debug_print('Finished updating JSON cache:', bl_index)

    # }}}

    # Update XML from JSON {{{
    def update(self, booklists: dict[int, BookList], collections_attributes: Sequence[str], plugboard: object) -> None:
        debug_print('Starting update', collections_attributes)
        use_tz_var = False
        for i, booklist in booklists.items():
            playlist_map = self.build_id_playlist_map(i)
            debug_print('Updating XML Cache:', i)
            root = self.record_roots[i]
            lpath_map = self.build_lpath_map(root)
            ext_root = self.ext_roots.get(i, None)
            ext_lpath_map = None
            if ext_root is not None:
                ext_lpath_map = self.build_lpath_map(ext_root)
            gtz_count = ltz_count = 0
            use_tz_var = False
            for book in booklist:
                path = os.path.join(self.prefixes[i], *(book.lpath.split('/')))
                record = lpath_map.get(book.lpath, None)
                created = False
                if record is None:
                    created = True
                    record = self.create_text_record(root, i, book.lpath)
                if plugboard is not None:
                    newmi = book.deepcopy_metadata()
                    newmi.template_to_attribute(book, plugboard)
                    newmi.set('_new_book', getattr(book, '_new_book', False))
                    book.set('_pb_title_sort', newmi.get('title_sort', newmi.get('title', None)))
                    book.set('_pb_author_sort', newmi.get('author_sort', ''))
                else:
                    newmi = book
                (gtz_count, ltz_count, use_tz_var) = self.update_text_record(record, newmi, path, i, gtz_count, ltz_count, use_tz_var)
                # Ensure the collections in the XML database are recorded for
                # this book
                if book.device_collections is None:
                    book.device_collections = []
                book.device_collections = playlist_map.get(book.lpath, [])

                if created and ext_root is not None:
                    assert ext_lpath_map is not None
                    if ext_lpath_map.get(book.lpath, None) is None:
                        ext_record = self.create_ext_text_record(ext_root, i, book.lpath, book.thumbnail)
                        self.periodicalize_book(book, ext_record)

            debug_print(f'Timezone votes: {gtz_count} GMT, {ltz_count} LTZ, use_tz_var={use_tz_var}')
            self.update_playlists(i, root, booklist, collections_attributes)
        # Update the device collections because update playlist could have added
        # some new ones.
        debug_print('In update/ Starting refresh of device_collections')
        for i, booklist in booklists.items():
            playlist_map = self.build_id_playlist_map(i)
            for book in booklist:
                book.device_collections = playlist_map.get(book.lpath, [])
        self.fix_ids()
        debug_print('Finished update')

    def is_sony_periodical(self, book: Metadata) -> bool:
        if _('News') not in book.tags:
            return False
        assert book.lpath is not None  # device books always have an lpath
        if not book.lpath.lower().endswith('.epub'):
            return False
        assert book.pubdate is not None
        if book.pubdate.date() < date(2010, 10, 17):
            return False
        return True

    def periodicalize_book(self, book: Metadata, record: _Element) -> None:
        if not self.is_sony_periodical(book):
            return
        record.set('conformsTo', 'http://xmlns.sony.net/e-book/prs/periodicals/1.0/newspaper/1.0')

        record.set('description', '')

        name = None
        if '[' in book.title:
            name = book.title.split('[')[0].strip()
            if len(name) < 4:
                name = None
        if not name:
            try:
                name = [t for t in book.tags if t != _('News')][0]
            except Exception:
                name = None

        if not name:
            name = book.title

        record.set('periodicalName', name)

        try:
            assert book.pubdate is not None  # checked in is_sony_periodical()
            pubdate = strftime(book.pubdate.utctimetuple(), zone=lambda x: x)
            record.set('publicationDate', pubdate)
        except Exception:
            pass

    def rebuild_collections(self, booklist: BookList, bl_index: int) -> None:
        if bl_index not in self.record_roots:
            return
        root = self.record_roots[bl_index]
        self.update_playlists(bl_index, root, booklist, [])
        self.fix_ids()

    def update_playlists(self, bl_index: int, root: _Element, booklist: BookList, collections_attributes: Sequence[str]) -> None:
        debug_print('Starting update_playlists', collections_attributes, bl_index)
        self.reset_existing_playlists_map()
        collections = booklist.get_collections(collections_attributes)
        lpath_map = self.build_lpath_map(root)
        debug_print('update_playlists: finished building maps')
        for category, books in collections.items():
            records = [lpath_map.get(b.lpath, None) for b in books]
            # Remove any books that were not found, although this
            # *should* never happen
            if DEBUG and None in records:
                debug_print('WARNING: Some elements in the JSON cache were not found in the XML cache')
            records = [x for x in records if x is not None]
            # Ensure each book has an ID.
            for rec in records:
                if rec.get('id', None) is None:
                    rec.set('id', str(self.max_id(root) + 1))
            ids_or_none = [x.get('id', None) for x in records]
            # Given that we set the ids, there shouldn't be any None's. But
            # better to be safe...
            if None in ids_or_none:
                debug_print('WARNING: Some <text> elements do not have ids')
            ids = [x for x in ids_or_none if x is not None]

            playlist = self.get_or_create_playlist(bl_index, category)
            # Get the books currently in the playlist. We will need them to be
            # sure to put back any books that were manually added.
            playlist_ids: list[str] = []
            for item in playlist:
                id_ = item.get('id', None)
                if id_ is not None:
                    playlist_ids.append(id_)
            # Empty the playlist. We do this so that the playlist will have the
            # order specified by get_collections
            for item in list(playlist):
                playlist.remove(item)

            # Get a list of ids not known by get_collections
            extra_ids = [x for x in playlist_ids if x not in ids]
            # Rebuild the collection in the order specified by get_collections. Then
            # add the ids that get_collections didn't know about.
            for id_ in ids + extra_ids:
                item = playlist.makeelement(f'{{{self.namespaces[bl_index]}}}item', nsmap=playlist.nsmap, attrib={'id': id_})
                playlist.append(item)

        # Delete playlist entries not in collections
        for playlist in root.xpath('//*[local-name()="playlist"]'):
            title = playlist.get('title', None)
            if title not in collections:
                if DEBUG:
                    debug_print('Deleting playlist:', playlist.get('title', ''))
                playlist.getparent().remove(playlist)
                continue
            books = collections[title]
            records = [lpath_map.get(b.lpath, None) for b in books]
            records = [x for x in records if x is not None]
            ids = [x.get('id', None) for x in records]
            ids = [x for x in ids if x is not None]
            for item in list(playlist):
                if item.get('id', None) not in ids:
                    if DEBUG:
                        debug_print('Deleting item:', item.get('id', ''), 'from playlist:', playlist.get('title', ''))
                    playlist.remove(item)
        debug_print('Finishing update_playlists')

    def create_text_record(self, root: _Element, bl_id: int, lpath: str) -> _Element:
        namespace = self.namespaces[bl_id]
        id_ = self.max_id(root) + 1
        attrib = {
            'page': '0',
            'part': '0',
            'pageOffset': '0',
            'scale': '0',
            'id': str(id_),
            'sourceid': '1',
            'path': lpath,
        }
        ans = root.makeelement(f'{{{namespace}}}text', attrib=attrib, nsmap=root.nsmap)
        root.append(ans)
        return ans

    def create_ext_text_record(self, root: _Element, bl_id: int, lpath: str, thumbnail: tuple[int, int, bytes] | None) -> _Element:
        namespace = root.nsmap[None]
        attrib = {'path': lpath}
        ans = root.makeelement(f'{{{namespace}}}text', attrib=attrib, nsmap=root.nsmap)
        ans.tail = '\n'
        if len(root) > 0:
            root[-1].tail = '\n\t'
        else:
            root.text = '\n\t'
        root.append(ans)
        if thumbnail and thumbnail[-1]:
            ans.text = '\n' + '\t\t'
            t = root.makeelement(
                f'{{{namespace}}}thumbnail',
                attrib={'width': str(thumbnail[0]), 'height': str(thumbnail[1])},
                nsmap=root.nsmap,
            )
            t.text = 'main_thumbnail.jpg'
            ans.append(t)
            t.tail = '\n\t'
        return ans

    def update_text_record(
        self, record: _Element, book: Metadata, path: str, bl_index: int, gtz_count: int, ltz_count: int, use_tz_var: bool
    ) -> tuple[int, int, bool]:
        """
        Update the Sony database from the book. This is done if the timestamp in
        the db differs from the timestamp on the file.
        """

        # It seems that a Sony device can sometimes know what timezone it is in,
        # and apparently converts the dates to GMT when it writes them to its
        # DB. We can detect that a device is timezone-aware because there is a
        # 'tz' variable in the Sony DB, which we can set to "0" to tell the
        # device to ignore its own timezone when comparing mtime to the date in
        # the DB.

        # Unfortunately, if there is no tz variable in the DB, then we can't
        # tell when the device applies a timezone conversion. We use a horrible
        # heuristic to work around this problem. First, set dates only for new
        # books, trying to avoid upsetting the sony. Second, voting: if a book
        # is not new, compare its Sony DB date against localtime and gmtime.
        # Count the matches. When we must set a date, use the one with the most
        # matches. Use localtime if the case of a tie, and hope it is right.
        try:
            timestamp = os.path.getmtime(path)
        except Exception:
            debug_print('Failed to get timestamp for:', path)
            timestamp = time.time()
        rec_date = record.get('date', None)

        def clean(x: str | bytes) -> str:
            if isinstance(x, bytes):
                x = x.decode(preferred_encoding, 'replace')
            x.replace('\0', '')
            return x

        def record_set(k: str, v: str | bytes) -> None:
            try:
                record.set(k, clean(v))
            except Exception:
                # v is not suitable for XML, ignore
                pass

        if not getattr(book, '_new_book', False):  # book is not new
            if record.get('tz', None) is not None:
                use_tz_var = True
            if strftime(timestamp, zone=time.gmtime) == rec_date:
                gtz_count += 1
            elif strftime(timestamp, zone=time.localtime) == rec_date:
                ltz_count += 1
        else:  # book is new. Set the time using the current votes
            if use_tz_var:
                tz = time.localtime
                record.set('tz', '0')
                debug_print("Use localtime TZ and tz='0' for new book", book.lpath)
            elif ltz_count >= gtz_count:
                tz = time.localtime
                debug_print('Use localtime TZ for new book', book.lpath)
            else:
                tz = time.gmtime
                debug_print('Use GMT TZ for new book', book.lpath)
            date = strftime(timestamp, zone=tz)
            record.set('date', clean(date))
        try:
            record.set('size', clean(str(os.stat(path).st_size)))
        except Exception:
            record.set('size', '0')
        title = book.title or _('Unknown')
        record_set('title', title)
        ts = book.title_sort
        if not ts:
            ts = title_sort(title)
        record_set('titleSorter', ts)
        if self.use_author_sort:
            if book.author_sort:
                aus = book.author_sort
            else:
                debug_print('Author_sort is None for book', book.lpath)
                aus = authors_to_sort_string(book.authors)
            record_set('author', aus)
        else:
            record_set('author', authors_to_string(book.authors))
        ext = os.path.splitext(path)[1]
        if ext:
            ext = ext[1:].lower()
            mime = MIME_MAP.get(ext, None)
            if mime is None:
                mime = guess_type('a.' + ext)[0]
            if mime is not None:
                record.set('mime', clean(mime))
        if 'sourceid' not in record.attrib:
            record.set('sourceid', '1')
        if 'id' not in record.attrib:
            num = self.max_id(record.getroottree().getroot())
            record.set('id', str(num + 1))
        return gtz_count, ltz_count, use_tz_var

    # }}}

    # Writing the XML files {{{
    def cleanup_whitespace(self, bl_index: int) -> None:
        root = self.record_roots[bl_index]
        level = 2 if bl_index == 0 else 1
        if len(root) > 0:
            root.text = '\n' + '\t' * level
            for child in root:
                child.tail = '\n' + '\t' * level
                if len(child) > 0:
                    child.text = '\n' + '\t' * (level + 1)
                    for gc in child:
                        gc.tail = '\n' + '\t' * (level + 1)
                    next(child.iterchildren(reversed=True)).tail = '\n' + '\t' * level
            next(root.iterchildren(reversed=True)).tail = '\n' + '\t' * (level - 1)

    def move_playlists_to_bottom(self) -> None:
        for root in self.record_roots.values():
            seen: list[_Element] = []
            for pl in root.xpath('//*[local-name()="playlist"]'):
                pl.getparent().remove(pl)
                seen.append(pl)
            for pl in seen:
                root.append(pl)

    def write(self) -> None:
        from lxml import etree

        for i, path in self.paths.items():
            self.move_playlists_to_bottom()
            self.cleanup_whitespace(i)
            raw = etree.tostring(self.roots[i], encoding='UTF-8', xml_declaration=True)
            raw = raw.replace(b"<?xml version='1.0' encoding='UTF-8'?>", b'<?xml version="1.0" encoding="UTF-8"?>')
            with open(path, 'wb') as f:
                f.write(raw)
                fsync(f)

        for i, path in self.ext_paths.items():
            try:
                raw = etree.tostring(self.ext_roots[i], encoding='UTF-8', xml_declaration=True)
            except Exception:
                continue
            raw = raw.replace(b"<?xml version='1.0' encoding='UTF-8'?>", b'<?xml version="1.0" encoding="UTF-8"?>')
            with open(path, 'wb') as f:
                f.write(raw)
                fsync(f)

    # }}}

    # Utility methods {{{

    def build_lpath_map(self, root: _Element) -> dict[str, _Element]:
        m: dict[str, _Element] = {}
        for bk in root.xpath('//*[local-name()="text"]'):
            m[bk.get('path')] = bk
        return m

    def build_id_map(self, root: _Element) -> dict[str, _Element]:
        m: dict[str, _Element] = {}
        for bk in root.xpath('//*[local-name()="text"]'):
            m[bk.get('id')] = bk
        return m

    def book_by_lpath(self, lpath: str, root: _Element) -> _Element | None:
        matches = root.xpath(f'//*[local-name()="text" and @path="{lpath}"]')
        if matches:
            return matches[0]

    def max_id(self, root: _Element) -> int:
        ans = -1
        for x in root.xpath('//*[@id]'):
            id_ = x.get('id')
            try:
                num = int(id_)
                ans = max(ans, num)
            except Exception:
                continue
        return ans

    def detect_namespaces(self) -> None:
        self.nsmaps: dict[int, dict[str | None, str]] = {}
        for i, root in self.roots.items():
            self.nsmaps[i] = root.nsmap

        self.namespaces: dict[int, str | None] = {}
        for i in self.roots:
            for c in ('library', 'text', 'image', 'playlist', 'thumbnail', 'watchSpecial'):
                matches = self.record_roots[i].xpath(f'//*[local-name()="{c}"]')
                if matches:
                    e = matches[0]
                    self.namespaces[i] = e.nsmap[e.prefix]
                    break
            if i not in self.namespaces:
                ns = self.nsmaps[i].get(None, None)
                for prefix in self.nsmaps[i]:
                    if prefix is not None:
                        ns = self.nsmaps[i][prefix]
                        break
                self.namespaces[i] = ns

    # }}}
