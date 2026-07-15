from collections.abc import Callable
from typing import Any

class WPDError(Exception):
    pass

class NoWPD(Exception):
    pass

class WPDFileBusy(Exception):
    pass

class Device:
    data: dict[str, Any]

    def __init__(self, pnp_id: str) -> None:
        'Device'
        pass

    def update_data(self) -> None:
        'update_data() -> Reread the basic device data from the device (total, space, free space, storage locations, etc.)'
        pass

    def get_filesystem(self, storage_id: str, callback: Callable[[dict[str, Any], int], bool]) -> dict[str, dict[str, Any]]:
        (
            'get_filesystem(storage_id, callback) -> Get all files/folders on the storage identified by storage_id. Tries to use bulk operations when possible.'
            ' callback must be a callable that is called as (object, level). It is called with every found object. If the callback returns False and the object'
            ' is a folder, it is not recursed into.'
        )
        pass

    def list_folder_by_name(self, parent_id: str, names: tuple[str, ...]) -> dict[str, dict[str, Any]] | None:
        (
            'list_folder_by_name(parent_id, names) -> List the folder specified by names (a tuple of name components) relative to parent_id from the device.'
            ' Return None or a list of entries.'
        )
        pass

    def get_metadata_by_name(self, parent_id: str, names: tuple[str, ...]) -> dict[str, Any] | None:
        (
            'get_metadata_by_name(parent_id, names) -> get metadata for the file or folder folder specified by names (a tuple of name components) relative to'
            ' parent_id from the device. Return None or metadata.'
        )
        pass

    def get_file(self, object_id: str, stream: Any, callback: Callable[[int, int], None] | None = None) -> None:
        (
            'get_file(object_id, stream, callback=None) -> Get the file identified by object_id from the device. The file is written to the stream object,'
            ' which must be a file like object. If callback is not None, it must be a callable that accepts two arguments: (bytes_read, total_size). It will be'
            ' called after each chunk is read from the device. Note that it can be called multiple times with the same values.'
        )
        pass

    def get_file_by_name(self, parent_id: str, names: tuple[str, ...], stream: Any, callback: Callable[[int, int], None] | None = None) -> None:
        (
            'get_file_by_name(storage_id, parent_id, names, stream, callback=None) -> Get the file specified by names (a tuple of name components) relative to'
            ' parent_id from the device. stream must be a file-like object. The file will be written to it. callback works the same as in get_filelist().'
        )
        pass

    def create_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        'create_folder(parent_id, name) -> Create a folder. Returns the folder metadata.'
        pass

    def delete_object(self, object_id: str) -> None:
        'delete_object(object_id) -> Delete the object identified by object_id. Note that trying to delete a non-empty folder will raise an error.'
        pass

    def put_file(self, parent_id: str, name: str, stream: Any, size_in_bytes: int, callback: Callable[[int, int], None] | None = None) -> dict[str, Any]:
        (
            'put_file(parent_id, name, stream, size_in_bytes, callback=None) -> Copy a file from the stream object, creating a new file on the device with'
            ' parent identified by parent_id. Returns the file metadata of the newly created file. callback should be a callable that accepts two argument:'
            ' (bytes_written, total_size). It will be called after each chunk is written to the device. Note that it can be called multiple times with the same'
            ' arguments.'
        )
        pass

def init(name: str, major_version: int, minor_version: int, revision: int) -> None:
    (
        'init(name, major_version, minor_version, revision)\n\n Initializes this module. Call this method *only* in the thread in which you intend to use this'
        ' module. Also remember to call uninit before the thread exits.'
    )
    pass

def uninit() -> None:
    (
        'uninit()\n\n Uninitialize this module. Must be called in the same thread as init(). Do not use any function/objects from this module after uninit has'
        ' been called.'
    )
    pass

def enumerate_devices() -> tuple[str, ...]:
    (
        'enumerate_devices()\n\n Get the list of device PnP ids for all connected devices recognized by the WPD service. Do not call too often as it is'
        ' resource intensive.'
    )
    pass

def device_info(pnp_id: str) -> dict[str, Any]:
    'device_info(pnp_id)\n\n Return basic device information for the device identified by pnp_id (which you get from enumerate_devices).'
    pass
