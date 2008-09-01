/*
:mod:`winutil` -- Interface to Windows
============================================

.. module:: winutil
    :platform: Windows
    :synopsis: Various methods to interface with the operating system

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2008

This module contains utility functions to interface with the windows operating
system. It should be compiled with the same version of VisualStudio used to
compile python. It hasn't been tested with MinGW. We try to use unicode
wherever possible in this module.

.. exception:: winutil.DriveError
    Raised when scanning for mounted volumes fails.

.. function:: is_usb_device_connected(vid : integer, pid : integer) -> bool
    Return `True` iff the USB device identified by the VendorID `vid` and
    ProductID `pid` is connected to the system.

.. function:: get_usb_devices() -> list of lowercase strings
    Return a list of all USB devices connected to the system. Each
    device is represented by a lowercase unicode string whoose format is
    the windows *Device Identifier* format. See the MSDN documentation.

.. function:: get_mounted_volumes_for_usb_device(vid : integer, pid : integer) -> dictionary
    Return a dictionary of the form `volume_id`:`drive_letter` for all
    volumes mounted from the device specified by `vid` and `pid`.

    :raises: :exception:`winutil.DriveError` if scanning fails.

.. function:: special_folder_path(csidl_id) -> path
    Get paths to common system folders.
    See windows documentation of SHGetFolderPath.
    The paths are returned as unicode objects. `csidl_id` should be one
    of the symbolic constants defined in this module. You can also `OR`
    a symbolic constant with :data:`CSIDL_FLAG_CREATE` to force the operating
    system to create a folder if it does not exist. For example::

        >>> from winutil import *
        >>> special_folder_path(CSIDL_APPDATA)
        u'C:\\Documents and Settings\\Kovid Goyal\\Application Data'
        >>>  special_folder_path(CSIDL_PERSONAL)
        u'C:\\Documents and Settings\\Kovid Goyal\\My Documents'

.. function:: argv() -> list of unicode command line arguments
    Get command line arguments as unicode objects. Note that the
    first argument will be the path to the interpreter, *not* the
    script being run. So to replace sys.argv, you should use
    `if len(sys.argv) > 1: sys.argv[1:] = winutil.argv()[1-len(sys.argv):]`

*/


#define UNICODE
#include <Windows.h>
#include <Python.h>
#include <structseq.h>
#include <timefuncs.h>
#include <shlobj.h>
#include <stdio.h>
#include <setupapi.h>
#include <devguid.h>
#include <cfgmgr32.h>
#include <stdarg.h>
#include <time.h>

#define PyStructSequence_GET_ITEM(op, i) \
    (((PyStructSequence *)(op))->ob_item[i])


#define BUFSIZE    512
#define MAX_DRIVES 26
static PyObject *DriveError;
static BOOL DEBUG = FALSE;

//#define debug(fmt, ...) if DEBUG printf(x, __VA_ARGS__);
void
debug(const char *fmt, ...) {
    va_list argList;
    va_start(argList, fmt);
    if (DEBUG) vprintf(fmt, argList);
    va_end(argList);
}

struct tagDrives
{
    WCHAR letter;
    WCHAR volume[BUFSIZE];
};

static PyObject *
winutil_folder_path(PyObject *self, PyObject *args) {
    int res; DWORD dwFlags;
    PyObject *ans = NULL;
    TCHAR wbuf[MAX_PATH]; CHAR buf[4*MAX_PATH];
    memset(wbuf, 0, sizeof(TCHAR)*MAX_PATH); memset(buf, 0, sizeof(CHAR)*MAX_PATH);

    if (!PyArg_ParseTuple(args, "l", &dwFlags)) return NULL;

    res = SHGetFolderPath(NULL, dwFlags, NULL, 0, wbuf);
    if (res != S_OK) {
        if (res == E_FAIL) PyErr_SetString(PyExc_ValueError, "Folder does not exist.");
        PyErr_SetString(PyExc_ValueError, "Folder not valid");
        return NULL;
    }
    res = WideCharToMultiByte(CP_UTF8, 0, wbuf, -1, buf, 4*MAX_PATH, NULL, NULL);
    ans = PyUnicode_DecodeUTF8(buf, res-1, "strict");
    return ans;
}

