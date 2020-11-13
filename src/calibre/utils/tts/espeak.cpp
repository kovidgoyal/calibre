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

typedef struct {
	PyThreadState *thread_state;
	PyObject *data_callback, *err_type, *err_value, *err_traceback;
} CallbackData;

class ScopedGILAcquire {
public:
    inline ScopedGILAcquire(CallbackData *cbd) : data(cbd) {
		if (data && data->thread_state) {
			PyEval_RestoreThread(data->thread_state);
			data->thread_state = NULL;
		}
	}
    inline ~ScopedGILAcquire() { if (data) data->thread_state = PyEval_SaveThread(); }
private:
    CallbackData *data;
};

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

static PyObject*
set_parameter(PyObject *self, PyObject *args) {
	espeak_PARAMETER param;
	int value, relative = 0;
	if (!PyArg_ParseTuple(args, "ii|i", &param, &value, &relative)) return NULL;
	espeak_ERROR err;
	Py_BEGIN_ALLOW_THREADS;
	err = espeak_SetParameter(param, value, relative);
	Py_END_ALLOW_THREADS;
	if (err != EE_OK) return espeak_error("Failed to set set parameter", err);
	Py_RETURN_NONE;
}

static PyObject*
get_parameter(PyObject *self, PyObject *args) {
	espeak_PARAMETER param;
	int current = 1;
	if (!PyArg_ParseTuple(args, "i|i", &param, &current)) return NULL;
	long ans;
	Py_BEGIN_ALLOW_THREADS;
	ans = espeak_GetParameter(param, current);
	Py_END_ALLOW_THREADS;
	return PyLong_FromLong(ans);
}

static int
synth_callback(short* wav_data, int num_samples, espeak_EVENT *evt) {
	if (wav_data == NULL) return 0;
	CallbackData *cbdata = static_cast<CallbackData*>(evt->user_data);
	if (cbdata->data_callback) {
		ScopedGILAcquire sga(cbdata);
		PyObject *ret = PyObject_CallFunction(cbdata->data_callback, "y#", wav_data, num_samples * 2);
		if (!ret) {
			PyErr_Fetch(&cbdata->err_type, &cbdata->err_value, &cbdata->err_traceback);
			return 1;
		}
		int r = PyObject_IsTrue(ret) ? 1 : 0;
		Py_DECREF(ret);
		return r;
	}
	return 0;
}


static inline void
int_as_four_bytes(int32_t value, unsigned char *output) {
	output[0] = value & 0xff;
	output[1] = (value >> 8) & 0xff;
	output[2] = (value >> 16) & 0xff;
	output[3] = (value >> 24) & 0xff;
}


static PyObject*
create_recording_wav(PyObject *self, PyObject *args) {
	int buflength = 1000;
	unsigned int flags = 0;
	const char *text;
	Py_ssize_t text_len;
	CallbackData cbdata = {0};
	if (!PyArg_ParseTuple(args, "s#O|iI", &text, &text_len, &cbdata.data_callback, &buflength, &flags)) return NULL;
	espeak_Cancel();
	int rate = espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, buflength, NULL, espeakINITIALIZE_DONT_EXIT);
	if (rate == -1) return espeak_error("Initialization failed", EE_INTERNAL_ERROR);
	espeak_SetSynthCallback(synth_callback);
	unsigned char wave_hdr[44] = {
		'R', 'I', 'F', 'F', 0x24, 0xf0, 0xff, 0x7f, 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ',
		0x10, 0, 0, 0, 1, 0, 1, 0,  9, 0x3d, 0, 0, 0x12, 0x7a, 0, 0,
		2, 0, 0x10, 0, 'd', 'a', 't', 'a', 0x00, 0xf0, 0xff, 0x7f
	};
	int_as_four_bytes(rate, wave_hdr + 24);
	int_as_four_bytes(rate * 2, wave_hdr + 28);
	PyObject *ret = PyObject_CallFunction(cbdata.data_callback, "s#", wave_hdr, sizeof(wave_hdr));
	if (!ret) return NULL;
	Py_DECREF(ret);

	espeak_ERROR err;
	cbdata.thread_state = PyEval_SaveThread();
	err = espeak_Synth(text, text_len, 0, POS_CHARACTER, 0, flags | espeakCHARS_UTF8, NULL, &cbdata);
	if (cbdata.thread_state) PyEval_RestoreThread(cbdata.thread_state);
	if (cbdata.err_type) {
		PyErr_Restore(cbdata.err_type, cbdata.err_value, cbdata.err_traceback);
		return NULL;
	}
	if (err != EE_OK) return espeak_error("Failed to synthesize text", err);
	Py_RETURN_NONE;
}


// Boilerplate {{{
#define M(name, args, doc) { #name, (PyCFunction)name, args, ""}
static PyMethodDef methods[] = {
	M(info, METH_NOARGS, "version and path"),
	M(cancel, METH_NOARGS, "cancel all ongoing speech activity"),
	M(synchronize, METH_NOARGS, "synchronize all ongoing speech activity"),
	M(is_playing, METH_NOARGS, "True iff speech is happening"),
	M(set_parameter, METH_VARARGS, "set speech parameter"),
	M(get_parameter, METH_VARARGS, "get speech parameter"),
	M(create_recording_wav, METH_VARARGS, "save tts output as WAV"),
	M(list_voices, METH_VARARGS | METH_KEYWORDS, "list available voices"),
	M(set_voice_by_properties, METH_VARARGS | METH_KEYWORDS, "set voice by properties"),
    {NULL, NULL, 0, NULL}
};
#undef M

static int
exec_module(PyObject *m) {
#define AI(name) if (PyModule_AddIntConstant(m, #name, espeak##name) != 0) { return -1; }
	AI(RATE); AI(VOLUME); AI(PITCH); AI(RANGE); AI(PUNCTUATION); AI(CAPITALS); AI(WORDGAP);
	AI(SSML); AI(PHONEMES); AI(ENDPAUSE);
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
