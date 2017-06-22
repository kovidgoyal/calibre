#!/usr/bin/env python2
# coding: utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Gregory Riker'


'''
    Wrapper for libiMobileDevice library based on API documentation at
    http://www.libimobiledevice.org/docs/html/globals.html
'''

import os, sys

from collections import OrderedDict
from ctypes import (
    byref, cdll, create_string_buffer,
    c_char, c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulonglong, c_void_p,
    POINTER, string_at, Structure)

from calibre.constants import DEBUG, isosx, iswindows
from calibre.devices.idevice.parse_xml import XmlPropertyListParser
from calibre.devices.usbms.driver import debug_print


def load_library():
    if iswindows:
        env = "Windows"
        lib = cdll.LoadLibrary('libimobiledevice.dll')
        plist_lib = cdll.LoadLibrary('libplist.dll')
    elif isosx:
        env = "OS X"
        # Load libiMobileDevice
        path = 'libimobiledevice.6.dylib'
        lib = cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), path))
        # Load libplist
        path = 'libplist.3.dylib'
        plist_lib = cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), path))
    else:
        env = "linux"
        try:
            lib = cdll.LoadLibrary('libimobiledevice.so.6')
        except EnvironmentError:
            lib = cdll.LoadLibrary('libimobiledevice.so')
        plist_lib = cdll.LoadLibrary('libplist.so.3')
    return env, lib, plist_lib


class libiMobileDeviceException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class libiMobileDeviceIOException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class AFC_CLIENT_T(Structure):

    '''
    http://www.libimobiledevice.org/docs/html/structafc__client__private.html
    '''
    _fields_ = [
        # afc_client_private (afc.h)
        # service_client_private (service.h)
        # idevice_connection_private (idevice.h)
        ('connection_type', c_int),
        ('data', c_void_p),

        # ssl_data_private (idevice.h)
        ('session', c_void_p),
        ('ctx', c_void_p),
        ('bio', c_void_p),

        # afc_client_private (afc.h)
        ('afc_packet', c_void_p),
        ('file_handle', c_int),
        ('lock', c_int),

        # mutex - (Windows only?) (WinNT.h)
        ('LockCount', c_long),
        ('RecursionCount', c_long),
        ('OwningThread', c_void_p),
        ('LockSemaphore', c_void_p),
        ('SpinCount', c_void_p),

        # afc_client_private (afc.h)
        ('free_parent', c_int)]


class HOUSE_ARREST_CLIENT_T(Structure):

    '''
    http://www.libimobiledevice.org/docs/html/structhouse__arrest__client__private.html
    '''
    _fields_ = [
        # property_list_service_client
        # idevice_connection_private (idevice.h)
        ('type', c_int),
        ('data', c_void_p),

        # ssl_data_private (idevice.h)
        ('session', c_void_p),
        ('ctx', c_void_p),
        ('bio', c_void_p),

        # (house_arrest.h)
        ('mode', c_int)
    ]


class IDEVICE_T(Structure):

    '''
    http://www.libimobiledevice.org/docs/html/structidevice__private.html
    '''
    _fields_ = [
        ("udid", c_char_p),
        ("conn_type", c_int),
        ("conn_data", c_void_p)]


class INSTPROXY_CLIENT_T(Structure):

    '''
    http://www.libimobiledevice.org/docs/html/structinstproxy__client__private.html
    '''
    _fields_ = [
        # instproxy_client_private (installation_proxy.h)
        # idevice_connection_private (idevice.h)
        ('connection_type', c_int),
        ('data', c_void_p),

        # ssl_data_private (idevice.h)
        ('session', c_void_p),
        ('ctx', c_void_p),
        ('bio', c_void_p),

        # mutex - Windows only (WinNT.h)
        ('LockCount', c_long),
        ('RecursionCount', c_long),
        ('OwningThread', c_void_p),
        ('LockSemaphore', c_void_p),
        ('SpinCount', c_void_p),
        ('status_updater', c_void_p)
    ]


class LOCKDOWND_CLIENT_T(Structure):

    '''
    http://www.libimobiledevice.org/docs/html/structlockdownd__client__private.html
    '''
    _fields_ = [
        # lockdownd_client_private
        # property_list_service_client
        # idevice_connection_private
        ('connection_type', c_int),
        ('data', c_void_p),

        # ssl_data_private
        ('session', c_char_p),
        ('ctx', c_char_p),
        ('bio', c_char_p),

        # lockdown_client_private
        ('ssl_enabled', c_int),
        ('session_id', c_char_p),
        ('udid', c_char_p),
        ('label', c_char_p)]


class LOCKDOWND_SERVICE_DESCRIPTOR(Structure):

    '''
    from libimobiledevice/include/libimobiledevice/lockdown.h
    '''
    _fields_ = [
        ('port', c_uint),
        ('ssl_enabled', c_ubyte)
    ]


