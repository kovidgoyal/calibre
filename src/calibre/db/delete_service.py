#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, tempfile, shutil, errno, time
from threading import Thread
from Queue import Queue

from calibre.utils.recycle_bin import delete_tree, delete_file

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

    def shutdown(self, timeout=20):
        self.requests.put(None)
        self.join(timeout)

    def create_staging(self, library_path):
        base_path = os.path.dirname(library_path)
        base = os.path.basename(library_path)
        try:
            return tempfile.mkdtemp(prefix=base+' deleted ', dir=base_path)
        except OSError:
            return tempfile.mkdtemp(prefix=base+' deleted ')

    def delete_books(self, paths, library_path):
        tdir = self.create_staging(library_path)
        self.queue_paths(tdir, paths, delete_empty_parent=True)

    def queue_paths(self, tdir, paths, delete_empty_parent=True):
        for path in paths:
            if os.path.exists(path):
                try:
                    shutil.move(path, tdir)
                except EnvironmentError:
                    # Wait a little in case something has locked a file
                    time.sleep(1)
                    shutil.move(path, tdir)
                if delete_empty_parent:
                    parent = os.path.dirname(path)
                    try:
                        os.rmdir(parent)
                    except OSError as e:
                        if e.errno != errno.ENOTEMPTY:
                            raise
                self.requests.put(os.path.join(tdir, os.path.basename(path)))

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

    def do_delete(self, x):
        if os.path.isdir(x):
            delete_tree(x)
        else:
            delete_file(x)
        try:
            os.rmdir(os.path.dirname(x))
        except OSError as e:
            if e.errno != errno.ENOTEMPTY:
                raise

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

