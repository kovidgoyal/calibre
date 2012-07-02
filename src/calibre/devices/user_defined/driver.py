# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class USER_DEFINED(USBMS):

    name           = 'User Defined USB driver'
    gui_name       = 'User Defined USB Device'
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'pdf']

    VENDOR_ID   = 0xFFFF
    PRODUCT_ID  = 0xFFFF
    BCD         = None

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''

    VENDOR_NAME      = []
    WINDOWS_MAIN_MEM = ''
    WINDOWS_CARD_A_MEM = ''

    OSX_MAIN_MEM = 'Device Main Memory'

    MAIN_MEMORY_VOLUME_LABEL  = 'Device Main Memory'

    SUPPORTS_SUB_DIRS = True

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('USB Vendor ID (in hex)') + ':::<p>' +
            _('Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('USB Product ID (in hex)')+ ':::<p>' +
            _('Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('USB Revision ID (in hex)')+ ':::<p>' +
            _('Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        '',
        _('Windows main memory vendor string') + ':::<p>' +
            _('This field is used only on windows. '
              'Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('Windows main memory ID string') + ':::<p>' +
            _('This field is used only on windows. '
              'Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('Windows card A vendor string') + ':::<p>' +
            _('This field is used only on windows. '
              'Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('Windows card A ID string') + ':::<p>' +
            _('This field is used only on windows. '
              'Get this ID using Preferences -> Misc -> Get information to '
              'set up the user-defined device') + '</p>',
        _('Main memory folder') + ':::<p>' +
            _('Enter the folder where the books are to be stored. This folder '
              'is prepended to any send_to_device template') + '</p>',
        _('Card A folder') + ':::<p>' +
            _('Enter the folder where the books are to be stored. This folder '
              'is prepended to any send_to_device template') + '</p>',
        _('Swap main and card A') + ':::<p>' +
            _('Check this box if the device\'s main memory is being seen as '
              'card a and the card is being seen as main memory') + '</p>',
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                '0xffff',
                '0xffff',
                '0xffff',
                None,
                '',
                '',
                '',
                '',
                '',
                '',
                False,
    ]
    OPT_USB_VENDOR_ID           = 0
    OPT_USB_PRODUCT_ID          = 1
    OPT_USB_REVISION_ID         = 2
    # OPT 3 isn't used
    OPT_USB_WINDOWS_MM_VEN_ID   = 4
    OPT_USB_WINDOWS_MM_ID       = 5
    OPT_USB_WINDOWS_CA_VEN_ID   = 6
    OPT_USB_WINDOWS_CA_ID       = 7
    OPT_MAIN_MEM_FOLDER         = 8
    OPT_CARD_A_FOLDER           = 9
    OPT_SWAP_MAIN_AND_CARD      = 10

    def initialize(self):
        self.plugin_needs_delayed_initialization = True
        USBMS.initialize(self)

    def do_delayed_plugin_initialization(self):
        try:
            e = self.settings().extra_customization
            self.VENDOR_ID          = int(e[self.OPT_USB_VENDOR_ID], 16)
            self.PRODUCT_ID         = int(e[self.OPT_USB_PRODUCT_ID], 16)
            self.BCD                = [int(e[self.OPT_USB_REVISION_ID], 16)]
            if e[self.OPT_USB_WINDOWS_MM_VEN_ID]:
                self.VENDOR_NAME.append(e[self.OPT_USB_WINDOWS_MM_VEN_ID])
            if e[self.OPT_USB_WINDOWS_CA_VEN_ID] and \
                    e[self.OPT_USB_WINDOWS_CA_VEN_ID] not in self.VENDOR_NAME:
                self.VENDOR_NAME.append(e[self.OPT_USB_WINDOWS_CA_VEN_ID])
            self.WINDOWS_MAIN_MEM   = e[self.OPT_USB_WINDOWS_MM_ID] + '&'
            self.WINDOWS_CARD_A_MEM = e[self.OPT_USB_WINDOWS_CA_ID] + '&'
            self.EBOOK_DIR_MAIN     = e[self.OPT_MAIN_MEM_FOLDER]
            self.EBOOK_DIR_CARD_A   = e[self.OPT_CARD_A_FOLDER]
        except:
            import traceback
            traceback.print_exc()
        self.plugin_needs_delayed_initialization = False

    def windows_sort_drives(self, drives):

        if len(drives) < 2: return drives
        e = self.settings().extra_customization
        if not e[self.OPT_SWAP_MAIN_AND_CARD]:
            return drives
        main = drives.get('main', None)
        carda = drives.get('carda', None)
        if main and carda:
            drives['main'] = carda
            drives['carda'] = main
        return drives

    def linux_swap_drives(self, drives):
        if len(drives) < 2 or not drives[1] or not drives[2]: return drives
        e = self.settings().extra_customization
        if not e[self.OPT_SWAP_MAIN_AND_CARD]:
            return drives
        drives = list(drives)
        t = drives[0]
        drives[0] = drives[1]
        drives[1] = t
        return tuple(drives)


