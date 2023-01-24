/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <atomic>
#include <array>
#include <vector>
#include <map>
#include <deque>
#include <memory>
#include <sstream>
#include <mutex>
#include <filesystem>
#include <functional>
#include <iostream>
#include <unordered_map>
#include <io.h>
#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
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

#define debug(format_string, ...) { \
    std::scoped_lock _sl_(output_lock); \
    DWORD _tid_ = GetCurrentThreadId(); \
    char _buf_[64] = {0}; snprintf(_buf_, sizeof(_buf_)-1, "thread-%u", _tid_); \
    fprintf(stderr, "%s " format_string "\n", main_thread_id == _tid_ ? "thread-main" : _buf_, __VA_ARGS__); fflush(stderr);\
}

static std::mutex output_lock;
static std::atomic_bool main_loop_is_running;
static DWORD main_thread_id;
enum {
    STDIN_FAILED = 1,
    STDIN_MSG,
    EXIT_REQUESTED
};

// trim from start (in place)
static inline void
ltrim(std::string &s) {
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char ch) {
        return !std::isspace(ch);
    }));
}

// trim from end (in place)
static inline void
rtrim(std::string &s) {
    s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
        return !std::isspace(ch);
    }).base(), s.end());
}

static std::vector<std::wstring_view>
split(std::wstring_view const &src, std::wstring const &delim = L" ") {
    size_t pos;
    std::vector<std::wstring_view> ans; ans.reserve(16);
    std::wstring_view sv(src);
    while ((pos = sv.find(delim)) != std::wstring_view::npos) {
        if (pos > 0) ans.emplace_back(sv.substr(0, pos));
        sv = sv.substr(pos + 1);
    }
    if (sv.size() > 0) ans.emplace_back(sv);
    return ans;
}

static std::wstring
join(std::vector<std::wstring_view> parts, std::wstring const &delim = L" ") {
    std::wstring ans; ans.reserve(1024);
    for (auto const &x : parts) {
        ans.append(x);
        ans.append(delim);
    }
    ans.erase(ans.size() - delim.size());
    return ans;
}

static id_type
parse_id(std::wstring_view const& s) {
    id_type ans = 0;
    for (auto ch : s) {
        auto delta = ch - '0';
        if (delta < 0 || delta > 9) {
            throw std::wstring(L"Not a valid id: ") + std::wstring(s);
        }
        ans = (ans * 10) + delta;
    }
    return ans;
}


static std::string
serialize_string_for_json(std::string const &src) {
    std::string ans("\"");
    ans.reserve(src.size() + 16);
    for (auto ch : src) {
        switch(ch) {
            case '\\':
                ans += "\\\\"; break;
            case '"':
                ans += "\\\""; break;
            case '\n':
                ans += "\\n"; break;
            case '\r':
                ans += "\\r"; break;
            default:
                ans += ch; break;
        }
    }
    ans += '"';
    return ans;
}

class json_val {  // {{{
private:
    enum { DT_INT, DT_STRING, DT_LIST, DT_OBJECT, DT_NONE, DT_BOOL } type;
    std::string s;
    bool b;
    long long i;
    std::vector<json_val> list;
    std::map<std::string, json_val> object;
public:
    json_val() : type(DT_NONE) {}
    json_val(std::string &&text) : type(DT_STRING), s(text) {}
    json_val(const char *ns) : type(DT_STRING), s(ns) {}
    json_val(winrt::hstring const& text) : type(DT_STRING), s(winrt::to_string(text)) {}
    json_val(std::wstring const& text) : type(DT_STRING), s(winrt::to_string(text)) {}
    json_val(std::string_view text) : type(DT_STRING), s(text) {}
    json_val(long long num) : type(DT_INT), i(num) {}
    json_val(std::vector<json_val> &&items) : type(DT_LIST), list(items) {}
    json_val(std::map<std::string, json_val> &&m) : type(DT_OBJECT), object(m) {}
    json_val(std::initializer_list<std::pair<const std::string, json_val>> vals) : type(DT_OBJECT), object(vals) { }
    json_val(bool x) : type(DT_BOOL), b(x) {}

