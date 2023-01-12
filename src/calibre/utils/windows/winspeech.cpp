/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <array>
#include <collection.h>
#include <winrt/base.h>
#include <ppltasks.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <windows.foundation.h>
#include <windows.media.speechsynthesis.h>
#include <windows.storage.streams.h>

using namespace Windows::Foundation;
using namespace Windows::Foundation::Collections;
using namespace Windows::Media::SpeechSynthesis;
using namespace Windows::Storage::Streams;
using namespace Platform;
using namespace Concurrency;

// static void
// wait_for_async( Windows::Foundation::IAsyncInfo ^op ) {
//     while(op->Status == Windows::Foundation::AsyncStatus::Started) {
//         CoreWindow::GetForCurrentThread()->Dispatcher->ProcessEvents(CoreProcessEventsOption::ProcessAllIfPresent);
//     }
// }

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

#define WM_DONE (WM_USER + 0)

static void
ensure_current_thread_has_message_queue(void) {
    MSG msg;
    PeekMessage(&msg, NULL, WM_USER, WM_USER, PM_NOREMOVE);
}

static bool
send_done_message_to_thread(DWORD thread_id) {
    return PostThreadMessageA(thread_id, WM_DONE, 0, 0);
}

static bool
pump_till_done(void) {
    MSG msg;
    while (true) {
        BOOL ret = GetMessage(&msg, NULL, 0, 0);
        if (ret == 0) { PyErr_SetString(PyExc_OSError, "WM_QUIT received"); return false; } // WM_QUIT
        if (ret == -1) { PyErr_SetFromWindowsErr(0); return false; }
		if (msg.message == WM_DONE) {
            break;
        }
		DispatchMessage(&msg);
    }
    return true;
}

static PyObject*
Synthesizer_create_recording(Synthesizer *self, PyObject *args) {
    wchar_raii pytext;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &pytext)) return NULL;
    StringReference text(pytext.ptr());
    bool error_ocurred = false;
    HRESULT hr = S_OK;
    std::array<wchar_t, 2048> error_msg;
    DataReader ^reader = nullptr;
    DWORD main_thread_id = GetCurrentThreadId();
    unsigned long long stream_size;
    unsigned int bytes_read;

    create_task(self->synth->SynthesizeTextToStreamAsync(text.GetString()), task_continuation_context::use_current()
    ).then([&reader, &stream_size](task<SpeechSynthesisStream^> stream_task) {
        SpeechSynthesisStream^ stream = stream_task.get();
        stream_size = stream->Size;
        reader = ref new DataReader(stream);
        return reader->LoadAsync((unsigned int)stream_size);
    }).then([main_thread_id, &bytes_read, &error_msg, &error_ocurred, &reader](task<unsigned int> bytes_read_task) {
        try {
            bytes_read = bytes_read_task.get();
        } catch (Exception ^ex) {
            std::swprintf(error_msg.data(), error_msg.size(), L"Could not synthesize speech from text: %ls", ex->Message->Data());
            error_ocurred = true;
        }
        send_done_message_to_thread(main_thread_id);
    });

    if (!pump_till_done()) return NULL;

    if (error_ocurred) {
        pyobject_raii err(PyUnicode_FromWideChar(error_msg.data(), -1));
        PyErr_Format(PyExc_OSError, "%V", err.ptr(), "Could not create error message unicode object");
        return NULL;
    }
    auto data = ref new Platform::Array<byte>(bytes_read);
    reader->ReadBytes(data);
    return PyBytes_FromStringAndSize((const char*)data->Data, bytes_read);
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
    M(create_recording, METH_VARARGS),
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
