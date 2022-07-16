/*
 * uchardet.c
 * Copyright (C) 2022 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "Python.h"
#include <uchardet.h>

#define CAPSULE_NAME "uchardet.detector_capsule"
#define CAPSULE_ATTR "detector_capsule"

static PyObject*
detect(PyObject *self, PyObject *bytes) {
    if (!PyBytes_Check(bytes)) { PyErr_SetString(PyExc_TypeError, "a byte string is required"); return NULL; }
    PyObject *capsule = PyObject_GetAttrString(self, CAPSULE_ATTR);
    if (!capsule) return NULL;
    void *d = PyCapsule_GetPointer(capsule, CAPSULE_NAME);
    if (!d) return NULL;
    uchardet_reset(d);
    uchardet_handle_data(d, PyBytes_AS_STRING(bytes), (size_t)PyBytes_GET_SIZE(bytes));
    uchardet_data_end(d);
    return PyUnicode_FromString(uchardet_get_charset(d));
}

static PyMethodDef methods[] = {
    {"detect", detect, METH_O,
    "detect(bytestring) -> encoding name\n\n"
    		"Detect the encoding of the specified bytestring"
    },
    {NULL, NULL, 0, NULL}
};


static void
free_detector(PyObject *capsule) {
    void *d = PyCapsule_GetPointer(capsule, CAPSULE_NAME);
    if (d) uchardet_delete(d);
}

static int
exec_module(PyObject *module) {
    uchardet_t detector = uchardet_new();
    if (!detector) { PyErr_NoMemory(); return -1; }
    PyObject *detector_capsule = PyCapsule_New(detector, CAPSULE_NAME, free_detector);
    if (!detector_capsule) return -1;
    int ret = PyModule_AddObjectRef(module, CAPSULE_ATTR, detector_capsule);
    Py_DECREF(detector_capsule);
    return ret;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "uchardet",
    .m_doc      = "Detect the encoding of bytestring",
    .m_methods  = methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_uchardet(void) {
    return PyModuleDef_Init(&module_def);
}
