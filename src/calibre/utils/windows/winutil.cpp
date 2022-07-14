/*
 * winutil.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "common.h"
#include <processthreadsapi.h>
#include <wininet.h>
#include <Lmcons.h>
#include <combaseapi.h>
#include <locale.h>
#include <shlobj.h>
#include <shlguid.h>
#include <shellapi.h>
#include <shlwapi.h>
#include <commoncontrols.h>
#include <comip.h>
#include <comdef.h>
#include <atlbase.h>  // for CComPtr
#include <versionhelpers.h>

// GUID {{{
typedef struct {
    PyObject_HEAD
	GUID guid;
} PyGUID;

static PyTypeObject PyGUIDType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static PyObject*
create_guid(const wchar_t *str) {
	PyGUID *self = (PyGUID *) PyGUIDType.tp_alloc(&PyGUIDType, 0);
	if (self) {
		HRESULT hr = IIDFromString(str, &self->guid);
		if (FAILED(hr)) return error_from_hresult(hr);
	}
	return (PyObject*)self;
}

static PyObject*
create_guid(const GUID &g) {
	PyGUID *self = (PyGUID *) PyGUIDType.tp_alloc(&PyGUIDType, 0);
	if (self) self->guid = g;
	return (PyObject*)self;
}

static PyObject*
PyGUID_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
	wchar_raii s;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &s)) return NULL;
	return create_guid(s.ptr());
}

static void
PyGUID_dealloc(PyGUID *self) { }

static PyObject*
PyGUID_repr(PyGUID *self) {
	com_wchar_raii s;
	HRESULT hr = StringFromIID(self->guid, s.unsafe_address());
	if (FAILED(hr)) return error_from_hresult(hr);
	return PyUnicode_FromWideChar(s.ptr(), -1);
}

#define M(name, args) {#name, (PyCFunction)Handle_##name, args, ""}
static PyMethodDef PyGUID_methods[] = {
    {NULL, NULL, 0, NULL}
};
#undef M

// }}}

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
Handle_detach(Handle *self) {
	void *h = self->handle;
	self->handle = NULL;
	return PyLong_FromVoidPtr(h);
}

static PyObject*
Handle_as_int(Handle * self) {
	return PyLong_FromVoidPtr(self->handle);
}

static int
Handle_as_bool(Handle *self) {
	return self->handle != NULL;
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

static PyObject *
Handle_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
	PyObject *h = NULL, *name = NULL;
	int htype = NormalHandle;
    if (!PyArg_ParseTuple(args, "|O!iU", &PyLong_Type, &h, &htype, &name)) return NULL;
	switch(htype) {
		case NormalHandle:
		case IconHandle:
		case ModuleHandle:
			break;
		default:
			PyErr_Format(PyExc_TypeError, "unknown handle type: %d", type);
			return NULL;
	}
	Handle *self = (Handle *) HandleType.tp_alloc(type, 0);
	if (self) {
		self->handle = h ? PyLong_AsVoidPtr(h) : NULL;
		self->handle_type = static_cast<WinHandleType>(htype);
		self->associated_name = name;
	}
	return (PyObject*)self;
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
	M(detach, METH_NOARGS),
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

class scoped_com_initializer {  // {{{
	public:
		scoped_com_initializer() : m_succeded(false) { if (SUCCEEDED(CoInitialize(NULL))) m_succeded = true; }
		~scoped_com_initializer() { CoUninitialize(); }
		bool succeeded() { return m_succeded; }
	private:
		bool m_succeded;
		scoped_com_initializer( const scoped_com_initializer & ) ;
		scoped_com_initializer & operator=( const scoped_com_initializer & ) ;
}; // }}}

static PyObject*
get_computer_name(PyObject *self, PyObject *args) {
    COMPUTER_NAME_FORMAT fmt = ComputerNameDnsFullyQualified;
    if (!PyArg_ParseTuple(args, "|i", &fmt)) return NULL;
    DWORD sz = 0;
    GetComputerNameExW(fmt, NULL, &sz);
    sz *= 4;
    wchar_t *buf = (wchar_t*) PyMem_Malloc(sz * sizeof(wchar_t));
    if (!buf) return PyErr_NoMemory();
    PyObject *ans = NULL;
    if (GetComputerNameExW(fmt, buf, &sz)) ans = PyUnicode_FromWideChar(buf, -1);
    else PyErr_SetFromWindowsErr(0);
    PyMem_Free(buf);
    return ans;
}

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

static PyObject*
known_folder_path(PyObject *self, PyObject *args) {
	PyGUID *id;
	DWORD flags = KF_FLAG_DEFAULT;
	if (!PyArg_ParseTuple(args, "O!|k", &PyGUIDType, &id, &flags)) return NULL;
	com_wchar_raii path;
	HRESULT hr = SHGetKnownFolderPath(id->guid, flags, NULL, path.unsafe_address());
	return PyUnicode_FromWideChar(path.ptr(), -1);
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
    wchar_t buf[MAX_PATH + 8] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetTempPathW(sz, buf)) return PyErr_SetFromWindowsErr(0);
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
	BOOL ok;
	Py_BEGIN_ALLOW_THREADS
	ok = GetDiskFreeSpaceEx(path.ptr(), &bytes_available_to_caller, &total_bytes, &total_free_bytes);
	Py_END_ALLOW_THREADS
    if (!ok) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
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
                Py_ssize_t psz = p->FileNameLength / sizeof(wchar_t);
                PyObject *temp = Py_BuildValue("ku#", p->Action, p->FileName, psz);
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
supports_hardlinks(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
	UINT dt = GetDriveType(path.ptr());
	if (dt == DRIVE_REMOTE || dt == DRIVE_CDROM) Py_RETURN_FALSE;
	DWORD max_component_length, flags;
	if (!GetVolumeInformationW(path.ptr(), NULL, 0, NULL, &max_component_length, &flags, NULL, 0)) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
	if (flags & FILE_SUPPORTS_HARD_LINKS) Py_RETURN_TRUE;
	Py_RETURN_FALSE;
}

static PyObject*
filesystem_type_name(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
	DWORD max_component_length, flags;
    wchar_t fsname[128];
	if (!GetVolumeInformationW(path.ptr(), NULL, 0, NULL, &max_component_length, &flags, fsname, sizeof(fsname)/sizeof(fsname[0]))) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    return PyUnicode_FromWideChar(fsname, -1);
}

static PyObject*
winutil_create_hard_link(PyObject *self, PyObject *args) {
	wchar_raii path, existing_path;
	if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar_no_none, &path, py_to_wchar_no_none, &existing_path)) return NULL;
	BOOL ok;
	Py_BEGIN_ALLOW_THREADS
	ok = CreateHardLinkW(path.ptr(), existing_path.ptr(), NULL);
	Py_END_ALLOW_THREADS
    if (!ok) return PyErr_SetExcFromWindowsErrWithFilenameObjects(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
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
	wchar_raii path; unsigned long attrs = FILE_ATTRIBUTE_NORMAL;
	if (!PyArg_ParseTuple(args, "O&|k", py_to_wchar_no_none, &path, &attrs)) return NULL;
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
	if (!com.succeeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }

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

static PyObject*
resolve_lnk(PyObject *self, PyObject *args) {
	wchar_raii path;
    HRESULT hr;
    PyObject *win_id = NULL;
    unsigned short timeout = 0;
	if (!PyArg_ParseTuple(args, "O&|HO!", py_to_wchar, &path, &timeout, &PyLong_Type, &win_id)) return NULL;
	if (!path.ptr()) {
		PyErr_SetString(PyExc_TypeError, "Path must not be None");
		return NULL;
	}
	scoped_com_initializer com;
	if (!com.succeeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }
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
    hr = persist_file->Load(path.ptr(), 0);
    if (FAILED(hr)) return error_from_hresult(hr, "Failed to load link");
    DWORD flags = SLR_UPDATE | ( (timeout & 0xffff) << 16 );
    if (win_id) {
        hr = shell_link->Resolve(static_cast<HWND>(PyLong_AsVoidPtr(win_id)), flags);
    } else {
        hr = shell_link->Resolve(NULL, flags | SLR_NO_UI | SLR_NOTRACK | SLR_NOLINKINFO);
    }
	if (FAILED(hr)) return error_from_hresult(hr, "Failed to resolve link");
    wchar_t buf[2048];
    hr = shell_link->GetPath(buf, arraysz(buf), NULL, 0);
    if (FAILED(hr)) return error_from_hresult(hr, "Failed to get path from link");
    return PyUnicode_FromWideChar(buf, -1);
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
	if (!com.succeeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }

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
		if (FAILED(shell_link->GetPath(buf, arraysz(buf), NULL, 0))) Py_RETURN_NONE;
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
connect_named_pipe(PyObject *self, PyObject *args) {
	HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&", convert_handle, &handle)) return NULL;
	BOOL ok;
	Py_BEGIN_ALLOW_THREADS;
	ok = ConnectNamedPipe(handle, NULL);
	Py_END_ALLOW_THREADS;
	if (!ok) return set_error_from_handle(args);
	Py_RETURN_NONE;
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
    DWORD current_size = 4096;
    wchar_raii buf((wchar_t*)PyMem_Malloc(current_size * sizeof(wchar_t)));
    if (!buf) return PyErr_NoMemory();
    DWORD needed_size;
    Py_BEGIN_ALLOW_THREADS
    needed_size = GetLongPathNameW(path.ptr(), buf.ptr(), current_size);
    Py_END_ALLOW_THREADS
    if (needed_size >= current_size - 32) {
        current_size = needed_size + 32;
        buf.attach((wchar_t*)PyMem_Malloc(current_size * sizeof(wchar_t)));
        if (!buf) return PyErr_NoMemory();
        Py_BEGIN_ALLOW_THREADS
        needed_size = GetLongPathNameW(path.ptr(), buf.ptr(), current_size);
        Py_END_ALLOW_THREADS
    }
    if (!needed_size) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    if (needed_size >= current_size - 2) {
        PyErr_SetString(PyExc_OSError, "filename length changed between calls");
        return NULL;
    }
    buf.ptr()[current_size-1] = 0;
    return PyUnicode_FromWideChar(buf.ptr(), -1);
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
    DWORD ec = GetLastError();
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
	return PyLong_FromUnsignedLong(GetLastError());
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

static PyObject*
create_mutex(PyObject *self, PyObject *args) {
	int initial_owner = 0, allow_existing = 1;
	wchar_raii name;
	if (!PyArg_ParseTuple(args, "O&|pp", py_to_wchar, &name, &allow_existing, &initial_owner)) return NULL;
	HANDLE h = CreateMutexW(NULL, initial_owner, name.ptr());
	if (h == NULL) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
	if (!allow_existing && GetLastError() == ERROR_ALREADY_EXISTS) {
		CloseHandle(h);
		return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_FileExistsError, ERROR_ALREADY_EXISTS, PyTuple_GET_ITEM(args, 0));
	}
	return (PyObject*)Handle_create(h);
}


static PyObject*
parse_cmdline(PyObject *self, PyObject *args) {
	wchar_raii cmdline;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &cmdline)) return NULL;
	int num;
	LPWSTR *data = CommandLineToArgvW(cmdline.ptr(), &num);
	if (data == NULL) return PyErr_SetFromWindowsErr(0);
	PyObject *ans = PyTuple_New(num);
	if (!ans) { LocalFree(data); return NULL; }
	for (int i = 0; i < num; i++) {
		PyObject *temp = PyUnicode_FromWideChar(data[i], -1);
		if (!temp) { Py_CLEAR(ans); LocalFree(data); return NULL; }
		PyTuple_SET_ITEM(ans, i, temp);
	}
	LocalFree(data);
	return ans;
}

static PyObject*
run_cmdline(PyObject *self, PyObject *args) {
	wchar_raii cmdline;
	unsigned long flags;
	unsigned long wait_for = 0;
	if (!PyArg_ParseTuple(args, "O&k|k", py_to_wchar_no_none, &cmdline, &flags, &wait_for)) return NULL;
	STARTUPINFO si = {0};
	si.cb = sizeof(si);
	PROCESS_INFORMATION pi = {0};
	if (!CreateProcessW(NULL, cmdline.ptr(), NULL, NULL, FALSE, flags, NULL, NULL, &si, &pi)) return PyErr_SetFromWindowsErr(0);
	if (wait_for) WaitForInputIdle(pi.hProcess, wait_for);
	CloseHandle(pi.hProcess);
	CloseHandle(pi.hThread);
	Py_RETURN_NONE;
}

static PyObject*
is_wow64_process(PyObject *self, PyObject *args) {
	BOOL ans;
	if (!IsWow64Process(GetCurrentProcess(), &ans)) return PyErr_SetFromWindowsErr(0);
	return Py_BuildValue("O", ans ? Py_True : Py_False);
}

static PyObject*
write_file(PyObject *self, PyObject *args) {
    int offset = 0;
    Py_ssize_t size;
    const char *data;
    HANDLE handle;
    if (!PyArg_ParseTuple(args, "O&y#|i", convert_handle, &handle, &data, &size, &offset)) return NULL;
    DWORD written = 0;
    BOOL ok;
    Py_BEGIN_ALLOW_THREADS
    ok = WriteFile(handle, data + offset, size - offset, &written, NULL);
    Py_END_ALLOW_THREADS
    if (!ok) return set_error_from_handle(args);
    return PyLong_FromUnsignedLong(written);
}

static PyObject*
wait_named_pipe(PyObject *self, PyObject *args) {
    wchar_raii path;
    unsigned long timeout = 0;
    if (!PyArg_ParseTuple(args, "O&|k", py_to_wchar_no_none, &path, &timeout)) return NULL;
    BOOL ok;
    Py_BEGIN_ALLOW_THREADS
    ok = WaitNamedPipeW(path.ptr(), timeout);
    Py_END_ALLOW_THREADS
    if (!ok) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, 0, PyTuple_GET_ITEM(args, 0));
    Py_RETURN_TRUE;
}

static PyObject*
set_thread_execution_state(PyObject *self, PyObject *args) {
    unsigned long new_state;
    if (!PyArg_ParseTuple(args, "k", &new_state)) return NULL;
    if (SetThreadExecutionState(new_state) == NULL) return PyErr_SetFromWindowsErr(0);
    Py_RETURN_NONE;
}

// Icon loading {{{
#pragma pack( push )
#pragma pack( 2 )
typedef struct {
	int count;
	const wchar_t *resource_id;
} ResourceData;
#pragma pack( pop )


BOOL CALLBACK
EnumResProc(HMODULE handle, LPWSTR type, LPWSTR name, ResourceData *data) {
	if (data->count-- > 0) return TRUE;
	data->resource_id = name;
	return FALSE;
}

static const wchar_t*
get_resource_id_for_index(HMODULE handle, const int index, LPCWSTR type = RT_GROUP_ICON) {
	ResourceData data = {index, NULL};
	int count = index;
	EnumResourceNamesW(handle, type, reinterpret_cast<ENUMRESNAMEPROC>(EnumResProc), reinterpret_cast<LONG_PTR>(&data));
	return data.resource_id;
}

#pragma pack( push )
#pragma pack( 2 )
struct GRPICONDIRENTRY {
    BYTE bWidth;
    BYTE bHeight;
    BYTE bColorCount;
    BYTE bReserved;
    WORD wPlanes;
    WORD wBitCount;
    DWORD dwBytesInRes;
    WORD nID;
  };
#pragma pack( pop )

static PyObject*
load_icon(PyObject *args, HMODULE handle, GRPICONDIRENTRY *entry) {
	HRSRC res = FindResourceExW(handle, RT_ICON, MAKEINTRESOURCEW(entry->nID), MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL));
	if (!res) {
		DWORD ec = GetLastError();
		if (ec == ERROR_RESOURCE_TYPE_NOT_FOUND || ec == ERROR_RESOURCE_NAME_NOT_FOUND || ec == ERROR_RESOURCE_LANG_NOT_FOUND) return NULL;
		return set_error_from_handle(args, ec);
	}
	HGLOBAL hglob = LoadResource(handle, res);
	if (hglob == NULL) return set_error_from_handle(args);
	BYTE* data = (BYTE*)LockResource(hglob);
	if (!data) return NULL;
	DWORD sz = SizeofResource(handle, res);
	if (!sz) return NULL;
	HICON icon = CreateIconFromResourceEx(data, sz, TRUE, 0x00030000, 0, 0, LR_DEFAULTCOLOR);
    Py_ssize_t psz = sz;
	return Py_BuildValue("y#N", data, psz, Handle_create(icon, IconHandle));
}

struct GRPICONDIR {
    WORD idReserved;
    WORD idType;
    WORD idCount;
    GRPICONDIRENTRY idEntries[1];
};

static PyObject*
load_icons(PyObject *self, PyObject *args) {
	HMODULE handle;
	int index;
	if (!PyArg_ParseTuple(args, "O&i", convert_handle, &handle, &index)) return NULL;

	LPCWSTR resource_id = index < 0 ? MAKEINTRESOURCEW(-index) : get_resource_id_for_index(handle, index);
	if (resource_id == NULL) { PyErr_Format(PyExc_IndexError, "no resource found with index: %d in handle: %S", index, PyTuple_GET_ITEM(args, 0)); return NULL; }
	HRSRC res = FindResourceExW(handle, RT_GROUP_ICON, resource_id, MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL));
	if (res == NULL) return set_error_from_handle(args);
	DWORD size = SizeofResource(handle, res);
	if (!size) { PyErr_SetString(PyExc_ValueError, "the icon group resource at the specified index is empty"); return NULL; }
	HGLOBAL hglob = LoadResource(handle, res);
	if (hglob == NULL) return set_error_from_handle(args);
	GRPICONDIR *grp_icon_dir = (GRPICONDIR*)LockResource(hglob);
	if (!grp_icon_dir) { PyErr_SetString(PyExc_RuntimeError, "failed to lock icon group resource"); return NULL; }
	PyObject *ans = PyList_New(0);
	if (!ans) return NULL;
	for (size_t i = 0; i < grp_icon_dir->idCount; i++) {
		PyObject *hicon = load_icon(args, handle, grp_icon_dir->idEntries + i);
		if (hicon) {
			int ret = PyList_Append(ans, hicon);
			Py_CLEAR(hicon);
			if (ret != 0) { Py_CLEAR(ans); return NULL; }
		} else if (PyErr_Occurred()) { Py_CLEAR(ans); return NULL; }
	}
	return ans;
}

_COM_SMARTPTR_TYPEDEF(IImageList, __uuidof(IImageList));

static HICON
get_icon_at_index(int shilsize, int index) {
	IImageListPtr spiml;
	HRESULT hr = SHGetImageList(shilsize, IID_PPV_ARGS(&spiml));
	HICON hico = NULL;
	if (SUCCEEDED(hr)) spiml->GetIcon(index, ILD_TRANSPARENT, &hico);
	return hico;
}

static PyObject*
get_icon_for_file(PyObject *self, PyObject *args) {
	wchar_raii path;
	if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &path)) return NULL;
	scoped_com_initializer com;
	if (!com.succeeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }
	SHFILEINFO fi = {0};
	DWORD_PTR res;
	Py_BEGIN_ALLOW_THREADS
	res = SHGetFileInfoW(path.ptr(), 0, &fi, sizeof(fi), SHGFI_SYSICONINDEX);
	Py_END_ALLOW_THREADS
	if (!res) return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, ERROR_RESOURCE_TYPE_NOT_FOUND, PyTuple_GET_ITEM(args, 0));
	HICON icon;
#define R(shil) { \
	Py_BEGIN_ALLOW_THREADS \
	icon = get_icon_at_index(SHIL_JUMBO, fi.iIcon); \
	Py_END_ALLOW_THREADS \
	if (icon) return (PyObject*)Handle_create(icon, IconHandle); \
}
	R(SHIL_JUMBO); R(SHIL_EXTRALARGE); R(SHIL_LARGE); R(SHIL_SYSSMALL); R(SHIL_SMALL);
#undef R
	return PyErr_SetExcFromWindowsErrWithFilenameObject(PyExc_OSError, ERROR_RESOURCE_TYPE_NOT_FOUND, PyTuple_GET_ITEM(args, 0));
} // }}}

// Boilerplate  {{{
static const char winutil_doc[] = "Defines utility methods to interface with windows.";

#define M(name, args) { #name, name, args, ""}
static PyMethodDef winutil_methods[] = {
	M(run_cmdline, METH_VARARGS),
	M(is_wow64_process, METH_NOARGS),
    M(get_dll_directory, METH_NOARGS),
    M(create_mutex, METH_VARARGS),
    M(supports_hardlinks, METH_VARARGS),
    M(filesystem_type_name, METH_VARARGS),
    M(get_async_key_state, METH_VARARGS),
    M(create_named_pipe, METH_VARARGS),
    M(connect_named_pipe, METH_VARARGS),
    M(set_handle_information, METH_VARARGS),
    M(get_long_path_name, METH_VARARGS),
    M(get_process_times, METH_O),
	M(get_handle_information, METH_VARARGS),
	M(get_last_error, METH_NOARGS),
	M(load_library, METH_VARARGS),
	M(load_icons, METH_VARARGS),
	M(get_icon_for_file, METH_VARARGS),
	M(parse_cmdline, METH_VARARGS),
	M(write_file, METH_VARARGS),
	M(wait_named_pipe, METH_VARARGS),
	M(set_thread_execution_state, METH_VARARGS),
	M(known_folder_path, METH_VARARGS),
    M(get_computer_name, METH_VARARGS),

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

    {"resolve_lnk", (PyCFunction)resolve_lnk, METH_VARARGS,
        "resolve_lnk()\n\nGet the target of a lnk file."
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
        "read_file(handle, chunk_size=16KB)\n\nWrapper for ReadFile"
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

static int
exec_module(PyObject *m) {
#define add_type(name, doc, obj) obj##Type.tp_name = "winutil." #name; obj##Type.tp_doc = doc; obj##Type.tp_basicsize = sizeof(obj); \
	obj##Type.tp_itemsize = 0; obj##Type.tp_flags = Py_TPFLAGS_DEFAULT; obj##Type.tp_repr = (reprfunc)obj##_repr; \
	obj##Type.tp_str = (reprfunc)obj##_repr; obj##Type.tp_new = obj##_new; obj##Type.tp_dealloc = (destructor)obj##_dealloc; \
	obj##Type.tp_methods = obj##_methods; \
	if (PyType_Ready(&obj##Type) < 0) { return -1; } \
	Py_INCREF(&obj##Type); if (PyModule_AddObject(m, #name, (PyObject*) &obj##Type) < 0) { Py_DECREF(&obj##Type); return -1; }


	HandleNumberMethods.nb_int = (unaryfunc)Handle_as_int;
	HandleNumberMethods.nb_bool = (inquiry)Handle_as_bool;
	HandleType.tp_as_number = &HandleNumberMethods;
	add_type(Handle, "Wrappers for Win32 handles that free the handle on delete automatically", Handle);
	add_type(GUID, "Wrapper for Win32 GUID", PyGUID);
#undef add_type

#define A(name) { PyObject *g = create_guid(FOLDERID_##name); if (!g) { return -1; } if (PyModule_AddObject(m, "FOLDERID_" #name, g) < 0) { Py_DECREF(g); return -1; } }
	A(AdminTools);
	A(Startup);
	A(RoamingAppData);
	A(RecycleBinFolder);
	A(CDBurning);
	A(CommonAdminTools);
	A(CommonStartup);
	A(ProgramData);
	A(PublicDesktop);
	A(PublicDocuments);
	A(Favorites);
	A(PublicMusic);
	A(CommonOEMLinks);
	A(PublicPictures);
	A(CommonPrograms);
	A(CommonStartMenu);
	A(CommonStartup);
	A(CommonTemplates);
	A(PublicVideos);
	A(NetworkFolder);
	A(ConnectionsFolder);
	A(ControlPanelFolder);
	A(Cookies);
	A(Desktop);
	A(ComputerFolder);
	A(Favorites);
	A(Fonts);
	A(History);
	A(InternetFolder);
	A(InternetCache);
	A(LocalAppData);
	A(Documents);
	A(Music);
	A(Pictures);
	A(Videos);
	A(NetHood);
	A(NetworkFolder);
	A(Documents);
	A(PrintersFolder);
	A(PrintHood);
	A(Profile);
	A(ProgramFiles);
	A(ProgramFilesX86);
	A(ProgramFilesCommon);
	A(ProgramFilesCommonX86);
	A(Programs);
	A(Recent);
	A(ResourceDir);
	A(LocalizedResourcesDir);
	A(SendTo);
	A(StartMenu);
	A(Startup);
	A(System);
	A(SystemX86);
	A(Templates);
	A(Windows);

#undef A

#define A(name) if (PyModule_AddIntConstant(m, #name, name) != 0) { return -1; }

    A(CSIDL_ADMINTOOLS);
    A(CSIDL_APPDATA);
    A(CSIDL_COMMON_ADMINTOOLS);
    A(CSIDL_COMMON_APPDATA);
    A(CSIDL_COMMON_DOCUMENTS);
    A(CSIDL_COOKIES);
    A(CSIDL_FLAG_CREATE);
    A(CSIDL_FLAG_DONT_VERIFY);
    A(CSIDL_FONTS);
    A(CSIDL_HISTORY);
    A(CSIDL_INTERNET_CACHE);
    A(CSIDL_LOCAL_APPDATA);
    A(CSIDL_MYPICTURES);
    A(CSIDL_PERSONAL);
    A(CSIDL_PROGRAM_FILES);
    A(CSIDL_PROGRAM_FILES_COMMON);
    A(CSIDL_SYSTEM);
    A(CSIDL_WINDOWS);
    A(CSIDL_PROFILE);
    A(CSIDL_STARTUP);
    A(CSIDL_COMMON_STARTUP);
    A(CREATE_NEW);
    A(CREATE_ALWAYS);
    A(OPEN_EXISTING);
    A(OPEN_ALWAYS);
    A(TRUNCATE_EXISTING);
    A(FILE_SHARE_READ);
    A(FILE_SHARE_WRITE);
    A(FILE_SHARE_DELETE);
    PyModule_AddIntConstant(m, "FILE_SHARE_VALID_FLAGS", FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    A(FILE_ATTRIBUTE_READONLY);
    A(FILE_ATTRIBUTE_NORMAL);
    A(FILE_ATTRIBUTE_TEMPORARY);
    A(FILE_FLAG_DELETE_ON_CLOSE);
    A(FILE_FLAG_SEQUENTIAL_SCAN);
    A(FILE_FLAG_RANDOM_ACCESS);
    A(GENERIC_READ);
    A(GENERIC_WRITE);
    A(DELETE);
    A(FILE_BEGIN);
    A(FILE_CURRENT);
    A(FILE_END);
    A(MOVEFILE_COPY_ALLOWED);
    A(MOVEFILE_CREATE_HARDLINK);
    A(MOVEFILE_DELAY_UNTIL_REBOOT);
    A(MOVEFILE_FAIL_IF_NOT_TRACKABLE);
    A(MOVEFILE_REPLACE_EXISTING);
    A(MOVEFILE_WRITE_THROUGH);
    A(FILE_NOTIFY_CHANGE_FILE_NAME);
    A(FILE_NOTIFY_CHANGE_DIR_NAME);
    A(FILE_NOTIFY_CHANGE_ATTRIBUTES);
    A(FILE_NOTIFY_CHANGE_SIZE);
    A(FILE_NOTIFY_CHANGE_LAST_WRITE);
    A(FILE_NOTIFY_CHANGE_LAST_ACCESS);
    A(FILE_NOTIFY_CHANGE_CREATION);
    A(FILE_NOTIFY_CHANGE_SECURITY);
    A(FILE_ACTION_ADDED);
    A(FILE_ACTION_REMOVED);
    A(FILE_ACTION_MODIFIED);
    A(FILE_ACTION_RENAMED_OLD_NAME);
    A(FILE_ACTION_RENAMED_NEW_NAME);
    A(FILE_LIST_DIRECTORY);
    A(FILE_FLAG_BACKUP_SEMANTICS);
    A(SHGFP_TYPE_CURRENT);
    A(SHGFP_TYPE_DEFAULT);
    A(PIPE_ACCESS_INBOUND);
    A(FILE_FLAG_FIRST_PIPE_INSTANCE);
    A(PIPE_TYPE_BYTE);
    A(PIPE_READMODE_BYTE);
    A(PIPE_WAIT);
    A(PIPE_REJECT_REMOTE_CLIENTS);
    A(HANDLE_FLAG_INHERIT);
    A(HANDLE_FLAG_PROTECT_FROM_CLOSE);
    A(VK_RMENU);
    A(DONT_RESOLVE_DLL_REFERENCES);
    A(LOAD_LIBRARY_AS_DATAFILE);
    A(LOAD_LIBRARY_AS_IMAGE_RESOURCE);
    A(INFINITE);
    A(REG_QWORD);
    A(ERROR_SUCCESS);
    A(ERROR_MORE_DATA);
    A(ERROR_NO_MORE_ITEMS);
    A(ERROR_FILE_NOT_FOUND);
    A(ERROR_GEN_FAILURE);
    A(ERROR_INSUFFICIENT_BUFFER);
    A(ERROR_BAD_COMMAND);
    A(ERROR_INVALID_DATA);
    A(ERROR_NOT_READY);
    A(ERROR_SHARING_VIOLATION);
    A(ERROR_LOCK_VIOLATION);
    A(ERROR_ALREADY_EXISTS);
    A(ERROR_BROKEN_PIPE);
    A(ERROR_PIPE_BUSY);
    A(NormalHandle);
    A(ModuleHandle);
    A(IconHandle);

	A(KF_FLAG_DEFAULT);
	A(KF_FLAG_FORCE_APP_DATA_REDIRECTION);
	A(KF_FLAG_RETURN_FILTER_REDIRECTION_TARGET);
	A(KF_FLAG_FORCE_PACKAGE_REDIRECTION);
	A(KF_FLAG_NO_PACKAGE_REDIRECTION);
	A(KF_FLAG_FORCE_APPCONTAINER_REDIRECTION);
	A(KF_FLAG_NO_APPCONTAINER_REDIRECTION);
	A(KF_FLAG_CREATE);
	A(KF_FLAG_DONT_VERIFY);
	A(KF_FLAG_DONT_UNEXPAND);
	A(KF_FLAG_NO_ALIAS);
	A(KF_FLAG_INIT);
	A(KF_FLAG_DEFAULT_PATH);
	A(KF_FLAG_NOT_PARENT_RELATIVE);
	A(KF_FLAG_SIMPLE_IDLIST);
	A(KF_FLAG_ALIAS_ONLY);
    A(ComputerNameDnsDomain);
    A(ComputerNameDnsFullyQualified);
    A(ComputerNameDnsHostname);
    A(ComputerNameNetBIOS);
    A(ComputerNamePhysicalDnsDomain);
    A(ComputerNamePhysicalDnsFullyQualified);
    A(ComputerNamePhysicalDnsHostname);
    A(ComputerNamePhysicalNetBIOS);

    A(ES_AWAYMODE_REQUIRED);
    A(ES_CONTINUOUS);
    A(ES_DISPLAY_REQUIRED);
    A(ES_SYSTEM_REQUIRED);
    A(ES_USER_PRESENT);
#undef A
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_winutil(void) {
    module_def.m_name     = "winutil";
    module_def.m_doc      = winutil_doc;
    module_def.m_methods  = winutil_methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
