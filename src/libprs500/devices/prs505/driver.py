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
from libprs500.devices.prs500.books import BookList
import shutil
''''''

from libprs500.devices.interface import Device
from libprs500.devices.errors import DeviceError

from libprs500 import islinux, iswindows

import sys, os

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
    PRODUCT_NAME = 'Sony Portable Reader System'
    
    MEDIA_XML    = 'database/cache/media.xml'
    CACHE_XML    = 'Sony Reader/database/cache.xml'
    
    LINUX_DEVICE_NODE   = 'sony_prs_505'
    LINUX_DEVICE_PATH   = os.path.join('/dev', LINUX_DEVICE_NODE)
    
    def __init__(self):
        self._main_prefix = self._card_prefix = None
        self.hm = None
        if islinux:
            import dbus
            self.bus = dbus.SystemBus() 
            self.hm  = dbus.Interface(self.bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager"), "org.freedesktop.Hal.Manager")
    
    def is_connected(self):
        if self.hm is not None: # linux
            devs = self.hm.FindDeviceStringMatch('info.product', 'Sony Portable Reader System')
            for dev in devs:
                obj = self.bus.get_object("org.freedesktop.Hal", dev)
                if obj.GetPropertyInteger('usb_device.product_id', dbus_interface='org.freedesktop.Hal.Device') == self.__class__.PRODUCT_ID:
                    return True
        return False
    
    def open_linux(self):
        try:
            mm = self.hm.FindDeviceStringMatch('volume.label', 'Sony Reader Main Memory')[0]
        except:
            raise DeviceError('Unable to find %s. Is it connected?'%(self.__class__.__name__,))
        try:
            sc = self.hm.FindDeviceStringMatch('volume.label', 'Sony Reader Storage Card')[0]
        except:
            sc = None
        
        def conditional_mount(dev):
            mmo = self.bus.get_object("org.freedesktop.Hal", dev)
            label = mmo.GetPropertyString('volume.label', dbus_interface='org.freedesktop.Hal.Device')
            is_mounted = mmo.GetPropertyString('volume.is_mounted', dbus_interface='org.freedesktop.Hal.Device')
            mount_point = mmo.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
            fstype = mmo.GetPropertyString('volume.fstype', dbus_interface='org.freedesktop.Hal.Device')
            if is_mounted:
                return str(mount_point)
            mmo.Mount(label, fstype, ['umask=077', 'uid='+str(os.getuid())],# 'gid='+str(os.getgid())], 
                      dbus_interface='org.freedesktop.Hal.Device.Volume')
            return label+os.sep
        
        self._main_prefix = conditional_mount(mm)+os.sep
        self._card_prefix = None
        if sc is not None:
            self._card_prefix = conditional_mount(sc)+os.sep
    
    def open(self):
        if self.hm is not None: # linux
            self.open_linux()
            
    def set_progress_reporter(self, pr):
        self.report_progress = pr
        
    def get_device_information(self, end_session=True):
        return ('PRS-505', '', '', '')
    
    def card_prefix(self, end_session=True):
        return self._card_prefix
    
    def total_space(self, end_session=True):
        if not iswindows:
            msz = 0
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            csz = 0
            if self._card_prefix is not None:
                stats = os.statvfs(self._card_prefix)
                csz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
                
        return (msz, 0, csz)
    
    def free_space(self, end_session=True):
        if not iswindows:
            msz = 0
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_bsize * stats.f_bavail
            csz = 0
            if self._card_prefix is not None:
                stats = os.statvfs(self._card_prefix)
                csz = stats.f_bsize * stats.f_bavail
                
        return (msz, 0, csz)
                
    def books(self, oncard=False, end_session=True):
        db = self.__class__.CACHE_XML if oncard else self.__class__.MEDIA_XML
        prefix = self._card_prefix if oncard else self._main_prefix
        f = open(prefix + db, 'rb')
        bl = BookList(root='', sfile=f)
        paths = bl.purge_corrupted_files()
        for path in paths:
            if os.path.exists(path):
                os.unlink(path)
        return bl
    
    def munge_path(self, path):
        if path.startswith('/') and not path.startswith(self._main_prefix):
            path = self._main_prefix + path[1:]
        elif path.startswith('card:/'):
            path = path.replace('card:/', self._card_prefix)
        return path
            
    def mkdir(self, path, end_session=True):
        """ Make directory """
        path = self.munge_path(path)
        os.mkdir(path)
        
    def list(self, path, recurse=False, end_session=True):
        path = self.munge_path(path)        
        if os.path.isfile(path):
            return [(os.path.dirname(path), [File(path)])]
        entries = [File(os.path.join(path, f)) for f in os.listdir(path)]
        dirs = [(path, entries)]
        for _file in entries:
            if recurse and _file.is_dir:
                dirs[len(dirs):] = self.list(_file.path, recurse=True, end_session=False)
        return dirs
    
    def get_file(self, path, outfile, end_session=True):
        path = self.munge_path(path)
        src = open(path, 'rb')
        shutil.copyfileobj(src, outfile, 10*1024*1024)
                 
    def put_file(self, infile, path, end_session=True):
        path = self.munge_path(path)
        if os.path.isdir(path):
            path = os.path.join(path, infile.name)
        dest = open(path, 'wb')
        shutil.copyfileobj(infile, dest, 10*1024*1024)
        
    def rm(self, path, end_session=True):
        path = self.munge_path(path)
        os.unlink(path)
        
    def touch(self, path, end_session=True):
        path = self.munge_path(path)
        if not os.path.exists(path):
            open(path, 'w').close()
        if not os.path.isdir(path):
            os.utime(path, None)

def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())