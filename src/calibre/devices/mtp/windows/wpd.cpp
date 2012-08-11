/*
 * mtp.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the MIT license.
 */


#define UNICODE
#include <Windows.h>
#include <Python.h>

#include <Objbase.h>
#include <PortableDeviceApi.h>
#include <PortableDevice.h>

// Utility functions {{{
#define ENSURE_WPD(retval) \
    if (portable_device_manager == NULL) { PyErr_SetString(NoWPD, "No WPD service available."); return retval; }

static PyObject *WPDError = NULL, *NoWPD = NULL;
static IPortableDeviceManager *portable_device_manager = NULL;
static int _com_initialized = 0;
typedef struct {
    wchar_t *name;
    unsigned int major_version;
    unsigned int minor_version;
    unsigned int revision;
} ClientInfo;
static ClientInfo client_info = {NULL, 0, 0, 0};

static PyObject *hresult_set_exc(const char *msg, HRESULT hr) { 
    PyObject *o = NULL, *mess;
    LPWSTR desc = NULL;

    FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM|FORMAT_MESSAGE_ALLOCATE_BUFFER|FORMAT_MESSAGE_IGNORE_INSERTS,
            NULL, hr, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPWSTR)&desc, 0, NULL);
    if (desc == NULL) {
        o = PyUnicode_FromString("No description available.");
    } else {
        o = PyUnicode_FromWideChar(desc, wcslen(desc));
        LocalFree(desc);
    }
    if (o == NULL) return PyErr_NoMemory();
    mess = PyUnicode_FromFormat("%s: hr=%lu facility=%u error_code=%u description: %U", msg, hr, HRESULT_FACILITY(hr), HRESULT_CODE(hr), o);
    Py_XDECREF(o);
    if (mess == NULL) return PyErr_NoMemory();
    PyErr_SetObject(WPDError, mess);
    Py_DECREF(mess);
    return NULL;
}

static wchar_t *unicode_to_wchar(PyObject *o) {
    wchar_t *buf;
    Py_ssize_t len;
    if (!PyUnicode_Check(o)) {PyErr_Format(PyExc_TypeError, "The pnp id must be a unicode object"); return NULL;}
    len = PyUnicode_GET_SIZE(o);
    if (len < 1) {PyErr_Format(PyExc_TypeError, "The pnp id must not be empty."); return NULL;}
    buf = (wchar_t *)calloc(len+2, sizeof(wchar_t));
    if (buf == NULL) { PyErr_NoMemory(); return NULL; }
    len = PyUnicode_AsWideChar((PyUnicodeObject*)o, buf, len);
    if (len == -1) { free(buf); PyErr_Format(PyExc_TypeError, "Invalid pnp id."); return NULL; }
    return buf;
}

static IPortableDeviceValues *get_client_information() {
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
}

static IPortableDevice *open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information) {
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

}

static PyObject* get_device_information(IPortableDevice *device) {
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
} 
// }}}

