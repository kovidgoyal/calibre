#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate, Protocol, Unpack

from calibre import prints
from calibre.constants import DEBUG
from calibre.devices.interface import DevicePlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    import re
    from collections.abc import Callable, Collection, Sequence
    from threading import RLock

    from calibre.devices.interface import DetectedDevice, ProgressReporter
    from calibre.prints import PrintKwargs


def debug(*args: object, **kwargs: Unpack[PrintKwargs]) -> None:
    if DEBUG:
        prints('MTP:', *args, **kwargs)


class HasLock(Protocol):
    @property
    def lock(self) -> RLock: ...


def synchronous[S: HasLock, **P, R](func: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R]:
    @wraps(func)
    def synchronizer(self: S, *args: P.args, **kwargs: P.kwargs) -> R:
        with self.lock:
            return func(self, *args, **kwargs)

    return synchronizer


class MTPDeviceBase(DevicePlugin):
    name = 'MTP Device Interface'
    gui_name = _('MTP device')
    icon = 'devices/tablet.png'
    description = _('Communicate with MTP devices')
    author = 'Kovid Goyal'
    version = (1, 0, 0)

    if TYPE_CHECKING:

        @property
        def prefs(self) -> dict[str, Any]: ...

    def __init__(self, *args: str | None, **kwargs: str | None) -> None:
        DevicePlugin.__init__(self, *args, **kwargs)
        self.progress_reporter = None
        self.current_friendly_name: str | None = None
        self.report_progress: ProgressReporter = lambda x, y: None
        self.current_serial_num: str | None = None

    def reset(
        self,
        key: str = '-1',
        log_packets: bool = False,
        report_progress: ProgressReporter | None = None,
        detected_device: DetectedDevice | None = None,
    ) -> None:
        pass

    def set_progress_reporter(self, report_progress: ProgressReporter) -> None:
        self.report_progress = report_progress

    def get_gui_name(self) -> str:
        return self.current_friendly_name or self.gui_name

    def is_usb_connected(
        self, devices_on_system: Collection[DetectedDevice], debug: bool = False, only_presence: bool = False
    ) -> tuple[bool, DetectedDevice | None]:
        # We manage device presence ourselves, so this method should always
        # return False
        return False, None

    @property
    def save_template(self) -> str:
        raise NotImplementedError

    def filesystem_callback(self, msg: str) -> None:
        pass

    def is_folder_ignored(self, storage_or_storage_id: object, path: Sequence[str]) -> bool:
        return False

    def build_template_regexp(self) -> re.Pattern[str]:
        from calibre.devices.utils import build_template_regexp

        return build_template_regexp(self.save_template)

    def is_customizable(self) -> bool:
        return True
