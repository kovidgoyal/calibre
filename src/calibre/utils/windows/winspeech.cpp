/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <algorithm>
#include <atomic>
#include <filesystem>
#include <array>
#include <string>
#include <string_view>
#include <vector>
#include <map>
#include <deque>
#include <charconv>
#include <memory>
#include <fstream>
#include <sstream>
#include <mutex>
#include <filesystem>
#include <functional>
#include <iostream>
#include <unordered_map>
#include <io.h>
#include <winrt/base.h>
#include <winrt/windows.foundation.h>
#include <winrt/windows.foundation.collections.h>
#include <winrt/windows.storage.streams.h>
#include <winrt/windows.media.speechsynthesis.h>
#include <winrt/windows.media.core.h>
#include <winrt/windows.media.playback.h>

#ifdef max
#undef max
#endif
using namespace winrt::Windows::Foundation;
using namespace winrt::Windows::Foundation::Collections;
using namespace winrt::Windows::Media::SpeechSynthesis;
using namespace winrt::Windows::Media::Playback;
using namespace winrt::Windows::Media::Core;
using namespace winrt::Windows::Storage::Streams;
typedef uint64_t id_type;

static std::mutex output_lock;
static DWORD main_thread_id;

template<typename T> static void
__debug_multiple_impl(T x) {
    if constexpr (std::is_same_v<T, wchar_t*> || std::is_same_v<T, std::wstring> || std::is_same_v<T, winrt::hstring> || std::is_same_v<T, std::wstring_view>) {
        std::cerr << winrt::to_string(x);
    } else {
        std::cerr << x;
    }
}

template<typename T> static void
__debug_multiple(T x) {
    __debug_multiple_impl(x);
    std::cerr << std::endl;
}

template<typename T, typename... Args> static void
__debug_multiple(T x, Args... args) {
    __debug_multiple_impl(x);
    std::cerr << " ";
    __debug_multiple(args...);
}

template<typename... Args> static void
debug(Args... args) {
    std::scoped_lock _sl_(output_lock);
    DWORD tid = GetCurrentThreadId();
    if (tid == main_thread_id) std::cerr << "thread-main"; else std::cerr << "thread-" << tid;
    std::cerr << ": ";
    __debug_multiple(args...);
}

static std::atomic_bool main_loop_is_running;
enum {
    STDIN_FAILED = 1,
    STDIN_MSG,
    EXIT_REQUESTED
};

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

static double
parse_double(const wchar_t *raw) {
    std::wistringstream s(raw, std::ios_base::in);
    s.imbue(std::locale("C"));
    double ans;
    s >> ans;
    return ans;
}

static void
serialize_string_for_json(std::string const &src, std::ostream &out) {
    out << '"';
    for (auto ch : src) {
        switch(ch) {
            case '\\':
                out << "\\\\"; break;
            case '"':
                out << "\\\""; break;
            case '\n':
                out << "\\n"; break;
            case '\r':
                out << "\\r"; break;
            default:
                out << ch; break;
        }
    }
    out << '"';
}

template<typename T> static void
serialize_integer(std::ostream &out, T val, int base = 10) {
    std::array<char, 16> str;
    if (auto [ptr, ec] = std::to_chars(str.data(), str.data() + str.size(), val, base); ec == std::errc()) {
        out << std::string_view(str.data(), ptr - str.data());
    } else {
        throw std::exception(std::make_error_code(ec).message().c_str());
    }
}

template<typename T>static void
serialize_float(std::ostream &out, T val, std::chars_format fmt = std::chars_format::fixed) {
    std::array<char, 16> str;
    if (auto [ptr, ec] = std::to_chars(str.data(), str.data() + str.size(), val, fmt); ec == std::errc()) {
        out << std::string_view(str.data(), ptr - str.data());
    } else {
        throw std::exception(std::make_error_code(ec).message().c_str());
    }
}


class json_val {  // {{{
private:
    enum { DT_INT, DT_UINT, DT_STRING, DT_LIST, DT_OBJECT, DT_NONE, DT_BOOL, DT_FLOAT } type;
    std::string s;
    bool b;
    double f;
    int64_t i;
    uint64_t u;
    std::vector<json_val> list;
    std::map<std::string, json_val> object;

