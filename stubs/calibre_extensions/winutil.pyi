from typing import Any

class Handle:
    def __init__(self, handle: int | None = None, handle_type: int = 0, associated_name: str | None = None) -> None:
        'Wrappers for Win32 handles that free the handle on delete automatically'
        pass

    def close(self) -> None:
        'Close the underlying Win32 handle now, instead of when this object is deleted'
        pass

    def detach(self) -> int:
        'Return the underlying handle as an integer and stop owning it, it will no longer be closed automatically'
        pass

    def __int__(self) -> int:
        'Return the underlying handle as an integer'
        pass

    def __bool__(self) -> bool:
        'Return False if the underlying handle is NULL'
        pass

    def __repr__(self) -> str:
        'Return a representation of this handle, including its type and associated name'
        pass

class GUID:
    def __init__(self, guid_string: str) -> None:
        'Wrapper for Win32 GUID'
        pass

    def __repr__(self) -> str:
        'Return the string form of this GUID, as returned by StringFromIID()'
        pass

def run_cmdline(cmdline: str, flags: int, wait_for: int = 0) -> None:
    'Run the specified command line using CreateProcess(), optionally waiting for it to become idle'
    pass

def is_wow64_process() -> bool:
    'Return True if the current process is a 32-bit process running on 64-bit Windows'
    pass

def get_dll_directory() -> str:
    'Wrapper for GetDllDirectory'
    pass

def create_mutex(name: str | None, allow_existing: bool = True, initial_owner: bool = False) -> Handle:
    'Wrapper for CreateMutex, raises FileExistsError if allow_existing is False and the mutex already exists'
    pass

def supports_hardlinks(path: str) -> bool:
    'Return True if the volume containing path supports hard links'
    pass

def filesystem_type_name(path: str) -> str:
    'Return the name of the filesystem (e.g. NTFS) for the volume containing path'
    pass

def get_async_key_state(key: int) -> int:
    'Wrapper for GetAsyncKeyState'
    pass

def create_named_pipe(
    name: str, open_mode: int, pipe_mode: int, max_instances: int, out_buffer_size: int, in_buffer_size: int, default_time_out: int
) -> Handle:
    'Wrapper for CreateNamedPipe'
    pass

def connect_named_pipe(handle: Handle) -> None:
    'Wrapper for ConnectNamedPipe'
    pass

def set_handle_information(handle: Handle, mask: int, flags: int) -> None:
    'Wrapper for SetHandleInformation'
    pass

def set_pipe_blocking(handle: Handle, blocking: bool = False) -> None:
    'Set the specified pipe handle to blocking or non-blocking mode'
    pass

def wait_for_single_object(handle: Handle, timeout_ms: int = -1) -> int:
    'Wrapper for WaitForSingleObject, timeout_ms < 0 means wait forever, raises TimeoutError if the wait times out'
    pass

def wait_for_multiple_objects(handles: list[Handle] | tuple[Handle, ...], wait_all: bool = False, timeout_ms: int = -1) -> int:
    'Wrapper for WaitForMultipleObjects, timeout_ms < 0 means wait forever, raises TimeoutError if the wait times out'
    pass

def get_long_path_name(path: str) -> str:
    'Wrapper for GetLongPathName'
    pass

def get_process_times(pid: int | None) -> tuple[int, int, int, int]:
    'Returns (creation, exit, kernel, user) times as 64-bit integers, for the process with the specified pid, or the current process if pid is None'
    pass

def get_handle_information(handle: Handle) -> int:
    'Wrapper for GetHandleInformation'
    pass

def get_last_error() -> int:
    'Wrapper for GetLastError'
    pass

def load_library(path: str, flags: int = 0) -> Handle:
    'Wrapper for LoadLibraryEx'
    pass

def load_icons(handle: Handle, index: int) -> list[tuple[bytes, Handle]]:
    'Load the icons in the icon group resource at the specified index (or resource id if index is negative) from the specified module handle'
    pass

def get_icon_for_file(path: str, width: int = 256, height: int = 256) -> Handle:
    'Get an icon of the specified size for the specified file, uses IShellItemImageFactory'
    pass

def parse_cmdline(cmdline: str) -> tuple[str, ...]:
    'Parse the specified command line into arguments using CommandLineToArgvW'
    pass

def write_file(handle: Handle, data: bytes, offset: int = 0) -> int:
    'Wrapper for WriteFile, returns the number of bytes written'
    pass

def wait_named_pipe(path: str, timeout: int = 0) -> bool:
    'Wrapper for WaitNamedPipe'
    pass

def set_thread_execution_state(new_state: int) -> None:
    'Wrapper for SetThreadExecutionState'
    pass

def known_folder_path(id: GUID, flags: int = 0) -> str:
    'Wrapper for SHGetKnownFolderPath, id should be one of the FOLDERID_* constants defined in this module'
    pass

