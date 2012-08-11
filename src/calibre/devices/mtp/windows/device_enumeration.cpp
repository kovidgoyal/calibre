/*
 * device_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the MIT license.
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

PyObject* get_device_information(IPortableDevice *device) { // {{{
    IPortableDeviceContent *content = NULL;
    IPortableDeviceProperties *properties = NULL;
    IPortableDeviceKeyCollection *keys = NULL;
    IPortableDeviceValues *values = NULL;
    HRESULT hr;
    LPWSTR temp;
    ULONG ti;
    PyObject *t, *ans = NULL;
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

end:
    if (keys != NULL) keys->Release();
    if (values != NULL) values->Release();
    if (properties != NULL) properties->Release();
    if (content != NULL) content->Release();
    return ans;
} // }}}

} // namespace wpd
