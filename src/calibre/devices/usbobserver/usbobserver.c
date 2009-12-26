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


#include <Python.h>

#include <stdio.h>

#include <IOKit/usb/IOUSBLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>

CFStringRef USB_PROPS[3] = { CFSTR("USB Vendor Name"), CFSTR("USB Product Name"), CFSTR("USB Serial Number") };

static PyObject*
get_iokit_string_property(io_service_t dev, int prop) {
  CFTypeRef PropRef;
  char buf[500];

  PropRef = IORegistryEntryCreateCFProperty(dev, USB_PROPS[prop], kCFAllocatorDefault, 0);
  if (PropRef) {
      if(!CFStringGetCString(PropRef, buf, 500, kCFStringEncodingUTF8)) buf[0] = '\0';
  } else buf[0] = '\0';

  return PyUnicode_DecodeUTF8(buf, strlen(buf), "replace");
}

static PyObject *
usbobserver_get_usb_devices(PyObject *self, PyObject *args) {
  
  CFMutableDictionaryRef matchingDict;
  kern_return_t kr;

  //Set up matching dictionary for class IOUSBDevice and its subclasses
  matchingDict = IOServiceMatching(kIOUSBDeviceClassName);
  if (!matchingDict) {
    PyErr_SetString(PyExc_RuntimeError, "Couldn't create a USB matching dictionary");
    return NULL;
  }

  io_iterator_t iter;
  IOServiceGetMatchingServices(kIOMasterPortDefault, matchingDict, &iter);
  io_service_t usbDevice;
  IOCFPlugInInterface **plugInInterface = NULL;
  SInt32 score;
  IOUSBDeviceInterface182 **dev = NULL;
  UInt16 vendor, product, bcd;
  PyObject *manufacturer, *productn, *serial;

  PyObject *devices, *device;
  devices = PyList_New(0);
  if (devices == NULL) {
      PyErr_NoMemory();
      return NULL;
  }

  while ((usbDevice = IOIteratorNext(iter))) {
    plugInInterface = NULL; dev = NULL;
    //Create an intermediate plugin
    kr = IOCreatePlugInInterfaceForService(usbDevice, kIOUSBDeviceUserClientTypeID, kIOCFPlugInInterfaceID, &plugInInterface, &score);
    if ((kIOReturnSuccess != kr) || !plugInInterface) {
      printf("Unable to create a plug-in (%08x)\n", kr); continue;
    }
    //Now create the device interface
    HRESULT result = (*plugInInterface)->QueryInterface(plugInInterface, CFUUIDGetUUIDBytes(kIOUSBDeviceInterfaceID), (LPVOID)&dev);

    if (result || !dev) {
        printf("Couldn't create a device interface (%08x)\n", (int) result);
        continue;
    }

    kr = (*dev)->GetDeviceVendor(dev, &vendor);
    kr = (*dev)->GetDeviceProduct(dev, &product);
    kr = (*dev)->GetDeviceReleaseNumber(dev, &bcd);

    manufacturer = get_iokit_string_property(usbDevice, 0);
    if (manufacturer == NULL) manufacturer = Py_None;
    productn = get_iokit_string_property(usbDevice, 1);
    if (productn == NULL) productn = Py_None;
    serial = get_iokit_string_property(usbDevice, 2);
    if (serial == NULL) serial = Py_None;

    device = Py_BuildValue("(iiiNNN)", vendor, product, bcd, manufacturer, productn, serial);
    if (device == NULL) {
      IOObjectRelease(usbDevice);
      (*plugInInterface)->Release(plugInInterface);
      (*dev)->Release(dev);
      Py_DECREF(devices);
      return NULL;

    }
    if (PyList_Append(devices, device) == -1) {
      IOObjectRelease(usbDevice);
      (*plugInInterface)->Release(plugInInterface);
      (*dev)->Release(dev);
      Py_DECREF(devices);
      Py_DECREF(device);
      return NULL;
    }

    IOObjectRelease(usbDevice);
    (*plugInInterface)->Release(plugInInterface);
    (*dev)->Release(dev);
    Py_DECREF(device);
  }
    
  return devices;
}

static PyMethodDef usbobserver_methods[] = {
    {"get_usb_devices", usbobserver_get_usb_devices, METH_VARARGS, 
     "Get list of connected USB devices. Returns a list of tuples. Each tuple is of the form (vendor_id, product_id)."
    },
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initusbobserver(void) {
    (void) Py_InitModule("usbobserver", usbobserver_methods);
}