// Module startup/shutdown {{{
static PyObject *
wpd_init(PyObject *self, PyObject *args) {
    HRESULT hr;
    PyObject *o;
    if (!PyArg_ParseTuple(args, "OIII", &o, &client_info.major_version, &client_info.minor_version, &client_info.revision)) return NULL;
    client_info.name = unicode_to_wchar(o);
    if (client_info.name == NULL) return NULL;

    if (!_com_initialized) {
        Py_BEGIN_ALLOW_THREADS;
        hr = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) _com_initialized = 1;
        else {PyErr_SetString(WPDError, "Failed to initialize COM"); return NULL;}
    }

    if (portable_device_manager == NULL) {
        Py_BEGIN_ALLOW_THREADS;
        hr = CoCreateInstance(CLSID_PortableDeviceManager, NULL,
                CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&portable_device_manager));
        Py_END_ALLOW_THREADS;

        if (FAILED(hr)) {
            portable_device_manager = NULL;
            PyErr_SetString((hr == REGDB_E_CLASSNOTREG) ? NoWPD : WPDError, (hr == REGDB_E_CLASSNOTREG) ? 
                "This computer is not running the Windows Portable Device framework. You may need to install Windows Media Player 11 or newer." : 
                "Failed to create the WPD device manager interface");
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
wpd_uninit(PyObject *self, PyObject *args) {
    if (portable_device_manager != NULL) {
        Py_BEGIN_ALLOW_THREADS;
        portable_device_manager->Release();
        Py_END_ALLOW_THREADS;
        portable_device_manager = NULL;
    }

    if (_com_initialized) {
        Py_BEGIN_ALLOW_THREADS;
        CoUninitialize();
        Py_END_ALLOW_THREADS;
        _com_initialized = 0;
    }

    if (client_info.name != NULL) { free(client_info.name); }
    // hresult_set_exc("test", HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED)); return NULL;

    Py_RETURN_NONE;
}
// }}}

// enumerate_devices() {{{
static PyObject *
wpd_enumerate_devices(PyObject *self, PyObject *args) {
    PyObject *refresh = NULL, *ans = NULL, *temp;
    HRESULT hr;
    DWORD num_of_devices, i;
    PWSTR *pnp_device_ids;

    ENSURE_WPD(NULL);

    if (!PyArg_ParseTuple(args, "|O", &refresh)) return NULL;

    if (refresh != NULL && PyObject_IsTrue(refresh)) {
        Py_BEGIN_ALLOW_THREADS;
        hr = portable_device_manager->RefreshDeviceList();
        Py_END_ALLOW_THREADS;
        if (FAILED(hr)) return hresult_set_exc("Failed to refresh the list of portable devices", hr);
    }

    hr = portable_device_manager->GetDevices(NULL, &num_of_devices);
    num_of_devices += 15; // Incase new devices were connected between this call and the next
    if (FAILED(hr)) return hresult_set_exc("Failed to get number of devices on the system", hr);
    pnp_device_ids = (PWSTR*)calloc(num_of_devices, sizeof(PWSTR));
    if (pnp_device_ids == NULL) return PyErr_NoMemory();

    Py_BEGIN_ALLOW_THREADS;
    hr = portable_device_manager->GetDevices(pnp_device_ids, &num_of_devices);
    Py_END_ALLOW_THREADS;

    if (SUCCEEDED(hr)) {
        ans = PyTuple_New(num_of_devices);
        if (ans != NULL) {
            for(i = 0; i < num_of_devices; i++) {
                temp = PyUnicode_FromWideChar(pnp_device_ids[i], wcslen(pnp_device_ids[i]));
                if (temp == NULL) { PyErr_NoMemory(); Py_DECREF(ans); ans = NULL; break;}
                PyTuple_SET_ITEM(ans, i, temp);
            }
        }
    } else { 
        hresult_set_exc("Failed to get list of portable devices", hr);
    }

    for (i = 0; i < num_of_devices; i++) {
        Py_BEGIN_ALLOW_THREADS;
        CoTaskMemFree(pnp_device_ids[i]);
        Py_END_ALLOW_THREADS;
        pnp_device_ids[i] = NULL;
    }
    free(pnp_device_ids);
    pnp_device_ids = NULL;

    return Py_BuildValue("N", ans);
} // }}}

// device_info() {{{
static PyObject *
wpd_device_info(PyObject *self, PyObject *args) {
    PyObject *py_pnp_id, *ans = NULL;
    wchar_t *pnp_id;
    IPortableDeviceValues *client_information = NULL;
    IPortableDevice *device = NULL;

    ENSURE_WPD(NULL);

    if (!PyArg_ParseTuple(args, "O", &py_pnp_id)) return NULL;
    pnp_id = unicode_to_wchar(py_pnp_id);
    if (pnp_id == NULL) return NULL;

    client_information = get_client_information();
    if (client_information != NULL) {
        device = open_device(pnp_id, client_information);
        if (device != NULL) {
            ans = get_device_information(device);
        }
    }

    if (pnp_id != NULL) free(pnp_id);
    if (client_information != NULL) client_information->Release();
    if (device != NULL) {device->Close(); device->Release();}
    return ans;
} // }}}

static PyMethodDef wpd_methods[] = {
    {"init", wpd_init, METH_VARARGS,
        "init(name, major_version, minor_version, revision)\n\n Initializes this module. Call this method *only* in the thread in which you intend to use this module. Also remember to call uninit before the thread exits."
    },

    {"uninit", wpd_uninit, METH_VARARGS,
        "uninit()\n\n Uninitialize this module. Must be called in the same thread as init(). Do not use any function/objects from this module after uninit has been called."
    },

    {"enumerate_devices", wpd_enumerate_devices, METH_VARARGS,
        "enumerate_devices(refresh=False)\n\n Get the list of device PnP ids for all connected devices recognized by the WPD service. The result is cached, unless refresh=True. Do not call with refresh=True too often as it is resource intensive."
    },

    {"device_info", wpd_device_info, METH_VARARGS,
        "device_info(pnp_id)\n\n Return basic device information for the device identified by pnp_id (which you get from enumerate_devices)."
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initwpd(void) {
    PyObject *m;

    m = Py_InitModule3("wpd", wpd_methods, "Interface to the WPD windows service.");
    if (m == NULL) return;

    WPDError = PyErr_NewException("wpd.WPDError", NULL, NULL);
    if (WPDError == NULL) return;

    NoWPD = PyErr_NewException("wpd.NoWPD", NULL, NULL);
    if (NoWPD == NULL) return;
}


