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
extern PyObject *WPDError, *NoWPD;

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

} Device;
extern PyTypeObject DeviceType;

// Utility functions
PyObject *hresult_set_exc(const char *msg, HRESULT hr);
wchar_t *unicode_to_wchar(PyObject *o);

extern IPortableDeviceValues* get_client_information();
extern IPortableDevice* open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information);
extern PyObject* get_device_information(IPortableDevice *device);

}