    json_val(VoiceInformation const& voice) : type(DT_OBJECT) {
        const char *gender = "";
        switch (voice.Gender()) {
            case VoiceGender::Male: gender = "male"; break;
            case VoiceGender::Female: gender = "female"; break;
        }
        object = {
            {"display_name", json_val(voice.DisplayName())},
            {"description", json_val(voice.Description())},
            {"id", json_val(voice.Id())},
            {"language", json_val(voice.Language())},
            {"gender", json_val(gender)},
        };
    }

    json_val(IVectorView<VoiceInformation> const& voices) : type(DT_LIST) {
        list.reserve(voices.Size());
        for(auto const& voice : voices) {
            list.emplace_back(json_val(voice));
        }
    }

    json_val(MediaPlaybackState const& state) : type(DT_STRING) {
        switch(state) {
            case MediaPlaybackState::None: s = "none"; break;
            case MediaPlaybackState::Opening: s = "opening"; break;
            case MediaPlaybackState::Buffering: s = "buffering"; break;
            case MediaPlaybackState::Playing: s = "playing"; break;
            case MediaPlaybackState::Paused: s = "paused"; break;
            default: s = "unknown"; break;
        }
    }

    std::string serialize() const {
        switch(type) {
            case DT_NONE:
                return "nil";
            case DT_BOOL:
                return b ? "true" : "false";
            case DT_INT:
                // this is not really correct since JS has various limits on numeric types, but good enough for us
                return std::to_string(i);
            case DT_STRING:
                return serialize_string_for_json(s);
            case DT_LIST: {
                std::string ans("[");
                ans.reserve(list.size() * 32);
                for (auto const &i : list) {
                    ans += i.serialize();
                    ans += ", ";
                }
                ans.erase(ans.size() - 2); ans += "]";
                return ans;
            }
            case DT_OBJECT: {
                std::string ans("{");
                ans.reserve(object.size() * 64);
                for (const auto& [key, value]: object) {
                    ans += serialize_string_for_json(key);
                    ans += ": ";
                    ans += value.serialize();
                    ans += ", ";
                }
                ans.erase(ans.size() - 2); ans += "}";
                return ans;
            }
        }
        return "";
    }
}; // }}}

static void
output(id_type cmd_id, std::string_view const &msg_type, json_val const &&msg) {
    std::scoped_lock sl(output_lock);
    try {
        std::cout << cmd_id << " " << msg_type << " " << msg.serialize() << std::endl;
    } catch(...) {}
}

static void
output_error(id_type cmd_id, std::string_view const &msg, std::string_view const &error, long long line, HRESULT hr=S_OK) {
    std::map<std::string, json_val> m = {{"msg", json_val(msg)}, {"error", json_val(error)}, {"file", json_val("winspeech.cpp")}, {"line", json_val(line)}};
    if (hr != S_OK) m["hr"] = json_val((long long)hr);
    output(cmd_id, "error", std::move(m));
}

#define CATCH_ALL_EXCEPTIONS(msg, cmd_id) \
  catch(winrt::hresult_error const& ex) { \
    output_error(cmd_id, msg, winrt::to_string(ex.message()), __LINE__, ex.to_abi()); \
} catch (std::exception const &ex) { \
    output_error(cmd_id, msg, ex.what(), __LINE__); \
} catch (std::string const &ex) { \
    output_error(cmd_id, msg, ex, __LINE__); \
} catch (std::wstring const &ex) { \
    output_error(cmd_id, msg, winrt::to_string(ex), __LINE__); \
} catch (...) { \
    output_error(cmd_id, msg, "Unknown exception type was raised", __LINE__); \
}

