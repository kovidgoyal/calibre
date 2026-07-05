from collections.abc import Callable

class MTPError(Exception):
    pass

class Device:

    def __init__(self, busnum: int, devnum: int, vendor_id: int, product_id: int, vendor: str, product: str, usb_serialnum: str | None) -> None:
        'Device'
        pass

    def update_storage_info(self) -> None:
        'update_storage_info() -> Reread the storage info from the device (total, space, free space, storage locations, etc.)'
        pass

    def get_filesystem(self, storage_id: int, callback: Callable[[dict[str, int | str | bool], int], object]) -> tuple[list[dict[str, int | str | bool]], list[tuple[int, str]]]:
        'get_filesystem(storage_id, callback) -> Get the list of files and folders on the device in storage_id. Returns files, errors. callback must be a callable that is called as with (entry, level). It is called with every found object. If callback returns False and the object is a folder, it is not recursed into.'
        pass

    def get_file(self, fileid: int, stream: object, callback: Callable[[int, int], object] | None = None) -> tuple[bool, list[tuple[int, str]]]:
        'get_file(fileid, stream, callback=None) -> Get the file specified by fileid from the device. stream must be a file-like object. The file will be written to it. callback works the same as in get_filelist(). Returns ok, errs, where errs is a list of errors (if any).'
        pass

    def get_file_by_name(self, storage_id: int, parent_id: int, names: tuple[str, ...], stream: object, callback: Callable[[int, int], object] | None = None) -> tuple[bool, list[tuple[int, str]]] | None:
        'get_file_by_name(storage_id, parent_id, names, stream, callback=None) -> Get the file specified by names (a tuple of name components) relative to parent_id from the device. stream must be a file-like object. The file will be written to it. callback works the same as in get_filelist(). Returns None or (ok, errs), where errs is a list of errors (if any).'
        pass

    def list_folder_by_name(self, storage_id: int, parent_id: int, names: tuple[str, ...]) -> list[dict[str, int | str | bool]] | None:
        'list_folder_by_name(storage_id, parent_id, names) -> List the folder specified by names (a tuple of name components) relative to parent_id from the device. Return None or a list of entries.'
        pass

    def get_metadata_by_name(self, storage_id: int, parent_id: int, names: tuple[str, ...]) -> tuple[dict[str, int | str | bool] | None, list[tuple[int, str]]] | None:
        'get_metadata_by_name(storage_id, parent_id, names) -> Return metadata for specified name (a tuple of name components) relative to parent from the device. Return (metadata, errs).'
        pass

    def put_file(self, storage_id: int, parent_id: int, filename: str, stream: object, size: int, callback: Callable[[int, int], object] | None = None) -> tuple[dict[str, int | str | bool] | None, list[tuple[int, str]]]:
        'put_file(storage_id, parent_id, filename, stream, size, callback=None) -> Put a file on the device. The file is read from stream. It is put inside the folder identified by parent_id on the storage identified by storage_id. Use parent_id=0 to put it in the root. stream must be a file-like object. size is the size in bytes of the data in stream. callback works the same as in get_filelist(). Returns fileinfo, errs, where errs is a list of errors (if any), and fileinfo is a file information dictionary, as returned by get_filelist(). fileinfo will be None if case or errors.'
        pass

    def create_folder(self, storage_id: int, parent_id: int, name: str) -> tuple[dict[str, int | str | bool] | None, list[tuple[int, str]]]:
        'create_folder(storage_id, parent_id, name) -> Create a folder named name under parent parent_id (use 0 for root) in the storage identified by storage_id. Returns folderinfo, errors, where folderinfo is the same dict as returned by get_folderlist(), it will be None if there are errors.'
        pass

    def delete_object(self, id: int) -> tuple[bool, list[tuple[int, str]]]:
        'delete_object(id) -> Delete the object identified by id from the device. Can be used to delete files, folders, etc. Returns ok, errs.'
        pass

    @property
    def friendly_name(self) -> str | None:
        'The friendly name of this device, can be None.'
        pass

    @property
    def manufacturer_name(self) -> str | None:
        'The manufacturer name of this device, can be None.'
        pass

    @property
    def model_name(self) -> str | None:
        'The model name of this device, can be None.'
        pass

    @property
    def serial_number(self) -> str | None:
        'The serial number of this device, can be None.'
        pass

    @property
    def device_version(self) -> str | None:
        'The device version of this device, can be None.'
        pass

    @property
    def ids(self) -> tuple[int, int, int, int, str | None]:
        'The ids of the device (busnum, devnum, vendor_id, product_id, usb_serialnum)'
        pass

    @property
    def storage_info(self) -> list[dict[str, int | str | bool]]:
        'Information about the storage locations on the device. Returns a list of dictionaries where each dictionary corresponds to the LIBMTP_devicestorage_struct.'
        pass

LIBMTP_VERSION_STRING: str
LIBMTP_DEBUG_NONE: int
LIBMTP_DEBUG_PTP: int
LIBMTP_DEBUG_PLST: int
LIBMTP_DEBUG_USB: int
LIBMTP_DEBUG_DATA: int
LIBMTP_DEBUG_ALL: int
LIBMTP_FILES_AND_FOLDERS_ROOT: int

def set_debug_level(level: int) -> None:
    'set_debug_level(level)\n\nSet the debug level bit mask, see LIBMTP_DEBUG_* constants.'
    pass

def is_mtp_device(busnum: int, devnum: int) -> bool:
    'is_mtp_device(busnum, devnum)\n\nA probe is done and True returned if the probe succeeds. Note that probing can cause some devices to malfunction, and it is not very reliable, which is why we prefer to use the device database.'
    pass

def known_devices() -> list[tuple[int, int]]:
    'known_devices() -> Return the list of known (vendor_id, product_id) combinations.'
    pass
