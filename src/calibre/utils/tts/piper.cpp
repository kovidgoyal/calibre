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
#include <queue>
#include <cstdint>
#include <algorithm>
#include <limits>
#include <chrono>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#ifdef _WIN32
#define ORT_DLL_IMPORT
#endif
// The OrtApi is initialized in exec_module() so that a mismatched
// onnxruntime library is reported as an error instead of crashing
#define ORT_API_MANUAL_INIT
#include <onnxruntime_cxx_api.h>
#undef ORT_API_MANUAL_INIT
#include <onnxruntime_session_options_config_keys.h>
// Querying which execution provider each node of the model is assigned to
#define HAS_EP_ASSIGNMENT_INFO (ORT_API_VERSION >= 24)
#if __has_include(<dml_provider_factory.h>)
#include <dml_provider_factory.h>
#define HAS_DML_HEADERS
#endif

#define CLAUSE_INTONATION_FULL_STOP 0x00000000
#define CLAUSE_INTONATION_COMMA 0x00001000
#define CLAUSE_INTONATION_QUESTION 0x00002000
#define CLAUSE_INTONATION_EXCLAMATION 0x00003000

#define CLAUSE_TYPE_CLAUSE 0x00040000
#define CLAUSE_TYPE_SENTENCE 0x00080000

#define CLAUSE_PERIOD (40 | CLAUSE_INTONATION_FULL_STOP | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_COMMA (20 | CLAUSE_INTONATION_COMMA | CLAUSE_TYPE_CLAUSE)
#define CLAUSE_QUESTION (40 | CLAUSE_INTONATION_QUESTION | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_EXCLAMATION (45 | CLAUSE_INTONATION_EXCLAMATION | CLAUSE_TYPE_SENTENCE)
#define CLAUSE_COLON (30 | CLAUSE_INTONATION_FULL_STOP | CLAUSE_TYPE_CLAUSE)
#define CLAUSE_SEMICOLON (30 | CLAUSE_INTONATION_COMMA | CLAUSE_TYPE_CLAUSE)
static const bool PRINT_TIMING_INFORMATION = false;

typedef char32_t Phoneme;
typedef int64_t PhonemeId;
typedef int64_t SpeakerId;
typedef std::map<Phoneme, std::vector<PhonemeId>> PhonemeIdMap;
const PhonemeId ID_PAD = 0; // interleaved
const PhonemeId ID_BOS = 1; // beginning of sentence
const PhonemeId ID_EOS = 2; // end of sentence

static bool initialized = false, voice_set = false;
PyObject *normalize_func = NULL;
static char espeak_data_dir[512] = {0};
static PhonemeIdMap current_phoneme_id_map;
static int current_sample_rate = 0;
static int current_num_speakers = 1;
static float current_length_scale = 1;
static float current_noise_scale = 1;
static float current_noise_w = 1;
static float current_sentence_delay = 0;
static bool current_normalize_volume = true;
// The Env must outlive all sessions created with it
static std::unique_ptr<Ort::Env> ort_env;
std::unique_ptr<Ort::Session> session;
static std::basic_string<ORTCHAR_T> current_model_path;
// The execution provider used by session, empty when session uses only the CPU
static std::string active_provider;
// Number of nodes of the model run by the provider used by session and the
// total number of nodes. Both are zero if this information is unavailable.
struct NodeCounts {
    size_t on_provider = 0, total = 0;
};
static NodeCounts active_node_counts;
static bool use_gpu = false;
// Providers that failed to load or run a model, these are not tried again
// until set_use_gpu() is called
static std::set<std::string> failed_providers;
std::queue<std::vector<PhonemeId>> phoneme_id_queue;
std::vector<float> chunk_samples;
static struct {
    PyObject *func, *args;
} normalize_data = {0};

static long long
now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// Hardware accelerated execution providers in order of preference. Only
// providers that append_execution_provider() knows how to add are listed.
static const std::vector<std::string> PRIORITY_ORDER = {
#ifdef _WIN32
    "DmlExecutionProvider", // DirectML, any GPU on Windows
#endif
#ifdef __APPLE__
    "CoreMLExecutionProvider",
#endif
    "MIGraphXExecutionProvider", // AMD GPU
    "ROCMExecutionProvider",     // AMD GPU, removed from onnxruntime >= 1.23 in favor of MIGraphX
    "TensorRTExecutionProvider",
    "CUDAExecutionProvider",     // NVIDIA GPU
    "OpenVINOExecutionProvider", // Intel GPU and CPU
};

