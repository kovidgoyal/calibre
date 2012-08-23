/*
 * mtp.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace wpd;

// Module exception types
PyObject *wpd::WPDError = NULL, *wpd::NoWPD = NULL, *wpd::WPDFileBusy = NULL;

// The global device manager
IPortableDeviceManager *wpd::portable_device_manager = NULL;

// Flag indicating if COM has been initialized
static int _com_initialized = 0;
// Application Info
wpd::ClientInfo wpd::client_info = {NULL, 0, 0, 0};

extern IPortableDeviceValues* wpd::get_client_information();
extern IPortableDevice* wpd::open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information);
extern PyObject* wpd::get_device_information(IPortableDevice *device, IPortableDevicePropertiesBulk **bulk_properties);

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

    Py_BEGIN_ALLOW_THREADS;
    hr = portable_device_manager->RefreshDeviceList();
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return hresult_set_exc("Failed to refresh the list of portable devices", hr);

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
    if (wcslen(pnp_id) < 1) { PyErr_SetString(WPDError, "The PNP id must not be empty."); return NULL; }
    if (pnp_id == NULL) return NULL;

    client_information = get_client_information();
    if (client_information != NULL) {
        device = open_device(pnp_id, client_information);
        if (device != NULL) {
            ans = get_device_information(device, NULL);
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
        "enumerate_devices()\n\n Get the list of device PnP ids for all connected devices recognized by the WPD service. Do not call too often as it is resource intensive."
    },

    {"device_info", wpd_device_info, METH_VARARGS,
        "device_info(pnp_id)\n\n Return basic device information for the device identified by pnp_id (which you get from enumerate_devices)."
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initwpd(void) {
    PyObject *m;

    wpd::DeviceType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&wpd::DeviceType) < 0)
        return;
 
    m = Py_InitModule3("wpd", wpd_methods, "Interface to the WPD windows service.");
    if (m == NULL) return;

    WPDError = PyErr_NewException("wpd.WPDError", NULL, NULL);
    if (WPDError == NULL) return;
    PyModule_AddObject(m, "WPDError", MTPError);

    NoWPD = PyErr_NewException("wpd.NoWPD", NULL, NULL);
    if (NoWPD == NULL) return;
    PyModule_AddObject(m, "NoWPD", MTPError);

    WPDFileBusy = PyErr_NewException("wpd.WPDFileBusy", NULL, NULL);
    if (WPDFileBusy == NULL) return;
    PyModule_AddObject(m, "WPDFileBusy", MTPError);

    Py_INCREF(&DeviceType);
    PyModule_AddObject(m, "Device", (PyObject *)&DeviceType);

}


