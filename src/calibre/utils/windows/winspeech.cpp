/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <array>
#include <deque>
#include <memory>
#include <mutex>
#include <functional>
#include <unordered_map>
#include <winrt/base.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Storage.Streams.h>
#include <winrt/Windows.Media.SpeechSynthesis.h>
#include <winrt/Windows.Media.Core.h>
#include <winrt/Windows.Media.Playback.h>

using namespace winrt::Windows::Foundation;
using namespace winrt::Windows::Foundation::Collections;
using namespace winrt::Windows::Media::SpeechSynthesis;
using namespace winrt::Windows::Media::Playback;
using namespace winrt::Windows::Media::Core;
using namespace winrt::Windows::Storage::Streams;
typedef unsigned long long id_type;

static PyObject*
runtime_error_as_python_error(PyObject *exc_type, winrt::hresult_error const &ex, const char *file, const int line, const char *prefix="", PyObject *name=NULL) {
    pyobject_raii msg(PyUnicode_FromWideChar(ex.message().c_str(), -1));
    const HRESULT hr = ex.to_abi();
    if (name) PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x] %V: %S", file, line, prefix, hr, msg.ptr(), "Out of memory", name);
    else PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x] %V", file, line, prefix, hr, msg.ptr(), "Out of memory");
    return NULL;
}
#define set_python_error_from_runtime(ex, ...) runtime_error_as_python_error(PyExc_OSError, ex, __FILE__, __LINE__, __VA_ARGS__)

template<typename T>
class WeakRefs {
    private:
    std::mutex weak_ref_lock;
    std::unordered_map<id_type, T*> refs;
    id_type counter;
    public:
    void register_ref(T *self) {
        std::scoped_lock lock(weak_ref_lock);
        self->id = ++counter;
        refs[self->id] = self;
    }
    void unregister_ref(T *self, std::function<void(T*)> dealloc) {
        std::scoped_lock lock(weak_ref_lock);
        dealloc(self);
        refs.erase(self->id);
        self->id = 0;
    }
    void use_ref(id_type id, DWORD creation_thread_id, std::function<void(T*)> callback) {
        if (GetCurrentThreadId() == creation_thread_id) {
            try {
                callback(at(id));
            } catch (std::out_of_range) {
                callback(NULL);
            }
        }
        else {
            std::scoped_lock lock(weak_ref_lock);
            try {
                callback(at(id));
            } catch (std::out_of_range) {
                callback(NULL);
            }
        }
    }
};

struct Synthesizer {
    PyObject_HEAD
    id_type id;
    DWORD creation_thread_id;
    SpeechSynthesizer synth{nullptr};
    MediaPlayer player{nullptr};
};

static PyTypeObject SynthesizerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static WeakRefs<Synthesizer> synthesizer_weakrefs;


static PyObject*
Synthesizer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) { INITIALIZE_COM_IN_FUNCTION
	Synthesizer *self = (Synthesizer *) type->tp_alloc(type, 0);
    if (self) {
        try {
            self->synth = SpeechSynthesizer();
            self->player = MediaPlayer();
            self->player.AudioCategory(MediaPlayerAudioCategory::Speech);
        } catch(winrt::hresult_error const& ex) {
            set_python_error_from_runtime(ex, "Failed to get SpeechSynthesisStream from text");
            Py_CLEAR(self);
        }
    }
    if (PyErr_Occurred()) { Py_CLEAR(self); }
    if (self) {
        self->creation_thread_id = GetCurrentThreadId();
        synthesizer_weakrefs.register_ref(self);
        com.detach();
    }
    return (PyObject*)self;
}

static void
Synthesizer_dealloc(Synthesizer *self_) {
    synthesizer_weakrefs.unregister_ref(self_, [](Synthesizer *self) {
        self->synth = SpeechSynthesizer{nullptr};
        self->player = MediaPlayer{nullptr};
        Py_TYPE(self)->tp_free((PyObject*)self);
        CoUninitialize();
    });
}

static void
ensure_current_thread_has_message_queue(void) {
    MSG msg;
    PeekMessage(&msg, NULL, WM_USER, WM_USER, PM_NOREMOVE);
}

