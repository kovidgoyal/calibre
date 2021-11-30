/*
 * global.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Windows.h>
#include <atlbase.h>
#include <Python.h>

#include <Objbase.h>
#include <PortableDeviceApi.h>
#include <PortableDevice.h>
#include "../../../utils/windows/common.h"

#define ENSURE_WPD(retval) \
    if (!portable_device_manager) { PyErr_SetString(NoWPD, "No WPD service available."); return retval; }

namespace wpd {

// Module exception types
extern PyObject *WPDError, *NoWPD, *WPDFileBusy;

// The global device manager
extern CComPtr<IPortableDeviceManager> portable_device_manager;

// Device type
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    wchar_raii pnp_id;
    CComPtr<IPortableDevice> device;
    pyobject_raii device_information;
    CComPtr<IPortableDevicePropertiesBulk> bulk_properties;
} Device;
extern PyTypeObject DeviceType;

#define hresult_set_exc(msg, hr) set_error_from_hresult(wpd::WPDError, __FILE__, __LINE__, hr, msg)

extern IPortableDeviceValues* get_client_information();
extern IPortableDevice* open_device(const wchar_t *pnp_id, CComPtr<IPortableDeviceValues> &client_information);
extern PyObject* get_device_information(CComPtr<IPortableDevice> &device, CComPtr<IPortableDevicePropertiesBulk> &bulk_properties);
extern PyObject* get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties, PyObject *callback);
extern PyObject* get_file(IPortableDevice *device, const wchar_t *object_id, PyObject *dest, PyObject *callback);
extern PyObject* create_folder(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name);
extern PyObject* delete_object(IPortableDevice *device, const wchar_t *object_id);
extern PyObject* put_file(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name, PyObject *src, unsigned PY_LONG_LONG size, PyObject *callback);

}
