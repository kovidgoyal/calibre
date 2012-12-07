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

.. function:: internet_connected() -> Return True if there is an active
   internet connection.

*/


#define UNICODE
#include <Windows.h>
#include <Wininet.h>
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

static void console_out(LPCWSTR fmt, LPCWSTR arg) {
    char *bfmt, *barg;
    int sz;

    sz = WideCharToMultiByte(CP_UTF8, 0, fmt, -1, NULL, 0, NULL, NULL);
    bfmt = (char*)calloc(sz+1, sizeof(char));
    WideCharToMultiByte(CP_UTF8, 0, fmt, -1, bfmt, sz, NULL, NULL);

    sz = WideCharToMultiByte(CP_UTF8, 0, arg, -1, NULL, 0, NULL, NULL);
    barg = (char*)calloc(sz+1, sizeof(char));
    WideCharToMultiByte(CP_UTF8, 0, arg, -1, barg, sz, NULL, NULL);

    if (bfmt != NULL && barg != NULL) {
        printf(bfmt, barg);
        fflush(stdout);
        free(bfmt); free(barg);
    }
}

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
    int argc, i;
    if (!PyArg_ParseTuple(args, "")) return NULL;
    _argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (_argv == NULL) { PyErr_NoMemory(); return NULL; }
    argv = PyList_New(argc);
    if (argv != NULL) {
        for (i = 0; i < argc; i++) {
            v = PyUnicode_FromWideChar(_argv[i], wcslen(_argv[i]));
            if ( v == NULL) {
                Py_DECREF(argv); argv = NULL; PyErr_NoMemory(); break;
            }
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

static LPWSTR
get_registry_property(HDEVINFO hDevInfo, DWORD index, DWORD property, BOOL *iterate) {
    /* Get the property specified by `property` from the registry for the
     * device enumerated by `index` in the collection `hDevInfo`. `iterate`
     * will be set to `FALSE` if `index` points outside `hDevInfo`.
     * :return: A string allocated on the heap containing the property or
     *          `NULL` if an error occurred.
     */
    SP_DEVINFO_DATA DeviceInfoData;
    DWORD DataT;
    LPWSTR buffer = NULL;
    DWORD buffersize = 0;
    DeviceInfoData.cbSize = sizeof(SP_DEVINFO_DATA);

    if (!SetupDiEnumDeviceInfo(hDevInfo, index, &DeviceInfoData)) {
        *iterate = FALSE;
        return NULL;
    }

    while(!SetupDiGetDeviceRegistryPropertyW(
            hDevInfo,
            &DeviceInfoData,
            property,
            &DataT,
            (PBYTE)buffer,
            buffersize,
            &buffersize)) {
            if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
                if (buffer != NULL) { PyMem_Free(buffer); buffer = NULL; }
                buffer = (LPWSTR)PyMem_Malloc(2*buffersize); // Twice for bug in Win2k
            } else {
                if (buffer != NULL) { PyMem_Free(buffer); buffer = NULL; }
            	PyErr_SetFromWindowsErr(0);
                break;
            }
    } //while

    return buffer;
}

static BOOL                                                                                                                                                                           
check_device_id(LPWSTR buffer, unsigned int vid, unsigned int pid) {                                                                                                                  
    WCHAR xVid[9], dVid[9], xPid[9], dPid[9];                                                                                                                                         
    unsigned int j;                                                                                                                                                                   
    _snwprintf_s(xVid, 9, _TRUNCATE, L"vid_%4.4x", vid);
    _snwprintf_s(dVid, 9, _TRUNCATE, L"vid_%4.4d", vid);
    _snwprintf_s(xPid, 9, _TRUNCATE, L"pid_%4.4x", pid);
    _snwprintf_s(dPid, 9, _TRUNCATE, L"pid_%4.4d", pid);
                                                                                                                                                                                      
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


    for(nLoopIndex = 0; nLoopIndex < MAX_DRIVES; nLoopIndex++)
    {
        // if a drive is present (we cannot ignore the A and B drives as there
        // are people out there that think mapping devices to use those letters
        // is a good idea, sigh)
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
					wcscpy_s(g_drives[g_count].volume, BUFSIZE, volume);
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

static DEVINST 
GetDrivesDevInstByDeviceNumber(long DeviceNumber,
          UINT DriveType, LPWSTR szDosDeviceName)
{
    GUID *guid;
    HDEVINFO hDevInfo;
    DWORD dwIndex, dwBytesReturned;
    BOOL bRet, IsFloppy;
    BYTE Buf[1024];
    PSP_DEVICE_INTERFACE_DETAIL_DATA pspdidd;
    long res;
    HANDLE hDrive;
    STORAGE_DEVICE_NUMBER sdn;
    SP_DEVICE_INTERFACE_DATA         spdid;
    SP_DEVINFO_DATA                  spdd;
    DWORD                            dwSize;


    IsFloppy = (wcsstr(szDosDeviceName, L"\\Floppy") != NULL); // is there a better way?

    switch (DriveType) {
    case DRIVE_REMOVABLE:
        if ( IsFloppy ) {
        guid = (GUID*)&GUID_DEVINTERFACE_FLOPPY;
        } else {
        guid = (GUID*)&GUID_DEVINTERFACE_DISK;
        }
        break;
    case DRIVE_FIXED:
        guid = (GUID*)&GUID_DEVINTERFACE_DISK;
        break;
    case DRIVE_CDROM:
        guid = (GUID*)&GUID_DEVINTERFACE_CDROM;
        break;
    default:
        PyErr_SetString(PyExc_ValueError, "Invalid drive type");
        return 0;
    }

    // Get device interface info set handle
    // for all devices attached to system
    hDevInfo = SetupDiGetClassDevs(guid, NULL, NULL,
                        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

    if (hDevInfo == INVALID_HANDLE_VALUE)  {
        PyErr_SetString(PyExc_ValueError, "Invalid handle value");
        return 0;
    }

    // Retrieve a context structure for a device interface
    // of a device information set.
    dwIndex = 0;
    bRet = FALSE;

    
    pspdidd =  (PSP_DEVICE_INTERFACE_DETAIL_DATA)Buf;
    spdid.cbSize = sizeof(spdid);

    while ( TRUE )  {
        bRet = SetupDiEnumDeviceInterfaces(hDevInfo, NULL,
            guid, dwIndex, &spdid);
        if ( !bRet ) {
        break;
        }

        dwSize = 0;
        SetupDiGetDeviceInterfaceDetail(hDevInfo,
        &spdid, NULL, 0, &dwSize, NULL);

        if ( dwSize!=0 && dwSize<=sizeof(Buf) ) {
        pspdidd->cbSize = sizeof(*pspdidd); // 5 Bytes!

        ZeroMemory((PVOID)&spdd, sizeof(spdd));
        spdd.cbSize = sizeof(spdd);

        res =
            SetupDiGetDeviceInterfaceDetail(hDevInfo, &
                                            spdid, pspdidd,
                                            dwSize, &dwSize,
                                            &spdd);
        if ( res ) {
            hDrive = CreateFile(pspdidd->DevicePath,0,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
            if ( hDrive != INVALID_HANDLE_VALUE ) {
            dwBytesReturned = 0;
            res = DeviceIoControl(hDrive,
                            IOCTL_STORAGE_GET_DEVICE_NUMBER,
                            NULL, 0, &sdn, sizeof(sdn),
                            &dwBytesReturned, NULL);
            if ( res ) {
                if ( DeviceNumber == (long)sdn.DeviceNumber ) {
                CloseHandle(hDrive);
                SetupDiDestroyDeviceInfoList(hDevInfo);
                return spdd.DevInst;
                }
            }
            CloseHandle(hDrive);
            }
        }
        }
        dwIndex++;
    }

    SetupDiDestroyDeviceInfoList(hDevInfo);
    PyErr_SetString(PyExc_ValueError, "Invalid device number");

    return 0;
}



static BOOL
eject_drive_letter(WCHAR DriveLetter) {
    LPWSTR szRootPath = L"X:\\", 
           szDevicePath = L"X:", 
           szVolumeAccessPath = L"\\\\.\\X:";
    WCHAR  szDosDeviceName[MAX_PATH];
    long DeviceNumber, res, tries;
    HANDLE hVolume; 
    STORAGE_DEVICE_NUMBER sdn;
    DWORD dwBytesReturned;
    DEVINST DevInst;
    ULONG Status;
    ULONG ProblemNumber;
    UINT DriveType;
    PNP_VETO_TYPE VetoType;
    WCHAR VetoNameW[MAX_PATH];
    BOOL bSuccess;
    DEVINST DevInstParent;
    
    szRootPath[0] = DriveLetter;
    szDevicePath[0] = DriveLetter;
    szVolumeAccessPath[4] = DriveLetter;

    DeviceNumber = -1;

    hVolume = CreateFileW(szVolumeAccessPath, 0,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
    if (hVolume == INVALID_HANDLE_VALUE) {
        PyErr_SetFromWindowsErr(0);
        return FALSE;
    }

    dwBytesReturned = 0;
    res = DeviceIoControl(hVolume,
                        IOCTL_STORAGE_GET_DEVICE_NUMBER,
                        NULL, 0, &sdn, sizeof(sdn),
                        &dwBytesReturned, NULL);
    if ( res ) {
        DeviceNumber = sdn.DeviceNumber;
    }
    CloseHandle(hVolume);

    if ( DeviceNumber == -1 ) {
        PyErr_SetString(PyExc_ValueError, "Can't find drive number");
        return FALSE;
    }

    res = QueryDosDevice(szDevicePath, szDosDeviceName, MAX_PATH);
    if ( !res ) {
       PyErr_SetString(PyExc_ValueError, "Can't find dos device");
       return FALSE;
    }

    DriveType = GetDriveType(szRootPath);

    DevInst = GetDrivesDevInstByDeviceNumber(DeviceNumber,
                  DriveType, szDosDeviceName);
    if (DevInst == 0) return FALSE;

    DevInstParent = 0;
    Status = 0;
    ProblemNumber = 0;
    bSuccess = FALSE;

    res = CM_Get_Parent(&DevInstParent, DevInst, 0);

    for ( tries = 0; tries < 3; tries++ ) {
        VetoNameW[0] = 0;

        res = CM_Request_Device_EjectW(DevInstParent,
                &VetoType, VetoNameW, MAX_PATH, 0);

        bSuccess = (res==CR_SUCCESS &&
                            VetoType==PNP_VetoTypeUnknown);
        if ( bSuccess )  {
            break;
        }

        Sleep(500); // required to give the next tries a chance!
    }
    if (!bSuccess)  PyErr_SetString(PyExc_ValueError, "Failed to eject drive after three tries");
    return bSuccess;
}

static PyObject *
winutil_eject_drive(PyObject *self, PyObject *args) {
    char letter = '0';
    WCHAR DriveLetter = L'0';

    if (!PyArg_ParseTuple(args, "c", &letter)) return NULL;

    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, &letter, 1, &DriveLetter, 1) == 0) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }

    if (!eject_drive_letter(DriveLetter)) return NULL;
    Py_RETURN_NONE;
}


PSP_DEVICE_INTERFACE_DETAIL_DATA
get_device_ancestors(HDEVINFO hDevInfo, DWORD index, PyObject *candidates, BOOL *iterate, BOOL ddebug) {
    SP_DEVICE_INTERFACE_DATA            interfaceData;
    SP_DEVINFO_DATA						devInfoData;
    BOOL                                status;
    PSP_DEVICE_INTERFACE_DETAIL_DATA    interfaceDetailData;
    DWORD                               interfaceDetailDataSize,
                                        reqSize;
    DEVINST                             parent, pos;
    wchar_t                             temp[BUFSIZE];
    int                                 i;
    PyObject                            *devid;

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
    interfaceDetailData = (PSP_DEVICE_INTERFACE_DETAIL_DATA)PyMem_Malloc(interfaceDetailDataSize+50);
    if ( interfaceDetailData == NULL ) {
        PyErr_NoMemory();
        return NULL;
    }
    interfaceDetailData->cbSize = sizeof (SP_INTERFACE_DEVICE_DETAIL_DATA);
    devInfoData.cbSize = sizeof(SP_DEVINFO_DATA);

    status = SetupDiGetDeviceInterfaceDetail (
                  hDevInfo,                 // Interface Device info handle
                  &interfaceData,           // Interface data for the event class
                  interfaceDetailData,      // Interface detail data
                  interfaceDetailDataSize,  // Interface detail data size
                  &reqSize,                 // Buffer size required to get the detail data
                  &devInfoData);            // Interface device info
    if (ddebug) printf("Getting ancestors\n"); fflush(stdout);

    if ( status == FALSE ) {PyErr_SetFromWindowsErr(0); PyMem_Free(interfaceDetailData); return NULL;}

    pos = devInfoData.DevInst;

    for(i = 0; i < 10; i++) {
        // Get the device instance of parent.
        if (CM_Get_Parent(&parent, pos, 0) != CR_SUCCESS) break;
        if (CM_Get_Device_ID(parent, temp, BUFSIZE, 0) == CR_SUCCESS) {
            if (ddebug) console_out(L"device id: %s\n", temp);
            devid = PyUnicode_FromWideChar(temp, wcslen(temp));
            if (devid) {
                PyList_Append(candidates, devid);
                Py_DECREF(devid);
            }
        }
        pos = parent;
    }

    return interfaceDetailData;
}

static PyObject *
winutil_get_removable_drives(PyObject *self, PyObject *args) {
    HDEVINFO hDevInfo;
	BOOL  iterate = TRUE, ddebug = FALSE;
	PSP_DEVICE_INTERFACE_DETAIL_DATA interfaceDetailData;
    DWORD i;
    unsigned int j;
    size_t length;
    WCHAR volume[BUFSIZE];
    struct tagDrives g_drives[MAX_DRIVES];
    PyObject *volumes, *key, *candidates, *pdebug = Py_False, *temp;

    if (!PyArg_ParseTuple(args, "|O", &pdebug)) {
    	return NULL;
    }

    // Find all removable drives
    for (j = 0; j < MAX_DRIVES; j++) g_drives[j].letter = 0;
    if (!get_all_removable_disks(g_drives)) return NULL;

    volumes = PyDict_New();
    if (volumes == NULL) return PyErr_NoMemory();
    ddebug = PyObject_IsTrue(pdebug);

    hDevInfo = create_device_info_set((LPGUID)&GUID_DEVINTERFACE_VOLUME,
                            NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (hDevInfo == INVALID_HANDLE_VALUE) { Py_DECREF(volumes); return NULL; }

    // Enumerate through the set
    for (i=0; iterate; i++) {
        candidates = PyList_New(0);
        if (candidates == NULL) { Py_DECREF(volumes); return PyErr_NoMemory();}

        interfaceDetailData = get_device_ancestors(hDevInfo, i, candidates, &iterate, ddebug);
        if (interfaceDetailData == NULL) {
            PyErr_Print(); 
            Py_DECREF(candidates); candidates = NULL; 
            continue;
        }

        length = wcslen(interfaceDetailData->DevicePath);
        interfaceDetailData->DevicePath[length] = L'\\';
        interfaceDetailData->DevicePath[length+1] = 0;

        if (ddebug) console_out(L"Device path: %s\n", interfaceDetailData->DevicePath);
        // On Vista+ DevicePath contains the information we need.
        temp = PyUnicode_FromWideChar(interfaceDetailData->DevicePath, length);
        if (temp == NULL) return PyErr_NoMemory();
        PyList_Append(candidates, temp);
        Py_DECREF(temp);
        if(GetVolumeNameForVolumeMountPointW(interfaceDetailData->DevicePath, volume, BUFSIZE)) {
            if (ddebug) console_out(L"Volume: %s\n", volume);
            
            for(j = 0; j < MAX_DRIVES; j++) {
                if(g_drives[j].letter != 0 && wcscmp(g_drives[j].volume, volume)==0) {
                    if (ddebug) printf("Found drive: %c\n", (char)g_drives[j].letter); fflush(stdout);
                    key = PyBytes_FromFormat("%c", (char)g_drives[j].letter);
                    if (key == NULL) return PyErr_NoMemory();
                    PyDict_SetItem(volumes, key, candidates);
                    Py_DECREF(key); key = NULL;
                    break;
                }
            }

        }
        Py_XDECREF(candidates); candidates = NULL;
        PyMem_Free(interfaceDetailData);
    } //for

    SetupDiDestroyDeviceInfoList(hDevInfo);
    return volumes;
}

static PyObject *
winutil_get_usb_devices(PyObject *self, PyObject *args) {
	unsigned int j;
    size_t buffersize;
	HDEVINFO hDevInfo;
	DWORD i; BOOL iterate = TRUE;
    PyObject *devices, *temp = (PyObject *)1;
    LPWSTR buffer;
    BOOL ok = 1;

	if (!PyArg_ParseTuple(args, "")) return NULL;

	devices = PyList_New(0);
	if (devices == NULL) {PyErr_NoMemory(); return NULL;}

	// Create a Device information set with all USB devices
    hDevInfo = create_device_info_set(NULL, L"USB", 0,
            DIGCF_PRESENT | DIGCF_ALLCLASSES);
    if (hDevInfo == INVALID_HANDLE_VALUE) { 
        Py_DECREF(devices);
        return NULL;
    }
    // Enumerate through the set
    for (i=0; iterate; i++) {
        buffer = get_registry_property(hDevInfo, i, SPDRP_HARDWAREID, &iterate);
        if (buffer == NULL) {
            PyErr_Print(); continue;
        }
        buffersize = wcslen(buffer);
        for (j = 0; j < buffersize; j++) buffer[j] = towlower(buffer[j]);
        temp = PyUnicode_FromWideChar(buffer, buffersize);
        PyMem_Free(buffer);
        if (temp == NULL) {
        	PyErr_NoMemory();
            ok = 0;
        	break;
        }
        PyList_Append(devices, temp); Py_DECREF(temp); temp = NULL;
    } //for
    if (!ok) { Py_DECREF(devices); devices = NULL; }
    SetupDiDestroyDeviceInfoList(hDevInfo);
	return devices;
}


static PyObject *
winutil_is_usb_device_connected(PyObject *self, PyObject *args) {
	unsigned int vid, pid;
    HDEVINFO hDevInfo;
    DWORD i; BOOL iterate = TRUE;
    LPWSTR buffer;
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
winutil_internet_connected(PyObject *self, PyObject *args) {
    DWORD flags;
    BOOL ans = InternetGetConnectedState(&flags, 0);
    if (ans) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}


static PyObject *
winutil_strftime(PyObject *self, PyObject *args)
{
	PyObject *tup = NULL;
	struct tm buf;
	const char *_fmt;
	size_t fmtlen, buflen;
	wchar_t *outbuf = NULL, *fmt = NULL;
	size_t i;
    memset((void *) &buf, '\0', sizeof(buf));

	if (!PyArg_ParseTuple(args, "s|O:strftime", &_fmt, &tup))
		return NULL;

    if (mbstowcs_s(&fmtlen, NULL, 0, _fmt, strlen(_fmt)) != 0) {
        PyErr_SetString(PyExc_ValueError, "Failed to convert fmt to wchar");
        return NULL;
    }
    fmt = (wchar_t *)PyMem_Malloc((fmtlen+2)*sizeof(wchar_t));
    if (fmt == NULL) return PyErr_NoMemory();
    if (mbstowcs_s(&fmtlen, fmt, fmtlen+2, _fmt, strlen(_fmt)) != 0) {
        PyErr_SetString(PyExc_ValueError, "Failed to convert fmt to wchar");
        goto end;
    }

	if (tup == NULL) {
		time_t tt = time(NULL);
		if(localtime_s(&buf, &tt) != 0) {
            PyErr_SetString(PyExc_ValueError, "Failed to get localtime()");
            goto end;
        }
	} else if (!gettmarg(tup, &buf))
	    goto end;

	if (buf.tm_mon == -1)
	    buf.tm_mon = 0;
	else if (buf.tm_mon < 0 || buf.tm_mon > 11) {
            PyErr_SetString(PyExc_ValueError, "month out of range");
            goto end;
        }
	if (buf.tm_mday == 0)
	    buf.tm_mday = 1;
	else if (buf.tm_mday < 0 || buf.tm_mday > 31) {
            PyErr_SetString(PyExc_ValueError, "day of month out of range");
            goto end;
        }
        if (buf.tm_hour < 0 || buf.tm_hour > 23) {
            PyErr_SetString(PyExc_ValueError, "hour out of range");
            goto end;
        }
        if (buf.tm_min < 0 || buf.tm_min > 59) {
            PyErr_SetString(PyExc_ValueError, "minute out of range");
            goto end;
        }
        if (buf.tm_sec < 0 || buf.tm_sec > 61) {
            PyErr_SetString(PyExc_ValueError, "seconds out of range");
            goto end;
        }
        /* tm_wday does not need checking of its upper-bound since taking
        ``% 7`` in gettmarg() automatically restricts the range. */
        if (buf.tm_wday < 0) {
            PyErr_SetString(PyExc_ValueError, "day of week out of range");
            goto end;
        }
	if (buf.tm_yday == -1)
	    buf.tm_yday = 0;
	else if (buf.tm_yday < 0 || buf.tm_yday > 365) {
            PyErr_SetString(PyExc_ValueError, "day of year out of range");
            goto end;
        }
        if (buf.tm_isdst < -1 || buf.tm_isdst > 1) {
            PyErr_SetString(PyExc_ValueError,
                            "daylight savings flag out of range");
            goto end;
        }

	for (i = 5*fmtlen; ; i += i) {
		outbuf = (wchar_t *)PyMem_Malloc(i*sizeof(wchar_t));
		if (outbuf == NULL) {
			PyErr_NoMemory(); goto end;
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
		PyMem_Free(outbuf);
#if defined _MSC_VER && _MSC_VER >= 1400 && defined(__STDC_SECURE_LIB__)
		/* VisualStudio .NET 2005 does this properly */
		if (buflen == 0 && errno == EINVAL) {
			PyErr_SetString(PyExc_ValueError, "Invalid format string");
            goto end;
        }
#endif
    }
end:
    PyMem_Free(fmt); return NULL;
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

	{"get_removable_drives", winutil_get_removable_drives, METH_VARARGS,
    "get_removable_drives(debug=False) -> dict\n\n"
    		"Return mapping of all removable drives in the system. Maps drive letters "
    		"to a list of device id strings, atleast one of which will carry the information "
            "needed for device matching. On Vista+ it is always the last string in the list. "
            "Note that you should upper case all strings."},

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

	{"eject_drive", winutil_eject_drive, METH_VARARGS,
			"eject_drive(drive_letter)\n\nEject a drive. Raises an exception on failure."
	},

    {"internet_connected", winutil_internet_connected, METH_VARARGS,
        "internet_connected()\n\nReturn True if there is an active internet connection"
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
    PyModule_AddIntConstant(m, "CSIDL_FONTS", CSIDL_FONTS);
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

