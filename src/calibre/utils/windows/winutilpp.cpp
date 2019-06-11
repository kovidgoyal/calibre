/*
 * winutil.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define UNICODE
#include <Windows.h>
#include <combaseapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <atlbase.h>  // for CComPtr
#include <Python.h>

static inline int
py_to_wchar(PyObject *obj, wchar_t **output) {
	if (!PyUnicode_Check(obj)) {
		if (obj == Py_None) { *output = NULL; return 1; }
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
#if PY_MAJOR_VERSION < 3
	*output = PyUnicode_AS_UNICODE(obj);
#else
	*output = PyUnicode_AsWideCharString(obj, NULL);
#endif
	return 1;
}

static inline void
free_wchar_buffer(wchar_t **buf) {
#if PY_MAJOR_VERSION >= 3
	PyMem_Free(*buf);
#endif
	*buf = NULL;
}


extern "C" {

PyObject *
add_to_recent_docs(PyObject *self, PyObject *args) {
	wchar_t *path, *app_id;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &path, py_to_wchar, &app_id)) return NULL;
	if (app_id) {
		CComPtr<IShellItem> item;
		HRESULT hr = SHCreateItemFromParsingName(path, NULL, IID_PPV_ARGS(&item));
		if (SUCCEEDED(hr)) {
			SHARDAPPIDINFO info;
			info.psi = item;
			info.pszAppID = app_id;
			SHAddToRecentDocs(SHARD_APPIDINFO, &info);
		}
	} else {
		SHAddToRecentDocs(SHARD_PATHW, path);
	}
	free_wchar_buffer(&path); free_wchar_buffer(&app_id);
	Py_RETURN_NONE;
}


PyObject *
file_association(PyObject *self, PyObject *args) {
	wchar_t *ext, buf[2048];
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &ext)) return NULL;
	HRESULT hr = AssocQueryStringW(0, ASSOCSTR_EXECUTABLE, ext, NULL, buf, &sz);
	free_wchar_buffer(&ext);
	if (!SUCCEEDED(hr)) Py_RETURN_NONE;
	return Py_BuildValue("u#", buf, (int)sz);
}

}