/* Legacy code {{{

template<typename T>
class WeakRefs {
    private:
    std::mutex weak_ref_lock;
    std::unordered_map<id_type, T*> refs;
    id_type counter;
    public:
    id_type register_ref(T *self) {
        std::scoped_lock lock(weak_ref_lock);
        auto id = ++counter;
        refs[id] = self;
        return id;
    }
    void unregister_ref(T* self) {
        std::scoped_lock lock(weak_ref_lock);
        auto id = self->clear_id();
        refs.erase(id);
        self->~T();
    }
    void use_ref(id_type id, std::function<void(T*)> callback) {
        std::scoped_lock lock(weak_ref_lock);
        try {
            callback(refs.at(id));
        } catch (std::out_of_range) {
            callback(NULL);
        }
    }
};

enum class EventType {
    playback_state_changed = 1, media_opened, media_failed, media_ended, source_changed, cue_entered, cue_exited, track_failed
};

class Event {
    private:
        EventType type;
    public:
        Event(EventType type) : type(type) {}
        Event(const Event &source) : type(source.type) {}
};

class SynthesizerImplementation {
    private:
    id_type id;
    DWORD creation_thread_id;
    SpeechSynthesizer synth{nullptr};
    MediaPlayer player{nullptr};
    MediaSource current_source{nullptr};
    SpeechSynthesisStream current_stream{nullptr};
    MediaPlaybackItem currently_playing{nullptr};

    struct {
        MediaPlaybackSession::PlaybackStateChanged_revoker playback_state_changed;
        MediaPlayer::MediaEnded_revoker media_ended; MediaPlayer::MediaOpened_revoker media_opened;
        MediaPlayer::MediaFailed_revoker media_failed; MediaPlayer::SourceChanged_revoker source_changed;

        MediaPlaybackItem::TimedMetadataTracksChanged_revoker timed_metadata_tracks_changed;
        std::vector<TimedMetadataTrack::CueEntered_revoker> cue_entered;
        std::vector<TimedMetadataTrack::CueExited_revoker> cue_exited;
        std::vector<TimedMetadataTrack::TrackFailed_revoker> track_failed;
    } revoker;

    std::vector<Event> events;
    std::mutex events_lock;

    public:
    SynthesizerImplementation();

    void add_simple_event(EventType type) {
        try {
            std::scoped_lock lock(events_lock);
            events.emplace_back(type);
        } catch(...) {}
    }

    SpeechSynthesisStream synthesize(const std::wstring_view &text, bool is_ssml = false) {
        if (is_ssml) return synth.SynthesizeSsmlToStreamAsync(text).get();
        return synth.SynthesizeTextToStreamAsync(text).get();
    }

    void speak(const std::wstring_view &text, bool is_ssml = false) {
        revoker.cue_entered.clear();
        revoker.cue_exited.clear();
        revoker.track_failed.clear();
        current_stream = synthesize(text, is_ssml);
        current_source = MediaSource::CreateFromStream(current_stream, current_stream.ContentType());
        currently_playing = MediaPlaybackItem(current_source);
        auto self_id = id;
        revoker.timed_metadata_tracks_changed = currently_playing.TimedMetadataTracksChanged(winrt::auto_revoke, [self_id](auto, auto const &args) {
            auto change_type = args.CollectionChange();
            auto index = args.Index();
            synthesizer_weakrefs.use_ref(self_id, [change_type, index](auto s) {
            if (!s) return;
            switch (change_type) {
            case CollectionChange::ItemInserted: {
                s->register_metadata_handler_for_speech(s->currently_playing.TimedMetadataTracks().GetAt(index));
                } break;
            case CollectionChange::Reset:
                for (auto const& track : s->currently_playing.TimedMetadataTracks()) {
                    s->register_metadata_handler_for_speech(track);
                }
                break;
            }});
        });
        player.Source(currently_playing);
        for (auto const &track : currently_playing.TimedMetadataTracks()) {
            register_metadata_handler_for_speech(track);
        }
    }

    bool is_creation_thread() const noexcept {
        return creation_thread_id == GetCurrentThreadId();
    }

    id_type clear_id() noexcept {
        auto ans = id;
        id = 0;
        return ans;
    }

    void register_metadata_handler_for_speech(TimedMetadataTrack const& track) {
        fprintf(stderr, "99999999999 registering metadata handler\n");
        auto self_id = id;
#define simple_event_listener(method, event_type) \
        revoker.event_type.push_back(method(winrt::auto_revoke, [self_id](auto, const auto&) { \
        fprintf(stderr, "111111111 %s %u\n", #event_type, GetCurrentThreadId()); fflush(stderr); \
        synthesizer_weakrefs.use_ref(self_id, [](auto s) { \
            if (!s) return; \
            s->add_simple_event(EventType::event_type); \
            fprintf(stderr, "2222222222 %d\n", s->player.PlaybackSession().PlaybackState()); \
        }); \
    }));
        simple_event_listener(track.CueEntered, cue_entered);
        simple_event_listener(track.CueExited, cue_exited);
        simple_event_listener(track.TrackFailed, track_failed);
#undef simple_event_listener
        track.CueEntered([](auto, const auto&) {
            fprintf(stderr, "cue entered\n"); fflush(stderr);
        });
}


};

struct Synthesizer {
    PyObject_HEAD
    SynthesizerImplementation impl;
};

static PyTypeObject SynthesizerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static WeakRefs<SynthesizerImplementation> synthesizer_weakrefs;

SynthesizerImplementation::SynthesizerImplementation() {
    events.reserve(128);
    synth = SpeechSynthesizer();
    synth.Options().IncludeSentenceBoundaryMetadata(true);
    synth.Options().IncludeWordBoundaryMetadata(true);
    player = MediaPlayer();
    player.AudioCategory(MediaPlayerAudioCategory::Speech);
    player.AutoPlay(true);
    creation_thread_id = GetCurrentThreadId();
    id = synthesizer_weakrefs.register_ref(this);
    auto self_id = id;
#define simple_event_listener(method, event_type) \
        revoker.event_type = method(winrt::auto_revoke, [self_id](auto, const auto&) { \
        fprintf(stderr, "111111111 %s %u\n", #event_type, GetCurrentThreadId()); fflush(stderr); \
        synthesizer_weakrefs.use_ref(self_id, [](auto s) { \
            if (!s) return; \
            s->add_simple_event(EventType::event_type); \
            fprintf(stderr, "2222222222 %d\n", s->player.PlaybackSession().PlaybackState()); \
        }); \
    });
    simple_event_listener(player.PlaybackSession().PlaybackStateChanged, playback_state_changed);
    simple_event_listener(player.MediaOpened, media_opened);
    simple_event_listener(player.MediaFailed, media_failed);
    simple_event_listener(player.MediaEnded, media_ended);
    simple_event_listener(player.SourceChanged, source_changed);
#undef simple_event_listener
    player.PlaybackSession().PlaybackStateChanged([](auto, const auto&) {
        fprintf(stderr, "111111111 %s %u\n", "playback state changed", GetCurrentThreadId()); fflush(stderr); \
    });
    player.MediaOpened([](auto, const auto&) {
        fprintf(stderr, "111111111 %s %u\n", "media opened", GetCurrentThreadId()); fflush(stderr); \
    });
    player.MediaFailed([](auto, const auto&) {
        fprintf(stderr, "111111111 %s %u\n", "media failed", GetCurrentThreadId()); fflush(stderr); \
    });
    player.MediaEnded([](auto, const auto&) {
        fprintf(stderr, "111111111 %s %u\n", "media ended", GetCurrentThreadId()); fflush(stderr); \
    });
}

static PyObject*
Synthesizer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) { INITIALIZE_COM_IN_FUNCTION
	Synthesizer *self = (Synthesizer *) type->tp_alloc(type, 0);
    if (self) {
        auto i = &self->impl;
        try {
            new (i) SynthesizerImplementation();
        } CATCH_ALL_EXCEPTIONS("Failed to create SynthesizerImplementation object");
        if (PyErr_Occurred()) { Py_CLEAR(self); }
    }
    if (self) com.detach();
    return (PyObject*)self;
}

static void
Synthesizer_dealloc(Synthesizer *self) {
    auto *i = &self->impl;
    try {
        synthesizer_weakrefs.unregister_ref(i);
    } CATCH_ALL_EXCEPTIONS("Failed to destruct SynthesizerImplementation");
    if (PyErr_Occurred()) { PyErr_Print(); }
    Py_TYPE(self)->tp_free((PyObject*)self);
    CoUninitialize();
}

static void
ensure_current_thread_has_message_queue(void) {
    MSG msg;
    PeekMessage(&msg, NULL, WM_USER, WM_USER, PM_NOREMOVE);
}

#define PREPARE_METHOD_CALL ensure_current_thread_has_message_queue(); if (!self->impl.is_creation_thread()) { PyErr_SetString(PyExc_RuntimeError, "Cannot use a Synthesizer object from a thread other than the thread it was created in"); return NULL; }

static PyObject*
Synthesizer_speak(Synthesizer *self, PyObject *args) {
    PREPARE_METHOD_CALL;
    wchar_raii pytext;
    int is_ssml = 0;
	if (!PyArg_ParseTuple(args, "O&|p", py_to_wchar_no_none, &pytext, &is_ssml)) return NULL;
    try {
        self->impl.speak(pytext.as_view(), (bool)is_ssml);
    } CATCH_ALL_EXCEPTIONS("Failed to start speaking text");
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}


static PyObject*
Synthesizer_create_recording(Synthesizer *self, PyObject *args) {
    PREPARE_METHOD_CALL;
    wchar_raii pytext;
    PyObject *callback;
    int is_ssml = 0;
	if (!PyArg_ParseTuple(args, "O&O|p", py_to_wchar_no_none, &pytext, &callback, &is_ssml)) return NULL;
    if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be callable"); return NULL; }

    SpeechSynthesisStream stream{nullptr};
    try {
        stream = self->impl.synthesize(pytext.as_view(), (bool)is_ssml);
    } CATCH_ALL_EXCEPTIONS( "Failed to get SpeechSynthesisStream from text");
    if (PyErr_Occurred()) return NULL;
    unsigned long long stream_size = stream.Size(), bytes_read = 0;
    DataReader reader(stream);
    unsigned int n;
    const static unsigned int chunk_size = 16 * 1024;
    while (bytes_read < stream_size) {
        try {
            n = reader.LoadAsync(chunk_size).get();
        } CATCH_ALL_EXCEPTIONS("Failed to load data from DataReader");
        if (PyErr_Occurred()) return NULL;
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
    } CATCH_ALL_EXCEPTIONS("Could not convert Voice to dict");
    return NULL;
}


static PyObject*
all_voices(PyObject*, PyObject*) { INITIALIZE_COM_IN_FUNCTION
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
    } CATCH_ALL_EXCEPTIONS("Could not get all voices");
    return NULL;
}

static PyObject*
default_voice(PyObject*, PyObject*) { INITIALIZE_COM_IN_FUNCTION
    try {
        return voice_as_dict(SpeechSynthesizer::DefaultVoice());
    } CATCH_ALL_EXCEPTIONS("Could not get default voice");
    return NULL;
}

#define M(name, args) { #name, (PyCFunction)Synthesizer_##name, args, ""}
static PyMethodDef Synthesizer_methods[] = {
    M(create_recording, METH_VARARGS),
    M(speak, METH_VARARGS),
    {NULL, NULL, 0, NULL}
};
#undef M

static PyObject*
pump_waiting_messages(PyObject*, PyObject*) {
	UINT firstMsg = 0, lastMsg = 0;
    MSG msg;
    bool found = false;
	// Read all of the messages in this next loop,
	// removing each message as we read it.
	while (PeekMessage(&msg, NULL, firstMsg, lastMsg, PM_REMOVE)) {
		// If it's a quit message, we're out of here.
		if (msg.message == WM_QUIT) {
            Py_RETURN_NONE;
		}
        found = true;
		// Otherwise, dispatch the message.
		DispatchMessage(&msg);
	} // End of PeekMessage while loop

    if (found) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}


}}} */


