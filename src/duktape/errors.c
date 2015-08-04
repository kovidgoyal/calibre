/*
 * errors.c
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "dukpy.h"

static int copy_error_attr(PyObject *obj, const char* name, PyObject *dest) {
    PyObject *value = NULL;
    if (!PyObject_HasAttrString(obj, name)) return NULL;
    value = PyObject_GetAttrString(obj, name);
    if (value == NULL) return 0;
    if (PyDict_SetItemString(dest, name, value) != 0) {Py_DECREF(value); return 0;}
    Py_DECREF(value);    
    return 1;
}

void set_dukpy_error(PyObject *obj) {
    PyObject *err = NULL, *iterator = NULL, *item = NULL;
    Py_ssize_t i = 0;
    if (Py_TYPE(obj) == &DukObject_Type) {
        err = PyDict_New();
        if (err == NULL) { PyErr_NoMemory(); return; }

        // Look for the common error object properties that may be up the prototype chain
        if (!copy_error_attr(obj, "name", err)) { Py_DECREF(err); return; }
        if (!copy_error_attr(obj, "message", err)) { Py_DECREF(err); return; }
        if (!copy_error_attr(obj, "fileName", err)) { Py_DECREF(err); return; }
        if (!copy_error_attr(obj, "lineNumber", err)) { Py_DECREF(err); return; }
        if (!copy_error_attr(obj, "stack", err)) { Py_DECREF(err); return; }
        
        // Now copy over own properties
        iterator = PyObject_CallMethod(obj, "items", NULL);
        if (iterator == NULL) { Py_DECREF(err); return; }
        while (item = PyIter_Next(iterator)) {
            PyDict_SetItem(err, PyTuple_GET_ITEM(item, 0), PyTuple_GET_ITEM(item, 1));
            Py_DECREF(item);
        }

        PyErr_SetObject(JSError, err);
        Py_DECREF(err); Py_DECREF(iterator);
    } else PyErr_SetObject(JSError, obj);
}
