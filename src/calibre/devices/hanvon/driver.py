# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Hanvon devices
'''
import re, os

from calibre.devices.usbms.driver import USBMS

def is_alex(device_info):
    return device_info[3] == u'Linux 2.6.28 with pxa3xx_u2d' and \
            device_info[4] == u'Seleucia Disk'

class N516(USBMS):

    name           = 'N516 driver'
    gui_name       = 'N516'
    description    = _('Communicate with the Hanvon N520 eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'prc', 'mobi', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x323, 0x326, 0x327]

    VENDOR_NAME      = 'INGENIC'
    WINDOWS_MAIN_MEM = '_FILE-STOR_GADGE'

    MAIN_MEMORY_VOLUME_LABEL  = 'N520 Internal Memory'

    EBOOK_DIR_MAIN = 'e_book'
    SUPPORTS_SUB_DIRS = True

    def can_handle(self, device_info, debug=False):
        return not is_alex(device_info)

class KIBANO(N516):

    name = 'Kibano driver'
    gui_name = 'Kibano'
    description    = _('Communicate with the Kibano eBook reader.')
    FORMATS     = ['epub', 'pdf', 'txt']
    BCD         = [0x323]

    VENDOR_NAME      = 'EBOOK'
    # We use EXTERNAL_SD_CARD for main mem as some devices have not working
    # main memories
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['INTERNAL_SD_CARD',
                                             'EXTERNAL_SD_CARD']

class THEBOOK(N516):
    name = 'The Book driver'
    gui_name = 'The Book'
    description    = _('Communicate with The Book reader.')
    author         = 'Kovid Goyal'

    BCD = [0x399]
    MAIN_MEMORY_VOLUME_LABEL  = 'The Book Main Memory'
    EBOOK_DIR_MAIN = 'My books'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['_FILE-STOR_GADGE',
            'FILE-STOR_GADGET']

class LIBREAIR(N516):
    name = 'Libre Air Driver'
    gui_name = 'Libre Air'
    description    = _('Communicate with the Libre Air reader.')
    author         = 'Kovid Goyal'
    FORMATS = ['epub', 'mobi', 'prc', 'fb2', 'rtf', 'txt', 'pdf']

    BCD = [0x399]
    VENDOR_NAME      = ['ALURATEK', 'LINUX']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'
    EBOOK_DIR_MAIN = 'Books'

class ALEX(N516):

    name = 'Alex driver'
    gui_name = 'SpringDesign Alex'
    description    = _('Communicate with the SpringDesign Alex eBook reader.')
    author         = 'Kovid Goyal'

    FORMATS     = ['epub', 'fb2', 'pdf']
    VENDOR_NAME      = 'ALEX'
    WINDOWS_MAIN_MEM = 'READER'

    MAIN_MEMORY_VOLUME_LABEL  = 'Alex Internal Memory'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = False
    THUMBNAIL_HEIGHT = 120

    def can_handle(self, device_info, debug=False):
        return is_alex(device_info)

    def alex_cpath(self, file_abspath):
        base = os.path.dirname(file_abspath)
        name = os.path.splitext(os.path.basename(file_abspath))[0] + '.png'
        return os.path.join(base, 'covers', name)

    def upload_cover(self, path, filename, metadata, filepath):
        from calibre.ebooks import calibre_cover
        from calibre.utils.magick.draw import thumbnail
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            cover = coverdata[2]
        else:
            cover = calibre_cover(metadata.get('title', _('Unknown')),
                    metadata.get('authors', _('Unknown')))

        cover = thumbnail(cover, width=self.THUMBNAIL_HEIGHT,
                height=self.THUMBNAIL_HEIGHT, fmt='png')[-1]

        cpath = self.alex_cpath(os.path.join(path, filename))
        cdir = os.path.dirname(cpath)
        if not os.path.exists(cdir):
            os.makedirs(cdir)
        with open(cpath, 'wb') as coverfile:
            coverfile.write(cover)

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)
            try:
                cpath = self.alex_cpath(path)
                if os.path.exists(cpath):
                    os.remove(cpath)
            except:
                pass
        self.report_progress(1.0, _('Removing books from device...'))

class AZBOOKA(ALEX):

    name = 'Azbooka driver'
    gui_name = 'Azbooka'
    description = _('Communicate with the Azbooka')

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'

    MAIN_MEMORY_VOLUME_LABEL  = 'Azbooka Internal Memory'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

    def can_handle(self, device_info, debug=False):
        return not is_alex(device_info)

    def upload_cover(self, path, filename, metadata, filepath):
        pass

class EB511(USBMS):
    name           = 'Elonex EB 511 driver'
    gui_name       = 'EB 511'
    description    = _('Communicate with the Elonex EB 511 eBook reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS     = ['epub', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x45e]
    PRODUCT_ID  = [0xffff]
    BCD         = [0x0]

    MAIN_MEMORY_VOLUME_LABEL  = 'EB 511 Internal Memory'

    EBOOK_DIR_MAIN = 'e_book'
    SUPPORTS_SUB_DIRS = True

    OSX_MAIN_MEM_VOL_PAT = re.compile(r'/eReader')

class ODYSSEY(N516):
    name  = 'Cybook Odyssey driver'
    gui_name       = 'Odyssey'
    description    = _('Communicate with the Cybook Odyssey eBook reader.')

    BCD = [0x316]
    VENDOR_NAME      = ['LINUX', 'BOOKEEN']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['FILE-STOR_GADGET', 'FLASH_DISK']

    FORMATS     = ['epub', 'fb2', 'html', 'pdf', 'txt']

    EBOOK_DIR_MAIN = 'Digital Editions'

    def get_main_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return ''