static PyObject *
winutil_argv(PyObject *self, PyObject *args) {
    PyObject *argv, *v;
    LPWSTR *_argv;
    LPSTR buf;
    int argc, i, bytes;
    if (!PyArg_ParseTuple(args, "")) return NULL;
    _argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (_argv == NULL) { PyErr_NoMemory(); return NULL; }
    argv = PyList_New(argc);
    if (argv != NULL) {
        for (i = 0; i < argc; i++) {
            bytes = WideCharToMultiByte(CP_UTF8, 0, _argv[i], -1, NULL, 0, NULL, NULL);
            buf = (LPSTR)PyMem_Malloc(sizeof(CHAR)*bytes);
            if (buf == NULL) { Py_DECREF(argv); argv = NULL; break; }
            WideCharToMultiByte(CP_UTF8, 0, _argv[i], -1, buf, bytes, NULL, NULL);
            v = PyUnicode_DecodeUTF8(buf, bytes-1, "strict");
            PyMem_Free(buf);
            if (v == NULL) { Py_DECREF(argv); argv = NULL; break; }
            PyList_SetItem(argv, i, v);
        }
    }
    LocalFree(_argv);
    return argv;
}

static LPVOID
format_last_error() {
    /* Format the last error as a string. The returned pointer should
       be freed with :cfunction:`LocalFree(lpMsgBuf)`. It can be printed with
       :cfunction:`printf("\n%ws\n", (LPCTSTR)lpMsgBuf)`.
    */

    LPVOID lpMsgBuf;
    FormatMessage(
    FORMAT_MESSAGE_ALLOCATE_BUFFER |
    FORMAT_MESSAGE_FROM_SYSTEM |
    FORMAT_MESSAGE_IGNORE_INSERTS,
    NULL,
    GetLastError(),
    0, // Default language
    (LPTSTR) &lpMsgBuf,
    0,
    NULL
	);
	return lpMsgBuf;
}

static PyObject *
winutil_set_debug(PyObject *self, PyObject *args) {
	PyObject *yes;
	if (!PyArg_ParseTuple(args, "O", &yes)) return NULL;
	DEBUG = (BOOL)PyObject_IsTrue(yes);
	return Py_None;
}

static LPTSTR
get_registry_property(HDEVINFO hDevInfo, DWORD index, DWORD property, BOOL *iterate) {
    /* Get a the property specified by `property` from the registry for the
     * device enumerated by `index` in the collection `hDevInfo`. `iterate`
     * will be set to `FALSE` if `index` points outside `hDevInfo`.
     * :return: A string allocated on the heap containing the property or
     *          `NULL` if an error occurred.
     */
    SP_DEVINFO_DATA DeviceInfoData;
    DWORD DataT;
    LPTSTR buffer = NULL;
    DWORD buffersize = 0;
    DeviceInfoData.cbSize = sizeof(SP_DEVINFO_DATA);

    if (!SetupDiEnumDeviceInfo(hDevInfo, index, &DeviceInfoData)) {
        *iterate = FALSE;
        return NULL;
    }

    while(!SetupDiGetDeviceRegistryProperty(
            hDevInfo,
            &DeviceInfoData,
            property,
            &DataT,
            (PBYTE)buffer,
            buffersize,
            &buffersize)) {
            if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
                buffer = (LPTSTR)PyMem_Malloc(2*buffersize); // Twice for bug in Win2k
            } else {
            	PyMem_Free(buffer);
            	PyErr_SetFromWindowsErr(0);
                buffer = NULL;
                break;
            }
    } //while

    return buffer;
}

