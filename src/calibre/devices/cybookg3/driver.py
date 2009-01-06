__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com'

'''
Device driver for Bookeen's Cybook Gen 3
'''
import os, fnmatch, shutil, time
from itertools import cycle

from calibre.devices.interface import Device
from calibre.devices.errors import DeviceError, FreeSpaceError

from calibre.devices.cybookg3.books import BookList, EBOOK_DIR, EBOOK_TYPES
from calibre import iswindows, islinux, isosx, __appname__

class CYBOOKG3(Device):
    # Ordered list of supported formats
    FORMATS     = EBOOK_TYPES
    VENDOR_ID   = 0x0bda
    PRODUCT_ID  = 0x0703
    BCD         = 0x110
    #THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Cybook Gen 3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Cybook Gen 3 Storage Card'
    
    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                  <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.device_revision_bcd" int="%(bcd)s">
                      <match key="volume.is_partition" bool="false">
                          <merge key="volume.label" type="string">%(main_memory)s</merge>
                          <merge key="%(app)s.mainvolume" type="string">%(deviceclass)s</merge>
                      </match>
                  </match>
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                  <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.device_revision_bcd" int="%(bcd)s">
                      <match key="volume.is_partition" bool="true">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                      </match>
                  </match>
              </match>
          </match>
      </match>
  </device>
'''
    
    
    def __init__(self, key='-1', log_packets=False, report_progress=None) :
        self._main_prefix = self._card_prefix = None
    
    @classmethod
    def get_fdi(cls):
        return cls.FDI_TEMPLATE%dict(
                                     app=__appname__,
                                     deviceclass=cls.__name__,
                                     vendor_id=hex(cls.VENDOR_ID),
                                     product_id=hex(cls.PRODUCT_ID),
                                     bcd=hex(cls.BCD),
                                     main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                     storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                     )
    
    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress
    
    def get_device_information(self, end_session=True):
        """ 
        Ask device for device information. See L{DeviceInfoQuery}. 
        @return: (device name, device version, software version on device, mime type)
        """
        return (self.__class__.__name__, '', '', '')
    
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
    
    def books(self, oncard=False, end_session=True):
        if oncard and self._card_prefix is None:
            return []
        prefix = self._card_prefix if oncard else self._main_prefix
        bl = BookList(prefix)
        return bl
    
    def upload_books(self, files, names, on_card=False, end_session=True):
        if on_card and not self._card_prefix:
            raise ValueError(_('The reader has no storage card connected.'))
            
        if not on_card:
            path = os.path.join(self._main_prefix, EBOOK_DIR)
        else:
            path = os.path.join(self._card_prefix, EBOOK_DIR)
            
        sizes = map(os.path.getsize, files)
        size = sum(sizes)
    
        if on_card and size > self.free_space()[2] - 1024*1024: 
            raise FreeSpaceError("There is insufficient free space "+\
                                          "on the storage card")
        if not on_card and size > self.free_space()[0] - 2*1024*1024: 
            raise FreeSpaceError("There is insufficient free space " +\
                                         "in main memory")

        paths = []
        names = iter(names)
        
        for infile in files:
            filepath = os.path.join(path, names.next())
            paths.append(filepath)
            
            shutil.copy2(infile, filepath)
    
        return zip(paths, cycle([on_card]))
    
    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        for location in locations:
            path = location[0]
            on_card = 1 if location[1] else 0
            booklists[on_card].add_book(path, os.path.basename(path))
    
    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)
                
                filepath, ext = os.path.splitext(path)
                basepath, filename = os.path.split(filepath)
                
                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')
                
                # Delete the thumbnails file auto generated for the ebook
                for p, d, files in os.walk(basepath):
                    for filen in fnmatch.filter(files, filename + "*.t2b"):
                        os.unlink(os.path.join(p, filen))
    
    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            for bl in booklists:
                bl.remove_book(path)
        
    def sync_booklists(self, booklists, end_session=True):
        # There is no meta data on the device to update. The device is treated
        # as a mass storage device and does not use a meta data xml file like
        # the Sony Readers.
        pass
    
    def get_file(self, path, outfile, end_session=True): 
        path = self.munge_path(path)
        src = open(path, 'rb')
        shutil.copyfileobj(src, outfile, 10*1024*1024)
    
    def munge_path(self, path):
        if path.startswith('/') and not (path.startswith(self._main_prefix) or \
            (self._card_prefix and path.startswith(self._card_prefix))):
            path = self._main_prefix + path[1:]
        elif path.startswith('card:'):
            path = path.replace('card:', self._card_prefix[:-1])
        return path
        

    def _windows_match_device(self, device_id):
        device_id = device_id.upper()
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
            if self._windows_match_device(str(drive.PNPDeviceID)):
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
        
    def open_osx(self):
        raise NotImplementedError()

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