    void serialize(std::ostream &out) const {
        switch(type) {
            case DT_NONE:
                out << "nil"; break;
            case DT_BOOL:
                out << (b ? "true" : "false"); break;
            case DT_INT:
                // this is not really correct since JS has various limits on numeric types, but good enough for us
                serialize_integer(out, i); break;
            case DT_UINT:
                // this is not really correct since JS has various limits on numeric types, but good enough for us
                serialize_integer(out, u); break;
            case DT_FLOAT:
                // again not technically correct
                serialize_float(out, f); break;
            case DT_STRING:
                return serialize_string_for_json(s, out);
            case DT_LIST: {
                out << '[';
                bool first = true;
                for (auto const &i : list) {
                    if (!first) out << ", ";
                    first = false;
                    i.serialize(out);
                }
                out << ']';
                break;
            }
            case DT_OBJECT: {
                out << '{';
                bool first = true;
                for (const auto& [key, value]: object) {
                    if (!first) out << ", ";
                    first = false;
                    serialize_string_for_json(key, out);
                    out << ": ";
                    value.serialize(out);
                }
                out << '}';
                break;
            }
        }
    }

public:
    json_val() : type(DT_NONE) {}
    json_val(std::string &&text) : type(DT_STRING), s(text) {}
    json_val(const char *ns) : type(DT_STRING), s(ns) {}
    json_val(winrt::hstring const& text) : type(DT_STRING), s(winrt::to_string(text)) {}
    json_val(std::wstring const& text) : type(DT_STRING), s(winrt::to_string(text)) {}
    json_val(std::string_view text) : type(DT_STRING), s(text) {}
    json_val(std::vector<json_val> &&items) : type(DT_LIST), list(items) {}
    json_val(std::map<std::string, json_val> &&m) : type(DT_OBJECT), object(m) {}
    json_val(std::initializer_list<std::pair<const std::string, json_val>> const& vals) : type(DT_OBJECT), object(vals) { }

    static json_val from_hresult(HRESULT hr) {
        json_val ans; ans.type = DT_STRING;
        std::array<char, 16> str;
        str[0] = '0'; str[1] = 'x';
        if (auto [ptr, ec] = std::to_chars(str.data()+2, str.data() + str.size(), (uint32_t)hr, 16); ec == std::errc()) {
            ans.s = std::string(str.data(), ptr - str.data());
        } else {
            throw std::exception(std::make_error_code(ec).message().c_str());
        }
        return ans;
    }

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

    json_val(MediaPlayerError const& e) : type(DT_STRING) {
        // https://learn.microsoft.com/en-us/uwp/api/windows.media.playback.mediaplayererror
        switch(e) {
            case MediaPlayerError::Unknown: s = "unknown"; break;
            case MediaPlayerError::Aborted: s = "aborted"; break;
            case MediaPlayerError::NetworkError: s = "network_error"; break;
            case MediaPlayerError::DecodingError: s = "decoding_error"; break;
            case MediaPlayerError::SourceNotSupported: s = "source_not_supported"; break;
            default: s = "unknown"; break;
        }
    }

    json_val(winrt::Windows::Foundation::TimeSpan const &t) : type(DT_INT) {
        i = std::chrono::nanoseconds(t).count();
    }

    json_val(winrt::hstring const &label, SpeechCue const &cue) : type(DT_OBJECT) {
        object = {
            {"type", label},
            {"text", cue.Text()},
            {"start_time", cue.StartTime()},
            {"start_pos_in_text", cue.StartPositionInInput().Value()},
            {"end_pos_in_text", cue.EndPositionInInput().Value()},
        };
    }

    template<typename T> json_val(T x) {
        static_assert(sizeof(bool) < sizeof(int16_t), "The bool type on this machine is more than one byte");
        if constexpr (std::is_same_v<T, int64_t> || std::is_same_v<T, int32_t> || std::is_same_v<T, int16_t>) {
            type = DT_INT;
            i = x;
        } else if constexpr (std::is_same_v<T, uint64_t> || std::is_same_v<T, uint32_t> || std::is_same_v<T, uint16_t>) {
            type = DT_UINT;
            u = x;
        } else if constexpr (std::is_same_v<T, float> || std::is_same_v<T, double>) {
            type = DT_FLOAT;
            f = x;
        } else if constexpr (std::is_same_v<T, bool>) {
            type = DT_BOOL;
            b = x;
        }
#ifdef _MSVC
        else {
            static_assert(false, "Unknown type T cannot be converted to JSON");
        }
#endif
    }