static BOOL
check_device_id(LPTSTR buffer, unsigned int vid, unsigned int pid) {
    WCHAR xVid[9], dVid[9], xPid[9], dPid[9];
    unsigned int j;
    swprintf(xVid, L"vid_%4.4x", vid);
    swprintf(dVid, L"vid_%4.4d", vid);
    swprintf(xPid, L"pid_%4.4x", pid);
    swprintf(dPid, L"pid_%4.4d", pid);

    for (j = 0; j < wcslen(buffer); j++) buffer[j] = tolower(buffer[j]);

    return ( (wcsstr(buffer, xVid) != NULL || wcsstr(buffer, dVid) != NULL ) &&
             (wcsstr(buffer, xPid) != NULL || wcsstr(buffer, dPid) != NULL )
           );
}


static HDEVINFO
create_device_info_set(LPGUID guid, PCTSTR enumerator, HWND parent, DWORD flags) {
    HDEVINFO hDevInfo;
    hDevInfo = SetupDiGetClassDevs(
    		guid,
            enumerator,
            parent,
            flags
            );
    if (hDevInfo == INVALID_HANDLE_VALUE) {
        PyErr_SetFromWindowsErr(0);
    }
    return hDevInfo;
}

int n;

BOOL
get_all_removable_disks(struct tagDrives *g_drives)
{
    WCHAR	caDrive[4];
	WCHAR	volume[BUFSIZE];
	int		nLoopIndex;
	DWORD	dwDriveMask;
	unsigned int g_count=0;


	caDrive[0]	= 'A';
    caDrive[1]	= ':';
    caDrive[2]	= '\\';
    caDrive[3]	= 0;





	// Get all drives in the system.
    dwDriveMask = GetLogicalDrives();


	if(dwDriveMask == 0)
	{
		PyErr_SetString(DriveError, "GetLogicalDrives failed");
		return FALSE;
	}


	// Loop for all drives (MAX_DRIVES = 26)


    for(nLoopIndex = 0; nLoopIndex< MAX_DRIVES; nLoopIndex++)
    {
        // if a drive is present,
		if(dwDriveMask & 1)
        {
            caDrive[0] = 'A' + nLoopIndex;


			// If a drive is removable
			if(GetDriveType(caDrive) == DRIVE_REMOVABLE)
			{
				//Get its volume info and store it in the global variable.
				if(GetVolumeNameForVolumeMountPoint(caDrive, volume, BUFSIZE))
	            {
		            g_drives[g_count].letter = caDrive[0];
					wcscpy(g_drives[g_count].volume, volume);
					g_count ++;
				}

			}
		}
		dwDriveMask >>= 1;
	}


	// success if atleast one removable drive is found.
	if(g_count == 0)
	{
	    PyErr_SetString(DriveError, "No removable drives found");
		return FALSE;
	}
	return TRUE;

}

