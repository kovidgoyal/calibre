/*
 * device_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

namespace wpd {

IPortableDevice*
open_device(const wchar_t *pnp_id, CComPtr<IPortableDeviceValues> &client_information) { // {{{
    CComPtr<IPortableDevice> device;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = device.CoCreateInstance(CLSID_PortableDevice, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create IPortableDevice", hr); device = NULL; }
    else {
        Py_BEGIN_ALLOW_THREADS;
        hr = device->Open(pnp_id, client_information);
        Py_END_ALLOW_THREADS;
        if FAILED(hr) {
            Py_BEGIN_ALLOW_THREADS;
            device.Release();
            Py_END_ALLOW_THREADS;
            hresult_set_exc((hr == E_ACCESSDENIED) ? "Read/write access to device is denied": "Failed to open device", hr);
        }
    }

    return device.Detach();

} // }}}

static PyObject*
get_storage_info(IPortableDevice *device) { // {{{
    HRESULT hr, hr2;
    CComPtr<IPortableDeviceContent> content = NULL;
    CComPtr<IEnumPortableDeviceObjectIDs> objects = NULL;
    CComPtr<IPortableDeviceProperties> properties = NULL;
    CComPtr<IPortableDeviceKeyCollection> storage_properties = NULL;
    DWORD fetched, i;
    GUID guid;
    ULONGLONG capacity, free_space, capacity_objects, free_objects;
    ULONG access, storage_type = WPD_STORAGE_TYPE_UNDEFINED;

    pyobject_raii storage(PyList_New(0));
	if (!storage) return NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get content interface from device", hr); return NULL;}

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&properties);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get properties interface", hr); return NULL;}

    Py_BEGIN_ALLOW_THREADS;
    hr = storage_properties.CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to create storage properties collection", hr); return NULL;}

#define A(what) hr = storage_properties->Add(what); if (FAILED(hr)) { hresult_set_exc("Failed to add storage property " #what " for storage query", hr); return NULL; }
    A(WPD_OBJECT_CONTENT_TYPE);
    A(WPD_FUNCTIONAL_OBJECT_CATEGORY);
    A(WPD_STORAGE_DESCRIPTION);
    A(WPD_STORAGE_CAPACITY);
    A(WPD_STORAGE_CAPACITY_IN_OBJECTS);
    A(WPD_STORAGE_FREE_SPACE_IN_BYTES);
    A(WPD_STORAGE_FREE_SPACE_IN_OBJECTS);
    A(WPD_STORAGE_ACCESS_CAPABILITY);
    A(WPD_STORAGE_FILE_SYSTEM_TYPE);
    A(WPD_STORAGE_TYPE);
    A(WPD_OBJECT_NAME);
#undef A

    Py_BEGIN_ALLOW_THREADS;
    hr = content->EnumObjects(0, WPD_DEVICE_OBJECT_ID, NULL, &objects);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get objects from device", hr); return NULL;}

    hr = S_OK;
    while (hr == S_OK) {
		generic_raii_array<wchar_t*, co_task_mem_free, 16> object_ids;
        Py_BEGIN_ALLOW_THREADS;
        hr = objects->Next((ULONG)object_ids.size(), object_ids.ptr(), &fetched);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) {
            for(i = 0; i < fetched; i++) {
				CComPtr<IPortableDeviceValues> values;
                Py_BEGIN_ALLOW_THREADS;
                hr2 = properties->GetValues(object_ids[i], storage_properties, &values);
                Py_END_ALLOW_THREADS;
                if (SUCCEEDED(hr2)) {
                    if (
                        SUCCEEDED(values->GetGuidValue(WPD_OBJECT_CONTENT_TYPE, &guid)) && IsEqualGUID(guid, WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT) &&
                        SUCCEEDED(values->GetGuidValue(WPD_FUNCTIONAL_OBJECT_CATEGORY, &guid)) && IsEqualGUID(guid, WPD_FUNCTIONAL_CATEGORY_STORAGE)
                       ) {
                        capacity = 0; capacity_objects = 0; free_space = 0; free_objects = 0;
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_CAPACITY, &capacity);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_CAPACITY_IN_OBJECTS, &capacity_objects);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_FREE_SPACE_IN_BYTES, &free_space);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_FREE_SPACE_IN_OBJECTS, &free_objects);
                        values->GetUnsignedIntegerValue(WPD_STORAGE_TYPE, &storage_type);
                        PyObject *paccess = Py_False;
                        if (SUCCEEDED(values->GetUnsignedIntegerValue(WPD_STORAGE_ACCESS_CAPABILITY, &access)) && access == WPD_STORAGE_ACCESS_CAPABILITY_READWRITE) paccess = Py_True;
                        pyobject_raii soid(PyUnicode_FromWideChar(object_ids[i], -1));
                        if (!soid) return NULL;
                        pyobject_raii so(Py_BuildValue("{s:K, s:K, s:K, s:K, s:O, s:O}",
                                "capacity", capacity, "capacity_objects", capacity_objects, "free_space", free_space, "free_objects", free_objects, "rw", paccess, "id", soid.ptr()));
                        if (!so) return NULL;
#define A(which, key) { com_wchar_raii buf; if (SUCCEEDED(values->GetStringValue(which, buf.unsafe_address()))) { \
							pyobject_raii d(PyUnicode_FromWideChar(buf.ptr(), -1)); \
							if (d) PyDict_SetItemString(so.ptr(), key, d.ptr()); \
							else PyErr_Clear(); \
                        }}
						A(WPD_STORAGE_DESCRIPTION, "description");
						A(WPD_OBJECT_NAME, "name");
						A(WPD_STORAGE_FILE_SYSTEM_TYPE, "filesystem");
#undef A
						const wchar_t *st;
                        switch(storage_type) {
                            case WPD_STORAGE_TYPE_REMOVABLE_RAM:
                                st = L"removable_ram";
                                break;
                            case WPD_STORAGE_TYPE_REMOVABLE_ROM:
                                st = L"removable_rom";
                                break;
                            case WPD_STORAGE_TYPE_FIXED_RAM:
                                st = L"fixed_ram";
                                break;
                            case WPD_STORAGE_TYPE_FIXED_ROM:
                                st = L"fixed_rom";
                                break;
                            default:
                                st = L"unknown_unknown";
                        }
						pyobject_raii dt(PyUnicode_FromWideChar(st, -1));
						if (dt) PyDict_SetItemString(so.ptr(), "type", dt.ptr());
                        if (PyList_Append(storage.ptr(), so.ptr()) != 0) return NULL;
                    }
                }
            }
        }// if(SUCCEEDED(hr))
    }
	return storage.detach();
} // }}}

PyObject*
get_device_information(const wchar_t *pnp_id, CComPtr<IPortableDevice> &device, CComPtr<IPortableDevicePropertiesBulk> &pb) { // {{{
    CComPtr<IPortableDeviceContent> content = NULL;
    CComPtr<IPortableDeviceProperties> properties = NULL;
    CComPtr<IPortableDeviceKeyCollection> keys = NULL;
    CComPtr<IPortableDeviceValues> values = NULL;
    CComPtr<IPortableDeviceCapabilities> capabilities = NULL;
    CComPtr<IPortableDevicePropVariantCollection> categories = NULL;
    HRESULT hr;
    DWORD num_of_categories, i;
    ULONG ti;
    PyObject *ans = NULL;
    const char *type = NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = keys.CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return hresult_set_exc("Failed to create IPortableDeviceKeyCollection", hr);

#define A(what) hr = keys->Add(what); if (FAILED(hr)) { return hresult_set_exc("Failed to add key " #what " to IPortableDeviceKeyCollection", hr); }
    A(WPD_DEVICE_PROTOCOL);
    // Despite the MSDN documentation, this does not exist in PortableDevice.h
    // hr = keys->Add(WPD_DEVICE_TRANSPORT);
    A(WPD_DEVICE_FRIENDLY_NAME);
    A(WPD_DEVICE_MANUFACTURER);
    A(WPD_DEVICE_MODEL);
    A(WPD_DEVICE_SERIAL_NUMBER);
    A(WPD_DEVICE_FIRMWARE_VERSION);
    A(WPD_DEVICE_TYPE);
#undef A

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return hresult_set_exc("Failed to get IPortableDeviceContent", hr);

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&properties);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return hresult_set_exc("Failed to get IPortableDeviceProperties", hr);

    Py_BEGIN_ALLOW_THREADS;
    hr = properties->GetValues(WPD_DEVICE_OBJECT_ID, keys, &values);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) return hresult_set_exc("Failed to get device info", hr);

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Capabilities(&capabilities);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) return hresult_set_exc("Failed to get device capabilities", hr);

    Py_BEGIN_ALLOW_THREADS;
    hr = capabilities->GetFunctionalCategories(&categories);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) return hresult_set_exc("Failed to get device functional categories", hr);

    Py_BEGIN_ALLOW_THREADS;
    hr = categories->GetCount(&num_of_categories);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) return hresult_set_exc("Failed to get device functional categories number", hr);

    ans = PyDict_New();
    if (ans == NULL) return NULL;

#define S(what, key) { \
	com_wchar_raii temp; \
    if (SUCCEEDED(values->GetStringValue(what, temp.unsafe_address()))) { \
        pyobject_raii t(PyUnicode_FromWideChar(temp.ptr(), -1)); \
        if (t) if (PyDict_SetItemString(ans, key, t.ptr()) != 0) PyErr_Clear(); \
    }}

	S(WPD_DEVICE_PROTOCOL, "protocol");

    if (SUCCEEDED(values->GetUnsignedIntegerValue(WPD_DEVICE_TYPE, &ti))) {
		type = "unknown";
        switch (ti) {
            case WPD_DEVICE_TYPE_CAMERA:
                type = "camera"; break;
            case WPD_DEVICE_TYPE_MEDIA_PLAYER:
                type = "media player"; break;
            case WPD_DEVICE_TYPE_PHONE:
                type = "phone"; break;
            case WPD_DEVICE_TYPE_VIDEO:
                type = "video"; break;
            case WPD_DEVICE_TYPE_PERSONAL_INFORMATION_MANAGER:
                type = "personal information manager"; break;
            case WPD_DEVICE_TYPE_AUDIO_RECORDER:
                type = "audio recorder"; break;
            case WPD_DEVICE_TYPE_GENERIC:
                break;
        }
		pyobject_raii t(PyUnicode_FromString(type));
		if (t) PyDict_SetItemString(ans, "type", t.ptr());
    }

	S(WPD_DEVICE_FRIENDLY_NAME, "friendly_name");
	S(WPD_DEVICE_MANUFACTURER, "manufacturer_name");
	S(WPD_DEVICE_MODEL, "model_name");
	S(WPD_DEVICE_SERIAL_NUMBER, "serial_number");
	S(WPD_DEVICE_FIRMWARE_VERSION, "device_version");
#undef S

    bool has_storage = false;
    for (i = 0; i < num_of_categories && !has_storage; i++) {
        prop_variant pv;
        if (SUCCEEDED(categories->GetAt(i, &pv)) && pv.puuid != NULL) {
            if (IsEqualGUID(WPD_FUNCTIONAL_CATEGORY_STORAGE, *pv.puuid)) has_storage = true;
        }
    }
    PyDict_SetItemString(ans, "has_storage", has_storage ? Py_True : Py_False);
    pyobject_raii pid(PyUnicode_FromWideChar(pnp_id, -1));
    if (pid) PyDict_SetItemString(ans, "pnp_id", pid.ptr());

    if (has_storage) {
        pyobject_raii storage(get_storage_info(device));
        if (!storage) {
			pyobject_raii exc_type, exc_value, exc_tb;
            PyErr_Fetch(exc_type.unsafe_address(), exc_value.unsafe_address(), exc_tb.unsafe_address());
            if (exc_type) {
                PyErr_NormalizeException(exc_type.unsafe_address(), exc_value.unsafe_address(), exc_tb.unsafe_address());
                PyDict_SetItemString(ans, "storage_error", exc_value.ptr());
            } else {
				pyobject_raii t(PyUnicode_FromString("get_storage_info() failed without an error set"));
                if (t) PyDict_SetItemString(ans, "storage_error", t.ptr());
			}
        } else {
			PyDict_SetItemString(ans, "storage", storage.ptr());
		}
    }

    bool is_buggy_piece_of_shit_device = false;
    PyObject *q = PyDict_GetItemString(ans, "manufacturer_name");
    if (q && PyUnicode_CompareWithASCIIString(q, "BarnesAndNoble") == 0) {
        q = PyDict_GetItemString(ans, "model_name");
        if (q && PyUnicode_CompareWithASCIIString(q, "BNRV1300") == 0) is_buggy_piece_of_shit_device = true;
    }

    if (is_buggy_piece_of_shit_device) {
        PyDict_SetItemString(ans, "has_bulk_properties", Py_False);
        pb = NULL;
    } else {
        Py_BEGIN_ALLOW_THREADS;
        hr = properties->QueryInterface(IID_PPV_ARGS(&pb));
        Py_END_ALLOW_THREADS;
        PyDict_SetItemString(ans, "has_bulk_properties", (FAILED(hr)) ? Py_False: Py_True);
    }
    return ans;
} // }}}

} // namespace wpd