    friend std::ostream& operator<<(std::ostream &os, const json_val &self) {
        self.serialize(os);
        return os;
    }

}; // }}}

static void
output(id_type cmd_id, std::string_view const &msg_type, json_val const &&msg) {
    std::scoped_lock sl(output_lock);
    try {
        std::cout << cmd_id << " " << msg_type << " " << msg << std::endl;
    } catch(...) {}
}

static void
output_error(id_type cmd_id, std::string_view const &msg, std::string_view const &error, int64_t line, HRESULT hr=S_OK) {
    std::map<std::string, json_val> m = {{"msg", msg}, {"error", error}, {"file", "winspeech.cpp"}, {"line", line}};
    if (hr != S_OK) m["hr"] = json_val::from_hresult(hr);
    output(cmd_id, "error", std::move(m));
}

#define CATCH_ALL_EXCEPTIONS(msg, cmd_id) \
  catch(winrt::hresult_error const& ex) { \
    output_error(cmd_id, msg, winrt::to_string(ex.message()), __LINE__, ex.to_abi()); \
} catch(const std::system_error& ex) { \
    output_error(cmd_id, msg, "system_error with code: " + std::to_string(ex.code().value()) + " and meaning: " + ex.what(), __LINE__); \
} catch (std::exception const &ex) { \
    output_error(cmd_id, msg, ex.what(), __LINE__); \
} catch (std::string const &ex) { \
    output_error(cmd_id, msg, ex, __LINE__); \
} catch (std::wstring const &ex) { \
    output_error(cmd_id, msg, winrt::to_string(ex), __LINE__); \
} catch (...) { \
    output_error(cmd_id, msg, "Unknown exception type was raised", __LINE__); \
}

struct Revokers {
    MediaPlaybackSession::PlaybackStateChanged_revoker playback_state_changed;
    MediaPlayer::MediaEnded_revoker media_ended; MediaPlayer::MediaOpened_revoker media_opened;
    MediaPlayer::MediaFailed_revoker media_failed; MediaPlayer::SourceChanged_revoker source_changed;

    MediaPlaybackItem::TimedMetadataTracksChanged_revoker timed_metadata_tracks_changed;
    std::vector<TimedMetadataTrack::CueEntered_revoker> cue_entered;
    std::vector<TimedMetadataTrack::CueExited_revoker> cue_exited;
    std::vector<TimedMetadataTrack::TrackFailed_revoker> track_failed;
};

struct Mark {
    uint32_t id, pos_in_text;
    Mark(uint32_t id, uint32_t pos) : id(id), pos_in_text(pos) {}
};
typedef std::vector<Mark> Marks;

class Synthesizer {
    private:
    SpeechSynthesizer synth{nullptr};
    MediaPlayer player{nullptr};
    MediaSource current_source{nullptr};
    SpeechSynthesisStream current_stream{nullptr};
    MediaPlaybackItem current_item{nullptr};
    std::vector<wchar_t> current_text_storage;
    Marks current_marks;
    int32_t last_reported_mark_index;
    std::atomic<id_type> current_cmd_id;

    Revokers revoker;
    std::recursive_mutex recursive_lock;

    public:
    // Speak {{{
    void register_metadata_handler_for_track(uint32_t index, id_type cmd_id);
    void load_stream_for_playback(SpeechSynthesisStream const &&stream, id_type cmd_id, bool is_cued);
    winrt::fire_and_forget speak(id_type cmd_id, std::wstring_view const &text, bool is_ssml, bool is_cued, std::vector<wchar_t> &&buf, Marks const && marks);
    void register_metadata_handler_for_speech(id_type cmd_id, long index);
    bool cmd_id_is_current(id_type cmd_id) const noexcept { return current_cmd_id.load() == cmd_id; }
    void on_cue_entered(id_type cmd_id, const winrt::hstring &label, const SpeechCue &cue);
    // }}}

    winrt::fire_and_forget save(id_type cmd_id, std::wstring_view const &text, bool is_ssml, std::vector<wchar_t> &&buf, std::filesystem::path path);
    void start_save_stream(SpeechSynthesisStream const &&stream, std::filesystem::path path, id_type cmd_id);

    void initialize() {
        synth = SpeechSynthesizer();
        player = MediaPlayer();
        player.AudioCategory(MediaPlayerAudioCategory::Speech);
        player.AutoPlay(true);
    }