static Ort::Env &
get_ort_env() {
    if (!ort_env) {
        ort_env = std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_WARNING, "piper");
        ort_env->DisableTelemetryEvents();
    }
    return *ort_env;
}

// Return the accelerated providers present in this build of onnxruntime, in
// priority order. Raises Ort::Exception on failure.
static std::vector<std::string>
accelerated_providers() {
    std::vector<std::string> ans;
    const std::vector<std::string> available = Ort::GetAvailableProviders();
    for (const std::string &p : PRIORITY_ORDER) {
        if (std::find(available.begin(), available.end(), p) != available.end()) ans.push_back(p);
    }
    return ans;
}

// Raises an exception if the provider cannot be added
static void
append_execution_provider(Ort::SessionOptions &opts, const std::string &name) {
    if (name == "CUDAExecutionProvider") {
        Ort::CUDAProviderOptions o;
        opts.AppendExecutionProvider_CUDA_V2(*o);
    } else if (name == "TensorRTExecutionProvider") {
        Ort::TensorRTProviderOptions o;
        opts.AppendExecutionProvider_TensorRT_V2(*o);
    } else if (name == "MIGraphXExecutionProvider") {
        // This struct has no constructor, so set the documented defaults
        OrtMIGraphXProviderOptions o{};
        o.migraphx_mem_limit = SIZE_MAX;
        opts.AppendExecutionProvider_MIGraphX(o);
    } else if (name == "ROCMExecutionProvider") {
        OrtROCMProviderOptions o;
        opts.AppendExecutionProvider_ROCM(o);
    } else if (name == "DmlExecutionProvider") {
#ifdef HAS_DML_HEADERS
        const OrtDmlApi *dml_api = nullptr;
        Ort::ThrowOnError(Ort::GetApi().GetExecutionProviderApi("DML", ORT_API_VERSION, reinterpret_cast<const void **>(&dml_api)));
        Ort::ThrowOnError(dml_api->SessionOptionsAppendExecutionProvider_DML(opts, 0));
#else
        throw std::runtime_error("calibre was built without the DirectML headers");
#endif
    } else if (name == "CoreMLExecutionProvider" || name == "OpenVINOExecutionProvider") {
        // These are the only providers in PRIORITY_ORDER that the generic API supports
        opts.AppendExecutionProvider(name, std::unordered_map<std::string, std::string>{});
    } else {
        throw std::runtime_error("Unsupported execution provider: " + name);
    }
}

// Create a session that uses the specified provider, or only the CPU if
// provider is empty. Raises an exception on failure.
static std::unique_ptr<Ort::Session>
create_session(const std::basic_string<ORTCHAR_T> &model_path, const std::string &provider) {
    // The Env must exist before providers are appended as they use its logger
    Ort::Env &env = get_ort_env();
    Ort::SessionOptions opts;
    opts.DisableCpuMemArena();
    opts.DisableMemPattern(); // required by DirectML
    opts.DisableProfiling();
    opts.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL); // required by DirectML
#if HAS_EP_ASSIGNMENT_INFO
    opts.AddConfigEntry(kOrtSessionOptionsRecordEpGraphAssignmentInfo, "1");
#endif
    if (!provider.empty()) append_execution_provider(opts, provider);
    return std::make_unique<Ort::Session>(env, model_path.c_str(), opts);
}

// Count the nodes of the model assigned to the specified provider. Raises an
// exception on failure.
static NodeCounts
count_nodes(const Ort::Session &s, const std::string &provider) {
    NodeCounts ans;
#if HAS_EP_ASSIGNMENT_INFO
    for (const auto &subgraph : s.GetEpGraphAssignmentInfo()) {
        const size_t n = subgraph.GetNodes().size();
        ans.total += n;
        if (subgraph.GetEpName() == provider) ans.on_provider += n;
    }
#endif
    return ans;
}

