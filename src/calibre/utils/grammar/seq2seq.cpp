/*
 * seq2seq.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

// Run encoder-decoder (sequence to sequence) models such as T5 that have been
// exported to ONNX by Hugging Face optimum. Supports the three layouts optimum
// produces:
//   separate: encoder + decoder + decoder_with_past
//   merged:   encoder + decoder_model_merged (has a use_cache_branch input)
//   nocache:  encoder + decoder, the whole sequence is decoded at every step

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "../onnx_common.h"

using calibre_ort::NodeCounts;
using calibre_ort::OrtPath;

typedef std::vector<int64_t> TokenIds;
static const char PAST_PREFIX[] = "past_key_values.";
static const char PRESENT_PREFIX[] = "present.";
static const float NEG_INF = -std::numeric_limits<float>::infinity();

enum class Layout { Separate, Merged, NoCache };

static bool
starts_with(const std::string &s, const char *prefix) {
    return s.rfind(prefix, 0) == 0;
}

struct InputInfo {
    std::string name;
    ONNXTensorElementDataType type;
    std::vector<int64_t> shape;
};

struct SessionData {
    std::unique_ptr<Ort::Session> session;
    std::vector<InputInfo> inputs;
    std::vector<std::string> output_names;
    NodeCounts node_counts;

    bool
    has_input(const std::string &name) const {
        for (const auto &i : inputs)
            if (i.name == name) return true;
        return false;
    }
};

// Values available to be fed to a session, keyed by input name
typedef std::map<std::string, const OrtValue *> Feeds;

class Model {
  public:
    SessionData encoder, decoder, decoder_with_past;
    Layout layout = Layout::NoCache;
    std::string provider;
    int64_t decoder_start_token_id = 0, eos_token_id = 1, pad_token_id = 0;
    // Generation can be aborted by setting the terminate flag on its run
    // options, scoring is fast enough to never need aborting
    Ort::RunOptions generate_run_options, score_run_options;
    std::atomic<bool> aborted{false};

    Model(
        Ort::Env &env,
        const OrtPath &encoder_path,
        const OrtPath &decoder_path,
        const OrtPath &decoder_with_past_path,
        const std::string &provider,
        int num_threads)
        : provider(provider) {
        load(env, encoder, encoder_path, num_threads);
        load(env, decoder, decoder_path, num_threads);
        if (!decoder_with_past_path.empty()) {
            load(env, decoder_with_past, decoder_with_past_path, num_threads);
            layout = Layout::Separate;
        } else if (decoder.has_input("use_cache_branch")) layout = Layout::Merged;
        for (const char *name : {"input_ids", "attention_mask"})
            if (!encoder.has_input(name)) throw std::runtime_error(std::string("The encoder model has no input named: ") + name);
        if (encoder.output_names.empty()) throw std::runtime_error("The encoder model has no outputs");
        if (std::find(decoder.output_names.begin(), decoder.output_names.end(), "logits") == decoder.output_names.end())
            throw std::runtime_error("The decoder model has no output named: logits");
    }

    NodeCounts
    node_counts() const {
        NodeCounts ans;
        for (const SessionData *s : {&encoder, &decoder, &decoder_with_past}) {
            ans.on_provider += s->node_counts.on_provider;
            ans.total += s->node_counts.total;
        }
        return ans;
    }

    // Run the encoder on a batch of token id sequences, which are padded to
    // the same length. Returns the hidden states and the attention mask.
    std::pair<Ort::Value, Ort::Value>
    encode(const std::vector<TokenIds> &batch, Ort::RunOptions &ro) {
        size_t max_len = 1;
        for (const auto &x : batch) max_len = std::max(max_len, x.size());
        const std::vector<int64_t> shape{(int64_t)batch.size(), (int64_t)max_len};
        Ort::Value ids = int64_tensor(shape), mask = int64_tensor(shape);
        int64_t *idp = ids.GetTensorMutableData<int64_t>(), *mp = mask.GetTensorMutableData<int64_t>();
        for (size_t b = 0; b < batch.size(); b++) {
            for (size_t i = 0; i < max_len; i++) {
                const bool present = i < batch[b].size();
                idp[b * max_len + i] = present ? batch[b][i] : pad_token_id;
                mp[b * max_len + i] = present ? 1 : 0;
            }
        }
        Feeds feeds{{"input_ids", ids}, {"attention_mask", mask}};
        std::vector<std::string> outputs{encoder.output_names[0]};
        std::vector<Ort::Value> r = run(encoder, feeds, outputs, ro);
        return {std::move(r[0]), std::move(mask)};
    }

    // Teacher forced decoding of each target given its input. Returns, for
    // every position of every target, the log probability of the target token
    // and the token the model considers most likely.
    std::vector<std::pair<std::vector<float>, TokenIds>>
    score(const std::vector<std::pair<TokenIds, TokenIds>> &pairs) {
        std::vector<TokenIds> inputs, decoder_inputs;
        size_t max_len = 1;
        for (const auto &p : pairs) {
            inputs.push_back(p.first);
            TokenIds d{decoder_start_token_id};
            if (!p.second.empty()) d.insert(d.end(), p.second.begin(), p.second.end() - 1);
            max_len = std::max(max_len, d.size());
            decoder_inputs.push_back(std::move(d));
        }
        for (auto &d : decoder_inputs) d.resize(max_len, pad_token_id);
        auto [hidden, mask] = encode(inputs, score_run_options);
        std::map<std::string, Ort::Value> past;
        Ort::Value logits = run_full_decoder(decoder_inputs, hidden, mask, past, false, score_run_options);
        std::vector<std::pair<std::vector<float>, TokenIds>> ans;
        const size_t vocab_size = (size_t)logits.GetTensorTypeAndShapeInfo().GetShape().back();
        std::vector<float> row(vocab_size);
        for (size_t b = 0; b < pairs.size(); b++) {
            const TokenIds &target = pairs[b].second;
            std::vector<float> logprobs;
            TokenIds best;
            for (size_t t = 0; t < target.size(); t++) {
                logits_row(logits, b, t, row);
                log_softmax(row);
                const int64_t tok = target[t];
                logprobs.push_back(tok >= 0 && (size_t)tok < vocab_size ? row[tok] : NEG_INF);
                best.push_back(std::max_element(row.begin(), row.end()) - row.begin());
            }
            ans.emplace_back(std::move(logprobs), std::move(best));
        }
        return ans;
    }

    // Greedy (num_beams == 1) or beam search decoding. Returns up to
    // num_return_sequences (token ids, score) pairs sorted by descending score.
    // The token ids start with forced_prefix and do not include the start or
    // end tokens. Returns an empty vector if aborted.
    std::vector<std::pair<TokenIds, float>>
    generate(const TokenIds &input_ids, size_t max_length, size_t num_beams, size_t num_return_sequences, float length_penalty, const TokenIds &forced_prefix) {
        aborted = false;
        generate_run_options.UnsetTerminate();
        num_beams = std::max<size_t>(1, num_beams);
        num_return_sequences = std::max<size_t>(1, std::min(num_return_sequences, num_beams));
        auto [hidden1, mask1] = encode({input_ids}, generate_run_options);
        Ort::Value hidden = tile(hidden1, num_beams), mask = tile(mask1, num_beams);

        TokenIds start{decoder_start_token_id};
        start.insert(start.end(), forced_prefix.begin(), forced_prefix.end());
        std::vector<TokenIds> beams(num_beams, forced_prefix);
        std::vector<float> beam_scores(num_beams, NEG_INF);
        beam_scores[0] = 0;
        std::vector<std::pair<TokenIds, float>> finished;
        auto normalized = [length_penalty](float score, size_t len) { return score / std::pow((float)std::max<size_t>(1, len), length_penalty); };

        std::map<std::string, Ort::Value> past;
        Ort::Value logits = run_full_decoder(std::vector<TokenIds>(num_beams, start), hidden, mask, past, true, generate_run_options);
        const size_t vocab_size = (size_t)logits.GetTensorTypeAndShapeInfo().GetShape().back();
        std::vector<float> row(vocab_size);
        std::vector<size_t> order(vocab_size);
        const size_t k = 2 * num_beams;

        while (beams[0].size() < max_length) {
            if (aborted) return {};
            const size_t last_pos = (size_t)logits.GetTensorTypeAndShapeInfo().GetShape()[1] - 1;
            struct Candidate {
                float score;
                size_t beam;
                int64_t token;
            };
            std::vector<Candidate> candidates;
            for (size_t b = 0; b < num_beams; b++) {
                if (beam_scores[b] == NEG_INF) continue;
                logits_row(logits, b, last_pos, row);
                log_softmax(row);
                std::iota(order.begin(), order.end(), 0);
                const size_t n = std::min(k, vocab_size);
                std::partial_sort(order.begin(), order.begin() + n, order.end(), [&row](size_t a, size_t c) { return row[a] > row[c]; });
                for (size_t i = 0; i < n; i++) candidates.push_back({beam_scores[b] + row[order[i]], b, (int64_t)order[i]});
            }
            std::sort(candidates.begin(), candidates.end(), [](const Candidate &a, const Candidate &b) { return a.score > b.score; });
            std::vector<TokenIds> next_beams;
            std::vector<float> next_scores;
            std::vector<size_t> sources;
            for (size_t rank = 0; rank < candidates.size() && next_beams.size() < num_beams; rank++) {
                const Candidate &c = candidates[rank];
                if (c.token == eos_token_id) {
                    if (rank < num_beams) finished.emplace_back(beams[c.beam], normalized(c.score, beams[c.beam].size() + 1));
                    continue;
                }
                TokenIds t = beams[c.beam];
                t.push_back(c.token);
                next_beams.push_back(std::move(t));
                next_scores.push_back(c.score);
                sources.push_back(c.beam);
            }
            if (next_beams.empty()) break;
            if (finished.size() >= num_beams) {
                float worst = finished[0].second;
                for (const auto &f : finished) worst = std::min(worst, f.second);
                if (worst >= normalized(next_scores[0], next_beams[0].size())) {
                    beams.clear();
                    break;
                }
            }
            while (next_beams.size() < num_beams) { // pad with dead beams
                next_beams.push_back(next_beams[0]);
                next_scores.push_back(NEG_INF);
                sources.push_back(sources[0]);
            }
            beams = std::move(next_beams);
            beam_scores = std::move(next_scores);
            if (beams[0].size() >= max_length) break;
            reorder_past(past, sources);
            TokenIds last;
            for (const auto &b : beams) last.push_back(b.back());
            logits = run_incremental_decoder(last, beams, hidden, mask, past, generate_run_options);
        }
        if (aborted) return {};
        for (size_t b = 0; b < beams.size() && finished.size() < num_return_sequences; b++) {
            if (beam_scores[b] != NEG_INF) finished.emplace_back(beams[b], normalized(beam_scores[b], beams[b].size()));
        }
        std::stable_sort(finished.begin(), finished.end(), [](const auto &a, const auto &b) { return a.second > b.second; });
        if (finished.size() > num_return_sequences) finished.resize(num_return_sequences);
        return finished;
    }

    void
    abort() {
        aborted = true;
        generate_run_options.SetTerminate();
    }

  private:
    void
    load(Ort::Env &env, SessionData &sd, const OrtPath &path, int num_threads) {
        Ort::SessionOptions opts;
        if (num_threads > 0) opts.SetIntraOpNumThreads(num_threads);
        calibre_ort::configure_session_options(opts, provider, calibre_ort::COREML_DYNAMIC_SHAPE_OPTIONS);
        sd.session = std::make_unique<Ort::Session>(env, path.c_str(), opts);
        Ort::AllocatorWithDefaultOptions allocator;
        for (size_t i = 0; i < sd.session->GetInputCount(); i++) {
            Ort::TypeInfo ti = sd.session->GetInputTypeInfo(i);
            auto tsi = ti.GetTensorTypeAndShapeInfo();
            sd.inputs.push_back({sd.session->GetInputNameAllocated(i, allocator).get(), tsi.GetElementType(), tsi.GetShape()});
        }
        for (size_t i = 0; i < sd.session->GetOutputCount(); i++) sd.output_names.push_back(sd.session->GetOutputNameAllocated(i, allocator).get());
        sd.node_counts = calibre_ort::count_nodes(*sd.session, provider.empty() ? "CPUExecutionProvider" : provider);
    }

    Ort::Value
    int64_tensor(const std::vector<int64_t> &shape) {
        Ort::AllocatorWithDefaultOptions allocator;
        return Ort::Value::CreateTensor<int64_t>(allocator, shape.data(), shape.size());
    }

    Ort::Value
    token_tensor(const std::vector<TokenIds> &batch) {
        const size_t len = batch.empty() ? 0 : batch[0].size();
        Ort::Value ans = int64_tensor({(int64_t)batch.size(), (int64_t)len});
        int64_t *p = ans.GetTensorMutableData<int64_t>();
        for (size_t b = 0; b < batch.size(); b++) std::memcpy(p + b * len, batch[b].data(), len * sizeof(int64_t));
        return ans;
    }

    std::vector<Ort::Value>
    run(SessionData &sd, const Feeds &feeds, const std::vector<std::string> &outputs, Ort::RunOptions &ro) {
        std::vector<const char *> in_names, out_names;
        std::vector<const OrtValue *> in_values;
        for (const auto &i : sd.inputs) {
            auto it = feeds.find(i.name);
            if (it == feeds.end()) throw std::runtime_error("Unsupported model input: " + i.name);
            in_names.push_back(i.name.c_str());
            in_values.push_back(it->second);
        }
        for (const auto &o : outputs) out_names.push_back(o.c_str());
        std::vector<OrtValue *> out_values(outputs.size(), nullptr);
        Ort::ThrowOnError(
            Ort::GetApi().Run(*sd.session, ro, in_names.data(), in_values.data(), in_values.size(), out_names.data(), out_names.size(), out_values.data()));
        std::vector<Ort::Value> ans;
        for (OrtValue *v : out_values) ans.emplace_back(v);
        return ans;
    }

    // Store the present.* outputs as past_key_values.* entries. If
    // only_decoder is true, the cross attention (encoder) entries are not
    // updated, as some models output only placeholders for them when using
    // the cache.
    static void
    store_past(std::vector<Ort::Value> &values, const std::vector<std::string> &names, std::map<std::string, Ort::Value> &past, bool only_decoder) {
        for (size_t i = 0; i < names.size(); i++) {
            if (!starts_with(names[i], PRESENT_PREFIX)) continue;
            if (only_decoder && names[i].find(".decoder.") == std::string::npos) continue;
            std::string key = PAST_PREFIX + names[i].substr(sizeof(PRESENT_PREFIX) - 1);
            past.erase(key);
            past.emplace(key, std::move(values[i]));
        }
    }

    // Decode full sequences (which must all be the same length) without
    // using a cache. Fills past with the key/value cache if want_past is true
    // and the model supports caching. Returns the logits.
    Ort::Value
    run_full_decoder(
        const std::vector<TokenIds> &tokens,
        Ort::Value &hidden,
        Ort::Value &mask,
        std::map<std::string, Ort::Value> &past,
        bool want_past,
        Ort::RunOptions &ro) {
        Ort::Value ids = token_tensor(tokens);
        Feeds feeds{{"input_ids", ids}, {"encoder_hidden_states", hidden}, {"encoder_attention_mask", mask}};
        std::vector<Ort::Value> keep_alive;
        if (layout == Layout::Merged) {
            Ort::AllocatorWithDefaultOptions allocator;
            const std::vector<int64_t> one{1};
            keep_alive.push_back(Ort::Value::CreateTensor<bool>(allocator, one.data(), one.size()));
            *keep_alive.back().GetTensorMutableData<bool>() = false;
            feeds["use_cache_branch"] = keep_alive.back();
            for (const auto &i : decoder.inputs) {
                if (!starts_with(i.name, PAST_PREFIX)) continue;
                // An empty cache: [batch, num_heads, 0, head_dim]
                std::vector<int64_t> shape = i.shape;
                if (shape.size() != 4) throw std::runtime_error("Unsupported shape for model input: " + i.name);
                shape[0] = (int64_t)tokens.size();
                shape[2] = 0;
                keep_alive.push_back(Ort::Value::CreateTensor(allocator, shape.data(), shape.size(), i.type));
                feeds[i.name] = keep_alive.back();
            }
        }
        const bool fetch_past = want_past && layout != Layout::NoCache;
        std::vector<std::string> outputs = fetch_past ? decoder.output_names : std::vector<std::string>{"logits"};
        std::vector<Ort::Value> r = run(decoder, feeds, outputs, ro);
        const size_t logits_idx = std::find(outputs.begin(), outputs.end(), "logits") - outputs.begin();
        Ort::Value logits = std::move(r[logits_idx]);
        if (fetch_past) store_past(r, outputs, past, false);
        return logits;
    }

    Ort::Value
    run_incremental_decoder(
        const TokenIds &last,
        const std::vector<TokenIds> &beams,
        Ort::Value &hidden,
        Ort::Value &mask,
        std::map<std::string, Ort::Value> &past,
        Ort::RunOptions &ro) {
        if (layout == Layout::NoCache) {
            std::vector<TokenIds> full;
            for (const auto &b : beams) {
                TokenIds t{decoder_start_token_id};
                t.insert(t.end(), b.begin(), b.end());
                full.push_back(std::move(t));
            }
            return run_full_decoder(full, hidden, mask, past, false, ro);
        }
        std::vector<TokenIds> step;
        for (int64_t t : last) step.push_back({t});
        Ort::Value ids = token_tensor(step);
        Feeds feeds{{"input_ids", ids}, {"encoder_hidden_states", hidden}, {"encoder_attention_mask", mask}};
        for (const auto &p : past) feeds[p.first] = p.second;
        std::vector<Ort::Value> keep_alive;
        if (layout == Layout::Merged) {
            Ort::AllocatorWithDefaultOptions allocator;
            const std::vector<int64_t> one{1};
            keep_alive.push_back(Ort::Value::CreateTensor<bool>(allocator, one.data(), one.size()));
            *keep_alive.back().GetTensorMutableData<bool>() = true;
            feeds["use_cache_branch"] = keep_alive.back();
        }
        SessionData &sd = layout == Layout::Separate ? decoder_with_past : decoder;
        std::vector<Ort::Value> r = run(sd, feeds, sd.output_names, ro);
        const size_t logits_idx = std::find(sd.output_names.begin(), sd.output_names.end(), "logits") - sd.output_names.begin();
        if (logits_idx >= r.size()) throw std::runtime_error("The decoder model has no output named: logits");
        Ort::Value logits = std::move(r[logits_idx]);
        store_past(r, sd.output_names, past, true);
        return logits;
    }

    // Reorder the batch dimension of the self attention cache so that row i
    // comes from row sources[i]. The cross attention cache is the same for
    // every beam so it is left alone.
    static void
    reorder_past(std::map<std::string, Ort::Value> &past, const std::vector<size_t> &sources) {
        bool identity = true;
        for (size_t i = 0; i < sources.size(); i++) identity = identity && sources[i] == i;
        if (identity) return;
        for (auto &p : past) {
            if (p.first.find(".decoder.") == std::string::npos) continue;
            p.second = gather_rows(p.second, sources);
        }
    }

    static size_t
    element_size(ONNXTensorElementDataType t) {
        switch (t) {
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT: return 4;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT16: return 2;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_BFLOAT16: return 2;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE: return 8;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64: return 8;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32: return 4;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL: return 1;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8: return 1;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8: return 1;
            default: throw std::runtime_error("Unsupported tensor element type: " + std::to_string((int)t));
        }
    }

    // Create a tensor whose row i (along the first dimension) is row
    // sources[i] of src
    static Ort::Value
    gather_rows(const Ort::Value &src, const std::vector<size_t> &sources) {
        auto info = src.GetTensorTypeAndShapeInfo();
        std::vector<int64_t> shape = info.GetShape();
        const ONNXTensorElementDataType type = info.GetElementType();
        const size_t src_rows = (size_t)shape[0];
        const size_t row_bytes = src_rows ? info.GetElementCount() / src_rows * element_size(type) : 0;
        shape[0] = (int64_t)sources.size();
        Ort::AllocatorWithDefaultOptions allocator;
        Ort::Value ans = Ort::Value::CreateTensor(allocator, shape.data(), shape.size(), type);
        const char *s = static_cast<const char *>(src.GetTensorRawData());
        char *d = static_cast<char *>(ans.GetTensorMutableRawData());
        for (size_t i = 0; i < sources.size(); i++) {
            if (sources[i] >= src_rows) throw std::runtime_error("Invalid row index");
            std::memcpy(d + i * row_bytes, s + sources[i] * row_bytes, row_bytes);
        }
        return ans;
    }

    // Repeat a tensor with a first dimension of 1, n times
    static Ort::Value
    tile(Ort::Value &src, size_t n) {
        if (n == 1) return std::move(src);
        return gather_rows(src, std::vector<size_t>(n, 0));
    }

    // Copy the logits for the specified batch item and position into row
    static void
    logits_row(const Ort::Value &logits, size_t b, size_t t, std::vector<float> &row) {
        auto info = logits.GetTensorTypeAndShapeInfo();
        const std::vector<int64_t> shape = info.GetShape();
        if (shape.size() != 3) throw std::runtime_error("The logits have an unexpected shape");
        const size_t seq_len = (size_t)shape[1], vocab_size = (size_t)shape[2];
        if (b >= (size_t)shape[0] || t >= seq_len) throw std::runtime_error("Logits index out of range");
        row.resize(vocab_size);
        const size_t offset = (b * seq_len + t) * vocab_size;
        switch (info.GetElementType()) {
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT: {
                const float *p = logits.GetTensorData<float>() + offset;
                std::copy(p, p + vocab_size, row.begin());
            } break;
            case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT16: {
                const Ort::Float16_t *p = logits.GetTensorData<Ort::Float16_t>() + offset;
                for (size_t i = 0; i < vocab_size; i++) row[i] = p[i].ToFloat();
            } break;
            default: throw std::runtime_error("Unsupported data type for logits");
        }
    }

    static void
    log_softmax(std::vector<float> &row) {
        const float m = *std::max_element(row.begin(), row.end());
        double sum = 0;
        for (float x : row) sum += std::exp((double)(x - m));
        const float lse = m + (float)std::log(sum);
        for (float &x : row) x -= lse;
    }
};

// Python wrapper {{{
// The Env must outlive all sessions, which can be owned by Python objects
// that are freed after the module, so it is never freed. It must be a plain
// pointer that is deliberately leaked, a static smart pointer would be
// destroyed at process exit, after the static objects in the onnxruntime
// library, causing a crash on macOS when the destructor locks an already
// destroyed mutex.
static Ort::Env *ort_env = nullptr;

// Raises an exception on failure. Must be called with the GIL held.
static Ort::Env &
get_ort_env() {
    if (!ort_env) {
        Ort::Env *env = new Ort::Env(ORT_LOGGING_LEVEL_WARNING, "seq2seq");
        env->DisableTelemetryEvents();
        ort_env = env;
    }
    return *ort_env;
}

typedef struct {
    PyObject_HEAD Model *model;
} Seq2SeqModel;

static bool
token_ids_from_python(PyObject *seq, TokenIds &ans, const char *what) {
    PyObject *fast = PySequence_Fast(seq, what);
    if (!fast) return false;
    const Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    ans.reserve(n);
    for (Py_ssize_t i = 0; i < n; i++) {
        const long long v = PyLong_AsLongLong(PySequence_Fast_GET_ITEM(fast, i));
        if (v == -1 && PyErr_Occurred()) {
            Py_DECREF(fast);
            return false;
        }
        ans.push_back((int64_t)v);
    }
    Py_DECREF(fast);
    return true;
}

static PyObject *
token_ids_to_python(const TokenIds &ids) {
    PyObject *ans = PyTuple_New(ids.size());
    if (!ans) return NULL;
    for (size_t i = 0; i < ids.size(); i++) {
        PyObject *x = PyLong_FromLongLong(ids[i]);
        if (!x) {
            Py_DECREF(ans);
            return NULL;
        }
        PyTuple_SET_ITEM(ans, i, x);
    }
    return ans;
}

static PyObject *
Seq2SeqModel_new(PyTypeObject *type, PyObject *args, PyObject *kw) {
    static const char *kwlist[] = {
        "encoder_path", "decoder_path", "decoder_with_past_path", "provider", "num_threads", "decoder_start_token_id", "eos_token_id", "pad_token_id", NULL};
    PyObject *enc, *dec, *decp = Py_None;
    const char *provider = "";
    int num_threads = 0;
    long long start_id = 0, eos_id = 1, pad_id = 0;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "UU|OsiLLL", (char **)kwlist, &enc, &dec, &decp, &provider, &num_threads, &start_id, &eos_id, &pad_id))
        return NULL;
    OrtPath encoder_path, decoder_path, decoder_with_past_path;
    if (!calibre_ort::path_from_python(enc, encoder_path) || !calibre_ort::path_from_python(dec, decoder_path)) return NULL;
    if (decp != Py_None) {
        if (!PyUnicode_Check(decp)) {
            PyErr_SetString(PyExc_TypeError, "decoder_with_past_path must be a string or None");
            return NULL;
        }
        if (!calibre_ort::path_from_python(decp, decoder_with_past_path)) return NULL;
    }
    Seq2SeqModel *self = (Seq2SeqModel *)type->tp_alloc(type, 0);
    if (!self) return NULL;
    Ort::Env *env;
    try {
        env = &get_ort_env();
    } catch (const std::exception &e) {
        Py_DECREF(self);
        PyErr_Format(PyExc_OSError, "Failed to initialize onnxruntime: %s", e.what());
        return NULL;
    }
    std::string error;
    const std::string prov(provider);
    Py_BEGIN_ALLOW_THREADS;
    try {
        self->model = new Model(*env, encoder_path, decoder_path, decoder_with_past_path, prov, num_threads);
        self->model->decoder_start_token_id = start_id;
        self->model->eos_token_id = eos_id;
        self->model->pad_token_id = pad_id;
    } catch (const std::exception &e) {
        error = e.what();
        if (error.empty()) error = "Unknown error";
    }
    Py_END_ALLOW_THREADS;
    if (!error.empty()) {
        Py_DECREF(self);
        PyErr_Format(PyExc_OSError, "Failed to load the model: %s", error.c_str());
        return NULL;
    }
    return (PyObject *)self;
}

static void
Seq2SeqModel_dealloc(Seq2SeqModel *self) {
    delete self->model;
    self->model = NULL;
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
Seq2SeqModel_score(Seq2SeqModel *self, PyObject *pairs) {
    std::vector<std::pair<TokenIds, TokenIds>> items;
    PyObject *fast = PySequence_Fast(pairs, "pairs must be a sequence of (input_ids, target_ids)");
    if (!fast) return NULL;
    for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(fast); i++) {
        PyObject *a, *b;
        if (!PyArg_ParseTuple(PySequence_Fast_GET_ITEM(fast, i), "OO", &a, &b)) {
            Py_DECREF(fast);
            return NULL;
        }
        items.emplace_back();
        if (!token_ids_from_python(a, items.back().first, "input_ids must be a sequence of ints") ||
            !token_ids_from_python(b, items.back().second, "target_ids must be a sequence of ints")) {
            Py_DECREF(fast);
            return NULL;
        }
    }
    Py_DECREF(fast);
    if (items.empty()) return PyList_New(0);
    std::vector<std::pair<std::vector<float>, TokenIds>> results;
    std::string error;
    Py_BEGIN_ALLOW_THREADS;
    try {
        results = self->model->score(items);
    } catch (const std::exception &e) { error = e.what(); }
    Py_END_ALLOW_THREADS;
    if (!error.empty()) {
        PyErr_Format(PyExc_RuntimeError, "Failed to run the model: %s", error.c_str());
        return NULL;
    }
    PyObject *ans = PyList_New(results.size());
    if (!ans) return NULL;
    for (size_t i = 0; i < results.size(); i++) {
        PyObject *lp = PyTuple_New(results[i].first.size());
        if (!lp) {
            Py_DECREF(ans);
            return NULL;
        }
        for (size_t j = 0; j < results[i].first.size(); j++) {
            PyObject *f = PyFloat_FromDouble(results[i].first[j]);
            if (!f) {
                Py_DECREF(lp);
                Py_DECREF(ans);
                return NULL;
            }
            PyTuple_SET_ITEM(lp, j, f);
        }
        PyObject *best = token_ids_to_python(results[i].second);
        PyObject *item = best ? PyTuple_Pack(2, lp, best) : NULL;
        Py_DECREF(lp);
        Py_XDECREF(best);
        if (!item) {
            Py_DECREF(ans);
            return NULL;
        }
        PyList_SET_ITEM(ans, i, item);
    }
    return ans;
}

static PyObject *
Seq2SeqModel_generate(Seq2SeqModel *self, PyObject *args, PyObject *kw) {
    static const char *kwlist[] = {"input_ids", "max_length", "num_beams", "num_return_sequences", "length_penalty", "forced_prefix", NULL};
    PyObject *pyids, *pyprefix = NULL;
    Py_ssize_t max_length = 256, num_beams = 1, num_return = 1;
    float length_penalty = 1.0f;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "O|nnnfO", (char **)kwlist, &pyids, &max_length, &num_beams, &num_return, &length_penalty, &pyprefix))
        return NULL;
    if (max_length < 1 || num_beams < 1 || num_return < 1) {
        PyErr_SetString(PyExc_ValueError, "max_length, num_beams and num_return_sequences must be positive");
        return NULL;
    }
    TokenIds ids, prefix;
    if (!token_ids_from_python(pyids, ids, "input_ids must be a sequence of ints")) return NULL;
    if (pyprefix && !token_ids_from_python(pyprefix, prefix, "forced_prefix must be a sequence of ints")) return NULL;
    std::vector<std::pair<TokenIds, float>> results;
    std::string error;
    bool aborted = false;
    Py_BEGIN_ALLOW_THREADS;
    try {
        results = self->model->generate(ids, (size_t)max_length, (size_t)num_beams, (size_t)num_return, length_penalty, prefix);
    } catch (const std::exception &e) { error = e.what(); }
    aborted = self->model->aborted;
    Py_END_ALLOW_THREADS;
    if (aborted) Py_RETURN_NONE;
    if (!error.empty()) {
        PyErr_Format(PyExc_RuntimeError, "Failed to run the model: %s", error.c_str());
        return NULL;
    }
    PyObject *ans = PyList_New(results.size());
    if (!ans) return NULL;
    for (size_t i = 0; i < results.size(); i++) {
        PyObject *t = token_ids_to_python(results[i].first);
        PyObject *item = t ? Py_BuildValue("Nd", t, (double)results[i].second) : NULL;
        if (!item) {
            Py_DECREF(ans);
            return NULL;
        }
        PyList_SET_ITEM(ans, i, item);
    }
    return ans;
}

static PyObject *
Seq2SeqModel_abort(Seq2SeqModel *self, PyObject *args) {
    self->model->abort();
    Py_RETURN_NONE;
}

static PyObject *
Seq2SeqModel_get_provider(Seq2SeqModel *self, void *closure) {
    return PyUnicode_FromString(self->model->provider.empty() ? "CPUExecutionProvider" : self->model->provider.c_str());
}

static PyObject *
Seq2SeqModel_get_node_counts(Seq2SeqModel *self, void *closure) {
    NodeCounts c = self->model->node_counts();
    return Py_BuildValue("nn", (Py_ssize_t)c.on_provider, (Py_ssize_t)c.total);
}

static PyObject *
Seq2SeqModel_get_layout(Seq2SeqModel *self, void *closure) {
    switch (self->model->layout) {
        case Layout::Separate: return PyUnicode_FromString("separate");
        case Layout::Merged: return PyUnicode_FromString("merged");
        case Layout::NoCache: break;
    }
    return PyUnicode_FromString("nocache");
}

static PyMethodDef Seq2SeqModel_methods[] = {
    {"score",
     (PyCFunction)Seq2SeqModel_score,
     METH_O,
     "score(pairs) -> For every (input_ids, target_ids) pair return (logprobs, best_ids) where logprobs is the log probability of each target token "
     "given the input and the preceding target tokens and best_ids are the tokens the model considers most likely at each position. target_ids "
     "should end with the end of sequence token."},
    {"generate",
     (PyCFunction)Seq2SeqModel_generate,
     METH_VARARGS | METH_KEYWORDS,
     "generate(input_ids, max_length=256, num_beams=1, num_return_sequences=1, length_penalty=1.0, forced_prefix=()) -> Return a list of (token_ids, "
     "score) sorted by descending score, or None if aborted. The token_ids start with forced_prefix and exclude the start and end of sequence tokens. "
     "Uses greedy decoding when num_beams is 1, otherwise beam search."},
    {"abort", (PyCFunction)Seq2SeqModel_abort, METH_NOARGS, "abort() -> Abort any generate() calls that are running. Can be called from any thread."},
    {NULL} /* Sentinel */
};

