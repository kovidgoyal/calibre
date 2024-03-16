/*
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#include <string>
#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <Python.h>
#include <memory>
#include <comdef.h>
#include <system_error>
#include "../cpp_binding.h"

static inline PyObject*
set_error_from_hresult(PyObject *exc_type, const char *file, const int line, const HRESULT hr, const char *prefix="", PyObject *name=NULL) {
    _com_error err(hr);
    PyObject *pmsg = PyUnicode_FromWideChar(err.ErrorMessage(), -1);
    if (name) PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x wCode=%d] %V: %S", file, line, prefix, hr, err.WCode(), pmsg, "Out of memory", name);
    else PyErr_Format(exc_type, "%s:%d:%s:[hr=0x%x wCode=%d] %V", file, line, prefix, hr, err.WCode(), pmsg, "Out of memory");
    Py_CLEAR(pmsg);
    return NULL;
}
#define error_from_hresult(hr, ...) set_error_from_hresult(PyExc_OSError, __FILE__, __LINE__, hr, __VA_ARGS__)

// trim from end (in place)
template<typename T>
static inline void
rtrim(std::basic_string<T> &s) {
    s.erase(std::find_if(s.rbegin(), s.rend(), [](T ch) {
        switch (ch) { case ' ': case '\t': case '\n': case '\r': case '\v': case '\f': return false; }
        return true;
    }).base(), s.end());
}

static inline std::wstring
get_last_error(std::wstring const & prefix = L"") {
    auto ec = GetLastError();
    LPWSTR buf;
    DWORD n;

    if ((n = FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER |
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        ec,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&buf),
        0, NULL)) == 0) {
        auto error_code{ ::GetLastError() };
        throw std::system_error(error_code, std::system_category(), "Failed to retrieve error message string.");
    }
    auto deleter = [](void* p) { ::LocalFree(p); };
    std::unique_ptr<WCHAR, decltype(deleter)> ptrBuffer(buf, deleter);
    auto msg = std::wstring(buf, n);
    std::wstring ans = prefix;
    if (prefix.size() > 0) {
        ans += L": ";
    }
    rtrim(msg);
    ans += L"Code: " + std::to_wstring(ec) + L" Message: " + msg;
    return ans;
}

class scoped_com_initializer {  // {{{
	public:
		scoped_com_initializer() : m_succeded(false), hr(0) {
            hr = CoInitialize(NULL);
            if (SUCCEEDED(hr)) m_succeded = true;
        }
		~scoped_com_initializer() { if (succeeded()) CoUninitialize(); }

		explicit operator bool() const noexcept { return m_succeded; }

		bool succeeded() const noexcept { return m_succeded; }

        PyObject* set_python_error() const noexcept {
            if (hr == RPC_E_CHANGED_MODE) {
                PyErr_SetString(PyExc_OSError, "COM initialization failed as it was already initialized in multi-threaded mode");
            } else {
                _com_error err(hr);
                PyObject *pmsg = PyUnicode_FromWideChar(err.ErrorMessage(), -1);
                PyErr_Format(PyExc_OSError, "COM initialization failed: %V", pmsg, "Out of memory");
            }
            return NULL;
        }

        void detach() noexcept { m_succeded = false; }

	private:
		bool m_succeded;
        HRESULT hr;
		scoped_com_initializer( const scoped_com_initializer & ) ;
		scoped_com_initializer & operator=( const scoped_com_initializer & ) ;
}; // }}}

#define INITIALIZE_COM_IN_FUNCTION scoped_com_initializer com; if (!com) return com.set_python_error();

template<typename T>
static inline void co_task_mem_free(T *x) { CoTaskMemFree(x); }
typedef generic_raii<wchar_t*, co_task_mem_free> com_wchar_raii;

static inline void mapping_raii_free(void *x) { UnmapViewOfFile(x); }
typedef generic_raii<void*, mapping_raii_free> mapping_raii;
static inline HANDLE invalid_handle_value_getter(void) { return INVALID_HANDLE_VALUE; }
static inline void close_handle(HANDLE x) { CloseHandle(x); }
typedef generic_raii<HANDLE, close_handle, invalid_handle_value_getter> handle_raii;
typedef generic_raii<HANDLE, close_handle> handle_raii_null;

struct prop_variant : PROPVARIANT {
	prop_variant(VARTYPE vt=VT_EMPTY) noexcept : PROPVARIANT{} { PropVariantInit(this); this->vt = vt;  }

    ~prop_variant() noexcept { clear(); }

    void clear() noexcept { PropVariantClear(this); }
};
