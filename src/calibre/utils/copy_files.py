#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import stat
import time
from collections import defaultdict
from contextlib import suppress
from typing import Callable, Dict, List, Set, Tuple, Union

from calibre.constants import filesystem_encoding, iswindows
from calibre.utils.filenames import make_long_path_useable, samefile, windows_hardlink

if iswindows:
    from calibre_extensions import winutil

WINDOWS_SLEEP_FOR_RETRY_TIME = 2  # seconds
WindowsFileId = Tuple[int, int, int]

class UnixFileCopier:

    def __init__(self, delete_all=False, allow_move=False):
        self.delete_all = delete_all
        self.allow_move = allow_move
        self.copy_map: Dict[str, str] = {}

    def register(self, path: str, dest: str) -> None:
        self.copy_map[path] = dest

    def register_folder(self, path: str) -> None:
        pass

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.delete_all and exc_val is None:
            self.delete_all_source_files()

    def rename_all(self) -> None:
        for src_path, dest_path in self.copy_map.items():
            os.replace(src_path, dest_path)

    def copy_all(self) -> None:
        for src_path, dest_path in self.copy_map.items():
            with suppress(OSError):
                os.link(src_path, dest_path, follow_symlinks=False)
                try:
                    shutil.copystat(src_path, dest_path, follow_symlinks=False)
                except OSError:
                    # Failure to copy metadata is not critical
                    import traceback
                    traceback.print_exc()
                continue
            with suppress(shutil.SameFileError):
                shutil.copy2(src_path, dest_path, follow_symlinks=False)

    def delete_all_source_files(self) -> None:
        for src_path in self.copy_map:
            with suppress(FileNotFoundError):
                os.unlink(src_path)


def windows_lock_path_and_callback(path: str, f: Callable) -> None:
    is_folder = os.path.isdir(path)
    flags = winutil.FILE_FLAG_BACKUP_SEMANTICS if is_folder else winutil.FILE_FLAG_SEQUENTIAL_SCAN
    h = winutil.create_file(make_long_path_useable(path), winutil.GENERIC_READ, 0, winutil.OPEN_EXISTING, flags)
    try:
        f()
    finally:
        h.close()


class WindowsFileCopier:

    '''
    Locks all files before starting the copy, ensuring other processes cannot interfere
    '''

    def __init__(self, delete_all=False, allow_move=False):
        self.delete_all = delete_all
        self.allow_move = allow_move
        self.path_to_fileid_map : Dict[str, WindowsFileId] = {}
        self.fileid_to_paths_map: Dict[WindowsFileId, Set[str]] = defaultdict(set)
        self.path_to_handle_map: Dict[str, 'winutil.Handle'] = {}
        self.folder_to_handle_map: Dict[str, 'winutil.Handle'] = {}
        self.folders: List[str] = []
        self.copy_map: Dict[str, str] = {}

    def register(self, path: str, dest: str) -> None:
        with suppress(OSError):
            # Ensure the file is not read-only
            winutil.set_file_attributes(make_long_path_useable(path), winutil.FILE_ATTRIBUTE_NORMAL)
        self.path_to_fileid_map[path] = winutil.get_file_id(make_long_path_useable(path))
        self.copy_map[path] = dest

    def register_folder(self, path: str) -> None:
        with suppress(OSError):
            # Ensure the folder is not read-only
            winutil.set_file_attributes(make_long_path_useable(path), winutil.FILE_ATTRIBUTE_NORMAL)
        self.path_to_fileid_map[path] = winutil.get_file_id(make_long_path_useable(path))
        self.folders.append(path)

    def _open_file(self, path: str, retry_on_sharing_violation: bool = True, is_folder: bool = False) -> 'winutil.Handle':
        flags = winutil.FILE_FLAG_BACKUP_SEMANTICS if is_folder else winutil.FILE_FLAG_SEQUENTIAL_SCAN
        access_flags = winutil.GENERIC_READ
        if self.delete_all:
            access_flags |= winutil.DELETE
        share_flags = winutil.FILE_SHARE_DELETE if self.allow_move else 0
        try:
            return winutil.create_file(make_long_path_useable(path), access_flags, share_flags, winutil.OPEN_EXISTING, flags)
        except OSError as e:
            if e.winerror == winutil.ERROR_SHARING_VIOLATION:
                # The file could be a hardlink to an already opened file,
                # in which case we use the same handle for both files
                fileid = self.path_to_fileid_map[path]
                for other in self.fileid_to_paths_map[fileid]:
                    if other in self.path_to_handle_map:
                        return self.path_to_handle_map[other]
                if retry_on_sharing_violation:
                    time.sleep(WINDOWS_SLEEP_FOR_RETRY_TIME)
                    return self._open_file(path, False, is_folder)
            raise

    def open_all_handles(self) -> None:
        for path, file_id in self.path_to_fileid_map.items():
            self.fileid_to_paths_map[file_id].add(path)
        for src in self.copy_map:
            self.path_to_handle_map[src] = self._open_file(src)
        for path in self.folders:
            self.folder_to_handle_map[path] = self._open_file(path, is_folder=True)

    def __enter__(self) -> None:
        try:
            self.open_all_handles()
        except OSError:
            self.close_all_handles()
            raise

    def close_all_handles(self, delete_on_close: bool = False) -> None:
        while self.path_to_handle_map:
            path, h = next(iter(self.path_to_handle_map.items()))
            if delete_on_close:
                winutil.set_file_handle_delete_on_close(h, True)
            h.close()
            self.path_to_handle_map.pop(path)
        while self.folder_to_handle_map:
            path, h = next(reversed(self.folder_to_handle_map.items()))
            if delete_on_close:
                try:
                    winutil.set_file_handle_delete_on_close(h, True)
                except OSError as err:
                    # Ignore dir not empty errors. Should never happen but we
                    # ignore it as the UNIX semantics are to not delete folders
                    # during __exit__ anyway and we dont want to leak the handle.
                    if err.winerror != winutil.ERROR_DIR_NOT_EMPTY:
                        raise
            h.close()
            self.folder_to_handle_map.pop(path)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close_all_handles(delete_on_close=self.delete_all and exc_val is None)

    def copy_all(self) -> None:
        for src_path, dest_path in self.copy_map.items():
            with suppress(Exception):
                windows_hardlink(make_long_path_useable(src_path), make_long_path_useable(dest_path))
                shutil.copystat(make_long_path_useable(src_path), make_long_path_useable(dest_path), follow_symlinks=False)
                continue
            handle = self.path_to_handle_map[src_path]
            winutil.set_file_pointer(handle, 0, winutil.FILE_BEGIN)
            with open(make_long_path_useable(dest_path), 'wb') as f:
                sz = 1024 * 1024
                while True:
                    raw = winutil.read_file(handle, sz)
                    if not raw:
                        break
                    f.write(raw)
            shutil.copystat(make_long_path_useable(src_path), make_long_path_useable(dest_path), follow_symlinks=False)

    def rename_all(self) -> None:
        for src_path, dest_path in self.copy_map.items():
            winutil.move_file(make_long_path_useable(src_path), make_long_path_useable(dest_path))