    void output(id_type cmd_id, std::string_view const& type, json_val const && x) {
        std::scoped_lock sl(recursive_lock);
        if (cmd_id_is_current(cmd_id)) ::output(cmd_id, type, std::move(x));
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
            current_text_storage = std::vector<wchar_t>();
            current_marks = Marks();
            last_reported_mark_index = -1;
        }
    }

    double volume() const {
        return synth.Options().AudioVolume();
    }

    void volume(double val) {
        if (val < 0 || val > 1) throw std::out_of_range("Invalid volume value must be between 0 and 1");
        std::scoped_lock sl(recursive_lock);
        synth.Options().AudioVolume(val);
    }

    double rate() const {
        return synth.Options().SpeakingRate();
    }

    void rate(double val) {
        if (val < 0.5 || val > 6.0) throw std::out_of_range("Invalid rate value must be between 0.5 and 6");
        std::scoped_lock sl(recursive_lock);
        synth.Options().SpeakingRate(val);
    }

    double pitch() const {
        return synth.Options().AudioPitch();
    }

    void pitch(double val) {
        if (val < 0 || val > 2) throw std::out_of_range("Invalid pitch value must be between 0 and 2");
        std::scoped_lock sl(recursive_lock);
        synth.Options().AudioPitch(val);
    }

    void pause() const {
        player.Pause();
    }

    void play() const {
        player.Play();
    }

    bool toggle() const {
        switch (player.PlaybackSession().PlaybackState()) {
            case MediaPlaybackState::Playing: pause(); return true;
            case MediaPlaybackState::Paused: play(); return true;
            default: return false;
        }
    }

    MediaPlaybackState playback_state() const {
        return player.PlaybackSession().PlaybackState();
    }

};

static Synthesizer sx;

static size_t
decode_into(std::string_view src, std::wstring_view dest) {
    int n = MultiByteToWideChar(CP_UTF8, 0, src.data(), (int)src.size(), (wchar_t*)dest.data(), (int)dest.size());
    if (n == 0 && src.size() > 0) {
        throw std::system_error(GetLastError(), std::system_category(), "Failed to decode cued text");
    }
    return n;
}

static std::wstring_view
parse_cued_text(std::string_view src, Marks &marks, std::wstring_view dest) {
    size_t dest_pos = 0;
    if (dest.size() < src.size()) throw std::exception("Destination buffer for parse_cued_text() too small");
    while (src.size()) {
        auto pos = src.find('\0');
        size_t limit = pos == std::string_view::npos ? src.size() : pos;
        if (limit) {
            dest_pos += decode_into(src.substr(0, limit), dest.substr(dest_pos, dest.size() - dest_pos));
            src = src.substr(limit, src.size() - limit);
        }
        if (pos != std::string_view::npos) {
            src = src.substr(1, src.size() - 1);
            if (src.size() >= 4) {
                uint32_t mark = *((uint32_t*)src.data());
                marks.emplace_back(mark, (uint32_t)dest_pos);
                src = src.substr(4, src.size() - 4);
            }
        }
    }
    return dest.substr(0, dest_pos);
}

static std::wstring_view
read_from_shm(id_type cmd_id, const std::wstring_view size, const std::wstring &address, std::vector<wchar_t> &buf, Marks &marks, bool is_cued=false) {
    id_type shm_size = parse_id(size);
    handle_raii_null handle(OpenFileMappingW(FILE_MAP_READ, false, address.data()));
    if (!handle) {
        output_error(cmd_id, "Could not open shared memory at: " + winrt::to_string(address), winrt::to_string(get_last_error()), __LINE__);
        return {};
    }
    mapping_raii mapping(MapViewOfFile(handle.ptr(), FILE_MAP_READ, 0, 0, (SIZE_T)shm_size));
    if (!mapping) {
        output_error(cmd_id, "Could not map shared memory", winrt::to_string(get_last_error()), __LINE__);
        return {};
    }
    buf.reserve(shm_size + 2);
    std::string_view src((const char*)mapping.ptr(), shm_size);
    std::wstring_view dest(buf.data(), buf.capacity());
    if (is_cued) return parse_cued_text(src, marks, dest);
    return std::wstring_view(buf.data(), decode_into(src, dest));
}


