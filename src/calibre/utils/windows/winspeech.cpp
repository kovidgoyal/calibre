/*
 * winspeech.cpp
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#include "common.h"

#include <atomic>
#include <filesystem>
#include <string_view>
#include <fstream>
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
#include <winrt/windows.media.devices.h>
#include <winrt/windows.devices.enumeration.h>

#ifdef max
#undef max
#endif
using namespace winrt::Windows::Foundation;
using namespace winrt::Windows::Foundation::Collections;
using namespace winrt::Windows::Media::SpeechSynthesis;
using namespace winrt::Windows::Media::Playback;
using namespace winrt::Windows::Media::Core;
using namespace winrt::Windows::Media::Devices;
using namespace winrt::Windows::Devices::Enumeration;
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
            {"display_name", voice.DisplayName()},
            {"description", voice.Description()},
            {"id", voice.Id()},
            {"language", voice.Language()},
            {"gender", gender},
        };
    }

    json_val(IVectorView<VoiceInformation> const& voices) : type(DT_LIST) {
        list.reserve(voices.Size());
        for(auto const& voice : voices) {
            list.emplace_back(voice);
        }
    }

    json_val(TimedMetadataTrackErrorCode const ec) : type(DT_STRING) {
        switch(ec) {
            case TimedMetadataTrackErrorCode::DataFormatError:
                s = "data_format_error"; break;
            case TimedMetadataTrackErrorCode::NetworkError:
                s = "network_error"; break;
            case TimedMetadataTrackErrorCode::InternalError:
                s = "internal_error"; break;
            case TimedMetadataTrackErrorCode::None:
                s = "none"; break;
        }
    }

    json_val(DeviceInformationKind const dev) : type(DT_STRING) {
        switch(dev) {
            case DeviceInformationKind::Unknown:
                s = "unknown"; break;
            case DeviceInformationKind::AssociationEndpoint:
                s = "association_endpoint"; break;
            case DeviceInformationKind::AssociationEndpointContainer:
                s = "association_endpoint_container"; break;
            case DeviceInformationKind::AssociationEndpointService:
                s = "association_endpoint_service"; break;
            case DeviceInformationKind::Device:
                s = "device"; break;
            case DeviceInformationKind::DevicePanel:
                s = "device_panel"; break;
            case DeviceInformationKind::DeviceInterface:
                s = "device_interface"; break;
            case DeviceInformationKind::DeviceInterfaceClass:
                s = "device_interface_class"; break;
            case DeviceInformationKind::DeviceContainer:
                s = "device_container"; break;
        }
    }

    json_val(DeviceInformation const& dev) : type(DT_OBJECT) {
        object = {
            {"id", dev.Id()},
            {"name", dev.Name()},
            {"kind", dev.Kind()},
            {"is_default", dev.IsDefault()},
            {"is_enabled", dev.IsEnabled()},
        };
    }

    json_val(DeviceInformationCollection const& devices) : type(DT_LIST) {
        list.reserve(devices.Size());
        for(auto const& dev : devices) {
            list.emplace_back(json_val(dev));
        }
    }

    json_val(MediaPlaybackState const& state) : type(DT_STRING) {
        switch(state) {
            case MediaPlaybackState::None: s = "none"; break;
            case MediaPlaybackState::Opening: s = "opening"; break;
            case MediaPlaybackState::Buffering: s = "buffering"; break;
            case MediaPlaybackState::Playing: s = "playing"; break;
            case MediaPlaybackState::Paused: s = "paused"; break;
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

    template<typename T> json_val(T const x) {
        if constexpr (std::is_same_v<T, bool>) {
            type = DT_BOOL;
            b = x;
        } else if constexpr (std::is_unsigned_v<T>) {
            type = DT_UINT;
            u = x;
        } else if constexpr (std::is_integral_v<T>) {
            type = DT_INT;
            i = x;
        } else if constexpr (std::is_floating_point_v<T>) {
            type = DT_FLOAT;
            f = x;
        } else {
            static_assert(!sizeof(T), "Unknown type T cannot be converted to JSON");
        }
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

static bool
run_catching_exceptions(std::function<void(void)> f, std::string_view const &msg, int64_t line, id_type cmd_id=0) {
    bool ok = false;
    try {
        f();
        ok = true;
    } catch(winrt::hresult_error const& ex) {
        output_error(cmd_id, msg, winrt::to_string(ex.message()), line, ex.to_abi());
    } catch(const std::system_error& ex) {
        output_error(cmd_id, msg, "system_error with code: " + std::to_string(ex.code().value()) + " and meaning: " + ex.what(), line);
    } catch (std::exception const &ex) {
        output_error(cmd_id, msg, ex.what(), line);
    } catch (std::string const &ex) {
        output_error(cmd_id, msg, ex, line);
    } catch (std::wstring const &ex) {
        output_error(cmd_id, msg, winrt::to_string(ex), line);
    } catch (...) {
        output_error(cmd_id, msg, "Unknown exception type was raised", line);
    }
    return ok;
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

struct Marks {
    std::vector<Mark> entries;
    int32_t last_reported_mark_index;
    Marks() : entries(), last_reported_mark_index(-1) {}
};

static SpeechSynthesizer speech_synthesizer{nullptr};
static MediaPlayer media_player{nullptr};

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
                marks.entries.emplace_back(mark, (uint32_t)dest_pos);
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
static Revokers speak_revoker = {};

static void
register_metadata_handler_for_track(MediaPlaybackTimedMetadataTrackList const &tracks, uint32_t index, id_type cmd_id, std::shared_ptr<Marks> marks) {
    TimedMetadataTrack track = tracks.GetAt(index);
    tracks.SetPresentationMode((unsigned int)index, TimedMetadataTrackPresentationMode::ApplicationPresented);

    speak_revoker.cue_entered.emplace_back(track.CueEntered(winrt::auto_revoke, [cmd_id, marks](auto track, const auto& args) {
        if (!main_loop_is_running.load()) return;
        auto label = track.Label();
        auto cue = args.Cue().template as<SpeechCue>();
        output(cmd_id, "cue_entered", {label, cue});
        if (label != L"SpeechWord") return;
        uint32_t pos = cue.StartPositionInInput().Value();
        for (int32_t i = std::max(0, marks->last_reported_mark_index); i < (int32_t)marks->entries.size(); i++) {
            int32_t idx = -1;
            if (marks->entries[i].pos_in_text > pos) {
                idx = i-1;
                if (idx == marks->last_reported_mark_index && marks->entries[i].pos_in_text - pos < 3) idx = i;
            } else if (marks->entries[i].pos_in_text == pos) idx = i;
            if (idx > -1) {
                output(cmd_id, "mark_reached", {{"id", marks->entries[idx].id}});
                marks->last_reported_mark_index = idx;
                break;
            }
        }
    }));

    speak_revoker.cue_exited.emplace_back(track.CueExited(winrt::auto_revoke, [cmd_id](auto track, const auto& args) {
        if (main_loop_is_running.load()) output(
            cmd_id, "cue_exited", json_val(track.Label(), args.Cue().template as<SpeechCue>()));
    }));

    speak_revoker.track_failed.emplace_back(track.TrackFailed(winrt::auto_revoke, [cmd_id](auto, const auto& args) {
        auto error = args.Error();
        if (main_loop_is_running.load()) output(
            cmd_id, "track_failed", {{"code", error.ErrorCode()}, {"hr", json_val::from_hresult(error.ExtendedError())}});
    }));
};


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
    auto marks = std::make_shared<Marks>();
    std::vector<wchar_t> buf;
    std::wstring_view text;
    if (is_shm) {
        text = read_from_shm(cmd_id, parts.at(0), std::wstring(parts.at(1)), buf, *marks, is_cued);
        if (text.size() == 0) return;
    } else {
        address = join(parts);
        if (address.size() == 0) throw std::string("Address missing");
        buf.reserve(address.size() + 1);
        text = std::wstring_view(buf.data(), address.size());
        address.copy(buf.data(), address.size());
    }
    *((wchar_t*)text.data() + text.size()) = 0;  // ensure NULL termination

    output(cmd_id, "synthesizing", {{"ssml", is_ssml}, {"num_marks", marks->entries.size()}, {"text_length", text.size()}});
    SpeechSynthesisStream stream{nullptr};
    if (!run_catching_exceptions([&]() {
        speech_synthesizer.Options().IncludeSentenceBoundaryMetadata(true);
        speech_synthesizer.Options().IncludeWordBoundaryMetadata(true);
        if (is_ssml) stream = speech_synthesizer.SynthesizeSsmlToStreamAsync(text).get();
        else stream = speech_synthesizer.SynthesizeTextToStreamAsync(text).get();
    }, "Failed to synthesize speech", __LINE__, cmd_id)) return;

    speak_revoker = {};  // delete any revokers previously installed
    MediaSource source(MediaSource::CreateFromStream(stream, stream.ContentType()));

    speak_revoker.playback_state_changed = media_player.PlaybackSession().PlaybackStateChanged(
            winrt::auto_revoke, [cmd_id](auto session, auto const&) {
        if (main_loop_is_running.load()) output(
            cmd_id, "playback_state_changed", {{"state", session.PlaybackState()}});
    });
    speak_revoker.media_opened = media_player.MediaOpened(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
        if (main_loop_is_running.load()) output(
            cmd_id, "media_state_changed", {{"state", "opened"}});
    });
    speak_revoker.media_ended = media_player.MediaEnded(winrt::auto_revoke, [cmd_id](auto player, auto const&) {
        if (main_loop_is_running.load()) output(
            cmd_id, "media_state_changed", {{"state", "ended"}});
    });
    speak_revoker.media_failed = media_player.MediaFailed(winrt::auto_revoke, [cmd_id](auto player, auto const& args) {
        if (main_loop_is_running.load()) output(
            cmd_id, "media_state_changed", {{"state", "failed"}, {"error", args.ErrorMessage()}, {"hr", json_val::from_hresult(args.ExtendedErrorCode())}, {"code", args.Error()}});
    });
    auto playback_item = std::make_shared<MediaPlaybackItem>(source);

    speak_revoker.timed_metadata_tracks_changed = playback_item->TimedMetadataTracksChanged(winrt::auto_revoke,
        [cmd_id, playback_item_weak_ref = std::weak_ptr(playback_item), marks](auto, auto const &args) {
        auto change_type = args.CollectionChange();
        long index;
        switch (change_type) {
            case CollectionChange::ItemInserted: index = args.Index(); break;
            case CollectionChange::Reset: index = -1; break;
            default: index = -2; break;
        }
        auto pi{ playback_item_weak_ref.lock() };
        if (index > -2 && pi && main_loop_is_running.load()) register_metadata_handler_for_track(pi->TimedMetadataTracks(), index, cmd_id, marks);
    });

    for (uint32_t i = 0; i < playback_item->TimedMetadataTracks().Size(); i++) {
        register_metadata_handler_for_track(playback_item->TimedMetadataTracks(), i, cmd_id, marks);
    }
    media_player.Source(*playback_item);
}
// }}}

// Save {{{
static void
save_stream(SpeechSynthesisStream const &&stream, std::filesystem::path path, id_type cmd_id) {
    unsigned long long stream_size = stream.Size(), bytes_read = 0;
    DataReader reader(stream);
    unsigned int n;
    const static unsigned int chunk_size = 16 * 1024;
    std::array<uint8_t, chunk_size> buf;
    std::ofstream outfile;
    if (!run_catching_exceptions([&](){
        outfile.open(path.string(), std::ios::out | std::ios::trunc);
    }, "Failed to create file: " + path.string(), __LINE__, cmd_id)) return;

    while (bytes_read < stream_size) {
        if (!run_catching_exceptions([&]() {
            n = reader.LoadAsync(chunk_size).get();
        }, "Failed to load data from DataReader", __LINE__, cmd_id)) return;
        if (n > 0) {
            bytes_read += n;
            if (!run_catching_exceptions([&]() {
                reader.ReadBytes(winrt::array_view(buf.data(), buf.data() + n));
                outfile.write((const char*)buf.data(), n);
                if (!outfile.good()) throw "Failed to write to output file";
            }, "Failed to save bytes from DataReader to file", __LINE__, cmd_id)) return;
        }
    }
    output(cmd_id, "saved", {{"size", bytes_read}});
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
    SpeechSynthesisStream stream{nullptr};
    speech_synthesizer.Options().IncludeSentenceBoundaryMetadata(false);
    speech_synthesizer.Options().IncludeWordBoundaryMetadata(false);
    if (!run_catching_exceptions([&]() {
        if (is_ssml) stream = speech_synthesizer.SynthesizeSsmlToStreamAsync(text).get();
        else stream = speech_synthesizer.SynthesizeTextToStreamAsync(text).get();
    }, "Failed to synthesize speech", __LINE__, cmd_id)) return;
    save_stream(std::move(stream), path, cmd_id);
}
// }}}


typedef std::function<void(id_type, std::vector<std::wstring_view>, int64_t*)> handler_function;

static DeviceInformationKind
get_device_kind(const std::wstring x) {
    if (x == L"device") return DeviceInformationKind::Device;
    if (x == L"association_endpoint") return DeviceInformationKind::AssociationEndpoint;
    if (x == L"association_endpoint_container") return DeviceInformationKind::AssociationEndpointContainer;
    if (x == L"association_endpoint_service") return DeviceInformationKind::AssociationEndpointService;
    if (x == L"device_container") return DeviceInformationKind::DeviceContainer;
    if (x == L"device_interface") return DeviceInformationKind::DeviceInterface;
    if (x == L"device_interface_class") return DeviceInformationKind::DeviceInterfaceClass;
    if (x == L"device_panel") return DeviceInformationKind::DevicePanel;
    return DeviceInformationKind::Unknown;
}

static const std::unordered_map<std::string, handler_function> handlers = {

    {"exit", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t* exit_code) {
        try {
            *exit_code = parse_id(parts.at(0));
        } catch(...) { }
        *exit_code = 0;
    }},

    {"echo", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        output(cmd_id, "echo", {{"msg", join(parts)}});
    }},

    {"play", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        media_player.Play();
        output(cmd_id, "play", {{"playback_state", media_player.PlaybackSession().PlaybackState()}});
    }},

    {"pause", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        media_player.Pause();
        output(cmd_id, "pause", {{"playback_state", media_player.PlaybackSession().PlaybackState()}});
    }},

    {"state", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        auto ps = media_player.PlaybackSession();
        if (ps) output(cmd_id, "state", {{"playback_state", ps.PlaybackState()}});
        else output(cmd_id, "state", {{"playback_state", ""}});
    }},

    {"default_voice", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        output(cmd_id, "default_voice", {{"voice", SpeechSynthesizer::DefaultVoice()}});
    }},

    {"all_voices", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        output(cmd_id, "all_voices", {{"voices", SpeechSynthesizer::AllVoices()}});
    }},

    {"all_audio_devices", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        output(cmd_id, "all_audio_devices", {{"devices", DeviceInformation::FindAllAsync(MediaDevice::GetAudioRenderSelector()).get()}});
    }},

    {"speak", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        handle_speak(cmd_id, parts);
    }},

    {"audio_device", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        bool found = false;
        if (parts.size()) {
            auto device_kind = std::wstring(parts.at(0));
            parts.erase(parts.begin(), parts.begin() + 1);
            auto device_id = join(parts);
            auto di = DeviceInformation::CreateFromIdAsync(device_id, {}, get_device_kind(device_kind)).get();
            if (di) {
                media_player.AudioDevice(di);
                found = true;
            }
        }
        auto x = media_player.AudioDevice();
        if (x) output(cmd_id, "audio_device", {{"device", x}, {"found", found}});
        else output(cmd_id, "audio_device", {{"device", ""}, {"found", found}});
    }},

    {"voice", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        bool found = false;
        if (parts.size()) {
            auto voice_id = winrt::hstring(parts.at(0));
            if (voice_id == L"__default__") {
                voice_id = SpeechSynthesizer::DefaultVoice().Id();
            }
            for (auto const &candidate : SpeechSynthesizer::AllVoices()) {
                if (candidate.Id() == voice_id) {
                    speech_synthesizer.Voice(candidate);
                    found = true;
                    break;
                }
            }
        }
        auto x = speech_synthesizer.Voice();
        if (x) output(cmd_id, "voice", {{"voice", speech_synthesizer.Voice()}, {"found", found}});
        else output(cmd_id, "voice", {{"voice", ""}, {"found", found}});
    }},

    {"volume", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        if (parts.size()) {
            auto vol = parse_double(parts.at(0).data());
            if (vol < 0 || vol > 1) throw std::out_of_range("Invalid volume value must be between 0 and 1");
            speech_synthesizer.Options().AudioVolume(vol);
        }
        output(cmd_id, "volume", {{"value", speech_synthesizer.Options().AudioVolume()}});
    }},

    {"rate", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        if (parts.size()) {
            auto rate = parse_double(parts.at(0).data());
            if (rate < 0.5 || rate > 6.0) throw std::out_of_range("Invalid rate value must be between 0.5 and 6");
            speech_synthesizer.Options().SpeakingRate(rate);
        }
        output(cmd_id, "rate", {{"value", speech_synthesizer.Options().SpeakingRate()}});
    }},

    {"pitch", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        if (parts.size()) {
            auto pitch = parse_double(parts.at(0).data());
            if (pitch < 0 || pitch > 2) throw std::out_of_range("Invalid pitch value must be between 0 and 2");
            speech_synthesizer.Options().AudioPitch(pitch);
        }
        output(cmd_id, "pitch", {{"value", speech_synthesizer.Options().AudioPitch()}});
    }},

    {"save", [](id_type cmd_id, std::vector<std::wstring_view> parts, int64_t*) {
        handle_save(cmd_id, parts);
    }},
};


static int64_t
handle_stdin_message(winrt::hstring const &&msg) {
    if (msg == L"exit") {
        return 0;
    }
    id_type cmd_id;
    std::wstring_view command;
    bool ok = false;
    std::vector<std::wstring_view> parts;
    int64_t exit_code = -1;
    if (!run_catching_exceptions([&]() {
        parts = split(msg);
        command = parts.at(1); cmd_id = parse_id(parts.at(0));
        if (cmd_id == 0) {
            throw std::exception("Command id of zero is not allowed");
        }
        parts.erase(parts.begin(), parts.begin() + 2);
        ok = true;
    }, "Invalid input message: " + winrt::to_string(msg), __LINE__)) return exit_code;
    handler_function handler;
    std::string cmd(winrt::to_string(command));
    try {
        handler = handlers.at(cmd.c_str());
    } catch (std::out_of_range) {
        output_error(cmd_id, "Unknown command", cmd, __LINE__);
        return exit_code;
    }
    run_catching_exceptions([&]() {
        handler(cmd_id, parts, &exit_code);
    }, "Error handling input message", __LINE__, cmd_id);
    return exit_code;
}

#define INITIALIZE_FAILURE_MESSAGE  "Failed to initialize SpeechSynthesizer and MediaPlayer"

static PyObject*
run_main_loop(PyObject*, PyObject*) {
    if (!run_catching_exceptions([]() {
        std::cout.imbue(std::locale("C"));
        std::cin.imbue(std::locale("C"));
        std::cerr.imbue(std::locale("C"));
        std::wcin.imbue(std::locale("C"));
        std::wcout.imbue(std::locale("C"));
        std::wcerr.imbue(std::locale("C"));
    }, "Failed to set stdio locales to C", __LINE__)) {
        return PyLong_FromLongLong(1);
    }

    if (!run_catching_exceptions([]() {
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    }, "Failed to initialize COM", __LINE__)) {
        return PyLong_FromLongLong(1);
    }

    main_thread_id = GetCurrentThreadId();

    if (!run_catching_exceptions([]() {
        speech_synthesizer = SpeechSynthesizer();
        media_player = MediaPlayer();
        media_player.AudioCategory(MediaPlayerAudioCategory::Speech);
        media_player.AutoPlay(true);
    }, INITIALIZE_FAILURE_MESSAGE, __LINE__)) {
        return PyLong_FromLongLong(1);
    }

    if (_isatty(_fileno(stdin))) {
        std::cout << "Welcome to winspeech. Type exit to quit." << std::endl;
    }
    int64_t exit_code = -1;
    main_loop_is_running.store(true);

    Py_BEGIN_ALLOW_THREADS;
    std::string input_buffer;
    while (exit_code < 0) {
        try {
            if (!std::getline(std::cin, input_buffer)) {
                if (!std::cin.eof()) exit_code = 1;
                break;
            }
            rtrim(input_buffer);
            if (input_buffer.size() > 0) {
                run_catching_exceptions([&]() {
                    exit_code = handle_stdin_message(std::move(winrt::to_hstring(input_buffer)));
                }, "Error handling STDIN message", __LINE__);
                if (exit_code >= 0) break;
            }
        } catch(...) {
            exit_code = 1;
            output_error(0, "Unknown exception type reading and handling line of input", "", __LINE__);
            break;
        }
    }
    Py_END_ALLOW_THREADS;

    main_loop_is_running.store(false);
    try {
        speak_revoker = {};
        speech_synthesizer = SpeechSynthesizer{nullptr};
        media_player = MediaPlayer{nullptr};
    } catch(...) {}

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
    PyModule_AddStringMacro(m, INITIALIZE_FAILURE_MESSAGE);
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