// Run the model on a list of phoneme ids. Raises an exception on failure.
static std::vector<Ort::Value>
run_inference(Ort::Session &s, std::vector<PhonemeId> &ids) {
    auto memoryInfo = Ort::MemoryInfo::CreateCpu(OrtAllocatorType::OrtArenaAllocator, OrtMemType::OrtMemTypeDefault);
    std::vector<Ort::Value> input_tensors;

    // Allocate
    std::vector<int64_t> phoneme_id_lengths{(int64_t)ids.size()};
    std::vector<float> scales{current_noise_scale, current_length_scale, current_noise_w};

    std::vector<int64_t> phoneme_ids_shape{1, (int64_t)ids.size()};
    input_tensors.push_back(Ort::Value::CreateTensor<int64_t>(memoryInfo, ids.data(), ids.size(), phoneme_ids_shape.data(), phoneme_ids_shape.size()));

    std::vector<int64_t> phoneme_id_lengths_shape{(int64_t)phoneme_id_lengths.size()};
    input_tensors.push_back(
        Ort::Value::CreateTensor<int64_t>(
            memoryInfo, phoneme_id_lengths.data(), phoneme_id_lengths.size(), phoneme_id_lengths_shape.data(), phoneme_id_lengths_shape.size()));

    std::vector<int64_t> scales_shape{(int64_t)scales.size()};
    input_tensors.push_back(Ort::Value::CreateTensor<float>(memoryInfo, scales.data(), scales.size(), scales_shape.data(), scales_shape.size()));

    // Add speaker id.
    // NOTE: These must be kept outside the "if" below to avoid being
    // deallocated.
    std::vector<int64_t> speaker_id{(int64_t)0};
    std::vector<int64_t> speaker_id_shape{(int64_t)speaker_id.size()};

    if (current_num_speakers > 1) {
        input_tensors.push_back(
            Ort::Value::CreateTensor<int64_t>(memoryInfo, speaker_id.data(), speaker_id.size(), speaker_id_shape.data(), speaker_id_shape.size()));
    }

    // From export_onnx.py
    std::array<const char *, 4> input_names = {"input", "input_lengths", "scales", "sid"};
    std::array<const char *, 1> output_names = {"output"};

    // Infer
    Ort::RunOptions ro;
    long long st;
    if (PRINT_TIMING_INFORMATION) st = now();
    std::vector<Ort::Value> ans = s.Run(ro, input_names.data(), input_tensors.data(), input_tensors.size(), output_names.data(), output_names.size());
    if (PRINT_TIMING_INFORMATION) {
        printf("model run time: %f\n", (now() - st) / 1e9);
        fflush(stdout);
    }
    return ans;
}

struct LoadResult {
    std::unique_ptr<Ort::Session> session;
    std::string provider, error;
    NodeCounts node_counts;
    std::vector<std::pair<std::string, std::string>> provider_failures;
};

// Try each provider in turn, verifying it with a short inference, falling
// back to only the CPU. Does not use any Python APIs so can be called without
// the GIL.
static LoadResult
load_model(const std::basic_string<ORTCHAR_T> &model_path, const std::vector<std::string> &providers) {
    LoadResult ans;
    long long st;
    if (PRINT_TIMING_INFORMATION) st = now();
    for (const std::string &p : providers) {
        try {
            std::unique_ptr<Ort::Session> s = create_session(model_path, p);
            // Providers silently leave nodes they do not support to the CPU,
            // some, such as MIGraphX, leave the entire model to the CPU.
            NodeCounts counts = count_nodes(*s, p);
            if (counts.total > 0 && counts.on_provider == 0)
                throw std::runtime_error("none of the operations in this model are supported by this execution provider");
            std::vector<PhonemeId> ids{ID_BOS, ID_PAD, ID_EOS};
            run_inference(*s, ids);
            ans.session = std::move(s);
            ans.provider = p;
            ans.node_counts = counts;
            break;
        } catch (const std::exception &e) { ans.provider_failures.emplace_back(p, e.what()); }
    }
    if (!ans.session) {
        try {
            ans.session = create_session(model_path, "");
            ans.node_counts = count_nodes(*ans.session, "CPUExecutionProvider");
        } catch (const std::exception &e) {
            ans.session.reset();
            ans.error = e.what();
        }
    }
    if (PRINT_TIMING_INFORMATION) {
        printf("model loading time: %f\n", (now() - st) / 1e9);
        fflush(stdout);
    }
    return ans;
}

