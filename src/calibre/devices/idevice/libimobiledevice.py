#!/usr/bin/env python
# coding: utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Gregory Riker'

'''
    Wrapper for libiMobileDevice library based on API documentation at
    http://www.libimobiledevice.org/docs/html/globals.html
'''

import binascii, os, sys, time

from collections import OrderedDict
from ctypes import *
from datetime import datetime

from calibre.constants import DEBUG, islinux, isosx, iswindows
from calibre.devices.usbms.driver import debug_print

from calibre_plugins.marvin.parse_xml import XmlPropertyListParser
#from calibre.devices.idevice.parse_xml import XmlPropertyListParser

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
        ('connection', c_long),
        ('afc_packet', c_void_p),
        ('file_handle', c_int),
        ('lock', c_int),
        ('mutex', c_long),
        ('own_connection', c_int)]

class HOUSE_ARREST_CLIENT_T(Structure):
    '''
    http://www.libimobiledevice.org/docs/html/structhouse__arrest__client__private.html
    '''
    _fields_ = [
        ("parent", c_long),
        ("mode", c_int)]

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
        ("parent", c_long),
        ("mutex", c_long),
        ("status_updater", c_long)]

class LOCKDOWND_CLIENT_T(Structure):
    '''
    http://www.libimobiledevice.org/docs/html/structlockdownd__client__private.html
    '''
    _fields_ = [
        ('parent', c_long),
        ('ssl_enabled', c_int),
        ('session_id', c_char_p),
        ('udid', c_char_p),
        ('label', c_char_p)]


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

    def __init__(self, log=debug_print, verbose=False):
        self.log = log
        self.verbose = verbose

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
            self.log(e.value)
            self.disconnect_idevice()

        return self.device_connected

    def copy_to_iDevice(self, src, dst):
        '''
        High-level convenience method to copy src on local filesystem to
        dst on iDevice.
        src: file on local filesystem
        dst: file to be created on iOS filesystem
        '''
        self._log_location("src='%s', dst='%s'" % (src, dst))
        with open(src) as f:
            content = bytearray(f.read())
        mode = 'wb'
        handle = self._afc_file_open(dst, mode=mode)
        if handle is not None:
            success = self._afc_file_write(handle, content, mode=mode)
            if self.verbose:
                self.log(" success: %s" % success)
            self._afc_file_close(handle)
        else:
            if self.verbose:
                self.log(" could not create copy")

    def copy_from_iDevice(self, src, dst):
        '''
        High-level convenience method to copy from src on iDevice to
        dst on local filesystem.
        src: path to file on iDevice
        dst: file object on local filesystem
        '''
        self._log_location("src='%s', dst='%s'" % (src, dst.name))
        data = self.read(src, mode='rb')
        dst.write(data)
        dst.close()

        # Update timestamps to match
        file_stats = self._afc_get_file_info(src)
        os.utime(dst.name, (file_stats['st_mtime'], file_stats['st_mtime']))

    def disconnect_idevice(self):
        '''
        Convenience method to close connection
        '''
        self._log_location(self.device_name)
        if self.device_mounted:
            self._afc_client_free()
            self._house_arrest_client_free()
            #self._lockdown_goodbye()
            self._idevice_free()
            self.device_mounted = False
        else:
            if self.verbose:
                self.log(" device already disconnected")

    def dismount_ios_media_folder(self):
        self._afc_client_free()
        #self._lockdown_goodbye()
        self._idevice_free()
        self.device_mounted = False

    def exists(self, path):
        '''
        Determine if path exists

        Returns [True|False] or file_info
        '''
        self._log_location("'%s'" % path)
        return self._afc_get_file_info(path)

    def get_device_info(self):
        '''
        Return device profile
        '''
        self._log_location()
        self.device_info = self._afc_get_device_info()
        return self.device_info

    def get_device_list(self):
        '''
        Return a list of connected udids
        '''
        self._log_location()

        self.lib.idevice_get_device_list.argtypes = [POINTER(POINTER(POINTER(c_char * self.UDID_SIZE))), POINTER(c_long)]

        count = c_long(0)
        udid = c_char * self.UDID_SIZE
        devices = POINTER(POINTER(udid))()
        device_list = []
        error = self.lib.idevice_get_device_list(byref(devices), byref(count))
        if error and self.verbose:
            self.log(" ERROR: %s" % self._idevice_error(error))
        else:
            index = 0
            while devices[index]:
                device_list.append(devices[index].contents.value)
                index += 1
            if self.verbose:
                self.log(" %s" % repr(device_list))
        return device_list

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

    def listdir(self, path):
        '''
        Return a list containing the names of the entries in the iOS directory
        given by path.
        '''
        self._log_location("'%s'" % path)
        return self._afc_read_directory(path).keys()

    def load_library(self):
        if islinux:
            env = "linux"
            self.lib = cdll.LoadLibrary('libimobiledevice.so.4')
            self.plist_lib = cdll.LoadLibrary('libplist.so.1')
        elif isosx:
            env = "OS X"

            # Load libiMobileDevice
            path = 'libimobiledevice.4.dylib'
            if hasattr(sys, 'frameworks_dir'):
                self.lib = cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), path))
            else:
                self.lib = cdll.LoadLibrary(path)

            # Load libplist
            path = 'libplist.1.dylib'
            if hasattr(sys, 'frameworks_dir'):
                self.plist_lib = cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), path))
            else:
                self.plist_lib = cdll.LoadLibrary(path)
        elif iswindows:
            env = "Windows"
            self.lib = cdll.LoadLibrary('libimobiledevice.dll')
            self.plist_lib = cdll.LoadLibrary('libplist.dll')

        self._log_location(env)
        self.log(" libimobiledevice loaded from '%s'" % self.lib._name)
        self.log(" libplist loaded from '%s'" % self.plist_lib._name)

        if False:
            self._idevice_set_debug_level(DEBUG)

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

                if not app_name in self.installed_apps:
                    self.log(" '%s' not installed on this iDevice" % app_name)
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
                self.log(e.value)
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
                self.log(e.value)
                self.disconnect_idevice()

        if self.device_mounted:
            self._log_location("'%s' mounted" % (app_name if app_name else app_id))
        else:
            self._log_location("unable to mount '%s'" % (app_name if app_name else app_id))
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
            self.log(e.value)
            self.dismount_ios_media_folder()

    def read(self, path, mode='r'):
        '''
        Convenience method to read from path on iDevice
        '''
        self._log_location("'%s', mode='%s'" % (path, mode))

        data = None
        handle = self._afc_file_open(path, mode)
        if handle is not None:
            file_stats = self._afc_get_file_info(path)
            data = self._afc_file_read(handle, int(file_stats['st_size']), mode)
            self._afc_file_close(handle)
        else:
            if self.verbose:
                self.log(" could not open file")
            raise libiMobileDeviceIOException("could not open file for reading")

        return data

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
        self._log_location("'%s'" % path)
        return self._afc_get_file_info(path)

    def write(self, content, destination, mode='w'):
        '''
        Convenience method to write to path on iDevice
        '''
        self._log_location(destination)

        handle = self._afc_file_open(destination, mode=mode)
        if handle is not None:
            success = self._afc_file_write(handle, content, mode=mode)
            if self.verbose:
                self.log(" success: %s" % success)
            self._afc_file_close(handle)
        else:
            if self.verbose:
                self.log(" could not open file for writing")
            raise libiMobileDeviceIOException("could not open file for writing")

    # ~~~ lib helpers ~~~
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

        error = self.lib.afc_client_free(byref(self.afc))
        if error and self.verbose:
            self.log(" ERROR: %s" % self.afc_error(error))

    def _afc_client_new(self):
        '''
        Makes a connection to the AFC service on the device
        '''
        self._log_location()
        self.afc = None
        afc_client_t = POINTER(AFC_CLIENT_T)()
        error = self.lib.afc_client_new(byref(self.device), self.port, byref(afc_client_t))

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
        error = self.lib.afc_client_new_from_house_arrest_client(byref(self.house_arrest), byref(afc_client_t))

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
        e = "UNKNOWN ERROR (%s)" % error
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
        self._log_location(handle.value)

        error = self.lib.afc_file_close(byref(self.afc), handle)
        if error and self.verbose:
            self.log(" ERROR: %s" % self._afc_error(error))

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
        self._log_location("'%s', mode='%s'" % (filename, mode))

        handle = c_ulonglong(0)

        if 'r' in mode:
            error = self.lib.afc_file_open(byref(self.afc), str(filename), self.AFC_FOPEN_RDONLY, byref(handle))
        elif 'w' in mode:
            error = self.lib.afc_file_open(byref(self.afc), str(filename), self.AFC_FOPEN_WRONLY, byref(handle))

        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._afc_error(error))
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
        self._log_location("%s, size=%d, mode='%s'" % (handle.value, size, mode))

        bytes_read = c_uint(0)

        if 'b' in mode:
            data = bytearray(size)
            datatype = c_char * size
            error = self.lib.afc_file_read(byref(self.afc), handle, byref(datatype.from_buffer(data)), size, byref(bytes_read))
            if error:
                if self.verbose:
                    self.log(" ERROR: %s" % self._afc_error(error))
            return data
        else:
            data = create_string_buffer(size)
            error = self.lib.afc_file_read(byref(self.afc), handle, byref(data), size, byref(bytes_read))
            if error:
                if self.verbose:
                    self.log(" ERROR: %s" % self._afc_error(error))
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
        self._log_location("handle=%d, mode='%s'" % (handle.value, mode))

        bytes_written = c_uint(0)

        if 'b' in mode:
            # Content already contained in a bytearray()
            data = content
            datatype = c_char * len(content)
        else:
            data = bytearray(content,'utf-8')
            datatype = c_char * len(content)

        error = self.lib.afc_file_write(byref(self.afc), handle, byref(datatype.from_buffer(data)), len(content), byref(bytes_written))
        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._afc_error(error))
            return False
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

            error = self.lib.afc_get_device_info(byref(self.afc), byref(info_raw))
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
                        self.log("  %s: %s" % (key, device_info[key]))
            else:
                if self.verbose:
                    self.log(" ERROR: %s" % self._afc_error(error))
        else:
            if self.verbose:
                self.log(" ERROR: AFC not initialized, can't get device info")
        return device_info

    def _afc_get_file_info(self, path):
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
        self._log_location("'%s'" % path)

        infolist_p = c_char * 1024
        infolist = POINTER(POINTER(infolist_p))()
        error = self.lib.afc_get_file_info(byref(self.afc), str(path), byref(infolist))
        file_stats = {}
        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._afc_error(error))
        else:
            num_items = 0
            item_list = []
            while infolist[num_items]:
                item_list.append(infolist[num_items])
                num_items += 1
            item_type = None
            for i in range(0, len(item_list), 2):
                if item_list[i].contents.value in ['st_mtime', 'st_birthtime']:
                    integer = item_list[i+1].contents.value[:10]
                    decimal = item_list[i+1].contents.value[10:]
                    value = float("%s.%s" % (integer, decimal))
                else:
                    value = item_list[i+1].contents.value
                file_stats[item_list[i].contents.value] = value

            if False and self.verbose:
                for key in file_stats.keys():
                    self.log(" %s: %s" % (key, file_stats[key]))
        return file_stats

    def _afc_read_directory(self, directory=''):
        '''
        Gets a directory listing of the directory requested

        Args:
         client: (AFC_CLIENT_T) The client to get a directory listing from
         dir:    (const char *) The directory to list (a fully-qualified path)
         list:   (char ***) A char list of files in that directory, terminated by
                  an empty string. NULL if there was an error.

        Result:
         error: AFC_E_SUCCESS on success or an AFC_E_* error value
         file_stats:
            {'<path_basename>': {<file_stats>} ...}

        '''
        self._log_location("'%s'" % directory)

        file_stats = {}
        dirs_p = c_char_p
        dirs = POINTER(dirs_p)()
        error = self.lib.afc_read_directory(byref(self.afc), str(directory), byref(dirs))
        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._afc_error(error))
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
                path = '/'.join([directory, this_item])
                file_stats[os.path.basename(path)] = self._afc_get_file_info(path)
            self.current_dir = directory
        return file_stats


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

        error = self.lib.house_arrest_client_free(byref(self.house_arrest))
        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._house_arrest_error(error))

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
        error = self.lib.house_arrest_client_new(byref(self.device), self.port, byref(house_arrest_client_t))
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._house_arrest_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if not house_arrest_client_t:
                if self.verbose:
                    self.log(" Could not start document sharing service")
                    self.log("  1: Bad command")
                    self.log("  2: Bad device")
                    self.log("  3. Connection refused")
                    self.log("  6. Bad version")
                return None
            else:
                if self.verbose:
                    self.log("          parent: %s" % house_arrest_client_t.contents.parent)
                    self.log("            mode: %s" % house_arrest_client_t.contents.mode)
                return house_arrest_client_t.contents

    def _house_arrest_error(self, error):
        e = "UNKNOWN ERROR"
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
        error = self.lib.house_arrest_get_result(byref(self.house_arrest), byref(plist))
        plist = c_void_p.from_buffer(plist)

        # Convert the plist to xml
        xml = POINTER(c_void_p)()
        xml_len = c_long(0)
        self.lib.plist_to_xml(c_void_p.from_buffer(plist), byref(xml), byref(xml_len))
        result = XmlPropertyListParser().parse(string_at(xml, xml_len.value))
        self.lib.plist_free(plist)

        # To determine success, we need to inspect the returned plist
        if hasattr(result, 'Status'):
            if self.verbose:
                self.log("          STATUS: %s" % result['Status'])
        elif hasattr(result, 'Error'):
            if self.verbose:
                self.log("           ERROR: %s" % result['Error'])
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
        self._log_location("command='%s' appid='%s'" % (command, appid))

        commands = ['VendContainer', 'VendDocuments']

        if command not in commands:
            if self.verbose:
                self.log(" ERROR: available commands: %s" % ', '.join(commands))
            return

        _command = create_string_buffer(command)
        _appid = create_string_buffer(appid)

        error = self.lib.house_arrest_send_command(byref(self.house_arrest), _command, _appid)
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._house_arrest_error(error))
            raise libiMobileDeviceException(error_description)


    def _idevice_error(self, error):
        e = "UNKNOWN ERROR"
        if not error:
            e = "Success"
        elif error == -1:
            e = "INVALID_ARG"
        elif error == -2:
            e = "UNKNOWN_ERROR"
        elif error == -3:
            e = "NO_DEVICE"
        elif error == -4:
            e = "NOT_ENOUGH_DATA"
        elif error == -5:
            e = "BAD_HEADER"
        elif error == -6:
            e = "SSL_ERROR"
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

        error = self.lib.idevice_free(byref(self.device))
        if error:
            if self.verbose:
                self.log(" ERROR: %s" % self._idevice_error(error))

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
        error = self.lib.idevice_new(byref(idevice_t), c_void_p())

        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._idevice_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if self.verbose:
                if idevice_t.contents.conn_type == 1:
                    self.log("       conn_type: CONNECTION_USBMUXD")
                else:
                    self.log("       conn_type: Unknown (%d)" % idevice_t.contents.conn_type)
                self.log("       conn_data: %s" % idevice_t.contents.conn_data)
                self.log("            udid: %s" % idevice_t.contents.udid)
            return idevice_t.contents

    def _idevice_set_debug_level(self, debug):
        '''
        Sets the level of debugging

        Args:
         level (int) Set to 0 for no debugging, 1 for debugging

        '''
        self._log_location(debug)
        self.lib.idevice_set_debug_level(debug)


    def _instproxy_browse(self, applist=[]):
        '''
        Fetch the app list
        '''
        self._log_location(applist)

        apps = c_void_p()
        error = self.lib.instproxy_browse(byref(self.instproxy), self.client_options, byref(apps))

        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            # Get the number of apps
            #app_count = self.lib.plist_array_get_size(apps)
            #self.log("       app_count: %d" % app_count)

            # Convert the app plist to xml
            xml = POINTER(c_void_p)()
            xml_len = c_long(0)
            self.lib.plist_to_xml(c_void_p.from_buffer(apps), byref(xml), byref(xml_len))
            app_list = XmlPropertyListParser().parse(string_at(xml, xml_len.value))
            installed_apps = {}
            for app in app_list:
                if not applist:
                    try:
                        installed_apps[app['CFBundleName']] = {'app_id': app['CFBundleIdentifier'], 'app_version': app['CFBundleVersion']}
                    except:
                        installed_apps[app['CFBundleDisplayName']] = {'app_id': app['CFBundleDisplayName'], 'app_version': app['CFBundleDisplayName']}
                else:
                    if 'CFBundleName' in app:
                        if app['CFBundleName'] in applist:
                            installed_apps[app['CFBundleName']] = {'app_id': app['CFBundleIdentifier'], 'app_version': app['CFBundleVersion']}
                            if len(installed_apps) == len(app_list):
                                break
                    elif 'CFBundleDisplayName' in app:
                        if app['CFBundleDisplayName'] in applist:
                            installed_apps[app['CFBundleDisplayName']] = {'app_id': app['CFBundleIdentifier'], 'app_version': app['CFBundleVersion']}
                            if len(installed_apps) == len(app_list):
                                break
                    else:
                        self.log(" unable to find app name")
                        for key in sorted(app.keys()):
                            print(" %s \t %s" % (key, app[key]))
                        continue

            if self.verbose:
                for app in sorted(installed_apps, key=lambda s: s.lower()):
                    attrs = {'app_name': app, 'app_id': installed_apps[app]['app_id'], 'app_version': installed_apps[app]['app_version']}
                    self.log("  {app_name:<30}  {app_id:<40} {app_version}".format(**attrs))

        self.lib.plist_free(apps)
        return installed_apps

    def _instproxy_client_new(self):
        '''
        Create an instproxy_client
        '''
        self._log_location()

        instproxy_client_t = POINTER(INSTPROXY_CLIENT_T)()
        #error = self.lib.instproxy_client_new(byref(self.device), self.port.value, byref(instproxy_client_t))
        error = self.lib.instproxy_client_new(byref(self.device), self.port, byref(instproxy_client_t))
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if self.verbose:
                self.log("          parent: %s" % instproxy_client_t.contents.parent)
                self.log("           mutex: %s" % instproxy_client_t.contents.mutex)
                self.log("  status_updater: %s" % instproxy_client_t.contents.status_updater)
            return instproxy_client_t.contents

    def _instproxy_client_free(self):
        '''
        '''
        self._log_location()

        error = self.lib.instproxy_client_free(byref(self.instproxy))
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._instproxy_error(error))
            raise libiMobileDeviceException(error_description)

    def _instproxy_client_options_add(self, app_type, domain):
        '''
        Specify the type of apps we want to browse
        '''
        self._log_location("'%s', '%s'" % (app_type, domain))

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
        e = "UNKNOWN ERROR"
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


    def _lockdown_client_free(self):
        '''
        Close the lockdownd client session if one is running, free up the lockdown_client struct

        Args:
         client: (LOCKDOWN_CLIENT_T) The  lockdownd client to free

        Return:
         error: LOCKDOWN_E_SUCCESS on success, NP_E_INVALID_ARG when client is NULL

        '''
        self._log_location()

        error = self.lib.lockdownd_client_free(byref(self.control))
        if error:
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
        SERVICE_NAME = create_string_buffer('calibre')
        error = self.lib.lockdownd_client_new_with_handshake(byref(self.device),
            byref(lockdownd_client_t),
            SERVICE_NAME)

        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if self.verbose:
                self.log("          parent: %s" % lockdownd_client_t.contents.parent)
                self.log("     ssl_enabled: %s" % lockdownd_client_t.contents.ssl_enabled)
                self.log("      session_id: %s" % lockdownd_client_t.contents.session_id)
                self.log("            udid: %s" % lockdownd_client_t.contents.udid)
                self.log("           label: %s" % lockdownd_client_t.contents.label)
            return lockdownd_client_t.contents

    def _lockdown_error(self, error):
        e = "UNKNOWN ERROR"
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

        device_name_b = c_char * 32
        device_name_p = POINTER(device_name_b)()
        device_name = None
        error = self.lib.lockdownd_get_device_name(byref(self.control), byref(device_name_p))
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            device_name = device_name_p.contents.value
            if self.verbose:
                self.log("     device_name: %s" % device_name)
        return device_name

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
            error = self.lib.lockdownd_goodbye(byref(self.control))
            if self.verbose:
                self.log(" ERROR: %s" % self.error_lockdown(error))
        else:
            if self.verbose:
                self.log(" connection already closed")

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
        self.port = POINTER(c_uint)()
        error = self.lib.lockdownd_start_service(byref(self.control), SERVICE_NAME, byref(self.port))
        if error:
            error_description = self.LIB_ERROR_TEMPLATE.format(
                cls=self.__class__.__name__,
                func=sys._getframe().f_code.co_name,
                desc=self._lockdown_error(error))
            raise libiMobileDeviceException(error_description)
        else:
            if self.verbose:
                self.log("            port: %s" % self.port.contents.value)


    def _log_location(self, *args):
        '''
        '''
        if not self.verbose:
            return

        arg1 = arg2 = ''

        if len(args) > 0:
            arg1 = args[0]
        if len(args) > 1:
            arg2 = args[1]

        self.log(self.LOCATION_TEMPLATE.format(cls=self.__class__.__name__,
            func=sys._getframe(1).f_code.co_name, arg1=arg1, arg2=arg2))

