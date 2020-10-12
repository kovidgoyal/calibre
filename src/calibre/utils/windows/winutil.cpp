/*
 * winutil.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#include <Windows.h>
#include <processthreadsapi.h>
#include <wininet.h>
#include <Lmcons.h>
#include <combaseapi.h>
#include <locale.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <atlbase.h>  // for CComPtr
#include <Python.h>
#include <versionhelpers.h>

// Handle {{{
typedef enum { NormalHandle, ModuleHandle, IconHandle } WinHandleType;

typedef struct {
    PyObject_HEAD
	void *handle;
	WinHandleType handle_type;
	PyObject *associated_name;
} Handle;

static void
Handle_close_(Handle *self) {
	if (self->handle) {
		switch(self->handle_type) {
			case NormalHandle:
				CloseHandle(self->handle); break;
			case ModuleHandle:
				FreeLibrary((HMODULE)self->handle); break;
			case IconHandle:
				DestroyIcon((HICON)self->handle); break;
		}
		self->handle = NULL;
	}
}

static void
Handle_dealloc(Handle *self) {
	Handle_close_(self);
	Py_CLEAR(self->associated_name);
}

static PyObject*
Handle_as_int(Handle * self) {
	return PyLong_FromVoidPtr(self->handle);
}

static PyObject*
Handle_repr(Handle * self) {
	const char* name = "UNKNOWN";
	switch(self->handle_type) {
		case NormalHandle:
			name = "HANDLE"; break;
		case ModuleHandle:
			name = "HMODULE"; break;
		case IconHandle:
			name = "HICON"; break;
	}
	return PyUnicode_FromFormat("<Win32 handle of type %s at: %p %V>", name, self->handle, self->associated_name, "");
}

static PyNumberMethods HandleNumberMethods = {0};

static PyTypeObject HandleType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static Handle*
Handle_create(void *handle, WinHandleType handle_type = NormalHandle, PyObject *associated_name = NULL) {
	Handle *self = (Handle *) HandleType.tp_alloc(&HandleType, 0);
	if (self != NULL) {
		self->handle = handle;
		self->handle_type = handle_type;
		if (associated_name) { self->associated_name = associated_name; Py_INCREF(associated_name); }
	}
	return self;
}

static int
convert_handle(Handle *obj, void **output) {
	if (Py_TYPE(obj) != &HandleType) {
		PyErr_SetString(PyExc_TypeError, "Handle object expected");
		return 0;
	}
	*output = obj->handle;
	return 1;
}

static PyObject*
set_error_from_handle(Handle *h, int error_code=0) {
	if (h->associated_name) {
		PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, error_code, h->associated_name);
	} else PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, error_code, Handle_repr(h));
	return NULL;
}

static PyObject*
set_error_from_handle(PyObject *args, int error_code=0, Py_ssize_t idx=0) {
	return set_error_from_handle((Handle*)PyTuple_GET_ITEM(args, idx), error_code);
}

static PyObject*
Handle_close(Handle *self) {
	Handle_close_(self);
	Py_RETURN_NONE;
}

#define M(name, args) {#name, (PyCFunction)Handle_##name, args, ""}
static PyMethodDef Handle_methods[] = {
	M(close, METH_NOARGS),
    {NULL, NULL, 0, NULL}
};
#undef M
// }}}

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

// py_to_wchar {{{
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
} // }}}

static PyObject *
winutil_folder_path(PyObject *self, PyObject *args) {
    int res, csidl;
    DWORD flags = SHGFP_TYPE_CURRENT;
    wchar_t wbuf[MAX_PATH] = {0};
    if (!PyArg_ParseTuple(args, "i|k", &csidl, &flags)) return NULL;

    res = SHGetFolderPathW(NULL, csidl, NULL, flags, wbuf);
    if (res != S_OK) {
        if (res == E_FAIL) PyErr_SetString(PyExc_ValueError, "Folder does not exist.");
        PyErr_SetString(PyExc_ValueError, "Folder not valid");
        return NULL;
    }
    return PyUnicode_FromWideChar(wbuf, -1);
}

static PyObject *
winutil_internet_connected(PyObject *self, PyObject *args) {
    DWORD flags;
    BOOL ans = InternetGetConnectedState(&flags, 0);
    if (ans) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyObject *
winutil_prepare_for_restart(PyObject *self, PyObject *args) {
    FILE *f1 = NULL, *f2 = NULL;
    if (stdout != NULL) fclose(stdout);
    if (stderr != NULL) fclose(stderr);
    _wfreopen_s(&f1, L"NUL", L"a+t", stdout);
    _wfreopen_s(&f2, L"NUL", L"a+t", stderr);
    Py_RETURN_NONE;
}

static PyObject *
winutil_get_max_stdio(PyObject *self, PyObject *args) {
    return Py_BuildValue("i", _getmaxstdio());
}


static PyObject *
winutil_set_max_stdio(PyObject *self, PyObject *args) {
    int num = 0;
    if (!PyArg_ParseTuple(args, "i", &num)) return NULL;
    if (_setmaxstdio(num) == -1) return PyErr_SetFromErrno(PyExc_ValueError);
    Py_RETURN_NONE;
}

static PyObject *
winutil_username(PyObject *self) {
    wchar_t buf[UNLEN + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetUserName(buf, &sz)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, -1);
}

static PyObject *
winutil_temp_path(PyObject *self) {
    wchar_t buf[MAX_PATH + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetTempPath(sz, buf)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, -1);
}


static PyObject *
winutil_locale_name(PyObject *self) {
    wchar_t buf[LOCALE_NAME_MAX_LENGTH + 1] = {0};
    if (!GetUserDefaultLocaleName(buf, sizeof(buf)/sizeof(buf[0]))) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, -1);
}


static PyObject *
winutil_localeconv(PyObject *self) {
    struct lconv *d = localeconv();
#define W(name) #name, d->_W_##name
    return Py_BuildValue(
        "{su su su su su su su su}",
        W(decimal_point), W(thousands_sep), W(int_curr_symbol), W(currency_symbol),
        W(mon_decimal_point), W(mon_thousands_sep), W(positive_sign), W(negative_sign)
    );
#undef W
}


static PyObject*
winutil_move_file(PyObject *self, PyObject *args) {
    wchar_raii a, b;
    unsigned int flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH;
    if (!PyArg_ParseTuple(args, "O&O&|I", py_to_wchar_no_none, &a, py_to_wchar_no_none, &b, &flags)) return NULL;
    if (!MoveFileExW(a.ptr(), b.ptr(), flags))
        return PyErr_SetExcFromWindowsErrWithFilenameObjects(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    Py_RETURN_NONE;
}

static PyObject*
winutil_get_disk_free_space(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &path)) return NULL;
    ULARGE_INTEGER bytes_available_to_caller, total_bytes, total_free_bytes;
    if (!GetDiskFreeSpaceEx(path.ptr(), &bytes_available_to_caller, &total_bytes, &total_free_bytes)) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return Py_BuildValue("KKK", bytes_available_to_caller.QuadPart, total_bytes.QuadPart, total_free_bytes.QuadPart);
}

static PyObject*
winutil_read_file(PyObject *self, PyObject *args) {
    unsigned long chunk_size = 16 * 1024;
	HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&|k", convert_handle, &handle, &chunk_size)) return NULL;
    PyObject *ans = PyBytes_FromStringAndSize(NULL, chunk_size);
    if (!ans) return PyErr_NoMemory();
    DWORD bytes_read;
    BOOL ok;
    Py_BEGIN_ALLOW_THREADS;
    ok = ReadFile(handle, PyBytes_AS_STRING(ans), chunk_size, &bytes_read, NULL);
    Py_END_ALLOW_THREADS;
    if (!ok) {
        Py_DECREF(ans);
        return set_error_from_handle(args);
    }
    if (bytes_read < chunk_size) _PyBytes_Resize(&ans, bytes_read);
    return ans;
}

static PyObject*
winutil_read_directory_changes(PyObject *self, PyObject *args) {
    PyObject *buffer; int watch_subtree; unsigned long filter;
	HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&O!pk", convert_handle, &handle, &PyBytes_Type, &buffer, &watch_subtree, &filter)) return NULL;
    DWORD bytes_returned;
    BOOL ok;
    Py_BEGIN_ALLOW_THREADS;
    ok = ReadDirectoryChangesW(handle, PyBytes_AS_STRING(buffer), (DWORD)PyBytes_GET_SIZE(buffer), watch_subtree, filter, &bytes_returned, NULL, NULL);
    Py_END_ALLOW_THREADS;
    if (!ok) return set_error_from_handle(args);
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

static PyObject*
winutil_get_file_size(PyObject *self, PyObject *args) {
	HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&", convert_handle, &handle)) return NULL;
    LARGE_INTEGER ans = {0};
    if (!GetFileSizeEx(handle, &ans)) return set_error_from_handle(args);
    return PyLong_FromLongLong(ans.QuadPart);
}

static PyObject*
winutil_set_file_pointer(PyObject *self, PyObject *args) {
    unsigned long move_method = FILE_BEGIN;
	HANDLE handle;
    LARGE_INTEGER pos = {0};
    if (!PyArg_ParseTuple(args, "O&L|k", convert_handle, &handle, &pos.QuadPart, &move_method)) return NULL;
    LARGE_INTEGER ans = {0};
    if (!SetFilePointerEx(handle, pos, &ans, move_method)) return set_error_from_handle(args);
    return PyLong_FromLongLong(ans.QuadPart);
}

static PyObject*
winutil_create_file(PyObject *self, PyObject *args) {
	wchar_raii path;
    unsigned long desired_access, share_mode, creation_disposition, flags_and_attributes;
	if (!PyArg_ParseTuple(args, "O&kkkk", py_to_wchar_no_none, &path, &desired_access, &share_mode, &creation_disposition, &flags_and_attributes)) return NULL;
    HANDLE h = CreateFileW(
        path.ptr(), desired_access, share_mode, NULL, creation_disposition, flags_and_attributes, NULL
    );
    if (h == INVALID_HANDLE_VALUE) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return (PyObject*)Handle_create(h, NormalHandle, PyTuple_GET_ITEM(args, 0));
}

static PyObject*
winutil_delete_file(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
    if (!DeleteFileW(path.ptr())) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    Py_RETURN_NONE;
}

static PyObject*
winutil_create_hard_link(PyObject *self, PyObject *args) {
	wchar_raii path, existing_path;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar_no_none, &path, py_to_wchar_no_none, &existing_path)) return NULL;
    if (!CreateHardLinkW(path.ptr(), existing_path.ptr(), NULL)) return PyErr_SetExcFromWindowsErrWithFilenameObjects(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    Py_RETURN_NONE;
}


static PyObject*
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

static PyObject*
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

static PyObject*
winutil_set_file_attributes(PyObject *self, PyObject *args) {
	wchar_raii path; unsigned long attrs;
	if (!PyArg_ParseTuple(args, "O&k", py_to_wchar_no_none, &path, &attrs)) return NULL;
    if (!SetFileAttributes(path.ptr(), attrs)) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    Py_RETURN_NONE;
}


static PyObject *
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


static PyObject *
winutil_file_association(PyObject *self, PyObject *args) {
	wchar_t buf[2048];
	wchar_raii ext;
	DWORD sz = sizeof(buf);
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &ext)) return NULL;
	HRESULT hr = AssocQueryStringW(0, ASSOCSTR_EXECUTABLE, ext.ptr(), NULL, buf, &sz);
	if (!SUCCEEDED(hr) || sz < 1) Py_RETURN_NONE;
	return Py_BuildValue("u", buf);
}

static PyObject *
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

static PyObject *
winutil_notify_associations_changed(PyObject *self, PyObject *args) {
	SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_DWORD | SHCNF_FLUSH, NULL, NULL);
	Py_RETURN_NONE;
}

static PyObject *
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

static PyObject *
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

static PyObject *
get_dll_directory(PyObject *self, PyObject *args) {
    DWORD sz = GetDllDirectory(0, NULL) * 2;
    wchar_t *buf = (wchar_t*)PyMem_Malloc(sz);
    if (!buf) return PyErr_NoMemory();
    GetDllDirectory(sz - 1, buf);
    buf[sz - 1] = 0;
    PyObject *ans = PyUnicode_FromWideChar(buf, -1);
    PyMem_Free(buf);
    return ans;
}

static PyObject *
create_named_pipe(PyObject *self, PyObject *args) {
    wchar_raii name;
    unsigned long open_mode, pipe_mode, max_instances, out_buffer_size, in_buffer_size, default_time_out;
    if (!PyArg_ParseTuple(args, "O&kkkkkk", py_to_wchar_no_none, &name, &open_mode, &pipe_mode, &max_instances, &out_buffer_size, &in_buffer_size, &default_time_out)) return NULL;
    HANDLE h = CreateNamedPipeW(name.ptr(), open_mode, pipe_mode, max_instances, out_buffer_size, in_buffer_size, default_time_out, NULL);
    if (h == INVALID_HANDLE_VALUE) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return (PyObject*)Handle_create(h, NormalHandle, PyTuple_GET_ITEM(args, 0));
}

static PyObject *
set_handle_information(PyObject *self, PyObject *args) {
    unsigned long mask, flags;
	HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&kk", convert_handle, &handle, &mask, &flags)) return NULL;
    if (!SetHandleInformation(handle, mask, flags)) return set_error_from_handle(args);
    Py_RETURN_NONE;
}

static PyObject *
get_long_path_name(PyObject *self, PyObject *args) {
    wchar_raii path;
    if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
    DWORD sz = GetLongPathNameW(path.ptr(), NULL, 0) * 2;
    if (!sz) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    wchar_t *buf = (wchar_t*) PyMem_Malloc(sz);
    if (!buf) return PyErr_NoMemory();
    if (!GetLongPathNameW(path.ptr(), buf, sz-1)) {
        PyMem_Free(buf);
        return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    }
    buf[sz-1] = 0;
    PyObject *ans = PyUnicode_FromWideChar(buf, -1);
    PyMem_Free(buf);
    return ans;
}

static PyObject *
get_process_times(PyObject *self, PyObject *pid) {
    HANDLE h = INVALID_HANDLE_VALUE;
    if (pid == Py_None) {
        h = GetCurrentProcess();
    } else if (PyLong_Check(pid)) {
        h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, PyLong_AsUnsignedLong(pid));
        if (h == NULL) return PyErr_SetFromWindowsErr(0);
    } else {
        PyErr_SetString(PyExc_TypeError, "process pid must be None or an integer");
        return NULL;
    }
    FILETIME creation, exit, kernel, user;
    BOOL ok = GetProcessTimes(h, &creation, &exit, &kernel, &user);
    int ec = GetLastError();
    CloseHandle(h);
    if (!ok) return PyErr_SetFromWindowsErr(ec);
#define T(ft) ((unsigned long long)(ft.dwHighDateTime) << 32 | ft.dwLowDateTime)
    return Py_BuildValue("KKKK", T(creation), T(exit), T(kernel), T(user));
#undef T
}

static PyObject*
get_async_key_state(PyObject *self, PyObject *args) {
	int key;
	if (!PyArg_ParseTuple(args, "i", &key)) return NULL;
	long state = GetAsyncKeyState(key);
	return PyLong_FromLong(state);
}

static PyObject*
get_handle_information(PyObject *self, PyObject *args) {
	HANDLE handle;
	if (!PyArg_ParseTuple(args, "O&", convert_handle, &handle)) return NULL;
	DWORD ans;
	if (!GetHandleInformation(handle, &ans)) return set_error_from_handle(args);
	return PyLong_FromUnsignedLong(ans);
}

static PyObject*
get_last_error(PyObject *self, PyObject *args) {
	return PyLong_FromLong(GetLastError());
}

static PyObject*
load_library(PyObject *self, PyObject *args) {
	unsigned long flags = 0;
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&|k", py_to_wchar_no_none, &path, &flags)) return NULL;
	HMODULE h = LoadLibraryEx(path.ptr(), NULL, flags);
	if (h == NULL) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
	return (PyObject*)Handle_create(h, ModuleHandle, PyTuple_GET_ITEM(args, 0));
}

// Boilerplate  {{{
static const char winutil_doc[] = "Defines utility methods to interface with windows.";

#define M(name, args) { #name, name, args, ""}
static PyMethodDef winutil_methods[] = {
    M(get_dll_directory, METH_NOARGS),
    M(get_async_key_state, METH_VARARGS),
    M(create_named_pipe, METH_VARARGS),
    M(set_handle_information, METH_VARARGS),
    M(get_long_path_name, METH_VARARGS),
    M(get_process_times, METH_O),
	M(get_handle_information, METH_VARARGS),
	M(get_last_error, METH_NOARGS),
	M(load_library, METH_VARARGS),

    {"special_folder_path", winutil_folder_path, METH_VARARGS,
    "special_folder_path(csidl_id) -> path\n\n"
            "Get paths to common system folders. "
            "See windows documentation of SHGetFolderPath. "
            "The paths are returned as unicode objects. csidl_id should be one "
            "of the symbolic constants defined in this module. You can also OR "
            "a symbolic constant with CSIDL_FLAG_CREATE to force the operating "
            "system to create a folder if it does not exist."},

    {"internet_connected", winutil_internet_connected, METH_VARARGS,
        "internet_connected()\n\nReturn True if there is an active internet connection"
    },

    {"prepare_for_restart", winutil_prepare_for_restart, METH_VARARGS,
        "prepare_for_restart()\n\nRedirect output streams so that the child process does not lock the temp files"
    },

    {"getmaxstdio", winutil_get_max_stdio, METH_VARARGS,
        "getmaxstdio()\n\nThe maximum number of open file handles."
    },

    {"setmaxstdio", winutil_set_max_stdio, METH_VARARGS,
        "setmaxstdio(num)\n\nSet the maximum number of open file handles."
    },

    {"username", (PyCFunction)winutil_username, METH_NOARGS,
        "username()\n\nGet the current username as a unicode string."
    },

    {"temp_path", (PyCFunction)winutil_temp_path, METH_NOARGS,
        "temp_path()\n\nGet the current temporary dir as a unicode string."
    },

    {"locale_name", (PyCFunction)winutil_locale_name, METH_NOARGS,
        "locale_name()\n\nGet the current locale name as a unicode string."
    },

    {"localeconv", (PyCFunction)winutil_localeconv, METH_NOARGS,
        "localeconv()\n\nGet the locale conventions as unicode strings."
    },

    {"move_file", (PyCFunction)winutil_move_file, METH_VARARGS,
        "move_file()\n\nRename the specified file."
    },

    {"add_to_recent_docs", (PyCFunction)winutil_add_to_recent_docs, METH_VARARGS,
        "add_to_recent_docs()\n\nAdd a path to the recent documents list"
    },

    {"file_association", (PyCFunction)winutil_file_association, METH_VARARGS,
        "file_association()\n\nGet the executable associated with the given file extension"
    },

    {"friendly_name", (PyCFunction)winutil_friendly_name, METH_VARARGS,
        "friendly_name()\n\nGet the friendly name for the specified prog_id/exe"
    },

    {"notify_associations_changed", (PyCFunction)winutil_notify_associations_changed, METH_VARARGS,
        "notify_associations_changed()\n\nNotify the OS that file associations have changed"
    },

    {"move_to_trash", (PyCFunction)winutil_move_to_trash, METH_VARARGS,
        "move_to_trash()\n\nMove the specified path to trash"
    },

    {"manage_shortcut", (PyCFunction)winutil_manage_shortcut, METH_VARARGS,
        "manage_shortcut()\n\nManage a shortcut"
    },

    {"get_file_id", (PyCFunction)winutil_get_file_id, METH_VARARGS,
        "get_file_id(path)\n\nGet the windows file id (volume_num, file_index_high, file_index_low)"
    },

    {"create_file", (PyCFunction)winutil_create_file, METH_VARARGS,
        "create_file(path, desired_access, share_mode, creation_disposition, flags_and_attributes)\n\nWrapper for CreateFile"
    },

    {"get_file_size", (PyCFunction)winutil_get_file_size, METH_VARARGS,
        "get_file_size(handle)\n\nWrapper for GetFileSizeEx"
    },

    {"set_file_pointer", (PyCFunction)winutil_set_file_pointer, METH_VARARGS,
        "set_file_pointer(handle, pos, method=FILE_BEGIN)\n\nWrapper for SetFilePointer"
    },

    {"read_file", (PyCFunction)winutil_read_file, METH_VARARGS,
        "set_file_pointer(handle, chunk_size=16KB)\n\nWrapper for ReadFile"
    },

    {"get_disk_free_space", (PyCFunction)winutil_get_disk_free_space, METH_VARARGS,
        "get_disk_free_space(path)\n\nWrapper for GetDiskFreeSpaceEx"
    },

    {"delete_file", (PyCFunction)winutil_delete_file, METH_VARARGS,
        "delete_file(path)\n\nWrapper for DeleteFile"
    },

    {"create_hard_link", (PyCFunction)winutil_create_hard_link, METH_VARARGS,
        "create_hard_link(path, existing_path)\n\nWrapper for CreateHardLink"
    },

    {"nlinks", (PyCFunction)winutil_nlinks, METH_VARARGS,
        "nlinks(path)\n\nReturn the number of hardlinks"
    },

    {"set_file_attributes", (PyCFunction)winutil_set_file_attributes, METH_VARARGS,
        "set_file_attributes(path, attrs)\n\nWrapper for SetFileAttributes"
    },

    {"move_file", (PyCFunction)winutil_move_file, METH_VARARGS,
        "move_file(a, b, flags)\n\nWrapper for MoveFileEx"
    },

    {"read_directory_changes", (PyCFunction)winutil_read_directory_changes, METH_VARARGS,
        "read_directory_changes(handle, buffer, subtree, flags)\n\nWrapper for ReadDirectoryChangesW"
    },

    {NULL, NULL, 0, NULL}
};
#undef M

static struct PyModuleDef winutil_module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "winutil",
    /* m_doc      */ winutil_doc,
    /* m_size     */ -1,
    /* m_methods  */ winutil_methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};