struct Revokers {
    MediaPlaybackSession::PlaybackStateChanged_revoker playback_state_changed;
    MediaPlayer::MediaEnded_revoker media_ended; MediaPlayer::MediaOpened_revoker media_opened;
    MediaPlayer::MediaFailed_revoker media_failed; MediaPlayer::SourceChanged_revoker source_changed;

    MediaPlaybackItem::TimedMetadataTracksChanged_revoker timed_metadata_tracks_changed;
    std::vector<TimedMetadataTrack::CueEntered_revoker> cue_entered;
    std::vector<TimedMetadataTrack::CueExited_revoker> cue_exited;
    std::vector<TimedMetadataTrack::TrackFailed_revoker> track_failed;
};

class Synthesizer {
    private:
    SpeechSynthesizer synth{nullptr};
    MediaPlayer player{nullptr};
    MediaSource current_source{nullptr};
    SpeechSynthesisStream current_stream{nullptr};
    MediaPlaybackItem current_item{nullptr};
    std::atomic<id_type> current_cmd_id;

    Revokers revoker;
    std::recursive_mutex recursive_lock;

    void load_stream_for_playback(SpeechSynthesisStream const &stream, id_type cmd_id) {
        std::scoped_lock sl(recursive_lock);
        if (cmd_id != current_cmd_id.load()) return;
        revoker.playback_state_changed = player.PlaybackSession().PlaybackStateChanged(
                winrt::auto_revoke, [cmd_id](auto session, auto const&) {
            if (main_loop_is_running.load()) sx.output(
                cmd_id, "playback_state_changed", {{"state", json_val(session.PlaybackState())}});
        });
        revoker.media_opened = player.MediaOpened(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
            if (main_loop_is_running.load()) sx.output(
                cmd_id, "media_state_changed", {{"state", json_val("opened")}});
        });
        revoker.media_ended = player.MediaEnded(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
            if (main_loop_is_running.load()) sx.output(
                cmd_id, "media_state_changed", {{"state", json_val("ended")}});
        });
        revoker.media_failed = player.MediaFailed(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
            if (main_loop_is_running.load()) sx.output(
                cmd_id, "media_state_changed", {{"state", json_val("failed")}});
        });
            current_stream = stream;
            current_source = MediaSource::CreateFromStream(current_stream, current_stream.ContentType());
            current_item = MediaPlaybackItem(current_source);
            player.Source(current_item);
    }
    public:
    bool cmd_id_is_current(id_type cmd_id) const noexcept { return current_cmd_id.load() == cmd_id; }
    void output(id_type cmd_id, std::string_view const& type, json_val const && x) {
        std::scoped_lock sl(recursive_lock);
        if (cmd_id_is_current(cmd_id)) ::output(cmd_id, type, std::move(x));
    }
    void initialize() {
        synth = SpeechSynthesizer();
        synth.Options().IncludeSentenceBoundaryMetadata(true);
        synth.Options().IncludeWordBoundaryMetadata(true);
        player = MediaPlayer();
        player.AudioCategory(MediaPlayerAudioCategory::Speech);
        player.AutoPlay(true);
    }

    void stop_current_activity() {
        std::scoped_lock sl(recursive_lock);
        if (current_cmd_id.load()) {
            current_cmd_id.store(0);
            revoker = {};
            current_source = MediaSource{nullptr};
            current_stream = SpeechSynthesisStream{nullptr};
            current_item = MediaPlaybackItem{nullptr};
            player.Pause();
        }
    }

    winrt::fire_and_forget speak(id_type cmd_id, std::wstring_view const &text, bool is_ssml) {
        winrt::apartment_context main_thread;  // capture calling thread
        SpeechSynthesisStream stream{nullptr};
        { std::scoped_lock sl(recursive_lock);
            stop_current_activity();
            current_cmd_id.store(cmd_id);
        }
        if (is_ssml) stream = co_await synth.SynthesizeSsmlToStreamAsync(text);
        else stream = co_await synth.SynthesizeTextToStreamAsync(text);
        co_await main_thread;
        if (main_loop_is_running.load()) {
            load_stream_for_playback(stream, cmd_id);
        }
    }

};

