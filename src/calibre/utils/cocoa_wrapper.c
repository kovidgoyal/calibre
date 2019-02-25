/*
 * cocoa_wrapper.c
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Python.h>

extern double cocoa_cursor_blink_time(void);

static PyObject*
cursor_blink_time(PyObject *self) {
    (void)self;
    double ans = cocoa_cursor_blink_time();
    return PyFloat_FromDouble(ans);
}

static PyMethodDef module_methods[] = {
    {"cursor_blink_time", (PyCFunction)cursor_blink_time, METH_NOARGS, ""},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};


#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
#define INITMODULE PyModule_Create(&bzzdec_module)
static struct PyModuleDef cocoa_module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "cocoa",
    /* m_doc      */ "",
    /* m_size     */ -1,
    /* m_methods  */ module_methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};
CALIBRE_MODINIT_FUNC PyInit_cocoa(void) {
#else
#define INITERROR return
#define INITMODULE Py_InitModule3("cocoa", module_methods, "")
CALIBRE_MODINIT_FUNC initcocoa(void) {
#endif

    PyObject *m = INITMODULE;
    if (m == NULL) {
        INITERROR;
    }
#if PY_MAJOR_VERSION >= 3
    return m;
#endif
}