class libiMobileDevice():

    '''
    Wrapper for libiMobileDevice
    '''
    # AFC File operation enumerations
    AFC_FOPEN_RDONLY = 1
    AFC_FOPEN_RW = 2
    AFC_FOPEN_WRONLY = 3
    AFC_FOPEN_WR = 4
    AFC_FOPEN_APPEND = 5
    AFC_FOPEN_RDAPPEND = 6

    # Error reporting template
    LIB_ERROR_TEMPLATE = "ERROR: {cls}:{func}(): {desc}"

    # Location reporting template
    LOCATION_TEMPLATE = "{cls}:{func}({arg1}) {arg2}"

    # iDevice udid string
    UDID_SIZE = 40

    def __init__(self, **kwargs):
        self.verbose = kwargs.get('verbose', False)
        if not self.verbose:
            self._log = self.__null
            self._log_location = self.__null
        self._log_location()
        self.afc = None
        self.app_version = 0
        self.client_options = None
        self.control = None
        self.device = None
        self.device_connected = None
        self.device_info = None
        self.device_mounted = False
        self.device_name = None
        self.file_stats = {}
        self.house_arrest = None
        self.installed_apps = None
        self.instproxy = None

        self.load_library()

    # ~~~ Public methods ~~~
    def connect_idevice(self):
        '''
        Convenience method to get iDevice ready to talk
        '''
        self._log_location()
        self.device_connected = False
        try:
            self.device = self._idevice_new()
            self.control = self._lockdown_client_new_with_handshake()
            self.device_name = self._lockdown_get_device_name()
            self._lockdown_start_service("com.apple.mobile.installation_proxy")
            self.device_connected = True

        except libiMobileDeviceException as e:
            self._log_error(e.value)
            self.disconnect_idevice()

        return self.device_connected

    def copy_to_idevice(self, src, dst):
        '''
        High-level convenience method to copy src from local filesystem to
        dst on iDevice.
        Assumed to be a binary file (epub, sqlite, etc)
        src: file on local filesystem
        dst: file to be created on iOS filesystem
        '''
        self._log_location("src:{0} dst:{1}".format(repr(src), repr(dst)))
        BUFFER_SIZE = 10 * 1024 * 1024

        handle = self._afc_file_open(str(dst), mode='wb')
        if handle is not None:
            # Get the file size
            file_stats = os.stat(src)
            file_size = file_stats.st_size
            self._log("file_size: {:,} bytes".format(file_size))
            if file_size > BUFFER_SIZE:
                bytes_remaining = file_size
                with lopen(src, 'rb') as f:
                    while bytes_remaining:
                        if bytes_remaining > BUFFER_SIZE:
                            self._log("copying {:,} byte chunk".format(BUFFER_SIZE))
                            content = bytearray(f.read(BUFFER_SIZE))
                            success = self._afc_file_write(handle, content, mode='wb')
                            bytes_remaining -= BUFFER_SIZE
                        else:
                            self._log("copying final {:,} bytes".format(bytes_remaining))
                            content = bytearray(f.read(bytes_remaining))
                            success = self._afc_file_write(handle, content, mode='wb')
                            bytes_remaining = 0
                            self._log(" success: {0}".format(success))
            else:
                with lopen(src, 'rb') as f:
                    content = bytearray(f.read())
                success = self._afc_file_write(handle, content, mode='wb')
                self._log(" success: {0}".format(success))

            self._afc_file_close(handle)
        else:
            self._log(" could not create copy")

    def copy_from_idevice(self, src, dst):
        '''
        High-level convenience method to copy from src on iDevice to
        dst on local filesystem.
        src: path to file on iDevice
        dst: file object on local filesystem
        '''
        self._log_location()
        self._log("src: {0}".format(repr(src)))
        self._log("dst: {0}".format(dst.name))

        BUFFER_SIZE = 10 * 1024 * 1024
        data = None
        mode = 'rb'
        handle = self._afc_file_open(src, mode)
        if handle is not None:
            file_stats = self._afc_get_file_info(src)
            file_size = int(file_stats['st_size'])
            self._log("file {0} file_size: {1:,} bytes".format(repr(src), file_size))
            if file_size > BUFFER_SIZE:
                bytes_remaining = file_size
                while bytes_remaining:
                    if bytes_remaining > BUFFER_SIZE:
                        self._log("copying file {0} to {1}, {2:,} byte chunk".format(repr(src), dst.name, BUFFER_SIZE))
                        data = self._afc_file_read(handle, BUFFER_SIZE, mode)
                        dst.write(data)
                        bytes_remaining -= BUFFER_SIZE
                    else:
                        self._log("copying file {0} to {1}, final {2:,} bytes".format(repr(src), dst.name, bytes_remaining))
                        data = self._afc_file_read(handle, bytes_remaining, mode)
                        dst.write(data)
                        bytes_remaining = 0
            else:
                self._log("copying file {0} to {1}, {2:,} bytes".format(repr(src), dst.name, file_size))
                data = self._afc_file_read(handle, file_size, mode)
                dst.write(data)

            self._afc_file_close(handle)
            dst.close()

            # Update timestamps to match
            file_stats = self._afc_get_file_info(src)
            self._log("copied file {0} ({1:,} bytes) to file '{2}' ({3:,} bytes)".format(repr(src), file_size, dst.name, os.path.getsize(dst.name)))
            os.utime(dst.name, (file_stats['st_mtime'], file_stats['st_mtime']))

        else:
            self._log(" could not open file")
            raise libiMobileDeviceIOException("could not open file {0} for reading".format(repr(src)))

    def disconnect_idevice(self):
        '''
        Convenience method to close connection
        '''
        self._log_location(self.device_name)
        if self.device_mounted:
            self._afc_client_free()
            self._house_arrest_client_free()
            # self._lockdown_goodbye()
            self._idevice_free()
            self.device_mounted = False
        else:
            self._log(" device already disconnected")

    def dismount_ios_media_folder(self):
        if self.device_mounted:
            self._afc_client_free()
            # self._lockdown_goodbye()
            self._idevice_free()
            self.device_mounted = False

    def exists(self, path, silent=False):
        '''
        Determine if path exists

        Returns file_info or {}
        '''
        self._log_location("{0}".format(repr(path)))
        return self._afc_get_file_info(path, silent=silent)

    def get_device_info(self):
        '''
        Return device profile:
          {'Model': 'iPad2,5',
           'FSTotalBytes': '14738952192',
           'FSFreeBytes':  '11264917504',
           'FSBlockSize': '4096'}
        '''
        self._log_location()
        self.device_info = self._afc_get_device_info()
        return self.device_info

    def get_device_list(self):
        '''
        Return a list of connected udids
        '''
        self._log_location()
        return self._idevice_get_device_list()

    def get_folder_size(self, path):
        '''
        Recursively descend through a dir to add all file sizes in folder
        '''
        def _calculate_folder_size(path, initial_folder_size):
            '''
            Recursively calculate folder size
            '''
            this_dir = self._afc_read_directory(path)
            folder_size = 0
            for item in this_dir:
                folder_size += int(this_dir[item]['st_size'])
                if this_dir[item]['st_ifmt'] == 'S_IFDIR':
                    new_path = '/'.join([path, item])
                    initial_folder_size += _calculate_folder_size(new_path, folder_size)
            return folder_size + initial_folder_size

        self._log_location(path)
        stats = self.stat(path)
        cumulative_folder_size = _calculate_folder_size(path, int(stats['st_size']))
        return cumulative_folder_size

    def get_installed_apps(self, applist):
        '''
        Generate a sorted dict of installed apps from applist
        An empty applist returns all installed apps

        {<appname>: {'app_version': '1.2.3', 'app_id': 'com.apple.iBooks'}}
        '''

        # For apps in applist, get the details
        self.instproxy = self._instproxy_client_new()
        self.client_options = self._instproxy_client_options_new()
        self._instproxy_client_options_add("ApplicationType", "User")
        installed_apps = self._instproxy_browse(applist=applist)
        self.installed_apps = OrderedDict()
        for app in sorted(installed_apps, key=lambda s: s.lower()):
            self.installed_apps[app] = installed_apps[app]

        # Free the resources
        self._instproxy_client_options_free()
        self._instproxy_client_free()

    def get_preferences(self, requested_items=(
        'DeviceClass',
        'DeviceColor',
        'DeviceName',
        'FirmwareVersion',
        'HardwareModel',
        'ModelNumber',
        'PasswordProtected',
        'ProductType',
        'ProductVersion',
        'SerialNumber',
        'TimeIntervalSince1970',
        'TimeZone',
        'TimeZoneOffsetFromUTC',
        'UniqueDeviceID')):
        '''
        Get a partial list device-specific information
        See _lockdown_get_value() for all known items
        '''
        self._log_location()
        return self._lockdown_get_value(requested_items)

    def listdir(self, path, get_stats=True):
        '''
        Return a list containing the names of the entries in the iOS directory
        given by path.
        '''
        self._log_location("{0}".format(repr(path)))
        return self._afc_read_directory(path, get_stats=get_stats)

    def load_library(self):
        env, self.lib, self.plist_lib = load_library()
        self._log_location(env)
        self._log(" libimobiledevice loaded from '{0}'".format(self.lib._name))
        self._log(" libplist loaded from '{0}'".format(self.plist_lib._name))

        if False:
            self._idevice_set_debug_level(DEBUG)

    def mkdir(self, path):
        '''
        Mimic mkdir(), creating a directory at path. Does not create
        intermediate folders
        '''
        self._log_location("{0}".format(repr(path)))
        return self._afc_make_directory(path)

    def mount_ios_app(self, app_name=None, app_id=None):
        '''
        Convenience method to get iDevice ready to talk to app_name or app_id
        app_name:
            Check installed apps for app_name
            If available, establish afc connection with app container
        app_id:
            establish afc connection with app container
        '''
        self._log_location(app_name if app_name else app_id)

        self.device_mounted = False

        if app_name:
            try:
                self.device = self._idevice_new()
                self.control = self._lockdown_client_new_with_handshake()
                self.device_name = self._lockdown_get_device_name()

                # Get the installed apps
                self._lockdown_start_service("com.apple.mobile.installation_proxy")
                self.instproxy = self._instproxy_client_new()
                self.client_options = self._instproxy_client_options_new()
                self._instproxy_client_options_add("ApplicationType", "User")
                self.installed_apps = self._instproxy_browse(applist=[app_name])
                self._instproxy_client_options_free()
                self._instproxy_client_free()

                if app_name not in self.installed_apps:
                    self._log(" {0} not installed on this iDevice".format(repr(app_name)))
                    self.disconnect_idevice()
                else:
                    # Mount the app's Container
                    self._lockdown_start_service("com.apple.mobile.house_arrest")
                    self.house_arrest = self._house_arrest_client_new()
                    self._house_arrest_send_command(command='VendContainer',
                                                    appid=self.installed_apps[app_name]['app_id'])
                    self._house_arrest_get_result()
                    self.afc = self._afc_client_new_from_house_arrest_client()
                    self._lockdown_client_free()
                    self.app_version = self.installed_apps[app_name]['app_version']
                    self.device_mounted = True

            except libiMobileDeviceException as e:
                self._log_error(e.value)
                self.disconnect_idevice()

        elif app_id:
            try:
                self.device = self._idevice_new()
                self.control = self._lockdown_client_new_with_handshake()
                self.device_name = self._lockdown_get_device_name()
                self._lockdown_start_service("com.apple.mobile.house_arrest")
                self.house_arrest = self._house_arrest_client_new()
                self._house_arrest_send_command(command='VendContainer', appid=app_id)
                self._house_arrest_get_result()
                self.afc = self._afc_client_new_from_house_arrest_client()
                self._lockdown_client_free()
                self.device_mounted = True

            except libiMobileDeviceException as e:
                self._log_error("{0}: {1}".format(app_id, e.value))
                self.disconnect_idevice()

        if self.device_mounted:
            self._log_location("'{0}' mounted".format(app_name if app_name else app_id))
        else:
            self._log_location("unable to mount '{0}'".format(app_name if app_name else app_id))
        return self.device_mounted

    def mount_ios_media_folder(self):
        '''
        Mount the non-app folders:
            AirFair
            Airlock
            ApplicationArchives
            Books
            DCIM
            DiskAid
            Downloads
            PhotoData
            Photos
            Purchases
            Safari
            general_storage
            iTunes_Control
        '''
        self._log_location()
        try:
            self.device = self._idevice_new()
            self.control = self._lockdown_client_new_with_handshake()
            self._lockdown_start_service("com.apple.afc")
            self.afc = self._afc_client_new()

            self._lockdown_client_free()
            self.device_mounted = True

        except libiMobileDeviceException as e:
            self._log(e.value)
            self.dismount_ios_media_folder()

    def read(self, path, mode='r'):
        '''
        Convenience method to read from path on iDevice to memory buffer.
        Use for small files.
        For larger files copied to local file, use copy_from_idevice()
        '''
        self._log_location("{0} mode='{1}'".format(repr(path), mode))

        data = None
        handle = self._afc_file_open(path, mode)
        if handle is not None:
            file_stats = self._afc_get_file_info(path)
            data = self._afc_file_read(handle, int(file_stats['st_size']), mode)
            self._afc_file_close(handle)
        else:
            self._log(" could not open file")
            raise libiMobileDeviceIOException("could not open file {0} for reading".format(repr(path)))

        return data

    def rename(self, from_name, to_name):
        '''
        Renames a file or directory on the device

        client: (afc_client_t) The client to have rename
        from_name:   (const char *) The fully-qualified path to rename from
        to_name:     (const char *) The fully-qualified path to rename to
        '''
        self._log_location("from: {0} to: {1}".format(repr(from_name), repr(to_name)))

        error = self.lib.afc_rename_path(byref(self.afc),
                                         str(from_name),
                                         str(to_name))
        if error:
            self._log(" ERROR: {0}".format(self._afc_error(error)))

    def remove(self, path):
        '''
        Deletes a file or directory

        client  (afc_client_t) The client to use
        path    (const char *) The fully-qualified path to delete
        '''
        self._log_location("{0}".format(repr(path)))

        error = self.lib.afc_remove_path(byref(self.afc), str(path))

        if error:
            self._log_error(" ERROR: {0} path:{1}".format(self._afc_error(error), repr(path)))

    def stat(self, path):
        '''
        Return a stat dict for path
         file_stats:
          {'st_size': '12345',
           'st_blocks': '123',
           'st_nlink': '1',
           'st_ifmt': ['S_IFREG'|'S_IFDIR'],
           'st_mtime': xxx.yyy,
           'st_birthtime': xxx.yyy}

        '''
        self._log_location("{0}".format(repr(path)))
        return self._afc_get_file_info(path)

    def write(self, content, destination, mode='w'):
        '''
        Convenience method to write to path on iDevice
        '''
        self._log_location("{0}".format(repr(destination)))

        handle = self._afc_file_open(destination, mode=mode)
        if handle is not None:
            success = self._afc_file_write(handle, content, mode=mode)
            self._log(" success: {0}".format(success))
            self._afc_file_close(handle)
        else:
            self._log(" could not open file for writing")
            raise libiMobileDeviceIOException("could not open file for writing")

    # ~~~ AFC functions ~~~
    # http://www.libimobiledevice.org/docs/html/include_2libimobiledevice_2afc_8h.html
    def _afc_client_free(self):
        '''
        Frees up an AFC client.
        If the connection was created by the client itself, the connection will be closed.

        Args:
         client: (AFC_CLIENT_T) The client to free

        Result:
         AFC client freed, connection closed
        '''
        self._log_location()

        error = self.lib.afc_client_free(byref(self.afc)) & 0xFFFF
        if error:
            self._log_error(" ERROR: {0}".format(self._afc_error(error)))

    def _afc_client_new(self):
        '''
        Makes a connection to the AFC service on the device
        '''
        self._log_location()
        self.afc = None
        afc_client_t = POINTER(AFC_CLIENT_T)()
        error = self.lib.afc_client_new(byref(self.device),
                                        self.lockdown,
                                        byref(afc_client_t)) & 0xFFFF

        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._afc_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if afc_client_t.contents:
                return afc_client_t.contents
            else:
                error_description = self.LIB_ERROR_TEMPLATE.format(
                    cls=self.__class__.__name__,
                    func=sys._getframe().f_code.co_name,
                    desc="AFC not initialized")
                raise libiMobileDeviceException(error_description)

    def _afc_client_new_from_house_arrest_client(self):
        '''
        Creates an AFC client using the given house_arrest client's connection,
        allowing file access to a specific application directory requested by functions
        like house_arrest_request_vendor_documents().
        (NB: this header is declared in house_arrest.h)

        Args:
         house_arrest: (HOUSE_ARREST_CLIENT_T) The house_arrest client to use
         afc_client:   (AFC_CLIENT_T *) Pointer that will be set to a newly allocated
                        afc_client_t upon successful return

        Return:
         error: AFC_E_SUCCESS if the afc client was successfuly created, AFC_E_INVALID_ARG
                 if client is invalid or was already used to create an afc client, or an
                 AFC_E_* error code returned by afc_client_new_from_connection()

        NOTE:
         After calling this function the house_arrest client will go into an AFC mode that
         will only allow calling house_arrest_client_free(). Only call
         house_arrest_client_free() if all AFC operations have completed, since it will
         close the connection.
        '''
        self._log_location()

        self.afc = None
        afc_client_t = POINTER(AFC_CLIENT_T)()
        error = self.lib.afc_client_new_from_house_arrest_client(byref(self.house_arrest),
                                                                 byref(afc_client_t)) & 0xFFFF

        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._afc_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if afc_client_t.contents:
                return afc_client_t.contents
            else:
                error_description = self.LIB_ERROR_TEMPLATE.format(
                    cls=self.__class__.__name__,
                    func=sys._getframe().f_code.co_name,
                    desc="AFC not initialized")
                raise libiMobileDeviceException(error_description)

    def _afc_error(self, error):
        '''
        Returns an error string based on a numeric error returned by an AFC function call

        Args:
         error: (int)

        Result:
         (str) describing error

        '''
        e = "UNKNOWN ERROR (%d)" % error
        if not error:
            e = "Success (0)"
        elif error == 2:
            e = "Header invalid (2)"
        elif error == 3:
            e = "No resources (3)"
        elif error == 4:
            e = "Read error (4)"
        elif error == 5:
            e = "Write error (5)"
        elif error == 6:
            e = "Unknown packet type (6)"
        elif error == 7:
            e = "Invalid arg (7)"
        elif error == 8:
            e = "Object not found (8)"
        elif error == 9:
            e = "Object is directory (9)"
        elif error == 10:
            e = "Permission denied (10)"
        elif error == 11:
            e = "Service not connected (11)"
        elif error == 12:
            e = "Operation timeout"
        elif error == 13:
            e = "Too much data"
        elif error == 14:
            e = "End of data"
        elif error == 15:
            e = "Operation not supported"
        elif error == 16:
            e = "Object exists"
        elif error == 17:
            e = "Object busy"
        elif error == 18:
            e = "No space left"
        elif error == 19:
            e = "Operation would block"
        elif error == 20:
            e = "IO error"
        elif error == 21:
            e = "Operation interrupted"
        elif error == 22:
            e = "Operation in progress"
        elif error == 23:
            e = "Internal error"
        elif error == 30:
            e = "MUX error"
        elif error == 31:
            e = "No memory"
        elif error == 32:
            e = "Not enough data"
        elif error == 33:
            e = "Directory not empty"
        return e

    def _afc_file_close(self, handle):
        '''
        Closes a file on the device

        Args:
         client: (AFC_CLIENT_T) The client to close the file with
         handle: (uint64) File handle of a previously opened file

        Result:
         File closed

        '''
        self._log_location("handle:{0}".format(handle.value))

        error = self.lib.afc_file_close(byref(self.afc),
                                        handle) & 0xFFFF
        if error:
            self._log_error(" ERROR: {0} handle:{1}".format(self._afc_error(error), handle))

    def _afc_file_open(self, filename, mode='r'):
        '''
        Opens a file on the device

        Args:
        (wrapper convenience)
         'r' reading (default)
         'w' writing, replacing
         'b' binary

        (libiMobileDevice)
         client:    (AFC_CLIENT_T) The client to use to open the file
         filename:  (const char *) The file to open (must be a fully-qualified path)
         file_mode: (AFC_FILE_MODE_T) The mode to use to open the file. Can be AFC_FILE_READ
                    or AFC_FILE_WRITE; the former lets you read and write, however, the
                    second one will create the file, destroying anything previously there.
         handle:    (uint64_t *) Pointer to a uint64_t that will hold the handle of the file

        Result:
         error:      (afc_error_t) AFC_E_SUCCESS (0) on success or AFC_E_* error value

        '''
        self._log_location("{0} mode='{1}'".format(repr(filename), mode))

        handle = c_ulonglong(0)

        if 'r' in mode:
            error = self.lib.afc_file_open(byref(self.afc),
                                           str(filename),
                                           self.AFC_FOPEN_RDONLY,
                                           byref(handle)) & 0xFFFF
        elif 'w' in mode:
            error = self.lib.afc_file_open(byref(self.afc),
                                           str(filename),
                                           self.AFC_FOPEN_WRONLY,
                                           byref(handle)) & 0xFFFF

        if error:
            self._log_error(" ERROR: {0} filename:{1}".format(self._afc_error(error), repr(filename)))
            return None
        else:
            return handle

    def _afc_file_read(self, handle, size, mode):
        '''
        Attempts to read the given number of bytes from the given file

        Args:
        (wrapper)
         mode: ['r'|'rb']

        (libiMobileDevice)
         client:     (AFC_CLIENT_T) The relevant AFC client
         handle:     (uint64_t) File handle of a previously opened file
         data:       (char *) Pointer to the memory region to store the read data
         length:     (uint32_t) The number of bytes to read
         bytes_read: (uint32_t *) The number of bytes actually read

        Result:
         error       (afc_error_t) AFC_E_SUCCESS (0) on success or AFC_E_* error value

        '''
        self._log_location("handle:{0} size:{1:,} mode='{2}'".format(handle.value, size, mode))

        bytes_remaining = size
        if 'b' in mode:
            data = bytearray(size)
            datatype = c_char * size
            while bytes_remaining > 0:
                bytes_read = c_uint(0)
                error = self.lib.afc_file_read(byref(self.afc),
                                               handle,
                                               byref(datatype.from_buffer(data), size - bytes_remaining),
                                               bytes_remaining,
                                               byref(bytes_read)) & 0xFFFF
                if error:
                    self._log_error(" ERROR: {0} handle:{1}".format(self._afc_error(error), handle.value))
                    bytes_remaining = 0
                elif bytes_read.value <= 0:
                    self._log_error(" ERROR: reading {0:,} bytes, 0 bytes read, handle:{1}".format(bytes_remaining, handle.value))
                    bytes_remaining = 0
                else:
                    bytes_remaining -= bytes_read.value
            return data
        else:
            data = create_string_buffer(size)
            while bytes_remaining > 0:
                bytes_read = c_uint(0)
                error = self.lib.afc_file_read(byref(self.afc), handle, byref(data, size - bytes_remaining), bytes_remaining, byref(bytes_read))
                if error:
                    self._log_error(" ERROR: {0} handle:{1}".format(self._afc_error(error), handle.value))
                    bytes_remaining = 0
                elif bytes_read.value <= 0:
                    self._log_error(" ERROR: reading {0:,} bytes, 0 bytes read, handle:{1}".format(bytes_remaining, handle.value))
                    bytes_remaining = 0
                else:
                    bytes_remaining -= bytes_read.value
            return data.value

    def _afc_file_write(self, handle, content, mode='w'):
        '''
        Writes a given number of bytes to a file

        Args:
        (wrapper)
         mode: ['w'|'wb']

        (libiMobileDevice)
         client:        (AFC_CLIENT_T) The client to use to write to the file
         handle:        (uint64_t) File handle of previously opened file
         data:          (const char *) The data to write to the file
         length:        (uint32_t) How much data to write
         bytes_written: (uint32_t *) The number of bytes actually written to the file

        Result:
         error:         (afc_error_t) AFC_E_SUCCESS (0) on success or AFC_E_* error value

        '''
        self._log_location("handle:{0} mode='{1}'".format(handle.value, mode))

        size = len(content)
        if 'b' in mode:
            # Content already contained in a bytearray()
            data = content
            datatype = c_char * size
        else:
            data = bytearray(content, 'utf-8')
            datatype = c_char * size

        bytes_remaining = size
        while bytes_remaining > 0:
            bytes_written = c_uint(0)
            error = self.lib.afc_file_write(byref(self.afc),
                                        handle,
                                        byref(datatype.from_buffer(data), size - bytes_remaining),
                                        bytes_remaining,
                                        byref(bytes_written)) & 0xFFFF
            if error:
                self._log_error(" ERROR: {0} handle:{1}".format(self._afc_error(error), handle.value))
                return False
            elif bytes_written.value <= 0:
                self._log_error(" ERROR: writing {0:,} bytes, 0 bytes written, handle:{1}".format(bytes_remaining, handle.value))
                return False
            else:
                bytes_remaining -= bytes_written.value
        return True

    def _afc_get_device_info(self):
        '''
        Get device information for a connected client

        Args:
         client: (AFC_CLIENT_T) The client to get the device info for
         infos: (char ***) A char ** list of parameters as returned by AFC or
                None if there was an error

        Result:
         error:         (afc_error_t) AFC_E_SUCCESS (0) on success or AFC_E_* error value
         device_info:
          {'Model': 'iPad2,5',
           'FSTotalBytes': '14738952192',
           'FSFreeBytes':  '11264917504',
           'FSBlockSize': '4096'}

        '''
        self._log_location()

        device_info = {}
        if self.afc is not None:
            info_raw_p = c_char_p
            info_raw = POINTER(info_raw_p)()

            error = self.lib.afc_get_device_info(byref(self.afc),
                                                 byref(info_raw)) & 0xFFFF
            if not error:
                num_items = 0
                item_list = []
                while info_raw[num_items]:
                    item_list.append(info_raw[num_items])
                    num_items += 1
                for i in range(0, len(item_list), 2):
                    device_info[item_list[i]] = item_list[i+1]
                if self.verbose:
                    for key in device_info.keys():
                        self._log("{0:>16}: {1}".format(key, device_info[key]))
            else:
                self._log(" ERROR: {0}".format(self._afc_error(error)))
        else:
            self._log(" ERROR: AFC not initialized, can't get device info")
        return device_info

    def _afc_get_file_info(self, path, silent=False):
        '''
        Gets information about a specific file

        Args:
         client:   (AFC_CLIENT_T) The client to use to get the information of a file
         path:     (const char *) The fully qualified path to the file
         infolist: (char ***) Pointer to a buffer that will be filled with a NULL-terminated
                    list of strings with the file information. Set to NULL before calling
                    this function

        Result:
         error:    (afc_error_t) AFC_E_SUCCESS (0) on success or AFC_E_* error value
         file_stats:
          {'st_size': '12345',
           'st_blocks': '123',
           'st_nlink': '1',
           'st_ifmt': ['S_IFREG'|'S_IFDIR'],
           'st_mtime': xxx.yyy,
           'st_birthtime': xxx.yyy}

        '''
        self._log_location("{0}".format(repr(path)))

        infolist_p = c_char * 1024
        infolist = POINTER(POINTER(infolist_p))()
        error = self.lib.afc_get_file_info(byref(self.afc),
                                           str(path),
                                           byref(infolist)) & 0xFFFF
        file_stats = {}
        if error:
            if not silent or self.verbose:
                self._log_error(" ERROR: {0} path:{1}".format(self._afc_error(error), repr(path)))
        else:
            num_items = 0
            item_list = []
            while infolist[num_items]:
                item_list.append(infolist[num_items])
                num_items += 1
            for i in range(0, len(item_list), 2):
                if item_list[i].contents.value in ['st_mtime', 'st_birthtime']:
                    integer = item_list[i+1].contents.value[:10]
                    decimal = item_list[i+1].contents.value[10:]
                    value = float("{0}.{1}".format(integer, decimal))
                else:
                    value = item_list[i+1].contents.value
                file_stats[item_list[i].contents.value] = value

            if False and self.verbose:
                for key in file_stats.keys():
                    self._log(" {0}: {1}".format(key, file_stats[key]))
        return file_stats

    def _afc_make_directory(self, path):
        '''
        Creates a directory on the device. Does not create intermediate dirs.

        Args:
         client: (AFC_CLIENT_T) The client to use to make a directory
         dir:    (const char *) The directory's fully-qualified path

        Result:
         error:  AFC_E_SUCCESS on success or an AFC_E_* error value
        '''
        self._log_location("{0}".format(repr(path)))

        error = self.lib.afc_make_directory(byref(self.afc),
                                            str(path)) & 0xFFFF
        if error:
            self._log_error(" ERROR: {0} path: {1}".format(self._afc_error(error), repr(path)))

        return error

    def _afc_read_directory(self, directory='', get_stats=True):
        '''
        Gets a directory listing of the directory requested

        Args:
         client:    (AFC_CLIENT_T) The client to get a directory listing from
         dir:       (const char *) The directory to list (a fully-qualified path)
         list:      (char ***) A char list of files in that directory, terminated by
                     an empty string. NULL if there was an error.
         get_stats: If True, return full file stats for each file in dir (slower)
                    If False, return filename only (faster)
        Result:
         error: AFC_E_SUCCESS on success or an AFC_E_* error value
         file_stats:
            {'<path_basename>': {<file_stats>} ...}

        '''
        self._log_location("{0}".format(repr(directory)))

        file_stats = {}
        dirs_p = c_char_p
        dirs = POINTER(dirs_p)()
        error = self.lib.afc_read_directory(byref(self.afc),
                                            str(directory),
                                            byref(dirs)) & 0xFFFF
        if error:
            self._log_error(" ERROR: {0} directory: {1}".format(self._afc_error(error), repr(directory)))
        else:
            num_dirs = 0
            dir_list = []
            while dirs[num_dirs]:
                dir_list.append(dirs[num_dirs])
                num_dirs += 1

            # Build a dict of the file_info stats
            for i, this_item in enumerate(dir_list):
                if this_item.startswith('.'):
                    continue
                if directory == '/':
                    path = '/' + this_item
                else:
                    path = '/'.join([directory, this_item])
                if get_stats:
                    file_stats[os.path.basename(path)] = self._afc_get_file_info(path)
                else:
                    file_stats[os.path.basename(path)] = {}
            self.current_dir = directory
        return file_stats

    # ~~~ house_arrest functions ~~~
    # http://www.libimobiledevice.org/docs/html/include_2libimobiledevice_2house__arrest_8h.html
    def _house_arrest_client_free(self):
        '''
        Disconnects a house_arrest client from the device, frees up the
        house_arrest client data

        Args:
         client: (HOUSE_ARREST_CLIENT_T) The house_arrest client to disconnect and free

        Return:
         error: HOUSE_ARREST_E_SUCCESS on success,
                HOUSE_ARREST_E_INVALID_ARG when client is NULL,
                HOUSE_ARREST_E_* error code otherwise

        NOTE:
         After using afc_client_new_from_house_arrest_client(), make sure you call
         afc_client_free() before calling this function to ensure a proper cleanup. Do
         not call this function if you still need to perform AFC operations since it
         will close the connection.

        '''

        self._log_location()

        error = self.lib.house_arrest_client_free(byref(self.house_arrest)) & 0xFFFF
        if error:
            error = error - 0x10000
            self._log_error(" ERROR: {0}".format(self._house_arrest_error(error)))

    def _house_arrest_client_new(self):
        '''
        Connects to the house_arrest client on the specified device

        Args:
         device: (IDEVICE_T) The device to connect to
         port:   (uint16_t) Destination port (usually given by lockdownd_start_service)
         client: (HOUSE_ARREST_CLIENT_T *) Pointer that will point to a newly allocated
                  house_arrest_client_t upon successful return

        Return:
         HOUSE_ARREST_E_SUCCESS on success
         HOUSE_ARREST_E_INVALID_ARG when client is NULL
         HOUSE_ARREST_E_* error code otherwise

        '''
        self._log_location()

        house_arrest_client_t = POINTER(HOUSE_ARREST_CLIENT_T)()
        error = self.lib.house_arrest_client_new(byref(self.device),
                                                 self.lockdown,
                                                 byref(house_arrest_client_t)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._house_arrest_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if not house_arrest_client_t:
                self._log(" Could not start document sharing service")
                self._log("  1: Bad command")
                self._log("  2: Bad device")
                self._log("  3. Connection refused")
                self._log("  6. Bad version")
                return None
            else:
                return house_arrest_client_t.contents

    def _house_arrest_error(self, error):
        e = "UNKNOWN ERROR (%d)" % error
        if not error:
            e = "Success (0)"
        elif error == -1:
            e = "Invalid arg (-1)"
        elif error == -2:
            e = "plist error (-2)"
        elif error == -3:
            e = "connection failed (-3)"
        elif error == -4:
            e = "invalid mode (-4)"

        return e

    def _house_arrest_get_result(self):
        '''
        Retrieves the result of a previously sent house_arrest_* request

        Args:
         client: (HOUSE_ARREST_CLIENT_T) The house_arrest client to use
         dict:   (plist_t *) Pointer that will be set to a plist containing the result
                  of the last performed operation. It holds a key 'Status' with the
                  value 'Complete' on success, or 'a key 'Error' with an error
                  description as value. The caller is responsible for freeing the
                  returned plist.

        Return:
         error:  HOUSE_ARREST_E_SUCCESS if a result plist was retrieved,
                 HOUSE_ARREST_E_INVALID_ARG if client is invalid,
                 HOUSE_ARREST_E_INVALID_MODE if the client is not in the correct mode, or
                 HOUSE_ARREST_E_CONN_FAILED if a connection error occured.

        '''
        self._log_location()

        plist = c_char_p()
        self.lib.house_arrest_get_result(byref(self.house_arrest),
                                         byref(plist)) & 0xFFFF
        plist = c_void_p.from_buffer(plist)

        # Convert the plist to xml
        xml = POINTER(c_void_p)()
        xml_len = c_long(0)
        self.plist_lib.plist_to_xml(c_void_p.from_buffer(plist), byref(xml), byref(xml_len))
        result = XmlPropertyListParser().parse(string_at(xml, xml_len.value))
        self.plist_lib.plist_free(plist)

        # To determine success, we need to inspect the returned plist
        if 'Status' in result:
            self._log("          STATUS: {0}".format(result['Status']))
        elif 'Error' in result:
            self._log("           ERROR: {0}".format(result['Error']))
            raise libiMobileDeviceException(result['Error'])

    def _house_arrest_send_command(self, command=None, appid=None):
        '''
        Send a command to the connected house_arrest service

        Args:
         client:  (HOUSE_ARREST_CLIENT_T) The house_arrest client to use
         command: (const char *) The command to send. Currently, only 'VendContainer'
                   and 'VendDocuments' are known
         appid:   (const char *) The application identifier

        Result:
         error:   HOUSE_ARREST_E_SUCCESS if the command was successfully sent,
                  HOUSE_ARREST_E_INVALID_ARG if client, command, or appid is invalid,
                  HOUSE_ARREST_E_INVALID_MODE if the client is not in the correct mode, or
                  HOUSE_ARREST_E_CONN_FAILED if a connection error occured.

        NOTE:     If the function returns HOUSE_ARREST_E_SUCCESS it does not mean that
                  the command was successful. To check for success or failure you need
                  to call house_arrest_get_result().

        '''
        self._log_location("command={0} appid={1}".format(repr(command), repr(appid)))

        commands = ['VendContainer', 'VendDocuments']

        if command not in commands:
            self._log(" ERROR: available commands: {0}".format(', '.join(commands)))
            return

        _command = create_string_buffer(command)
        _appid = create_string_buffer(appid)

        error = self.lib.house_arrest_send_command(byref(self.house_arrest),
                                                   _command,
                                                   _appid) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._house_arrest_error(error))
            raise libiMobileDeviceException(error_description)

    # ~~~ idevice functions ~~~
    # http://www.libimobiledevice.org/docs/html/libimobiledevice_8h.html
    def _idevice_error(self, error):
        e = "UNKNOWN ERROR (%d)" % error
        if not error:
            e = "Success"
        elif error == -1:
            e = "INVALID_ARG (-1)"
        elif error == -2:
            e = "UNKNOWN_ERROR (-2)"
        elif error == -3:
            e = "NO_DEVICE (-3)"
        elif error == -4:
            e = "NOT_ENOUGH_DATA (-4)"
        elif error == -5:
            e = "BAD_HEADER (-5)"
        elif error == -6:
            e = "SSL_ERROR (-6)"
        return e

    def _idevice_free(self):
        '''
        Cleans up an idevice structure, then frees the structure itself.

        Args:
         device: (IDEVICE_T) idevice to free

        Return:
         error: IDEVICE_E_SUCCESS if ok, otherwise an error code.
        '''
        self._log_location()

        error = self.lib.idevice_free(byref(self.device)) & 0xFFFF

        if error:
            error = error - 0x10000
            self._log_error(" ERROR: {0}".format(self._idevice_error(error)))

    def _idevice_get_device_list(self):
        '''
        Return a list of connected udids
        n devices: [udid, udid,...]
        0 devices: []
        Error:     None
        '''
        self._log_location()

        self.lib.idevice_get_device_list.argtypes = [POINTER(POINTER(POINTER(c_char * self.UDID_SIZE))), POINTER(c_long)]

        count = c_long(0)
        udid = c_char * self.UDID_SIZE
        devices = POINTER(POINTER(udid))()
        device_list = []
        error = self.lib.idevice_get_device_list(byref(devices), byref(count)) & 0xFFFF
        if error:
            error = error - 0x10000
            if error == -3:
                self._log(" no connected devices")
            else:
                device_list = None
                self._log_error(" ERROR: {0}".format(self._idevice_error(error)))
        else:
            index = 0
            while devices[index]:
                # Filter out redundant entries
                if devices[index].contents.value not in device_list:
                    device_list.append(devices[index].contents.value)
                index += 1
            self._log(" {0}".format(repr(device_list)))
        # self.lib.idevice_device_list_free()
        return device_list

    def _idevice_new(self):
        '''
        Creates an IDEVICE_T structure for the device specified  by udid, if the
        device is available.

        Args:
         device: (IDEVICE_T) On successful return, a pointer to a populated IDEVICE_T structure.
         udid:   (const char *) The UDID to match. If NULL, use connected device.

        Return:
         error:   IDEVICE_E_SUCCESS if ok, otherwise an error code

        '''
        self._log_location()

        idevice_t = POINTER(IDEVICE_T)()
        error = self.lib.idevice_new(byref(idevice_t),
                                     c_void_p()) & 0xFFFF

        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._idevice_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if idevice_t.contents.conn_type == 1:
                self._log("       conn_type: CONNECTION_USBMUXD")
            else:
                self._log("       conn_type: Unknown ({0})".format(idevice_t.contents.conn_type))
            self._log("            udid: {0}".format(idevice_t.contents.udid))
            return idevice_t.contents

    def _idevice_set_debug_level(self, debug):
        '''
        Sets the level of debugging

        Args:
         level (int) Set to 0 for no debugging, 1 for debugging

        '''
        self._log_location(debug)
        self.lib.idevice_set_debug_level(debug)

    # ~~~ instproxy functions ~~~
    # http://www.libimobiledevice.org/docs/html/include_2libimobiledevice_2installation__proxy_8h.html
    def _instproxy_browse(self, applist=[]):
        '''
        Fetch the app list
        '''
        self._log_location(applist)

        apps = c_void_p()
        error = self.lib.instproxy_browse(byref(self.instproxy),
                                          self.client_options,
                                          byref(apps)) & 0xFFFF

        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            # Get the number of apps
            # app_count = self.lib.plist_array_get_size(apps)
            # self._log("       app_count: {0}".format(app_count))

            # Convert the app plist to xml
            xml = POINTER(c_void_p)()
            xml_len = c_long(0)
            self.plist_lib.plist_to_xml(c_void_p.from_buffer(apps), byref(xml), byref(xml_len))
            app_list = XmlPropertyListParser().parse(string_at(xml, xml_len.value))
            installed_apps = {}
            for app in app_list:
                if 'CFBundleName' in app:
                    app_name = app['CFBundleName']
                elif 'CFBundleDisplayName' in app:
                    app_name = app['CFBundleDisplayName']
                elif 'CFBundleExecutable' in app:
                    app_name = app['CFBundleExecutable']
                else:
                    self._log(" unable to find app name in bundle:")
                    for key in sorted(app.keys()):
                        self._log("  {0}   {1}".format(repr(key), repr(app[key])))
                    continue

                if not applist:
                    # Collecting all installed apps info
                    installed_apps[app_name] = {'app_id': app['CFBundleIdentifier'], 'app_version': app['CFBundleVersion']}
                else:
                    # Selectively collecting app info
                    if app_name in applist:
                        installed_apps[app['CFBundleName']] = {'app_id': app['CFBundleIdentifier'], 'app_version': app['CFBundleVersion']}
                        if len(installed_apps) == len(app_list):
                            break

            if self.verbose:
                for app in sorted(installed_apps, key=lambda s: s.lower()):
                    attrs = {'app_name': app, 'app_id': installed_apps[app]['app_id'], 'app_version': installed_apps[app]['app_version']}
                    self._log("  {app_name:<30}  {app_id:<40} {app_version}".format(**attrs))

        self.plist_lib.plist_free(apps)
        return installed_apps

    def _instproxy_client_new(self):
        '''
        Create an instproxy_client
        '''
        self._log_location()

        instproxy_client_t = POINTER(INSTPROXY_CLIENT_T)()
        error = self.lib.instproxy_client_new(byref(self.device),
                                              self.lockdown,
                                              byref(instproxy_client_t)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            return instproxy_client_t.contents

    def _instproxy_client_free(self):
        '''
        '''
        self._log_location()

        error = self.lib.instproxy_client_free(byref(self.instproxy)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)

    def _instproxy_client_options_add(self, app_type, domain):
        '''
        Specify the type of apps we want to browse
        '''
        self._log_location("{0}, {1}".format(repr(app_type), repr(domain)))

        self.lib.instproxy_client_options_add(self.client_options,
                                              app_type, domain, None)

    def _instproxy_client_options_free(self):
        '''
        '''
        self._log_location()
        self.lib.instproxy_client_options_free(self.client_options)

    def _instproxy_client_options_new(self):
        '''
        Create a client options plist
        '''
        self._log_location()

        self.lib.instproxy_client_options_new.restype = c_char * 8
        client_options = self.lib.instproxy_client_options_new()
        client_options = c_void_p.from_buffer(client_options)
        return client_options

    def _instproxy_error(self, error):
        '''
        Return a string version of the error code
        '''
        e = "UNKNOWN ERROR (%d)" % error
        if not error:
            e = "Success"
        elif error == -1:
            e = "Invalid arg (-1)"
        elif error == -2:
            e = "Plist error (-2)"
        elif error == -3:
            e = "Connection failed (-3)"
        elif error == -4:
            e = "Operation in progress (-4)"
        elif error == -5:
            e = "Operation failed (-5)"
        return e

    # ~~~ lockdown functions ~~~
    # http://www.libimobiledevice.org/docs/html/include_2libimobiledevice_2lockdown_8h.html
    def _lockdown_client_free(self):
        '''
        Close the lockdownd client session if one is running, free up the lockdown_client struct

        Args:
         client: (LOCKDOWN_CLIENT_T) The  lockdownd client to free

        Return:
         error: LOCKDOWN_E_SUCCESS on success, NP_E_INVALID_ARG when client is NULL

        '''
        self._log_location()

        error = self.lib.lockdownd_client_free(byref(self.control)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)

        self.control = None

    def _lockdown_client_new_with_handshake(self):
        '''
        Create a new lockdownd client for the device, starts initial handshake.

        Args:
         device: (IDEVICE_T) The device to create a lockdownd client for
         client: (LOCKDOWN_CLIENT_D *) The pointer to the location of the new lockdownd client
         label:  (const char *) The label to use for communication, usually the program name.
                  Pass NULL to disable sending the label in requests to lockdownd.

        Return:
         error:  LOCKDOWN_E_SUCCESS on success,
                 NP_E_INVALID_ARG when client is NULL,
                 LOCKDOWN_E_INVALID_CONF if configuration data is wrong
         locked_down: [True|False]

        NOTE:
         The device disconnects automatically if the lockdown connection idles for more
         than 10 seconds. Make sure to call lockdownd_client_free() as soon as the
         connection is no longer needed.

        '''
        self._log_location()

        lockdownd_client_t = POINTER(LOCKDOWND_CLIENT_T)()
        # SERVICE_NAME = create_string_buffer('calibre')
        SERVICE_NAME = c_void_p()
        error = self.lib.lockdownd_client_new_with_handshake(byref(self.device),
                                                             byref(lockdownd_client_t),
                                                             SERVICE_NAME) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            return lockdownd_client_t.contents

    def _lockdown_error(self, error):
        e = "UNKNOWN ERROR (%d)" % error
        if not error:
            e = "Success"
        elif error == -1:
            e = "INVALID_ARG"
        elif error == -2:
            e = "INVALID_CONF"
        elif error == -3:
            e = "PLIST_ERROR"
        elif error == -4:
            e = "PAIRING_FAILED"
        elif error == -5:
            e = "SSL_ERROR"
        elif error == -6:
            e = "DICT_ERROR"
        elif error == -7:
            e = "START_SERVICE_FAILED"
        elif error == -8:
            e = "NOT_ENOUGH_DATA"
        elif error == -9:
            e = "SET_VALUE_PROHIBITED"
        elif error == -10:
            e = "GET_VALUE_PROHIBITED"
        elif error == -11:
            e = "REMOVE_VALUE_PROHIBITED"
        elif error == -12:
            e = "MUX_ERROR"
        elif error == -13:
            e = "ACTIVATION_FAILED"
        elif error == -14:
            e = "PASSWORD_PROTECTED"
        elif error == -15:
            e = "NO_RUNNING_SESSION"
        elif error == -16:
            e = "INVALID_HOST_ID"
        elif error == -17:
            e = "INVALID_SERVICE"
        elif error == -18:
            e = "INVALID_ACTIVATION_RECORD"
        elif error == -256:
            e = "UNKNOWN_ERROR"
        return e

    def _lockdown_get_device_name(self):
        '''
        Retrieves the name of the device as set by user

        Args:
         client:      (LOCKDOWND_CLIENT_T) An initialized lockdownd client
         device_name: (char **) Holds the name of the device.

        Return:
         error:       LOCKDOWN_E_SUCCESS on success
         device_name: Name of iDevice

        '''
        self._log_location()

        device_name_p = c_char_p()
        device_name = None
        error = self.lib.lockdownd_get_device_name(byref(self.control),
                                                   byref(device_name_p)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            device_name = device_name_p.value
            self._log("     device_name: {0}".format(device_name))
        return device_name

    def _lockdown_get_value(self, requested_items=[]):
        '''
        Retrieves a preferences plist using an optional domain and/or key name.

        requested_items: A python list of specific preference items to retrieve
                         An empty list (default) retrieves all available values
        Args:
         client: (LOCKDOWND_CLIENT_T) An initialized lockdown client
         domain: (const char *) The domain to query on or NULL for global domain
         key:    (const char *) The key name to request or NULL to query for all keys
         value:  (PLIST_T *) A plist node representing the result value code

        Return:
         error:  LOCKDOWN_E_SUCCESS on success,
                 NP_E_INVALID_ARG when client is NULL

        preferences_dict: A dict of requested device values

        Available values (as of iOS 6.3):
        --------------------------
        ActivationState
        ActivationStateAcknowledged
        ActivityURL
        BasebandActivationTicketVersion
        BasebandCertID
        BasebandChipID
        BasebandKeyHashInformation
        BasebandMasterKeyHash
        BasebandRegioSKU
        BasebandSerialNumber
        BasebandStatus
        BluetoothAddress
        BoardID
        BuildVersion
        CPUArchitecture
        CarrierBundleInfoArray
        CertID
        ChipID
        ChipSerialNo
        CompassCalibration
        DeviceCertificate
        DeviceClass
        DeviceColor
        DeviceName
        DevicePublicKey
        DieID
        EthernetAddress
        FirmwareVersion
        FusingStatus
        HardwareModel
        HardwarePlatform
        HostAttached
        IMLockdownEventRegisteredKey
        IntegratedCircuitCardIdentity
        InternationalMobileEquipmentIdentity
        InternationalMobileSubscriberIdentity
        MLBSerailNumber
        MobileSubscriberCountryCode
        MobileSubscriberNetworkCode
        ModelNumber
        NonVolatileRAM
        PartitionType
        PasswordProtected
        PhoneNumber
        ProductType
        ProductVersion
        ProductSOC
        ProtocolVersion
        ProximitySensorCalibration
        RegionInfo
        SBLockdownEverRegisteredKey
        SIMGID1
        SIMGID2
        SIMStatus
        SIMTrayStatus
        SerialNumber
        SoftwareBehavior
        SoftwareBundleVersion
        SupportedDeviceFamilies
        TelephonyCapability
        TimeIntervalSince1970
        TimeZone
        TimeZoneOffsetFromUTC
        TrustedHostAttached
        UniqueChipID
        UniqueDeviceID
        UseActivityURL
        UseRaptorCerts
        Use24HourClock
        WeDelivered
        WiFiAddress
        kCTPostponementInfoPRIVersion
        kCTPostponementInfoPRLName
        kCTPostponementInfoUniqueID
        kCTPostponementStatus
        '''
        self._log_location()

        preferences = c_char_p()
        preferences_dict = {}

        error = self.lib.lockdownd_get_value(byref(self.control),
                                             None,
                                             None,
                                             byref(preferences)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            xml = POINTER(c_char_p)()
            xml_len = c_uint(0)
            self.plist_lib.plist_to_xml(c_char_p.from_buffer(preferences), byref(xml), byref(xml_len))
            preferences_list = XmlPropertyListParser().parse(string_at(xml, xml_len.value))
            source_list = preferences_list.keys()
            if requested_items:
                source_list = requested_items
            for pref in source_list:
                preferences_dict[pref] = preferences_list[pref]

        self.plist_lib.plist_free(preferences)
        return preferences_dict

    def _lockdown_goodbye(self):
        '''
        Sends a Goodbye request lockdownd, signaling the end of communication

        Args:
         client: (LOCKDOWND_CLIENT_T) The lockdown client

        Return:
         error:  LOCKDOWN_E_SUCCESS on success,
                 LOCKDOWN_E_INVALID_ARG when client is NULL,
                 LOCKDOWN_E_PLIST_ERROR if the device did not acknowledge the request

        '''
        self._log_location()

        if self.control:
            error = self.lib.lockdownd_goodbye(byref(self.control)) & 0xFFFF
            error = error - 0x10000
            self._log(" ERROR: {0}".format(self.error_lockdown(error)))
        else:
            self._log(" connection already closed")

    def _lockdown_start_service(self, service_name):
        '''
        Request to start service

        Args:
         client:  (LOCKDOWND_CLIENT_T) The lockdownd client
         service: (const char *) The name of the service to start
         port:    (unit16_t *) The port number the service was started on

        Return:
         error:   LOCKDOWN_E_SUCCESS on success,
                  NP_E_INVALID_ARG if a parameter is NULL,
                  LOCKDOWN_E_INVALID_SERVICE if the requested service is not known by the device,
                  LOCKDOWN_E_START_SERVICE_FAILED if the service could not because started by the device

        '''
        self._log_location(service_name)

        SERVICE_NAME = create_string_buffer(service_name)
        self.lockdown = POINTER(LOCKDOWND_SERVICE_DESCRIPTOR)()
        error = self.lib.lockdownd_start_service(byref(self.control),
                                                 SERVICE_NAME,
                                                 byref(self.lockdown)) & 0xFFFF
        if error:
            error = error - 0x10000
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)

    # ~~~ logging ~~~
    def _log(self, msg=None):
        '''
        Print msg to console
        '''
        if msg:
            debug_print(" {0}".format(msg))
        else:
            debug_print()

    def _log_error(self, *args):
        '''
        Print error message with location regardless of self.verbose
        '''
        arg1 = arg2 = ''

        if len(args) > 0:
            arg1 = args[0]
        if len(args) > 1:
            arg2 = args[1]

        debug_print(self.LOCATION_TEMPLATE.format(cls=self.__class__.__name__,
            func=sys._getframe(1).f_code.co_name, arg1=arg1, arg2=arg2))

    def _log_location(self, *args):
        '''
        '''
        arg1 = arg2 = ''

        if len(args) > 0:
            arg1 = args[0]
        if len(args) > 1:
            arg2 = args[1]

        debug_print(self.LOCATION_TEMPLATE.format(cls=self.__class__.__name__,
            func=sys._getframe(1).f_code.co_name, arg1=arg1, arg2=arg2))

    def __null(self, *args, **kwargs):
        pass