static Synthesizer sx;

static inline std::wstring
decode_utf8(std::string_view const& src) {
    std::wstring ans(src.length() + 1, 0);
    size_t count = MultiByteToWideChar(CP_UTF8, 0, src.data(), (int)src.length(), ans.data(), (int)ans.length());
    if (count == 0) {
        switch(GetLastError()) {
            case ERROR_INSUFFICIENT_BUFFER:
                throw std::exception("Could not convert UTF-8 to UTF-16: buffer too small");
            case ERROR_INVALID_PARAMETER:
                throw std::exception("Could not convert UTF-8 to UTF-16: invalid parameter");
            case ERROR_NO_UNICODE_TRANSLATION:
                throw std::exception("Could not convert UTF-8 to UTF-16: invalid UTF-8 encountered");
            default:
                throw std::exception("Could not convert UTF-8 to UTF-16: unknown error");
        }
    }
    count++; // ensure trailing null
    if (ans.length() > count) {
        auto extra = ans.length() - count;
        ans.erase(ans.length() - extra, extra);
    }
    return ans;
}

static void
handle_speak(id_type cmd_id, std::vector<std::wstring_view> &parts) {
    bool is_ssml = false, is_shm = false;
    try {
        is_ssml = parts.at(0) == L"ssml";
        is_shm = parts.at(1) == L"shm";
    } catch (std::exception const&) {
        throw std::string("Not a well formed speak command");
    }
    parts.erase(parts.begin(), parts.begin() + 2);
    auto address = join(parts);
    if (address.size() == 0) throw std::string("Address missing");
    if (is_shm) {
        throw std::string("TODO: Implement support for SHM");
    }
    sx.speak(cmd_id, address, is_ssml);
}

