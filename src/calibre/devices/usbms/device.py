__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Generic device driver. This is not a complete stand alone driver. It is
intended to be subclassed with the relevant parts implemented for a particular
device. This class handles device detection.
'''

import os, subprocess, time, re

from calibre.devices.interface import DevicePlugin
from calibre.devices.errors import DeviceError
from calibre import iswindows, islinux, isosx, __appname__

class Device(DevicePlugin):
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

    OSX_MAIN_MEM = None
    OSX_CARD_A_MEM = None
    OSX_CARD_B_MEM = None

    MAIN_MEMORY_VOLUME_LABEL  = ''
    STORAGE_CARD_VOLUME_LABEL = ''

    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="0">
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
                  <match key="@info.parent:storage.lun" int="1">
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
                  <match key="@info.parent:storage.lun" int="2">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
'''
    FDI_BCD_TEMPLATE = '<match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.device_revision_bcd" int="%(bcd)s">'


    def reset(self, key='-1', log_packets=False, report_progress=None) :
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

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
            csz = self._windows_space(self._card_prefix)[1]

        return (msz, casz, cbsz)

    def windows_match_device(self, pnp_id, device_id):
        pnp_id = pnp_id.upper()

        if device_id and pnp_id is not None:
            device_id = device_id.upper()

            if 'VEN_' + self.VENDOR_NAME in pnp_id and 'PROD_' + device_id in pnp_id:
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
        time.sleep(6)
        drives = {}
        wmi = __import__('wmi', globals(), locals(), [], -1)
        c = wmi.WMI(find_classes=False)
        for drive in c.Win32_DiskDrive():
            if self.windows_match_device(str(drive.PNPDeviceID), self.WINDOWS_MAIN_MEM):
                drives['main'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(str(drive.PNPDeviceID), self.WINDOWS_CARD_A_MEM):
                drives['carda'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(str(drive.PNPDeviceID), self.WINDOWS_CARD_B_MEM):
                drives['cardb'] = self.windows_get_drive_prefix(drive)

            if 'main' in drives.keys() and 'carda' in drives.keys() and 'cardb' in drives.keys():
                break

        if 'main' not in drives:
            raise DeviceError(
                _('Unable to detect the %s disk drive. Try rebooting.') %
                self.__class__.__name__)

        drives = self.windows_sort_drives(drives)
        self._main_prefix = drives.get('main')
        self._card_a_prefix = drives.get('carda', None)
        self._card_b_prefix = drives.get('cardb', None)

    def get_osx_mountpoints(self, raw=None):
        if raw is None:
            ioreg = '/usr/sbin/ioreg'
            if not os.access(ioreg, os.X_OK):
                ioreg = 'ioreg'
            raw = subprocess.Popen((ioreg+' -w 0 -S -c IOMedia').split(),
                                   stdout=subprocess.PIPE).communicate()[0]
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
            if self.OSX_MAIN_MEM is not None and line.strip().endswith('<class IOMedia>') and self.OSX_MAIN_MEM in line:
                get_dev_node(lines[i+1:], 'main')
            if self.OSX_CARD_A_MEM is not None and line.strip().endswith('<class IOMedia>') and self.OSX_CARD_A_MEM in line:
                get_dev_node(lines[i+1:], 'carda')
            if self.OSX_CARD_B_MEM is not None and line.strip().endswith('<class IOMedia>') and self.OSX_CARD_B_MEM in line:
                get_dev_node(lines[i+1:], 'cardb')
            if len(names.keys()) == 3:
                break
        return names

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

    def open_linux(self):
        import dbus
        bus = dbus.SystemBus()
        hm  = dbus.Interface(bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager"), "org.freedesktop.Hal.Manager")

        def conditional_mount(dev):
            mmo = bus.get_object("org.freedesktop.Hal", dev)
            label = mmo.GetPropertyString('volume.label', dbus_interface='org.freedesktop.Hal.Device')
            is_mounted = mmo.GetPropertyString('volume.is_mounted', dbus_interface='org.freedesktop.Hal.Device')
            mount_point = mmo.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
            fstype = mmo.GetPropertyString('volume.fstype', dbus_interface='org.freedesktop.Hal.Device')
            if is_mounted:
                return str(mount_point)
            mmo.Mount(label, fstype, ['umask=077', 'uid='+str(os.getuid()), 'sync'],
                          dbus_interface='org.freedesktop.Hal.Device.Volume')
            return os.path.normpath('/media/'+label)+'/'

        mm = hm.FindDeviceStringMatch(__appname__+'.mainvolume', self.__class__.__name__)
        if not mm:
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%(self.__class__.__name__,))
        self._main_prefix = None
        for dev in mm:
            try:
                self._main_prefix = conditional_mount(dev)+os.sep
                break
            except dbus.exceptions.DBusException:
                continue

        if not self._main_prefix:
            raise DeviceError('Could not open device for reading. Try a reboot.')

        self._card_a_prefix = self._card_b_prefix = None
        cards = hm.FindDeviceStringMatch(__appname__+'.cardvolume', self.__class__.__name__)

        def mount_card(dev):
            try:
                return conditional_mount(dev)+os.sep
            except:
                import traceback
                print traceback

        if len(cards) >= 1:
            self._card_a_prefix = mount_card(cards[0])
        if len(cards) >=2:
            self._card_b_prefix = mount_card(cards[1])

    def open(self):
        time.sleep(5)
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None
        if islinux:
            try:
                self.open_linux()
            except DeviceError:
                time.sleep(3)
                self.open_linux()
        if iswindows:
            try:
                self.open_windows()
            except DeviceError:
                time.sleep(3)
                self.open_windows()
        if isosx:
            try:
                self.open_osx()
            except DeviceError:
                time.sleep(3)
                self.open_osx()

