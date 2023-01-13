/*
 * Copyright (C) 2021 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <Python.h>
#include <wchar.h>
#if __cplusplus >= 201703L
#include <string_view>
#endif

#define arraysz(x) (sizeof(x)/sizeof(x[0]))

template<typename T, void free_T(void*), T null=static_cast<T>(NULL)>
class generic_raii {
	private:
		generic_raii( const generic_raii & ) noexcept;
		generic_raii & operator=( const generic_raii & ) noexcept ;

	protected:
		T handle;

	public:
		explicit generic_raii(T h = null) noexcept : handle(h) {}
		~generic_raii() noexcept { release(); }

		void release() noexcept {
			if (handle != null) {
				free_T(handle);
				handle = null;
			}
		}

		T ptr() noexcept { return handle; }
		T detach() noexcept { T ans = handle; handle = null; return ans; }
		void attach(T val) noexcept { release(); handle = val; }
		T* unsafe_address() noexcept { return &handle; }
		explicit operator bool() const noexcept { return handle != null; }
};

#if __cplusplus >= 201703L
class wchar_raii : public generic_raii<wchar_t*, PyMem_Free> {
    private:
        Py_ssize_t sz;
    public:
        int from_unicode(PyObject *obj) {
            wchar_t *buf = PyUnicode_AsWideCharString(obj, &sz);
            if (!buf) return 0;
            attach(buf);
            return 1;
        }
        std::wstring_view as_view() const { return std::wstring_view(handle, sz); }
};
#else
typedef generic_raii<wchar_t*, PyMem_Free> wchar_raii;
#endif

static inline void python_object_destructor(void *p) { PyObject *x = reinterpret_cast<PyObject*>(p); Py_XDECREF(x); }
typedef generic_raii<PyObject*, python_object_destructor> pyobject_raii;

template<typename T, void free_T(void*), size_t sz, T null=static_cast<T>(NULL)>
class generic_raii_array {
	private:
		generic_raii_array( const generic_raii_array & ) noexcept;
		generic_raii_array & operator=( const generic_raii_array & ) noexcept ;

	protected:
		T array[sz];

	public:
		explicit generic_raii_array() noexcept : array() {}
		~generic_raii_array() noexcept { release(); }

		void release() noexcept {
			for (size_t i = 0; i < sz; i++) {
				if (array[i] != null) {
					free_T(array[i]);
					array[i] = null;
				}
			}
		}

		T* ptr() noexcept { return reinterpret_cast<T*>(array); }
		size_t size() const noexcept { return sz; }
		T operator [](size_t i) noexcept { return array[i]; }
		const T operator[](size_t i) const noexcept { return array[i]; }
};


static inline int
py_to_wchar(PyObject *obj, wchar_raii *output) {
	if (!PyUnicode_Check(obj)) {
		if (obj == Py_None) { output->release(); return 1; }
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
    wchar_t *buf = PyUnicode_AsWideCharString(obj, NULL);
    if (!buf) { PyErr_NoMemory(); return 0; }
	output->attach(buf);
	return 1;
}

static inline int
py_to_wchar_no_none(PyObject *obj, wchar_raii *output) {
	if (!PyUnicode_Check(obj)) {
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
#if __cplusplus >= 201703L
    return output->from_unicode(obj);
#else
    wchar_t *buf = PyUnicode_AsWideCharString(obj, NULL);
    if (!buf) { return 0; }
    output->attach(buf);
    return 1;
#endif
}