static PyGetSetDef Seq2SeqModel_getsets[] = {
    {"provider", (getter)Seq2SeqModel_get_provider, NULL, "The name of the onnxruntime execution provider used to run the model", NULL},
    {"node_counts",
     (getter)Seq2SeqModel_get_node_counts,
     NULL,
     "(number of nodes run by the provider, total number of nodes) for all the sessions of this model. Both are zero if onnxruntime is too old to "
     "report this information.",
     NULL},
    {"layout", (getter)Seq2SeqModel_get_layout, NULL, "The layout of the model files: separate, merged or nocache", NULL},
    {NULL} /* Sentinel */
};

static PyTypeObject Seq2SeqModelType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "seq2seq.Seq2SeqModel",
    /* tp_basicsize      */ sizeof(Seq2SeqModel),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)Seq2SeqModel_dealloc,
    /* tp_vectorcall_offset */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_as_async       */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */
    "Seq2SeqModel(encoder_path, decoder_path, decoder_with_past_path=None, provider='', num_threads=0, decoder_start_token_id=0, "
    "eos_token_id=1, pad_token_id=0) -> An encoder-decoder model. provider is the name of an onnxruntime execution provider, the "
    "empty string means use only the CPU. num_threads of zero means use the onnxruntime default.",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ Seq2SeqModel_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ Seq2SeqModel_getsets,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ Seq2SeqModel_new,
};
// }}}

