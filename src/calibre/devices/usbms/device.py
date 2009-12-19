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

import os
import subprocess
import time
import re
import sys
import glob
from itertools import repeat

from calibre.devices.interface import DevicePlugin
from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre import iswindows, islinux, isosx, __appname__
from calibre.utils.filenames import shorten_components_to

class Device(DeviceConfig, DevicePlugin):

    '''
    This class provides logic common to all drivers for devices that export themselves
    as USB Mass Storage devices. If you are writing such a driver, inherit from this
    class.
    '''

    VENDOR_ID   = 0x0
    PRODUCT_ID  = 0x0
    BCD         = None

    VENDOR_NAME = None
    WINDOWS_MAIN_MEM = None
    WINDOWS_CARD_A_MEM = None
    WINDOWS_CARD_B_MEM = None

    # The following are used by the check_ioreg_line method and can be either:
    # None, a string, a list of strings or a compiled regular expression
    OSX_MAIN_MEM = None
    OSX_CARD_A_MEM = None
    OSX_CARD_B_MEM = None

    MAIN_MEMORY_VOLUME_LABEL  = ''
    STORAGE_CARD_VOLUME_LABEL = ''
    STORAGE_CARD2_VOLUME_LABEL = None

    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = False

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    EBOOK_DIR_CARD_B = ''
    DELETE_EXTS = []

    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun0)d">
                          <merge key="volume.label" type="string">%(main_memory)s</merge>
                          <merge key="%(app)s.mainvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun1)d">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun2)d">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
