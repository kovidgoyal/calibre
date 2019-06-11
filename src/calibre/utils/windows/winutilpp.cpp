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

class wchar_raii {
	private:
		wchar_t **handle;
		// copy and assignment not implemented; prevent their use by
		// declaring private.
		wchar_raii( const wchar_raii & ) ;
		wchar_raii & operator=( const wchar_raii & ) ;

	public:
		wchar_raii(wchar_t **buf) : handle(*buf) {}

		~wchar_raii() {
#if PY_MAJOR_VERSION >= 3
			PyMem_Free(*handle);
#endif
			*handle = NULL;
		}

		wchar_t *ptr() { return *handle; }
};

extern "C" {

PyObject *
winutil_add_to_recent_docs(PyObject *self, PyObject *args) {
	wchar_t *path_, *app_id_;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &path_, py_to_wchar, &app_id_)) return NULL;
	wchar_raii path(path_), app_id(app_id_);
	if (app_id.ptr()) {
		CComPtr<IShellItem> item;
		HRESULT hr = SHCreateItemFromParsingName(path.ptr(), NULL, IID_PPV_ARGS(&item));
		if (SUCCEEDED(hr)) {
			SHARDAPPIDINFO info;
			info.psi = item;
			info.pszAppID = app_id.ptr();
			SHAddToRecentDocs(SHARD_APPIDINFO, &info);
		}
	} else {
		SHAddToRecentDocs(SHARD_PATHW, path.ptr());
	}
	Py_RETURN_NONE;
}


PyObject *
winutil_file_association(PyObject *self, PyObject *args) {
	wchar_t *ext_, buf[2048];
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &ext_)) return NULL;
	wchar_raii ext(ext_);
	HRESULT hr = AssocQueryStringW(0, ASSOCSTR_EXECUTABLE, ext.ptr(), NULL, buf, &sz);
	if (!SUCCEEDED(hr) || sz < 1) Py_RETURN_NONE;
	return Py_BuildValue("u", buf);
}

PyObject *
winutil_friendly_name(PyObject *self, PyObject *args) {
	wchar_t *exe_, *prog_id_, buf[2048], *p;
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &prog_id_, py_to_wchar, &exe_)) return NULL;
	wchar_raii exe(exe_), prog_id(prog_id_);
	ASSOCF flags = ASSOCF_REMAPRUNDLL;
	if (exe.ptr()) {
		p = exe.ptr();
		flags |= ASSOCF_OPEN_BYEXENAME;
	} else p = prog_id.ptr();
	if (!p) Py_RETURN_NONE;
	HRESULT hr = AssocQueryStringW(flags, ASSOCSTR_FRIENDLYAPPNAME, p, NULL, buf, &sz);
	if (!SUCCEEDED(hr) || sz < 1) Py_RETURN_NONE;
	return Py_BuildValue("u", buf);
}

PyObject *
winutil_notify_associations_changed(PyObject *self, PyObject *args) {
	SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_DWORD | SHCNF_FLUSH, NULL, NULL);
	Py_RETURN_NONE;
}

}