static bool
warn_about_provider_failure(const std::string &provider, const std::string &error) {
    return PyErr_WarnFormat(
               PyExc_RuntimeWarning, 1, "Failed to use the %s execution provider, falling back to CPU. Error: %s", provider.c_str(), error.c_str()) == 0;
}

// Load current_model_path into session using the current settings. Must be
// called with the GIL held, returns false with a Python exception set on failure.
static bool
load_session() {
    std::vector<std::string> providers;
    if (use_gpu) {
        try {
            providers = accelerated_providers();
        } catch (const std::exception &e) {
            PyErr_Format(PyExc_OSError, "Failed to query onnxruntime for available execution providers: %s", e.what());
            return false;
        }
        providers.erase(
            std::remove_if(providers.begin(), providers.end(), [](const std::string &p) { return failed_providers.count(p) > 0; }), providers.end());
    }
    session.reset();
    active_provider.clear();
    active_node_counts = NodeCounts();
    LoadResult r;
    Py_BEGIN_ALLOW_THREADS;
    r = load_model(current_model_path, providers);
    Py_END_ALLOW_THREADS;
    for (const auto &f : r.provider_failures) failed_providers.insert(f.first);
    if (!r.session) {
        PyErr_Format(PyExc_OSError, "Failed to load the piper model: %s", r.error.c_str());
        return false;
    }
    session = std::move(r.session);
    active_provider = r.provider;
    active_node_counts = r.node_counts;
    for (const auto &f : r.provider_failures) {
        if (!warn_about_provider_failure(f.first, f.second)) return false;
    }
    return true;
}