def get_computer_name(fmt: int = 3) -> str:
    'Wrapper for GetComputerNameEx, fmt should be one of the ComputerName* constants defined in this module (default ComputerNameDnsFullyQualified)'
    pass

def special_folder_path(csidl_id: int, flags: int = 0) -> str:
    (
        'special_folder_path(csidl_id) -> path\n\nGet paths to common system folders. See windows documentation of SHGetFolderPath. The paths are returned as'
        ' unicode objects. csidl_id should be one of the symbolic constants defined in this module. You can also OR a symbolic constant with CSIDL_FLAG_CREATE'
        ' to force the operating system to create a folder if it does not exist.'
    )
    pass

def internet_connected() -> bool:
    'internet_connected()\n\nReturn True if there is an active internet connection'
    pass

def prepare_for_restart() -> None:
    'prepare_for_restart()\n\nRedirect output streams so that the child process does not lock the temp files'
    pass

def getmaxstdio() -> int:
    'getmaxstdio()\n\nThe maximum number of open file handles.'
    pass

def setmaxstdio(num: int) -> None:
    'setmaxstdio(num)\n\nSet the maximum number of open file handles.'
    pass

def username() -> str:
    'username()\n\nGet the current username as a unicode string.'
    pass

def temp_path() -> str:
    'temp_path()\n\nGet the current temporary dir as a unicode string.'
    pass

def locale_name() -> str:
    'locale_name()\n\nGet the current locale name as a unicode string.'
    pass

def localeconv() -> dict[str, str]:
    'localeconv()\n\nGet the locale conventions as unicode strings.'
    pass

def move_file(a: str, b: str, flags: int = 9) -> None:
    'move_file(a, b, flags)\n\nWrapper for MoveFileEx'
    pass

def add_to_recent_docs(path: str, app_id: str | None = None) -> None:
    'add_to_recent_docs()\n\nAdd a path to the recent documents list'
    pass

def file_association(ext: str | None) -> str | None:
    'file_association()\n\nGet the executable associated with the given file extension'
    pass

def friendly_name(prog_id: str | None, exe: str | None) -> str | None:
    'friendly_name()\n\nGet the friendly name for the specified prog_id/exe'
    pass

def notify_associations_changed() -> None:
    'notify_associations_changed()\n\nNotify the OS that file associations have changed'
    pass

def move_to_trash(path: str) -> None:
    'move_to_trash()\n\nMove the specified path to trash'
    pass

def manage_shortcut(path: str, target: str | None, description: str | None, quoted_args: str | None) -> str | None:
    'manage_shortcut()\n\nManage a shortcut'
    pass

def resolve_lnk(path: str, timeout: int = 0, win_id: int | None = None) -> str:
    'resolve_lnk()\n\nGet the target of a lnk file.'
    pass

def get_file_id(path: str | None) -> tuple[int, int, int] | None:
    'get_file_id(path)\n\nGet the windows file id (volume_num, file_index_high, file_index_low)'
    pass

def create_file(path: str, desired_access: int, share_mode: int, creation_disposition: int, flags_and_attributes: int) -> Handle:
    'create_file(path, desired_access, share_mode, creation_disposition, flags_and_attributes)\n\nWrapper for CreateFile'
    pass

def get_file_size(handle: Handle) -> int:
    'get_file_size(handle)\n\nWrapper for GetFileSizeEx'
    pass

def set_file_pointer(handle: Handle, pos: int, method: int = 0) -> int:
    'set_file_pointer(handle, pos, method=FILE_BEGIN)\n\nWrapper for SetFilePointer'
    pass

def set_file_handle_delete_on_close(handle: Handle, delete_on_close: bool) -> None:
    (
        'set_file_handle_delete_on_close(handle, delete_on_close)\n\nSet the delete on close flag on the specified handle. Note only works if CreateFile() is'
        ' called with DELETE generic access, and without FILE_FLAG_DELETE_ON_CLOSE.'
    )
    pass

def read_file(handle: Handle, chunk_size: int = 16384) -> bytes:
    'read_file(handle, chunk_size=16KB)\n\nWrapper for ReadFile'
    pass

def get_disk_free_space(path: str | None) -> tuple[int, int, int]:
    'get_disk_free_space(path)\n\nWrapper for GetDiskFreeSpaceEx'
    pass

def delete_file(path: str) -> None:
    'delete_file(path)\n\nWrapper for DeleteFile'
    pass

def create_hard_link(path: str, existing_path: str) -> None:
    'create_hard_link(path, existing_path)\n\nWrapper for CreateHardLink'
    pass

def nlinks(path: str) -> int:
    'nlinks(path)\n\nReturn the number of hardlinks'
    pass

