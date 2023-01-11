/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <collection.h>
#include <winrt/base.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <windows.foundation.h>
#include <windows.media.speechsynthesis.h>
#include <windows.storage.streams.h>

using namespace Windows::Foundation;
using namespace Windows::Foundation::Collections;
using namespace Windows::Media::SpeechSynthesis;
using namespace Windows::Storage::Streams;

typedef struct {
    PyObject_HEAD
    SpeechSynthesizer ^synth;
} Synthesizer;


static PyTypeObject SynthesizerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static PyObject *
Synthesizer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) { INITIALIZE_COM_IN_FUNCTION
	Synthesizer *self = (Synthesizer *) type->tp_alloc(type, 0);
    if (self) {
        self->synth = ref new SpeechSynthesizer();
    }
    if (self && !PyErr_Occurred()) com.detach();
    return (PyObject*)self;
}

static void
Synthesizer_dealloc(Synthesizer *self) {
    self->synth = nullptr;
    CoUninitialize();
}

static PyObject*
voice_as_dict(VoiceInformation ^voice) {
    const char *gender = "";
    switch (voice->Gender) {
        case VoiceGender::Male: gender = "male"; break;
        case VoiceGender::Female: gender = "female"; break;
    }
    return Py_BuildValue("{su su su su ss}",
        "display_name", voice->DisplayName? voice->DisplayName->Data() : NULL,
        "description", voice->Description ? voice->Description->Data() : NULL,
        "id", voice->Id ? voice->Id->Data(): NULL,
        "language", voice->Language ? voice->Language->Data() : NULL,
        "gender", gender
    );
}

static PyObject*
all_voices(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    IVectorView<VoiceInformation^>^ voices = SpeechSynthesizer::AllVoices;
    pyobject_raii ans(PyTuple_New(voices->Size));
    if (!ans) return NULL;
    Py_ssize_t i = 0;
    for(auto voice : voices) {
        PyObject *v = voice_as_dict(voice);
        if (v) {
            PyTuple_SET_ITEM(ans.ptr(), i++, v);
        } else {
            return NULL;
        }
    }
    return ans.detach();
}

static PyObject*
default_voice(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    return voice_as_dict(SpeechSynthesizer::DefaultVoice);
}

#define M(name, args) { #name, (PyCFunction)Synthesizer_##name, args, ""}
static PyMethodDef Synthesizer_methods[] = {
    {NULL, NULL, 0, NULL}
};
#undef M

#define M(name, args) { #name, name, args, ""}
static PyMethodDef methods[] = {
    M(all_voices, METH_NOARGS),
    M(default_voice, METH_NOARGS),
    {NULL, NULL, 0, NULL}
};
#undef M


static int
exec_module(PyObject *m) {
    SynthesizerType.tp_name = "winspeech.Synthesizer";
    SynthesizerType.tp_doc = "Wrapper for SpeechSynthesizer";
    SynthesizerType.tp_basicsize = sizeof(Synthesizer);
    SynthesizerType.tp_itemsize = 0;
    SynthesizerType.tp_flags = Py_TPFLAGS_DEFAULT;
    SynthesizerType.tp_new = Synthesizer_new;
    SynthesizerType.tp_methods = Synthesizer_methods;
	SynthesizerType.tp_dealloc = (destructor)Synthesizer_dealloc;
	if (PyType_Ready(&SynthesizerType) < 0) return -1;

	Py_INCREF(&SynthesizerType);
    if (PyModule_AddObject(m, "Synthesizer", (PyObject *) &SynthesizerType) < 0) {
        Py_DECREF(&SynthesizerType);
        return -1;
    }

    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_winspeech(void) {
    module_def.m_name     = "winspeech";
    module_def.m_doc      = "Windows Speech API wrapper";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