static PyObject *
initialize(PyObject *self, PyObject *args) {
    const char *path = "";
    if (!PyArg_ParseTuple(args, "|s", &path)) return NULL;
    if (!initialized || strcmp(espeak_data_dir, path) != 0) {
        if (espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, path && path[0] ? path : NULL, 0) < 0) {
            PyErr_Format(PyExc_ValueError, "Could not initialize espeak-ng with datadir: %s", path ? path : "<default>");
            return NULL;
        }
        Py_CLEAR(normalize_data.func);
        Py_CLEAR(normalize_data.args);
        initialized = true;
        snprintf(espeak_data_dir, sizeof(espeak_data_dir), "%s", path);
        PyObject *unicodedata = PyImport_ImportModule("unicodedata");
        if (!unicodedata) return NULL;
        normalize_data.func = PyObject_GetAttrString(unicodedata, "normalize");
        Py_CLEAR(unicodedata);
        if (!normalize_data.func) return NULL;
        normalize_data.args = Py_BuildValue("(ss)", "NFD", "");
        if (!normalize_data.args) return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
set_espeak_voice_by_name(PyObject *self, PyObject *pyname) {
    if (!PyUnicode_Check(pyname)) {
        PyErr_SetString(PyExc_TypeError, "espeak voice name must be a unicode string");
        return NULL;
    }
    if (!initialized) {
        PyErr_SetString(PyExc_Exception, "must call initialize() first");
        return NULL;
    }
    if (espeak_SetVoiceByName(PyUnicode_AsUTF8(pyname)) < 0) {
        PyErr_Format(PyExc_ValueError, "failed to set espeak voice: %U", pyname);
        return NULL;
    }
    voice_set = true;
    Py_RETURN_NONE;
}

static const char *
categorize_terminator(int terminator) {
    const char *terminator_str = "";
    terminator &= 0x000FFFFF;
    switch (terminator) {
        case CLAUSE_PERIOD: terminator_str = "."; break;
        case CLAUSE_QUESTION: terminator_str = "?"; break;
        case CLAUSE_EXCLAMATION: terminator_str = "!"; break;
        case CLAUSE_COMMA: terminator_str = ","; break;
        case CLAUSE_COLON: terminator_str = ":"; break;
        case CLAUSE_SEMICOLON: terminator_str = ";"; break;
    }
    return terminator_str;
}

static PyObject *
phonemize(PyObject *self, PyObject *pytext) {
    if (!PyUnicode_Check(pytext)) {
        PyErr_SetString(PyExc_TypeError, "text must be a unicode string");
        return NULL;
    }
    if (!initialized) {
        PyErr_SetString(PyExc_Exception, "must call initialize() first");
        return NULL;
    }
    if (!voice_set) {
        PyErr_SetString(PyExc_Exception, "must set the espeak voice first");
        return NULL;
    }
    PyObject *phonemes_and_terminators = PyList_New(0);
    if (!phonemes_and_terminators) return NULL;
    const char *text = PyUnicode_AsUTF8(pytext);

    while (text != NULL) {
        int terminator = 0;
        const char *phonemes;
        Py_BEGIN_ALLOW_THREADS;
        phonemes = espeak_TextToPhonemesWithTerminator((const void **)&text, espeakCHARS_UTF8, espeakPHONEMES_IPA, &terminator);
        Py_END_ALLOW_THREADS;
        // Categorize terminator
        const char *terminator_str = categorize_terminator(terminator);
        PyObject *item = Py_BuildValue("(ssO)", phonemes, terminator_str, (terminator & CLAUSE_TYPE_SENTENCE) != 0 ? Py_True : Py_False);
        if (item == NULL) {
            Py_CLEAR(phonemes_and_terminators);
            return NULL;
        }
        int ret = PyList_Append(phonemes_and_terminators, item);
        Py_CLEAR(item);
        if (ret != 0) {
            Py_CLEAR(phonemes_and_terminators);
            return NULL;
        }
    }
    return phonemes_and_terminators;
}

static PyObject *
set_voice(PyObject *self, PyObject *args) {
    PyObject *cfg;
    PyObject *pymp;
    if (!PyArg_ParseTuple(args, "OU", &cfg, &pymp)) return NULL;

    PyObject *evn = PyObject_GetAttrString(cfg, "espeak_voice_name");
    if (!evn) return NULL;
    PyObject *ret = set_espeak_voice_by_name(NULL, evn);
    Py_CLEAR(evn);
    if (ret == NULL) return NULL;
    Py_DECREF(ret);

#define G(name, dest, conv)                                \
    {                                                      \
        PyObject *sr = PyObject_GetAttrString(cfg, #name); \
        if (!sr) return NULL;                              \
        dest = conv(sr);                                   \
        Py_CLEAR(sr);                                      \
        if (PyErr_Occurred()) return NULL;                 \
    }
    G(sample_rate, current_sample_rate, PyLong_AsLong);
    G(num_speakers, current_num_speakers, PyLong_AsLong);
    G(length_scale, current_length_scale, (float)PyFloat_AsDouble);
    G(noise_scale, current_noise_scale, (float)PyFloat_AsDouble);
    G(noise_w, current_noise_w, (float)PyFloat_AsDouble);
    G(sentence_delay, current_sentence_delay, (float)PyFloat_AsDouble);
    G(normalize_volume, current_normalize_volume, PyObject_IsTrue);
#undef G

    PyObject *map = PyObject_GetAttrString(cfg, "phoneme_id_map");
    if (!map) return NULL;
    current_phoneme_id_map.clear();
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next(map, &pos, &key, &value)) {
        unsigned long cp = PyLong_AsUnsignedLong(key);
        if (PyErr_Occurred()) break;
        std::vector<PhonemeId> ids;
        for (Py_ssize_t i = 0; i < PyList_GET_SIZE(value); i++) {
            unsigned long id = PyLong_AsUnsignedLong(PyList_GET_ITEM(value, i));
            if (PyErr_Occurred()) break;
            ids.push_back(id);
        }
        current_phoneme_id_map[cp] = ids;
    }
    Py_CLEAR(map);
    if (PyErr_Occurred()) return NULL;

#ifdef _WIN32
    wchar_t *model_path = PyUnicode_AsWideCharString(pymp, NULL);
    if (!model_path) return NULL;
    current_model_path = model_path;
    PyMem_Free(model_path);
#else
    const char *model_path = PyUnicode_AsUTF8(pymp);
    if (!model_path) return NULL;
    current_model_path = model_path;
#endif
    if (!load_session()) return NULL;
    Py_RETURN_NONE;
}

static PyObject *
normalize(const char *text) {
    PyObject *t = PyUnicode_FromString(text);
    if (!t || PyTuple_SetItem(normalize_data.args, 1, t) != 0) return NULL;
    return PyObject_CallObject(normalize_data.func, normalize_data.args);
}

static PyObject *
start(PyObject *self, PyObject *args) {
    const char *text;
    if (!PyArg_ParseTuple(args, "s", &text)) return NULL;
    if (!voice_set || session.get() == NULL) {
        PyErr_SetString(PyExc_Exception, "must call set_voice() first");
        return NULL;
    }
    // Clear state
    while (!phoneme_id_queue.empty()) phoneme_id_queue.pop();
    chunk_samples.clear();

    // Convert to phonemes
    std::vector<std::string> sentence_phonemes{""};
    Py_BEGIN_ALLOW_THREADS;
    std::size_t current_idx = 0;
    const void *text_ptr = text;
    while (text_ptr != nullptr) {
        int terminator = 0;
        const char *phonemes = espeak_TextToPhonemesWithTerminator(&text_ptr, espeakCHARS_UTF8, espeakPHONEMES_IPA, &terminator);
        if (phonemes) sentence_phonemes[current_idx] += phonemes;
        const char *terminator_str = categorize_terminator(terminator);
        sentence_phonemes[current_idx] += terminator_str;
        if ((terminator & CLAUSE_TYPE_SENTENCE) == CLAUSE_TYPE_SENTENCE) {
            sentence_phonemes.push_back("");
            current_idx = sentence_phonemes.size() - 1;
        }
    }
    Py_END_ALLOW_THREADS;

    // phonemes to ids
    std::vector<PhonemeId> sentence_ids;
    for (auto &phonemes_str : sentence_phonemes) {
        if (phonemes_str.empty()) continue;
        sentence_ids.push_back(ID_BOS);
        sentence_ids.push_back(ID_PAD);

        PyObject *normalized_text = normalize(phonemes_str.c_str());
        if (!normalized_text) return NULL;
        int kind = PyUnicode_KIND(normalized_text);
        void *data = PyUnicode_DATA(normalized_text);

        // Filter out (lang) switch (flags).
        // These surround words from languages other than the current voice.
        bool in_lang_flag = false;
        for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(normalized_text); i++) {
            char32_t ch = PyUnicode_READ(kind, data, i);
            if (in_lang_flag) {
                if (ch == U')') {
                    // End of (lang) switch
                    in_lang_flag = false;
                }
            } else if (ch == U'(') {
                // Start of (lang) switch
                in_lang_flag = true;
            } else {
                // Look up ids
                auto ids_for_phoneme = current_phoneme_id_map.find(ch);
                if (ids_for_phoneme != current_phoneme_id_map.end()) {
                    for (auto id : ids_for_phoneme->second) {
                        sentence_ids.push_back(id);
                        sentence_ids.push_back(ID_PAD);
                    }
                }
            }
        }
        Py_CLEAR(normalized_text);
        sentence_ids.push_back(ID_EOS);
        phoneme_id_queue.emplace(std::move(sentence_ids));
        sentence_ids.clear();
    }
    Py_RETURN_NONE;
}