def get_copier(delete_all=False, allow_move=False) -> Union[UnixFileCopier, WindowsFileCopier]:
    return (WindowsFileCopier if iswindows else UnixFileCopier)(delete_all, allow_move)


def rename_files(src_to_dest_map: Dict[str, str]) -> None:
    ' Rename a bunch of files. On Windows all files are locked before renaming so no other process can interfere. '
    copier = get_copier(allow_move=True)
    for s, d in src_to_dest_map.items():
        copier.register(s, d)
    with copier:
        copier.rename_all()


def copy_files(src_to_dest_map: Dict[str, str], delete_source: bool = False) -> None:
    copier = get_copier(delete_source)
    for s, d in src_to_dest_map.items():
        if not samefile(s, d):
            copier.register(s, d)
    with copier:
        copier.copy_all()


def identity_transform(src_path: str, dest_path: str) -> str:
    return dest_path


def register_folder_recursively(
    src: str, copier: Union[UnixFileCopier, WindowsFileCopier], dest_dir: str,
    transform_destination_filename: Callable[[str, str], str] = identity_transform,
    read_only: bool = False
) -> None:

    def dest_from_entry(dirpath: str, x: str) -> str:
        path = os.path.join(dirpath, x)
        rel = os.path.relpath(path, src)
        return os.path.join(dest_dir, rel)

    def raise_error(e: OSError) -> None:
        raise e

    copier.register_folder(src)
    for (dirpath, dirnames, filenames) in os.walk(src, onerror=raise_error):
        for d in dirnames:
            path = os.path.join(dirpath, d)
            dest = dest_from_entry(dirpath, d)
            if not read_only:
                os.makedirs(make_long_path_useable(dest), exist_ok=True)
                shutil.copystat(make_long_path_useable(path), make_long_path_useable(dest), follow_symlinks=False)
            copier.register_folder(path)
        for f in filenames:
            path = os.path.join(dirpath, f)
            dest = dest_from_entry(dirpath, f)
            dest = transform_destination_filename(path, dest)
            if not iswindows and not read_only:
                s = os.stat(path, follow_symlinks=False)
                if stat.S_ISLNK(s.st_mode):
                    link_dest = os.readlink(path)
                    os.symlink(link_dest, dest)
                    continue
            copier.register(path, dest)


def windows_check_if_files_in_use(src_folder: str) -> None:
    copier = get_copier()
    register_folder_recursively(src_folder, copier, os.getcwd(), read_only=True)
    with copier:
        pass


def copy_tree(
    src: str, dest: str,
    transform_destination_filename: Callable[[str, str], str] = identity_transform,
    delete_source: bool = False
) -> None:
    '''
    Copy all files in the tree over. On Windows locks all files before starting the copy to ensure that
    other processes cannot interfere once the copy starts. Uses hardlinks, falling back to actual file copies
    only if hardlinking fails.
    '''
    if iswindows:
        if isinstance(src, bytes):
            src = src.decode(filesystem_encoding)
        if isinstance(dest, bytes):
            dest = dest.decode(filesystem_encoding)

    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    if samefile(src, dest):
        raise ValueError(f'Cannot copy tree if the source and destination are the same: {src!r} == {dest!r}')
    dest_dir = dest

    copier = get_copier(delete_source)
    register_folder_recursively(src, copier, dest_dir, transform_destination_filename)

    with copier:
        copier.copy_all()

    if delete_source and os.path.exists(make_long_path_useable(src)):
        try:
            shutil.rmtree(make_long_path_useable(src))
        except FileNotFoundError:
            # some kind of delayed folder removal on handle close on Windows? Or exists() is succeeding but
            # rmdir() is failing? Or something deleted the
            # folder between the call to exists() and rmtree(). Windows is full
            # of nanny programs that keep users safe from "themselves".
            pass
        except OSError:
            if iswindows:
                time.sleep(WINDOWS_SLEEP_FOR_RETRY_TIME)
                shutil.rmtree(make_long_path_useable(src))
            else:
                raise
