#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from pprint import pprint
from base64 import b64decode

from lxml import etree

from calibre import prints
from calibre.devices.errors import DeviceError
from calibre.constants import DEBUG
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import string_to_authors

EMPTY_CARD_CACHE = '''\
<?xml version="1.0" encoding="UTF-8"?>
<cache xmlns="http://www.kinoma.com/FskCache/1">
</cache>
'''

class XMLCache(object):

    def __init__(self, paths):
        if DEBUG:
            pprint(paths)
        self.paths = paths
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
            raise DeviceError('The SONY XML database is corrupted (no <records>)')
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
                if len(playlist) == 0:
                    if DEBUG:
                        prints('Removing playlist:', playlist.get('id', None))
                    playlist.getparent().remove(playlist)

    # }}}

    def fix_ids(self): # {{{

        def ensure_numeric_ids(root):
            idmap = {}
            for x in root.xpath('//*[@id]'):
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
            items = root.xpath('//*[@id]')
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
            root = self.roots[i]
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
                            ext = img.tag.split('}')[-1]
                            book.cover_data = [ext, raw]
                            break
                    break
    # }}}

    def update(self, booklists):
        pass

    def write(self):
        return
        for i, path in self.paths.items():
            raw = etree.tostring(self.roots[i], encoding='utf-8',
                    xml_declaration=True)
            with open(path, 'wb') as f:
                f.write(raw)

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

