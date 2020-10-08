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

class handle_raii {  // {{{
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

static inline int
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

static inline int
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

static PyObject*
set_error_from_file_handle(HANDLE h) {
    int error_code = GetLastError();
    wchar_t buf[4096] = {0};
    if (GetFinalPathNameByHandleW(h, buf, 4095, FILE_NAME_OPENED)) {
        PyObject *fname = PyUnicode_FromWideChar(buf, -1);
        if (fname) {
            PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, error_code, fname);
            Py_DECREF(fname);
            return NULL;
        }
    }
    return PyErr_SetFromWindowsErr(error_code);
}

extern "C" {

PyObject*
winutil_move_file(PyObject *self, PyObject *args) {
    wchar_raii a, b;
    unsigned int flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH;
    if (!PyArg_ParseTuple(args, "O&O&|I", py_to_wchar_no_none, &a, py_to_wchar_no_none, &b, &flags)) return NULL;
    if (!MoveFileExW(a.ptr(), b.ptr(), flags))
        return PyErr_SetExcFromWindowsErrWithFilenameObjects(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    Py_RETURN_NONE;
}

PyObject*
winutil_get_disk_free_space(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &path)) return NULL;
    ULARGE_INTEGER bytes_available_to_caller, total_bytes, total_free_bytes;
    if (!GetDiskFreeSpaceEx(path.ptr(), &bytes_available_to_caller, &total_bytes, &total_free_bytes)) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return Py_BuildValue("KKK", bytes_available_to_caller.QuadPart, total_bytes.QuadPart, total_free_bytes.QuadPart);
}

PyObject*
winutil_read_file(PyObject *self, PyObject *args) {
    unsigned long chunk_size = 16 * 1024;
    PyObject *handle;
    if (!PyArg_ParseTuple(args, "O!|k", &PyLong_Type, &handle, &chunk_size)) return NULL;
    PyObject *ans = PyBytes_FromStringAndSize(NULL, chunk_size);
    if (!ans) return PyErr_NoMemory();
    DWORD bytes_read;
    if (!ReadFile(PyLong_AsVoidPtr(handle), PyBytes_AS_STRING(ans), chunk_size, &bytes_read, NULL)) {
        Py_DECREF(ans);
        return set_error_from_file_handle(PyLong_AsVoidPtr(handle));
    }
    if (bytes_read < chunk_size) _PyBytes_Resize(&ans, bytes_read);
    return ans;
}

PyObject*
winutil_read_directory_changes(PyObject *self, PyObject *args) {
    PyObject *buffer, *handle; int watch_subtree; unsigned long filter;
    if (!PyArg_ParseTuple(args, "O!O!pk", &PyLong_Type, &handle, &PyBytes_Type, &buffer, &watch_subtree, &filter)) return NULL;
    DWORD bytes_returned;
    BOOL ok;
    Py_BEGIN_ALLOW_THREADS;
    ok = ReadDirectoryChangesW(PyLong_AsVoidPtr(handle), PyBytes_AS_STRING(buffer), (DWORD)PyBytes_GET_SIZE(buffer), watch_subtree, filter, &bytes_returned, NULL, NULL);
    Py_END_ALLOW_THREADS;
    if (!ok) return set_error_from_file_handle(PyLong_AsVoidPtr(handle));
    PFILE_NOTIFY_INFORMATION p;
    size_t offset = 0;
    PyObject *ans = PyList_New(0);
    if (!ans) return NULL;
    if (bytes_returned) {
        do {
            p = (PFILE_NOTIFY_INFORMATION)(PyBytes_AS_STRING(buffer) + offset);
            offset += p->NextEntryOffset;
            if (p->FileNameLength) {
                PyObject *temp = Py_BuildValue("ku#", p->Action, p->FileName, p->FileNameLength / sizeof(wchar_t));
                if (!temp) { Py_DECREF(ans); return NULL; }
                int ret = PyList_Append(ans, temp);
                Py_DECREF(temp);
                if (ret != 0) { Py_DECREF(ans); return NULL; }
            }
        } while(p->NextEntryOffset);
    } else {
        Py_CLEAR(ans);
        PyErr_SetString(PyExc_OverflowError, "the change events buffer overflowed, something has changed");
    }
    return ans;
}

