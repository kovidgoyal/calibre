__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Generic device driver. This is not a complete stand alone driver. It is
intended to be subclassed with the relevant parts implemented for a particular
device. This class handles devive detection.
'''

import os, time

from calibre.devices.interface import Device as _Device
from calibre.devices.errors import DeviceError
from calibre import iswindows, islinux, isosx, __appname__

class Device(_Device):
    '''
    This class provides logic common to all drivers for devices that export themselves
    as USB Mass Storage devices. If you are writing such a driver, inherit from this
    class.
    '''
    
    VENDOR_ID   = 0x0
    PRODUCT_ID  = 0x0
    BCD         = None
    
    VENDOR_NAME = ''
    PRODUCT_NAME = ''
    
    OSX_NAME_MAIN_MEM = ''
    OSX_NAME_CARD_MEM = ''
    
    MAIN_MEMORY_VOLUME_LABEL  = ''
    STORAGE_CARD_VOLUME_LABEL = ''
        
    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                  <match key="volume.is_partition" bool="false">
                          <merge key="volume.label" type="string">%(main_memory)s</merge>
                          <merge key="%(app)s.mainvolume" type="string">%(deviceclass)s</merge>
                  </match>
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                  <match key="volume.is_partition" bool="true">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
              </match>
          </match>
      </match>
  </device>
'''
    
    def __init__(self, key='-1', log_packets=False, report_progress=None) :
        self._main_prefix = self._card_prefix = None
    
    @classmethod
    def get_bcd_less_fdi(cls):
        return cls.FDI_TEMPLATE%dict(
                                     app=__appname__,
                                     deviceclass=cls.__name__,
                                     vendor_id=hex(cls.VENDOR_ID),
                                     product_id=hex(cls.PRODUCT_ID),
                                     main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                     storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                     )
    
    @classmethod
    def get_fdi(cls):
        if cls.BCD is None:
            return cls.get_bcd_less_fdi()
        raise NotImplementedError('TODO:')
    
    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress
    
    def card_prefix(self, end_session=True):
        return self._card_prefix

    @classmethod
    def _windows_space(cls, prefix):
        if prefix is None:
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
        msz = csz = 0
        print self._main_prefix
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            if self._card_prefix is not None:
                stats = os.statvfs(self._card_prefix)
                csz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
        else:
            msz = self._windows_space(self._main_prefix)[0]
            csz = self._windows_space(self._card_prefix)[0]
                
        return (msz, 0, csz)
    
    def free_space(self, end_session=True):
        msz = csz = 0
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * stats.f_bavail
            if self._card_prefix is not None:
                stats = os.statvfs(self._card_prefix)
                csz = stats.f_frsize * stats.f_bavail
        else:
            msz = self._windows_space(self._main_prefix)[1]
            csz = self._windows_space(self._card_prefix)[1]
                
        return (msz, 0, csz)

    @classmethod
    def windows_match_device(cls, device_id):
        device_id = device_id.upper()
        if 'VEN_'+cls.VENDOR_NAME in device_id and \
               'PROD_'+cls.PRODUCT_NAME in device_id:
            return True
        vid, pid = hex(cls.VENDOR_ID)[2:], hex(cls.PRODUCT_ID)[2:]        
        while len(vid) < 4: vid = '0' + vid
        while len(pid) < 4: pid = '0' + pid        
        if 'VID_'+vid in device_id and 'PID_'+pid in device_id:
            return True
        return False

    # This only supports Windows >= 2000
    def open_windows(self):
        drives = []
        wmi = __import__('wmi', globals(), locals(), [], -1) 
        c = wmi.WMI()
        for drive in c.Win32_DiskDrive():
            if self.__class__.windows_match_device(str(drive.PNPDeviceID)):
                if drive.Partitions == 0:
                    continue
                try:
                    partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
                    logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
                    prefix = logical_disk.DeviceID+os.sep
                    drives.append((drive.Index, prefix))
                except IndexError:
                    continue
                
        if not drives:
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%self.__class__.__name__)
        
        drives.sort(cmp=lambda a, b: cmp(a[0], b[0]))
        self._main_prefix = drives[0][1]
        if len(drives) > 1:
            self._card_prefix = drives[1][1]

    @classmethod
    def get_osx_mountpoints(cls, raw=None):
        if raw is None:
            ioreg = '/usr/sbin/ioreg'
            if not os.access(ioreg, os.X_OK):
                ioreg = 'ioreg'
            raw = subprocess.Popen((ioreg+' -w 0 -S -c IOMedia').split(), stdout=subprocess.PIPE).stdout.read()
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
            if line.strip().endswith('<class IOMedia>') and OSX_NAME_MAIN_MEM in line:
                get_dev_node(lines[i+1:], 'main')
            if line.strip().endswith('<class IOMedia>') and OSX_NAME_CARD_MEM in line:
                get_dev_node(lines[i+1:], 'card')
            if len(names.keys()) == 2:
                break
        return names
    
    def open_osx(self):
        mount = subprocess.Popen('mount', shell=True,  stdout=subprocess.PIPE).stdout.read()
        names = self.get_osx_mountpoints()
        dev_pat = r'/dev/%s(\w*)\s+on\s+([^\(]+)\s+'
        if 'main' not in names.keys():
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%self.__class__.__name__)
        main_pat = dev_pat%names['main']
        self._main_prefix = re.search(main_pat, mount).group(2) + os.sep
        card_pat = names['card'] if 'card' in names.keys() else None
        if card_pat is not None:
            card_pat = dev_pat%card_pat
            self._card_prefix = re.search(card_pat, mount).group(2) + os.sep
            
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
            
        self._card_prefix = None
        cards = hm.FindDeviceStringMatch(__appname__+'.cardvolume', self.__class__.__name__)
        
        for dev in cards:
            try:
                self._card_prefix = conditional_mount(dev)+os.sep
                break
            except:
                import traceback
                print traceback
                continue

    def open(self):
        time.sleep(5)
        self._main_prefix = self._card_prefix = None
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