static long long
handle_stdin_message(winrt::hstring const &&msg) {
    if (msg == L"exit") {
        return 0;
    }
    id_type cmd_id;
    std::wstring_view command;
    bool ok = false;
    std::vector<std::wstring_view> parts;
    try {
        parts = split(msg);
        command = parts.at(1); cmd_id = parse_id(parts.at(0));
        if (cmd_id == 0) {
            throw std::exception("Command id of zero is not allowed");
        }
        parts.erase(parts.begin(), parts.begin() + 2);
        ok = true;
    } CATCH_ALL_EXCEPTIONS((std::string("Invalid input message: ") + winrt::to_string(msg)), 0);
    if (!ok) return -1;
    try {
        if (command == L"exit") {
            try {
                return parse_id(parts.at(0));
            } catch(...) { }
            return 0;
        }
        else if (command == L"echo") {
            output(cmd_id, "echo", {{"msg", json_val(std::move(join(parts)))}});
        }
        else if (command == L"default_voice") {
            output(cmd_id, "default_voice", SpeechSynthesizer::DefaultVoice());
        }
        else if (command == L"all_voices") {
            output(cmd_id, "all_voices", SpeechSynthesizer::AllVoices());
        }
        else if (command == L"speak") {
            handle_speak(cmd_id, parts);
        }
        else throw std::string("Unknown command: ") + winrt::to_string(command);
    } CATCH_ALL_EXCEPTIONS("Error handling input message", cmd_id);
    return -1;
}

