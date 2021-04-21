/*
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <Windows.h>
#include <Python.h>
#include <comdef.h>
#define arraysz(x) (sizeof(x)/sizeof(x[0]))

static inline PyObject*
set_error_from_hresult(PyObject *exc_type, const char *file, const int line, const HRESULT hr, const char *prefix="", PyObject *name=NULL) {
    _com_error err(hr);
    LPCWSTR msg = err.ErrorMessage();
    PyObject *pmsg = PyUnicode_FromWideChar(msg, -1);
    PyObject *ans;
    if (name) ans = PyErr_Format(exc_type, "%s:%d:%s:[%li] %V: %S", file, line, prefix, hr, pmsg, "Out of memory", name);
    else ans = PyErr_Format(exc_type, "%s:%d:%s:[%li] %V", file, line, prefix, hr, pmsg, "Out of memory");
    Py_CLEAR(pmsg);
    return NULL;
}
#define error_from_hresult(hr, ...) set_error_from_hresult(PyExc_OSError, __FILE__, __LINE__, hr, __VA_ARGS__)

template<typename T, void free_T(void*), T null>
class generic_raii {
	private:
		T handle;
		generic_raii( const generic_raii & ) ;
		generic_raii & operator=( const generic_raii & ) ;

	public:
		explicit generic_raii(T h = null) : handle(h) {}
		~generic_raii() { release(); }

		void release() {
			if (handle != null) {
				free_T(handle);
				handle = null;
			}
		}

		T ptr() { return handle; }
		T detach() { T ans = handle; handle = null; return ans; }
		void set_ptr(T val) { handle = val; }
		T* address() { return &handle; }
		explicit operator bool() const { return handle != null; }
		T* operator &() { return &handle; }
};

typedef generic_raii<wchar_t*, PyMem_Free, NULL> wchar_raii;
typedef generic_raii<wchar_t*, CoTaskMemFree, NULL> com_wchar_raii;
static inline void python_object_destructor(void *p) { PyObject *x = reinterpret_cast<PyObject*>(p); Py_XDECREF(x); }
typedef generic_raii<PyObject*, python_object_destructor, NULL> pyobject_raii;
static inline void handle_destructor(HANDLE p) { CloseHandle(p); }
typedef generic_raii<HANDLE, handle_destructor, INVALID_HANDLE_VALUE> handle_raii;


static int
py_to_wchar(PyObject *obj, wchar_raii *output) {
	if (!PyUnicode_Check(obj)) {
		if (obj == Py_None) { return 1; }
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
    wchar_t *buf = PyUnicode_AsWideCharString(obj, NULL);
    if (!buf) { PyErr_NoMemory(); return 0; }
	output->set_ptr(buf);
	return 1;
}

static int
py_to_wchar_no_none(PyObject *obj, wchar_raii *output) {
	if (!PyUnicode_Check(obj)) {
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
    wchar_t *buf = PyUnicode_AsWideCharString(obj, NULL);
    if (!buf) { PyErr_NoMemory(); return 0; }
	output->set_ptr(buf);
	return 1;
}
