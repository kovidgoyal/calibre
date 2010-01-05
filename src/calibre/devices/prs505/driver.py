# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net> ' \
                '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY PRS-505
'''

import os
import re
import time
from itertools import cycle

from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.prs505.books import BookList, fix_ids
from calibre import __appname__

class PRS505(CLI, Device):

    name           = 'PRS-300/505 Device Interface'
    gui_name       = 'SONY Pocket Edition'
    description    = _('Communicate with the Sony PRS-300/505/500 eBook reader.')
    author         = 'Kovid Goyal and John Schember'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'

    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt']

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x031e]   #: Product Id for the PRS 300/505/new 500
    BCD          = [0x229, 0x1000, 0x22a]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile('PRS-(505|300|500)')
    WINDOWS_CARD_A_MEM = re.compile(r'PRS-(505|500)/\S+:MS')
    WINDOWS_CARD_B_MEM = re.compile(r'PRS-(505|500)/\S+:SD')

    OSX_MAIN_MEM   = re.compile(r'Sony PRS-(((505|300|500)/[^:]+)|(300)) Media')
    OSX_CARD_A_MEM = re.compile(r'Sony PRS-(505|500)/[^:]+:MS Media')
    OSX_CARD_B_MEM = re.compile(r'Sony PRS-(505|500)/[^:]+:SD Media')

    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'

    MEDIA_XML    = 'database/cache/media.xml'
    CACHE_XML    = 'Sony Reader/database/cache.xml'

    CARD_PATH_PREFIX          = __appname__

    SUPPORTS_SUB_DIRS = True
    MUST_READ_METADATA = True
    EBOOK_DIR_MAIN = 'database/media/books'

    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of metadata fields '
            'to turn into collections on the device.')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(['series', 'tags', 'authors'])

    def windows_filter_pnp_id(self, pnp_id):
        return '_LAUNCHER' in pnp_id

    def open(self):
        self.report_progress = lambda x, y: x
        Device.open(self)

        def write_cache(prefix):
            try:
                cachep = os.path.join(prefix, self.CACHE_XML)
                if not os.path.exists(cachep):
                    try:
                        os.makedirs(os.path.dirname(cachep), mode=0777)
                    except:
                        time.sleep(5)
                        os.makedirs(os.path.dirname(cachep), mode=0777)
                    with open(cachep, 'wb') as f:
                        f.write(u'''<?xml version="1.0" encoding="UTF-8"?>
                            <cache xmlns="http://www.kinoma.com/FskCache/1">
                            </cache>
                            '''.encode('utf8'))
                return True
            except:
                import traceback
                traceback.print_exc()
            return False

        if self._card_a_prefix is not None:
            if not write_cache(self._card_a_prefix):
                self._card_a_prefix = None
        if self._card_b_prefix is not None:
            if not write_cache(self._card_b_prefix):
                self._card_b_prefix = None

    def get_device_information(self, end_session=True):
        return (self.__class__.__name__, '', '', '')

    def books(self, oncard=None, end_session=True):
        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return []
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return []
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            self.report_progress(1.0, _('Getting list of books on device...'))
            return []

        db = self.__class__.CACHE_XML if oncard else self.__class__.MEDIA_XML
        prefix = self._card_a_prefix if oncard == 'carda' else self._card_b_prefix if oncard == 'cardb' else self._main_prefix
        bl = BookList(open(prefix + db, 'rb'), prefix, self.report_progress)
        paths = bl.purge_corrupted_files()
        for path in paths:
            path = os.path.join(prefix, path)
            if os.path.exists(path):
                os.unlink(path)
        self.report_progress(1.0, _('Getting list of books on device...'))
        return bl

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):

        path = self._sanity_check(on_card, files)

        paths, ctimes, sizes = [], [], []
        names = iter(names)
        metadata = iter(metadata)
        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            filepath = self.create_upload_path(path, mdata, fname)

            paths.append(filepath)
            self.put_file(infile, paths[-1], replace_file=True)
            ctimes.append(os.path.getctime(paths[-1]))
            sizes.append(os.stat(paths[-1]).st_size)

            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))

        return zip(paths, sizes, ctimes, cycle([on_card]))

    def add_books_to_metadata(self, locations, metadata, booklists):
        if not locations or not metadata:
            return

        metadata = iter(metadata)
        for location in locations:
            info = metadata.next()
            path = location[0]
            blist = 2 if location[3] == 'cardb' else 1 if location[3] == 'carda' else 0

            if self._main_prefix and path.startswith(self._main_prefix):
                name = path.replace(self._main_prefix, '')
            elif self._card_a_prefix and path.startswith(self._card_a_prefix):
                name = path.replace(self._card_a_prefix, '')
            elif self._card_b_prefix and path.startswith(self._card_b_prefix):
                name = path.replace(self._card_b_prefix, '')

            name = name.replace('\\', '/')
            name = name.replace('//', '/')
            if name.startswith('/'):
                name = name[1:]

            opts = self.settings()
            booklists[blist].add_book(info, name, opts.extra_customization.split(','), *location[1:-1])
        fix_ids(*booklists)

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            if os.path.exists(path):
                os.unlink(path)
                try:
                    os.removedirs(os.path.dirname(path))
                except:
                    pass
        self.report_progress(1.0, _('Removing books from device...'))

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

        self.report_progress(1.0, _('Sending metadata to device...'))


class PRS700(PRS505):

    name           = 'PRS-600/700/900 Device Interface'
    description    = _('Communicate with the Sony PRS-600/700/900 eBook reader.')
    author         = 'Kovid Goyal and John Schember'
    gui_name       = 'SONY Touch/Daily edition'
    supported_platforms = ['windows', 'osx', 'linux']

    BCD          = [0x31a]

    WINDOWS_MAIN_MEM = re.compile('PRS-((700/)|((6|9)00&))')
    WINDOWS_CARD_A_MEM = re.compile(r'PRS-((700/\S+:)|((6|9)00_))MS')
    WINDOWS_CARD_B_MEM = re.compile(r'PRS-((700/\S+:)|((6|9)00_))SD')

    OSX_MAIN_MEM   = re.compile(r'Sony PRS-((700/[^:]+)|((6|9)00)) Media')
    OSX_CARD_A_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|((6|9)00 ))MS Media')
    OSX_CARD_B_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|((6|9)00 ))SD Media')


