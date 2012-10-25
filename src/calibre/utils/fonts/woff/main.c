/*
 * main.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL2+ license.
 */


#define _UNICODE
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "woff.h"

static PyObject *WOFFError = NULL;

static PyObject* woff_err(uint32_t status) {
    const char *msg;
    switch(status) {
        case eWOFF_out_of_memory:
            return PyErr_NoMemory(); 
        case  eWOFF_invalid: 
            msg = "Invalid input data"; break;
        case eWOFF_compression_failure:
            msg = "Compression failed"; break;
        case eWOFF_bad_signature:
            msg = "Bad font signature"; break;
        case eWOFF_buffer_too_small:
            msg = "Buffer too small"; break;
        case eWOFF_bad_parameter:
            msg = "Bad parameter"; break;
        case eWOFF_illegal_order:
            msg = "Illegal order of WOFF chunks"; break;
        default:
            msg = "Unknown Error";
    }
    PyErr_SetString(WOFFError, msg);
    return NULL;
}

static PyObject*
to_woff(PyObject *self, PyObject *args) {
    const char *sfnt;
    char *woff = NULL;
    Py_ssize_t sz;
    uint32_t wofflen = 0, status = eWOFF_ok;
    PyObject *ans;

    if (!PyArg_ParseTuple(args, "s#", &sfnt, &sz)) return NULL;

    woff = (char*)woffEncode((uint8_t*)sfnt, sz, 0, 0, &wofflen, &status);

    if (WOFF_FAILURE(status) || woff == NULL) return woff_err(status);

    ans = Py_BuildValue("s#", woff, wofflen);
    free(woff);
    return ans;
}

static PyObject*
from_woff(PyObject *self, PyObject *args) {
    const char *woff;
    char *sfnt;
    Py_ssize_t sz;
    uint32_t sfntlen = 0, status = eWOFF_ok;
    PyObject *ans;

    if (!PyArg_ParseTuple(args, "s#", &woff, &sz)) return NULL;

    sfnt = (char*)woffDecode((uint8_t*)woff, sz, &sfntlen, &status);

    if (WOFF_FAILURE(status) || sfnt == NULL) return woff_err(status);
    ans = Py_BuildValue("s#", sfnt, sfntlen);
    free(sfnt);
    return ans;
}

static 
PyMethodDef methods[] = {
    {"to_woff", (PyCFunction)to_woff, METH_VARARGS,
     "to_woff(bytestring) -> Convert the sfnt data in bytestring to WOFF format (returned as a bytestring)."
    },

    {"from_woff", (PyCFunction)from_woff, METH_VARARGS,
     "from_woff(bytestring) -> Convert the woff data in bytestring to SFNT format (returned as a bytestring)."
    },


    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initwoff(void) {
    PyObject *m;

    m = Py_InitModule3(
            "woff", methods,
            "Convert to/from the WOFF<->sfnt font formats"
    );
    if (m == NULL) return;

    WOFFError = PyErr_NewException((char*)"woff.WOFFError", NULL, NULL);
    if (WOFFError == NULL) return;
    PyModule_AddObject(m, "WOFFError", WOFFError);
} 