PSP_DEVICE_INTERFACE_DETAIL_DATA
get_device_grandparent(HDEVINFO hDevInfo, DWORD index, PWSTR buf, PWSTR volume_id,
                       BOOL *iterate) {
    SP_DEVICE_INTERFACE_DATA            interfaceData;
    SP_DEVINFO_DATA						devInfoData;
    BOOL                                status;
    PSP_DEVICE_INTERFACE_DETAIL_DATA    interfaceDetailData;
    DWORD                               interfaceDetailDataSize,
                                        reqSize;
    DEVINST                             parent;

    interfaceData.cbSize = sizeof (SP_INTERFACE_DEVICE_DATA);
    devInfoData.cbSize   = sizeof (SP_DEVINFO_DATA);

    status = SetupDiEnumDeviceInterfaces (
                hDevInfo,               // Interface Device Info handle
                NULL,                   // Device Info data
                (LPGUID)&GUID_DEVINTERFACE_VOLUME, // Interface registered by driver
                index,                  // Member
                &interfaceData          // Device Interface Data
                );
    if ( status == FALSE ) {
        *iterate = FALSE;
        return NULL;
    }
    SetupDiGetDeviceInterfaceDetail (
                hDevInfo,           // Interface Device info handle
                &interfaceData,     // Interface data for the event class
                NULL,               // Checking for buffer size
                0,                  // Checking for buffer size
                &reqSize,           // Buffer size required to get the detail data
                NULL                // Checking for buffer size
    );

    interfaceDetailDataSize = reqSize;
    interfaceDetailData = (PSP_DEVICE_INTERFACE_DETAIL_DATA)PyMem_Malloc(interfaceDetailDataSize+10);
    if ( interfaceDetailData == NULL ) {
        PyErr_NoMemory();
        return NULL;
    }
    interfaceDetailData->cbSize = sizeof (SP_INTERFACE_DEVICE_DETAIL_DATA);

    status = SetupDiGetDeviceInterfaceDetail (
                  hDevInfo,                 // Interface Device info handle
                  &interfaceData,           // Interface data for the event class
                  interfaceDetailData,      // Interface detail data
                  interfaceDetailDataSize,  // Interface detail data size
                  &reqSize,                 // Buffer size required to get the detail data
                  &devInfoData);            // Interface device info

    if ( status == FALSE ) {PyErr_SetFromWindowsErr(0); PyMem_Free(interfaceDetailData); return NULL;}

    // Get the device instance of parent. This points to USBSTOR.
    CM_Get_Parent(&parent, devInfoData.DevInst, 0);
    // Get the device ID of the USBSTORAGE volume
    CM_Get_Device_ID(parent, volume_id, BUFSIZE, 0);
    // Get the device instance of grand parent. This points to USB root.
	CM_Get_Parent(&parent, parent, 0);
	// Get the device ID of the USB root.
	CM_Get_Device_ID(parent, buf, BUFSIZE, 0);

    return interfaceDetailData;
}

