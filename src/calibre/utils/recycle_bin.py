#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, time
from functools import partial

from calibre import isbytestring
from calibre.constants import (iswindows, isosx, plugins, filesystem_encoding,
        islinux)

recycle = None

if iswindows:
    import calibre.utils.winshell as winshell
    recycle = partial(winshell.delete_file, silent=True, no_confirm=True)
elif isosx:
    u = plugins['usbobserver'][0]
    if hasattr(u, 'send2trash'):
        def osx_recycle(path):
            if isbytestring(path):
                path = path.decode(filesystem_encoding)
            u.send2trash(path)
        recycle = osx_recycle
elif islinux:
    from calibre.utils.linux_trash import send2trash
    def fdo_recycle(path):
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        path = os.path.abspath(path)
        send2trash(path)
    recycle = fdo_recycle

can_recycle = callable(recycle)

def delete_file(path):
    if callable(recycle):
        try:
            recycle(path)
            return
        except:
            import traceback
            traceback.print_exc()
    os.remove(path)

def delete_tree(path, permanent=False):
    if permanent:
        try:
            # For completely mysterious reasons, sometimes a file is left open
            # leading to access errors. If we get an exception, wait and hope
            # that whatever has the file (Antivirus, DropBox?) lets go of it.
            shutil.rmtree(path)
        except:
            import traceback
            traceback.print_exc()
            time.sleep(1)
            shutil.rmtree(path)
    else:
        if callable(recycle):
            try:
                recycle(path)
                return
            except:
                import traceback
                traceback.print_exc()
        delete_tree(path, permanent=True)

