/*
 * piper.cpp
 * Copyright (C) 2025 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <espeak-ng/speak_lib.h>
#include <vector>
#include <map>
#include <memory>
#include <onnxruntime_cxx_api.h>

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

typedef char32_t Phoneme;
typedef int64_t PhonemeId;
typedef int64_t SpeakerId;
typedef std::map<Phoneme, std::vector<PhonemeId>> PhonemeIdMap;

static bool initialized = false, voice_set = false;
static char espeak_data_dir[512] = {0};
static PhonemeIdMap current_phoneme_id_map;
static int current_sample_rate = 0;
static int current_num_speakers = 1;
static float current_length_scale = 1;
static float current_noise_scale = 1;
static float current_noise_w  = 1;
std::unique_ptr<Ort::Session> session;

static PyObject*
initialize(PyObject *self, PyObject *args) {
    const char *path = "";
    if (!PyArg_ParseTuple(args, "|s", &path)) return NULL;
    if (!initialized || strcmp(espeak_data_dir, path) != 0) {
        if (espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, path && path[0] ? path : NULL, 0) < 0) {
            PyErr_Format(PyExc_ValueError, "Could not initialize espeak-ng with datadir: %s", path ? path : "<default>");
            return NULL;
        }
        initialized = true;
        snprintf(espeak_data_dir, sizeof(espeak_data_dir), "%s", path);
    }
    Py_RETURN_NONE;
}

static PyObject*
set_espeak_voice_by_name(PyObject *self, PyObject *pyname) {
    if (!PyUnicode_Check(pyname)) { PyErr_SetString(PyExc_TypeError, "espeak voice name must be a unicode string"); return NULL; }
    if (!initialized) { PyErr_SetString(PyExc_Exception, "must call initialize() first"); return NULL; }
    if (espeak_SetVoiceByName(PyUnicode_AsUTF8(pyname)) < 0) {
        PyErr_Format(PyExc_ValueError, "failed to set espeak voice: %U", pyname);
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

static PyObject*
set_voice(PyObject *self, PyObject *args) {
    PyObject *cfg; const char *model_path;
    if (!PyArg_ParseTuple(args, "Os", &cfg, &model_path)) return NULL;

    PyObject *evn = PyObject_GetAttrString(cfg, "espeak_voice_name");
    if (!evn) return NULL;
    PyObject *ret = set_espeak_voice_by_name(NULL, evn);
    Py_CLEAR(evn);
    if (ret == NULL) return NULL;
    Py_DECREF(ret);

#define G(name, dest, conv) { \
        PyObject *sr = PyObject_GetAttrString(cfg, #name); \
        if (!sr) return NULL; \
        dest = conv(sr); \
        Py_CLEAR(sr); \
}
    G(sample_rate, current_sample_rate, PyLong_AsLong);
    G(num_speakers, current_num_speakers, PyLong_AsLong);
    G(length_scale, current_length_scale, PyFloat_AsDouble);
    G(noise_scale, current_noise_scale, PyFloat_AsDouble);
    G(noise_w, current_noise_w, PyFloat_AsDouble);
#undef G

    PyObject *map = PyObject_GetAttrString(cfg, "phoneme_id_map");
    if (!map) return NULL;
    current_phoneme_id_map.clear();
    PyObject *key, *value; Py_ssize_t pos = 0;
    while (PyDict_Next(map, &pos, &key, &value)) {
        unsigned long cp = PyLong_AsUnsignedLong(key);
        std::vector<PhonemeId> ids;
        for (Py_ssize_t i = 0; i < PyList_GET_SIZE(value); i++) {
            unsigned long id = PyLong_AsUnsignedLong(PyList_GET_ITEM(value, i));
            ids.push_back(id);
        }
        current_phoneme_id_map[cp] = ids;
    }
    Py_CLEAR(map);

    // Load onnx model
    Ort::SessionOptions opts;
    opts.DisableCpuMemArena();
    opts.DisableMemPattern();
    opts.DisableProfiling();
    Ort::Env ort_env{ORT_LOGGING_LEVEL_WARNING, "piper"};
    session.reset();
    session = std::make_unique<Ort::Session>(Ort::Session(ort_env, model_path, opts));

    Py_RETURN_NONE;
}

// Boilerplate {{{
static char doc[] = "Text to speech using the Piper TTS models";
static PyMethodDef methods[] = {
    {"initialize", (PyCFunction)initialize, METH_VARARGS,
     "initialize(espeak_data_dir) -> Initialize this module. Must be called once before using any other functions from this module. If espeak_data_dir is not specified or is the mepty string the default data location is used."
    },
    {"set_voice", (PyCFunction)set_voice, METH_VARARGS,
     "set_voice(voice_config, model_path) -> Load the model in preparation for synthesis."
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
    current_phoneme_id_map.clear();
    session.reset();
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