def set_file_attributes(path: str, attrs: int = 128) -> None:
    'set_file_attributes(path, attrs)\n\nWrapper for SetFileAttributes'
    pass

def read_directory_changes(handle: Handle, buffer: bytes, subtree: bool, flags: int) -> list[tuple[int, str]]:
    'read_directory_changes(handle, buffer, subtree, flags)\n\nWrapper for ReadDirectoryChangesW'
    pass

def get_processes_using_files(*paths: str) -> list[dict[str, Any]]:
    'get_processes_using_files(path1, path2, ...)\n\nGet information about processes that have the specified files open.'
    pass

NormalHandle: int
ModuleHandle: int
IconHandle: int
BitmapHandle: int

CSIDL_ADMINTOOLS: int
CSIDL_APPDATA: int
CSIDL_COMMON_ADMINTOOLS: int
CSIDL_COMMON_APPDATA: int
CSIDL_COMMON_DOCUMENTS: int
CSIDL_COOKIES: int
CSIDL_FLAG_CREATE: int
CSIDL_FLAG_DONT_VERIFY: int
CSIDL_FONTS: int
CSIDL_HISTORY: int
CSIDL_INTERNET_CACHE: int
CSIDL_LOCAL_APPDATA: int
CSIDL_MYPICTURES: int
CSIDL_PERSONAL: int
CSIDL_PROGRAM_FILES: int
CSIDL_PROGRAM_FILES_COMMON: int
CSIDL_SYSTEM: int
CSIDL_WINDOWS: int
CSIDL_PROFILE: int
CSIDL_STARTUP: int
CSIDL_COMMON_STARTUP: int

CREATE_NEW: int
CREATE_ALWAYS: int
OPEN_EXISTING: int
OPEN_ALWAYS: int
TRUNCATE_EXISTING: int

FILE_SHARE_READ: int
FILE_SHARE_WRITE: int
FILE_SHARE_DELETE: int
FILE_SHARE_VALID_FLAGS: int

FILE_ATTRIBUTE_READONLY: int
FILE_ATTRIBUTE_NORMAL: int
FILE_ATTRIBUTE_HIDDEN: int
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED: int
FILE_ATTRIBUTE_OFFLINE: int
FILE_ATTRIBUTE_SYSTEM: int
FILE_ATTRIBUTE_TEMPORARY: int

FILE_FLAG_DELETE_ON_CLOSE: int
FILE_FLAG_SEQUENTIAL_SCAN: int
FILE_FLAG_RANDOM_ACCESS: int
FILE_FLAG_BACKUP_SEMANTICS: int
FILE_FLAG_OPEN_REPARSE_POINT: int

GENERIC_READ: int
GENERIC_WRITE: int
DELETE: int

FILE_BEGIN: int
FILE_CURRENT: int
FILE_END: int

MOVEFILE_COPY_ALLOWED: int
MOVEFILE_CREATE_HARDLINK: int
MOVEFILE_DELAY_UNTIL_REBOOT: int
MOVEFILE_FAIL_IF_NOT_TRACKABLE: int
MOVEFILE_REPLACE_EXISTING: int
MOVEFILE_WRITE_THROUGH: int

FILE_NOTIFY_CHANGE_FILE_NAME: int
FILE_NOTIFY_CHANGE_DIR_NAME: int
FILE_NOTIFY_CHANGE_ATTRIBUTES: int
FILE_NOTIFY_CHANGE_SIZE: int
FILE_NOTIFY_CHANGE_LAST_WRITE: int
FILE_NOTIFY_CHANGE_LAST_ACCESS: int
FILE_NOTIFY_CHANGE_CREATION: int
FILE_NOTIFY_CHANGE_SECURITY: int

FILE_ACTION_ADDED: int
FILE_ACTION_REMOVED: int
FILE_ACTION_MODIFIED: int
FILE_ACTION_RENAMED_OLD_NAME: int
FILE_ACTION_RENAMED_NEW_NAME: int

FILE_LIST_DIRECTORY: int

SHGFP_TYPE_CURRENT: int
SHGFP_TYPE_DEFAULT: int

PIPE_ACCESS_INBOUND: int
PIPE_ACCESS_OUTBOUND: int
PIPE_ACCESS_DUPLEX: int
FILE_FLAG_FIRST_PIPE_INSTANCE: int
PIPE_TYPE_BYTE: int
PIPE_READMODE_BYTE: int
PIPE_WAIT: int
PIPE_REJECT_REMOTE_CLIENTS: int

HANDLE_FLAG_INHERIT: int
HANDLE_FLAG_PROTECT_FROM_CLOSE: int

VK_RMENU: int

DONT_RESOLVE_DLL_REFERENCES: int
LOAD_LIBRARY_AS_DATAFILE: int
LOAD_LIBRARY_AS_IMAGE_RESOURCE: int

