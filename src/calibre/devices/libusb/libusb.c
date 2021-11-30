/*
 * libusb.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#ifdef __FreeBSD__
#include <libusb.h>
#else
#include <libusb-1.0/libusb.h>
#endif

static PyObject *Error = NULL;
static PyObject *cache = NULL;

static PyObject* format_err(int err) {
    PyErr_SetString(Error, libusb_error_name(err));
    return NULL;
}

static PyObject* read_string_property(libusb_device_handle *dev, uint8_t idx) {
    unsigned char buf[301];
    int err;
    PyObject *ans = NULL;

    Py_BEGIN_ALLOW_THREADS;
    err = libusb_get_string_descriptor_ascii(dev, idx, buf, 300);
    Py_END_ALLOW_THREADS;

    if (err > 0) {
        ans = PyUnicode_FromStringAndSize((char *)buf, err);
    }

    return ans;
}

static PyObject* read_string_data(libusb_device *dev, uint8_t manufacturer, uint8_t product, uint8_t serial) {
    libusb_device_handle *handle;
    int err;
    PyObject *ans = NULL, *p;

    ans = PyDict_New();
    if (ans == NULL) return PyErr_NoMemory();

    err = libusb_open(dev, &handle);

    if (err == 0) {
        p = read_string_property(handle, manufacturer);
        if (p != NULL) { PyDict_SetItemString(ans, "manufacturer", p); Py_DECREF(p); }

        p = read_string_property(handle, product);
        if (p != NULL) { PyDict_SetItemString(ans, "product", p); Py_DECREF(p); };

        p = read_string_property(handle, serial);
        if (p != NULL) { PyDict_SetItemString(ans, "serial", p); Py_DECREF(p); };

        libusb_close(handle);
    }

    return ans;
}

static PyObject* get_devices(PyObject *self, PyObject *args) {
    PyObject *ans = NULL, *d = NULL, *t = NULL, *rec = NULL;
    int err, i = 0;
    libusb_device **devs = NULL, *dev = NULL;
    ssize_t count;

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    Py_BEGIN_ALLOW_THREADS;
    count = libusb_get_device_list(NULL, &devs);
    Py_END_ALLOW_THREADS;
    if (count < 0) { Py_DECREF(ans); return format_err((int)count); }

    while ( (dev = devs[i++]) != NULL ) {
        struct libusb_device_descriptor desc;
        err = libusb_get_device_descriptor(dev, &desc);
        if (err != 0) { format_err(err); break; }
        if (desc.bDeviceClass == LIBUSB_CLASS_HUB) continue;

        d = Py_BuildValue("(BBHHH)", (unsigned char)libusb_get_bus_number(dev),
                (unsigned char)libusb_get_device_address(dev), (unsigned short)desc.idVendor, (unsigned short)desc.idProduct,
                (unsigned short)desc.bcdDevice);
        if (d == NULL) break;

        t = PyDict_GetItem(cache, d);
        if (t == NULL) {
            t = read_string_data(dev, desc.iManufacturer, desc.iProduct, desc.iSerialNumber);
            if (t == NULL) { Py_DECREF(d); break; }
            PyDict_SetItem(cache, d, t);
            Py_DECREF(t);
        }

        rec = Py_BuildValue("(NO)", d, t);
        if (rec == NULL) { Py_DECREF(d); break; }

        PyList_Append(ans, rec);
        Py_DECREF(rec);

    }

    if (dev != NULL) {
        // An error occurred
        Py_DECREF(ans); ans = NULL;
    }

    if (devs != NULL) libusb_free_device_list(devs, 1);

    return ans;
}

static char libusb_doc[] = "Interface to libusb.";

static PyMethodDef libusb_methods[] = {
    {"get_devices", get_devices, METH_NOARGS,
        "get_devices()\n\nGet the list of USB devices on the system."
    },

    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *m) {
    // We deliberately use the default context. This is the context used by
    // libmtp and we want to ensure that the busnum/devnum numbers are the same
    // here and for libmtp.
    if(libusb_init(NULL) != 0) return -1;

    Error = PyErr_NewException("libusb.Error", NULL, NULL);
    if (Error == NULL) return -1;
    cache = PyDict_New();
    if (cache == NULL) return -1;

    PyModule_AddObject(m, "Error", Error);
    PyModule_AddObject(m, "cache", cache);
	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "libusb",
    .m_doc      = libusb_doc,
    .m_methods  = libusb_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_libusb(void) { return PyModuleDef_Init(&module_def); }
