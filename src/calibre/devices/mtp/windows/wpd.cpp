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

static int _com_initialized = 0;
static PyObject *WPDError = NULL;
static IPortableDeviceManager *portable_device_manager = NULL;

static PyObject *
wpd_init(PyObject *self, PyObject *args) {
    HRESULT hr;

    if (!_com_initialized) {
        hr = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
        if (SUCCEEDED(hr)) _com_initialized = 1;
        else {PyErr_SetString(WPDError, "Failed to initialize COM"); return NULL;}
    }

    if (portable_device_manager == NULL) {
        hr = CoCreateInstance(CLSID_PortableDeviceManager, NULL,
                CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&portable_device_manager));

        if (FAILED(hr)) {
            portable_device_manager = NULL;
            PyErr_SetString(WPDError, (hr == REGDB_E_CLASSNOTREG) ? 
                "This computer is not running the Windows Portable Device framework. You may need to install Windows Media Player 11 or newer." : 
                "Failed to create the WPD device manager interface");
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
wpd_uninit(PyObject *self, PyObject *args) {
    if (_com_initialized) {
        CoUninitialize();
        _com_initialized = 0;
    }

    if (portable_device_manager != NULL) {
        portable_device_manager->Release();
        portable_device_manager = NULL;
    }

    Py_RETURN_NONE;
}

static PyMethodDef wpd_methods[] = {
    {"init", wpd_init, METH_VARARGS,
        "init()\n\n Initializes this module. Call this method *only* in the thread in which you intend to use this module. Also remember to call uninit before the thread exits."
    },

    {"uninit", wpd_uninit, METH_VARARGS,
        "uninit()\n\n Uninitialize this module. Must be called in the same thread as init(). Do not use any function/objects from this module after uninit has been called."
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

}


