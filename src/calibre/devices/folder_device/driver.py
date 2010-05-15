'''
Created on 15 May 2010

@author: charles
'''
import os
import time

from calibre.customize.ui import available_output_formats
from calibre.devices.usbms.driver import USBMS, BookList
from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.utils.filenames import ascii_filename as sanitize, shorten_components_to

class FOLDER_DEVICE(USBMS):
    type = _('Device Interface')

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'mobi', 'lrf', 'tcr', 'pmlz', 'lit', 'rtf', 'rb', 'pdf', 'oeb', 'txt', 'pdb']

    THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device
    # Whether the metadata on books can be set via the GUI.
    CAN_SET_METADATA = True
    SUPPORTS_SUB_DIRS = True
    DELETE_EXTS = []
    #: Path separator for paths to books on device
    path_sep = os.sep
    #: Icon for this device
    icon = I('reader.svg')
    METADATA_CACHE = '.metadata.calibre'

    _main_prefix = None
    _card_a_prefix = None
    _card_b_prefix = None

    def __init__(self, path):
        self._main_prefix = path
        self.booklist_class = BookList
        self.is_connected = True

    @classmethod
    def get_gui_name(cls):
        if hasattr(cls, 'gui_name'):
            return cls.gui_name
        if hasattr(cls, '__name__'):
            return cls.__name__
        return cls.name

    def disconnect_from_folder(self):
        self.is_connected = False

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        return self.is_connected, self

    def open(self):
        if self._main_prefix is None:
            raise NotImplementedError()
        return True

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def card_prefix(self, end_session=True):
        return (None, None)

    def total_space(self, end_session=True):
       return (1024*1024*1024, 0, 0)

    def free_space(self, end_session=True):
       return (1024*1024*1024, 0, 0)

    def get_main_ebook_dir(self):
        return ''
