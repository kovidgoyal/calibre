#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

AUTHTOOL="""#!%s
import os
scripts = %s
links = %s
os.setuid(0)
for s, l in zip(scripts, links):
    if os.path.lexists(l):
        os.remove(l)
    print 'Creating link:', l, '->', s
    omask = os.umask(022)
    os.symlink(s, l)
    os.umask(omask)
"""

DEST_PATH = '/usr/bin'

def create_symlinks():
    import os, tempfile, traceback, sys
    from Authorization import Authorization, kAuthorizationFlagDestroyRights
    from calibre.resources import scripts


    resources_path = os.environ['RESOURCEPATH']
    links   = [os.path.join(DEST_PATH, i) for i in scripts]
    scripts = [os.path.join(resources_path, 'loaders', i) for i in scripts]

    bad = False
    for s, l in zip(scripts, links):
        if os.path.exists(l) and os.path.exists(os.path.realpath(l)):
            continue
        bad = True
        break
    if bad:
        auth = Authorization(destroyflags=(kAuthorizationFlagDestroyRights,))
        fd, name = tempfile.mkstemp('.py')
        os.write(fd, AUTHTOOL % (sys.executable, repr(scripts), repr(links)))
        os.close(fd)
        os.chmod(name, 0700)
        try:
            pipe = auth.executeWithPrivileges(sys.executable, name)
            sys.stdout.write(pipe.read())
            pipe.close()
        except:
            traceback.print_exc()
        finally:
            os.unlink(name)

    return DEST_PATH, links

