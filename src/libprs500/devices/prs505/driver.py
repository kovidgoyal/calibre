##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Device driver for the SONY PRS-505
'''
import sys, os, shutil, time, subprocess, re
from itertools import cycle

from libprs500.devices.interface import Device
from libprs500.devices.errors import DeviceError, FreeSpaceError
from libprs500.devices.prs505.books import BookList, fix_ids
from libprs500 import iswindows, islinux, isosx
from libprs500.devices.libusb import get_device_by_id
from libprs500.devices.libusb import Error as USBError
from libprs500.devices.errors import PathError

class File(object):
    def __init__(self, path):
        stats = os.stat(path)
        self.is_dir = os.path.isdir(path)
        self.is_readonly = not os.access(path, os.W_OK)
        self.ctime = stats.st_ctime
        self.wtime = stats.st_mtime
        self.size  = stats.st_size 
        if path.endswith(os.sep): 
            path = path[:-1]
        self.path = path                        
        self.name = os.path.basename(path)
        

class PRS505(Device):
    VENDOR_ID    = 0x054c #: SONY Vendor Id
    PRODUCT_ID   = 0x031e #: Product Id for the PRS-505
    PRODUCT_NAME = 'PRS-505'
    VENDOR_NAME  = 'SONY'
    
    MEDIA_XML    = 'database/cache/media.xml'
    CACHE_XML    = 'Sony Reader/database/cache.xml'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'
    
    OSX_MAIN_NAME             = 'Sony PRS-505/UC Media'
    OSX_SD_NAME               = 'Sony PRS-505/UC:SD Media'
    OSX_MS_NAME               = 'Sony PRS-505/UC:MS Media'
    
    CARD_PATH_PREFIX          = 'libprs500'
    
    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                  <match key="volume.is_partition" bool="false">
                      <merge key="volume.label" type="string">%(main_memory)s</merge>
                      <merge key="libprs500.mainvolume" type="string">%(deviceclass)s</merge>
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
                      <merge key="libprs500.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
              </match>
          </match>
      </match>
  </device>
'''
    
    
    def __init__(self, log_packets=False):
        self._main_prefix = self._card_prefix = None
        
    @classmethod
    def get_fdi(cls):
        return cls.FDI_TEMPLATE%dict(
                                     deviceclass=cls.__name__,
                                     vendor_id=hex(cls.VENDOR_ID),
                                     product_id=hex(cls.PRODUCT_ID),
                                     main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                     storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                     )
    
    @classmethod
    def is_device(cls, device_id):
        if 'VEN_'+cls.VENDOR_NAME in device_id.upper() and \
               'PROD_'+cls.PRODUCT_NAME in device_id.upper():
            return True
        vid, pid = hex(cls.VENDOR_ID)[2:], hex(cls.PRODUCT_ID)[2:]
        if len(vid) < 4: vid = '0'+vid
        if len(pid) < 4: pid = '0'+pid
        if 'VID_'+vid in device_id.upper() and \
               'PID_'+pid in device_id.upper():
            return True
        return False
    
    @classmethod
    def is_connected(cls, helper=None):
        if iswindows:
            for c in helper.USBControllerDevice():
                if cls.is_device(c.Dependent.DeviceID):
                    return True
            return False
        else:
            try:
                return get_device_by_id(cls.VENDOR_ID, cls.PRODUCT_ID) != None
            except USBError:
                return False
        return False                
        
    
    def open_osx(self):
        mount = subprocess.Popen('mount', shell=True, 
                                 stdout=subprocess.PIPE).stdout.read()
        src = subprocess.Popen('ioreg -n "%s"'%(self.OSX_MAIN_NAME,), 
                               shell=True, stdout=subprocess.PIPE).stdout.read()
        try:
            devname = re.search(r'BSD Name.*=\s+"(\S+)"', src).group(1)
            self._main_prefix = re.search('/dev/%s(\w*)\s+on\s+([^\(]+)\s+'%(devname,), mount).group(2) + os.sep
        except:
            raise DeviceError('Unable to find %s. Is it connected?'%(self.__class__.__name__,))
        try:
            src = subprocess.Popen('ioreg -n "%s"'%(self.OSX_SD_NAME,), 
                               shell=True, stdout=subprocess.PIPE).stdout.read()
            devname = re.search(r'BSD Name.*=\s+"(\S+)"', src).group(1)
        except:
            try:
                src = subprocess.Popen('ioreg -n "%s"'%(self.OSX_MS_NAME,), 
                                   shell=True, stdout=subprocess.PIPE).stdout.read()
                devname = re.search(r'BSD Name.*=\s+"(\S+)"', src).group(1)
            except:
                devname = None
        if devname is not None:
            self._card_prefix = re.search('/dev/%s(\w*)\s+on\s+([^\(]+)\s+'%(devname,), mount).group(2) + os.sep
            
    
    def open_windows(self):
        drives = []
        import wmi
        c = wmi.WMI()
        for drive in c.Win32_DiskDrive():
            if self.__class__.is_device(drive.PNPDeviceID):
                if drive.Partitions == 0:
                    continue
                try:
                    partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
                except IndexError:
                    continue
                logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
                prefix = logical_disk.DeviceID+os.sep
                drives.append((drive.Index, prefix))
                
        if not drives:
            raise DeviceError('Unable to find %s. Is it connected?'%(self.__class__.__name__,))
        
        drives.sort(cmp=lambda a, b: cmp(a[0], b[0]))
        self._main_prefix = drives[0][1]
        if len(drives) > 1:
            self._card_prefix = drives[1][1]
            
    
    def open_linux(self):
        import dbus
        bus = dbus.SystemBus() 
        hm  = dbus.Interface(bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager"), "org.freedesktop.Hal.Manager")
        try:
            mm = hm.FindDeviceStringMatch('libprs500.mainvolume', self.__class__.__name__)[0]
        except:
            raise DeviceError('Unable to find %s. Is it connected?'%(self.__class__.__name__,))
        try:
            sc = hm.FindDeviceStringMatch('libprs500.cardvolume', self.__class__.__name__)[0]
        except:
            sc = None
        
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
        
        self._main_prefix = conditional_mount(mm)+os.sep
        self._card_prefix = None
        if sc is not None:
            self._card_prefix = conditional_mount(sc)+os.sep
    
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
            
    def set_progress_reporter(self, pr):
        self.report_progress = pr
        
    def get_device_information(self, end_session=True):
        return ('PRS-505', '', '', '')
    
    def card_prefix(self, end_session=True):
        return self._card_prefix
    
    @classmethod
    def _windows_space(cls, prefix):
        if prefix is None:
            return 0, 0
        import win32file
        sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                win32file.GetDiskFreeSpace(prefix[:-1])
        mult = sectors_per_cluster * bytes_per_sector
        return total_clusters * mult, free_clusters * mult
    
    def total_space(self, end_session=True):
        msz = csz = 0
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
                msz = stats.f_bsize * stats.f_bavail
            if self._card_prefix is not None:
                stats = os.statvfs(self._card_prefix)
                csz = stats.f_bsize * stats.f_bavail
        else:
            msz = self._windows_space(self._main_prefix)[1]
            csz = self._windows_space(self._card_prefix)[1]
                
        return (msz, 0, csz)
                
    def books(self, oncard=False, end_session=True):
        if oncard and self._card_prefix is None:
            return []
        db = self.__class__.CACHE_XML if oncard else self.__class__.MEDIA_XML
        prefix = self._card_prefix if oncard else self._main_prefix
        bl = BookList(open(prefix + db, 'rb'), prefix)
        paths = bl.purge_corrupted_files()
        for path in paths:
            path = os.path.join(self._card_prefix if oncard else self._main_prefix, path)
            if os.path.exists(path):
                os.unlink(path)
        return bl
    
    def munge_path(self, path):
        if path.startswith('/') and not (path.startswith(self._main_prefix) or \
            (self._card_prefix and path.startswith(self._card_prefix))):
            path = self._main_prefix + path[1:]
        elif path.startswith('card:'):
            path = path.replace('card:', self._card_prefix[:-1])
        return path
            
    def mkdir(self, path, end_session=True):
        """ Make directory """
        path = self.munge_path(path)
        os.mkdir(path)
        
    def list(self, path, recurse=False, end_session=True, munge=True):
        if munge:
            path = self.munge_path(path)
        if os.path.isfile(path):
            return [(os.path.dirname(path), [File(path)])]
        entries = [File(os.path.join(path, f)) for f in os.listdir(path)]
        dirs = [(path, entries)]
        for _file in entries:
            if recurse and _file.is_dir:
                dirs[len(dirs):] = self.list(_file.path, recurse=True, munge=False)
        return dirs
    
    def get_file(self, path, outfile, end_session=True):
        path = self.munge_path(path)
        src = open(path, 'rb')
        shutil.copyfileobj(src, outfile, 10*1024*1024)
                 
    def put_file(self, infile, path, replace_file=False, end_session=True):
        path = self.munge_path(path)
        if os.path.isdir(path):
            path = os.path.join(path, infile.name)
        if not replace_file and os.path.exists(path):
            raise PathError('File already exists: '+path)
        dest = open(path, 'wb')
        shutil.copyfileobj(infile, dest, 10*1024*1024)
        dest.flush()
        dest.close()
        
    def rm(self, path, end_session=True):
        path = self.munge_path(path)
        os.unlink(path)
        
    def touch(self, path, end_session=True):
        path = self.munge_path(path)
        if not os.path.exists(path):
            open(path, 'w').close()
        if not os.path.isdir(path):
            os.utime(path, None)
            
    def upload_books(self, files, names, on_card=False, end_session=True):
        path = os.path.join(self._card_prefix, self.CARD_PATH_PREFIX) if on_card \
               else os.path.join(self._main_prefix, 'database/media/books')
        infiles = [file if hasattr(file, 'read') else open(file, 'rb') for file in files]
        for f in infiles: f.seek(0, 2)
        sizes = [f.tell() for f in infiles]
        size = sum(sizes)
        space = self.free_space()
        mspace = space[0]
        cspace = space[2]
        if on_card and size > cspace - 1024*1024: 
            raise FreeSpaceError("There is insufficient free space "+\
                                          "on the storage card")
        if not on_card and size > mspace - 2*1024*1024: 
            raise FreeSpaceError("There is insufficient free space " +\
                                         "in main memory")
            
        paths, ctimes = [], []
        
        names = iter(names)
        for infile in infiles:
            infile.seek(0)            
            name = names.next()
            paths.append(os.path.join(path, name))
            if on_card and not os.path.exists(os.path.dirname(paths[-1])):
                os.mkdir(os.path.dirname(paths[-1]))
            self.put_file(infile, paths[-1], replace_file=True)
            ctimes.append(os.path.getctime(paths[-1]))
        return zip(paths, sizes, ctimes, cycle([on_card]))
    
    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        metadata = iter(metadata)
        for location in locations:
            info = metadata.next()
            path = location[0]
            on_card = 1 if location[3] else 0
            name = path.rpartition(os.sep)[2]
            name = (cls.CARD_PATH_PREFIX+'/' if on_card else 'database/media/books/') + name
            name = name.replace('//', '/')
            booklists[on_card].add_book(info, name, *location[1:-1])
        fix_ids(*booklists)
        
    def delete_books(self, paths, end_session=True):
        for path in paths:
            os.unlink(path)
            
    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            for bl in booklists:
                if hasattr(bl, 'remove_book'):
                    bl.remove_book(path)
        fix_ids(*booklists)
        
    def sync_booklists(self, booklists, end_session=True):
        fix_ids(*booklists)
        f = open(self._main_prefix + self.__class__.MEDIA_XML, 'wb')
        booklists[0].write(f)
        f.close()
        if self._card_prefix is not None and hasattr(booklists[1], 'write'):
            f = open(self._card_prefix + self.__class__.CACHE_XML, 'wb')
            booklists[1].write(f)
            f.close()
            
    
     

def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())