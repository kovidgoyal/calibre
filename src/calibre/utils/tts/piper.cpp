/*
 * piper.cpp
 * Copyright (C) 2025 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <espeak-ng/speak_lib.h>

#define CLAUSE_INTONATION_FULL_STOP 0x00000000
#define CLAUSE_INTONATION_COMMA 0x00001000
#define CLAUSE_INTONATION_QUESTION 0x00002000
#define CLAUSE_INTONATION_EXCLAMATION 0x00003000

#define CLAUSE_TYPE_CLAUSE 0x00040000
#define CLAUSE_TYPE_SENTENCE 0x00080000

#define CLAUSE_PERIOD (40 | CLAUSE_INTONATION_FULL_STOP | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_COMMA (20 | CLAUSE_INTONATION_COMMA | CLAUSE_TYPE_CLAUSE)
#define CLAUSE_QUESTION (40 | CLAUSE_INTONATION_QUESTION | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_EXCLAMATION                                                     \
    (45 | CLAUSE_INTONATION_EXCLAMATION | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_COLON (30 | CLAUSE_INTONATION_FULL_STOP | CLAUSE_TYPE_CLAUSE)
#define CLAUSE_SEMICOLON (30 | CLAUSE_INTONATION_COMMA | CLAUSE_TYPE_CLAUSE)

static bool initialized = false, voice_set = false;

static PyObject*
initialize(PyObject *self, PyObject *args) {
    const char *path = NULL;
    if (!PyArg_ParseTuple(args, "|s", &path)) return NULL;
    if (initialized) { PyErr_SetString(PyExc_Exception, "initialize() already called"); return NULL; }
    if (path && !path[0]) path = NULL;  // use default path
    if (espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, path, 0) < 0) {
        PyErr_Format(PyExc_ValueError, "Could not initialize espeak-ng with datadir: %s", path ? path : "<default>");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject*
set_espeak_voice_by_name(PyObject *self, PyObject *pyname) {
    if (!PyUnicode_Check(pyname)) { PyErr_SetString(PyExc_TypeError, "name must be a unicode string"); return NULL; }
    if (!initialized) { PyErr_SetString(PyExc_Exception, "must call initialize() first"); return NULL; }
    if (espeak_SetVoiceByName(PyUnicode_AsUTF8(pyname)) < 0) {
        PyErr_Format(PyExc_ValueError, "failed to set voice: %U", pyname);
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject*
phonemize(PyObject *self, PyObject *pytext) {
    if (!PyUnicode_Check(pytext)) { PyErr_SetString(PyExc_TypeError, "text must be a unicode string"); return NULL; }
    if (!initialized) { PyErr_SetString(PyExc_Exception, "must call initialize() first"); return NULL; }
    if (!voice_set) { PyErr_SetString(PyExc_Exception, "must set the espeak voice first"); return NULL; }
    PyObject *phonemes_and_terminators = PyList_New(0);
    if (!phonemes_and_terminators) return NULL;
    const char *text = PyUnicode_AsUTF8(pytext);

    while (text != NULL) {
        int terminator = 0;
        const char *terminator_str = "", *phonemes;
        Py_BEGIN_ALLOW_THREADS;
        phonemes = espeak_TextToPhonemesWithTerminator(
            (const void **)&text, espeakCHARS_UTF8, espeakPHONEMES_IPA, &terminator);
        Py_END_ALLOW_THREADS;
        // Categorize terminator
        terminator &= 0x000FFFFF;
        switch(terminator) {
            case CLAUSE_PERIOD: terminator_str = "."; break;
            case CLAUSE_QUESTION: terminator_str = "?"; break;
            case CLAUSE_EXCLAMATION: terminator_str = "!"; break;
            case CLAUSE_COMMA: terminator_str = ","; break;
            case CLAUSE_COLON: terminator_str = ":"; break;
            case CLAUSE_SEMICOLON: terminator_str = ";"; break;
        }
        PyObject *item = Py_BuildValue("(ssO)", phonemes, terminator_str, (terminator & CLAUSE_TYPE_SENTENCE) != 0 ? Py_True : Py_False);
        if (item == NULL) { Py_CLEAR(phonemes_and_terminators); return NULL; }
        int ret = PyList_Append(phonemes_and_terminators, item);
        Py_CLEAR(item);
        if (ret != 0) { Py_CLEAR(phonemes_and_terminators); return NULL; }
    }
    return phonemes_and_terminators;
}

// Boilerplate {{{
static char doc[] = "Text to speech using the Piper TTS models";
static PyMethodDef methods[] = {
    {"initialize", (PyCFunction)initialize, METH_VARARGS,
     "initialize(espeak_data_dir) -> Initialize this module. Must be called once before using any other functions from this module. If espeak_data_dir is not specified or is the mepty string the default data location is used."
    },
    {"set_espeak_voice_by_name", (PyCFunction)set_espeak_voice_by_name, METH_O,
     "set_espeak_voice_by_name(name) -> Set the voice to be used to phonemize text"
    },
    {"phonemize", (PyCFunction)phonemize, METH_O,
     "phonemize(text) -> Convert the specified text into espeak-ng phonemes"
    },
    {NULL}  /* Sentinel */
};

static int
exec_module(PyObject *mod) {
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

static void
cleanup_module(void*) {
    if (initialized) {
        initialized = false;
        voice_set = false;
        espeak_Terminate();
    }
}

CALIBRE_MODINIT_FUNC PyInit_piper(void) {
	module_def.m_name = "piper";
	module_def.m_slots = slots;
	module_def.m_doc = doc;
	module_def.m_methods = methods;
    module_def.m_free = cleanup_module;
	return PyModuleDef_Init(&module_def);
}
// }}}
