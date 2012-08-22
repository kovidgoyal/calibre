/*
 * global.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define UNICODE
#include <Windows.h>
#include <Python.h>

#include <Objbase.h>
#include <PortableDeviceApi.h>
#include <PortableDevice.h>

#define ENSURE_WPD(retval) \
    if (portable_device_manager == NULL) { PyErr_SetString(NoWPD, "No WPD service available."); return retval; }

namespace wpd {

// Module exception types
extern PyObject *WPDError, *NoWPD, *WPDFileBusy;

// The global device manager
extern IPortableDeviceManager *portable_device_manager;

// Application info
typedef struct {
    wchar_t *name;
    unsigned int major_version;
    unsigned int minor_version;
    unsigned int revision;
} ClientInfo;
extern ClientInfo client_info;

// Device type
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    wchar_t *pnp_id;
    IPortableDeviceValues *client_information;
    IPortableDevice *device;
    PyObject *device_information;
    IPortableDevicePropertiesBulk *bulk_properties;

} Device;
extern PyTypeObject DeviceType;

// Utility functions
PyObject *hresult_set_exc(const char *msg, HRESULT hr);
wchar_t *unicode_to_wchar(PyObject *o);
PyObject *wchar_to_unicode(const wchar_t *o);
int pump_waiting_messages();

extern IPortableDeviceValues* get_client_information();
extern IPortableDevice* open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information);
extern PyObject* get_device_information(IPortableDevice *device, IPortableDevicePropertiesBulk **bulk_properties);
extern PyObject* get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties);
extern PyObject* get_file(IPortableDevice *device, const wchar_t *object_id, PyObject *dest, PyObject *callback);
extern PyObject* create_folder(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name);

}

