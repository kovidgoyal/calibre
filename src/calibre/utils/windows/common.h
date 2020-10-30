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

static inline PyObject*
set_error_from_hresult(const char *file, const int line, const HRESULT hr, const char *prefix="", PyObject *name=NULL) {
    _com_error err(hr);
    LPCWSTR msg = err.ErrorMessage();
    PyObject *pmsg = PyUnicode_FromWideChar(msg, -1);
    PyObject *ans;
    if (name) ans = PyErr_Format(PyExc_OSError, "%s:%d:%s:[%li] %V: %S", file, line, prefix, hr, pmsg, "Out of memory", name);
    else ans = PyErr_Format(PyExc_OSError, "%s:%d:%s:[%li] %V", file, line, prefix, hr, pmsg, "Out of memory");
    Py_CLEAR(pmsg);
    return ans;
}
#define error_from_hresult(hr, ...) set_error_from_hresult(__FILE__, __LINE__, hr, __VA_ARGS__)

class wchar_raii {
	private:
		wchar_t *handle;
		wchar_raii( const wchar_raii & ) ;
		wchar_raii & operator=( const wchar_raii & ) ;

	public:
		wchar_raii() : handle(NULL) {}
		wchar_raii(wchar_t *h) : handle(h) {}

		~wchar_raii() {
			if (handle) {
				PyMem_Free(handle);
				handle = NULL;
			}
		}

		wchar_t *ptr() { return handle; }
		void set_ptr(wchar_t *val) { handle = val; }
		explicit operator bool() const { return handle != NULL; }
};


class com_wchar_raii {
	private:
		wchar_t *handle;
		com_wchar_raii( const com_wchar_raii & ) ;
		com_wchar_raii & operator=( const com_wchar_raii & ) ;

	public:
		com_wchar_raii() : handle(NULL) {}

		~com_wchar_raii() {
			if (handle) {
                CoTaskMemFree(handle);
				handle = NULL;
			}
		}

		wchar_t *ptr() { return handle; }
		wchar_t **address() { return &handle; }
		explicit operator bool() const { return handle != NULL; }
};

class pyobject_raii {
	private:
		PyObject *handle;
		pyobject_raii( const pyobject_raii & ) ;
		pyobject_raii & operator=( const pyobject_raii & ) ;

	public:
		pyobject_raii() : handle(NULL) {}
		pyobject_raii(PyObject* h) : handle(h) {}

		~pyobject_raii() { Py_CLEAR(handle); }

		PyObject *ptr() { return handle; }
		void set_ptr(PyObject *val) { handle = val; }
		PyObject **address() { return &handle; }
		explicit operator bool() const { return handle != NULL; }
        PyObject *detach() { PyObject *ans = handle; handle = NULL; return ans; }
};


class handle_raii {
	private:
		HANDLE handle;
		handle_raii( const handle_raii & ) ;
		handle_raii & operator=( const handle_raii & ) ;

	public:
		handle_raii() : handle(INVALID_HANDLE_VALUE) {}
		handle_raii(HANDLE h) : handle(h) {}

		~handle_raii() {
			if (handle != INVALID_HANDLE_VALUE) {
				CloseHandle(handle);
				handle = INVALID_HANDLE_VALUE;
			}
		}

		HANDLE ptr() const { return handle; }
		void set_ptr(HANDLE val) { handle = val; }
		explicit operator bool() const { return handle != INVALID_HANDLE_VALUE; }

};


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
