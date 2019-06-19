/*
 * eject.c
 * Copyright (C) 2013 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "Windows.h"
#include <stdio.h>
#include <wchar.h>
#include <winioctl.h>
#include <setupapi.h>
#include <devguid.h>
#include <cfgmgr32.h>

#define BUFSIZE 4096
#define LOCK_TIMEOUT        10000       // 10 Seconds
#define LOCK_RETRIES        20

#define BOOL2STR(x) ((x) ? L"True" : L"False")

// Error handling {{{

static void show_error(LPCWSTR msg) {
    MessageBeep(MB_ICONERROR);
    MessageBoxW(NULL, msg, L"Error", MB_OK|MB_ICONERROR);
}

static void show_detailed_error(LPCWSTR preamble, LPCWSTR msg, int code) {
    LPWSTR buf;
    buf = (LPWSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(WCHAR)*
            (wcslen(msg) + wcslen(preamble) + 80));

    _snwprintf_s(buf, 
        LocalSize(buf) / sizeof(WCHAR), _TRUNCATE,
        L"%s\r\n  %s (Error Code: %d)\r\n",
        preamble, msg, code);

    show_error(buf);
    LocalFree(buf);
}

static void print_detailed_error(LPCWSTR preamble, LPCWSTR msg, int code) {
    fwprintf_s(stderr, L"%s\r\n %s (Error Code: %d)\r\n", preamble, msg, code);
    fflush(stderr);
}

static void show_last_error_crt(LPCWSTR preamble) {
    WCHAR buf[BUFSIZE];
    int err = 0;

    _get_errno(&err);
    _wcserror_s(buf, BUFSIZE, err);
    show_detailed_error(preamble, buf, err);
}

static void show_last_error(LPCWSTR preamble) {
    WCHAR *msg = NULL;
    DWORD dw = GetLastError(); 

    FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | 
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&msg,
        0, NULL );

    show_detailed_error(preamble, msg, (int)dw);
}

static void print_last_error(LPCWSTR preamble) {
    WCHAR *msg = NULL;
    DWORD dw = GetLastError(); 

    FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | 
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&msg,
        0, NULL );

    print_detailed_error(preamble, msg, (int)dw);
}

// }}}
 
static void print_help() {
    fwprintf_s(stderr, L"Usage: calibre-eject.exe drive-letter1 [drive-letter2 drive-letter3 ...]");
}

static LPWSTR root_path = L"X:\\", device_path = L"X:", volume_access_path = L"\\\\.\\X:";
static wchar_t dos_device_name[MAX_PATH];
static UINT drive_type = 0;
static long device_number = -1;
static DEVINST dev_inst = 0, dev_inst_parent = 0;

// Unmount and eject volumes (drives) {{{
static HANDLE open_volume(wchar_t drive_letter) {
    DWORD access_flags;

    switch(drive_type) {
        case DRIVE_REMOVABLE:
            access_flags = GENERIC_READ | GENERIC_WRITE;
            break;
        case DRIVE_CDROM:
            access_flags = GENERIC_READ;
            break;
        default:
            fwprintf_s(stderr, L"Cannot eject %c: Drive type is incorrect.\r\n", drive_letter);
            fflush(stderr);
            return INVALID_HANDLE_VALUE;
    }

    return CreateFileW(volume_access_path, access_flags,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
}

static BOOL lock_volume(HANDLE volume) {
    DWORD bytes_returned;
    DWORD sleep_amount = LOCK_TIMEOUT / LOCK_RETRIES;
    int try_count;

    // Do this in a loop until a timeout period has expired
    for (try_count = 0; try_count < LOCK_RETRIES; try_count++) {
        if (DeviceIoControl(volume,
                            FSCTL_LOCK_VOLUME,
                            NULL, 0,
                            NULL, 0,
                            &bytes_returned,
                            NULL))
            return TRUE;

        Sleep(sleep_amount);
    }

    return FALSE;
}

static BOOL dismount_volume(HANDLE volume) {
    DWORD bytes_returned;

    return DeviceIoControl( volume,
                            FSCTL_DISMOUNT_VOLUME,
                            NULL, 0,
                            NULL, 0,
                            &bytes_returned,
                            NULL);
}

static BOOL disable_prevent_removal_of_volume(HANDLE volume) {
    DWORD bytes_returned;
    PREVENT_MEDIA_REMOVAL PMRBuffer;

    PMRBuffer.PreventMediaRemoval = FALSE;

    return DeviceIoControl( volume,
                            IOCTL_STORAGE_MEDIA_REMOVAL,
                            &PMRBuffer, sizeof(PREVENT_MEDIA_REMOVAL),
                            NULL, 0,
                            &bytes_returned,
                            NULL);
}

static BOOL auto_eject_volume(HANDLE volume) {
    DWORD bytes_returned;

    return DeviceIoControl( volume,
                            IOCTL_STORAGE_EJECT_MEDIA,
                            NULL, 0,
                            NULL, 0,
                            &bytes_returned,
                            NULL);
}

static BOOL unmount_drive(wchar_t drive_letter, BOOL *remove_safely, BOOL *auto_eject) {
    // Unmount the drive identified by drive_letter. Code adapted from:
    // http://support.microsoft.com/kb/165721
    HANDLE volume;
    *remove_safely = FALSE; *auto_eject = FALSE;

    volume = open_volume(drive_letter);
    if (volume == INVALID_HANDLE_VALUE) return FALSE;

    // Lock and dismount the volume.
    if (lock_volume(volume) && dismount_volume(volume)) {
        *remove_safely = TRUE;

        // Set prevent removal to false and eject the volume.
        if (disable_prevent_removal_of_volume(volume) && auto_eject_volume(volume))
            *auto_eject = TRUE;
    }
    CloseHandle(volume);
    return TRUE;

}
// }}}

// Eject USB device {{{
static void get_device_number(wchar_t drive_letter) {
    HANDLE volume;
    DWORD bytes_returned = 0;
    STORAGE_DEVICE_NUMBER sdn;

    volume = CreateFileW(volume_access_path, 0,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
    if (volume == INVALID_HANDLE_VALUE) {
        print_last_error(L"Failed to open volume while getting device number");
        return;
    }

    if (DeviceIoControl(volume,
                        IOCTL_STORAGE_GET_DEVICE_NUMBER,
                        NULL, 0, &sdn, sizeof(sdn),
                        &bytes_returned, NULL)) 
        device_number = sdn.DeviceNumber;
    CloseHandle(volume);
}

static DEVINST get_dev_inst_by_device_number(long device_number, UINT drive_type, LPWSTR dos_device_name) {
    GUID *guid;
    HDEVINFO dev_info;
    DWORD index, bytes_returned;
    BOOL bRet, is_floppy;
    BYTE Buf[1024];
    PSP_DEVICE_INTERFACE_DETAIL_DATA pspdidd;
    long res;
    HANDLE drive;
    STORAGE_DEVICE_NUMBER sdn;
    SP_DEVICE_INTERFACE_DATA spdid;
    SP_DEVINFO_DATA spdd;
    DWORD size;

    is_floppy = (wcsstr(dos_device_name, L"\\Floppy") != NULL); // is there a better way?

    switch (drive_type) {
        case DRIVE_REMOVABLE:
            guid = ( (is_floppy) ? (GUID*)&GUID_DEVINTERFACE_FLOPPY : (GUID*)&GUID_DEVINTERFACE_DISK );
            break;
        case DRIVE_FIXED:
            guid = (GUID*)&GUID_DEVINTERFACE_DISK;
            break;
        case DRIVE_CDROM:
            guid = (GUID*)&GUID_DEVINTERFACE_CDROM;
            break;
        default:
            fwprintf_s(stderr, L"Invalid drive type at line: %d\r\n", __LINE__);
            fflush(stderr);
            return 0;
    }

    // Get device interface info set handle
    // for all devices attached to system
    dev_info = SetupDiGetClassDevs(guid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

    if (dev_info == INVALID_HANDLE_VALUE)  {
        fwprintf_s(stderr, L"Failed to setup class devs at line: %d\r\n", __LINE__);
        fflush(stderr);
        return 0;
    }

    // Retrieve a context structure for a device interface
    // of a device information set.
    index = 0;
    bRet = FALSE;

    pspdidd =  (PSP_DEVICE_INTERFACE_DETAIL_DATA)Buf;
    spdid.cbSize = sizeof(spdid);

    while ( TRUE )  {
        bRet = SetupDiEnumDeviceInterfaces(dev_info, NULL,
            guid, index, &spdid);
        if ( !bRet )  break;

        size = 0;
        SetupDiGetDeviceInterfaceDetail(dev_info,
        &spdid, NULL, 0, &size, NULL);

        if ( size!=0 && size<=sizeof(Buf) ) {
        pspdidd->cbSize = sizeof(*pspdidd); // 5 Bytes!

        ZeroMemory((PVOID)&spdd, sizeof(spdd));
        spdd.cbSize = sizeof(spdd);

        res = SetupDiGetDeviceInterfaceDetail(dev_info, &spdid, pspdidd, size, &size, &spdd);
        if ( res ) {
            drive = CreateFile(pspdidd->DevicePath,0,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
            if ( drive != INVALID_HANDLE_VALUE ) {
            bytes_returned = 0;
            res = DeviceIoControl(drive,
                            IOCTL_STORAGE_GET_DEVICE_NUMBER,
                            NULL, 0, &sdn, sizeof(sdn),
                            &bytes_returned, NULL);
            if ( res ) {
                if ( device_number == (long)sdn.DeviceNumber ) {
                CloseHandle(drive);
                SetupDiDestroyDeviceInfoList(dev_info);
                return spdd.DevInst;
                }
            }
            CloseHandle(drive);
            }
        }
        }
        index++;
    }

    SetupDiDestroyDeviceInfoList(dev_info);
    fwprintf_s(stderr, L"Invalid device number at line: %d\r\n", __LINE__);
    fflush(stderr);

    return 0;
}


static void get_parent_device(wchar_t drive_letter) {
    get_device_number(drive_letter);
    if (device_number == -1) return;
    if (QueryDosDeviceW(device_path, dos_device_name, MAX_PATH) == 0) {
        print_last_error(L"Failed to query DOS device name");
        return;
    }

    dev_inst = get_dev_inst_by_device_number(device_number,
                  drive_type, dos_device_name);
    if (dev_inst == 0) {
        fwprintf_s(stderr, L"Failed to get device by device number");
        fflush(stderr);
        return;
    }
    if (CM_Get_Parent(&dev_inst_parent, dev_inst, 0) != CR_SUCCESS) {
        fwprintf_s(stderr, L"Failed to get device parent from CM");
        fflush(stderr);
        return;
    }
}

static int eject_device() {
    int tries;
    CONFIGRET res;
    PNP_VETO_TYPE VetoType;
    WCHAR VetoNameW[MAX_PATH];
    BOOL success;

    for ( tries = 0; tries < 3; tries++ ) {
        VetoNameW[0] = 0;

        res = CM_Request_Device_EjectW(dev_inst_parent,
                &VetoType, VetoNameW, MAX_PATH, 0);

        success = (res==CR_SUCCESS &&
                            VetoType==PNP_VetoTypeUnknown);
        if ( success )  {
            break;
        }

        Sleep(500); // required to give the next tries a chance!
    }
    if (!success) {
        fwprintf_s(stderr, L"CM_Request_Device_Eject failed after three tries\r\n");
        fflush(stderr);
    }
        
    return (success) ? 0 : 1;
}

// }}}

int wmain(int argc, wchar_t *argv[ ]) {
    int i = 0;
    wchar_t drive_letter;
    BOOL remove_safely, auto_eject;

    // Validate command line arguments
    if (argc < 2) { print_help(); return 1; }
    for (i = 1; i < argc; i++) {
        if (wcsnlen_s(argv[i], 2) != 1) { print_help(); return 1; }
    }

    // Unmount all mounted volumes and eject volume media
    for (i = 1; i < argc; i++) {
        drive_letter = *argv[i];
        root_path[0] = drive_letter;
        device_path[0] = drive_letter;
        volume_access_path[4] = drive_letter;
        drive_type = GetDriveTypeW(root_path);
        if (i == 1 && device_number == -1) {
            get_parent_device(drive_letter);
        }
        if (device_number != -1) {
            unmount_drive(drive_letter, &remove_safely, &auto_eject);
            fwprintf_s(stdout, L"Unmounting: %c: Remove safely: %s Media Ejected: %s\r\n",
                    drive_letter, BOOL2STR(remove_safely), BOOL2STR(auto_eject));
            fflush(stdout);
        }
    }

    // Eject the parent USB device
    if (device_number == -1) {
        fwprintf_s(stderr, L"Cannot eject, failed to get device number\r\n");
        fflush(stderr);
        return 1;
    }

    if (dev_inst_parent == 0) {
        fwprintf_s(stderr, L"Cannot eject, failed to get device parent\r\n");
        fflush(stderr);
        return 1;
    }

    return eject_device();
}


