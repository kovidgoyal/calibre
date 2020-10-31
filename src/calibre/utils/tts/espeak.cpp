/*
 * espeak.cpp
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <Python.h>
#include <espeak-ng/speak_lib.h>

static bool initialize_called = false;

// Boilerplate {{{
#define M(name, args) { #name, (PyCFunction)name, args, ""}
static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};
#undef M

static int
exec_module(PyObject *m) {
#define AI(name) if (PyModule_AddIntMacro(m, name) != 0) { return -1; }
#undef AI
    int sample_rate = espeak_Initialize(AUDIO_OUTPUT_SYNCH_PLAYBACK, 0, NULL, espeakINITIALIZE_DONT_EXIT);
    if (sample_rate == -1) {
        PyErr_SetString(PyExc_OSError, "Failed to initialize espeak library, are the data files missing?");
        return 1;
    }
    initialize_called = true;
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

static void
finalize(void*) {
    if (initialize_called) {
        espeak_Terminate();
        initialize_called = false;
    }
}

CALIBRE_MODINIT_FUNC PyInit_espeak(void) {
    module_def.m_name     = "espeak";
    module_def.m_doc      = "espeak-ng wrapper";
    module_def.m_slots    = slots;
    module_def.m_free     = finalize;
    module_def.m_methods  = methods;
	return PyModuleDef_Init(&module_def);
}