static PyObject *
winutil_get_mounted_volumes_for_usb_device(PyObject *self, PyObject *args) {
    unsigned int vid, pid, length, j;
	HDEVINFO hDevInfo;
	BOOL  iterate = TRUE;
	PSP_DEVICE_INTERFACE_DETAIL_DATA interfaceDetailData;
    DWORD i;
    WCHAR buf[BUFSIZE], volume[BUFSIZE], volume_id[BUFSIZE];
    struct tagDrives g_drives[MAX_DRIVES];
    PyObject *volumes, *key, *val;

    if (!PyArg_ParseTuple(args, "ii", &vid, &pid)) {
    	return NULL;
    }

    volumes = PyDict_New();
    if (volumes == NULL) return NULL;

    for (j = 0; j < MAX_DRIVES; j++) g_drives[j].letter = 0;

    // Find all removable drives
    if (!get_all_removable_disks(g_drives)) {
        return NULL;
    }

    hDevInfo = create_device_info_set((LPGUID)&GUID_DEVINTERFACE_VOLUME,
                            NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (hDevInfo == INVALID_HANDLE_VALUE) return NULL;

    // Enumerate through the set
    for (i=0; iterate; i++) {
        interfaceDetailData = get_device_grandparent(hDevInfo, i, buf, volume_id, &iterate);
        if (interfaceDetailData == NULL) {
            PyErr_Print(); continue;
        }
        debug("Device num: %d Device Id: %ws\n\n", i, buf);
        if (check_device_id(buf, vid, pid)) {
            debug("Device matches\n\n");
            length = wcslen(interfaceDetailData->DevicePath);
            interfaceDetailData->DevicePath[length] = '\\';
            interfaceDetailData->DevicePath[length+1] = 0;
            if(GetVolumeNameForVolumeMountPoint(interfaceDetailData->DevicePath, volume, BUFSIZE)) {

                for(j = 0; j < MAX_DRIVES; j++) {
                    // Compare volume mount point with the one stored earlier.
                    // If both match, return the corresponding drive letter.
                    if(g_drives[j].letter != 0 && wcscmp(g_drives[j].volume, volume)==0)
                    {
                        key = PyUnicode_FromWideChar(volume_id, wcslen(volume_id));
                        val = PyString_FromFormat("%c", (char)g_drives[j].letter);
                        if (key == NULL || val == NULL) {
                            PyErr_NoMemory();
                            PyMem_Free(interfaceDetailData);
                            return NULL;
                        }
                        PyDict_SetItem(volumes, key, val);
                    }
                }

            } else {
                debug("Failed to get volume name for volume mount point:\n");
                if (DEBUG) debug("%ws\n\n", format_last_error());
            }

            PyMem_Free(interfaceDetailData);
        }

    } //for

    SetupDiDestroyDeviceInfoList(hDevInfo);
    return volumes;

}

static PyObject *
winutil_get_usb_devices(PyObject *self, PyObject *args) {
	unsigned int j, buffersize;
	HDEVINFO hDevInfo;
	DWORD i; BOOL iterate = TRUE;
    PyObject *devices, *temp = (PyObject *)1;
    LPTSTR buffer;

	if (!PyArg_ParseTuple(args, "")) return NULL;

	devices = PyList_New(0);
	if (devices == NULL) {PyErr_NoMemory(); return NULL;}

	// Create a Device information set with all USB devices
    hDevInfo = create_device_info_set(NULL, L"USB", 0,
            DIGCF_PRESENT | DIGCF_ALLCLASSES);
    if (hDevInfo == INVALID_HANDLE_VALUE)
        return NULL;
    // Enumerate through the set
    for (i=0; iterate; i++) {
        buffer = get_registry_property(hDevInfo, i, SPDRP_HARDWAREID, &iterate);
        if (buffer == NULL) {
            PyErr_Print(); continue;
        }
        buffersize = wcslen(buffer);
        for (j = 0; j < buffersize; j++) buffer[j] = tolower(buffer[j]);
        temp = PyUnicode_FromWideChar(buffer, buffersize);
        PyMem_Free(buffer);
        if (temp == NULL) {
        	PyErr_NoMemory();
        	break;
        }
        PyList_Append(devices, temp);
    } //for
    if (temp == NULL) { Py_DECREF(devices); devices = NULL; }
    SetupDiDestroyDeviceInfoList(hDevInfo);
	return devices;
}


static PyObject *
winutil_is_usb_device_connected(PyObject *self, PyObject *args) {
	unsigned int vid, pid;
    HDEVINFO hDevInfo;
    DWORD i; BOOL iterate = TRUE;
    LPTSTR buffer;
    int found = FALSE;
    PyObject *ans;

    if (!PyArg_ParseTuple(args, "ii", &vid, &pid)) {
    	return NULL;
    }

    // Create a Device information set with all USB devices
    hDevInfo = create_device_info_set(NULL, L"USB", 0,
            DIGCF_PRESENT | DIGCF_ALLCLASSES);
    if (hDevInfo == INVALID_HANDLE_VALUE)
        return NULL;

    // Enumerate through the set
    for (i=0; iterate && !found; i++) {
        buffer = get_registry_property(hDevInfo, i, SPDRP_HARDWAREID, &iterate);
        if (buffer == NULL) {
            PyErr_Print(); continue;
        }
        found = check_device_id(buffer, vid, pid);
        PyMem_Free(buffer);
    } // for

    SetupDiDestroyDeviceInfoList(hDevInfo);
    ans = (found) ? Py_True : Py_False;
    Py_INCREF(ans);
    return ans;
}

static int
gettmarg(PyObject *args, struct tm *p)
{
	int y;
	memset((void *) p, '\0', sizeof(struct tm));

	if (!PyArg_Parse(args, "(iiiiiiiii)",
			 &y,
			 &p->tm_mon,
			 &p->tm_mday,
			 &p->tm_hour,
			 &p->tm_min,
			 &p->tm_sec,
			 &p->tm_wday,
			 &p->tm_yday,
			 &p->tm_isdst))
		return 0;
	if (y < 1900) {
		if (69 <= y && y <= 99)
			y += 1900;
		else if (0 <= y && y <= 68)
			y += 2000;
		else {
			PyErr_SetString(PyExc_ValueError,
					"year out of range");
			return 0;
		}
	}
	p->tm_year = y - 1900;
	p->tm_mon--;
	p->tm_wday = (p->tm_wday + 1) % 7;
	p->tm_yday--;
	return 1;
}

static PyObject *
winutil_strftime(PyObject *self, PyObject *args)
{
	PyObject *tup = NULL;
	struct tm buf;
	PyObject *format;
	const wchar_t *fmt;
	size_t fmtlen, buflen;
	wchar_t *outbuf = 0;
	size_t i;
    memset((void *) &buf, '\0', sizeof(buf));

	if (!PyArg_ParseTuple(args, "U|O:strftime", &format, &tup))
		return NULL;

	if (tup == NULL) {
		time_t tt = time(NULL);
		buf = *localtime(&tt);
	} else if (!gettmarg(tup, &buf))
		return NULL;

	if (buf.tm_mon == -1)
	    buf.tm_mon = 0;
	else if (buf.tm_mon < 0 || buf.tm_mon > 11) {
            PyErr_SetString(PyExc_ValueError, "month out of range");
                        return NULL;
        }
	if (buf.tm_mday == 0)
	    buf.tm_mday = 1;
	else if (buf.tm_mday < 0 || buf.tm_mday > 31) {
            PyErr_SetString(PyExc_ValueError, "day of month out of range");
                        return NULL;
        }
        if (buf.tm_hour < 0 || buf.tm_hour > 23) {
            PyErr_SetString(PyExc_ValueError, "hour out of range");
            return NULL;
        }
        if (buf.tm_min < 0 || buf.tm_min > 59) {
            PyErr_SetString(PyExc_ValueError, "minute out of range");
            return NULL;
        }
        if (buf.tm_sec < 0 || buf.tm_sec > 61) {
            PyErr_SetString(PyExc_ValueError, "seconds out of range");
            return NULL;
        }
        /* tm_wday does not need checking of its upper-bound since taking
        ``% 7`` in gettmarg() automatically restricts the range. */
        if (buf.tm_wday < 0) {
            PyErr_SetString(PyExc_ValueError, "day of week out of range");
            return NULL;
        }
	if (buf.tm_yday == -1)
	    buf.tm_yday = 0;
	else if (buf.tm_yday < 0 || buf.tm_yday > 365) {
            PyErr_SetString(PyExc_ValueError, "day of year out of range");
            return NULL;
        }
        if (buf.tm_isdst < -1 || buf.tm_isdst > 1) {
            PyErr_SetString(PyExc_ValueError,
                            "daylight savings flag out of range");
            return NULL;
        }

	/* Convert the unicode string to a wchar one */
    fmtlen = PyUnicode_GET_SIZE(format);
    fmt = (wchar_t *)PyMem_Malloc((fmtlen+1)*sizeof(wchar_t));
    if (fmt == NULL) return PyErr_NoMemory();
    i = PyUnicode_AsWideChar((PyUnicodeObject *)format, fmt, fmtlen);
    if (i < fmtlen) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to convert format string");
        PyMem_Free(fmt);
        return NULL;
    }

	for (i = 1024; ; i += i) {
		outbuf = (wchar_t *)PyMem_Malloc(i*sizeof(wchar_t));
		if (outbuf == NULL) {
			return PyErr_NoMemory();
		}
		buflen = wcsftime(outbuf, i, fmt, &buf);
		if (buflen > 0 || i >= 256 * fmtlen) {
			/* If the buffer is 256 times as long as the format,
			   it's probably not failing for lack of room!
			   More likely, the format yields an empty result,
			   e.g. an empty format, or %Z when the timezone
			   is unknown. */
			PyObject *ret;
			ret = PyUnicode_FromWideChar(outbuf, buflen);
			PyMem_Free(outbuf); PyMem_Free(fmt);
			return ret;
		}
		PyMem_Free(outbuf); PyMem_Free(fmt);
#if defined _MSC_VER && _MSC_VER >= 1400 && defined(__STDC_SECURE_LIB__)
		/* VisualStudio .NET 2005 does this properly */
		if (buflen == 0 && errno == EINVAL) {
			PyErr_SetString(PyExc_ValueError, "Invalid format string");
			return NULL;
        }
#endif
    }
}


