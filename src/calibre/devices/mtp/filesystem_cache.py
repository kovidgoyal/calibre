#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import json
import sys
import time
import weakref
from collections import defaultdict, deque
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from itertools import chain
from operator import attrgetter
from typing import IO, TYPE_CHECKING, cast

from calibre import force_unicode, human_readable, prints
from calibre.constants import iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.date import as_utc, local_tz
from calibre.utils.icu import lower, sort_key

if TYPE_CHECKING:
    import builtins

bexts = frozenset(BOOK_EXTENSIONS) - {'mbp', 'tan', 'rar', 'zip', 'xml'}

#: Identifier of an object or storage on the device, an int for libmtp and a str for WPD
type ObjectId = int | str
#: Dictionary describing a file, folder or storage on the device
type MTPEntry = Mapping[str, object]


def convert_timestamp(md: object) -> datetime:
    try:
        if isinstance(md, tuple):
            year, month, day, hour, minute, second, microsecond = cast('tuple[int, int, int, int, int, int, int]', md)
            return datetime(year, month, day, hour, minute, second, microsecond, local_tz)
        else:
            return datetime.fromtimestamp(cast('float', md), local_tz)
    except Exception:
        return datetime.fromtimestamp(0, local_tz)


class ListEntry:
    def __init__(self, entry: FileOrFolder) -> None:
        self.is_dir = entry.is_folder
        self.is_readonly = not entry.can_delete
        self.path = '/'.join(entry.full_path)
        self.name = entry.name
        self.size = entry.size
        self.ctime = self.wtime = time.mktime(entry.last_modified.timetuple())


class FileOrFolder:
    def __init__(self, entry: MTPEntry, fs_cache: FilesystemCache, is_storage: bool = False) -> None:
        self.object_id = cast('ObjectId', entry['id'])
        self.is_storage = is_storage
        self.is_folder = cast('bool', entry['is_folder'])
        self.storage_id = cast('ObjectId', entry['storage_id'])
        # self.parent_id is None for storage objects
        self.parent_id = cast('ObjectId | None', entry.get('parent_id', None))
        self.persistent_id = cast('ObjectId', entry.get('persistent_id', self.object_id))
        n = entry.get('name', None)
        if not n:
            if self.is_storage:
                prefix = 'Storage'
            else:
                prefix = 'Folder' if self.is_folder else 'File'
            n = f'{prefix}-{self.persistent_id}'
        self.name: str = force_unicode(cast('str | bytes', n), 'utf-8')
        self.size = cast('int', entry.get('size', 0))
        md = entry.get('modified', 0)
        self.last_modified = convert_timestamp(md)
        self.last_mod_string = self.last_modified.strftime('%Y/%m/%d %H:%M')
        self.last_modified = as_utc(self.last_modified)

        if self.storage_id not in fs_cache.all_storage_ids:
            raise ValueError(f'Storage id {self.storage_id} not valid for {entry}, valid values: {fs_cache.all_storage_ids}')

        self.is_hidden = cast('bool', entry.get('is_hidden', False))
        self.is_system = cast('bool', entry.get('is_system', False))
        self.can_delete = cast('bool', entry.get('can_delete', True))

        self.files: list[FileOrFolder] = []
        self.folders: list[FileOrFolder] = []
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
            self.storage_prefix = f'mtp:::{self.persistent_id}:::'

        # Ignore non ebook files and AppleDouble files
        self.is_ebook = not self.is_folder and not self.is_storage and self.name.rpartition('.')[-1].lower() in bexts and not self.name.startswith('._')

        # allow Kindle Scribe notebooks to be imported and preserve the notebook name
        if self.name == 'nbk' and not (self.is_folder or self.is_storage):
            if len(self.full_path) >= 3 and self.full_path[-3] == '.notebooks':
                nbk_name = self.full_path[-2].replace('!!notebook', '').replace('!!', ' ')
                self.name = f'Scribe {nbk_name} Notebook.kfx'
                self.is_ebook = True

    def __repr__(self) -> str:
        if self.is_storage:
            name = 'Storage'
        else:
            name = 'Folder' if self.is_folder else 'File'
        try:
            path = str(self.full_path)
        except Exception:
            path = ''
        datum = f'size={self.size}'
        if self.is_folder or self.is_storage:
            datum = f'children={len(self.files) + len(self.folders)}'
        return f'{name}(id={self.object_id}, storage_id={self.storage_id}, {datum}, path={path}, modified={self.last_mod_string})'

    __str__ = __repr__
    __unicode__ = __repr__

    @property
    def empty(self) -> bool:
        return not self.files and not self.folders

    @property
    def id_map(self) -> dict[ObjectId, FileOrFolder]:
        fs_cache = self.fs_cache()
        assert fs_cache is not None
        return fs_cache.id_maps[self.storage_id]

    @property
    def parent(self) -> FileOrFolder | None:
        if self.parent_id:
            return self.id_map[self.parent_id]
        if self.is_storage or self.parent_id is None:
            return None
        fs_cache2 = self.fs_cache()
        assert fs_cache2 is not None
        return fs_cache2.storage(self.storage_id)

    @property
    def in_root(self) -> bool:
        return self.parent_id is not None and self.parent_id == 0

    @property
    def storage(self) -> FileOrFolder | None:
        fs_cache3 = self.fs_cache()
        assert fs_cache3 is not None
        return fs_cache3.storage(self.storage_id)

    @property
    def full_path(self) -> tuple[str, ...]:
        parts: deque[str] = deque()
        parts.append(self.name)
        p = self.parent
        while p is not None:
            parts.appendleft(p.name)
            p = p.parent
        return tuple(parts)

    def __iter__(self) -> Iterator[FileOrFolder]:
        yield from self.folders
        yield from self.files

    def add_child(self, entry: MTPEntry) -> FileOrFolder:
        cache = self.fs_cache()
        assert cache is not None
        ans = FileOrFolder(entry, cache)
        t = self.folders if ans.is_folder else self.files
        t.append(ans)
        return ans

    def remove_child(self, entry: FileOrFolder) -> None:
        for x in (self.files, self.folders):
            try:
                x.remove(entry)
            except ValueError:
                pass
        self.id_map.pop(entry.object_id, None)
        entry.deleted = True

    def dump(self, prefix: str = '', out: IO[str] = sys.stdout) -> None:
        c = '+' if self.is_folder else '-'
        data = f'{sum(map(len, (self.files, self.folders)))} children' if self.is_folder else human_readable(self.size)
        data += f' modified={self.last_mod_string}'
        line = f'{prefix}{c} {self.name} [id:{self.object_id} {data}]'
        prints(line, file=out)
        for c in (self.folders, self.files):
            for e in sorted(c, key=lambda x: sort_key(x.name)):
                e.dump(prefix=prefix + '  ', out=out)

    def list(self, recurse: bool = False) -> Iterator[tuple[str, ListEntry | builtins.list[ListEntry]]]:
        if not self.is_folder:
            parent = self.parent
            assert parent is not None
            yield '/'.join(parent.full_path[1:]), ListEntry(self)
            return
        entries = [ListEntry(x) for x in chain(self.folders, self.files)]
        yield '/'.join(self.full_path[1:]), entries
        if recurse:
            for x in self.folders:
                yield from x.list(recurse=True)

    def folder_named(self, name: str) -> FileOrFolder | None:
        name = lower(name)
        for e in self.folders:
            if e.name and lower(e.name) == name:
                return e
        return None

    def file_named(self, name: str) -> FileOrFolder | None:
        name = lower(name)
        for e in self.files:
            if e.name and lower(e.name) == name:
                return e
        return None

    def find_path(self, path: Iterable[str]) -> FileOrFolder | None:
        """
        Find a path in this folder, where path is a
        tuple of folder and file names like ('eBooks', 'newest',
        'calibre.epub'). Finding is case-insensitive.
        """
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
    def mtp_relpath(self) -> tuple[str, ...]:
        return tuple(x.lower() for x in self.full_path[1:])

    @property
    def mtp_id_path(self) -> str:
        return 'mtp:::' + json.dumps(self.object_id) + ':::' + '/'.join(self.full_path)