INFINITE: int
REG_QWORD: int

ERROR_SUCCESS: int
ERROR_MORE_DATA: int
ERROR_NO_MORE_ITEMS: int
ERROR_FILE_NOT_FOUND: int
ERROR_GEN_FAILURE: int
ERROR_INSUFFICIENT_BUFFER: int
ERROR_BAD_COMMAND: int
ERROR_INVALID_DATA: int
ERROR_NOT_READY: int
ERROR_SHARING_VIOLATION: int
ERROR_LOCK_VIOLATION: int
ERROR_ALREADY_EXISTS: int
ERROR_BROKEN_PIPE: int
ERROR_PIPE_BUSY: int
ERROR_DIR_NOT_EMPTY: int
ERROR_ACCESS_DENIED: int
ERROR_NO_DATA: int

KF_FLAG_DEFAULT: int
KF_FLAG_FORCE_APP_DATA_REDIRECTION: int
KF_FLAG_RETURN_FILTER_REDIRECTION_TARGET: int
KF_FLAG_FORCE_PACKAGE_REDIRECTION: int
KF_FLAG_NO_PACKAGE_REDIRECTION: int
KF_FLAG_FORCE_APPCONTAINER_REDIRECTION: int
KF_FLAG_NO_APPCONTAINER_REDIRECTION: int
KF_FLAG_CREATE: int
KF_FLAG_DONT_VERIFY: int
KF_FLAG_DONT_UNEXPAND: int
KF_FLAG_NO_ALIAS: int
KF_FLAG_INIT: int
KF_FLAG_DEFAULT_PATH: int
KF_FLAG_NOT_PARENT_RELATIVE: int
KF_FLAG_SIMPLE_IDLIST: int
KF_FLAG_ALIAS_ONLY: int

ComputerNameDnsDomain: int
ComputerNameDnsFullyQualified: int
ComputerNameDnsHostname: int
ComputerNameNetBIOS: int
ComputerNamePhysicalDnsDomain: int
ComputerNamePhysicalDnsFullyQualified: int
ComputerNamePhysicalDnsHostname: int
ComputerNamePhysicalNetBIOS: int

ES_AWAYMODE_REQUIRED: int
ES_CONTINUOUS: int
ES_DISPLAY_REQUIRED: int
ES_SYSTEM_REQUIRED: int
ES_USER_PRESENT: int

WAIT_OBJECT_0: int
WAIT_ABANDONED_0: int
WAIT_TIMEOUT: int
WAIT_FAILED: int

FOLDERID_AdminTools: GUID
FOLDERID_Startup: GUID
FOLDERID_RoamingAppData: GUID
FOLDERID_RecycleBinFolder: GUID
FOLDERID_CDBurning: GUID
FOLDERID_CommonAdminTools: GUID
FOLDERID_CommonStartup: GUID
FOLDERID_ProgramData: GUID
FOLDERID_PublicDesktop: GUID
FOLDERID_PublicDocuments: GUID
FOLDERID_Favorites: GUID
FOLDERID_PublicMusic: GUID
FOLDERID_CommonOEMLinks: GUID
FOLDERID_PublicPictures: GUID
FOLDERID_CommonPrograms: GUID
FOLDERID_CommonStartMenu: GUID
FOLDERID_CommonTemplates: GUID
FOLDERID_PublicVideos: GUID
FOLDERID_NetworkFolder: GUID
FOLDERID_ConnectionsFolder: GUID
FOLDERID_ControlPanelFolder: GUID
FOLDERID_Cookies: GUID
FOLDERID_Desktop: GUID
FOLDERID_ComputerFolder: GUID
FOLDERID_Fonts: GUID
FOLDERID_History: GUID
FOLDERID_InternetFolder: GUID
FOLDERID_InternetCache: GUID
FOLDERID_LocalAppData: GUID
FOLDERID_Documents: GUID
FOLDERID_Music: GUID
FOLDERID_Pictures: GUID
FOLDERID_Videos: GUID
FOLDERID_NetHood: GUID
FOLDERID_PrintersFolder: GUID
FOLDERID_PrintHood: GUID
FOLDERID_Profile: GUID
FOLDERID_ProgramFiles: GUID
FOLDERID_ProgramFilesX86: GUID
FOLDERID_ProgramFilesCommon: GUID
FOLDERID_ProgramFilesCommonX86: GUID
FOLDERID_Programs: GUID
FOLDERID_Recent: GUID
FOLDERID_ResourceDir: GUID
FOLDERID_LocalizedResourcesDir: GUID
FOLDERID_SendTo: GUID
FOLDERID_StartMenu: GUID
FOLDERID_System: GUID
FOLDERID_SystemX86: GUID
FOLDERID_Templates: GUID
FOLDERID_Windows: GUID
