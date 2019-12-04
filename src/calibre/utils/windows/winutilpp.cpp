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
#include <versionhelpers.h>

class DeleteFileProgressSink : public IFileOperationProgressSink {  // {{{
 public:
  DeleteFileProgressSink() : m_cRef(0) {}

 private:
  ULONG STDMETHODCALLTYPE AddRef(void) { InterlockedIncrement(&m_cRef); return m_cRef; }
  ULONG STDMETHODCALLTYPE Release(void) {
	  ULONG ulRefCount = InterlockedDecrement(&m_cRef);
	  if (0 == m_cRef) delete this;
	  return ulRefCount;
  }
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, LPVOID* ppvObj) {
	  if (!ppvObj) return E_INVALIDARG;
	  *ppvObj = nullptr;
	  if (riid == IID_IUnknown || riid == IID_IFileOperationProgressSink) {
		  // Increment the reference count and return the pointer.
		  *ppvObj = reinterpret_cast<IUnknown*>(this);
		  AddRef();
		  return NOERROR;
	  }
	  return E_NOINTERFACE;
  }
  HRESULT STDMETHODCALLTYPE StartOperations(void) { return S_OK; }
  HRESULT STDMETHODCALLTYPE FinishOperations(HRESULT) { return S_OK; }
  HRESULT STDMETHODCALLTYPE PreRenameItem(
      DWORD, IShellItem*, LPCWSTR) { return S_OK; }
  HRESULT STDMETHODCALLTYPE PostRenameItem(
      DWORD, IShellItem*, LPCWSTR, HRESULT, IShellItem*) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PreMoveItem(
      DWORD, IShellItem*, IShellItem*, LPCWSTR) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PostMoveItem(
      DWORD, IShellItem*, IShellItem*, LPCWSTR, HRESULT, IShellItem*) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PreCopyItem(
      DWORD, IShellItem*, IShellItem*, LPCWSTR) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PostCopyItem(
      DWORD, IShellItem*, IShellItem*, LPCWSTR, HRESULT, IShellItem*) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PreDeleteItem(DWORD dwFlags, IShellItem*) {
	  if (!(dwFlags & TSF_DELETE_RECYCLE_IF_POSSIBLE)) return E_ABORT;
	  return S_OK;
  }
  HRESULT STDMETHODCALLTYPE PostDeleteItem(
      DWORD, IShellItem*, HRESULT, IShellItem*) { return S_OK; }
  HRESULT STDMETHODCALLTYPE PreNewItem(
      DWORD, IShellItem*, LPCWSTR) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE PostNewItem(
      DWORD, IShellItem*, LPCWSTR, LPCWSTR, DWORD, HRESULT, IShellItem*) { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE UpdateProgress(UINT, UINT) { return S_OK; }
  HRESULT STDMETHODCALLTYPE ResetTimer(void) { return S_OK; }
  HRESULT STDMETHODCALLTYPE PauseTimer(void) { return S_OK; }
  HRESULT STDMETHODCALLTYPE ResumeTimer(void) { return S_OK; }

  ULONG m_cRef;
}; // }}}

class wchar_raii {  // {{{
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
}; // }}}

class scoped_com_initializer {  // {{{
	public:
		scoped_com_initializer() : m_succeded(false) { if (SUCCEEDED(CoInitialize(NULL))) m_succeded = true; }
		~scoped_com_initializer() { CoUninitialize(); }
		bool succeded() { return m_succeded; }
	private:
		bool m_succeded;
		scoped_com_initializer( const scoped_com_initializer & ) ;
		scoped_com_initializer & operator=( const scoped_com_initializer & ) ;
}; // }}}

#if PY_MAJOR_VERSION < 3
static wchar_t*
PyUnicode_AsWideCharString(PyObject *obj, Py_ssize_t *size) {
    Py_ssize_t sz = PyUnicode_GET_SIZE(obj) * 4 + 4;
    wchar_t *ans = (wchar_t*)PyMem_Malloc(sz);
    memset(ans, 0, sz);
    Py_ssize_t res = PyUnicode_AsWideChar(reinterpret_cast<PyUnicodeObject*>(obj), ans, (sz / sizeof(wchar_t)) - 1);
    if (size) *size = res;
    return ans;
}
#endif

static inline int
py_to_wchar(PyObject *obj, wchar_raii *output) {
	if (!PyUnicode_Check(obj)) {
		if (obj == Py_None) { return 1; }
		PyErr_SetString(PyExc_TypeError, "unicode object expected");
		return 0;
	}
    wchar_t *buf = PyUnicode_AsWideCharString(obj, NULL);
	output->set_ptr(buf);
	return 1;
}

