#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time
from pprint import pprint
from base64 import b64decode
from uuid import uuid4

from lxml import etree

from calibre import prints, guess_type
from calibre.devices.errors import DeviceError
from calibre.constants import DEBUG
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import string_to_authors, authors_to_string

EMPTY_CARD_CACHE = '''\
<?xml version="1.0" encoding="UTF-8"?>
<cache xmlns="http://www.kinoma.com/FskCache/1">
</cache>
'''

MIME_MAP   = {
                "lrf" : "application/x-sony-bbeb",
                'lrx' : 'application/x-sony-bbeb',
                "rtf" : "application/rtf",
                "pdf" : "application/pdf",
                "txt" : "text/plain" ,
                'epub': 'application/epub+zip',
              }

DAY_MAP   = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
MONTH_MAP = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
INVERSE_DAY_MAP = dict(zip(DAY_MAP.values(), DAY_MAP.keys()))
INVERSE_MONTH_MAP = dict(zip(MONTH_MAP.values(), MONTH_MAP.keys()))

def strptime(src):
    src = src.strip()
    src = src.split()
    src[0] = str(DAY_MAP[src[0][:-1]])+','
    src[2] = str(MONTH_MAP[src[2]])
    return time.strptime(' '.join(src), '%w, %d %m %Y %H:%M:%S %Z')

def strftime(epoch, zone=time.gmtime):
    src = time.strftime("%w, %d %m %Y %H:%M:%S GMT", zone(epoch)).split()
    src[0] = INVERSE_DAY_MAP[int(src[0][:-1])]+','
    src[2] = INVERSE_MONTH_MAP[int(src[2])]
    return ' '.join(src)

def uuid():
    return str(uuid4()).replace('-', '', 1).upper()

