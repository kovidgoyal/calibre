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
CComPtr<IPortableDeviceManager> wpd::portable_device_manager = NULL;

// Flag indicating if COM has been initialized
static int _com_initialized = 0;
// Application Info
class ClientInfo {
    public:
        wchar_raii name;
        unsigned int major_version;
        unsigned int minor_version;
        unsigned int revision;
        ClientInfo() : name(), major_version(0), minor_version(0), revision(0) {}
};
static ClientInfo client_info;

IPortableDeviceValues* wpd::get_client_information() { // {{{
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

// Module startup/shutdown {{{
static PyObject *
wpd_init(PyObject *self, PyObject *args) {
    HRESULT hr;
    if (!PyArg_ParseTuple(args, "O&III", py_to_wchar_no_none, &client_info.name, &client_info.major_version, &client_info.minor_version, &client_info.revision)) return NULL;

    if (!_com_initialized) {
        Py_BEGIN_ALLOW_THREADS;
        hr = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) _com_initialized = 1;
        else {PyErr_SetString(WPDError, "Failed to initialize COM"); return NULL;}
    }

    if (!portable_device_manager) {
        Py_BEGIN_ALLOW_THREADS;
        hr = portable_device_manager.CoCreateInstance(CLSID_PortableDeviceManager, NULL, CLSCTX_INPROC_SERVER);
        Py_END_ALLOW_THREADS;

        if (FAILED(hr)) {
            portable_device_manager.Release();
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
    if (portable_device_manager) {
        Py_BEGIN_ALLOW_THREADS;
        portable_device_manager.Release();
        Py_END_ALLOW_THREADS;
    }

    if (_com_initialized) {
        Py_BEGIN_ALLOW_THREADS;
        CoUninitialize();
        Py_END_ALLOW_THREADS;
        _com_initialized = 0;
    }

    client_info.name.release();
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

    Py_BEGIN_ALLOW_THREADS;
    hr = portable_device_manager->GetDevices(NULL, &num_of_devices);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return hresult_set_exc("Failed to get number of devices on the system", hr);
    num_of_devices += 15; // In case new devices were connected between this call and the next
    pnp_device_ids = (PWSTR*)calloc(num_of_devices, sizeof(PWSTR));
    if (pnp_device_ids == NULL) return PyErr_NoMemory();

    Py_BEGIN_ALLOW_THREADS;
    hr = portable_device_manager->GetDevices(pnp_device_ids, &num_of_devices);
    Py_END_ALLOW_THREADS;

    if (SUCCEEDED(hr)) {
        ans = PyTuple_New(num_of_devices);
        if (ans != NULL) {
            for(i = 0; i < num_of_devices; i++) {
                temp = PyUnicode_FromWideChar(pnp_device_ids[i], -1);
                if (temp == NULL) { PyErr_NoMemory(); Py_DECREF(ans); ans = NULL; break;}
                PyTuple_SET_ITEM(ans, i, temp);
            }
        }
    } else {
        hresult_set_exc("Failed to get list of portable devices", hr);
    }

    Py_BEGIN_ALLOW_THREADS;
    for (i = 0; i < num_of_devices; i++) {
        CoTaskMemFree(pnp_device_ids[i]);
        pnp_device_ids[i] = NULL;
    }
    free(pnp_device_ids);
    pnp_device_ids = NULL;
    Py_END_ALLOW_THREADS;

    return ans;
} // }}}

// device_info() {{{
static PyObject *
wpd_device_info(PyObject *self, PyObject *args) {
    PyObject *ans = NULL;
    CComPtr<IPortableDevice> device = NULL;

    ENSURE_WPD(NULL);

    wchar_raii pnp_id;
    if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &pnp_id)) return NULL;
    if (wcslen(pnp_id.ptr()) < 1) { PyErr_SetString(WPDError, "The PNP id must not be empty."); return NULL; }

    CComPtr<IPortableDeviceValues> client_information = get_client_information();
    if (client_information) {
        device = open_device(pnp_id.ptr(), client_information);
        CComPtr<IPortableDevicePropertiesBulk> properties_bulk;
        if (device) ans = get_device_information(device, properties_bulk);
    }

    if (device) device->Close();
    return ans;
} // }}}

static char wpd_doc[] = "Interface to the WPD windows service.";

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

static int
exec_module(PyObject *m) {
    wpd::DeviceType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&wpd::DeviceType) < 0) return -1;

    WPDError = PyErr_NewException("wpd.WPDError", NULL, NULL);
    if (WPDError == NULL) return -1;
    PyModule_AddObject(m, "WPDError", WPDError);

    NoWPD = PyErr_NewException("wpd.NoWPD", NULL, NULL);
    if (NoWPD == NULL) return -1;
    PyModule_AddObject(m, "NoWPD", NoWPD);

    WPDFileBusy = PyErr_NewException("wpd.WPDFileBusy", NULL, NULL);
    if (WPDFileBusy == NULL) return -1;
    PyModule_AddObject(m, "WPDFileBusy", WPDFileBusy);

    Py_INCREF(&DeviceType);
    PyModule_AddObject(m, "Device", (PyObject *)&DeviceType);
	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_wpd(void) {
	module_def.m_name = "wpd";
	module_def.m_slots = slots;
	module_def.m_doc = wpd_doc;
	module_def.m_methods = wpd_methods;
	return PyModuleDef_Init(&module_def);
}