extern "C" {

PyObject *
winutil_add_to_recent_docs(PyObject *self, PyObject *args) {
	wchar_raii path, app_id;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &path, py_to_wchar, &app_id)) return NULL;
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
	wchar_t buf[2048];
	wchar_raii ext;
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &ext)) return NULL;
	HRESULT hr = AssocQueryStringW(0, ASSOCSTR_EXECUTABLE, ext.ptr(), NULL, buf, &sz);
	if (!SUCCEEDED(hr) || sz < 1) Py_RETURN_NONE;
	return Py_BuildValue("u", buf);
}

PyObject *
winutil_friendly_name(PyObject *self, PyObject *args) {
	wchar_t buf[2048], *p;
	wchar_raii exe, prog_id;
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &prog_id, py_to_wchar, &exe)) return NULL;
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

PyObject *
winutil_move_to_trash(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &path)) return NULL;

	scoped_com_initializer com;
	if (!com.succeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }

	CComPtr<IFileOperation> pfo;
	if (FAILED(CoCreateInstance(CLSID_FileOperation, nullptr, CLSCTX_ALL, IID_PPV_ARGS(&pfo)))) {
		PyErr_SetString(PyExc_OSError, "Failed to create IFileOperation instance");
		return NULL;
	}
	DWORD flags = FOF_NO_UI | FOF_NOERRORUI | FOF_SILENT;
	if (IsWindows8OrGreater()) {
		flags |= FOFX_ADDUNDORECORD | FOFX_RECYCLEONDELETE;
	} else {
		flags |= FOF_ALLOWUNDO;
	}
	if (FAILED(pfo->SetOperationFlags(flags))) {
		PyErr_SetString(PyExc_OSError, "Failed to set operation flags");
		return NULL;
	}

	CComPtr<IShellItem> delete_item;
	if (FAILED(SHCreateItemFromParsingName(path.ptr(), NULL, IID_PPV_ARGS(&delete_item)))) {
		PyErr_Format(PyExc_OSError, "Failed to create shell item for path: %R", PyTuple_GET_ITEM(args, 0));
		return NULL;
	}

	CComPtr<IFileOperationProgressSink> delete_sink(new DeleteFileProgressSink);
	if (FAILED(pfo->DeleteItem(delete_item, delete_sink))) {
		PyErr_SetString(PyExc_OSError, "Failed to delete item");
		return NULL;
	}

	if (FAILED(pfo->PerformOperations())) {
		PyErr_SetString(PyExc_OSError, "Failed to perform delete operation");
		return NULL;
	}

	Py_RETURN_NONE;
}

PyObject *
winutil_manage_shortcut(PyObject *self, PyObject *args) {
	wchar_raii path, target, description, quoted_args;
	if (!PyArg_ParseTuple(args, "O&O&O&O&", py_to_wchar, &path, py_to_wchar, &target, py_to_wchar, &description, py_to_wchar, &quoted_args)) return NULL;
	if (!path.ptr()) {
		PyErr_SetString(PyExc_TypeError, "Path must not be None");
		return NULL;
	}

	scoped_com_initializer com;
	if (!com.succeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }

	CComPtr<IShellLink> shell_link;
	if (FAILED(CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&shell_link)))) {
		PyErr_SetString(PyExc_OSError, "Failed to create IShellLink instance");
		return NULL;
	}
	CComPtr<IPersistFile> persist_file;
	if (FAILED(shell_link->QueryInterface(IID_PPV_ARGS(&persist_file)))) {
		PyErr_SetString(PyExc_OSError, "Failed to create IPersistFile instance");
		return NULL;
	}

	if (!target.ptr()) {
		wchar_t buf[2048];
		if (FAILED(persist_file->Load(path.ptr(), 0))) Py_RETURN_NONE;
		if (FAILED(shell_link->GetPath(buf, sizeof(buf), NULL, 0))) Py_RETURN_NONE;
		return Py_BuildValue("u", buf);
	}

	if (FAILED(shell_link->SetPath(target.ptr()))) {
		PyErr_SetString(PyExc_OSError, "Failed to set shortcut target");
		return NULL;
	}

	if (FAILED(shell_link->SetIconLocation(target.ptr(), 0))) {
		PyErr_SetString(PyExc_OSError, "Failed to set shortcut icon");
		return NULL;
	}

	if (description.ptr()) {
		if (FAILED(shell_link->SetDescription(description.ptr()))) {
			PyErr_SetString(PyExc_OSError, "Failed to set shortcut description");
			return NULL;
		}
	}

	if (quoted_args.ptr()) {
		if (FAILED(shell_link->SetArguments(quoted_args.ptr()))) {
			PyErr_SetString(PyExc_OSError, "Failed to set shortcut arguments");
			return NULL;
		}
	}

	if (FAILED(persist_file->Save(path.ptr(), FALSE))) {
		PyErr_SetString(PyExc_OSError, "Failed to save the shortcut");
		return NULL;
	}

	Py_RETURN_NONE;

}

// end extern "C"
}