static PyObject *
next(PyObject *self, PyObject *args) {
    int as_16bit_samples = 1;
    if (!PyArg_ParseTuple(args, "|p", &as_16bit_samples)) return NULL;
    if (phoneme_id_queue.empty()) return Py_BuildValue("yiiO", "", 0, current_sample_rate, Py_True);
    if (session.get() == NULL) {
        PyErr_SetString(PyExc_Exception, "must call set_voice() first");
        return NULL;
    }
    std::vector<Ort::Value> output_tensors;
    std::unique_ptr<Ort::Session> cpu_session;
    NodeCounts cpu_node_counts;
    std::string error, provider_error;
    const std::string provider = active_provider;

    Py_BEGIN_ALLOW_THREADS;
    // Process next list of phoneme ids
    auto next_ids = std::move(phoneme_id_queue.front());
    phoneme_id_queue.pop();
    try {
        output_tensors = run_inference(*session, next_ids);
    } catch (const std::exception &e) {
        if (provider.empty()) error = e.what();
        else {
            // The accelerated provider failed at runtime, fall back to the CPU
            provider_error = e.what();
            try {
                cpu_session = create_session(current_model_path, "");
                cpu_node_counts = count_nodes(*cpu_session, "CPUExecutionProvider");
                output_tensors = run_inference(*cpu_session, next_ids);
            } catch (const std::exception &cpu_err) { error = cpu_err.what(); }
        }
    }
    Py_END_ALLOW_THREADS;

    if (!provider_error.empty()) {
        failed_providers.insert(provider);
        active_provider.clear();
        active_node_counts = cpu_node_counts;
        session = std::move(cpu_session);
        if (!warn_about_provider_failure(provider, provider_error)) return NULL;
    }
    if (!error.empty()) {
        PyErr_Format(PyExc_OSError, "Failed to run the piper model: %s", error.c_str());
        return NULL;
    }
    if ((output_tensors.size() != 1) || (!output_tensors.front().IsTensor())) {
        PyErr_SetString(PyExc_ValueError, "failed to infer audio data from list of phoneme ids");
        return NULL;
    }

    int num_samples;
    const float *audio_tensor_data;
    PyObject *ans = NULL, *data = NULL;
    int num_of_silence_samples = 0;
    auto audio_shape = output_tensors.front().GetTensorTypeAndShapeInfo().GetShape();
    num_samples = (int)audio_shape[audio_shape.size() - 1];
    audio_tensor_data = output_tensors.front().GetTensorData<float>();
    float maxval = 1.f;

    Py_BEGIN_ALLOW_THREADS;
    if (current_sentence_delay > 0) num_of_silence_samples = (int)(current_sample_rate * current_sentence_delay);
    if (num_samples) {
        maxval = std::abs(audio_tensor_data[0]);
        float q;
        for (int i = 1; i < num_samples; i++)
            if ((q = std::abs(audio_tensor_data[i])) > maxval) maxval = q;
        if (maxval <= 1e-8) maxval = 1.f;
    }
    Py_END_ALLOW_THREADS;
    if (as_16bit_samples) {
        data = PyBytes_FromStringAndSize(NULL, sizeof(int16_t) * (num_samples + num_of_silence_samples));
        if (data) {
            Py_BEGIN_ALLOW_THREADS;
            int16_t *x = (int16_t *)PyBytes_AS_STRING(data);
            for (int i = 0; i < num_samples; i++) { x[i] = (int16_t)((audio_tensor_data[i] / maxval) * std::numeric_limits<int16_t>::max()); }
            memset(x + num_samples, 0, num_of_silence_samples * sizeof(int16_t));
            Py_END_ALLOW_THREADS;
        }
    } else {
        data = PyBytes_FromStringAndSize(NULL, sizeof(float) * (num_samples + num_of_silence_samples));
        if (data) {
            Py_BEGIN_ALLOW_THREADS;
            float *x = (float *)PyBytes_AS_STRING(data);
            for (int i = 0; i < num_samples; i++) x[i] = audio_tensor_data[i] / maxval;
            memset(x + num_samples, 0, num_of_silence_samples * sizeof(float));
            Py_END_ALLOW_THREADS;
        }
    }
    if (data) {
        ans = Py_BuildValue("OiiO", data, num_samples, current_sample_rate, phoneme_id_queue.empty() ? Py_True : Py_False);
        Py_DECREF(data);
    }
    return ans;
}

