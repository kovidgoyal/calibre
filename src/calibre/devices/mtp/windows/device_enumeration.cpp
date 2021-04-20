/*
 * device_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

namespace wpd {

IPortableDeviceValues *get_client_information() { // {{{
    HRESULT hr;

    ENSURE_WPD(NULL);
    CComPtr<IPortableDeviceValues> client_information;

    Py_BEGIN_ALLOW_THREADS;
	hr = client_information.CoCreateInstance(CLSID_PortableDeviceValues, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create IPortableDeviceValues", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetStringValue(WPD_CLIENT_NAME, client_info.name.ptr());
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to set client name", hr); return NULL; }
    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetUnsignedIntegerValue(WPD_CLIENT_MAJOR_VERSION, client_info.major_version);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to set major version", hr); return NULL; }
    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetUnsignedIntegerValue(WPD_CLIENT_MINOR_VERSION, client_info.minor_version);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to set minor version", hr); return NULL; }
    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetUnsignedIntegerValue(WPD_CLIENT_REVISION, client_info.revision);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to set revision", hr); return NULL; }
    //  Some device drivers need to impersonate the caller in order to function correctly.  Since our application does not
    //  need to restrict its identity, specify SECURITY_IMPERSONATION so that we work with all devices.
    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetUnsignedIntegerValue(WPD_CLIENT_SECURITY_QUALITY_OF_SERVICE, SECURITY_IMPERSONATION);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to set quality of service", hr); return NULL; }
    return client_information.Detach();
} // }}}

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
		wchar_t* object_ids[16] = {0};
        Py_BEGIN_ALLOW_THREADS;
        hr = objects->Next(arraysz(object_ids), object_ids, &fetched);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) {
			com_wchar_raii cleanup[arraysz(object_ids)];
            for (i = 0; i < arraysz(object_ids); i++) { cleanup[i].set_ptr(object_ids[i]); };
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
#define A(which, key) { com_wchar_raii buf; if (SUCCEEDED(values->GetStringValue(which, buf.address()))) { \
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
get_device_information(CComPtr<IPortableDevice> &device, IPortableDevicePropertiesBulk **pb) { // {{{
    IPortableDeviceContent *content = NULL;
    IPortableDeviceProperties *properties = NULL;
    IPortableDevicePropertiesBulk *properties_bulk = NULL;
    IPortableDeviceKeyCollection *keys = NULL;
    IPortableDeviceValues *values = NULL;
    IPortableDeviceCapabilities *capabilities = NULL;
    IPortableDevicePropVariantCollection *categories = NULL;
    HRESULT hr;
    DWORD num_of_categories, i;
    LPWSTR temp;
    ULONG ti;
    PyObject *t, *ans = NULL;
    const char *type = NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&keys));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to create IPortableDeviceKeyCollection", hr); goto end;}

    Py_BEGIN_ALLOW_THREADS;
    hr = keys->Add(WPD_DEVICE_PROTOCOL);
    // Despite the MSDN documentation, this does not exist in PortableDevice.h
    // hr = keys->Add(WPD_DEVICE_TRANSPORT);
    hr = keys->Add(WPD_DEVICE_FRIENDLY_NAME);
    hr = keys->Add(WPD_DEVICE_MANUFACTURER);
    hr = keys->Add(WPD_DEVICE_MODEL);
    hr = keys->Add(WPD_DEVICE_SERIAL_NUMBER);
    hr = keys->Add(WPD_DEVICE_FIRMWARE_VERSION);
    hr = keys->Add(WPD_DEVICE_TYPE);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to add keys to IPortableDeviceKeyCollection", hr); goto end;}

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get IPortableDeviceContent", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&properties);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get IPortableDeviceProperties", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = properties->GetValues(WPD_DEVICE_OBJECT_ID, keys, &values);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) {hresult_set_exc("Failed to get device info", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Capabilities(&capabilities);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) {hresult_set_exc("Failed to get device capabilities", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = capabilities->GetFunctionalCategories(&categories);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) {hresult_set_exc("Failed to get device functional categories", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = categories->GetCount(&num_of_categories);
    Py_END_ALLOW_THREADS;
    if(FAILED(hr)) {hresult_set_exc("Failed to get device functional categories number", hr); goto end; }

    ans = PyDict_New();
    if (ans == NULL) {PyErr_NoMemory(); goto end;}

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_PROTOCOL, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "protocol", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    // if (SUCCEEDED(values->GetUnsignedIntegerValue(WPD_DEVICE_TRANSPORT, &ti))) {
    //     PyDict_SetItemString(ans, "isusb", (ti == WPD_DEVICE_TRANSPORT_USB) ? Py_True : Py_False);
    //     t = PyLong_FromUnsignedLong(ti);
    // }

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
        t = PyUnicode_FromString(type);
        if (t != NULL) {
            PyDict_SetItemString(ans, "type", t); Py_DECREF(t);
        }
    }

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_FRIENDLY_NAME, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "friendly_name", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_MANUFACTURER, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "manufacturer_name", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_MODEL, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "model_name", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_SERIAL_NUMBER, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "serial_number", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    if (SUCCEEDED(values->GetStringValue(WPD_DEVICE_FIRMWARE_VERSION, &temp))) {
        t = PyUnicode_FromWideChar(temp, wcslen(temp));
        if (t != NULL) {PyDict_SetItemString(ans, "device_version", t); Py_DECREF(t);}
        CoTaskMemFree(temp);
    }

    t = Py_False;
    for (i = 0; i < num_of_categories; i++) {
        PROPVARIANT pv;
        PropVariantInit(&pv);
        if (SUCCEEDED(categories->GetAt(i, &pv)) && pv.puuid != NULL) {
            if (IsEqualGUID(WPD_FUNCTIONAL_CATEGORY_STORAGE, *pv.puuid)) {
                t = Py_True;
            }
        }
        PropVariantClear(&pv);
        if (t == Py_True) break;
    }
    PyDict_SetItemString(ans, "has_storage", t);

    if (t == Py_True) {
        pyobject_raii storage(get_storage_info(device));
        if (!storage) {
			pyobject_raii exc_type, exc_value, exc_tb;
            PyErr_Fetch(exc_type.address(), exc_value.address(), exc_tb.address());
            if (exc_type) {
                PyErr_NormalizeException(exc_type.address(), exc_value.address(), exc_tb.address());
                PyDict_SetItemString(ans, "storage_error", exc_value.ptr());
            } else {
                PyDict_SetItemString(ans, "storage_error", PyUnicode_FromString("get_storage_info() failed without an error set"));
			}
        } else {
			PyDict_SetItemString(ans, "storage", storage.ptr());
		}
    }

    Py_BEGIN_ALLOW_THREADS;
    hr = properties->QueryInterface(IID_PPV_ARGS(&properties_bulk));
    Py_END_ALLOW_THREADS;
    PyDict_SetItemString(ans, "has_bulk_properties", (FAILED(hr)) ? Py_False: Py_True);
    if (pb != NULL) *pb = (SUCCEEDED(hr)) ? properties_bulk : NULL;

end:
    if (keys != NULL) keys->Release();
    if (values != NULL) values->Release();
    if (properties != NULL) properties->Release();
    if (properties_bulk != NULL && pb == NULL) properties_bulk->Release();
    if (content != NULL) content->Release();
    if (capabilities != NULL) capabilities->Release();
    if (categories != NULL) categories->Release();
    return ans;
} // }}}

} // namespace wpd
