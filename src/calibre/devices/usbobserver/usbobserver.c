/*    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
 *    This program is free software; you can redistribute it and/or modify
 *    it under the terms of the GNU General Public License as published by
 *    the Free Software Foundation; either version 2 of the License, or
 *    (at your option) any later version.
 *
 *    This program is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    GNU General Public License for more details.
 *
 *    You should have received a copy of the GNU General Public License along
 *    with this program; if not, write to the Free Software Foundation, Inc.,
 *    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * Python extension to scan the system for USB devices on OS X machines.
 * To use
 * >>> import usbobserver
 * >>> usbobserver.get_devices()
 */

#define _DARWIN_USE_64_BIT_INODE
#define PY_SSIZE_T_CLEAN

#include <Python.h>

#include <stdio.h>

#include <CoreFoundation/CFNumber.h>
#include <CoreServices/CoreServices.h>
#include <IOKit/usb/IOUSBLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/storage/IOMedia.h>
#include <IOKit/IOBSD.h>
#include <IOKit/usb/USBSpec.h>

#include <mach/mach.h>
#include <sys/param.h>
#include <paths.h>
#include <sys/ucred.h>
#include <sys/mount.h>

#ifndef kUSBVendorString
#define kUSBVendorString "USB Vendor Name"
#endif

#ifndef kUSBProductString
#define kUSBProductString "USB Product Name"
#endif

#ifndef kUSBSerialNumberString
#define kUSBSerialNumberString "USB Serial Number"
#endif

#define NUKE(x) Py_XDECREF(x); x = NULL;


static PyObject*
usbobserver_get_iokit_string_property(io_service_t dev, CFStringRef prop) {
    CFTypeRef PropRef;
    char buf[500];

    PropRef = IORegistryEntryCreateCFProperty(dev, prop, kCFAllocatorDefault, 0);
    if (PropRef) {
        if(!CFStringGetCString(PropRef, buf, 500, kCFStringEncodingUTF8)) buf[0] = '\0';
        CFRelease(PropRef);
    } else buf[0] = '\0';

    return PyUnicode_DecodeUTF8(buf, strlen(buf), "replace");
}

static PyObject*
usbobserver_get_iokit_number_property(io_service_t dev, CFStringRef prop) {
    CFTypeRef PropRef;
    long val = 0;

    PropRef = IORegistryEntryCreateCFProperty(dev, prop, kCFAllocatorDefault, 0);
    if (PropRef) {
        CFNumberGetValue((CFNumberRef)PropRef, kCFNumberLongType, &val);
        CFRelease(PropRef);
    }

    return PyLong_FromLong(val);
}


static PyObject *
usbobserver_get_usb_devices(PyObject *self, PyObject *args) {

    CFMutableDictionaryRef matchingDict;
    kern_return_t kr;
    PyObject *devices, *device;
    io_service_t usbDevice;
    PyObject *vendor, *product, *bcd;
    PyObject *manufacturer, *productn, *serial;



    //Set up matching dictionary for class IOUSBDevice and its subclasses
    matchingDict = IOServiceMatching(kIOUSBDeviceClassName);
    if (!matchingDict) {
        PyErr_SetString(PyExc_RuntimeError, "Couldn't create a USB matching dictionary");
        return NULL;
    }

    io_iterator_t iter;
    kr = IOServiceGetMatchingServices(kIOMainPortDefault, matchingDict, &iter);
    if (KERN_SUCCESS != kr) {
            printf("IOServiceGetMatchingServices returned 0x%08x\n", kr);
            PyErr_SetString(PyExc_RuntimeError, "Could not run IO Matching");
            return NULL;
    }

    devices = PyList_New(0);
    if (devices == NULL) {
        PyErr_NoMemory();
        return NULL;
    }


    while ((usbDevice = IOIteratorNext(iter))) {

        vendor = usbobserver_get_iokit_number_property(usbDevice, CFSTR(kUSBVendorID));
        product = usbobserver_get_iokit_number_property(usbDevice, CFSTR(kUSBProductID));
        bcd = usbobserver_get_iokit_number_property(usbDevice, CFSTR(kUSBDeviceReleaseNumber));
        manufacturer = usbobserver_get_iokit_string_property(usbDevice, CFSTR(kUSBVendorString));
        productn = usbobserver_get_iokit_string_property(usbDevice, CFSTR(kUSBProductString));
        serial = usbobserver_get_iokit_string_property(usbDevice, CFSTR(kUSBSerialNumberString));
        if (usbDevice) IOObjectRelease(usbDevice);

        if (vendor != NULL && product != NULL && bcd != NULL) {

            if (manufacturer == NULL) { manufacturer = Py_None; Py_INCREF(Py_None); }
            if (productn == NULL) { productn = Py_None; Py_INCREF(Py_None); }
            if (serial == NULL) { serial = Py_None; Py_INCREF(Py_None); }

            device = Py_BuildValue("(OOOOOO)", vendor, product, bcd, manufacturer, productn, serial);
            if (device != NULL) {
                PyList_Append(devices, device);
                Py_DECREF(device);
            }
        }

        NUKE(vendor); NUKE(product); NUKE(bcd); NUKE(manufacturer);
        NUKE(productn); NUKE(serial);
    }

    if (iter) IOObjectRelease(iter);

    return devices;
}

