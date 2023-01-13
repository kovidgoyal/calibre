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
#include <winrt/base.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Storage.Streams.h>
#include <winrt/Windows.Media.SpeechSynthesis.h>

using namespace winrt::Windows::Foundation;
using namespace winrt::Windows::Foundation::Collections;
using namespace winrt::Windows::Media::SpeechSynthesis;
using namespace winrt::Windows::Storage::Streams;


struct Synthesizer {
    PyObject_HEAD
    SpeechSynthesizer synth{nullptr};
};


static PyTypeObject SynthesizerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static PyObject *
Synthesizer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) { INITIALIZE_COM_IN_FUNCTION
	Synthesizer *self = (Synthesizer *) type->tp_alloc(type, 0);
    if (self) {
        self->synth = SpeechSynthesizer();
    }
    if (self && !PyErr_Occurred()) com.detach();
    return (PyObject*)self;
}

static void
Synthesizer_dealloc(Synthesizer *self) {
    self->synth = SpeechSynthesizer{nullptr};
    CoUninitialize();
}

static void
ensure_current_thread_has_message_queue(void) {
    MSG msg;
    PeekMessage(&msg, NULL, WM_USER, WM_USER, PM_NOREMOVE);
}

/*
class CreateRecording {
private:
    DWORD main_thread_id;
    std::wstring error_msg;
    winrt::Windows::Storage::Streams::DataReader reader{nullptr};
    unsigned long long stream_size, bytes_read;

public:
    CreateRecording() : main_thread_id(0), error_msg(), reader(nullptr), stream_size(0), bytes_read(0) {
        main_thread_id = GetCurrentThreadId();
        ensure_current_thread_has_message_queue();
    }
    CreateRecording& operator = (const CreateRecording &) = delete;
    CreateRecording(const CreateRecording&) = delete;

    void record_plain_text(SpeechSynthesizer ^synth, const wchar_t* text, PyObject *callback, std::shared_ptr<CreateRecording> self) {
        StringReference rtext(text);
        create_task(synth->SynthesizeTextToStreamAsync(rtext.GetString()), task_continuation_context::use_current()).then(
                [self](task<SpeechSynthesisStream^> s) { self->threaded_save_stream(s, self); });
        this->run_loop(callback);
        reader = winrt::Windows::Storage::Streams::DataReader{nullptr};
    }

    void record_ssml(SpeechSynthesizer ^synth, const wchar_t* text, PyObject *callback, std::shared_ptr<CreateRecording> self) {
        StringReference rtext(text);
        create_task(synth->SynthesizeSsmlToStreamAsync(rtext.GetString()), task_continuation_context::use_current()).then(
                [self](task<SpeechSynthesisStream^> s) { self->threaded_save_stream(s, self); });
        this->run_loop(callback);
        reader = winrt::Windows::Storage::Streams::DataReader{nullptr};
    }

private:

    void send_message_to_main_thread(bool done = false) const {
        PostThreadMessageA(main_thread_id, WM_USER, 0, done ? 1 : 0);
    }

    void threaded_save_stream(task<SpeechSynthesisStream^> stream_task, std::shared_ptr<CreateRecording> self) {
        try {
            SpeechSynthesisStream^ stream = stream_task.get();
            stream_size = stream->Size;
            reader = winrt::Windows::Storage::Streams::DataReader(stream);
            this->chunked_read(self);
            return;
        } catch(winrt::hresult_error const& ex) {
            error_msg += L"Could not synthesize speech from text: ";
            error_msg += ex.message().c_str();
        }
        this->send_message_to_main_thread(true);
    }

    void chunked_read(std::shared_ptr<CreateRecording> self) {
        create_task(reader.LoadAsync(16 * 1024), task_continuation_context::use_current()).then(
                [self](task<unsigned int> s) { self->threaded_dispatch_chunk(s, self); });
    }

    void threaded_dispatch_chunk(task<unsigned int> bytes_loaded, std::shared_ptr<CreateRecording> self) {
        try {
            unsigned int n = bytes_loaded.get();
            bytes_read += n;
            fprintf(stderr, "11111111 %u\n", n);
            if (n > 0) {
                this->send_message_to_main_thread();
            }
            if (bytes_read < stream_size) {
                this->chunked_read(self);
                return;
            }
        } catch(winrt::hresult_error const& ex) {
            error_msg += L"Could not read data from synthesized speech stream: ";
            error_msg += ex.message().c_str();
        }
        this->send_message_to_main_thread(true);
    }

    void run_loop(PyObject *callback) {
        MSG msg;
        while (true) {
            BOOL ret = GetMessage(&msg, NULL, 0, 0);
            if (ret == 0) { PyErr_SetString(PyExc_OSError, "WM_QUIT received"); return;  }
            if (ret == -1) { PyErr_SetFromWindowsErr(0); return; }
            if (msg.message == WM_USER) {
                if (!this->commit_chunks(callback)) { break; }
                if (msg.lParam == 1) break;
            } else {
                DispatchMessage(&msg);
            }
        }

        if (error_msg.size() > 0) {
            pyobject_raii err(PyUnicode_FromWideChar(error_msg.data(), -1));
            PyErr_Format(PyExc_OSError, "%V", err.ptr(), "Could not create error message unicode object");
            return;
        }
        this->commit_chunks(callback);
    }

    bool commit_chunks(PyObject *callback) {
        // Platform::Array<byte> ^a;
        // while ((a = queue.pop()) != nullptr) {
        //     pyobject_raii ret(PyObject_CallFunction(callback, "y#", (const char*)a->Data, static_cast<Py_ssize_t>(a->Length)));
        //     if (!ret) return false;
        // }
        return true;
    }
};


static PyObject*
Synthesizer_create_recording(Synthesizer *self, PyObject *args) {
    wchar_raii pytext;
    PyObject *callback;
	if (!PyArg_ParseTuple(args, "O&O", py_to_wchar_no_none, &pytext, &callback)) return NULL;
    if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be callable"); return NULL; }
    auto cr = std::make_shared<CreateRecording>();
    cr->record_plain_text(self->synth, pytext.ptr(), callback, cr);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}
*/

static PyObject*
voice_as_dict(VoiceInformation const& voice) {
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
}


static PyObject*
all_voices(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    auto voices = SpeechSynthesizer::AllVoices();
    pyobject_raii ans(PyTuple_New(voices.Size()));
    if (!ans) return NULL;
    Py_ssize_t i = 0;
    try {
        for(auto const& voice : voices) {
            PyObject *v = voice_as_dict(voice);
            if (v) {
                PyTuple_SET_ITEM(ans.ptr(), i++, v);
            } else {
                return NULL;
            }
        }
    } catch(winrt::hresult_error const& ex) {
        error_from_hresult(ex.to_abi(), "Failed to list all voices");
        return NULL;
    }
    return ans.detach();
}

static PyObject*
default_voice(PyObject* /*self*/, PyObject* /*args*/) { INITIALIZE_COM_IN_FUNCTION
    try {
        return voice_as_dict(SpeechSynthesizer::DefaultVoice());
    } catch(winrt::hresult_error const& ex) {
        error_from_hresult(ex.to_abi(), "Failed to list all voices");
        return NULL;
    }
}

#define M(name, args) { #name, (PyCFunction)Synthesizer_##name, args, ""}
static PyMethodDef Synthesizer_methods[] = {
    // M(create_recording, METH_VARARGS),
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
