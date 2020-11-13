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

static PyObject *EspeakError = NULL;

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

static PyObject*
set_espeak_error(const char *prefix, espeak_ERROR err, const char *file, const int line) {
	const char *m = "Unknown error";
	switch(err) {
		case EE_OK:
			m = "No error"; break;
		case EE_INTERNAL_ERROR:
			m = "Internal error"; break;
		case EE_BUFFER_FULL:
			m = "Buffer full"; break;
		case EE_NOT_FOUND:
			m = "Not found"; break;
	}
	PyErr_Format(EspeakError, "[%s:%d] %s: %s", file, line, prefix, m);
	return NULL;
}
#define espeak_error(prefix, err) set_espeak_error(prefix, err, __FILE__, __LINE__)

static PyObject*
set_voice_by_properties(PyObject *self, PyObject *args, PyObject *kw) {
	espeak_VOICE q = {0};
	static const char* kwds[] = {"name", "language", "gender", "age", "variant", NULL};
	if (!PyArg_ParseTupleAndKeywords(args, kw, "|$ssBBB", (char**)kwds, &q.name, &q.languages, &q.gender, &q.age, &q.variant)) return NULL;
	espeak_ERROR err = espeak_SetVoiceByProperties(&q);
	if (err != EE_OK) return espeak_error("Failed to set voice by properties", err);
	Py_RETURN_NONE;
}

static PyObject*
cancel(PyObject *self, PyObject *args) {
	espeak_ERROR err;
	Py_BEGIN_ALLOW_THREADS;
	err = espeak_Cancel();
	Py_END_ALLOW_THREADS;
	if (err != EE_OK) return espeak_error("Failed to cancel speech", err);
	Py_RETURN_NONE;
}

static PyObject*
is_playing(PyObject *self, PyObject *args) {
	int ans;
	Py_BEGIN_ALLOW_THREADS
	ans = espeak_IsPlaying();
	Py_END_ALLOW_THREADS
	return Py_BuildValue("O", ans ? Py_True : Py_False);

}

static PyObject*
synchronize(PyObject *self, PyObject *args) {
	espeak_ERROR err;
	Py_BEGIN_ALLOW_THREADS;
	err = espeak_Synchronize();
	Py_END_ALLOW_THREADS;
	if (err != EE_OK) return espeak_error("Failed to synchronize speech", err);
	Py_RETURN_NONE;
}


// Boilerplate {{{
#define M(name, args, doc) { #name, (PyCFunction)name, args, ""}
static PyMethodDef methods[] = {
	M(info, METH_NOARGS, "version and path"),
	M(cancel, METH_NOARGS, "cancel all ongoing speech activity"),
	M(synchronize, METH_NOARGS, "synchronize all ongoing speech activity"),
	M(is_playing, METH_NOARGS, "True iff speech is happening"),
	M(list_voices, METH_VARARGS | METH_KEYWORDS, "list available voices"),
	M(set_voice_by_properties, METH_VARARGS | METH_KEYWORDS, "set voice by properties"),
    {NULL, NULL, 0, NULL}
};
#undef M

static int
exec_module(PyObject *m) {
#define AI(name) if (PyModule_AddIntMacro(m, name) != 0) { return -1; }
#undef AI
    EspeakError = PyErr_NewException("espeak.EspeakError", NULL, NULL);
    if (EspeakError == NULL) return -1;
    PyModule_AddObject(m, "EspeakError", EspeakError);

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
