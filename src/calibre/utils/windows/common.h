/*
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define PY_SSIZE_T_CLEAN
#define UNICODE
#include <Windows.h>
#include <Python.h>

class wchar_raii {
	private:
		wchar_t *handle;
		wchar_raii( const wchar_raii & ) ;
		wchar_raii & operator=( const wchar_raii & ) ;

	public:
		wchar_raii() : handle(NULL) {}

		~wchar_raii() {
			if (handle) {
				PyMem_Free(handle);
				handle = NULL;
			}
		}

		wchar_t *ptr() { return handle; }
		void set_ptr(wchar_t *val) { handle = val; }
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