static PyObject *
set_use_gpu(PyObject *self, PyObject *val) {
    int q = PyObject_IsTrue(val);
    if (q < 0) return NULL;
    if (use_gpu == (q != 0)) Py_RETURN_NONE;
    use_gpu = q != 0;
    // Give previously failed providers another chance
    failed_providers.clear();
    if (session.get() != NULL && !load_session()) return NULL;
    Py_RETURN_NONE;
}

static PyObject *
gpu_providers(PyObject *self, PyObject *args) {
    std::vector<std::string> providers;
    try {
        providers = accelerated_providers();
    } catch (const std::exception &e) {
        PyErr_Format(PyExc_OSError, "Failed to query onnxruntime for available execution providers: %s", e.what());
        return NULL;
    }
    PyObject *ans = PyTuple_New(providers.size());
    if (!ans) return NULL;
    for (size_t i = 0; i < providers.size(); i++) {
        PyObject *x = PyUnicode_FromString(providers[i].c_str());
        if (!x) {
            Py_DECREF(ans);
            return NULL;
        }
        PyTuple_SET_ITEM(ans, i, x);
    }
    return ans;
}

static PyObject *
current_backend(PyObject *self, PyObject *args) {
    if (session.get() == NULL) Py_RETURN_NONE;
#ifdef _WIN32
    PyObject *mp = PyUnicode_FromWideChar(current_model_path.c_str(), current_model_path.size());
#else
    PyObject *mp = PyUnicode_DecodeFSDefaultAndSize(current_model_path.c_str(), current_model_path.size());
#endif
    if (!mp) return NULL;
    return Py_BuildValue(
        "Nsnn",
        mp,
        active_provider.empty() ? "CPUExecutionProvider" : active_provider.c_str(),
        (Py_ssize_t)active_node_counts.on_provider,
        (Py_ssize_t)active_node_counts.total);
}

