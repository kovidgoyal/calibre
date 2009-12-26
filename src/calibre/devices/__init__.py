__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Device drivers.
'''

import sys, os, time, pprint
from functools import partial
from StringIO import StringIO

DAY_MAP   = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
MONTH_MAP = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
INVERSE_DAY_MAP = dict(zip(DAY_MAP.values(), DAY_MAP.keys()))
INVERSE_MONTH_MAP = dict(zip(MONTH_MAP.values(), MONTH_MAP.keys()))

def strptime(src):
    src = src.strip()
    src = src.split()
    src[0] = str(DAY_MAP[src[0][:-1]])+','
    src[2] = str(MONTH_MAP[src[2]])
    return time.strptime(' '.join(src), '%w, %d %m %Y %H:%M:%S %Z')

def strftime(epoch, zone=time.gmtime):
    src = time.strftime("%w, %d %m %Y %H:%M:%S GMT", zone(epoch)).split()
    src[0] = INVERSE_DAY_MAP[int(src[0][:-1])]+','
    src[2] = INVERSE_MONTH_MAP[int(src[2])]
    return ' '.join(src)

def debug():
    from calibre.customize.ui import device_plugins
    from calibre.devices.scanner import DeviceScanner
    from calibre.constants import iswindows, isosx, __version__
    from calibre import prints
    oldo, olde = sys.stdout, sys.stderr

    buf = StringIO()
    sys.stdout = sys.stderr = buf
    try:
        out = partial(prints, file=buf)
        out('Version:', __version__)
        s = DeviceScanner()
        s.scan()
        devices = (s.devices)
        if not iswindows:
            devices = [list(x) for x in devices]
            for d in devices:
                for i in range(3):
                    d[i] = hex(d[i])
        out('USB devices on system:')
        out(pprint.pformat(devices))
        if iswindows:
            if iswindows:
                import pythoncom
                pythoncom.CoInitialize()
                try:
                    wmi = __import__('wmi', globals(), locals(), [], -1)
                    drives = []
                    out('Drives detected:')
                    out('\t', '(ID, Partitions, Drive letter)')
                    for drive in wmi.WMI(find_classes=False).Win32_DiskDrive():
                        if drive.Partitions == 0:
                            continue
                        try:
                            partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
                            logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
                            prefix = logical_disk.DeviceID+os.sep
                            drives.append((str(drive.PNPDeviceID), drive.Index, prefix))
                        except IndexError:
                            drives.append((str(drive.PNPDeviceID), 'No mount points found'))
                    for drive in drives:
                        out('\t', drive)
                finally:
                    pythoncom.CoUninitialize()

        ioreg = None
        if isosx:
            from calibre.devices.usbms.device import Device
            mount = repr(Device.osx_run_mount())
            ioreg = Device.run_ioreg()
            ioreg = 'Output from mount:\n\n'+mount+'\n\n'+ioreg
        connected_devices = []
        for dev in device_plugins():
            out('Looking for', dev.__class__.__name__)
            connected = s.is_device_connected(dev, debug=True)
            if connected:
                connected_devices.append(dev)

        errors = {}
        success = False
        for dev in connected_devices:
            out('Device possibly connected:', dev.__class__.name)
            out('Trying to open device...', end=' ')
            try:
                dev.open()
                out('OK')
            except:
                import traceback
                errors[dev] = traceback.format_exc()
                out('failed')
                continue
            success = True
            if hasattr(dev, '_main_prefix'):
                out('Main memory:', repr(dev._main_prefix))
            out('Total space:', dev.total_space())
            break
        if not success and errors:
            out('Opening of the following devices failed')
            for dev,msg in errors.items():
                out(dev)
                out(msg)
                out(' ')

        if ioreg is not None:
            out(' ')
            out('IOREG Output')
            out(ioreg)

        return buf.getvalue().decode('utf-8')
    finally:
        sys.stdout = oldo
        sys.stderr = olde

