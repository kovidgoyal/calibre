/*
 * device_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

namespace wpd {

IPortableDeviceValues *get_client_information() { // {{{
    IPortableDeviceValues *client_information;
    HRESULT hr;

    ENSURE_WPD(NULL);

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDeviceValues, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&client_information));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create IPortableDeviceValues", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = client_information->SetStringValue(WPD_CLIENT_NAME, client_info.name);
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
    return client_information;
} // }}}

IPortableDevice *open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information) { // {{{
    IPortableDevice *device = NULL;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDevice, NULL, CLSCTX_INPROC_SERVER,
            IID_PPV_ARGS(&device));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) hresult_set_exc("Failed to create IPortableDevice", hr);
    else {
        Py_BEGIN_ALLOW_THREADS;
        hr = device->Open(pnp_id, client_information);
        Py_END_ALLOW_THREADS;
        if FAILED(hr) {
            Py_BEGIN_ALLOW_THREADS;
            device->Release();
            Py_END_ALLOW_THREADS;
            device = NULL;
            hresult_set_exc((hr == E_ACCESSDENIED) ? "Read/write access to device is denied": "Failed to open device", hr);
        }
    }

    return device;

} // }}}

PyObject* get_storage_info(IPortableDevice *device) { // {{{
    HRESULT hr, hr2;
    IPortableDeviceContent *content = NULL;
    IEnumPortableDeviceObjectIDs *objects = NULL;
    IPortableDeviceProperties *properties = NULL;
    IPortableDeviceKeyCollection *storage_properties = NULL;
    IPortableDeviceValues *values = NULL;
    PyObject *ans = NULL, *storage = NULL, *so = NULL, *desc = NULL, *soid = NULL;
    DWORD fetched, i;
    PWSTR object_ids[10];
    GUID guid;
    ULONGLONG capacity, free_space, capacity_objects, free_objects;
    ULONG access;
    LPWSTR storage_desc = NULL;

    storage = PyList_New(0);
    if (storage == NULL) { PyErr_NoMemory(); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get content interface from device", hr); goto end;}

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&properties);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get properties interface", hr); goto end;}

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&storage_properties));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to create storage properties collection", hr); goto end;}

    Py_BEGIN_ALLOW_THREADS;
    hr = storage_properties->Add(WPD_OBJECT_CONTENT_TYPE);
    hr = storage_properties->Add(WPD_FUNCTIONAL_OBJECT_CATEGORY);
    hr = storage_properties->Add(WPD_STORAGE_DESCRIPTION);
    hr = storage_properties->Add(WPD_STORAGE_CAPACITY);
    hr = storage_properties->Add(WPD_STORAGE_CAPACITY_IN_OBJECTS);
    hr = storage_properties->Add(WPD_STORAGE_FREE_SPACE_IN_BYTES);
    hr = storage_properties->Add(WPD_STORAGE_FREE_SPACE_IN_OBJECTS);
    hr = storage_properties->Add(WPD_STORAGE_ACCESS_CAPABILITY);
    hr = storage_properties->Add(WPD_STORAGE_FILE_SYSTEM_TYPE);
    hr = storage_properties->Add(WPD_OBJECT_NAME);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to create collection of properties for storage query", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->EnumObjects(0, WPD_DEVICE_OBJECT_ID, NULL, &objects);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {hresult_set_exc("Failed to get objects from device", hr); goto end;}

    hr = S_OK;
    while (hr == S_OK) {
        Py_BEGIN_ALLOW_THREADS;
        hr = objects->Next(10, object_ids, &fetched);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) {
            for(i = 0; i < fetched; i++) {
                Py_BEGIN_ALLOW_THREADS;
                hr2 = properties->GetValues(object_ids[i], storage_properties, &values);
                Py_END_ALLOW_THREADS;
                if SUCCEEDED(hr2) {
                    if (
                        SUCCEEDED(values->GetGuidValue(WPD_OBJECT_CONTENT_TYPE, &guid)) && IsEqualGUID(guid, WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT) &&
                        SUCCEEDED(values->GetGuidValue(WPD_FUNCTIONAL_OBJECT_CATEGORY, &guid)) && IsEqualGUID(guid, WPD_FUNCTIONAL_CATEGORY_STORAGE)
                       ) {
                        capacity = 0; capacity_objects = 0; free_space = 0; free_objects = 0;
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_CAPACITY, &capacity);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_CAPACITY_IN_OBJECTS, &capacity_objects);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_FREE_SPACE_IN_BYTES, &free_space);
                        values->GetUnsignedLargeIntegerValue(WPD_STORAGE_FREE_SPACE_IN_OBJECTS, &free_objects);
                        desc = Py_False;
                        if (SUCCEEDED(values->GetUnsignedIntegerValue(WPD_STORAGE_ACCESS_CAPABILITY, &access)) && access == WPD_STORAGE_ACCESS_CAPABILITY_READWRITE) desc = Py_True;
                        soid = PyUnicode_FromWideChar(object_ids[i], wcslen(object_ids[i]));
                        if (soid == NULL) { PyErr_NoMemory(); goto end; }
                        so = Py_BuildValue("{s:K,s:K,s:K,s:K,s:O,s:N}", 
                                "capacity", capacity, "capacity_objects", capacity_objects, "free_space", free_space, "free_objects", free_objects, "rw", desc, "id", soid);
                        if (so == NULL) { PyErr_NoMemory(); goto end; }
                        if (SUCCEEDED(values->GetStringValue(WPD_STORAGE_DESCRIPTION, &storage_desc))) {
                                desc = PyUnicode_FromWideChar(storage_desc, wcslen(storage_desc));
                                if (desc != NULL) { PyDict_SetItemString(so, "description", desc); Py_DECREF(desc);}
                                CoTaskMemFree(storage_desc); storage_desc = NULL;
                        }
                        if (SUCCEEDED(values->GetStringValue(WPD_OBJECT_NAME, &storage_desc))) {
                                desc = PyUnicode_FromWideChar(storage_desc, wcslen(storage_desc));
                                if (desc != NULL) { PyDict_SetItemString(so, "name", desc); Py_DECREF(desc);}
                                CoTaskMemFree(storage_desc); storage_desc = NULL;
                        }
                        if (SUCCEEDED(values->GetStringValue(WPD_STORAGE_FILE_SYSTEM_TYPE, &storage_desc))) {
                                desc = PyUnicode_FromWideChar(storage_desc, wcslen(storage_desc));
                                if (desc != NULL) { PyDict_SetItemString(so, "filesystem", desc); Py_DECREF(desc);}
                                CoTaskMemFree(storage_desc); storage_desc = NULL;
                        }
                        PyList_Append(storage, so);
                        Py_DECREF(so);
                    }
                }
            } 
            for (i = 0; i < fetched; i ++) { CoTaskMemFree(object_ids[i]); object_ids[i] = NULL;}
        }// if(SUCCEEDED(hr))
    }
    ans = storage;

end:
    if (content != NULL) content->Release();
    if (objects != NULL) objects->Release();
    if (properties != NULL) properties->Release();
    if (storage_properties != NULL) storage_properties->Release();
    if (values != NULL) values->Release();
    return ans;
} // }}}

PyObject* get_device_information(IPortableDevice *device, IPortableDevicePropertiesBulk **pb) { // {{{
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
    PyObject *t, *ans = NULL, *storage = NULL;
    char *type;

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
            default:
                type = "unknown";
        }
        t = PyString_FromString(type);
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
        storage = get_storage_info(device);
        if (storage == NULL) goto end;
        PyDict_SetItemString(ans, "storage", storage);
        
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