static PyObject*
usbobserver_get_bsd_path(io_object_t dev) {
    char cpath[ MAXPATHLEN ];
    CFTypeRef PropRef;
    size_t dev_path_length;

    cpath[0] = '\0';
    PropRef = IORegistryEntryCreateCFProperty(dev, CFSTR(kIOBSDNameKey), kCFAllocatorDefault, 0);
    if (!PropRef) return NULL;
    strcpy(cpath, _PATH_DEV);
    dev_path_length = strlen(cpath);

    if (!CFStringGetCString(PropRef,
                        cpath + dev_path_length,
                        MAXPATHLEN - dev_path_length,
                        kCFStringEncodingUTF8)) return NULL;

    return PyUnicode_DecodeUTF8(cpath, strlen(cpath), "replace");

}

static PyObject*
usbobserver_find_prop(io_registry_entry_t e, CFStringRef key, int is_string )
{
    char buf[500]; long val = 0;
    PyObject *ans;
    IOOptionBits bits = kIORegistryIterateRecursively | kIORegistryIterateParents;
    CFTypeRef PropRef = IORegistryEntrySearchCFProperty( e, kIOServicePlane, key, NULL, bits );

    if (!PropRef) return NULL;
    buf[0] = '\0';

    if(is_string) {
        CFStringGetCString(PropRef, buf, 500, kCFStringEncodingUTF8);
        ans = PyUnicode_DecodeUTF8(buf, strlen(buf), "replace");
    } else {
        CFNumberGetValue((CFNumberRef)PropRef, kCFNumberLongType, &val);
        ans = PyLong_FromLong(val);
    }

    CFRelease(PropRef);
    return ans;
}

static PyObject*
usbobserver_get_usb_drives(PyObject *self, PyObject *args) {
    CFMutableDictionaryRef matchingDict;
    kern_return_t kr = KERN_FAILURE;
    io_iterator_t iter;
    io_object_t        next;
    PyObject *ans = NULL, *bsd_path = NULL, *t = NULL, *vid, *pid, *bcd, *manufacturer, *product, *serial;

    //Set up matching dictionary for class IOMedia and its subclasses
    matchingDict = IOServiceMatching(kIOMediaClass);
    if (!matchingDict) {
        PyErr_SetString(PyExc_RuntimeError, "Couldn't create a Media matching dictionary");
        return NULL;
    }
    // Only want writable and ejectable leaf nodes
    CFDictionarySetValue(matchingDict, CFSTR(kIOMediaWritableKey), kCFBooleanTrue);
    CFDictionarySetValue(matchingDict, CFSTR(kIOMediaLeafKey), kCFBooleanTrue);
    CFDictionarySetValue(matchingDict, CFSTR(kIOMediaEjectableKey), kCFBooleanTrue);

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    kr = IOServiceGetMatchingServices(kIOMainPortDefault, matchingDict, &iter);
    if (KERN_SUCCESS != kr) {
            printf("IOServiceGetMatchingServices returned 0x%08x\n", kr);
            PyErr_SetString(PyExc_RuntimeError, "Could not run IO Matching");
            return NULL;
    }

    while ((next = IOIteratorNext(iter))) {
        bsd_path = usbobserver_get_bsd_path(next);
        vid = usbobserver_find_prop(next, CFSTR(kUSBVendorID), 0);
        pid = usbobserver_find_prop(next, CFSTR(kUSBProductID), 0);
        bcd = usbobserver_find_prop(next, CFSTR(kUSBDeviceReleaseNumber), 0);
        manufacturer = usbobserver_find_prop(next, CFSTR(kUSBVendorString), 1);
        product = usbobserver_find_prop(next, CFSTR(kUSBProductString), 1);
        serial = usbobserver_find_prop(next, CFSTR(kUSBSerialNumberString), 1);

        IOObjectRelease(next);

        if (bsd_path != NULL && vid != NULL && pid != NULL && bcd != NULL) {
            if (manufacturer == NULL) { manufacturer = Py_None; Py_INCREF(Py_None); }
            if (product == NULL) { product = Py_None; Py_INCREF(Py_None); }
            if (serial == NULL) { serial = Py_None; Py_INCREF(Py_None); }

            t = Py_BuildValue("(OOOOOOO)", bsd_path, vid, pid, bcd, manufacturer, product, serial);
            if (t != NULL) {
                PyList_Append(ans, t);
                Py_DECREF(t); t = NULL;
            }
        }
        NUKE(bsd_path); NUKE(vid); NUKE(pid); NUKE(bcd);
        NUKE(manufacturer); NUKE(product); NUKE(serial);
    }

    if (iter) IOObjectRelease(iter);

    return ans;
}