'''
    FDI_LUNS = {'lun0':0, 'lun1':1, 'lun2':2}
    FDI_BCD_TEMPLATE = '<match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.device_revision_bcd" int="%(bcd)s">'

    def reset(self, key='-1', log_packets=False, report_progress=None) :
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

    @classmethod
    def get_gui_name(cls):
        x = getattr(cls, 'gui_name', None)
        if x is None:
            x = cls.__name__
        return x


    @classmethod
    def get_fdi(cls):
        fdi = ''
        for vid in cls.VENDOR_ID:
            for pid in cls.PRODUCT_ID:
                fdi_base_values = dict(
                                       app=__appname__,
                                       deviceclass=cls.__name__,
                                       vendor_id=hex(vid),
                                       product_id=hex(pid),
                                       main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                       storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                  )
                fdi_base_values.update(cls.FDI_LUNS)

                if cls.BCD is None:
                    fdi_base_values['BCD_start'] = ''
                    fdi_base_values['BCD_end'] = ''
                    fdi += cls.FDI_TEMPLATE % fdi_base_values
                else:
                    for bcd in cls.BCD:
                        fdi_bcd_values = fdi_base_values
                        fdi_bcd_values['BCD_start'] = cls.FDI_BCD_TEMPLATE % dict(bcd=hex(bcd))
                        fdi_bcd_values['BCD_end'] = '</match>'
                        fdi += cls.FDI_TEMPLATE % fdi_bcd_values

        return fdi

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def card_prefix(self, end_session=True):
        return (self._card_a_prefix, self._card_b_prefix)

    @classmethod
    def _windows_space(cls, prefix):
        if not prefix:
            return 0, 0
        win32file = __import__('win32file', globals(), locals(), [], -1)
        try:
            sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                win32file.GetDiskFreeSpace(prefix[:-1])
        except Exception, err:
            if getattr(err, 'args', [None])[0] == 21: # Disk not ready
                time.sleep(3)
                sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                    win32file.GetDiskFreeSpace(prefix[:-1])
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

    def windows_match_device(self, drive, attr):
        pnp_id = (str(drive.PNPDeviceID) if not isinstance(drive, basestring)
                else str(drive)).upper()
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

    def windows_get_drive_prefix(self, drive):
        prefix = None

        try:
            partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
            logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
            prefix = logical_disk.DeviceID + os.sep
        except IndexError:
            pass

        return prefix

    def windows_sort_drives(self, drives):
        '''
        Called to disambiguate main memory and storage card for devices that
        do not distinguish between them on the basis of `WINDOWS_CARD_NAME`.
        For e.g.: The EB600
        '''
        return drives

    def open_windows(self):

        def matches_q(drive, attr):
            q = getattr(self, attr)
            if q is None: return False
            if isinstance(q, basestring):
                q = [q]
            pnp = str(drive.PNPDeviceID)
            for x in q:
                if x in pnp:
                    return True
            return False

        time.sleep(8)
        drives = {}
        wmi = __import__('wmi', globals(), locals(), [], -1)
        c = wmi.WMI(find_classes=False)
        for drive in c.Win32_DiskDrive():
            if self.windows_match_device(drive, 'WINDOWS_CARD_A_MEM') and not drives.get('carda', None):
                drives['carda'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(drive, 'WINDOWS_CARD_B_MEM') and not drives.get('cardb', None):
                drives['cardb'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(drive, 'WINDOWS_MAIN_MEM') and not drives.get('main', None):
                drives['main'] = self.windows_get_drive_prefix(drive)

            if 'main' in drives.keys() and 'carda' in drives.keys() and \
                    'cardb' in drives.keys():
                break

        # This is typically needed when the device has the same
        # WINDOWS_MAIN_MEM and WINDOWS_CARD_A_MEM in which case
        # if the devices is connected without a crad, the above
        # will incorrectly identify the main mem as carda
        # See for example the driver for the Nook
        if 'main' not in drives and 'carda' in drives:
            drives['main'] = drives.pop('carda')

        drives = self.windows_open_callback(drives)
        drives = self.windows_sort_drives(drives)

        if drives.get('main', None) is None:
            raise DeviceError(
                _('Unable to detect the %s disk drive. Try rebooting.') %
                self.__class__.__name__)

        self._main_prefix = drives.get('main')
        self._card_a_prefix = drives.get('carda', None)
        self._card_b_prefix = drives.get('cardb', None)

    def windows_open_callback(self, drives):
        return drives

    @classmethod
    def run_ioreg(cls, raw=None):
        if raw is not None:
            return raw
        ioreg = '/usr/sbin/ioreg'
        if not os.access(ioreg, os.X_OK):
            ioreg = 'ioreg'
        return subprocess.Popen((ioreg+' -w 0 -S -c IOMedia').split(),
                                stdout=subprocess.PIPE).communicate()[0]

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

    def open_osx(self):
        mount = subprocess.Popen('mount', shell=True,  stdout=subprocess.PIPE).stdout.read()
        names = self.get_osx_mountpoints()
        dev_pat = r'/dev/%s(\w*)\s+on\s+([^\(]+)\s+'
        if 'main' not in names.keys():
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%self.__class__.__name__)
        main_pat = dev_pat % names['main']
        self._main_prefix = re.search(main_pat, mount).group(2) + os.sep
        card_a_pat = names['carda'] if 'carda' in names.keys() else None
        card_b_pat = names['cardb'] if 'cardb' in names.keys() else None

        def get_card_prefix(pat):
            if pat is not None:
                pat = dev_pat % pat
                return re.search(pat, mount).group(2) + os.sep
            else:
                return None

        self._card_a_prefix = get_card_prefix(card_a_pat)
        self._card_b_prefix = get_card_prefix(card_b_pat)

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
            q = getattr(self, attr)
            if q is None: return True
            return q == val or val in q

        for x, isfile in walk('/sys/devices'):
            if isfile and x.endswith('idVendor'):
                usb_dir = d(x)
                for y in ('idProduct',):
                    if not os.access(j(usb_dir, y), os.R_OK):
                        usb_dir = None
                        continue
                e = lambda q : raw2num(open(j(usb_dir, q)).read())
                ven, prod = map(e, ('idVendor', 'idProduct'))
                if not (test(ven, 'VENDOR_ID') and test(prod, 'PRODUCT_ID')):
                    usb_dir = None
                    continue
                if self.BCD is not None:
                    if not os.access(j(usb_dir, 'bcdDevice'), os.R_OK) or \
                            not test(e('bcdDevice'), 'BCD'):
                        usb_dir = None
                        continue
                    else:
                        break
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

        def de_mangle(raw):
            return raw.replace('\\040', ' ').replace('\\011', '\t').replace('\\012',
                    '\n').replace('\\0134', '\\')

        for line in open('/proc/mounts').readlines():
            line = line.split()
            if line[0] == node:
                return de_mangle(line[1])
        return None

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
                    subprocess.Popen(['diskutil', 'eject', x])
                except:
                    pass

    def eject_linux(self):
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

    def get_main_ebook_dir(self):
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
            candidates = self.get_main_ebook_dir()
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
            if hasattr(obj, 'seek'):
                obj.seek(0, os.SEEK_END)
                size = obj.tell()
                obj.seek(0)
                return size
            return os.path.getsize(obj)

        sizes = [get_size(f) for f in files]
        size = sum(sizes)

        if not on_card and size > self.free_space()[0] - 2*1024*1024:
            raise FreeSpaceError(_("There is insufficient free space in main memory"))
        if on_card == 'carda' and size > self.free_space()[1] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if on_card == 'cardb' and size > self.free_space()[2] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        return path

    def create_upload_path(self, root, mdata, ext, id):
        from calibre.library.save_to_disk import config, get_components
        opts = config().parse()
        components = get_components(opts.template, mdata, id, opts.timefmt, 250)
        components = [str(x) for x in components]
        components = shorten_components_to(250 - len(root), components)
        filepath = '%s%s' % (os.path.join(root, *components), ext)
        filedir = os.path.dirname(filepath)

        if not self.SUPPORTS_SUB_DIRS or not self.settings().use_subdirs:
            filedir = root
            filepath = os.path.join(root, os.path.basename(filepath))

        if not os.path.exists(filedir):
            os.makedirs(filedir)

        return filepath
