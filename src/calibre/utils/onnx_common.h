/*
 * onnx_common.h
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

// Code shared by the extension modules that run models using onnxruntime.
// Every module that includes this must call init_ort_api() in its
// Py_mod_exec function before using any other onnxruntime APIs.

#pragma once

#include <Python.h>
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#ifdef _WIN32
#define ORT_DLL_IMPORT
#endif
// The OrtApi is initialized in init_ort_api() so that a mismatched
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

namespace calibre_ort {

typedef std::basic_string<ORTCHAR_T> OrtPath;

struct NodeCounts {
    size_t on_provider = 0, total = 0;
};

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

// Initialize the onnxruntime C++ API. Returns false with a Python exception
// set if the loaded onnxruntime library is incompatible.
static inline bool
init_ort_api() {
    const OrtApiBase *base = OrtGetApiBase();
    const OrtApi *api = base ? base->GetApi(ORT_API_VERSION) : NULL;
    if (!api) {
        PyErr_Format(
            PyExc_ImportError,
            "The loaded onnxruntime library (version: %s) does not support the API version %d this module was built with",
            base ? base->GetVersionString() : "unknown",
            ORT_API_VERSION);
        return false;
    }
    Ort::InitApi(api);
    return true;
}

// Return the accelerated providers present in this build of onnxruntime, in
// priority order. Raises Ort::Exception on failure.
static inline std::vector<std::string>
accelerated_providers() {
    std::vector<std::string> ans;
    const std::vector<std::string> available = Ort::GetAvailableProviders();
    for (const std::string &p : PRIORITY_ORDER) {
        if (std::find(available.begin(), available.end(), p) != available.end()) ans.push_back(p);
    }
    return ans;
}

typedef std::unordered_map<std::string, std::string> ProviderOptions;

// Options for CoreML suitable for models with dynamic input shapes, such as
// text models. MLProgram supports more operators than the older default
// NeuralNetwork format.
static const ProviderOptions COREML_DYNAMIC_SHAPE_OPTIONS = {{"ModelFormat", "MLProgram"}, {"RequireStaticInputShapes", "0"}};

// Raises an exception if the provider cannot be added. coreml_options are
// used only for the CoreML provider.
static inline void
append_execution_provider(Ort::SessionOptions &opts, const std::string &name, const ProviderOptions &coreml_options = ProviderOptions()) {
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
    } else if (name == "CoreMLExecutionProvider") {
        opts.AppendExecutionProvider(name, coreml_options);
    } else if (name == "OpenVINOExecutionProvider") {
        opts.AppendExecutionProvider(name, ProviderOptions());
    } else {
        throw std::runtime_error("Unsupported execution provider: " + name);
    }
}

// Apply the session options that are needed for every provider and add the
// specified provider, if it is not empty. Raises an exception on failure.
static inline void
configure_session_options(Ort::SessionOptions &opts, const std::string &provider, const ProviderOptions &coreml_options = ProviderOptions()) {
    opts.DisableMemPattern(); // required by DirectML
    opts.DisableProfiling();
    opts.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL); // required by DirectML
#if HAS_EP_ASSIGNMENT_INFO
    opts.AddConfigEntry(kOrtSessionOptionsRecordEpGraphAssignmentInfo, "1");
#endif
    if (!provider.empty()) append_execution_provider(opts, provider, coreml_options);
}

// Count the nodes of the model assigned to the specified provider. Raises an
// exception on failure. Returns zero counts if onnxruntime is too old to
// report this information.
static inline NodeCounts
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

// Convert a Python str to a path usable by onnxruntime. Returns false with a
// Python exception set on failure.
static inline bool
path_from_python(PyObject *pypath, OrtPath &ans) {
#ifdef _WIN32
    wchar_t *buf = PyUnicode_AsWideCharString(pypath, NULL);
    if (!buf) return false;
    ans = OrtPath(buf);
    PyMem_Free(buf);
#else
    const char *buf = PyUnicode_AsUTF8(pypath);
    if (!buf) return false;
    ans = OrtPath(buf);
#endif
    return true;
}

static inline PyObject *
path_to_python(const OrtPath &path) {
#ifdef _WIN32
    return PyUnicode_FromWideChar(path.c_str(), path.size());
#else
    return PyUnicode_DecodeFSDefaultAndSize(path.c_str(), path.size());
#endif
}

} // namespace calibre_ort