// Speak {{{
void Synthesizer::on_cue_entered(id_type cmd_id, const winrt::hstring &label, const SpeechCue &cue) {
    std::scoped_lock sl(recursive_lock);
    if (!cmd_id_is_current(cmd_id)) return;
    output(cmd_id, "cue_entered", json_val(label, cue));
    if (label != L"SpeechWord") return;
    uint32_t pos = cue.StartPositionInInput().Value();
    for (int32_t i = std::max(0, last_reported_mark_index); i < (int32_t)current_marks.size(); i++) {
        int32_t idx = -1;
        if (current_marks[i].pos_in_text > pos) {
            idx = i-1;
            if (idx == last_reported_mark_index && current_marks[i].pos_in_text - pos < 3) idx = i;
        } else if (current_marks[i].pos_in_text == pos) idx = i;
        if (idx > -1) {
            output(cmd_id, "mark_reached", {{"id", current_marks[idx].id}});
            last_reported_mark_index = idx;
            break;
        }
    }
}

void Synthesizer::register_metadata_handler_for_speech(id_type cmd_id, long index) {
    std::scoped_lock sl(recursive_lock);
    if (!cmd_id_is_current(cmd_id)) return;
    if (index < 0) {
        for (uint32_t i = 0; i < current_item.TimedMetadataTracks().Size(); i++) {
            register_metadata_handler_for_track(i, cmd_id);
        }
    } else {
        register_metadata_handler_for_track(index, cmd_id);
    }
}

void
Synthesizer::register_metadata_handler_for_track(uint32_t index, id_type cmd_id) {
    TimedMetadataTrack track = current_item.TimedMetadataTracks().GetAt(index);
    std::scoped_lock sl(recursive_lock);
    if (current_cmd_id.load() != cmd_id) return;
    revoker.cue_entered.push_back(track.CueEntered(winrt::auto_revoke, [cmd_id](auto track, const auto& args) {
        if (main_loop_is_running.load()) sx.on_cue_entered(cmd_id, track.Label(), args.Cue().template as<SpeechCue>());
    }));
    revoker.cue_exited.push_back(track.CueExited(winrt::auto_revoke, [cmd_id](auto track, const auto& args) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "cue_exited", json_val(track.Label(), args.Cue().template as<SpeechCue>()));
    }));
    revoker.track_failed.push_back(track.TrackFailed(winrt::auto_revoke, [cmd_id](auto, const auto& args) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "track_failed", {});
    }));
    current_item.TimedMetadataTracks().SetPresentationMode((unsigned int)index, TimedMetadataTrackPresentationMode::ApplicationPresented);
}

void
Synthesizer::load_stream_for_playback(SpeechSynthesisStream const &&stream, id_type cmd_id, bool is_cued) {
    std::scoped_lock sl(recursive_lock);
    if (cmd_id != current_cmd_id.load()) return;
    current_stream = stream;
    current_source = MediaSource::CreateFromStream(current_stream, current_stream.ContentType());

    revoker.playback_state_changed = player.PlaybackSession().PlaybackStateChanged(
            winrt::auto_revoke, [cmd_id](auto session, auto const&) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "playback_state_changed", {{"state", session.PlaybackState()}});
    });
    revoker.media_opened = player.MediaOpened(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "media_state_changed", {{"state", "opened"}});
    });
    revoker.media_ended = player.MediaEnded(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "media_state_changed", {{"state", "ended"}});
    });
    revoker.media_failed = player.MediaFailed(winrt::auto_revoke, [cmd_id](auto player, auto const& args) {
        if (main_loop_is_running.load()) sx.output(
            cmd_id, "media_state_changed", {{"state", "failed"}, {"error", args.ErrorMessage()}, {"code", args.Error()}});
    });
    current_item = MediaPlaybackItem(current_source);

    revoker.timed_metadata_tracks_changed = current_item.TimedMetadataTracksChanged(winrt::auto_revoke,
        [cmd_id](auto, auto const &args) {
        auto change_type = args.CollectionChange();
        long index;
        switch (change_type) {
            case CollectionChange::ItemInserted: index = args.Index(); break;
            case CollectionChange::Reset: index = -1; break;
            default: index = -2; break;
        }
        if (index > -2 && main_loop_is_running.load()) sx.register_metadata_handler_for_speech(cmd_id, index);
    });
    register_metadata_handler_for_speech(cmd_id, -1);

    player.Source(current_item);
}

