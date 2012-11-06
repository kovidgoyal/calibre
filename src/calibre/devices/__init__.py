__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Device drivers.
'''

import sys, time, pprint, operator
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

def get_connected_device():
    from calibre.customize.ui import device_plugins
    from calibre.devices.scanner import DeviceScanner
    dev = None
    scanner = DeviceScanner()
    scanner.scan()
    connected_devices = []
    for d in device_plugins():
        ok, det = scanner.is_device_connected(d)
        if ok:
            dev = d
            dev.reset(log_packets=False, detected_device=det)
            connected_devices.append((det, dev))

    if dev is None:
        print >>sys.stderr, 'Unable to find a connected ebook reader.'
        return

    for det, d in connected_devices:
        try:
            d.open(det, None)
        except:
            continue
        else:
            dev = d
            break
    return dev

def debug(ioreg_to_tmp=False, buf=None, plugins=None,
        disabled_plugins=None):
    '''
    If plugins is None, then this method calls startup and shutdown on the
    device plugins. So if you are using it in a context where startup could
    already have been called (for example in the main GUI), pass in the list of
    device plugins as the plugins parameter.
    '''
    import textwrap
    from calibre.customize.ui import device_plugins, disabled_device_plugins
    from calibre.debug import print_basic_debug_info
    from calibre.devices.scanner import DeviceScanner, win_pnp_drives
    from calibre.constants import iswindows, isosx
    from calibre import prints
    oldo, olde = sys.stdout, sys.stderr

    if buf is None:
        buf = StringIO()
    sys.stdout = sys.stderr = buf
    out = partial(prints, file=buf)

    devplugins = device_plugins() if plugins is None else plugins
    devplugins = list(sorted(devplugins, cmp=lambda
            x,y:cmp(x.__class__.__name__, y.__class__.__name__)))
    if plugins is None:
        for d in devplugins:
            try:
                d.startup()
            except:
                out('Startup failed for device plugin: %s'%d)

    if disabled_plugins is None:
        disabled_plugins = list(disabled_device_plugins())

    try:
        print_basic_debug_info(out=buf)
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
            drives = win_pnp_drives(debug=True)
            out('Drives detected:')
            for drive in sorted(drives.keys(),
                    key=operator.attrgetter('order')):
                prints(u'\t(%d)'%drive.order, drive, '~', drives[drive])

        ioreg = None
        if isosx:
            from calibre.devices.usbms.device import Device
            mount = repr(Device.osx_run_mount())
            drives = pprint.pformat(Device.osx_get_usb_drives())
            ioreg = 'Output from mount:\n'+mount+'\n\n'
            ioreg += 'Output from osx_get_usb_drives:\n'+drives+'\n\n'
            ioreg += Device.run_ioreg()
        connected_devices = []
        if disabled_plugins:
            out('\nDisabled plugins:', textwrap.fill(' '.join([x.__class__.__name__ for x in
                disabled_plugins])))
            out(' ')
        found_dev = False
        for dev in devplugins:
            if not dev.MANAGES_DEVICE_PRESENCE: continue
            out('Looking for devices of type:', dev.__class__.__name__)
            if dev.debug_managed_device_detection(s.devices, buf):
                found_dev = True
                break
            out(' ')

        if not found_dev:
            out('Looking for devices...')
            for dev in devplugins:
                if dev.MANAGES_DEVICE_PRESENCE: continue
                connected, det = s.is_device_connected(dev, debug=True)
                if connected:
                    out('\t\tDetected possible device', dev.__class__.__name__)
                    connected_devices.append((dev, det))

            out(' ')
            errors = {}
            success = False
            out('Devices possibly connected:', end=' ')
            for dev, det in connected_devices:
                out(dev.name, end=', ')
            if not connected_devices:
                out('None', end='')
            out(' ')
            for dev, det in connected_devices:
                out('Trying to open', dev.name, '...', end=' ')
                try:
                    dev.reset(detected_device=det)
                    dev.open(det, None)
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
                ioreg = 'IOREG Output\n'+ioreg
                out(' ')
                if ioreg_to_tmp:
                    open('/tmp/ioreg.txt', 'wb').write(ioreg)
                    out('Dont forget to send the contents of /tmp/ioreg.txt')
                    out('You can open it with the command: open /tmp/ioreg.txt')
                else:
                    out(ioreg)

        if hasattr(buf, 'getvalue'):
            return buf.getvalue().decode('utf-8')
    finally:
        sys.stdout = oldo
        sys.stderr = olde
        if plugins is None:
            for d in devplugins:
                try:
                    d.shutdown()
                except:
                    pass

def device_info(ioreg_to_tmp=False, buf=None):
    from calibre.devices.scanner import DeviceScanner, win_pnp_drives
    from calibre.constants import iswindows
    import re

    res = {}
    device_details = {}
    device_set = set()
    drive_details = {}
    drive_set = set()
    res['device_set'] = device_set
    res['device_details'] = device_details
    res['drive_details'] = drive_details
    res['drive_set'] = drive_set

    try:
        s = DeviceScanner()
        s.scan()
        devices = (s.devices)
        if not iswindows:
            devices = [list(x) for x in devices]
            for dev in devices:
                for i in range(3):
                    dev[i] = hex(dev[i])
                d = dev[0] + dev[1] + dev[2]
                device_set.add(d)
                device_details[d] = dev[0:3]
        else:
            for dev in devices:
                vid = re.search('vid_([0-9a-f]*)&', dev)
                if vid:
                    vid = vid.group(1)
                    pid = re.search('pid_([0-9a-f]*)&', dev)
                    if pid:
                        pid = pid.group(1)
                        rev = re.search('rev_([0-9a-f]*)$', dev)
                        if rev:
                            rev = rev.group(1)
                            d = vid+pid+rev
                            device_set.add(d)
                            device_details[d] = (vid, pid, rev)

            drives = win_pnp_drives(debug=False)
            for drive,details in drives.iteritems():
                order = 'ORD_' + str(drive.order)
                ven = re.search('VEN_([^&]*)&', details)
                if ven:
                    ven = ven.group(1)
                    prod = re.search('PROD_([^&]*)&', details)
                    if prod:
                        prod = prod.group(1)
                        d = (order, ven, prod)
                        drive_details[drive] = d
                        drive_set.add(drive)
    finally:
        pass
    return res
