"""
Created on 15 May 2010

@author: charles
"""

import os
from contextlib import suppress
from typing import TYPE_CHECKING

from calibre.devices.usbms.driver import USBMS, BookList
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Collection

    from qt.core import QWidget

    from calibre.devices.interface import DetectedDevice, ProgressReporter
    from calibre.utils.config_base import Config, OptionValues

# This class is added to the standard device plugin chain, so that it can
# be configured. It has invalid vendor_id etc, so it will never match a
# device. The 'real' FOLDER_DEVICE will use the config from it.


class FOLDER_DEVICE_FOR_CONFIG(USBMS):
    name = 'Folder Device Interface'
    gui_name = 'Folder Device'
    description = _('Use an arbitrary folder as a device.')
    author = 'John Schember/Charles Haley'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = list(BOOK_EXTENSIONS) + ['ppt', 'pptx']

    VENDOR_ID = [0xFFFF]
    PRODUCT_ID = [0xFFFF]
    BCD = [0xFFFF]
    DEVICE_PLUGBOARD_NAME = 'FOLDER_DEVICE'
    SUPPORTS_SUB_DIRS = True


class FOLDER_DEVICE(USBMS):
    type = _('Device interface')

    name = 'Folder Device Interface'
    gui_name = 'Folder Device'
    description = _('Use an arbitrary folder as a device.')
    author = 'John Schember/Charles Haley'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = FOLDER_DEVICE_FOR_CONFIG.FORMATS

    VENDOR_ID = [0xFFFF]
    PRODUCT_ID = [0xFFFF]
    BCD = [0xFFFF]
    DEVICE_PLUGBOARD_NAME = 'FOLDER_DEVICE'

    THUMBNAIL_HEIGHT = 68  # Height for thumbnails on device

    CAN_SET_METADATA = ['title', 'authors']
    SUPPORTS_SUB_DIRS = True

    #: Icon for this device
    icon = 'devices/folder.png'
    METADATA_CACHE = '.metadata.calibre'
    DRIVEINFO = '.driveinfo.calibre'

    _main_prefix = ''
    _card_a_prefix = None
    _card_b_prefix = None

    is_connected = False

    def __init__(self, path: str) -> None:
        if not os.path.isdir(path):
            raise OSError('Path is not a folder')
        path = USBMS.normalize_path(path)
        if path.endswith(os.sep):
            self._main_prefix = path
        else:
            self._main_prefix = path + os.sep
        self.booklist_class = BookList
        self.is_connected = True

    def is_folder_still_available(self) -> bool:
        with suppress(OSError):
            if self._main_prefix:
                return os.path.isdir(self._main_prefix)
        return False

    def reset(
        self,
        key: str = '-1',
        log_packets: bool = False,
        report_progress: ProgressReporter | None = None,
        detected_device: DetectedDevice | None = None,
    ) -> None:
        pass

    def unmount_device(self) -> None:
        self._main_prefix = ''
        self.is_connected = False

    # Returns itself rather than a detected USB device, the return value is
    # ignored by the device manager for folder devices
    def is_usb_connected(  # ty: ignore[invalid-method-override]
        self, devices_on_system: Collection[DetectedDevice], debug: bool = False, only_presence: bool = False
    ) -> tuple[bool, FOLDER_DEVICE]:
        return self.is_connected, self

    def open(self, connected_device: object, library_uuid: str | None) -> None:
        self.current_library_uuid = library_uuid

    def set_progress_reporter(self, report_progress: ProgressReporter | None) -> None:
        self.report_progress = report_progress or (lambda x, y: x)

    def card_prefix(self, end_session: bool = True) -> tuple[str | None, str | None]:
        return None, None

    def eject(self) -> None:
        self.is_connected = False

    @classmethod
    def _config(cls) -> Config:
        return FOLDER_DEVICE_FOR_CONFIG._config()

    @classmethod
    def settings(cls) -> OptionValues:
        return FOLDER_DEVICE_FOR_CONFIG._config().parse()

    def config_widget(self) -> QWidget:
        return FOLDER_DEVICE_FOR_CONFIG.config_widget(self)

    def save_settings(self, config_widget: QWidget) -> None:
        FOLDER_DEVICE_FOR_CONFIG.save_settings(self, config_widget)