extern "C" {

CALIBRE_MODINIT_FUNC PyInit_winutil(void) {
	HandleNumberMethods.nb_int = (unaryfunc)Handle_as_int;
    HandleType.tp_name = "winutil.Handle";
    HandleType.tp_doc = "Wrappers for Win32 handles that free the handle on delete automatically";
    HandleType.tp_basicsize = sizeof(Handle);
    HandleType.tp_itemsize = 0;
    HandleType.tp_flags = Py_TPFLAGS_DEFAULT;
	HandleType.tp_repr = (reprfunc)Handle_repr;
	HandleType.tp_as_number = &HandleNumberMethods;
	HandleType.tp_str = (reprfunc)Handle_repr;
    HandleType.tp_new = PyType_GenericNew;
    HandleType.tp_methods = Handle_methods;
	HandleType.tp_dealloc = (destructor)Handle_dealloc;
	if (PyType_Ready(&HandleType) < 0) return NULL;

    PyObject *m = PyModule_Create(&winutil_module);

    if (m == NULL) return NULL;

	Py_INCREF(&HandleType);
    if (PyModule_AddObject(m, "Handle", (PyObject *) &HandleType) < 0) {
        Py_DECREF(&HandleType);
        Py_DECREF(m);
        return NULL;
    }
    PyModule_AddIntConstant(m, "CSIDL_ADMINTOOLS", CSIDL_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_APPDATA", CSIDL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_ADMINTOOLS", CSIDL_COMMON_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_APPDATA", CSIDL_COMMON_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_DOCUMENTS", CSIDL_COMMON_DOCUMENTS);
    PyModule_AddIntConstant(m, "CSIDL_COOKIES", CSIDL_COOKIES);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_CREATE", CSIDL_FLAG_CREATE);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_DONT_VERIFY", CSIDL_FLAG_DONT_VERIFY);
    PyModule_AddIntConstant(m, "CSIDL_FONTS", CSIDL_FONTS);
    PyModule_AddIntConstant(m, "CSIDL_HISTORY", CSIDL_HISTORY);
    PyModule_AddIntConstant(m, "CSIDL_INTERNET_CACHE", CSIDL_INTERNET_CACHE);
    PyModule_AddIntConstant(m, "CSIDL_LOCAL_APPDATA", CSIDL_LOCAL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_MYPICTURES", CSIDL_MYPICTURES);
    PyModule_AddIntConstant(m, "CSIDL_PERSONAL", CSIDL_PERSONAL);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES", CSIDL_PROGRAM_FILES);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES_COMMON", CSIDL_PROGRAM_FILES_COMMON);
    PyModule_AddIntConstant(m, "CSIDL_SYSTEM", CSIDL_SYSTEM);
    PyModule_AddIntConstant(m, "CSIDL_WINDOWS", CSIDL_WINDOWS);
    PyModule_AddIntConstant(m, "CSIDL_PROFILE", CSIDL_PROFILE);
    PyModule_AddIntConstant(m, "CSIDL_STARTUP", CSIDL_STARTUP);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_STARTUP", CSIDL_COMMON_STARTUP);
    PyModule_AddIntConstant(m, "CREATE_NEW", CREATE_NEW);
    PyModule_AddIntConstant(m, "CREATE_ALWAYS", CREATE_ALWAYS);
    PyModule_AddIntConstant(m, "OPEN_EXISTING", OPEN_EXISTING);
    PyModule_AddIntConstant(m, "OPEN_ALWAYS", OPEN_ALWAYS);
    PyModule_AddIntConstant(m, "TRUNCATE_EXISTING", TRUNCATE_EXISTING);
    PyModule_AddIntConstant(m, "FILE_SHARE_READ", FILE_SHARE_READ);
    PyModule_AddIntConstant(m, "FILE_SHARE_WRITE", FILE_SHARE_WRITE);
    PyModule_AddIntConstant(m, "FILE_SHARE_DELETE", FILE_SHARE_DELETE);
    PyModule_AddIntConstant(m, "FILE_SHARE_VALID_FLAGS", FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_READONLY", FILE_ATTRIBUTE_READONLY);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_NORMAL", FILE_ATTRIBUTE_NORMAL);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_TEMPORARY", FILE_ATTRIBUTE_TEMPORARY);
    PyModule_AddIntConstant(m, "FILE_FLAG_DELETE_ON_CLOSE", FILE_FLAG_DELETE_ON_CLOSE);
    PyModule_AddIntConstant(m, "FILE_FLAG_SEQUENTIAL_SCAN", FILE_FLAG_SEQUENTIAL_SCAN);
    PyModule_AddIntConstant(m, "FILE_FLAG_RANDOM_ACCESS", FILE_FLAG_RANDOM_ACCESS);
    PyModule_AddIntConstant(m, "GENERIC_READ", GENERIC_READ);
    PyModule_AddIntConstant(m, "GENERIC_WRITE", GENERIC_WRITE);
    PyModule_AddIntConstant(m, "DELETE", DELETE);
    PyModule_AddIntConstant(m, "FILE_BEGIN", FILE_BEGIN);
    PyModule_AddIntConstant(m, "FILE_CURRENT", FILE_CURRENT);
    PyModule_AddIntConstant(m, "FILE_END", FILE_END);
    PyModule_AddIntConstant(m, "MOVEFILE_COPY_ALLOWED", MOVEFILE_COPY_ALLOWED);
    PyModule_AddIntConstant(m, "MOVEFILE_CREATE_HARDLINK", MOVEFILE_CREATE_HARDLINK);
    PyModule_AddIntConstant(m, "MOVEFILE_DELAY_UNTIL_REBOOT", MOVEFILE_DELAY_UNTIL_REBOOT);
    PyModule_AddIntConstant(m, "MOVEFILE_FAIL_IF_NOT_TRACKABLE", MOVEFILE_FAIL_IF_NOT_TRACKABLE);
    PyModule_AddIntConstant(m, "MOVEFILE_REPLACE_EXISTING", MOVEFILE_REPLACE_EXISTING);
    PyModule_AddIntConstant(m, "MOVEFILE_WRITE_THROUGH", MOVEFILE_WRITE_THROUGH);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_FILE_NAME", FILE_NOTIFY_CHANGE_FILE_NAME);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_DIR_NAME", FILE_NOTIFY_CHANGE_DIR_NAME);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_ATTRIBUTES", FILE_NOTIFY_CHANGE_ATTRIBUTES);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_SIZE", FILE_NOTIFY_CHANGE_SIZE);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_LAST_WRITE", FILE_NOTIFY_CHANGE_LAST_WRITE);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_LAST_ACCESS", FILE_NOTIFY_CHANGE_LAST_ACCESS);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_CREATION", FILE_NOTIFY_CHANGE_CREATION);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_SECURITY", FILE_NOTIFY_CHANGE_SECURITY);
    PyModule_AddIntConstant(m, "FILE_ACTION_ADDED", FILE_ACTION_ADDED);
    PyModule_AddIntConstant(m, "FILE_ACTION_REMOVED", FILE_ACTION_REMOVED);
    PyModule_AddIntConstant(m, "FILE_ACTION_MODIFIED", FILE_ACTION_MODIFIED);
    PyModule_AddIntConstant(m, "FILE_ACTION_RENAMED_OLD_NAME", FILE_ACTION_RENAMED_OLD_NAME);
    PyModule_AddIntConstant(m, "FILE_ACTION_RENAMED_NEW_NAME", FILE_ACTION_RENAMED_NEW_NAME);
    PyModule_AddIntConstant(m, "FILE_LIST_DIRECTORY", FILE_LIST_DIRECTORY);
    PyModule_AddIntConstant(m, "FILE_FLAG_BACKUP_SEMANTICS", FILE_FLAG_BACKUP_SEMANTICS);
    PyModule_AddIntConstant(m, "SHGFP_TYPE_CURRENT", SHGFP_TYPE_CURRENT);
    PyModule_AddIntConstant(m, "SHGFP_TYPE_DEFAULT", SHGFP_TYPE_DEFAULT);
    PyModule_AddIntConstant(m, "PIPE_ACCESS_INBOUND", PIPE_ACCESS_INBOUND);
    PyModule_AddIntConstant(m, "FILE_FLAG_FIRST_PIPE_INSTANCE", FILE_FLAG_FIRST_PIPE_INSTANCE);
    PyModule_AddIntConstant(m, "PIPE_TYPE_BYTE", PIPE_TYPE_BYTE);
    PyModule_AddIntConstant(m, "PIPE_READMODE_BYTE", PIPE_READMODE_BYTE);
    PyModule_AddIntConstant(m, "PIPE_WAIT", PIPE_WAIT);
    PyModule_AddIntConstant(m, "PIPE_REJECT_REMOTE_CLIENTS", PIPE_REJECT_REMOTE_CLIENTS);
    PyModule_AddIntConstant(m, "HANDLE_FLAG_INHERIT", HANDLE_FLAG_INHERIT);
    PyModule_AddIntConstant(m, "HANDLE_FLAG_PROTECT_FROM_CLOSE", HANDLE_FLAG_PROTECT_FROM_CLOSE);
    PyModule_AddIntConstant(m, "VK_RMENU", VK_RMENU);
    PyModule_AddIntConstant(m, "DONT_RESOLVE_DLL_REFERENCES", DONT_RESOLVE_DLL_REFERENCES);
    PyModule_AddIntConstant(m, "LOAD_LIBRARY_AS_DATAFILE", LOAD_LIBRARY_AS_DATAFILE);
    PyModule_AddIntConstant(m, "LOAD_LIBRARY_AS_IMAGE_RESOURCE", LOAD_LIBRARY_AS_IMAGE_RESOURCE);

    return m;
}
// end extern "C"
} // }}}