winrt::fire_and_forget Synthesizer::speak(id_type cmd_id, std::wstring_view const &text, bool is_ssml, bool is_cued, std::vector<wchar_t> &&buf, Marks const && marks) {
    SpeechSynthesisStream stream{nullptr};
    { std::scoped_lock sl(recursive_lock);
        stop_current_activity();
        current_cmd_id.store(cmd_id);
        current_text_storage = std::move(buf);
        current_marks = std::move(marks);
        synth.Options().IncludeSentenceBoundaryMetadata(true);
        synth.Options().IncludeWordBoundaryMetadata(true);
    }
    output(cmd_id, "synthesizing", {{"ssml", is_ssml}, {"num_marks", current_marks.size()}, {"text_length", text.size()}});
    bool ok = false;
    try {
        if (is_ssml) stream = co_await synth.SynthesizeSsmlToStreamAsync(text);
        else stream = co_await synth.SynthesizeTextToStreamAsync(text);
        ok = true;
    } CATCH_ALL_EXCEPTIONS("Failed to synthesize speech", cmd_id);
    if (ok) {
        if (main_loop_is_running.load()) {
            try {
                load_stream_for_playback(std::move(stream), cmd_id, is_cued);
            } CATCH_ALL_EXCEPTIONS("Failed to load synthesized stream for playback", cmd_id);
        }
    }
}

static void
handle_speak(id_type cmd_id, std::vector<std::wstring_view> &parts) {
    bool is_ssml = false, is_shm = false, is_cued = false;
    try {
        is_ssml = parts.at(0) == L"ssml";
        is_shm = parts.at(1) == L"shm";
        is_cued = parts.at(0) == L"cued";
    } catch (std::exception const&) {
        throw std::string("Not a well formed speak command");
    }
    parts.erase(parts.begin(), parts.begin() + 2);
    std::wstring address;
    Marks marks;
    std::vector<wchar_t> buf;
    std::wstring_view text;
    if (is_shm) {
        text = read_from_shm(cmd_id, parts.at(0), std::wstring(parts.at(1)), buf, marks, is_cued);
        if (text.size() == 0) return;
    } else {
        address = join(parts);
        if (address.size() == 0) throw std::string("Address missing");
        buf.reserve(address.size() + 1);
        text = std::wstring_view(buf.data(), address.size());
        address.copy(buf.data(), address.size());
    }
    *((wchar_t*)text.data() + text.size()) = 0;  // ensure NULL termination
    sx.speak(cmd_id, text, is_ssml, is_cued, std::move(buf), std::move(marks));
}
// }}}

// Save {{{
static winrt::fire_and_forget
save_stream(SpeechSynthesisStream const &&stream, std::filesystem::path path, id_type cmd_id) {
    unsigned long long stream_size = stream.Size(), bytes_read = 0;
    DataReader reader(stream);
    unsigned int n;
    const static unsigned int chunk_size = 16 * 1024;
    std::array<uint8_t, chunk_size> buf;
    std::ofstream outfile;
    bool ok = false;
    try {
        outfile.open(path.string(), std::ios::out | std::ios::trunc);
        ok = true;
    } CATCH_ALL_EXCEPTIONS("Failed to create file: " + path.string(), cmd_id);
    if (!ok) co_return;
    while (bytes_read < stream_size) {
        try {
            n = co_await reader.LoadAsync(chunk_size);
            ok = true;
        } CATCH_ALL_EXCEPTIONS("Failed to load data from DataReader", cmd_id);
        if (!ok) co_return;
        if (n > 0) {
            bytes_read += n;
            ok = false;
            try {
                reader.ReadBytes(winrt::array_view(buf.data(), buf.data() + n));
                outfile.write((const char*)buf.data(), n);
                if (!outfile.good()) throw "Failed to write to output file";
                ok = true;
            } CATCH_ALL_EXCEPTIONS("Failed to save bytes from DataReader to file", cmd_id);
            if (!ok) co_return;
        }
    }
    output(cmd_id, "saved", {{"size", bytes_read}});
}

void
Synthesizer::start_save_stream(SpeechSynthesisStream const &&stream, std::filesystem::path path, id_type cmd_id) {
    std::scoped_lock sl(recursive_lock);
    try {
        save_stream(std::move(stream), path, cmd_id);
    } CATCH_ALL_EXCEPTIONS("Failed to save loaded stream", cmd_id);
    stop_current_activity();
}

