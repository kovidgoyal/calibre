# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Barns and Nobel's Nook
'''

import io, os, errno

from calibre import fsync, prints
from calibre.constants import DEBUG
from calibre.devices.usbms.driver import USBMS


class NOOK(USBMS):

    name           = 'Nook Device Interface'
    gui_name       = _('The Nook')
    description    = _('Communicate with the Nook e-book reader.')
    author         = 'John Schember'
    icon           = I('devices/nook.png')
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdb', 'pdf']

    VENDOR_ID   = [0x2080, 0x18d1]  # 0x18d1 is for softrooted nook
    PRODUCT_ID  = [0x001]
    BCD         = [0x322]

    VENDOR_NAME = 'B&N'
    WINDOWS_MAIN_MEM = 'NOOK'
    WINDOWS_CARD_A_MEM = 'NOOK'

    OSX_MAIN_MEM = 'B&N nook Media'
    OSX_CARD_A_MEM = OSX_MAIN_MEM

    MAIN_MEMORY_VOLUME_LABEL  = 'Nook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Nook Storage Card'

    EBOOK_DIR_MAIN = 'my documents'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.jpg']
    SUPPORTS_SUB_DIRS = True

    def upload_cover(self, path, filename, metadata, filepath):
        from PIL import Image, ImageDraw

        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            cover = Image.open(io.BytesIO(coverdata[2]))
        else:
            coverdata = lopen(I('library.png'), 'rb').read()

            cover = Image.new('RGB', (96, 144), 'black')
            im = Image.open(io.BytesIO(coverdata))
            im.thumbnail((96, 144), Image.ANTIALIAS)

            x, y = im.size
            cover.paste(im, ((96-x)/2, (144-y)/2))

            draw = ImageDraw.Draw(cover)
            draw.text((1, 15), metadata.get('title', _('Unknown')).encode('ascii', 'ignore'))
            draw.text((1, 115), metadata.get('authors', _('Unknown')).encode('ascii', 'ignore'))

        data = io.BytesIO()
        cover.save(data, 'JPEG')
        coverdata = data.getvalue()

        with lopen('%s.jpg' % os.path.join(path, filename), 'wb') as coverfile:
            coverfile.write(coverdata)
            fsync(coverfile)

    def sanitize_path_components(self, components):
        return [x.replace('#', '_').replace('%', '_') for x in components]


class NOOK_COLOR(NOOK):
    name           = 'Nook Color Device Interface'
    description    = _('Communicate with the Nook Color, TSR, Glowlight and Tablet e-book readers.')

    PRODUCT_ID  = [
        0x002, 0x003, 0x004,
        0x005,  # Nook HD+
        0x007,  # Glowlight from 2013
        0xb,    # Glowlight from 2017
        0xc,    # Glowlight from 2019
    ]
    BCD         = [0x216, 0x9999]

    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['EBOOK_DISK', 'NOOK_TABLET',
            'NOOK_SIMPLETOUCH', 'NOOK_GLOWLIGHT']
    EBOOK_DIR_MAIN = 'My Files'
    SCAN_FROM_ROOT = True
    NEWS_IN_FOLDER = False

    def upload_cover(self, path, filename, metadata, filepath):
        pass

    def post_open_callback(self):
        product_id = self.device_being_opened[1]
        if DEBUG:
            prints('Opened NOOK with product id:', product_id)
        if product_id in (0xb, 0xc):
            if DEBUG:
                prints('Setting Nook upload directory to NOOK/My Files')
            self.EBOOK_DIR_MAIN = 'NOOK/My Files'
            try:
                os.makedirs(os.path.join(self._main_prefix, *self.EBOOK_DIR_MAIN.split('/')))
            except EnvironmentError as err:
                if err.errno != errno.EEXIST:
                    self.EBOOK_DIR_MAIN = 'NOOK'

    def get_carda_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return ''

    def create_upload_path(self, path, mdata, fname, create_dirs=True):
        is_news = mdata.tags and _('News') in mdata.tags
        subdir = 'Magazines' if is_news else 'Books'
        path = os.path.join(path, subdir)
        return USBMS.create_upload_path(self, path, mdata, fname,
                create_dirs=create_dirs)
