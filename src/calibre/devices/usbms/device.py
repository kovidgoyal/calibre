# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com> ' \
                '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Generic device driver. This is not a complete stand alone driver. It is
intended to be subclassed with the relevant parts implemented for a particular
device. This class handles device detection.
'''

import os, subprocess, time, re, sys, glob, operator
from itertools import repeat

from calibre.devices.interface import DevicePlugin
from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.constants import iswindows, islinux, isosx, plugins
from calibre.utils.filenames import ascii_filename as sanitize, shorten_components_to

if isosx:
    usbobserver, usbobserver_err = plugins['usbobserver']

class USBDevice:

    def __init__(self, dev):
        self.idVendor = dev[0]
        self.idProduct = dev[1]
        self.bcdDevice = dev[2]
        self.manufacturer = dev[3]
        self.product = dev[4]
        self.serial = dev[5]

    def match_serial(self, serial):
        return self.serial and self.serial == serial

    def match_numbers(self, vid, pid, bcd):
        return self.idVendor == vid and self.idProduct == pid and self.bcdDevice == bcd

    def match_strings(self, vid, pid, bcd, man, prod):
        return self.match_numbers(vid, pid, bcd) and \
                self.manufacturer == man and self.product == prod

class Device(DeviceConfig, DevicePlugin):

    '''
    This class provides logic common to all drivers for devices that export themselves
    as USB Mass Storage devices. Provides implementations for mounting/ejecting
    of USBMS devices on all platforms.
    '''

    VENDOR_ID   = 0x0
    PRODUCT_ID  = 0x0
    BCD         = None

    VENDOR_NAME = None

    #: String identifying the main memory of the device in the windows PnP id
    #: strings
    #: This can be None, string, list of strings or compiled regex
    WINDOWS_MAIN_MEM = None

    #: String identifying the first card of the device in the windows PnP id
    #: strings
    #: This can be None, string, list of strings or compiled regex
    WINDOWS_CARD_A_MEM = None

    #: String identifying the second card of the device in the windows PnP id
    #: strings
    #: This can be None, string, list of strings or compiled regex
    WINDOWS_CARD_B_MEM = None

    # The following are used by the check_ioreg_line method and can be either:
    # None, a string, a list of strings or a compiled regular expression
    OSX_MAIN_MEM = None
    OSX_CARD_A_MEM = None
    OSX_CARD_B_MEM = None

    #: Used by the new driver detection to disambiguate main memory from
    #: storage cards. Should be a regular expression that matches the
    #: main memory mount point assigned by OS X
    OSX_MAIN_MEM_VOL_PAT = None
    OSX_EJECT_COMMAND = ['diskutil', 'eject']

    MAIN_MEMORY_VOLUME_LABEL  = ''
    STORAGE_CARD_VOLUME_LABEL = ''
    STORAGE_CARD2_VOLUME_LABEL = None


    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    EBOOK_DIR_CARD_B = ''
    DELETE_EXTS = []

    # USB disk-based devices can see the book files on the device, so can
    # copy these back to the library
    BACKLOADING_ERROR_MESSAGE = None

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None):
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None
        try:
            self.detected_device = USBDevice(detected_device)
        except: # On windows detected_device is None
            self.detected_device = None
        self.set_progress_reporter(report_progress)

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress
        self.report_progress = report_progress
        if self.report_progress is None:
            self.report_progress = lambda x, y: x

    def card_prefix(self, end_session=True):
        return (self._card_a_prefix, self._card_b_prefix)

    @classmethod
    def _windows_space(cls, prefix):
        if not prefix:
            return 0, 0
        prefix = prefix[:-1]
        win32file = __import__('win32file', globals(), locals(), [], -1)
        try:
            sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                win32file.GetDiskFreeSpace(prefix)
        except Exception, err:
            if getattr(err, 'args', [None])[0] == 21: # Disk not ready
                time.sleep(3)
                sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                    win32file.GetDiskFreeSpace(prefix)
            else: raise
        mult = sectors_per_cluster * bytes_per_sector
        return total_clusters * mult, free_clusters * mult

    def total_space(self, end_session=True):
        msz = casz = cbsz = 0
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            if self._card_a_prefix is not None:
                stats = os.statvfs(self._card_a_prefix)
                casz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            if self._card_b_prefix is not None:
                stats = os.statvfs(self._card_b_prefix)
                cbsz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
        else:
            msz = self._windows_space(self._main_prefix)[0]
            casz = self._windows_space(self._card_a_prefix)[0]
            cbsz = self._windows_space(self._card_b_prefix)[0]

        return (msz, casz, cbsz)

    def free_space(self, end_session=True):
        msz = casz = cbsz = 0
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * stats.f_bavail
            if self._card_a_prefix is not None:
                stats = os.statvfs(self._card_a_prefix)
                casz = stats.f_frsize * stats.f_bavail
            if self._card_b_prefix is not None:
                stats = os.statvfs(self._card_b_prefix)
                cbsz = stats.f_frsize * stats.f_bavail
        else:
            msz = self._windows_space(self._main_prefix)[1]
            casz = self._windows_space(self._card_a_prefix)[1]
            cbsz = self._windows_space(self._card_b_prefix)[1]

        return (msz, casz, cbsz)

    def windows_filter_pnp_id(self, pnp_id):
        return False

    def windows_match_device(self, pnp_id, attr):
        device_id = getattr(self, attr)

        def test_vendor():
            vendors = [self.VENDOR_NAME] if isinstance(self.VENDOR_NAME,
                    basestring) else self.VENDOR_NAME
            for v in vendors:
                if 'VEN_'+str(v).upper() in pnp_id:
                    return True
            return False

        if device_id is None or not test_vendor():
            return False

        if self.windows_filter_pnp_id(pnp_id):
            return False

        if hasattr(device_id, 'search'):
            return device_id.search(pnp_id) is not None

        if isinstance(device_id, basestring):
            device_id = [device_id]

        for x in device_id:
            x = x.upper()

            if 'PROD_' + x in pnp_id:
                return True

        return False

    def windows_sort_drives(self, drives):
        '''
        Called to disambiguate main memory and storage card for devices that
        do not distinguish between them on the basis of `WINDOWS_CARD_NAME`.
        For e.g.: The EB600
        '''
        return drives

    def can_handle_windows(self, device_id, debug=False):
        from calibre.devices.scanner import win_pnp_drives
        drives = win_pnp_drives()
        for pnp_id in drives.values():
            if self.windows_match_device(pnp_id, 'WINDOWS_MAIN_MEM'):
                return True
            if debug:
                print '\tNo match found in:', pnp_id
        return False

    def open_windows(self):
        from calibre.devices.scanner import win_pnp_drives

        time.sleep(5)
        drives = {}
        for drive, pnp_id in win_pnp_drives().items():
            if self.windows_match_device(pnp_id, 'WINDOWS_CARD_A_MEM') and \
                    not drives.get('carda', False):
                drives['carda'] = drive
            elif self.windows_match_device(pnp_id, 'WINDOWS_CARD_B_MEM') and \
                    not drives.get('cardb', False):
                drives['cardb'] = drive
            elif self.windows_match_device(pnp_id, 'WINDOWS_MAIN_MEM') and \
                    not drives.get('main', False):
                drives['main'] = drive

            if 'main' in drives.keys() and 'carda' in drives.keys() and \
                    'cardb' in drives.keys():
                break

        # This is typically needed when the device has the same
        # WINDOWS_MAIN_MEM and WINDOWS_CARD_A_MEM in which case
        # if the device is connected without a card, the above
        # will incorrectly identify the main mem as carda
        # See for example the driver for the Nook
        if drives.get('carda', None) is not None and \
                drives.get('main', None) is None:
            drives['main'] = drives.pop('carda')

        if drives.get('main', None) is None:
            raise DeviceError(
                _('Unable to detect the %s disk drive. Try rebooting.') %
                self.__class__.__name__)

        # Sort drives by their PNP drive numbers if the CARD and MAIN
        # MEM strings are identical
        if self.WINDOWS_MAIN_MEM in (self.WINDOWS_CARD_A_MEM,
                self.WINDOWS_CARD_B_MEM) or \
                self.WINDOWS_CARD_A_MEM == self.WINDOWS_CARD_B_MEM:
            letters = sorted(drives.values(), key=operator.attrgetter('order'))
            drives = {}
            for which, letter in zip(['main', 'carda', 'cardb'], letters):
                drives[which] = letter

        drives = self.windows_sort_drives(drives)
        self._main_prefix = drives.get('main')
        self._card_a_prefix = drives.get('carda', None)
        self._card_b_prefix = drives.get('cardb', None)

    @classmethod
    def run_ioreg(cls, raw=None):
        if raw is not None:
            return raw
        ioreg = '/usr/sbin/ioreg'
        if not os.access(ioreg, os.X_OK):
            ioreg = 'ioreg'
        cmd = (ioreg+' -w 0 -S -c IOMedia').split()
        for i in range(3):
            try:
                return subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE).communicate()[0]
            except IOError: # Probably an interrupted system call
                if i == 2:
                    raise
            time.sleep(2)


    def osx_sort_names(self, names):
        return names

    def check_ioreg_line(self, line, pat):
        if pat is None:
            return False
        if not line.strip().endswith('<class IOMedia>'):
            return False
        if hasattr(pat, 'search'):
            return pat.search(line) is not None
        if isinstance(pat, basestring):
            pat = [pat]
        for x in pat:
            if x in line:
                return True
        return False

    def get_osx_mountpoints(self, raw=None):
        raw = self.run_ioreg(raw)
        lines = raw.splitlines()
        names = {}

        def get_dev_node(lines, loc):
            for line in lines:
                line = line.strip()
                if line.endswith('}'):
                    break
                match = re.search(r'"BSD Name"\s+=\s+"(.*?)"', line)
                if match is not None:
                    names[loc] = match.group(1)
                    break

        for i, line in enumerate(lines):
            if 'main' not in names and self.check_ioreg_line(line, self.OSX_MAIN_MEM):
                get_dev_node(lines[i+1:], 'main')
                continue
            if 'carda' not in names and self.check_ioreg_line(line, self.OSX_CARD_A_MEM):
                get_dev_node(lines[i+1:], 'carda')
                continue
            if 'cardb' not in names and self.check_ioreg_line(line, self.OSX_CARD_B_MEM):
                get_dev_node(lines[i+1:], 'cardb')
                continue
            if len(names.keys()) == 3:
                break
        return self.osx_sort_names(names)

    @classmethod
    def osx_run_mount(cls):
        for i in range(3):
            try:
                return subprocess.Popen('mount',
                                    stdout=subprocess.PIPE).communicate()[0]
            except IOError: # Probably an interrupted system call
                if i == 2:
                    raise
            time.sleep(2)

    @classmethod
    def osx_get_usb_drives(cls):
        if usbobserver_err:
            raise RuntimeError('Failed to load usbobserver: '+usbobserver_err)
        return usbobserver.get_usb_drives()

    def _osx_bsd_names(self):
        drives = self.osx_get_usb_drives()
        matches = []
        d = self.detected_device
        if d.serial:
            for path, vid, pid, bcd, ven, prod, serial in drives:
                if d.match_serial(serial):
                    matches.append(path)
        if not matches:
            if d.manufacturer and d.product:
                for path, vid, pid, bcd, man, prod, serial in drives:
                    if d.match_strings(vid, pid, bcd, man, prod):
                        matches.append(path)
            else:
                for path, vid, pid, bcd, man, prod, serial in drives:
                    if d.match_numbers(vid, pid, bcd):
                        matches.append(path)
        if not matches:
            raise DeviceError(
             'Could not detect BSD names for %s. Try rebooting.' % self.name)

        pat = re.compile(r'(?P<m>\d+)([a-z]+(?P<p>\d+)){0,1}')
        def nums(x):
            'Return (disk num, partition number)'
            m = pat.search(x)
            if m is None:
                return (10000, -1)
            g = m.groupdict()
            if g['p'] is None:
                g['p'] = 0
            return map(int, (g.get('m'), g.get('p')))

        def dcmp(x, y):
            '''
            Sorting based on the following scheme:
                - disks without partitions are first
                  - sub sorted based on disk number
                - disks with partitions are sorted first on
                  disk number, then on partition number
            '''
            x = x.rpartition('/')[-1]
            y = y.rpartition('/')[-1]
            x, y = nums(x), nums(y)
            if x[1] == 0 and y[1] > 0:
                return cmp(1, 2)
            if x[1] > 0 and y[1] == 0:
                return cmp(2, 1)
            ans = cmp(x[0], y[0])
            if ans == 0:
                ans = cmp(x[1], y[1])
            return ans

        matches.sort(cmp=dcmp)
        drives = {'main':matches[0]}
        if len(matches) > 1:
            drives['carda'] = matches[1]
        if len(matches) > 2:
            drives['cardb'] = matches[2]

        return drives

    def osx_bsd_names(self):
        drives = []
        for i in range(3):
            try:
                drives = self._osx_bsd_names()
                if len(drives) > 1: return drives
            except:
                if i == 2: raise
            time.sleep(3)
        return drives

    def open_osx(self):
        drives = self.osx_bsd_names()
        bsd_drives = dict(**drives)
        drives = self.osx_sort_names(drives)
        mount_map = usbobserver.get_mounted_filesystems()
        for k, v in drives.items():
            drives[k] = mount_map.get(v, None)
        if drives['main'] is None:
            print bsd_drives, mount_map, drives
            raise DeviceError(_('Unable to detect the %s mount point. Try rebooting.')%self.__class__.__name__)
        pat = self.OSX_MAIN_MEM_VOL_PAT
        if pat is not None and len(drives) > 1 and 'main' in drives:
            if pat.search(drives['main']) is None:
                main = drives['main']
                for x in ('carda', 'cardb'):
                    if x in drives and pat.search(drives[x]):
                        drives['main'] = drives.pop(x)
                        drives[x] = main
                        break

        self._main_prefix = drives['main']+os.sep
        def get_card_prefix(c):
            ans = drives.get(c, None)
            if ans is not None:
                ans += os.sep
            return ans
        self._card_a_prefix = get_card_prefix('carda')
        self._card_b_prefix = get_card_prefix('cardb')

    def find_device_nodes(self):

        def walk(base):
            base = os.path.abspath(os.path.realpath(base))
            for x in os.listdir(base):
                p = os.path.join(base, x)
                if os.path.islink(p) or not os.access(p, os.R_OK):
                    continue
                isfile = os.path.isfile(p)
                yield p, isfile
                if not isfile:
                    for y, q in walk(p):
                        yield y, q

        def raw2num(raw):
            raw = raw.lower()
            if not raw.startswith('0x'):
                raw = '0x' + raw
            return int(raw, 16)

        # Find device node based on vendor, product and bcd
        d, j = os.path.dirname, os.path.join
        usb_dir = None

        def test(val, attr):
            q = getattr(self.detected_device, attr)
            return q == val

        for x, isfile in walk('/sys/devices'):
            if isfile and x.endswith('idVendor'):
                usb_dir = d(x)
                for y in ('idProduct', 'idVendor', 'bcdDevice'):
                    if not os.access(j(usb_dir, y), os.R_OK):
                        usb_dir = None
                        continue
                e = lambda q : raw2num(open(j(usb_dir, q)).read())
                ven, prod, bcd = map(e, ('idVendor', 'idProduct', 'bcdDevice'))
                if not (test(ven, 'idVendor') and test(prod, 'idProduct') and
                        test(bcd, 'bcdDevice')):
                    usb_dir = None
                    continue
                else:
                    break

        if usb_dir is None:
            raise DeviceError(_('Unable to detect the %s disk drive.')
                    %self.__class__.__name__)

        devnodes, ok = [], {}
        for x, isfile in walk(usb_dir):
            if not isfile and '/block/' in x:
                parts = x.split('/')
                idx = parts.index('block')
                if idx == len(parts)-2:
                    sz = j(x, 'size')
                    node = parts[idx+1]
                    try:
                        exists = int(open(sz).read()) > 0
                        if exists:
                            node = self.find_largest_partition(x)
                            ok[node] = True
                        else:
                            ok[node] = False
                    except:
                        ok[node] = False
                    devnodes.append(node)

        devnodes += list(repeat(None, 3))
        ans = tuple(['/dev/'+x if ok.get(x, False) else None for x in devnodes[:3]])
        return self.linux_swap_drives(ans)

    def linux_swap_drives(self, drives):
        return drives

    def node_mountpoint(self, node):
        from calibre.devices.udisks import node_mountpoint
        return node_mountpoint(node)

    def find_largest_partition(self, path):
        node = path.split('/')[-1]
        nodes = []
        for x in glob.glob(path+'/'+node+'*'):
            sz = x + '/size'

            if not os.access(sz, os.R_OK):
                continue
            try:
                sz = int(open(sz).read())
            except:
                continue
            if sz > 0:
                nodes.append((x.split('/')[-1], sz))

        nodes.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        if not nodes:
            return node
        return nodes[-1][0]

    def open_linux(self):

        def mount(node, type):
            mp = self.node_mountpoint(node)
            if mp is not None:
                return mp, 0
            if type == 'main':
                label = self.MAIN_MEMORY_VOLUME_LABEL
            if type == 'carda':
                label = self.STORAGE_CARD_VOLUME_LABEL
            if type == 'cardb':
                label = self.STORAGE_CARD2_VOLUME_LABEL
                if not label:
                    label = self.STORAGE_CARD_VOLUME_LABEL + ' 2'
            extra = 0
            while True:
                q = ' (%d)'%extra if extra else ''
                if not os.path.exists('/media/'+label+q):
                    break
                extra += 1
            if extra:
                label += ' (%d)'%extra

            def do_mount(node, label):
                try:
                    from calibre.devices.udisks import mount
                    mount(node)
                    return 0
                except:
                    pass

                cmd = 'calibre-mount-helper'
                if getattr(sys, 'frozen_path', False):
                    cmd = os.path.join(sys.frozen_path, cmd)
                cmd = [cmd, 'mount']
                try:
                    p = subprocess.Popen(cmd + [node, '/media/'+label])
                except OSError:
                    raise DeviceError(
                    _('Could not find mount helper: %s.')%cmd[0])
                while p.poll() is None:
                    time.sleep(0.1)
                return p.returncode

            ret = do_mount(node, label)
            if ret != 0:
                return None, ret
            return self.node_mountpoint(node)+'/', 0

        main, carda, cardb = self.find_device_nodes()
        if main is None:
            raise DeviceError(_('Unable to detect the %s disk drive. Your '
            ' kernel is probably exporting a deprecated version of SYSFS.')
                    %self.__class__.__name__)

        self._linux_mount_map = {}
        mp, ret = mount(main, 'main')
        if mp is None:
            raise DeviceError(
            _('Unable to mount main memory (Error code: %d)')%ret)
        if not mp.endswith('/'): mp += '/'
        self._linux_mount_map[main] = mp
        self._main_prefix = mp
        self._linux_main_device_node = main
        cards = [(carda, '_card_a_prefix', 'carda'),
                 (cardb, '_card_b_prefix', 'cardb')]
        for card, prefix, typ in cards:
            if card is None: continue
            mp, ret = mount(card, typ)
            if mp is None:
                print >>sys.stderr, 'Unable to mount card (Error code: %d)'%ret
            else:
                if not mp.endswith('/'): mp += '/'
                setattr(self, prefix, mp)
                self._linux_mount_map[card] = mp

        self.filter_read_only_mount_points()

    def filter_read_only_mount_points(self):

        def is_readonly(mp):
            if mp is None:
                return True
            path = os.path.join(mp, 'calibre_readonly_test')
            ro = True
            try:
                with open(path, 'wb'):
                    ro = False
            except:
                pass
            else:
                try:
                    os.remove(path)
                except:
                    pass
            return ro

        for mp in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            if is_readonly(getattr(self, mp, None)):
                setattr(self, mp, None)

        if self._main_prefix is None:
            for p in ('_card_a_prefix', '_card_b_prefix'):
                nmp = getattr(self, p, None)
                if nmp is not None:
                    self._main_prefix = nmp
                    setattr(self, p, None)
                    break

        if self._main_prefix is None:
            raise DeviceError(_('The main memory of %s is read only. '
            'This usually happens because of file system errors.')
                    %self.__class__.__name__)

        if self._card_a_prefix is None and self._card_b_prefix is not None:
            self._card_a_prefix = self._card_b_prefix
            self._card_b_prefix = None



    def open(self):
        time.sleep(5)
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None
        if islinux:
            try:
                self.open_linux()
            except DeviceError:
                time.sleep(7)
                self.open_linux()
        if iswindows:
            try:
                self.open_windows()
            except DeviceError:
                time.sleep(7)
                self.open_windows()
        if isosx:
            try:
                self.open_osx()
            except DeviceError:
                time.sleep(7)
                self.open_osx()

        self.post_open_callback()

    def post_open_callback(self):
        pass

    def eject_windows(self):
        from calibre.constants import plugins
        from threading import Thread
        winutil, winutil_err = plugins['winutil']
        drives = []
        for x in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            x = getattr(self, x, None)
            if x is not None:
                drives.append(x[0].upper())

        def do_it(drives):
            for d in drives:
                try:
                    winutil.eject_drive(bytes(d)[0])
                except:
                    pass

        t = Thread(target=do_it, args=[drives])
        t.daemon = True
        t.start()
        self.__save_win_eject_thread = t

    def eject_osx(self):
        for x in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            x = getattr(self, x, None)
            if x is not None:
                try:
                    subprocess.Popen(self.OSX_EJECT_COMMAND + [x])
                except:
                    pass

    def eject_linux(self):
        try:
            from calibre.devices.udisks import eject
            return eject(self._linux_main_device_node)
        except:
            pass
        drives = self.find_device_nodes()
        for drive in drives:
            if drive:
                cmd = 'calibre-mount-helper'
                if getattr(sys, 'frozen_path', False):
                    cmd = os.path.join(sys.frozen_path, cmd)
                cmd = [cmd, 'eject']
                mp = getattr(self, "_linux_mount_map", {}).get(drive,
                        'dummy/')[:-1]
                try:
                    subprocess.Popen(cmd + [drive, mp]).wait()
                except:
                    pass

    def eject(self):
        if islinux:
            try:
                self.eject_linux()
            except:
                pass
        if iswindows:
            try:
                self.eject_windows()
            except:
                pass
        if isosx:
            try:
                self.eject_osx()
            except:
                pass
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

    def linux_post_yank(self):
        for drive, mp in getattr(self, '_linux_mount_map', {}).items():
            if drive and mp:
                mp = mp[:-1]
                cmd = 'calibre-mount-helper'
                if getattr(sys, 'frozen_path', False):
                    cmd = os.path.join(sys.frozen_path, cmd)
                cmd = [cmd, 'cleanup']
                if mp and os.path.exists(mp):
                    try:
                        subprocess.Popen(cmd + [drive, mp]).wait()
                    except:
                        import traceback
                        traceback.print_exc()
        self._linux_mount_map = {}

    def post_yank_cleanup(self):
        if islinux:
            try:
                self.linux_post_yank()
            except:
                import traceback
                traceback.print_exc()
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

    def get_main_ebook_dir(self, for_upload=False):
        return self.EBOOK_DIR_MAIN

    def _sanity_check(self, on_card, files):
        if on_card == 'carda' and not self._card_a_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card == 'cardb' and not self._card_b_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card and on_card not in ('carda', 'cardb'):
            raise DeviceError(_('Selected slot: %s is not supported.') % on_card)

        if on_card == 'carda':
            path = os.path.join(self._card_a_prefix,
                    *(self.EBOOK_DIR_CARD_A.split('/')))
        elif on_card == 'cardb':
            path = os.path.join(self._card_b_prefix,
                    *(self.EBOOK_DIR_CARD_B.split('/')))
        else:
            candidates = self.get_main_ebook_dir(for_upload=True)
            if isinstance(candidates, basestring):
                candidates = [candidates]
            candidates = [
                    ((os.path.join(self._main_prefix, *(x.split('/')))) if x else
                    self._main_prefix) for x
                    in candidates]
            existing = [x for x in candidates if os.path.exists(x)]
            if not existing:
                existing = candidates[:1]
            path = existing[0]

        def get_size(obj):
            path = getattr(obj, 'name', obj)
            return os.path.getsize(path)

        sizes = [get_size(f) for f in files]
        size = sum(sizes)

        if not on_card and size > self.free_space()[0] - 2*1024*1024:
            raise FreeSpaceError(_("There is insufficient free space in main memory"))
        if on_card == 'carda' and size > self.free_space()[1] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if on_card == 'cardb' and size > self.free_space()[2] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        return path

    def filename_callback(self, default, mi):
        '''
        Callback to allow drivers to change the default file name
        set by :meth:`create_upload_path`.
        '''
        return default

    def sanitize_path_components(self, components):
        '''
        Perform any device specific sanitization on the path components
        for files to be uploaded to the device
        '''
        return components

    def get_annotations(self, path_map):
        '''
        Resolve path_map to annotation_map of files found on the device
        '''
        return {}

    def create_upload_path(self, path, mdata, fname, create_dirs=True):
        path = os.path.abspath(path)
        extra_components = []

        special_tag = None
        if mdata.tags:
            for t in mdata.tags:
                if t.startswith(_('News')) or t.startswith('/'):
                    special_tag = t
                    break

        settings = self.settings()
        template = self.save_template()
        if mdata.tags and _('News') in mdata.tags:
            today = time.localtime()
            template = "{title}_%d-%d-%d" % (today[0], today[1], today[2])
        use_subdirs = self.SUPPORTS_SUB_DIRS and settings.use_subdirs

        fname = sanitize(fname)
        ext = os.path.splitext(fname)[1]

        from calibre.library.save_to_disk import get_components
        from calibre.library.save_to_disk import config
        opts = config().parse()
        if not isinstance(template, unicode):
            template = template.decode('utf-8')
        app_id = str(getattr(mdata, 'application_id', ''))
        # The db id will be in the created filename
        extra_components = get_components(template, mdata, fname,
                timefmt=opts.send_timefmt, length=250-len(app_id)-1)
        if not extra_components:
            extra_components.append(sanitize(self.filename_callback(fname,
                mdata)))
        else:
            extra_components[-1] = sanitize(self.filename_callback(extra_components[-1]+ext, mdata))

        if extra_components[-1] and extra_components[-1][0] in ('.', '_'):
            extra_components[-1] = 'x' + extra_components[-1][1:]

        if special_tag is not None:
            name = extra_components[-1]
            extra_components = []
            tag = special_tag
            if tag.startswith(_('News')):
                extra_components.append('News')
            else:
                for c in tag.split('/'):
                    c = sanitize(c)
                    if not c: continue
                    extra_components.append(c)
            extra_components.append(name)

        if not use_subdirs:
            extra_components = extra_components[-1:]

        def remove_trailing_periods(x):
            ans = x
            while ans.endswith('.'):
                ans = ans[:-1].strip()
            if not ans:
                ans = 'x'
            return ans

        extra_components = list(map(remove_trailing_periods, extra_components))
        components = shorten_components_to(250 - len(path), extra_components)
        components = self.sanitize_path_components(components)
        filepath = os.path.join(path, *components)
        filedir = os.path.dirname(filepath)


        if create_dirs and not os.path.exists(filedir):
            os.makedirs(filedir)

        return filepath
