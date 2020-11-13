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

class pyobject_raii {
	private:
		PyObject *handle;
		pyobject_raii( const pyobject_raii & ) ;
		pyobject_raii & operator=( const pyobject_raii & ) ;

	public:
		pyobject_raii() : handle(NULL) {}
		pyobject_raii(PyObject* h) : handle(h) {}

		~pyobject_raii() { Py_CLEAR(handle); }

		PyObject *ptr() { return handle; }
		void set_ptr(PyObject *val) { handle = val; }
		PyObject **address() { return &handle; }
		explicit operator bool() const { return handle != NULL; }
        PyObject *detach() { PyObject *ans = handle; handle = NULL; return ans; }
};

static bool initialize_called = false;

static PyObject*
info(PyObject *self, PyObject *args) {
	const char *path_data;
	const char *version = espeak_Info(&path_data);
	return Py_BuildValue("ss", version, path_data);
}

static PyObject*
list_voices(PyObject *self, PyObject *args, PyObject *kw) {
	espeak_VOICE q = {0};
	static const char* kwds[] = {"name", "language", "identifier", "gender", "age", NULL};
	if (!PyArg_ParseTupleAndKeywords(args, kw, "|$sssBB", (char**)kwds, &q.name, &q.languages, &q.identifier, &q.gender, &q.age)) return NULL;
	const espeak_VOICE **voices;
	Py_BEGIN_ALLOW_THREADS;
	voices = espeak_ListVoices(&q);
	Py_END_ALLOW_THREADS;
	pyobject_raii ans(PyList_New(0));
	if (!ans) return NULL;
	while (*voices) {
		const espeak_VOICE *x = *voices;
		pyobject_raii languages(PyList_New(0));
		if (!languages) return NULL;
		const char *pos = x->languages;
		while (pos && *pos) {
			const char priority = *pos;
			size_t sz = strlen(++pos);
			if (!sz) break;
			pyobject_raii lang(Py_BuildValue("bs", priority, pos));
			if (!lang) return NULL;
			if (PyList_Append(languages.ptr(), lang.ptr()) != 0) return NULL;
			pos += sz + 1;
		}
		pyobject_raii entry(Py_BuildValue("{ss ss sO sB sB}",
					"name", x->name, "identifier", x->identifier, "languages", languages.ptr(),
					"gender", x->gender, "age", x->age));
		if (!entry) return NULL;
		if (PyList_Append(ans.ptr(), entry.ptr()) != 0) return NULL;
		voices++;
	}
	return ans.detach();
}

// Boilerplate {{{
#define M(name, args, doc) { #name, (PyCFunction)name, args, ""}
static PyMethodDef methods[] = {
	M(info, METH_VARARGS, "version and path"),
	M(list_voices, METH_VARARGS | METH_KEYWORDS, "list available voices"),
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
