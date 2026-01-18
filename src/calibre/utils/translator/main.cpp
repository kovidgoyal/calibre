/*
 * main.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE

#include <Python.h>
#include "mo_parser.h"

typedef struct {
    PyObject_HEAD

    PyObject *fallback;
    MOParser parser;
} Translator;

extern PyTypeObject Translator_Type;

static PyObject *
new_translator(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    const char *mo_data = NULL; Py_ssize_t sz = 0;
    if (!PyArg_ParseTuple(args, "|z#", &mo_data, &sz)) return NULL;
    Translator *self = (Translator *)(&Translator_Type)->tp_alloc(&Translator_Type, 0);
    if (self != NULL) {
        new (&self->parser) MOParser();
        if (mo_data != NULL) {
            std::string err = self->parser.load(mo_data, sz);
            if (err.size()) {
                Py_CLEAR(self);
                PyErr_SetString(PyExc_ValueError, err.c_str()); return NULL;
            }
        }
    }
    return (PyObject*) self;
}

static void
dealloc_translator(Translator* self) {
    Py_CLEAR(self->fallback);
    self->parser.~MOParser();
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
plural(PyObject *self_, PyObject *pn) {
    if (!PyLong_Check(pn)) { PyErr_SetString(PyExc_TypeError, "n must be an integer"); return NULL; }
    unsigned long n = PyLong_AsUnsignedLong(pn);
    Translator *self = (Translator*)self_;
    return PyLong_FromUnsignedLong(self->parser.plural(n));
}

static PyMethodDef translator_methods[] = {
    {"plural", plural, METH_O, "plural(n: int) -> int:\n\n"
    		"Get the message catalog index based on the plural form specification."
    },
    {NULL}  /* Sentinel */
};

PyTypeObject Translator_Type = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "translator.Translator",
    .tp_basicsize = sizeof(Translator),
    .tp_dealloc = (destructor)dealloc_translator,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "Translator",
    .tp_methods = translator_methods,
    .tp_new = new_translator,
};


static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *m) {
    if (PyType_Ready(&Translator_Type) < 0) return -1;
    if (PyModule_AddObject(m, "Translator", (PyObject *)&Translator_Type) != 0) return -1;
    Py_INCREF(&Translator_Type);
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_translator(void) {
    module_def.m_name     = "translator";
    module_def.m_doc      = "Support for GNU gettext translations without holding the GIL so that it can be used in Qt as well";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