PyObject*
winutil_get_file_size(PyObject *self, PyObject *pyhandle) {
    if (!PyLong_Check(pyhandle)) { PyErr_SetString(PyExc_TypeError, "handle must be an int"); return NULL; }
    LARGE_INTEGER ans = {0};
    if (!GetFileSizeEx(PyLong_AsVoidPtr(pyhandle), &ans)) return set_error_from_file_handle(PyLong_AsVoidPtr(pyhandle));
    return PyLong_FromLongLong(ans.QuadPart);
}

PyObject*
winutil_set_file_pointer(PyObject *self, PyObject *args) {
    PyObject *handle; unsigned long move_method = FILE_BEGIN;
    LARGE_INTEGER pos = {0};
    if (!PyArg_ParseTuple(args, "O!L|k", &PyLong_Type, &handle, &pos.QuadPart, &move_method)) return NULL;
    LARGE_INTEGER ans = {0};
    if (!SetFilePointerEx(PyLong_AsVoidPtr(handle), pos, &ans, move_method)) return set_error_from_file_handle(PyLong_AsVoidPtr(handle));
    return PyLong_FromLongLong(ans.QuadPart);
}

PyObject*
winutil_create_file(PyObject *self, PyObject *args) {
	wchar_raii path;
    unsigned long desired_access, share_mode, creation_disposition, flags_and_attributes;
	if (!PyArg_ParseTuple(args, "O&kkkk", py_to_wchar_no_none, &path, &desired_access, &share_mode, &creation_disposition, &flags_and_attributes)) return NULL;
    HANDLE h = CreateFileW(
        path.ptr(), desired_access, share_mode, NULL, creation_disposition, flags_and_attributes, NULL
    );
    if (h == INVALID_HANDLE_VALUE) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return PyLong_FromVoidPtr(h);
}

PyObject*
winutil_delete_file(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
    if (!DeleteFileW(path.ptr())) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    Py_RETURN_NONE;
}

PyObject*
winutil_create_hard_link(PyObject *self, PyObject *args) {
	wchar_raii path, existing_path;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar_no_none, &path, py_to_wchar_no_none, &existing_path)) return NULL;
    if (!CreateHardLinkW(path.ptr(), existing_path.ptr(), NULL)) return PyErr_SetExcFromWindowsErrWithFilenameObjects(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    Py_RETURN_NONE;
}


PyObject*
winutil_get_file_id(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
	if (path.ptr()) {
		handle_raii file_handle(CreateFileW(path.ptr(), 0, 0, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL));
		if (!file_handle) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
		BY_HANDLE_FILE_INFORMATION info = {0};
		BOOL ok = GetFileInformationByHandle(file_handle.ptr(), &info);
		if (!ok) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
		unsigned long volnum = info.dwVolumeSerialNumber, index_high = info.nFileIndexHigh, index_low = info.nFileIndexLow;
		return Py_BuildValue("kkk", volnum, index_high, index_low);
	}
	Py_RETURN_NONE;
}

PyObject*
winutil_nlinks(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
    handle_raii file_handle(CreateFileW(path.ptr(), 0, 0, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL));
    if (!file_handle) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    BY_HANDLE_FILE_INFORMATION info = {0};
    BOOL ok = GetFileInformationByHandle(file_handle.ptr(), &info);
    if (!ok) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    unsigned long ans = info.nNumberOfLinks;
    return PyLong_FromUnsignedLong(ans);
}

PyObject*
winutil_set_file_attributes(PyObject *self, PyObject *args) {
	wchar_raii path; unsigned long attrs;
	if (!PyArg_ParseTuple(args, "O&k", py_to_wchar_no_none, &path, &attrs)) return NULL;
    if (!SetFileAttributes(path.ptr(), attrs)) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    Py_RETURN_NONE;
}


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
