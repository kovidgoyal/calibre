/*
 * winsapi.cpp
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define _ATL_APARTMENT_THREADED
#include "common.h"

#include <atlbase.h>
extern CComModule _Module;
#include <atlcom.h>

#include <sapi.h>
#pragma warning( push )
#pragma warning( disable : 4996 )  // sphelper.h uses deprecated GetVersionEx
#include <sphelper.h>
#pragma warning( pop )

// Structures {{{
typedef struct {
    PyObject_HEAD
    ISpVoice *voice;
    HANDLE shutdown_events_thread, events_available;
} Voice;


static PyTypeObject VoiceType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static const ULONGLONG speak_events = SPFEI(SPEI_START_INPUT_STREAM) | SPFEI(SPEI_END_INPUT_STREAM) | SPFEI(SPEI_TTS_BOOKMARK);

static PyObject *
Voice_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    HRESULT hr = CoInitialize(NULL);
    if (hr != S_OK && hr != S_FALSE) {
        if (hr == RPC_E_CHANGED_MODE) {
            return error_from_hresult(hr, "COM initialization failed as it was already initialized in multi-threaded mode");
        }
        return PyErr_NoMemory();
    }
	Voice *self = (Voice *) type->tp_alloc(type, 0);
    if (self) {
        if (FAILED(hr = CoCreateInstance(CLSID_SpVoice, NULL, CLSCTX_ALL, IID_ISpVoice, (void **)&self->voice))) {
            Py_CLEAR(self);
            return error_from_hresult(hr, "Failed to create ISpVoice instance");
        }
        if (FAILED(hr = self->voice->SetNotifyWin32Event())) {
            Py_CLEAR(self);
            return error_from_hresult(hr, "Failed to set event based notify mechanism");
        }
        self->events_available = self->voice->GetNotifyEventHandle();
        if (self->events_available == INVALID_HANDLE_VALUE) {
            Py_CLEAR(self);
            PyErr_SetString(PyExc_OSError, "Failed to get events handle for ISpVoice");
            return NULL;
        }
        self->shutdown_events_thread = CreateEventW(NULL, true, false, NULL);
        if (self->shutdown_events_thread == INVALID_HANDLE_VALUE) {
            Py_CLEAR(self);
            PyErr_SetFromWindowsErr(0);
            return NULL;
        }
    }
    return (PyObject*)self;
}

static void
Voice_dealloc(Voice *self) {
    if (self->voice) { self->voice->Release(); self->voice = NULL; }
    if (self->shutdown_events_thread != INVALID_HANDLE_VALUE) {
        CloseHandle(self->shutdown_events_thread);
        self->shutdown_events_thread = INVALID_HANDLE_VALUE;
    }
    CoUninitialize();
}
// }}}

// Enumeration {{{
static PyObject*
Voice_get_all_sound_outputs(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    CComPtr<IEnumSpObjectTokens> iterator = NULL;
    if (FAILED(hr = SpEnumTokens(SPCAT_AUDIOOUT, NULL, NULL, &iterator))) {
        return error_from_hresult(hr, "Failed to create audio output category iterator");
    }
    pyobject_raii ans(PyList_New(0));
    if (!ans) return NULL;
    while (true) {
        CComPtr<ISpObjectToken> token = NULL;
        if (FAILED(hr = iterator->Next(1, &token, NULL)) || hr == S_FALSE || !token) break;
        pyobject_raii dict(PyDict_New());
        if (!dict) return NULL;
        com_wchar_raii id, description;
        if (FAILED(hr = token->GetId(id.address()))) continue;
        pyobject_raii idpy(PyUnicode_FromWideChar(id.ptr(), -1));
        if (!idpy) return NULL;
        if (PyDict_SetItemString(dict.ptr(), "id", idpy.ptr()) != 0) return NULL;

        if (FAILED(hr = SpGetDescription(token, description.address(), NULL))) continue;
        pyobject_raii descriptionpy(PyUnicode_FromWideChar(description.ptr(), -1));
        if (!descriptionpy) return NULL;
        if (PyDict_SetItemString(dict.ptr(), "description", descriptionpy.ptr()) != 0) return NULL;

        if (PyList_Append(ans.ptr(), dict.ptr()) != 0) return NULL;
    }
    return PyList_AsTuple(ans.ptr());
}

static PyObject*
Voice_get_current_sound_output(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    CComPtr<ISpObjectToken> token = NULL;
    if (FAILED(hr = self->voice->GetOutputObjectToken(&token))) return error_from_hresult(hr, "Failed to get current output object token");
    if (hr == S_FALSE) Py_RETURN_NONE;
    com_wchar_raii id;
    if (FAILED(hr = token->GetId(id.address()))) return error_from_hresult(hr, "Failed to get ID for current audio output token");
    return PyUnicode_FromWideChar(id.ptr(), -1);
}

static PyObject*
Voice_set_current_sound_output(Voice *self, PyObject *args) {
    wchar_raii id;
    int allow_format_changes = 1;
    if (!PyArg_ParseTuple(args, "|O&p", py_to_wchar, &id, &allow_format_changes)) return NULL;
    HRESULT hr = S_OK;
    if (id) {
        CComPtr<ISpObjectToken> token = NULL;
        if (FAILED(hr = SpGetTokenFromId(id.ptr(), &token))) {
            return error_from_hresult(hr, "Failed to find sound output with id", PyTuple_GET_ITEM(args, 0));
        }
        if (FAILED(hr = self->voice->SetOutput(token, allow_format_changes))) return error_from_hresult(hr, "Failed to set sound output to", PyTuple_GET_ITEM(args, 0));

    } else {
        if (FAILED(hr = self->voice->SetOutput(NULL, allow_format_changes))) return error_from_hresult(hr, "Failed to set sound output to default");
    }
    Py_RETURN_NONE;
}


static PyObject*
Voice_get_current_voice(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    CComPtr<ISpObjectToken> token = NULL;
    if (FAILED(hr = self->voice->GetVoice(&token))) {
        return error_from_hresult(hr, "Failed to get current voice");
    }
    com_wchar_raii id;
    if (FAILED(hr = token->GetId(id.address()))) return error_from_hresult(hr, "Failed to get ID for current voice");
    return PyUnicode_FromWideChar(id.ptr(), -1);
}

static PyObject*
Voice_set_current_voice(Voice *self, PyObject *args) {
    wchar_raii id;
    if (!PyArg_ParseTuple(args, "|O&", py_to_wchar, &id)) return NULL;
    HRESULT hr = S_OK;
    if (id) {
        CComPtr<ISpObjectToken> token = NULL;
        if (FAILED(hr = SpGetTokenFromId(id.ptr(), &token))) {
            return error_from_hresult(hr, "Failed to find voice with id", PyTuple_GET_ITEM(args, 0));
        }
        if (FAILED(hr = self->voice->SetVoice(token))) return error_from_hresult(hr, "Failed to set voice to", PyTuple_GET_ITEM(args, 0));
    } else {
        if (FAILED(hr = self->voice->SetVoice(NULL))) return error_from_hresult(hr, "Failed to set voice to default");
    }
    Py_RETURN_NONE;
}

static PyObject*
Voice_get_all_voices(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    CComPtr<IEnumSpObjectTokens> iterator = NULL;
    if (FAILED(hr = SpEnumTokens(SPCAT_VOICES, NULL, NULL, &iterator))) {
        return error_from_hresult(hr, "Failed to create voice category iterator");
    }
    pyobject_raii ans(PyList_New(0));
    if (!ans) return NULL;
    while (true) {
        CComPtr<ISpObjectToken> token = NULL;
        if (FAILED(hr = iterator->Next(1, &token, NULL)) || hr == S_FALSE || !token) break;
        pyobject_raii dict(PyDict_New());
        if (!dict) return NULL;

        com_wchar_raii id, description;
        if (FAILED(hr = token->GetId(id.address()))) continue;
        pyobject_raii idpy(PyUnicode_FromWideChar(id.ptr(), -1));
        if (!idpy) return NULL;
        if (PyDict_SetItemString(dict.ptr(), "id", idpy.ptr()) != 0) return NULL;

        if (FAILED(hr = SpGetDescription(token, description.address(), NULL))) continue;
        pyobject_raii descriptionpy(PyUnicode_FromWideChar(description.ptr(), -1));
        if (!descriptionpy) return NULL;
        if (PyDict_SetItemString(dict.ptr(), "description", descriptionpy.ptr()) != 0) return NULL;
        CComPtr<ISpDataKey> attributes = NULL;
        if (FAILED(hr = token->OpenKey(L"Attributes", &attributes))) continue;
#define ATTR(name) {\
    com_wchar_raii val; \
    if (SUCCEEDED(attributes->GetStringValue(TEXT(#name), val.address()))) { \
        pyobject_raii pyval(PyUnicode_FromWideChar(val.ptr(), -1)); if (!pyval) return NULL; \
        if (PyDict_SetItemString(dict.ptr(), #name, pyval.ptr()) != 0) return NULL; \
    }\
}
        ATTR(gender); ATTR(name); ATTR(vendor); ATTR(age);
#undef ATTR
        com_wchar_raii val;
        if (SUCCEEDED(attributes->GetStringValue(L"language", val.address()))) {
            int lcid = wcstol(val.ptr(), NULL, 16);
            wchar_t buf[LOCALE_NAME_MAX_LENGTH];
            if (LCIDToLocaleName(lcid, buf, LOCALE_NAME_MAX_LENGTH, 0) > 0) {
                pyobject_raii pyval(PyUnicode_FromWideChar(buf, -1)); if (!pyval) return NULL;
                if (PyDict_SetItemString(dict.ptr(), "language", pyval.ptr()) != 0) return NULL;
            }
        }
        if (PyList_Append(ans.ptr(), dict.ptr()) != 0) return NULL;
    }
    return PyList_AsTuple(ans.ptr());
}
// }}}

// Volume and rate {{{
static PyObject*
Voice_get_current_volume(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    USHORT volume;
    if (FAILED(hr = self->voice->GetVolume(&volume))) return error_from_hresult(hr);
    return PyLong_FromUnsignedLong((unsigned long)volume);
}

static PyObject*
Voice_get_current_rate(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    long rate;
    if (FAILED(hr = self->voice->GetRate(&rate))) return error_from_hresult(hr);
    return PyLong_FromLong(rate);
}

static PyObject*
Voice_set_current_rate(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    long rate;
    if (!PyArg_ParseTuple(args, "l", &rate)) return NULL;
    if (rate < -10 || rate > 10) { PyErr_SetString(PyExc_ValueError, "rate must be between -10 and 10"); return NULL; }
    if (FAILED(hr = self->voice->SetRate(rate))) return error_from_hresult(hr);
    Py_RETURN_NONE;
}

static PyObject*
Voice_set_current_volume(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    unsigned short volume;
    if (!PyArg_ParseTuple(args, "H", &volume)) return NULL;
    if (FAILED(hr = self->voice->SetVolume(volume))) return error_from_hresult(hr);
    Py_RETURN_NONE;
}
// }}}

static PyObject*
Voice_speak(Voice *self, PyObject *args) {
    wchar_raii text_or_path;
    unsigned long flags = SPF_DEFAULT;
    int want_events = 0;
    HRESULT hr = S_OK;
    if (!PyArg_ParseTuple(args, "O&|kp", py_to_wchar, &text_or_path, &flags, &want_events)) return NULL;
    ULONGLONG events = want_events ? speak_events : 0;
    if (FAILED(hr = self->voice->SetInterest(events, events))) {
        return error_from_hresult(hr, "Failed to ask for events");
    }
    ULONG stream_number;
    Py_BEGIN_ALLOW_THREADS;
    hr = self->voice->Speak(text_or_path.ptr(), flags, &stream_number);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) return error_from_hresult(hr, "Failed to speak");
    return PyLong_FromUnsignedLong(stream_number);
}

static PyObject*
Voice_wait_until_done(Voice *self, PyObject *args) {
    unsigned long timeout = INFINITE;
    if (!PyArg_ParseTuple(args, "|k", &timeout)) return NULL;
    HRESULT hr ;
    Py_BEGIN_ALLOW_THREADS;
    hr = self->voice->WaitUntilDone(timeout);
    Py_END_ALLOW_THREADS;
    if (hr == S_OK) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyObject*
Voice_pause(Voice *self, PyObject *args) {
    HRESULT hr = self->voice->Pause();
    if (FAILED(hr)) return error_from_hresult(hr);
    Py_RETURN_NONE;
}

static PyObject*
Voice_resume(Voice *self, PyObject *args) {
    HRESULT hr = self->voice->Resume();
    if (FAILED(hr)) return error_from_hresult(hr);
    Py_RETURN_NONE;
}

static PyObject*
Voice_create_recording_wav(Voice *self, PyObject *args) {
    HRESULT hr = S_OK;
    wchar_raii path, text;
    int do_events = 0;
    SPSTREAMFORMAT format = SPSF_22kHz16BitMono;
    if (!PyArg_ParseTuple(args, "O&O&|ip", py_to_wchar_no_none, &path, py_to_wchar_no_none, &text, &format, &do_events)) return NULL;
    CComPtr <ISpStream> stream = NULL;
    CSpStreamFormat audio_fmt;
    if (FAILED(hr = audio_fmt.AssignFormat(format))) return error_from_hresult(hr, "Invalid Audio format");
    CComPtr<ISpObjectToken> token = NULL;
    if (FAILED(hr = self->voice->GetOutputObjectToken(&token))) return error_from_hresult(hr, "Failed to get current output object token");
    bool uses_default_output = hr == S_FALSE;

    if (FAILED(hr = SPBindToFile(path.ptr(), SPFM_CREATE_ALWAYS, &stream, &audio_fmt.FormatId(), audio_fmt.WaveFormatExPtr())))
        return error_from_hresult(hr, "Failed to open file", PyTuple_GET_ITEM(args, 0));

    if (FAILED(hr = self->voice->SetOutput(stream, TRUE))) {
        stream->Close();
        return error_from_hresult(hr, "Failed to set output to wav file", PyTuple_GET_ITEM(args, 0));
    }
    Py_BEGIN_ALLOW_THREADS;
    hr = self->voice->Speak(text.ptr(), SPF_DEFAULT, NULL);
    Py_END_ALLOW_THREADS;
    stream->Close();
    self->voice->SetOutput(uses_default_output ? NULL: token, TRUE);
    if (FAILED(hr)) return error_from_hresult(hr, "Failed to speak into wav file", PyTuple_GET_ITEM(args, 0));
    Py_RETURN_NONE;
}


static PyObject*
Voice_shutdown_event_loop(Voice *self, PyObject *args) {
    if (!SetEvent(self->shutdown_events_thread)) return PyErr_SetFromWindowsErr(0);
    Py_RETURN_NONE;
}

static PyObject*
Voice_get_events(Voice *self, PyObject *args) {
    HRESULT hr;
    const ULONG asz = 32;
    ULONG num_events;
    SPEVENT events[asz];
    PyObject *ret;
    long long val;
    int etype;
    PyObject *ans = PyList_New(0);
    if (!ans) return NULL;
    while (true) {
        Py_BEGIN_ALLOW_THREADS;
        hr = self->voice->GetEvents(asz, events, &num_events);
        Py_END_ALLOW_THREADS;
        if (hr != S_OK && hr != S_FALSE) break;
        if (num_events == 0) break;
        for (ULONG i = 0; i < num_events; i++) {
            etype = events[i].eEventId;
            bool ok = false;
            switch(etype) {
                case SPEI_TTS_BOOKMARK:
                    val = events[i].wParam;
                    ok = true;
                    break;
                case SPEI_START_INPUT_STREAM:
                case SPEI_END_INPUT_STREAM:
                    val = 0;
                    ok = true;
                    break;
            }
            if (ok) {
                ret = Py_BuildValue("kiL", events[i].ulStreamNum, etype, val);
                if (!ret) { Py_CLEAR(ans); return NULL; }
                int x = PyList_Append(ans, ret);
                Py_DECREF(ret);
                if (x != 0) { Py_CLEAR(ans); return NULL; }
            }
        }
    }
    return ans;
}

static PyObject*
Voice_wait_for_event(Voice *self, PyObject *args) {
    const HANDLE handles[2] = {self->shutdown_events_thread, self->events_available};
    DWORD ev;
    Py_BEGIN_ALLOW_THREADS;
    ev = WaitForMultipleObjects(2, handles, false, INFINITE);
    Py_END_ALLOW_THREADS;
    switch (ev) {
        case WAIT_OBJECT_0:
            Py_RETURN_FALSE;
        case WAIT_OBJECT_0 + 1:
            Py_RETURN_TRUE;
    }
    Py_RETURN_NONE;
}

// Boilerplate {{{
#define M(name, args) { #name, (PyCFunction)Voice_##name, args, ""}
static PyMethodDef Voice_methods[] = {
    M(get_all_voices, METH_NOARGS),
    M(get_all_sound_outputs, METH_NOARGS),

    M(speak, METH_VARARGS),
    M(wait_until_done, METH_VARARGS),
    M(pause, METH_NOARGS),
    M(resume, METH_NOARGS),
    M(create_recording_wav, METH_VARARGS),

    M(get_current_rate, METH_NOARGS),
    M(get_current_volume, METH_NOARGS),
    M(get_current_voice, METH_NOARGS),
    M(get_current_sound_output, METH_NOARGS),
    M(set_current_voice, METH_VARARGS),
    M(set_current_rate, METH_VARARGS),
    M(set_current_volume, METH_VARARGS),
    M(set_current_sound_output, METH_VARARGS),

    M(shutdown_event_loop, METH_NOARGS),
    M(wait_for_event, METH_NOARGS),
    M(get_events, METH_NOARGS),
    {NULL, NULL, 0, NULL}
};
#undef M

#define M(name, args) { #name, name, args, ""}
static PyMethodDef winsapi_methods[] = {
    {NULL, NULL, 0, NULL}
};
#undef M

static int
exec_module(PyObject *m) {
    VoiceType.tp_name = "winsapi.ISpVoice";
    VoiceType.tp_doc = "Wrapper for ISpVoice";
    VoiceType.tp_basicsize = sizeof(Voice);
    VoiceType.tp_itemsize = 0;
    VoiceType.tp_flags = Py_TPFLAGS_DEFAULT;
    VoiceType.tp_new = Voice_new;
    VoiceType.tp_methods = Voice_methods;
	VoiceType.tp_dealloc = (destructor)Voice_dealloc;
	if (PyType_Ready(&VoiceType) < 0) return -1;

	Py_INCREF(&VoiceType);
    if (PyModule_AddObject(m, "ISpVoice", (PyObject *) &VoiceType) < 0) {
        Py_DECREF(&VoiceType);
        return -1;
    }
#define AI(name) if (PyModule_AddIntMacro(m, name) != 0) { Py_DECREF(&VoiceType); return -1; }
    AI(SPF_DEFAULT);
    AI(SPF_ASYNC);
    AI(SPF_PURGEBEFORESPEAK);
    AI(SPF_IS_FILENAME);
    AI(SPF_IS_XML);
    AI(SPF_IS_NOT_XML);
    AI(SPF_PERSIST_XML);
    AI(SPF_NLP_SPEAK_PUNC);
    AI(SPF_PARSE_SSML);
    AI(SPF_PARSE_AUTODETECT);
    AI(SPF_NLP_MASK);
    AI(SPF_PARSE_MASK);
    AI(SPF_VOICE_MASK);
    AI(SPF_UNUSED_FLAGS);

    AI(INFINITE);

    AI(SPSF_Default);
    AI(SPSF_NoAssignedFormat);
    AI(SPSF_Text);
    AI(SPSF_NonStandardFormat);
    AI(SPSF_ExtendedAudioFormat);

    // Standard PCM wave formats
    AI(SPSF_8kHz8BitMono);
    AI(SPSF_8kHz8BitStereo);
    AI(SPSF_8kHz16BitMono);
    AI(SPSF_8kHz16BitStereo);
    AI(SPSF_11kHz8BitMono);
    AI(SPSF_11kHz8BitStereo);
    AI(SPSF_11kHz16BitMono);
    AI(SPSF_11kHz16BitStereo);
    AI(SPSF_12kHz8BitMono);
    AI(SPSF_12kHz8BitStereo);
    AI(SPSF_12kHz16BitMono);
    AI(SPSF_12kHz16BitStereo);
    AI(SPSF_16kHz8BitMono);
    AI(SPSF_16kHz8BitStereo);
    AI(SPSF_16kHz16BitMono);
    AI(SPSF_16kHz16BitStereo);
    AI(SPSF_22kHz8BitMono);
    AI(SPSF_22kHz8BitStereo);
    AI(SPSF_22kHz16BitMono);
    AI(SPSF_22kHz16BitStereo);
    AI(SPSF_24kHz8BitMono);
    AI(SPSF_24kHz8BitStereo);
    AI(SPSF_24kHz16BitMono);
    AI(SPSF_24kHz16BitStereo);
    AI(SPSF_32kHz8BitMono);
    AI(SPSF_32kHz8BitStereo);
    AI(SPSF_32kHz16BitMono);
    AI(SPSF_32kHz16BitStereo);
    AI(SPSF_44kHz8BitMono);
    AI(SPSF_44kHz8BitStereo);
    AI(SPSF_44kHz16BitMono);
    AI(SPSF_44kHz16BitStereo);
    AI(SPSF_48kHz8BitMono);
    AI(SPSF_48kHz8BitStereo);
    AI(SPSF_48kHz16BitMono);
    AI(SPSF_48kHz16BitStereo);

    // TrueSpeech format
    AI(SPSF_TrueSpeech_8kHz1BitMono);

    // A-Law formats
    AI(SPSF_CCITT_ALaw_8kHzMono);
    AI(SPSF_CCITT_ALaw_8kHzStereo);
    AI(SPSF_CCITT_ALaw_11kHzMono);
    AI(SPSF_CCITT_ALaw_11kHzStereo);
    AI(SPSF_CCITT_ALaw_22kHzMono);
    AI(SPSF_CCITT_ALaw_22kHzStereo);
    AI(SPSF_CCITT_ALaw_44kHzMono);
    AI(SPSF_CCITT_ALaw_44kHzStereo);

    // u-Law formats
    AI(SPSF_CCITT_uLaw_8kHzMono);
    AI(SPSF_CCITT_uLaw_8kHzStereo);
    AI(SPSF_CCITT_uLaw_11kHzMono);
    AI(SPSF_CCITT_uLaw_11kHzStereo);
    AI(SPSF_CCITT_uLaw_22kHzMono);
    AI(SPSF_CCITT_uLaw_22kHzStereo);
    AI(SPSF_CCITT_uLaw_44kHzMono);
    AI(SPSF_CCITT_uLaw_44kHzStereo);

    // ADPCM formats
    AI(SPSF_ADPCM_8kHzMono);
    AI(SPSF_ADPCM_8kHzStereo);
    AI(SPSF_ADPCM_11kHzMono);
    AI(SPSF_ADPCM_11kHzStereo);
    AI(SPSF_ADPCM_22kHzMono);
    AI(SPSF_ADPCM_22kHzStereo);
    AI(SPSF_ADPCM_44kHzMono);
    AI(SPSF_ADPCM_44kHzStereo);

    // GSM 6.10 formats
    AI(SPSF_GSM610_8kHzMono);
    AI(SPSF_GSM610_11kHzMono);
    AI(SPSF_GSM610_22kHzMono);
    AI(SPSF_GSM610_44kHzMono);

    AI(SPEI_UNDEFINED);

    //--- TTS engine
    AI(SPEI_START_INPUT_STREAM);
    AI(SPEI_END_INPUT_STREAM);
    AI(SPEI_VOICE_CHANGE);
    AI(SPEI_TTS_BOOKMARK);
    AI(SPEI_WORD_BOUNDARY);
    AI(SPEI_PHONEME);
    AI(SPEI_SENTENCE_BOUNDARY);
    AI(SPEI_VISEME);
    AI(SPEI_TTS_AUDIO_LEVEL);

    //--- Engine vendors use these reserved bits
    AI(SPEI_TTS_PRIVATE);
    AI(SPEI_MIN_TTS);
    AI(SPEI_MAX_TTS);

    //--- Speech Recognition
    AI(SPEI_END_SR_STREAM);
    AI(SPEI_SOUND_START);
    AI(SPEI_SOUND_END);
    AI(SPEI_PHRASE_START);
    AI(SPEI_RECOGNITION);
    AI(SPEI_HYPOTHESIS);
    AI(SPEI_SR_BOOKMARK);
    AI(SPEI_PROPERTY_NUM_CHANGE);
    AI(SPEI_PROPERTY_STRING_CHANGE);
    AI(SPEI_FALSE_RECOGNITION);
    AI(SPEI_INTERFERENCE);
    AI(SPEI_REQUEST_UI);
    AI(SPEI_RECO_STATE_CHANGE);
    AI(SPEI_ADAPTATION);
    AI(SPEI_START_SR_STREAM);
    AI(SPEI_RECO_OTHER_CONTEXT);
    AI(SPEI_SR_AUDIO_LEVEL);
    AI(SPEI_SR_RETAINEDAUDIO);

    //--- Engine vendors use these reserved bits
    AI(SPEI_SR_PRIVATE);
    AI(SPEI_MIN_SR);
    AI(SPEI_MAX_SR);

    //--- Reserved: Do not use
    AI(SPEI_RESERVED1);
    AI(SPEI_RESERVED2);
#undef AI
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_winsapi(void) {
    module_def.m_name     = "winsapi";
    module_def.m_doc      = "SAPI wrapper";
    module_def.m_methods  = winsapi_methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
