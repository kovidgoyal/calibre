/*
:mod:`libusb` -- Pythonic interface to libusb
=====================================================

.. module:: fontconfig
    :platform: Linux
    :synopsis: Pythonic interface to the libusb library

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2009

*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <libusb-1.0/libusb.h>

libusb_context *ctxt = NULL;

void cleanup() {
    if (ctxt != NULL) {
        libusb_exit(ctxt);
    }
}

PyObject*
py_libusb_scan(PyObject *self, PyObject *args) {
    libusb_device **list = NULL;
    struct libusb_device_descriptor dev;
    ssize_t ret = 0, i = 0;
    PyObject *ans, *pydev, *t;

    if (ctxt == NULL) return PyErr_NoMemory();

    ret = libusb_get_device_list(ctxt, &list);
    if (ret == LIBUSB_ERROR_NO_MEM) return PyErr_NoMemory();
    ans = PyTuple_New(ret);
    if (ans == NULL) return PyErr_NoMemory();

    for (i = 0; i < ret; i++) {
        if (libusb_get_device_descriptor(list[i], &dev) != 0) {
            PyTuple_SET_ITEM(ans, i, Py_None);
            continue;
        }
        pydev = PyTuple_New(3);
        if (pydev == NULL) return PyErr_NoMemory();

        t = PyInt_FromLong(dev.idVendor);
        if (t == NULL) return PyErr_NoMemory();
        PyTuple_SET_ITEM(pydev, 0, t);

        t = PyInt_FromLong(dev.idProduct);
        if (t == NULL) return PyErr_NoMemory();
        PyTuple_SET_ITEM(pydev, 1, t);

        t = PyInt_FromLong(dev.bcdDevice);
        if (t == NULL) return PyErr_NoMemory();
        PyTuple_SET_ITEM(pydev, 2, t);

        PyTuple_SET_ITEM(ans, i, pydev);
    }
    libusb_free_device_list(list, 1);

    return ans;
}

PyObject*
py_libusb_info(PyObject *self, PyObject *args) {
    unsigned long idVendor, idProduct, bcdDevice;
    ssize_t ret = 0, i = 0; int err = 0, n;
    libusb_device **list = NULL;
    libusb_device_handle *handle = NULL;
    struct libusb_device_descriptor dev;
    PyObject *ans, *t;
    unsigned char data[1000];

    if (ctxt == NULL) return PyErr_NoMemory();

    if (!PyArg_ParseTuple(args, "LLL", &idVendor, &idProduct, &bcdDevice))
		return NULL;

    ret = libusb_get_device_list(ctxt, &list);
    if (ret == LIBUSB_ERROR_NO_MEM) return PyErr_NoMemory();

    ans = PyDict_New();
    if (ans == NULL)  return PyErr_NoMemory();

    for (i = 0; i < ret; i++) {
        if (libusb_get_device_descriptor(list[i], &dev) != 0) continue;

        if (idVendor == dev.idVendor && idProduct == dev.idProduct && bcdDevice == dev.bcdDevice) {
            err = libusb_open(list[i], &handle);
            if (!err) {
                if (dev.iManufacturer) {
                    n = libusb_get_string_descriptor_ascii(handle, dev.iManufacturer, data, 1000);
                    if (n == LIBUSB_ERROR_TIMEOUT) {
                        libusb_close(handle);
                        err = libusb_open(list[i], &handle);
                        if (err) break;
                        n = libusb_get_string_descriptor_ascii(handle, dev.iManufacturer, data, 1000);
                    }
                    if (n > 0) {
                        t = PyBytes_FromStringAndSize((const char*)data, n);
                        if (t == NULL) return PyErr_NoMemory();
                        //Py_INCREF(t);
                        if (PyDict_SetItemString(ans, "manufacturer", t) != 0) return PyErr_NoMemory();
                    }
                }
                if (dev.iProduct) {
                    n = libusb_get_string_descriptor_ascii(handle, dev.iProduct, data, 1000);
                    if (n == LIBUSB_ERROR_TIMEOUT) {
                        libusb_close(handle);
                        err = libusb_open(list[i], &handle);
                        if (err) break;
                        n = libusb_get_string_descriptor_ascii(handle, dev.iManufacturer, data, 1000);
                    }
                    if (n > 0) {
                        t = PyBytes_FromStringAndSize((const char*)data, n);
                        if (t == NULL) return PyErr_NoMemory();
                        //Py_INCREF(t);
                        if (PyDict_SetItemString(ans, "product", t) != 0) return PyErr_NoMemory();
                    }
                }
                if (dev.iSerialNumber) {
                    n = libusb_get_string_descriptor_ascii(handle, dev.iSerialNumber, data, 1000);
                    if (n == LIBUSB_ERROR_TIMEOUT) {
                        libusb_close(handle);
                        err = libusb_open(list[i], &handle);
                        if (err) break;
                        n = libusb_get_string_descriptor_ascii(handle, dev.iManufacturer, data, 1000);
                    }
                    if (n > 0) {
                        t = PyBytes_FromStringAndSize((const char*)data, n);
                        if (t == NULL) return PyErr_NoMemory();
                        //Py_INCREF(t);
                        if (PyDict_SetItemString(ans, "serial", t) != 0) return PyErr_NoMemory();
                    }
                }

                libusb_close(handle);
            }
            break;
        }
    }
    libusb_free_device_list(list, 1);


    if (err != 0) {
        switch (err) {
            case LIBUSB_ERROR_NO_MEM:
                return PyErr_NoMemory();
            case LIBUSB_ERROR_ACCESS:
                PyErr_SetString(PyExc_ValueError, "Dont have permission to access this device");
                return NULL;
            case LIBUSB_ERROR_NO_DEVICE:
                PyErr_SetString(PyExc_ValueError, "Device disconnected");
                return NULL;
            default:
                PyErr_SetString(PyExc_ValueError, "Failed to open device");
                return NULL;
        }
    }

    return ans;
}


static 
PyMethodDef libusb_methods[] = {
    {"scan", py_libusb_scan, METH_VARARGS,
    "scan()\n\n"
    		"Return USB devices currently connected to system as a tuple of "
            "3-tuples. Each 3-tuple has (idVendor, idProduct, bcdDevice)."
    },

    {"info", py_libusb_info, METH_VARARGS,
        "info(idVendor, idProduct, bcdDevice)\n\n"
    	"Return extra information about the specified device. "
    },

    {NULL, NULL, 0, NULL}

};

PyMODINIT_FUNC
initlibusb(void) {
    PyObject *m;
    m = Py_InitModule3(
            "libusb", libusb_methods,
            "Interface with USB devices on system."
    );
    if (m == NULL) return;
    if (libusb_init(&ctxt) != 0) ctxt = NULL;
    Py_AtExit(cleanup);
}