static PyObject*
run_main_loop(PyObject*, PyObject*) {
    winrt::init_apartment(); // MTA (multi-threaded apartment)
    main_thread_id = GetCurrentThreadId();
    MSG msg;
    long long exit_code = 0;
    bool ok = false;
    try {
        new (&sx) Synthesizer();
        sx.initialize();
        ok = true;
    } CATCH_ALL_EXCEPTIONS("Error initializing Synthesizer", 0);
    if (!ok) return PyLong_FromUnsignedLongLong(1);

    Py_BEGIN_ALLOW_THREADS;
    main_loop_is_running.store(true);
    PeekMessage(&msg, NULL, WM_USER, WM_USER, PM_NOREMOVE);  // ensure we have a message queue

    if (_isatty(_fileno(stdin))) {
        std::cout << "Welcome to winspeech. Type exit to quit." << std::endl;
    }

    std::string input_buffer;
    while (true) {
        try {
            if (!std::getline(std::cin, input_buffer)) {
                if (!std::cin.eof()) exit_code = 1;
                break;
            }
            rtrim(input_buffer);
            if (input_buffer.size() > 0) {
                if ((exit_code = handle_stdin_message(std::move(winrt::to_hstring(input_buffer)))) >= 0) break;
            }
        } catch(...) {
            exit_code = 1;
            output_error(0, "Unknown exception type reading and handling line of input", "", __LINE__);
            break;
        }
    }

    main_loop_is_running.store(false);
    Py_END_ALLOW_THREADS;

    try {
        sx.stop_current_activity();
        (&sx)->~Synthesizer();
    } CATCH_ALL_EXCEPTIONS("Error stopping all activity", 0);

    return PyLong_FromLongLong(exit_code);
}

#define M(name, args) { #name, name, args, ""}
static PyMethodDef methods[] = {
    M(run_main_loop, METH_NOARGS),
    {NULL, NULL, 0, NULL}
};
#undef M

static int
exec_module(PyObject *m) {
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