typedef struct statfs fsstat;

static PyObject*
usbobserver_get_mounted_filesystems(PyObject *self, PyObject *args) {
    fsstat *buf = NULL;
    int num, i;
    PyObject *ans = NULL, *val;

    num = getfsstat(NULL, 0, MNT_NOWAIT);
    if (num == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
	num += 10;  // In case the number of volumes has increased
    buf = PyMem_New(fsstat, num);
    if (buf == NULL) return PyErr_NoMemory();

    num = getfsstat(buf, num*sizeof(fsstat), MNT_NOWAIT);
    if (num == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
		goto end;
    }

    ans = PyDict_New();
	if (ans == NULL) { goto end; }

    for (i = 0 ; i < num; i++) {
        val = PyUnicode_FromString(buf[i].f_mntonname);
		if (!val) {
            PyErr_Clear();
            val = PyUnicode_DecodeLocale(buf[i].f_mntonname, "surrogateescape");
            if (!val) { NUKE(ans); goto end; }
        }
		if (PyDict_SetItemString(ans, buf[i].f_mntfromname, val) != 0) { NUKE(ans); NUKE(val); goto end; }
        NUKE(val);
    }

end:
    PyMem_Del(buf);

    return ans;

}

static PyObject*
usbobserver_user_locale(PyObject *self, PyObject *args) {
    	CFStringRef id = NULL;
        CFLocaleRef loc = NULL;
        char buf[512] = {0};
        PyObject *ans = NULL;
        int ok = 0;

        loc = CFLocaleCopyCurrent();
        if (loc) {
            id = CFLocaleGetIdentifier(loc);
            if (id && CFStringGetCString(id, buf, 512, kCFStringEncodingUTF8)) {
                ok = 1;
                ans = PyUnicode_FromString(buf);
            }
        }

        if (loc) CFRelease(loc);
        if (ok) return ans;
        Py_RETURN_NONE;
}

static PyObject*
usbobserver_date_fmt(PyObject *self, PyObject *args) {
    	CFStringRef fmt = NULL;
        CFLocaleRef loc = NULL;
        CFDateFormatterRef formatter = NULL;
        char buf[512] = {0};
        PyObject *ans = NULL;
        int ok = 0;

        loc = CFLocaleCopyCurrent();
        if (loc) {
            formatter = CFDateFormatterCreate(kCFAllocatorDefault, loc, kCFDateFormatterShortStyle, kCFDateFormatterNoStyle);
            if (formatter) {
                fmt = CFDateFormatterGetFormat(formatter);
                if (fmt && CFStringGetCString(fmt, buf, 512, kCFStringEncodingUTF8)) {
                    ok = 1;
                    ans = PyUnicode_FromString(buf);
                }
            }
        }
        if (formatter) CFRelease(formatter);
        if (loc) CFRelease(loc);
        if (ok) return ans;
        Py_RETURN_NONE;
}

static int
usbobserver_has_mtp_interface(io_service_t usb_device) {
    io_iterator_t iter = 0;
    kern_return_t kr = KERN_FAILURE;
    io_registry_entry_t entry = 0;
    CFTypeRef prop = NULL;
    int ans = 0, found = 0;
    char buf[512] = {0};

    kr = IORegistryEntryCreateIterator(usb_device, kIOServicePlane, kIORegistryIterateRecursively, &iter);
    if (KERN_SUCCESS != kr) return 0;

    while (!found && (entry = IOIteratorNext(iter))) {
        prop = IORegistryEntryCreateCFProperty(entry, CFSTR("USB Interface Name"), kCFAllocatorDefault, 0);
        buf[0] = 0;
        if (prop) {
            if (!CFStringGetCString(prop, buf, 512, kCFStringEncodingUTF8)) buf[0] = 0;
            if (strncmp(buf, "MTP", 3) == 0) { found = 1; ans = 1; }
            CFRelease(prop); prop = NULL;
        }
        IOObjectRelease(entry);
    }

    IOObjectRelease(iter);
    return ans;
}

static PyObject*
usbobserver_is_mtp(PyObject *self, PyObject * args) {
    Py_ssize_t serial_sz = 0;
    long vendor_id = 0, product_id = 0, bcd = 0;
    char *serial = NULL, buf[500] = {0};
    CFNumberRef num = NULL;
    CFMutableDictionaryRef matching_dict = NULL;
    CFTypeRef prop = NULL;
    PyObject *ans = NULL;
    io_iterator_t iter = 0;
    kern_return_t kr = KERN_FAILURE;
    io_service_t usb_device = 0;

    if (!PyArg_ParseTuple(args, "iiis#", &vendor_id, &product_id, &bcd, &serial, &serial_sz)) return NULL;

    matching_dict = IOServiceMatching(kIOUSBDeviceClassName);
    if (!matching_dict) {
        PyErr_SetString(PyExc_RuntimeError, "Couldn't create a USB device matching dictionary");
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    num = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &vendor_id);
    if (num == NULL) { PyErr_NoMemory(); goto end; }
    CFDictionarySetValue(matching_dict, CFSTR(kUSBVendorID), num);
    CFRelease(num); num = NULL;

    num = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &product_id);
    if (num == NULL) { PyErr_NoMemory(); goto end; }
    CFDictionarySetValue(matching_dict, CFSTR(kUSBProductID), num);
    CFRelease(num); num = NULL;

    num = CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, &bcd);
    if (num == NULL) { PyErr_NoMemory(); goto end; }
    CFDictionarySetValue(matching_dict, CFSTR(kUSBDeviceReleaseNumber), num);
    CFRelease(num); num = NULL;

    kr = IOServiceGetMatchingServices(kIOMainPortDefault, matching_dict, &iter);
    matching_dict = NULL;
    if (KERN_SUCCESS != kr) {
        PyErr_Format(PyExc_RuntimeError, "IOServiceGetMatchingServices returned 0x%x", kr);
        goto end;
    }

    while (ans == NULL && (usb_device = IOIteratorNext(iter))) {
        prop = IORegistryEntryCreateCFProperty(usb_device, CFSTR(kUSBSerialNumberString), kCFAllocatorDefault, 0);
        buf[0] = 0;
        if (prop) {
            if (!CFStringGetCString(prop, buf, 500, kCFStringEncodingUTF8)) buf[0] = 0;
            CFRelease(prop); prop = NULL;
        }
        if (strncmp(serial, buf, MIN(500, serial_sz)) == 0) {
            // We have found the device now check for an MTP interface
            ans = (usbobserver_has_mtp_interface(usb_device)) ? Py_True : Py_False;
        }

        IOObjectRelease(usb_device);
    }
    if (ans == NULL) ans = Py_None; // device not found
