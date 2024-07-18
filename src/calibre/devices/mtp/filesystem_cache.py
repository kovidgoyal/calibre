#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
import sys
import time
import weakref
from collections import defaultdict, deque
from datetime import datetime
from itertools import chain
from operator import attrgetter
from typing import Dict, Tuple

from calibre import force_unicode, human_readable, prints
from calibre.constants import iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.date import as_utc, local_tz
from calibre.utils.icu import lower, sort_key

bexts = frozenset(BOOK_EXTENSIONS) - {'mbp', 'tan', 'rar', 'zip', 'xml'}


class ListEntry:

    def __init__(self, entry: 'FileOrFolder'):
        self.is_dir = entry.is_folder
        self.is_readonly = not entry.can_delete
        self.path = '/'.join(entry.full_path)
        self.name = entry.name
        self.size = entry.size
        self.ctime = self.wtime = time.mktime(entry.last_modified.timetuple())


class FileOrFolder:

    def __init__(self, entry, fs_cache: 'FilesystemCache', is_storage: bool = False):
        self.object_id = entry['id']
        self.is_storage = is_storage
        self.is_folder = entry['is_folder']
        self.storage_id = entry['storage_id']
        # self.parent_id is None for storage objects
        self.parent_id = entry.get('parent_id', None)
        self.persistent_id = entry.get('persistent_id', self.object_id)
        n = entry.get('name', None)
        if not n:
            if self.is_storage:
                prefix = 'Storage'
            else:
                prefix = 'Folder' if self.is_folder else 'File'
            n = f'{prefix}-{self.persistent_id}'
        self.name = force_unicode(n, 'utf-8')
        self.size = entry.get('size', 0)
        md = entry.get('modified', 0)
        try:
            if isinstance(md, tuple):
                self.last_modified = datetime(*(list(md)+[local_tz]))
            else:
                self.last_modified = datetime.fromtimestamp(md, local_tz)
        except Exception:
            self.last_modified = datetime.fromtimestamp(0, local_tz)
        self.last_mod_string = self.last_modified.strftime('%Y/%m/%d %H:%M')
        self.last_modified = as_utc(self.last_modified)

        if self.storage_id not in fs_cache.all_storage_ids:
            raise ValueError('Storage id %s not valid for %s, valid values: %s'%(self.storage_id,
                entry, fs_cache.all_storage_ids))

        self.is_hidden = entry.get('is_hidden', False)
        self.is_system = entry.get('is_system', False)
        self.can_delete = entry.get('can_delete', True)

        self.files = []
        self.folders = []
        if not self.is_storage:
            # storage ids can overlap filesystem object ids on libmtp. See https://bugs.launchpad.net/bugs/2072384
            # so only store actual filesystem object ids in id_map
            fs_cache.id_maps[self.storage_id][self.object_id] = self
            if iswindows:
                # On windows parent_id == storage_id for objects in root. Set
                # it 0 so the rest of the logic works as on libmtp.
                # See https://bugs.launchpad.net/bugs/2073323
                if self.storage_id == self.parent_id:
                    self.parent_id = 0
        self.fs_cache = weakref.ref(fs_cache)
        self.deleted = False

        if self.is_storage:
            self.storage_prefix = 'mtp:::%s:::'%self.persistent_id

        # Ignore non ebook files and AppleDouble files
        self.is_ebook = (not self.is_folder and not self.is_storage and
                self.name.rpartition('.')[-1].lower() in bexts and not self.name.startswith('._'))

    def __repr__(self):
        if self.is_storage:
            name = 'Storage'
        else:
            name = 'Folder' if self.is_folder else 'File'
        try:
            path = str(self.full_path)
        except Exception:
            path = ''
        datum = 'size=%s'%(self.size)
        if self.is_folder or self.is_storage:
            datum = 'children=%s'%(len(self.files) + len(self.folders))
        return '%s(id=%s, storage_id=%s, %s, path=%s, modified=%s)'%(name, self.object_id,
                self.storage_id, datum, path, self.last_mod_string)

    __str__ = __repr__
    __unicode__ = __repr__

    @property
    def empty(self):
        return not self.files and not self.folders

    @property
    def id_map(self) -> Dict[int, 'FileOrFolder']:
        return self.fs_cache().id_maps[self.storage_id]

    @property
    def parent(self):
        if self.parent_id:
            return self.id_map[self.parent_id]
        if self.is_storage or self.parent_id is None:
            return None
        return self.fs_cache().storage(self.storage_id)

    @property
    def in_root(self):
        return self.parent_id is not None and self.parent_id == 0

    @property
    def storage(self):
        return self.fs_cache().storage(self.storage_id)

    @property
    def full_path(self) -> Tuple[str, ...]:
        parts = deque()
        parts.append(self.name)
        p = self.parent
        while p is not None:
            parts.appendleft(p.name)
            p = p.parent
        return tuple(parts)

    def __iter__(self):
        yield from self.folders
        yield from self.files

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
        data += ' modified=%s'%self.last_mod_string
        line = '%s%s %s [id:%s %s]'%(prefix, c, self.name, self.object_id, data)
        prints(line, file=out)
        for c in (self.folders, self.files):
            for e in sorted(c, key=lambda x:sort_key(x.name)):
                e.dump(prefix=prefix+'  ', out=out)

    def list(self, recurse=False):
        if not self.is_folder:
            parent = self.parent
            yield '/'.join(parent.full_path[1:]), ListEntry(self)
            return
        entries = [ListEntry(x) for x in chain(self.folders, self.files)]
        yield '/'.join(self.full_path[1:]), entries
        if recurse:
            for x in self.folders:
                yield from x.list(recurse=True)

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


class FilesystemCache:

    def __init__(self, all_storage, entries):
        self.entries = []
        self.id_maps = defaultdict(dict)
        self.all_storage_ids = tuple(x['id'] for x in all_storage)

        for storage in all_storage:
            storage['storage_id'] = storage['id']
            e = FileOrFolder(storage, self, is_storage=True)
            self.entries.append(e)

        self.entries.sort(key=attrgetter('object_id'))
        self.all_storage_ids = tuple(x.storage_id for x in self.entries)

        for entry in entries:
            FileOrFolder(entry, self)

        for id_map in self.id_maps.values():
            for item in id_map.values():
                try:
                    p = item.parent
                except KeyError:
                    # Parent does not exist, set the parent to be the storage
                    # object
                    item.parent_id = 0
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
        id_map = self.id_maps[storage_id]
        for x in id_map.values():
            if x.is_ebook:
                if x.in_root and x.name.lower().endswith('.txt'):
                    continue  # Ignore .txt files in the root
                yield x

    def __len__(self):
        ans = len(self.id_maps)
        for id_map in self.id_maps.values():
            ans += len(id_map)
        return ans

    def resolve_mtp_id_path(self, path):
        if not path.startswith('mtp:::'):
            raise ValueError('%s is not a valid MTP path'%path)
        parts = path.split(':::', 2)
        if len(parts) < 3:
            raise ValueError('%s is not a valid MTP path'%path)
        try:
            object_id = json.loads(parts[1])
        except Exception:
            raise ValueError('%s is not a valid MTP path'%path)
        id_map = {}
        path = parts[2]
        storage_name = path.partition('/')[0]
        for entry in self.entries:
            if entry.name == storage_name:
                id_map = self.id_maps[entry.storage_id]
                break
        try:
            return id_map[object_id]
        except KeyError:
            raise ValueError('No object found with MTP path: %s'%path)
