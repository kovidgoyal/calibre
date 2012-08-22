#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref, sys
from operator import attrgetter
from future_builtins import map

from calibre import human_readable, prints, force_unicode
from calibre.utils.icu import sort_key

class FileOrFolder(object):

    def __init__(self, entry, fs_cache, all_storage_ids):
        self.object_id = entry['id']
        self.is_folder = entry['is_folder']
        self.name = force_unicode(entry.get('name', '___'), 'utf-8')
        self.persistent_id = entry.get('persistent_id', self.object_id)
        self.size = entry.get('size', 0)
        # self.parent_id is None for storage objects
        self.parent_id = entry.get('parent_id', None)
        if self.parent_id == 0:
            sid = entry['storage_id']
            if sid not in all_storage_ids:
                sid = all_storage_ids[0]
            self.parent_id = sid
        self.is_hidden = entry.get('is_hidden', False)
        self.is_system = entry.get('is_system', False)
        self.can_delete = entry.get('can_delete', True)

        self.files = []
        self.folders = []
        fs_cache.id_map[self.object_id] = self
        self.fs_cache = weakref.ref(fs_cache)

    @property
    def id_map(self):
        return self.fs_cache().id_map

    @property
    def parent(self):
        return None if self.parent_id is None else self.id_map[self.parent_id]

    def __iter__(self):
        for e in self.folders:
            yield e
        for e in self.files:
            yield e

    def dump(self, prefix='', out=sys.stdout):
        c = '+' if self.is_folder else '-'
        data = ('%s children'%(sum(map(len, (self.files, self.folders))))
            if self.is_folder else human_readable(self.size))
        line = '%s%s %s [id:%s %s]'%(prefix, c, self.name, self.object_id, data)
        prints(line, file=out)
        for c in (self.folders, self.files):
            for e in sorted(c, key=lambda x:sort_key(x.name)):
                e.dump(prefix=prefix+'  ', out=out)

class FilesystemCache(object):

    def __init__(self, all_storage, entries):
        self.entries = []
        self.id_map = {}

        for storage in all_storage:
            e = FileOrFolder(storage, self, [])
            self.entries.append(e)

        self.entries.sort(key=attrgetter('object_id'))
        all_storage_ids = [x.object_id for x in self.entries]

        for entry in entries:
            FileOrFolder(entry, self, all_storage_ids)

        for item in self.id_map.itervalues():
            p = item.parent
            if p is not None:
                t = p.folders if item.is_folder else p.files
                t.append(item)

    def dump(self, out=sys.stdout):
        for e in self.entries:
            e.dump(out=out)


