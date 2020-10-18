#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, tempfile, shutil, errno, time, atexit
from threading import Thread

from calibre.constants import ismacos
from calibre.ptempfile import remove_dir
from calibre.utils.filenames import remove_dir_if_empty
from calibre.utils.recycle_bin import delete_tree, delete_file
from polyglot.queue import Queue


class DeleteService(Thread):

    ''' Provide a blocking file delete implementation with support for the
    recycle bin. On windows, deleting files to the recycle bin spins the event
    loop, which can cause locking errors in the main thread. We get around this
    by only moving the files/folders to be deleted out of the library in the
    main thread, they are deleted to recycle bin in a separate worker thread.

    This has the added advantage that doing a restore from the recycle bin wont
    cause metadata.db and the file system to get out of sync. Also, deleting
    becomes much faster, since in the common case, the move is done by a simple
    os.rename(). The downside is that if the user quits calibre while a long
    move to recycle bin is happening, the files may not all be deleted.'''

    daemon = True

    def __init__(self):
        Thread.__init__(self)
        self.requests = Queue()
        if ismacos:
            from calibre_extensions.cocoa import enable_cocoa_multithreading
            enable_cocoa_multithreading()

    def shutdown(self, timeout=20):
        self.requests.put(None)
        self.join(timeout)

    def create_staging(self, library_path):
        base_path = os.path.dirname(library_path)
        base = os.path.basename(library_path)
        try:
            ans = tempfile.mkdtemp(prefix=base+' deleted ', dir=base_path)
        except OSError:
            ans = tempfile.mkdtemp(prefix=base+' deleted ')
        atexit.register(remove_dir, ans)
        return ans

    def remove_dir_if_empty(self, path):
        try:
            os.rmdir(path)
        except OSError as e:
            if e.errno == errno.ENOTEMPTY or len(os.listdir(path)) > 0:
                # Some linux systems appear to raise an EPERM instead of an
                # ENOTEMPTY, see https://bugs.launchpad.net/bugs/1240797
                return
            raise

    def delete_books(self, paths, library_path):
        tdir = self.create_staging(library_path)
        self.queue_paths(tdir, paths, delete_empty_parent=True)

    def queue_paths(self, tdir, paths, delete_empty_parent=True):
        try:
            self._queue_paths(tdir, paths, delete_empty_parent=delete_empty_parent)
        except:
            if os.path.exists(tdir):
                shutil.rmtree(tdir, ignore_errors=True)
            raise

    def _queue_paths(self, tdir, paths, delete_empty_parent=True):
        requests = []
        for path in paths:
            if os.path.exists(path):
                basename = os.path.basename(path)
                c = 0
                while True:
                    dest = os.path.join(tdir, basename)
                    if not os.path.exists(dest):
                        break
                    c += 1
                    basename = '%d - %s' % (c, os.path.basename(path))
                try:
                    shutil.move(path, dest)
                except EnvironmentError:
                    if os.path.isdir(path):
                        # shutil.move may have partially copied the directory,
                        # so the subsequent call to move() will fail as the
                        # destination directory already exists
                        raise
                    # Wait a little in case something has locked a file
                    time.sleep(1)
                    shutil.move(path, dest)
                if delete_empty_parent:
                    remove_dir_if_empty(os.path.dirname(path), ignore_metadata_caches=True)
                requests.append(dest)
        if not requests:
            remove_dir_if_empty(tdir)
        else:
            self.requests.put(tdir)

    def delete_files(self, paths, library_path):
        tdir = self.create_staging(library_path)
        self.queue_paths(tdir, paths, delete_empty_parent=False)

    def run(self):
        while True:
            x = self.requests.get()
            try:
                if x is None:
                    break
                try:
                    self.do_delete(x)
                except:
                    import traceback
                    traceback.print_exc()
            finally:
                self.requests.task_done()

    def wait(self):
        'Blocks until all pending deletes have completed'
        self.requests.join()

    def do_delete(self, tdir):
        if os.path.exists(tdir):
            try:
                for x in os.listdir(tdir):
                    x = os.path.join(tdir, x)
                    if os.path.isdir(x):
                        delete_tree(x)
                    else:
                        delete_file(x)
            finally:
                shutil.rmtree(tdir)


__ds = None


def delete_service():
    global __ds
    if __ds is None:
        __ds = DeleteService()
        __ds.start()
    return __ds


def shutdown(timeout=20):
    global __ds
    if __ds is not None:
        __ds.shutdown(timeout)
        __ds = None


def has_jobs():
    global __ds
    if __ds is not None:
        return (not __ds.requests.empty()) or __ds.requests.unfinished_tasks
    return False
