# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os
import shutil
import time
from typing import IO, TYPE_CHECKING

from calibre import fsync
from calibre.devices.errors import PathError
from calibre.utils import StreamOrPath
from calibre.utils.filenames import case_preserving_open_file

if TYPE_CHECKING:
    import builtins
    from collections.abc import Sequence


class File:
    def __init__(self, path: str) -> None:
        stats = os.stat(path)
        self.is_dir = os.path.isdir(path)
        self.is_readonly = not os.access(path, os.W_OK)
        self.ctime = getattr(stats, 'st_birthtime', stats.st_ctime)  # type: ignore
        self.wtime = stats.st_mtime
        self.size = stats.st_size
        if path.endswith(os.sep):
            path = path[:-1]
        self.path = path
        self.name = os.path.basename(path)


def check_transfer(infile: IO[bytes], dest: IO[bytes]) -> bool:
    infile.seek(0)
    dest.seek(0)
    return infile.read() == dest.read()


class CLI:
    _main_prefix: str | None = None
    _card_a_prefix: str | None = None
    _card_b_prefix: str | None = None
    SUPPORTS_SUB_DIRS: bool = False

    def delete_books(self, paths: Sequence[str], end_session: bool = True) -> None:
        raise NotImplementedError

    def get_file(self, path: str, outfile: IO[bytes], end_session: bool = True) -> None:
        path = self.munge_path(path)
        with open(path, 'rb') as src:
            shutil.copyfileobj(src, outfile)

    def put_file(self, infile: str | IO[bytes], path: str, replace_file: bool = False, end_session: bool = True) -> str:
        path = self.munge_path(path)
        with StreamOrPath(infile, 'rb') as infile:
            infile.seek(0)
            if os.path.isdir(path):
                path = os.path.join(path, infile.name)
            if not replace_file and os.path.exists(path):
                raise PathError('File already exists: ' + path)
            dest, actual_path = case_preserving_open_file(path)
            with dest:
                try:
                    shutil.copyfileobj(infile, dest)
                except OSError:
                    print('WARNING: First attempt to send file to device failed')
                    time.sleep(0.2)
                    infile.seek(0)
                    dest.seek(0)
                    dest.truncate()
                    shutil.copyfileobj(infile, dest)
                fsync(dest)
                # if not check_transfer(infile, dest): raise Exception('Transfer failed')
            return actual_path

    def munge_path(self, path: str) -> str:
        main = self._main_prefix or ''
        if path.startswith('/') and not (
            path.startswith(main)
            or (self._card_a_prefix and path.startswith(self._card_a_prefix))
            or (self._card_b_prefix and path.startswith(self._card_b_prefix))
        ):
            path = main + path[1:]
        elif path.startswith('carda:'):
            path = path.replace('carda:', (self._card_a_prefix or '')[:-1])
        elif path.startswith('cardb:'):
            path = path.replace('cardb:', (self._card_b_prefix or '')[:-1])
        return path

    def list(self, path: str, recurse: bool = False, end_session: bool = True, munge: bool = True) -> builtins.list[tuple[str, builtins.list[File]]]:
        if munge:
            path = self.munge_path(path)
        if os.path.isfile(path):
            return [(os.path.dirname(path), [File(path)])]
        entries = [File(os.path.join(path, f)) for f in os.listdir(path)]
        dirs = [(path, entries)]
        for _file in entries:
            if recurse and _file.is_dir:
                dirs[len(dirs) :] = self.list(_file.path, recurse=True, munge=False)
        return dirs

    def mkdir(self, path: str, end_session: bool = True) -> None:
        if self.SUPPORTS_SUB_DIRS:
            path = self.munge_path(path)
            os.mkdir(path)

    def rm(self, path: str, end_session: bool = True) -> None:
        path = self.munge_path(path)
        self.delete_books([path])

    def touch(self, path: str, end_session: bool = True) -> None:
        path = self.munge_path(path)
        if not os.path.exists(path):
            open(path, 'wb').close()
        if not os.path.isdir(path):
            os.utime(path, None)
