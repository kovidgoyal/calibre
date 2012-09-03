#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref, sys, json
from collections import deque
from operator import attrgetter
from future_builtins import map
from datetime import datetime

from calibre import human_readable, prints, force_unicode
from calibre.utils.date import local_tz, as_utc
from calibre.utils.icu import sort_key, lower
from calibre.ebooks import BOOK_EXTENSIONS

bexts = frozenset(BOOK_EXTENSIONS)

class FileOrFolder(object):

    def __init__(self, entry, fs_cache):
        self.all_storage_ids = fs_cache.all_storage_ids

        self.object_id = entry['id']
        self.is_folder = entry['is_folder']
        self.storage_id = entry['storage_id']
        # self.parent_id is None for storage objects
        self.parent_id = entry.get('parent_id', None)
        n = entry.get('name', None)
        if not n: n = '___'
        self.name = force_unicode(n, 'utf-8')
        self.persistent_id = entry.get('persistent_id', self.object_id)
        self.size = entry.get('size', 0)
        md = entry.get('modified', 0)
        try:
            self.last_modified = datetime.fromtimestamp(md, local_tz)
        except:
            self.last_modified = datetime.fromtimestamp(0, local_tz)
        self.last_modified = as_utc(self.last_modified)

        if self.storage_id not in self.all_storage_ids:
            raise ValueError('Storage id %s not valid for %s, valid values: %s'%(self.storage_id,
                entry, self.all_storage_ids))

        if self.parent_id == 0:
            self.parent_id = self.storage_id

        self.is_hidden = entry.get('is_hidden', False)
        self.is_system = entry.get('is_system', False)
        self.can_delete = entry.get('can_delete', True)

        self.files = []
        self.folders = []
        fs_cache.id_map[self.object_id] = self
        self.fs_cache = weakref.ref(fs_cache)
        self.deleted = False

        if self.storage_id == self.object_id:
            self.storage_prefix = 'mtp:::%s:::'%self.persistent_id

        self.is_ebook = (not self.is_folder and
                self.name.rpartition('.')[-1].lower() in bexts)

    def __repr__(self):
        name = 'Folder' if self.is_folder else 'File'
        try:
            path = unicode(self.full_path)
        except:
            path = ''
        datum = 'size=%s'%(self.size)
        if self.is_folder:
            datum = 'children=%s'%(len(self.files) + len(self.folders))
        return '%s(id=%s, storage_id=%s, %s, path=%s)'%(name, self.object_id,
                self.storage_id, datum, path)

    __str__ = __repr__
    __unicode__ = __repr__

    @property
    def empty(self):
        return not self.files and not self.folders

    @property
    def id_map(self):
        return self.fs_cache().id_map

    @property
    def parent(self):
        return None if self.parent_id is None else self.id_map[self.parent_id]

    @property
    def full_path(self):
        parts = deque()
        parts.append(self.name)
        p = self.parent
        while p is not None:
            parts.appendleft(p.name)
            p = p.parent
        return tuple(parts)

    def __iter__(self):
        for e in self.folders:
            yield e
        for e in self.files:
            yield e

    def add_child(self, entry):
        ans = FileOrFolder(entry, self.fs_cache())
        t = self.folders if ans.is_folder else self.files
        t.append(ans)
        return ans

    def remove_child(self, entry):
        for x in (self.files, self.folders):
            try:
                x.remove(entry)
            except ValueError:
                pass
        self.id_map.pop(entry.object_id, None)
        entry.deleted = True

    def dump(self, prefix='', out=sys.stdout):
        c = '+' if self.is_folder else '-'
        data = ('%s children'%(sum(map(len, (self.files, self.folders))))
            if self.is_folder else human_readable(self.size))
        line = '%s%s %s [id:%s %s]'%(prefix, c, self.name, self.object_id, data)
        prints(line, file=out)
        for c in (self.folders, self.files):
            for e in sorted(c, key=lambda x:sort_key(x.name)):
                e.dump(prefix=prefix+'  ', out=out)

    def folder_named(self, name):
        name = lower(name)
        for e in self.folders:
            if e.name and lower(e.name) == name:
                return e
        return None

    def file_named(self, name):
        name = lower(name)
        for e in self.files:
            if e.name and lower(e.name) == name:
                return e
        return None

    def find_path(self, path):
        '''
        Find a path in this folder, where path is a
        tuple of folder and file names like ('eBooks', 'newest',
        'calibre.epub'). Finding is case-insensitive.
        '''
        parent = self
        components = list(path)
        while components:
            child = components[0]
            components = components[1:]
            c = parent.folder_named(child)
            if c is None:
                c = parent.file_named(child)
            if c is None:
                return None
            parent = c
        return parent

    @property
    def mtp_relpath(self):
        return tuple(x.lower() for x in self.full_path[1:])

    @property
    def mtp_id_path(self):
        return 'mtp:::' + json.dumps(self.object_id) + ':::' + '/'.join(self.full_path)

class FilesystemCache(object):

    def __init__(self, all_storage, entries):
        self.entries = []
        self.id_map = {}
        self.all_storage_ids = tuple(x['id'] for x in all_storage)

        for storage in all_storage:
            storage['storage_id'] = storage['id']
            e = FileOrFolder(storage, self)
            self.entries.append(e)

        self.entries.sort(key=attrgetter('object_id'))
        all_storage_ids = [x.storage_id for x in self.entries]
        self.all_storage_ids = tuple(all_storage_ids)

        for entry in entries:
            FileOrFolder(entry, self)

        for item in self.id_map.itervalues():
            try:
                p = item.parent
            except KeyError:
                # Parent does not exist, set the parent to be the storage
                # object
                sid = p.storage_id
                if sid not in all_storage_ids:
                    sid = all_storage_ids[0]
                item.parent_id = sid
                p = item.parent

            if p is not None:
                t = p.folders if item.is_folder else p.files
                t.append(item)

    def dump(self, out=sys.stdout):
        for e in self.entries:
            e.dump(out=out)

    def storage(self, storage_id):
        for e in self.entries:
            if e.storage_id == storage_id:
                return e

    def iterebooks(self, storage_id):
        for x in self.id_map.itervalues():
            if x.storage_id == storage_id and x.is_ebook:
                if x.parent_id == storage_id and x.name.lower().endswith('.txt'):
                    continue # Ignore .txt files in the root
                yield x

    def resolve_mtp_id_path(self, path):
        if not path.startswith('mtp:::'):
            raise ValueError('%s is not a valid MTP path'%path)
        parts = path.split(':::')
        if len(parts) < 3:
            raise ValueError('%s is not a valid MTP path'%path)
        try:
            object_id = json.loads(parts[1])
        except:
            raise ValueError('%s is not a valid MTP path'%path)
        try:
            return self.id_map[object_id]
        except KeyError:
            raise ValueError('No object found with MTP path: %s'%path)


