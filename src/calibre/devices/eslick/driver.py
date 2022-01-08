#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.devices.usbms.driver import USBMS


class ESLICK(USBMS):

    name           = 'ESlick Device Interface'
    gui_name       = 'Foxit ESlick'
    description    = _('Communicate with the ESlick e-book reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdb', 'pdf', 'txt']

    VENDOR_ID   = [0x04cc]
    PRODUCT_ID  = [0x1a64]
    BCD         = [0x0110]

    VENDOR_NAME = 'FOXIT'
    WINDOWS_MAIN_MEM = 'ESLICK_USB_DEVIC'
    WINDOWS_CARD_A_MEM = 'ESLICK_USB_DEVIC'

    # OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    # OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'ESlick Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'ESlick Storage Card'

    SUPPORTS_SUB_DIRS = True

    @classmethod
    def can_handle(cls, dev, debug=False):
        return (dev[3], dev[4]) != ('philips', 'Philips d')


class EBK52(ESLICK):

    name           = 'EBK-52 Device Interface'
    gui_name       = 'Sigmatek EBK'
    description    = _('Communicate with the Sigmatek e-book reader.')

    FORMATS     = ['epub', 'fb2', 'pdf', 'txt']

    VENDOR_NAME = ''
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'EBOOK_READER'

    MAIN_MEMORY_VOLUME_LABEL  = 'Sigmatek Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sigmatek Storage Card'

    @classmethod
    def can_handle(cls, dev, debug=False):
        return (dev[3], dev[4]) == ('philips', 'Philips d')