end:
    Py_END_ALLOW_THREADS
    if (matching_dict) CFRelease(matching_dict);
    if (num) CFRelease(num);
    if (iter) IOObjectRelease(iter);
    Py_XINCREF(ans);
    return ans;
}

static char usbobserver_doc[] = "USB interface glue for OSX.";

static PyMethodDef usbobserver_methods[] = {
    {"get_usb_devices", usbobserver_get_usb_devices, METH_VARARGS,
     "Get list of connected USB devices. Returns a list of tuples. Each tuple is of the form (vendor_id, product_id, bcd, manufacturer, product, serial number)."
    },
    {"get_usb_drives", usbobserver_get_usb_drives, METH_VARARGS,
     "Get list of mounted drives. Returns a list of tuples, each of the form (name, bsd_path)."
    },
    {"get_mounted_filesystems", usbobserver_get_mounted_filesystems, METH_VARARGS,
     "Get mapping of mounted filesystems. Mapping is from BSD name to mount point."
    },
    {"user_locale", usbobserver_user_locale, METH_VARARGS,
     "user_locale() -> The name of the current user's locale or None if an error occurred"
    },
    {"date_format", usbobserver_date_fmt, METH_VARARGS,
     "date_format() -> The (short) date format used by the user's current locale"
    },
    {"is_mtp_device", usbobserver_is_mtp, METH_VARARGS,
     "is_mtp_device(vendor_id, product_id, bcd, serial) -> Return True if the specified device has an MTP interface"
    },

    {NULL, NULL, 0, NULL}
};
static int
exec_module(PyObject *module) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "usbobserver",
    .m_doc      = usbobserver_doc,
    .m_methods  = usbobserver_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_usbobserver(void) { return PyModuleDef_Init(&module_def); }