winrt::fire_and_forget Synthesizer::save(id_type cmd_id, std::wstring_view const &text, bool is_ssml, std::vector<wchar_t> &&buf, std::filesystem::path path) {
    SpeechSynthesisStream stream{nullptr};
    { std::scoped_lock sl(recursive_lock);
        stop_current_activity();
        current_cmd_id.store(cmd_id);
        current_text_storage = std::move(buf);
        synth.Options().IncludeSentenceBoundaryMetadata(false);
        synth.Options().IncludeWordBoundaryMetadata(false);
    }
    bool ok = false;
    try {
        if (is_ssml) stream = co_await synth.SynthesizeSsmlToStreamAsync(text);
        else stream = co_await synth.SynthesizeTextToStreamAsync(text);
        ok = true;
    } CATCH_ALL_EXCEPTIONS("Failed to synthesize speech", cmd_id);
    if (ok) {
        if (main_loop_is_running.load()) {
            try {
                sx.start_save_stream(std::move(stream), path, cmd_id);
            } CATCH_ALL_EXCEPTIONS("Failed to load synthesized stream for save", cmd_id);
        }
    }
}

static void
handle_save(id_type cmd_id, std::vector<std::wstring_view> &parts) {
    bool is_ssml;
    try {
        is_ssml = parts.at(0) == L"ssml";
    } catch (std::exception const&) {
        throw "Not a well formed save command"s;
    }
    std::vector<wchar_t> buf;
    std::wstring address;
    Marks marks;
    std::wstring_view text = read_from_shm(cmd_id, parts.at(1), std::wstring(parts.at(2)), buf, marks);
    if (text.size() == 0) return;
    parts.erase(parts.begin(), parts.begin() + 3);
    *((wchar_t*)text.data() + text.size()) = 0;  // ensure NULL termination
    auto filename = join(parts);
    auto path = std::filesystem::absolute(filename);
    output(cmd_id, "saving", {{"ssml", is_ssml}, {"output_path", path.string()}});
    sx.save(cmd_id, text, is_ssml, std::move(buf), path);
}
// }}}

static int64_t
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
        else if (command == L"play") {
            sx.play();
            output(cmd_id, "play", {{"playback_state", sx.playback_state()}});
        }
        else if (command == L"pause") {
            sx.play();
            output(cmd_id, "pause", {{"playback_state", sx.playback_state()}});
        }
        else if (command == L"state") {
            sx.play();
            output(cmd_id, "state", {{"playback_state", sx.playback_state()}});
        }
        else if (command == L"echo") {
            output(cmd_id, "echo", {{"msg", join(parts)}});
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
        else if (command == L"volume") {
            if (parts.size()) {
                auto vol = parse_double(parts[0].data());
                sx.volume(vol);
            }
            output(cmd_id, "volume", {{"value", sx.volume()}});
        }
        else if (command == L"rate") {
            if (parts.size()) {
                auto rate = parse_double(parts[0].data());
                sx.rate(rate);
            }
            output(cmd_id, "rate", {{"value", sx.rate()}});
        }
        else if (command == L"pitch") {
            if (parts.size()) {
                auto rate = parse_double(parts[0].data());
                sx.rate(rate);
            }
            output(cmd_id, "pitch", {{"pitch", sx.rate()}});
        }
        else if (command == L"save") {
            handle_save(cmd_id, parts);
        }
        else throw std::string("Unknown command: ") + winrt::to_string(command);
    } CATCH_ALL_EXCEPTIONS("Error handling input message", cmd_id);
    return -1;
}


static PyObject*
run_main_loop(PyObject*, PyObject*) {
    try {
        std::cout.imbue(std::locale("C"));
        std::cin.imbue(std::locale("C"));
        std::cerr.imbue(std::locale("C"));
        std::wcin.imbue(std::locale("C"));
        std::wcout.imbue(std::locale("C"));
        std::wcerr.imbue(std::locale("C"));
    } CATCH_ALL_EXCEPTIONS("Failed to set stdio locales to C", 0);
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    main_thread_id = GetCurrentThreadId();
    MSG msg;
    int64_t exit_code = 0;
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

PyMODINIT_FUNC PyInit_winspeech(void) {
    module_def.m_name     = "winspeech";
    module_def.m_doc      = "Windows Speech API wrapper";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
