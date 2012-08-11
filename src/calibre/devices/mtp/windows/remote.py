#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, sys, os

def build():
    builder = subprocess.Popen('ssh xp_build ~/build-wpd'.split())
    syncer = subprocess.Popen('ssh getafix ~/test-wpd'.split())
    if builder.wait() != 0:
        raise Exception('Failed to build plugin')
    if syncer.wait() != 0:
        raise Exception('Failed to rsync to getafix')
    subprocess.check_call(
        'scp xp_build:build/calibre/src/calibre/plugins/wpd.pyd /tmp'.split())
    subprocess.check_call(
        'scp /tmp/wpd.pyd getafix:calibre/src/calibre/devices/mtp/windows'.split())
    p = subprocess.Popen(
        'ssh getafix calibre-debug -e calibre/src/calibre/devices/mtp/windows/remote.py'.split())
    p.wait()
    print()


def main():
    import pprint
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import wpd
    from calibre.constants import plugins
    plugins._plugins['wpd'] = (wpd, '')
    sys.path.pop(0)
    wpd.init('calibre', 1, 0, 0)
    try:
        for pnp_id in wpd.enumerate_devices():
            print (pnp_id)
            pprint.pprint(wpd.device_info(pnp_id))
    finally:
        wpd.uninit()

if __name__ == '__main__':
    main()