class FilesystemCache:
    def __init__(self, all_storage: Iterable[dict[str, object]], entries: Iterable[MTPEntry]) -> None:
        self.entries: list[FileOrFolder] = []
        self.id_maps: defaultdict[ObjectId, dict[ObjectId, FileOrFolder]] = defaultdict(dict)
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

    def dump(self, out: IO[str] = sys.stdout) -> None:
        for e in self.entries:
            e.dump(out=out)

    def storage(self, storage_id: ObjectId | None) -> FileOrFolder | None:
        for e in self.entries:
            if e.storage_id == storage_id:
                return e

    def iterebooks(self, storage_id: ObjectId) -> Iterator[FileOrFolder]:
        id_map = self.id_maps[storage_id]
        for x in id_map.values():
            if x.is_ebook:
                if x.in_root and x.name.lower().endswith('.txt'):
                    continue  # Ignore .txt files in the root
                yield x

    def __len__(self) -> int:
        ans = len(self.id_maps)
        for id_map in self.id_maps.values():
            ans += len(id_map)
        return ans

    def resolve_mtp_id_path(self, path: str) -> FileOrFolder:
        if not path.startswith('mtp:::'):
            raise ValueError(f'{path} is not a valid MTP path')
        parts = path.split(':::', 2)
        if len(parts) < 3:
            raise ValueError(f'{path} is not a valid MTP path')
        try:
            object_id = json.loads(parts[1])
        except Exception:
            raise ValueError(f'{path} is not a valid MTP path')
        id_map: dict[ObjectId, FileOrFolder] = {}
        path = parts[2]
        storage_name = path.partition('/')[0]
        for entry in self.entries:
            if entry.name == storage_name:
                id_map = self.id_maps[entry.storage_id]
                break
        try:
            return id_map[object_id]
        except KeyError:
            raise ValueError(f'No object found with MTP path: {path}')