// Boilerplate {{{
static PyObject *
gpu_providers(PyObject *self, PyObject *args) {
    std::vector<std::string> providers;
    try {
        providers = calibre_ort::accelerated_providers();
    } catch (const std::exception &e) {
        PyErr_Format(PyExc_OSError, "Failed to query onnxruntime for available execution providers: %s", e.what());
        return NULL;
    }
    PyObject *ans = PyTuple_New(providers.size());
    if (!ans) return NULL;
    for (size_t i = 0; i < providers.size(); i++) {
        PyObject *s = PyUnicode_FromString(providers[i].c_str());
        if (!s) {
            Py_DECREF(ans);
            return NULL;
        }
        PyTuple_SET_ITEM(ans, i, s);
    }
    return ans;
}

static PyObject *
onnxruntime_version(PyObject *self, PyObject *args) {
    const OrtApiBase *base = OrtGetApiBase();
    return PyUnicode_FromString(base ? base->GetVersionString() : "unknown");
}

static char doc[] = "Run encoder-decoder (sequence to sequence) models using onnxruntime";
static PyMethodDef methods[] = {
    {"gpu_providers",
     (PyCFunction)gpu_providers,
     METH_NOARGS,
     "gpu_providers() -> Return the hardware accelerated execution providers available in this build of onnxruntime, in order of preference"},
    {"onnxruntime_version", (PyCFunction)onnxruntime_version, METH_NOARGS, "onnxruntime_version() -> The version of the loaded onnxruntime library"},
    {NULL} /* Sentinel */
};

static int
exec_module(PyObject *mod) {
    if (!calibre_ort::init_ort_api()) return -1;
    if (PyType_Ready(&Seq2SeqModelType) < 0) return -1;
    Py_INCREF(&Seq2SeqModelType);
    if (PyModule_AddObject(mod, "Seq2SeqModel", (PyObject *)&Seq2SeqModelType) < 0) {
        Py_DECREF(&Seq2SeqModelType);
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot slots[] = {{Py_mod_exec, (void *)exec_module}, {0, NULL}};

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC
PyInit_seq2seq(void) {
    module_def.m_name = "seq2seq";
    module_def.m_slots = slots;
    module_def.m_doc = doc;
    module_def.m_methods = methods;
    return PyModuleDef_Init(&module_def);
}
// }}}