static PyObject*
Synthesizer_speak(Synthesizer *self, PyObject *args) {
    wchar_raii pytext;
    PyObject *callback;
    int is_ssml = 0;
	if (!PyArg_ParseTuple(args, "O&O|p", py_to_wchar_no_none, &pytext, &callback, &is_ssml)) return NULL;
    if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be callable"); return NULL; }
    ensure_current_thread_has_message_queue();
    SpeechSynthesisStream stream{nullptr};
    try {
        if (is_ssml) stream = self->synth.SynthesizeSsmlToStreamAsync(pytext.as_view()).get();
        else stream = self->synth.SynthesizeTextToStreamAsync(pytext.as_view()).get();
    } catch (winrt::hresult_error const& ex) {
        return set_python_error_from_runtime(ex, "Failed to get SpeechSynthesisStream from text");
    }
    MediaSource source = winrt::Windows::Media::Core::MediaSource::CreateFromStream(stream, stream.ContentType());
    self->player.Source(source);
    self->player.Play();
    Py_RETURN_NONE;
}


static PyObject*
Synthesizer_create_recording(Synthesizer *self, PyObject *args) {
    wchar_raii pytext;
    PyObject *callback;
    int is_ssml = 0;
	if (!PyArg_ParseTuple(args, "O&O|p", py_to_wchar_no_none, &pytext, &callback, &is_ssml)) return NULL;
    if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be callable"); return NULL; }

    ensure_current_thread_has_message_queue();
    SpeechSynthesisStream stream{nullptr};
    try {
        if (is_ssml) stream = self->synth.SynthesizeSsmlToStreamAsync(pytext.as_view()).get();
        else stream = self->synth.SynthesizeTextToStreamAsync(pytext.as_view()).get();
    } catch(winrt::hresult_error const& ex) {
        return set_python_error_from_runtime(ex, "Failed to get SpeechSynthesisStream from text");
    }
    unsigned long long stream_size = stream.Size(), bytes_read = 0;
    DataReader reader(stream);
    unsigned int n;
    const static unsigned int chunk_size = 16 * 1024;
    while (bytes_read < stream_size) {
        try {
            n = reader.LoadAsync(chunk_size).get();
        } catch(winrt::hresult_error const& ex) {
            return set_python_error_from_runtime(ex, "Failed to load data from DataReader");
        }
        if (n > 0) {
            bytes_read += n;
            pyobject_raii b(PyBytes_FromStringAndSize(NULL, n));
            if (!b) return NULL;
            unsigned char *p = reinterpret_cast<unsigned char*>(PyBytes_AS_STRING(b.ptr()));
            reader.ReadBytes(winrt::array_view(p, p + n));
            pyobject_raii ret(PyObject_CallFunctionObjArgs(callback, b.ptr(), NULL));
        }
    }

    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}


static PyObject*
voice_as_dict(VoiceInformation const& voice) {
    try {
        const char *gender = "";
        switch (voice.Gender()) {
            case VoiceGender::Male: gender = "male"; break;
            case VoiceGender::Female: gender = "female"; break;
        }
        return Py_BuildValue("{su su su su ss}",
            "display_name", voice.DisplayName().c_str(),
            "description", voice.Description().c_str(),
            "id", voice.Id().c_str(),
            "language", voice.Language().c_str(),
            "gender", gender
        );
    } catch(winrt::hresult_error const& ex) {
        return set_python_error_from_runtime(ex);
    }
}


static PyObject*
all_voices(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    try {
        auto voices = SpeechSynthesizer::AllVoices();
        pyobject_raii ans(PyTuple_New(voices.Size()));
        if (!ans) return NULL;
        Py_ssize_t i = 0;
        for(auto const& voice : voices) {
            PyObject *v = voice_as_dict(voice);
            if (v) {
                PyTuple_SET_ITEM(ans.ptr(), i++, v);
            } else {
                return NULL;
            }
        }
        return ans.detach();
    } catch(winrt::hresult_error const& ex) {
        return set_python_error_from_runtime(ex);
    }
}

static PyObject*
default_voice(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    try {
        return voice_as_dict(SpeechSynthesizer::DefaultVoice());
    } catch(winrt::hresult_error const& ex) {
        return set_python_error_from_runtime(ex);
    }
}

#define M(name, args) { #name, (PyCFunction)Synthesizer_##name, args, ""}
static PyMethodDef Synthesizer_methods[] = {
    M(create_recording, METH_VARARGS),
    M(speak, METH_VARARGS),
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