class XMLCache(object):

    def __init__(self, paths, prefixes):
        if DEBUG:
            pprint(paths)
        self.paths = paths
        self.prefixes = prefixes
        parser = etree.XMLParser(recover=True)
        self.roots = {}
        for source_id, path in paths.items():
            if source_id == 0:
                if not os.path.exists(path):
                    raise DeviceError('The SONY XML cache media.xml does not exist. Try'
                        ' disconnecting and reconnecting your reader.')
                with open(path, 'rb') as f:
                    raw = f.read()
            else:
                raw = EMPTY_CARD_CACHE
                if os.access(path, os.R_OK):
                    with open(path, 'rb') as f:
                        raw = f.read()
            self.roots[source_id] = etree.fromstring(xml_to_unicode(
                        raw, strip_encoding_pats=True, assume_utf8=True,
                        verbose=DEBUG)[0],
                        parser=parser)

        recs = self.roots[0].xpath('//*[local-name()="records"]')
        if not recs:
            raise DeviceError('The SONY XML database is corrupted (no'
                    ' <records>). Try disconnecting an reconnecting'
                    ' your reader.')
        self.record_roots = {}
        self.record_roots.update(self.roots)
        self.record_roots[0] = recs[0]

        self.detect_namespaces()


    # Playlist management {{{
    def purge_broken_playlist_items(self, root):
        for item in root.xpath(
            '//*[local-name()="playlist"]/*[local-name()="item"]'):
            id_ = item.get('id', None)
            if id_ is None or not root.xpath(
                '//*[local-name()!="item" and @id="%s"]'%id_):
                if DEBUG:
                    prints('Purging broken playlist item:',
                            etree.tostring(item, with_tail=False))
                item.getparent().remove(item)


    def prune_empty_playlists(self):
        for i, root in self.record_roots.items():
            self.purge_broken_playlist_items(root)
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                if len(playlist) == 0 or not playlist.get('title', None):
                    if DEBUG:
                        prints('Removing playlist:', playlist.get('id', None),
                                playlist.get('title', None))
                    playlist.getparent().remove(playlist)

    def ensure_unique_playlist_titles(self):
        for i, root in self.record_roots.items():
            seen = set([])
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                title = playlist.get('title', None)
                if title is None:
                    title = _('Unnamed')
                    playlist.set('title', title)
                if title in seen:
                    for i in range(2, 1000):
                        if title+str(i) not in seen:
                            title = title+str(i)
                            playlist.set('title', title)
                            break
                else:
                    seen.add(title)

    def get_playlist_map(self):
        ans = {}
        self.ensure_unique_playlist_titles()
        self.prune_empty_playlists()
        for i, root in self.record_roots.items():
            ans[i] = {}
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                items = []
                for item in playlist:
                    id_ = item.get('id', None)
                    records = root.xpath(
                        '//*[local-name()="text" and @id="%s"]'%id_)
                    if records:
                        items.append(records[0])
                ans[i] = {playlist.get('title'):items}
        return ans

    def get_or_create_playlist(self, bl_idx, title):
        root = self.record_roots[bl_idx]
        for playlist in root.xpath('//*[local-name()="playlist"]'):
            if playlist.get('title', None) == title:
                return playlist
        ans = root.makeelement('{%s}playlist'%self.namespaces[bl_idx],
                nsmap=root.nsmap, attrib={
                    'uuid' : uuid(),
                    'title': title,
                    'id'   : str(self.max_id(root)+1),
                    'sourceid': '1'
                    })
        root.append(ans)
        return ans
    # }}}

    def fix_ids(self): # {{{

        def ensure_numeric_ids(root):
            idmap = {}
            for x in root.xpath('child::*[@id]'):
                id_ = x.get('id')
                try:
                    id_ = int(id_)
                except:
                    x.set('id', '-1')
                    idmap[id_] = '-1'

            if DEBUG and idmap:
                prints('Found non numeric ids:')
                prints(list(idmap.keys()))
            return idmap

        def remap_playlist_references(root, idmap):
            for playlist in root.xpath('//*[local-name()="playlist"]'):
                for item in playlist.xpath(
                        'descendant::*[@id and local-name()="item"]'):
                    id_ = item.get('id')
                    if id_ in idmap:
                        item.set('id', idmap[id_])
                        if DEBUG:
                            prints('Remapping id %s to %s'%(id_, idmap[id_]))

        def ensure_media_xml_base_ids(root):
            for num, tag in enumerate(('library', 'watchSpecial')):
                for x in root.xpath('//*[local-name()="%s"]'%tag):
                    x.set('id', str(num))

        def rebase_ids(root, base, sourceid, pl_sourceid):
            'Rebase all ids and also make them consecutive'
            for item in root.xpath('//*[@sourceid]'):
                sid = pl_sourceid if item.tag.endswith('playlist') else sourceid
                item.set('sourceid', str(sid))
            # Only rebase ids of nodes that are immediate children of the
            # record root (that way playlist/itemnodes are unaffected
            items = root.xpath('child::*[@id]')
            items.sort(cmp=lambda x,y:cmp(int(x.get('id')), int(y.get('id'))))
            idmap = {}
            for i, item in enumerate(items):
                old = int(item.get('id'))
                new = base + i
                if old != new:
                    item.set('id', str(new))
                    idmap[old] = str(new)
            return idmap

        self.prune_empty_playlists()

        for i in sorted(self.roots.keys()):
            root = self.record_roots[i]
            if i == 0:
                ensure_media_xml_base_ids(root)

            idmap = ensure_numeric_ids(root)
            remap_playlist_references(root, idmap)
            if i == 0:
                sourceid, playlist_sid = 1, 0
                base = 0
            else:
                previous = i-1
                if previous not in self.roots:
                    previous = 0
                max_id = self.max_id(self.roots[previous])
                sourceid = playlist_sid = max_id + 1
                base = max_id + 2
            idmap = rebase_ids(root, base, sourceid, playlist_sid)
            remap_playlist_references(root, idmap)

        last_bl = max(self.roots.keys())
        max_id = self.max_id(self.roots[last_bl])
        self.roots[0].set('nextID', str(max_id+1))
    # }}}

    def update_booklist(self, bl, bl_index): # {{{
        if bl_index not in self.record_roots:
            return
        root = self.record_roots[bl_index]
        for book in bl:
            record = self.book_by_lpath(book.lpath, root)
            if record is not None:
                title = record.get('title', None)
                if title is not None and title != book.title:
                    if DEBUG:
                        prints('Renaming title', book.title, 'to', title)
                    book.title = title
                authors = record.get('author', None)
                if authors is not None:
                    authors = string_to_authors(authors)
                    if authors != book.authors:
                        if DEBUG:
                            prints('Renaming authors', book.authors, 'to',
                                    authors)
                        book.authors = authors
                for thumbnail in record.xpath(
                        'descendant::*[local-name()="thumbnail"]'):
                    for img in thumbnail.xpath(
                            'descendant::*[local-name()="jpeg"]|'
                            'descendant::*[local-name()="png"]'):
                        if img.text:
                            raw = b64decode(img.text.strip())
                            book.thumbnail = raw
                            break
                    break
    # }}}

    # Update XML Cache {{{
    def update(self, booklists, collections_attributes):
        playlist_map = self.get_playlist_map()

        for i, booklist in booklists.items():
            if DEBUG:
                prints('Updating booklist:', i)
            root = self.record_roots[i]
            for book in booklist:
                path = os.path.join(self.prefixes[i], *(book.lpath.split('/')))
                record = self.book_by_lpath(book.lpath, root)
                if record is None:
                    record = self.create_text_record(root, i, book.lpath)
                self.update_text_record(record, book, path, i)
                bl_pmap = playlist_map[i]
                self.update_playlists(i, root, booklist, bl_pmap,
                        collections_attributes)

        self.fix_ids()

    def update_playlists(self, bl_index, root, booklist, playlist_map,
            collections_attributes):
        collections = booklist.get_collections(collections_attributes)
        for category, books in collections.items():
            records = [self.book_by_lpath(b.lpath, root) for b in books]
            # Remove any books that were not found, although this
            # *should* never happen
            if DEBUG and None in records:
                prints('WARNING: Some elements in the JSON cache were not'
                        'found in the XML cache')
            records = [x for x in records if x is not None]
            for rec in records:
                if rec.get('id', None) is None:
                    rec.set('id', str(self.max_id(root)+1))
            ids = [x.get('id', None) for x in records]
            if None in ids:
                if DEBUG:
                    prints('WARNING: Some <text> elements do not have ids')
                    ids = [x for x in ids if x is not None]

            playlist = self.get_or_create_playlist(bl_index, category)
            playlist_ids = []
            for item in playlist:
                id_ = item.get('id', None)
                if id_ is not None:
                    playlist_ids.append(id_)
            for item in list(playlist):
                playlist.remove(item)

            extra_ids = [x for x in playlist_ids if x not in ids]
            for id_ in ids + extra_ids:
                item = playlist.makeelement(
                        '{%s}item'%self.namespaces[bl_index],
                        nsmap=playlist.nsmap, attrib={'id':id_})
                playlist.append(item)



    def create_text_record(self, root, bl_id, lpath):
        namespace = self.namespaces[bl_id]
        id_ = self.max_id(root)+1
        attrib = {
                'page':'0', 'part':'0','pageOffset':'0','scale':'0',
                'id':str(id_), 'sourceid':'1', 'path':lpath}
        ans = root.makeelement('{%s}text'%namespace, attrib=attrib, nsmap=root.nsmap)
        root.append(ans)
        return ans

    def update_text_record(self, record, book, path, bl_index):
        timestamp = os.path.getctime(path)
        date = strftime(timestamp)
        if date != record.get('date', None):
            if DEBUG:
                prints('Changing date of', path, 'from',
                        record.get('date', ''), 'to', date)
                prints('\tctime', strftime(os.path.getctime(path)))
                prints('\tmtime', strftime(os.path.getmtime(path)))
            record.set('date', date)
        record.set('size', str(os.stat(path).st_size))
        record.set('title', book.title)
        record.set('author', authors_to_string(book.authors))
        ext = os.path.splitext(path)[1]
        if ext:
            ext = ext[1:].lower()
            mime = MIME_MAP.get(ext, None)
            if mime is None:
                mime = guess_type('a.'+ext)[0]
                if mime is not None:
                    record.set('mime', mime)
        if 'sourceid' not in record.attrib:
            record.set('sourceid', '1')
        if 'id' not in record.attrib:
            num = self.max_id(record.getroottree().getroot())
            record.set('id', str(num+1))
    # }}}

    # Writing the XML files {{{
    def cleanup_whitespace(self, bl_index):
        root = self.record_roots[bl_index]
        level = 2 if bl_index == 0 else 1
        if len(root) > 0:
            root.text = '\n'+'\t'*level
            for child in root:
                child.tail = '\n'+'\t'*level
                if len(child) > 0:
                    child.text = '\n'+'\t'*(level+1)
                    for gc in child:
                        gc.tail = '\n'+'\t'*(level+1)
                    child.iterchildren(reversed=True).next().tail = '\n'+'\t'*level
            root.iterchildren(reversed=True).next().tail = '\n'+'\t'*(level-1)

    def write(self):
        for i, path in self.paths.items():
            self.cleanup_whitespace(i)
            raw = etree.tostring(self.roots[i], encoding='UTF-8',
                    xml_declaration=True)
            raw = raw.replace("<?xml version='1.0' encoding='UTF-8'?>",
                    '<?xml version="1.0" encoding="UTF-8"?>')
            with open(path, 'wb') as f:
                f.write(raw)
    # }}}

    def book_by_lpath(self, lpath, root):
        matches = root.xpath(u'//*[local-name()="text" and @path="%s"]'%lpath)
        if matches:
            return matches[0]


    def max_id(self, root):
        ans = -1
        for x in root.xpath('//*[@id]'):
            id_ = x.get('id')
            try:
                num = int(id_)
                if num > ans:
                    ans = num
            except:
                continue
        return ans

    def detect_namespaces(self):
        self.nsmaps = {}
        for i, root in self.roots.items():
            self.nsmaps[i] = root.nsmap

        self.namespaces = {}
        for i in self.roots:
            for c in ('library', 'text', 'image', 'playlist', 'thumbnail',
                    'watchSpecial'):
                matches = self.record_roots[i].xpath('//*[local-name()="%s"]'%c)
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

        if DEBUG:
            prints('Found nsmaps:')
            pprint(self.nsmaps)
            prints('Found namespaces:')
            pprint(self.namespaces)