// Boilerplate {{{
static char doc[] = "Text to speech using the Piper TTS models";
static PyMethodDef methods[] = {
    {"initialize",
     (PyCFunction)initialize,
     METH_VARARGS,
     "initialize(espeak_data_dir) -> Initialize this module. Must be called once before using any other functions from this module. If espeak_data_dir is not "
     "specified or is the empty string the default data location is used."},
    {"set_voice", (PyCFunction)set_voice, METH_VARARGS, "set_voice(voice_config, model_path) -> Load the model in preparation for synthesis."},
    {"start", (PyCFunction)start, METH_VARARGS, "start(text) -> Start synthesizing the specified text, call next() repeatedly to get the audiodata."},
    {"next",
     (PyCFunction)next,
     METH_VARARGS,
     "next(as_16bit_samples=True) -> Return the next chunk of audio data (audio_data, num_samples, sample_rate, is_last). Here audio_data is a bytes object "
     "consisting of either native 16bit integer audio samples or native floats in the range [-1, 1]."},

    {"set_espeak_voice_by_name", (PyCFunction)set_espeak_voice_by_name, METH_O, "set_espeak_voice_by_name(name) -> Set the voice to be used to phonemize text"},
    {"phonemize", (PyCFunction)phonemize, METH_O, "phonemize(text) -> Convert the specified text into espeak-ng phonemes"},
    {"set_use_gpu",
     (PyCFunction)set_use_gpu,
     METH_O,
     "set_use_gpu(use_gpu) -> Set whether hardware accelerated execution providers (GPU, etc.) are used to run the model, falling back to the CPU if they "
     "fail. If a voice is already loaded it is reloaded. Defaults to False. Must not be called concurrently with other functions from this module."},
    {"gpu_providers",
     (PyCFunction)gpu_providers,
     METH_NOARGS,
     "gpu_providers() -> Return the hardware accelerated execution providers available in this build of onnxruntime, in the order in which they are tried"},
    {"current_backend",
     (PyCFunction)current_backend,
     METH_NOARGS,
     "current_backend() -> Return (model_path, execution_provider_name, num_nodes_on_provider, num_nodes) for the currently loaded model or None if no "
     "model is loaded. The provider can change from a GPU provider to CPUExecutionProvider if the GPU fails while synthesizing. Nodes the provider does "
     "not support run on the CPU. The node counts are zero if onnxruntime is too old to report them."},
    {NULL} /* Sentinel */
};

static int
exec_module(PyObject *mod) {
    const OrtApiBase *base = OrtGetApiBase();
    const OrtApi *api = base ? base->GetApi(ORT_API_VERSION) : NULL;
    if (!api) {
        PyErr_Format(
            PyExc_ImportError,
            "The loaded onnxruntime library (version: %s) does not support the API version %d this module was built with",
            base ? base->GetVersionString() : "unknown",
            ORT_API_VERSION);
        return -1;
    }
    Ort::InitApi(api);
    return 0;
}

static PyModuleDef_Slot slots[] = {{Py_mod_exec, (void *)exec_module}, {0, NULL}};

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

static void
cleanup_module(void *) {
    if (initialized) {
        initialized = false;
        voice_set = false;
        espeak_Terminate();
    }
    current_phoneme_id_map.clear();
    session.reset();
    active_provider.clear();
    ort_env.reset();
    Py_CLEAR(normalize_data.func);
    Py_CLEAR(normalize_data.args);
}

CALIBRE_MODINIT_FUNC
PyInit_piper(void) {
    module_def.m_name = "piper";
    module_def.m_slots = slots;
    module_def.m_doc = doc;
    module_def.m_methods = methods;
    module_def.m_free = cleanup_module;
    return PyModuleDef_Init(&module_def);
}
// }}}
