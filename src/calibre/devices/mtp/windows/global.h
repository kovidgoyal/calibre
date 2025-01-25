/*
 * global.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <windows.h>
#include <atlbase.h>
#include <Python.h>

#include <objbase.h>
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

static inline PyObject*
set_error_from_hresult_mtp(PyObject *exc_type, const char *file, const int line, const HRESULT hr, const char *prefix="", PyObject *name=NULL) {
    _com_error err(hr);
    PyObject *pmsg = PyUnicode_FromWideChar(err.ErrorMessage(), -1);
    // See https://learn.microsoft.com/en-us/windows/win32/wpd_sdk/error-constants
    const char *err_name = "unknown";
#define C(x) case (unsigned long)x: err_name = #x; break
#define D(code, x) case (unsigned long)code: err_name = #x; break
    switch((unsigned long)hr) {
        C(E_WPD_DEVICE_ALREADY_OPENED); C(E_WPD_DEVICE_IS_HUNG); C(E_WPD_DEVICE_NOT_OPEN); C(E_WPD_OBJECT_ALREADY_ATTACHED_TO_DEVICE);
        C(E_WPD_OBJECT_ALREADY_ATTACHED_TO_SERVICE); C(E_WPD_OBJECT_NOT_ATTACHED_TO_DEVICE); C(E_WPD_OBJECT_NOT_ATTACHED_TO_SERVICE);
        C(E_WPD_OBJECT_NOT_COMMITED); C(E_WPD_SERVICE_ALREADY_OPENED); C(E_WPD_SERVICE_BAD_PARAMETER_ORDER); C(E_WPD_SERVICE_NOT_OPEN);
        C(E_WPD_SMS_INVALID_RECIPIENT); C(E_WPD_SMS_INVALID_MESSAGE_BODY); C(E_WPD_SMS_SERVICE_UNAVAILABLE);

        C(ERROR_ACCESS_DENIED); C(ERROR_ARITHMETIC_OVERFLOW); C(ERROR_BUSY); C(ERROR_CANCELLED); C(ERROR_DATATYPE_MISMATCH);
        C(ERROR_DEVICE_IN_USE); C(ERROR_DEVICE_NOT_CONNECTED); C(ERROR_DIR_NOT_EMPTY); C(ERROR_EMPTY); C(ERROR_FILE_NOT_FOUND);
        C(ERROR_GEN_FAILURE); C(ERROR_INVALID_DATA); C(ERROR_INVALID_DATATYPE); C(ERROR_INVALID_FUNCTION); C(ERROR_INVALID_OPERATION);
        C(ERROR_INVALID_PARAMETER); C(ERROR_INVALID_TIME); C(ERROR_IO_DEVICE); C(ERROR_NOT_FOUND); C(ERROR_NOT_READY);
        C(ERROR_NOT_SUPPORTED); C(ERROR_OPERATION_ABORTED); C(ERROR_READ_FAULT); C(ERROR_RESOURCE_NOT_AVAILABLE);
        C(ERROR_SEM_TIMEOUT); C(ERROR_TIMEOUT); C(ERROR_UNSUPPORTED_TYPE); C(ERROR_WRITE_FAULT); C(WSAETIMEDOUT);

        D(0xC00D2767, NS_E_DRM_DEBUGGING_NOT_ALLOWED); D(0xC00D00CD, NS_E_NOT_LICENSED);

        D(0x80042003, SESSION_NOT_OPEN); D(0x80042004, INVALID_TRANSACTION_ID); D(0x80042005, OPERATION_NOT_SUPPORTED);
        D(0x80042006, PARAMETER_NOT_SUPPORTED); D(0x80042007, INCOMPLETE_TRANSFER); D(0x80042008, INVALID_STORAGE_ID);
        D(0x80042009, INVALID_OBJECT_HANDLE); D(0x8004200A, DEVICE_PROP_NOT_SUPPORTED); D(0x8004200B, INVALID_OBJECT_FORMAT_CODE);
        D(0x80042012, PARTIAL_DELETION); D(0x80042013, STORE_NOT_AVAILABLE); D(0x80042014, SPECIFICATION_BY_FORMAT_UNSUPPORTED);
        D(0x80042015, NO_VALID_OBJECTINFO); D(0x80042016, INVALID_CODE_FORMAT); D(0x80042017, UNKNOWN_VENDOR_CODE);
        D(0x8004201A, INVALID_PARENT_OBJECT); D(0x8004201B, INVALID_DEVICE_PROP_FORMAT); D(0x8004201C, INVALID_DEVICE_PROP_VALUE);
        D(0x8004201E, SESSION_ALREADY_OPEN); D(0x8004201F, TRANSACTION_CANCELED); D(0x80042020, SPECIFICATION_OF_DESTINATION_UNSUPPORTED);
        D(0x8004A801, INVALID_OBJECTPROP_CODE); D(0x8004A802, INVALID_OBJECT_FORMAT); D(0x8004A803, INVALID_OBJECTPROP_VALUE);
        D(0x8004A804, INVALID_OBJECT_REFERENCE); D(0x8004A806, INVALID_DATASET); D(0x8004A807, OBJECT_TOO_LARGE);
        D(0x8004A301, INVALID_SERVICE_ID); D(0x8004A302, INVALID_SERVICE_PROP_CODE);
    }
#undef C
#undef D
    if (name) PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x wCode=%d name=%s] %V: %S", file, line, prefix, hr, err.WCode(), err_name, pmsg, "Out of memory", name);
    else PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x wCode=%d name=%s] %V", file, line, prefix, hr, err.WCode(), err_name, pmsg, "Out of memory");
    Py_CLEAR(pmsg);
    return NULL;
}

#define hresult_set_exc(msg, hr, ...) set_error_from_hresult_mtp(wpd::WPDError, __FILE__, __LINE__, hr, msg, __VA_ARGS__)

extern IPortableDeviceValues* get_client_information();
extern IPortableDevice* open_device(const wchar_t *pnp_id, CComPtr<IPortableDeviceValues> &client_information);
extern PyObject* get_device_information(const wchar_t *pnp_id, CComPtr<IPortableDevice> &device, CComPtr<IPortableDevicePropertiesBulk> &bulk_properties);
extern PyObject* get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties, PyObject *callback);
extern PyObject* get_file(IPortableDevice *device, const wchar_t *object_id, PyObject *dest, PyObject *callback);
extern PyObject* create_folder(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name);
extern PyObject* delete_object(IPortableDevice *device, const wchar_t *object_id);
extern PyObject* put_file(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name, PyObject *src, unsigned PY_LONG_LONG size, PyObject *callback);
extern PyObject* find_in_parent(
    CComPtr<IPortableDeviceContent> &content, const wchar_t *parent_id, PyObject *name);
extern PyObject* list_folder(
        IPortableDevice *device, CComPtr<IPortableDeviceContent> &content, IPortableDevicePropertiesBulk *bulk_properties,
        const wchar_t *folder_id);
extern PyObject* get_metadata(CComPtr<IPortableDeviceContent> &content, const wchar_t *object_id);
}
