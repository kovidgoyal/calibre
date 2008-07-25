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


static PyObject *
usbobserver_get_usb_devices(PyObject *self, PyObject *args) {
  
  mach_port_t masterPort;
  CFMutableDictionaryRef matchingDict;
  kern_return_t kr;

  /* Create a master port for communication with IOKit */
  kr = IOMasterPort(MACH_PORT_NULL, &masterPort);

  if (kr || !masterPort) {
    PyErr_SetString(PyExc_RuntimeError, "Couldn't create master IOKit port");
    return NULL;
  }
  
  //Set up matching dictionary for class IOUSBDevice and its subclasses
  matchingDict = IOServiceMatching(kIOUSBDeviceClassName);
  if (!matchingDict) {
    PyErr_SetString(PyExc_RuntimeError, "Couldn't create a USB matching dictionary");
    mach_port_deallocate(mach_task_self(), masterPort);
    return NULL;
  }

  io_iterator_t iter;
  IOServiceGetMatchingServices(kIOMasterPortDefault, matchingDict, &iter);
  io_service_t usbDevice;
  IOCFPlugInInterface **plugInInterface = NULL;
  SInt32 score;
  IOUSBDeviceInterface182 **dev = NULL;
  UInt16 vendor, product;

  PyObject *devices, *device;
  devices = PyList_New(0);
  if (devices == NULL) {
      PyErr_NoMemory();
      mach_port_deallocate(mach_task_self(), masterPort);
      return NULL;
  }

  while (usbDevice = IOIteratorNext(iter)) {
    plugInInterface = NULL; dev = NULL;
    //Create an intermediate plugin
    kr = IOCreatePlugInInterfaceForService(usbDevice, kIOUSBDeviceUserClientTypeID, kIOCFPlugInInterfaceID, &plugInInterface, &score);
    if ((kIOReturnSuccess != kr) || !plugInInterface)
      printf("Unable to create a plug-in (%08x)\n", kr);
    //Now create the device interface
    HRESULT result = (*plugInInterface)->QueryInterface(plugInInterface, CFUUIDGetUUIDBytes(kIOUSBDeviceInterfaceID), (LPVOID)&dev);

    if (result || !dev) printf("Couldn't create a device interface (%08x)\n", (int) result);

    kr = (*dev)->GetDeviceVendor(dev, &vendor);
    kr = (*dev)->GetDeviceProduct(dev, &product);
    device = Py_BuildValue("(ii)", vendor, product);
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
    

  //Finished with master port
  mach_port_deallocate(mach_task_self(), masterPort);
  
  return Py_BuildValue("N", devices);
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
