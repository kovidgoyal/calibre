#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, sys, os, pprint, signal, time, glob, io
pprint, io

def build(mod='wpd'):
    master = subprocess.Popen('ssh -MN getafix'.split())
    master2 = subprocess.Popen('ssh -MN xp_build'.split())
    try:
        while not glob.glob(os.path.expanduser('~/.ssh/*kovid@xp_build*')):
            time.sleep(0.05)
        builder = subprocess.Popen('ssh xp_build ~/build-wpd'.split())
        if builder.wait() != 0:
            raise Exception('Failed to build plugin')
        while not glob.glob(os.path.expanduser('~/.ssh/*kovid@getafix*')):
            time.sleep(0.05)
        syncer = subprocess.Popen('ssh getafix ~/test-wpd'.split())
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
    finally:
        for m in (master2, master):
            m.send_signal(signal.SIGHUP)
        for m in (master2, master):
            m.wait()

def main():
    fp, d = os.path.abspath(__file__), os.path.dirname
    if b'CALIBRE_DEVELOP_FROM' not in os.environ:
        env = os.environ.copy()
        env[b'CALIBRE_DEVELOP_FROM'] = bytes(d(d(d(d(d(fp))))))
        subprocess.call(['calibre-debug', '-e', fp], env=env)
        return

    sys.path.insert(0, os.path.dirname(fp))
    if 'wpd' in sys.modules:
        del sys.modules['wpd']
    import wpd
    from calibre.constants import plugins
    plugins._plugins['wpd'] = (wpd, '')
    sys.path.pop(0)

    from calibre.devices.scanner import win_scanner
    from calibre.devices.mtp.windows.driver import MTP_DEVICE
    dev = MTP_DEVICE(None)
    dev.startup()
    print (dev.wpd, dev.wpd_error)

    try:
        devices = win_scanner()
        pnp_id = dev.detect_managed_devices(devices)
        if not pnp_id:
            raise ValueError('Failed to detect device')
        # pprint.pprint(dev.detected_devices)
        print ('Trying to connect to:', pnp_id)
        dev.open(pnp_id, '')
        pprint.pprint(dev.dev.data)
        print ('Connected to:', dev.get_gui_name())
        print ('Total space', dev.total_space())
        print ('Free space', dev.free_space())
        # pprint.pprint(dev.dev.create_folder(dev.filesystem_cache.entries[0].object_id,
        #     'zzz'))
        # print ('Fetching file: oFF (198214 bytes)')
        # stream = dev.get_file('oFF')
        # print ("Fetched size: ", stream.tell())
        size = 4
        stream = io.BytesIO(b'a'*size)
        name = 'zzz-test-file.txt'
        stream.seek(0)
        f = dev.put_file(dev.filesystem_cache.entries[0], name, stream, size)
        print ('Put file:', f)
        # dev.filesystem_cache.dump()
    finally:
        dev.shutdown()

    print ('Device connection shutdown')

if __name__ == '__main__':
    main()

