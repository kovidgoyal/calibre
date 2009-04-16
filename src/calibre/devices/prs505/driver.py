__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Device driver for the SONY PRS-505
'''
import sys, os, shutil, time, subprocess, re
from itertools import cycle

from calibre.devices.interface import Device
from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.prs505.books import BookList, fix_ids
from calibre import iswindows, islinux, isosx, __appname__
from calibre.devices.errors import PathError

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
    VENDOR_ID    = 0x054c   #: SONY Vendor Id
    PRODUCT_ID   = 0x031e   #: Product Id for the PRS-505
    BCD          = [0x229]  #: Needed to disambiguate 505 and 700 on linux
    PRODUCT_NAME = 'PRS-505'
    VENDOR_NAME  = 'SONY'
    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt']

    MEDIA_XML    = 'database/cache/media.xml'
    CACHE_XML    = 'Sony Reader/database/cache.xml'

    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'

    OSX_NAME                  = 'Sony PRS-505'

    CARD_PATH_PREFIX          = __appname__

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
'''.replace('%(app)s', __appname__)


    def __init__(self, log_packets=False):
        self._main_prefix = self._card_prefix = None

    @classmethod
    def get_fdi(cls):
        return cls.FDI_TEMPLATE%dict(
                                     deviceclass=cls.__name__,
                                     vendor_id=hex(cls.VENDOR_ID),
                                     product_id=hex(cls.PRODUCT_ID),
                                     bcd=hex(cls.BCD[0]),
                                     main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                     storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                     )

    @classmethod
    def is_device(cls, device_id):
        device_id = device_id.upper()
        if 'VEN_'+cls.VENDOR_NAME in device_id and \
               'PROD_'+cls.PRODUCT_NAME in device_id:
            return True
        vid, pid = hex(cls.VENDOR_ID)[2:], hex(cls.PRODUCT_ID)[2:]
        if len(vid) < 4: vid = '0'+vid
        if len(pid) < 4: pid = '0'+pid
        if 'VID_'+vid in device_id and \
               'PID_'+pid in device_id:
            return True
        return False

    @classmethod
    def get_osx_mountpoints(cls, raw=None):
        if raw is None:
            ioreg = '/usr/sbin/ioreg'
            if not os.access(ioreg, os.X_OK):
                ioreg = 'ioreg'
            raw = subprocess.Popen((ioreg+' -w 0 -S -c IOMedia').split(),
                                   stdout=subprocess.PIPE).communicate()[0]
        lines = raw.splitlines()
        names = {}
        for i, line in enumerate(lines):
            if line.strip().endswith('<class IOMedia>') and cls.OSX_NAME in line:
                loc = 'stick' if ':MS' in line else 'card' if ':SD' in line else 'main'
                for line in lines[i+1:]:
                    line = line.strip()
                    if line.endswith('}'):
                        break
                    match = re.search(r'"BSD Name"\s+=\s+"(.*?)"', line)
                    if match is not None:
                        names[loc] = match.group(1)
                        break
            if len(names.keys()) == 3:
                break
        return names


    def open_osx(self):
        mount = subprocess.Popen('mount', shell=True,
                                 stdout=subprocess.PIPE).stdout.read()
        names = self.get_osx_mountpoints()
        dev_pat = r'/dev/%s(\w*)\s+on\s+([^\(]+)\s+'
        if 'main' not in names.keys():
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%self.__class__.__name__)
        main_pat = dev_pat%names['main']
        self._main_prefix = re.search(main_pat, mount).group(2) + os.sep
        card_pat = names['stick'] if 'stick' in names.keys() else names['card'] if 'card' in names.keys() else None
        if card_pat is not None:
            card_pat = dev_pat%card_pat
            self._card_prefix = re.search(card_pat, mount).group(2) + os.sep


    def open_windows(self):
        time.sleep(6)
        drives = []
        wmi = __import__('wmi', globals(), locals(), [], -1)
        c = wmi.WMI(find_classes=False)
        for drive in c.Win32_DiskDrive():
            if self.__class__.is_device(str(drive.PNPDeviceID)):
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


    def open_linux(self):
        import dbus
        bus = dbus.SystemBus()
        hm  = dbus.Interface(bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager"), "org.freedesktop.Hal.Manager")

        def conditional_mount(dev, main_mem=True):
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
        keys = []
        for card in cards:
            keys.append(int('UC_SD' in bus.get_object("org.freedesktop.Hal", card).GetPropertyString('info.parent', dbus_interface='org.freedesktop.Hal.Device')))

        cards = zip(cards, keys)
        cards.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        cards = [i[0] for i in cards]

        for dev in cards:
            try:
                self._card_prefix = conditional_mount(dev, False)+os.sep
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
        if self._card_prefix is not None:
            try:
                cachep = os.path.join(self._card_prefix, self.CACHE_XML)
                if not os.path.exists(cachep):
                    os.makedirs(os.path.dirname(cachep), mode=0777)
                    f = open(cachep, 'wb')
                    f.write(u'''<?xml version="1.0" encoding="UTF-8"?>
<cache xmlns="http://www.kinoma.com/FskCache/1">
</cache>
'''.encode('utf8'))
                    f.close()
            except:
                self._card_prefix = None
                import traceback
                traceback.print_exc()

    def set_progress_reporter(self, pr):
        self.report_progress = pr

    def get_device_information(self, end_session=True):
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

    def upload_books(self, files, names, on_card=False, end_session=True,
                     metadata=None):
        if on_card and not self._card_prefix:
            raise ValueError(_('The reader has no storage card connected.'))
        path = os.path.join(self._card_prefix, self.CARD_PATH_PREFIX) if on_card \
               else os.path.join(self._main_prefix, 'database', 'media', 'books')

        def get_size(obj):
            if hasattr(obj, 'seek'):
                obj.seek(0, 2)
                size = obj.tell()
                obj.seek(0)
                return size
            return os.path.getsize(obj)

        sizes = map(get_size, files)
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
        for infile in files:
            close = False
            if not hasattr(infile, 'read'):
                infile, close = open(infile, 'rb'), True
            infile.seek(0)
            name = names.next()
            paths.append(os.path.join(path, name))
            if not os.path.exists(os.path.dirname(paths[-1])):
                os.makedirs(os.path.dirname(paths[-1]))
            self.put_file(infile, paths[-1], replace_file=True)
            if close:
                infile.close()
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
            if os.path.exists(path):
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
        if not os.path.exists(self._main_prefix):
            os.makedirs(self._main_prefix)
        f = open(self._main_prefix + self.__class__.MEDIA_XML, 'wb')
        booklists[0].write(f)
        f.close()
        if self._card_prefix is not None and hasattr(booklists[1], 'write'):
            if not os.path.exists(self._card_prefix):
                os.makedirs(self._card_prefix)
            f = open(self._card_prefix + self.__class__.CACHE_XML, 'wb')
            booklists[1].write(f)
            f.close()




def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())
