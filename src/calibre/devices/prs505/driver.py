__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net> ' \
                '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for the SONY PRS-505
'''
import sys, os, shutil, time, subprocess, re
from itertools import cycle

from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.prs505.books import BookList, fix_ids
from calibre import iswindows, islinux, isosx, __appname__
from calibre.devices.errors import PathError

class PRS505(CLI, Device):

    name           = 'PRS-505 Device Interface'
    description    = _('Communicate with the Sony PRS-505 eBook reader.')
    author         = _('Kovid Goyal and John Schember')
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt']
    
    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x031e]   #: Product Id for the PRS-505
    BCD          = [0x229]  #: Needed to disambiguate 505 and 700 on linux

    VENDOR_NAME  = 'SONY'
    WINDOWS_MAIN_MEM = 'PRS-505'
    WINDOWS_CARD_A_MEM = 'PRS-505/UC:MS'
    WINDOWS_CARD_B_MEM = 'PRS-505/UC:SD'

    OSX_MAIN_MEM = 'Sony PRS-505/UC Media'
    OSX_CARD_A_MEM = 'Sony PRS-505/UC:MS Media'
    OSX_CARD_B_MEM = 'Sony PRS-505/UC:SD'

    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'

    MEDIA_XML    = 'database/cache/media.xml'
    CACHE_XML    = 'Sony Reader/database/cache.xml'

    CARD_PATH_PREFIX          = __appname__

    def open(self):
        Device.open(self)
        
        def write_cache(prefix):
            try:
                cachep = os.path.join(prefix, self.CACHE_XML)
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

        if self._card_a_prefix is not None:
            write_cache(self._card_a_prefix)
        if self._card_b_prefix is not None:
            write_cache(self._card_b_prefix)

    def get_device_information(self, end_session=True):
        return (self.__class__.__name__, '', '', '')

    def books(self, oncard=None, end_session=True):
        if oncard == 'carda' and not self._card_a_prefix:
            return []
        elif oncard == 'cardb' and not self._card_b_prefix:
            return []
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            return []

        db = self.__class__.CACHE_XML if oncard else self.__class__.MEDIA_XML
        prefix = self._card_a_prefix if oncard == 'carda' else self._card_b_prefix if oncard == 'cardb' else self._main_prefix
        bl = BookList(open(prefix + db, 'rb'), prefix)
        paths = bl.purge_corrupted_files()
        for path in paths:
            path = os.path.join(prefix, path)
            if os.path.exists(path):
                os.unlink(path)
        return bl

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        if on_card == 'carda' and not self._card_a_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card == 'cardb' and not self._card_b_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card and on_card not in ('carda', 'cardb'):
            raise DeviceError(_('The reader has no storage card in this slot.'))

        if on_card == 'carda':
            path = os.path.join(self._card_a_prefix, self.CARD_PATH_PREFIX)
        elif on_card == 'cardb':
            path = os.path.join(self._card_b_prefix, self.CARD_PATH_PREFIX)
        else:
            path = os.path.join(self._main_prefix, 'database', 'media', 'books')

        def get_size(obj):
            if hasattr(obj, 'seek'):
                obj.seek(0, 2)
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

        paths, ctimes = [], []

        names = iter(names)
        metadata = iter(metadata)
        for infile in files:
            close = False
            if not hasattr(infile, 'read'):
                infile, close = open(infile, 'rb'), True
            infile.seek(0)
            
            newpath = path
            mdata = metadata.next()

            if 'tags' in mdata.keys():
                for tag in mdata['tags']:
                    if tag.startswith(_('News')):
                        newpath = os.path.join(newpath, 'news')
                        newpath = os.path.join(newpath, mdata.get('title', ''))
                        newpath = os.path.join(newpath, mdata.get('timestamp', ''))
                    elif tag.startswith('/'):
                        newpath = path
                        newpath += tag
                        newpath = os.path.normpath(newpath)
                        break

            if newpath == path:
                newpath = os.path.join(newpath, mdata.get('authors', _('Unknown')))
                newpath = os.path.join(newpath, mdata.get('title', _('Unknown')))

            if not os.path.exists(newpath):
                os.makedirs(newpath)

            filepath = os.path.join(newpath, names.next())
            paths.append(filepath)

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
            blist = 2 if location[3] == 'cardb' else 1 if location[3] == 'carda' else 0
            name = path.rpartition(os.sep)[2]
            name = (cls.CARD_PATH_PREFIX+'/' if blist else 'database/media/books/') + name
            name = name.replace('//', '/')
            booklists[blist].add_book(info, name, *location[1:-1])
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
        
        def write_card_prefix(prefix, listid):
            if prefix is not None and hasattr(booklists[listid], 'write'):
                if not os.path.exists(prefix):
                    os.makedirs(prefix)
                f = open(prefix + self.__class__.CACHE_XML, 'wb')
                booklists[listid].write(f)
                f.close()
        write_card_prefix(self._card_a_prefix, 1)
        write_card_prefix(self._card_b_prefix, 2)
