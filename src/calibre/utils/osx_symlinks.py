#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, cPickle
from calibre.constants import isnewosx

AUTHTOOL="""#!/usr/bin/python
import os
scripts = %s
links = %s
os.setuid(0)
for s, l in zip(scripts, links):
    try:
        os.remove(l)
    except:
        pass
    print 'Creating link:', l, '->', s
    omask = os.umask(022)
    os.symlink(s, l)
    os.umask(omask)
"""

DEST_PATH = '/usr/bin'

def create_symlinks():
    return create_symlinks_new() if isnewosx else create_symlinks_old()

def get_scripts():
    return cPickle.load(open(P('scripts.pickle'), 'rb'))

def create_symlinks_new():
    scripts = get_scripts()

    links   = [os.path.join(DEST_PATH, i) for i in scripts]
    scripts = [os.path.join(
        sys.binaries_path if scripts[i] == 'gui' else sys.console_binaries_path, i) for i in scripts]

    return do_it(scripts, links)


def create_symlinks_old():
    scripts = get_scripts()

    resources_path = os.environ['RESOURCEPATH']
    links   = [os.path.join(DEST_PATH, i) for i in scripts]
    scripts = [os.path.join(resources_path, 'loaders', i) for i in scripts]

    return do_it(scripts, links)

def do_it(scripts, links):
    import os, tempfile, traceback
    from Authorization import Authorization, kAuthorizationFlagDestroyRights
    r1, r2 = DEST_PATH, links
    bad = False
    for s, l in zip(scripts, links):
        if os.path.exists(l) and os.path.exists(os.path.realpath(l)):
            continue
        bad = True
        break
    if bad:
        ph, pp = os.environ.get('PYTHONHOME', None), os.environ.get('PYTHONPATH', None)
        auth = Authorization(destroyflags=(kAuthorizationFlagDestroyRights,))
        fd, name = tempfile.mkstemp('.py')
        os.write(fd, AUTHTOOL % (repr(scripts), repr(links)))
        os.close(fd)
        os.chmod(name, 0700)
        try:
            if pp:
                del os.environ['PYTHONPATH']
            if ph:
                del os.environ['PYTHONHOME']
            pipe = auth.executeWithPrivileges(name)
            try:
                sys.stdout.write(pipe.read())
            except:
                sys.stdout.write(pipe.read()) # Probably EINTR
            pipe.close()
        except:
            r1, r2 = None, traceback.format_exc()
        finally:
            os.unlink(name)
            if pp:
                os.environ['PYTHONPATH'] = pp
            if ph:
                os.environ['PYTHONHOME'] = ph

    return r1, r2

