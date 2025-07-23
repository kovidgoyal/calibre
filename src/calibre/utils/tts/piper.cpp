/*
 * piper.cpp
 * Copyright (C) 2025 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <espeak-ng/speak_lib.h>

static PyObject*
phonemize(PyObject *self, PyObject *args) {
    Py_RETURN_NONE;
}

// Boilerplate {{{
static char doc[] = "Text to speech using the Piper TTS models";
static PyMethodDef methods[] = {
    {"phonemize", (PyCFunction)phonemize, METH_VARARGS,
     "Convert the specified text into espeak-ng phonemes"
    },
    {NULL}  /* Sentinel */
};
static int
exec_module(PyObject *mod) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_piper(void) {
	module_def.m_name = "piper";
	module_def.m_slots = slots;
	module_def.m_doc = doc;
	module_def.m_methods = methods;
	return PyModuleDef_Init(&module_def);
}
// }}}
