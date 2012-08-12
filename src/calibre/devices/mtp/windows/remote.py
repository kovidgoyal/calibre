#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, sys, os, pprint

def build(mod='wpd'):
    builder = subprocess.Popen('ssh xp_build ~/build-wpd'.split())
    syncer = subprocess.Popen('ssh getafix ~/test-wpd'.split())
    if builder.wait() != 0:
        raise Exception('Failed to build plugin')
    if syncer.wait() != 0:
        raise Exception('Failed to rsync to getafix')
    subprocess.check_call(
        ('scp xp_build:build/calibre/src/calibre/plugins/%s.pyd /tmp'%mod).split())
    subprocess.check_call(
        ('scp /tmp/%s.pyd getafix:calibre/src/calibre/devices/mtp/windows'%mod).split())
    p = subprocess.Popen(
        'ssh getafix calibre-debug -e calibre/src/calibre/devices/mtp/windows/remote.py'.split())
    p.wait()
    print()


def main():
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

def winutil():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    del sys.modules['winutil']
    import winutil
    from calibre.constants import plugins
    plugins._plugins['winutil'] = (winutil, '')
    sys.path.pop(0)
    print (winutil.serial_number_from_drive('F'))

def get_subkeys(key):
    import _winreg
    index = -1
    while True:
        index += 1
        try:
            yield _winreg.EnumKey(key, index)
        except OSError:
            break

def get_values(key):
    import _winreg
    index = -1
    while True:
        index +=1
        try:
            yield _winreg.EnumValue(key, index)
        except OSError:
            break

def test():
    vid, pid = 0x1949, 0x4
    import _winreg as r
    usb = r.OpenKey(r.HKEY_LOCAL_MACHINE, 'SYSTEM\\CurrentControlSet\\Enum\\USB')
    q = ('vid_%4.4x&pid_%4.4x'%(vid, pid))
    dev = r.OpenKey(usb, q)
    print (list(get_subkeys(dev)))

if __name__ == '__main__':
    # main()
    winutil()