static PyMethodDef WinutilMethods[] = {
    {"special_folder_path", winutil_folder_path, METH_VARARGS,
    "special_folder_path(csidl_id) -> path\n\n"
    		"Get paths to common system folders. "
    		"See windows documentation of SHGetFolderPath. "
    		"The paths are returned as unicode objects. csidl_id should be one "
    		"of the symbolic constants defined in this module. You can also OR "
    		"a symbolic constant with CSIDL_FLAG_CREATE to force the operating "
    		"system to create a folder if it does not exist."},

    {"argv", winutil_argv, METH_VARARGS,
    "argv() -> list of command line arguments\n\n"
    		"Get command line arguments as unicode objects. Note that the "
    		"first argument will be the path to the interpreter, *not* the "
    		"script being run. So to replace sys.argv, you should use "
    		"sys.argv[1:] = argv()[1:]."},

	{"is_usb_device_connected", winutil_is_usb_device_connected, METH_VARARGS,
    "is_usb_device_connected(vid, pid) -> bool\n\n"
    		"Check if the USB device identified by VendorID: vid (integer) and"
    		" ProductID: pid (integer) is currently connected."},

	{"get_usb_devices", winutil_get_usb_devices, METH_VARARGS,
	    "get_usb_devices() -> list of strings\n\n"
	    		"Return a list of the hardware IDs of all USB devices "
	    		"connected to the system."},

	{"get_mounted_volumes_for_usb_device", winutil_get_mounted_volumes_for_usb_device, METH_VARARGS,
		    "get_mounted_volumes_for_usb_device(vid, pid) -> dict\n\n"
		    		"Return a dictionary of volume_id:drive_letter for all"
		    		"volumes mounted on the system that belong to the"
		    		"usb device specified by vid (integer) and pid (integer)."},

	{"set_debug", winutil_set_debug, METH_VARARGS,
			"set_debug(bool)\n\nSet debugging mode."
	},

    {"strftime", winutil_strftime, METH_VARARGS,
        "strftime(format[, tuple]) -> string\n\
\n\
Convert a time tuple to a string according to a format specification.\n\
See the library reference manual for formatting codes. When the time tuple\n\
is not present, current time as returned by localtime() is used. format must\n\
be a unicode string. Returns unicode strings."
     },

    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initwinutil(void) {
    PyObject *m;
    m = Py_InitModule3("winutil", WinutilMethods,
    "Defines utility methods to interface with windows."
    );
    if (m == NULL) return;
    DriveError = PyErr_NewException("winutil.DriveError", NULL, NULL);

    PyModule_AddIntConstant(m, "CSIDL_ADMINTOOLS", CSIDL_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_APPDATA", CSIDL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_ADMINTOOLS", CSIDL_COMMON_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_APPDATA", CSIDL_COMMON_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_DOCUMENTS", CSIDL_COMMON_DOCUMENTS);
    PyModule_AddIntConstant(m, "CSIDL_COOKIES", CSIDL_COOKIES);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_CREATE", CSIDL_FLAG_CREATE);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_DONT_VERIFY", CSIDL_FLAG_DONT_VERIFY);
    PyModule_AddIntConstant(m, "CSIDL_HISTORY", CSIDL_HISTORY);
    PyModule_AddIntConstant(m, "CSIDL_INTERNET_CACHE", CSIDL_INTERNET_CACHE);
    PyModule_AddIntConstant(m, "CSIDL_LOCAL_APPDATA", CSIDL_LOCAL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_MYPICTURES", CSIDL_MYPICTURES);
    PyModule_AddIntConstant(m, "CSIDL_PERSONAL", CSIDL_PERSONAL);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES", CSIDL_PROGRAM_FILES);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES_COMMON", CSIDL_PROGRAM_FILES_COMMON);
    PyModule_AddIntConstant(m, "CSIDL_SYSTEM", CSIDL_SYSTEM);
    PyModule_AddIntConstant(m, "CSIDL_WINDOWS", CSIDL_WINDOWS);

}

