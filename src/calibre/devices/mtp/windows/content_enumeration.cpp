/*
 * content_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

#include <new>

namespace wpd {

static int
pump_waiting_messages() {
	UINT firstMsg = 0, lastMsg = 0;
    MSG msg;
	int result = 0;
	// Read all of the messages in this next loop,
	// removing each message as we read it.
	while (PeekMessage(&msg, NULL, firstMsg, lastMsg, PM_REMOVE)) {
		// If it's a quit message, we're out of here.
		if (msg.message == WM_QUIT) {
			result = 1;
			break;
		}
		// Otherwise, dispatch the message.
		DispatchMessage(&msg);
	} // End of PeekMessage while loop

    return result;
}

static IPortableDeviceKeyCollection*
create_filesystem_properties_collection() { // {{{
    CComPtr<IPortableDeviceKeyCollection> properties;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = properties.CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;

    if (FAILED(hr)) { hresult_set_exc("Failed to create filesystem properties collection", hr); return NULL; }

#define ADDPROP(x) hr = properties->Add(x); if (FAILED(hr)) { hresult_set_exc("Failed to add property " #x " to filesystem properties collection", hr); return NULL; }

    ADDPROP(WPD_OBJECT_CONTENT_TYPE);
    ADDPROP(WPD_OBJECT_PARENT_ID);
    ADDPROP(WPD_OBJECT_PERSISTENT_UNIQUE_ID);
    ADDPROP(WPD_OBJECT_NAME);
    ADDPROP(WPD_OBJECT_ORIGINAL_FILE_NAME);
    // ADDPROP(WPD_OBJECT_SYNC_ID);
    ADDPROP(WPD_OBJECT_ISSYSTEM);
    ADDPROP(WPD_OBJECT_ISHIDDEN);
    ADDPROP(WPD_OBJECT_CAN_DELETE);
    ADDPROP(WPD_OBJECT_SIZE);
    ADDPROP(WPD_OBJECT_DATE_CREATED);
    ADDPROP(WPD_OBJECT_DATE_MODIFIED);
#undef ADDPROP

    return properties.Detach();

} // }}}

// Convert properties from COM to python {{{
static void
set_string_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, const CComPtr<IPortableDeviceValues> &properties) {
    HRESULT hr;
	com_wchar_raii property;
    hr = properties->GetStringValue(key, property.unsafe_address());
    if (SUCCEEDED(hr)) {
		pyobject_raii val(PyUnicode_FromWideChar(property.ptr(), -1));
        if (val) if (PyDict_SetItemString(dict, pykey, val.ptr()) != 0) PyErr_Clear();
    }
}

static void
set_bool_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, const CComPtr<IPortableDeviceValues> &properties) {
    BOOL ok = 0;
    HRESULT hr;

    hr = properties->GetBoolValue(key, &ok);
    if (SUCCEEDED(hr)) {
        if (PyDict_SetItemString(dict, pykey, (ok)?Py_True:Py_False) != 0) PyErr_Clear();
	}
}

static void
set_size_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, const CComPtr<IPortableDeviceValues> &properties) {
    ULONGLONG val = 0;
    HRESULT hr;
    hr = properties->GetUnsignedLargeIntegerValue(key, &val);
    if (SUCCEEDED(hr)) {
        pyobject_raii pval(PyLong_FromUnsignedLongLong(val));
        if (pval) {
            if (PyDict_SetItemString(dict, pykey, pval.ptr()) != 0) PyErr_Clear();
        } else PyErr_Clear();
    }
}

static void
set_date_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, const CComPtr<IPortableDeviceValues> &properties) {
	prop_variant ts;
    if (SUCCEEDED(properties->GetValue(key, &ts))) {
		SYSTEMTIME st;
        if (ts.vt == VT_DATE && VariantTimeToSystemTime(ts.date, &st)) {
            const unsigned int microseconds = 1000 * st.wMilliseconds;
			pyobject_raii t(Py_BuildValue("H H H H H H I", (unsigned short)st.wYear,
                    (unsigned short)st.wMonth, (unsigned short)st.wDay,
                    (unsigned short)st.wHour, (unsigned short)st.wMinute,
                    (unsigned short)st.wSecond, microseconds));
			if (t) if (PyDict_SetItemString(dict, pykey, t.ptr()) != 0) PyErr_Clear();
        }
    }
}

static void
set_content_type_property(PyObject *dict, const CComPtr<IPortableDeviceValues> &properties) {
    GUID guid = GUID_NULL;
    BOOL is_folder = 0;

    if (SUCCEEDED(properties->GetGuidValue(WPD_OBJECT_CONTENT_TYPE, &guid)) && IsEqualGUID(guid, WPD_CONTENT_TYPE_FOLDER)) is_folder = 1;
    if (PyDict_SetItemString(dict, "is_folder", (is_folder) ? Py_True : Py_False) != 0) PyErr_Clear();
}

static void
set_properties(PyObject *obj, const CComPtr<IPortableDeviceValues> &values) {
    set_content_type_property(obj, values);

    set_string_property(obj, WPD_OBJECT_PARENT_ID, "parent_id", values);
    set_string_property(obj, WPD_OBJECT_NAME, "nominal_name", values);
    // set_string_property(obj, WPD_OBJECT_SYNC_ID, "sync_id", values);
    set_string_property(obj, WPD_OBJECT_ORIGINAL_FILE_NAME, "name", values);
    set_string_property(obj, WPD_OBJECT_PERSISTENT_UNIQUE_ID, "persistent_id", values);

    set_bool_property(obj, WPD_OBJECT_ISHIDDEN, "is_hidden", values);
    set_bool_property(obj, WPD_OBJECT_CAN_DELETE, "can_delete", values);
    set_bool_property(obj, WPD_OBJECT_ISSYSTEM, "is_system", values);

    set_size_property(obj, WPD_OBJECT_SIZE, "size", values);
    set_date_property(obj, WPD_OBJECT_DATE_MODIFIED, "modified", values);
    set_date_property(obj, WPD_OBJECT_DATE_CREATED, "created", values);
}

// }}}

// Bulk get filesystem {{{

class GetBulkPropertiesCallback : public IPortableDevicePropertiesBulkCallback {
private:
    PyObject *items;
    PyObject *subfolders;
    unsigned int level;
    HANDLE complete;
    ULONG self_ref;
    PyObject *callback;

	void do_one_object(CComPtr<IPortableDeviceValues> &properties) {
		com_wchar_raii property;
		if (!SUCCEEDED(properties->GetStringValue(WPD_OBJECT_ID, property.unsafe_address()))) return;
		pyobject_raii object_id(PyUnicode_FromWideChar(property.ptr(), -1));
		if (!object_id) { PyErr_Clear(); return; }
		pyobject_raii obj(PyDict_GetItem(this->items, object_id.ptr()));
		if (!obj) {
			obj.attach(Py_BuildValue("{s:O}", "id", object_id.ptr()));
			if (!obj) { PyErr_Clear(); return; }
			if (PyDict_SetItem(this->items, object_id.ptr(), obj.ptr()) != 0) { PyErr_Clear(); return; }
		} else Py_INCREF(obj.ptr());
		set_properties(obj.ptr(), properties);
		pyobject_raii r(PyObject_CallFunction(callback, "OI", obj.ptr(), this->level));
		if (!r) PyErr_Clear();
		else if (r && PyObject_IsTrue(r.ptr())) {
			PyObject *borrowed = PyDict_GetItemString(obj.ptr(), "id");
			if (borrowed) if (PyList_Append(this->subfolders, borrowed) != 0) PyErr_Clear();
		}
	}

	void handle_values(IPortableDeviceValuesCollection* values) {
		DWORD num = 0;
		if (!items) return;
		if (!SUCCEEDED(values->GetCount(&num))) return;
		for (DWORD i = 0; i < num; i++) {
			CComPtr<IPortableDeviceValues> properties;
			if (SUCCEEDED(values->GetAt(i, &properties))) do_one_object(properties);
		}
	}


public:
	GetBulkPropertiesCallback() : items(NULL), subfolders(NULL), level(0), complete(INVALID_HANDLE_VALUE), self_ref(0), callback(NULL) {}
    ~GetBulkPropertiesCallback() { if (complete != INVALID_HANDLE_VALUE) CloseHandle(complete); complete = INVALID_HANDLE_VALUE; }

	bool start_processing(PyObject *items, PyObject *subfolders, unsigned int level, PyObject *callback) {
		complete = CreateEvent(NULL, FALSE, FALSE, NULL);
		if (complete == NULL || complete == INVALID_HANDLE_VALUE) return false;

		this->items = items; this->subfolders = subfolders; this->level = level; this->callback = callback;
		self_ref = 0;
		return true;
	}
	void end_processing() {
		if (complete != INVALID_HANDLE_VALUE) CloseHandle(complete);
		items = NULL; subfolders = NULL; level = 0; complete = INVALID_HANDLE_VALUE; callback = NULL;
	}
	bool handle_is_valid() const { return complete != INVALID_HANDLE_VALUE; }

    HRESULT __stdcall OnStart(REFGUID Context) { return S_OK; }
    HRESULT __stdcall OnEnd(REFGUID Context, HRESULT hrStatus) { if (complete != INVALID_HANDLE_VALUE) SetEvent(complete); return S_OK; }
    ULONG __stdcall AddRef() { InterlockedIncrement((long*) &self_ref); return self_ref; }
    ULONG __stdcall Release() {
        ULONG refcnt = self_ref - 1;
        if (InterlockedDecrement((long*) &self_ref) == 0) { delete this; return 0; }
        return refcnt;
    }
    HRESULT __stdcall QueryInterface(REFIID riid, LPVOID* obj) {
        HRESULT hr = S_OK;
        if (obj == NULL) { hr = E_INVALIDARG; return hr; }

        if ((riid == IID_IUnknown) || (riid == IID_IPortableDevicePropertiesBulkCallback)) {
            AddRef();
            *obj = this;
        }
        else {
            *obj = NULL;
            hr = E_NOINTERFACE;
        }
        return hr;
    }
	HRESULT __stdcall GetBulkPropertiesCallback::OnProgress(REFGUID Context, IPortableDeviceValuesCollection* values) {
		handle_values(values);
		return S_OK;
	}

	DWORD wait_for_messages(int seconds=60) {
		DWORD wait_result;
		if (complete == INVALID_HANDLE_VALUE) return WAIT_OBJECT_0;
		Py_BEGIN_ALLOW_THREADS;
		wait_result = MsgWaitForMultipleObjects(1, &complete, FALSE, seconds * 1000, QS_ALLEVENTS);
		Py_END_ALLOW_THREADS;
		return wait_result;
	}

};


static bool
bulk_get_filesystem(
		unsigned int level, IPortableDevice *device, IPortableDevicePropertiesBulk *bulk_properties,
		CComPtr<IPortableDevicePropVariantCollection> &object_ids,
		PyObject *pycallback, PyObject *ans, PyObject *subfolders
) {
    CComPtr<IPortableDeviceKeyCollection> properties(create_filesystem_properties_collection());
    if (!properties) return false;

	GetBulkPropertiesCallback *bulk_properties_callback = new (std::nothrow) GetBulkPropertiesCallback();
	if (!bulk_properties_callback) { PyErr_NoMemory(); return false; }

    GUID guid_context;
    HRESULT hr;
	if (!bulk_properties_callback->start_processing(ans, subfolders, level, pycallback)) {
		delete bulk_properties_callback;
		PyErr_NoMemory();
		return false;
	}
    hr = bulk_properties->QueueGetValuesByObjectList(object_ids, properties, bulk_properties_callback, &guid_context);
    if (FAILED(hr)) {
		bulk_properties_callback->end_processing();
		delete bulk_properties_callback;
		hresult_set_exc("Failed to queue bulk property retrieval", hr);
		return false;
	}

    hr = bulk_properties->Start(guid_context);
    if (FAILED(hr)) {
		bulk_properties_callback->end_processing();
		delete bulk_properties_callback;
		hresult_set_exc("Failed to start bulk operation", hr);
		return false;
	}

    bulk_properties_callback->AddRef();
    while (!PyErr_Occurred()) {
		DWORD wait_result = bulk_properties_callback->wait_for_messages();
        if (wait_result == WAIT_OBJECT_0) {
            break; // Event was signalled, bulk operation complete
        } else if (wait_result == WAIT_OBJECT_0 + 1) { // Messages need to be dispatched
            int pump_result = pump_waiting_messages();
            if (pump_result == 1) PyErr_SetString(PyExc_RuntimeError, "Application has been asked to quit.");
        } else if (wait_result == WAIT_TIMEOUT) {
            // 60 seconds with no updates, looks bad
            PyErr_SetString(WPDError, "The device seems to have hung.");
        } else if (wait_result == WAIT_ABANDONED_0) {
            // This should never happen
            PyErr_SetString(WPDError, "An unknown error occurred (mutex abandoned)");
        } else {
            // The wait failed for some reason
            const char buf[256] = {0};
            _snprintf_s((char *const)buf, sizeof(buf) - 1, _TRUNCATE, "handle wait failed in bulk filesystem get at file: %s line: %d", __FILE__, __LINE__);
            PyErr_SetExcFromWindowsErrWithFilename(WPDError, 0, buf);
        }
    }
    bulk_properties_callback->end_processing();
    if (PyErr_Occurred()) {
        bulk_properties->Cancel(guid_context);
        pump_waiting_messages();
    }
	bulk_properties_callback->Release();
    return PyErr_Occurred() ? false : true;
}

// }}}

// find_objects_in() {{{
static bool
find_objects_in(CComPtr<IPortableDeviceContent> &content, CComPtr<IPortableDevicePropVariantCollection> &object_ids, const wchar_t *parent_id, bool *enum_failed) {
    /*
     * Find all children of the object identified by parent_id.
     * The child ids are put into object_ids. Returns False if any errors
     * occurred (also sets the python exception).
     */
    CComPtr<IEnumPortableDeviceObjectIDs> children;
    HRESULT hr = S_OK, hr2 = S_OK;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->EnumObjects(0, parent_id, NULL, &children);
    Py_END_ALLOW_THREADS;

    if (FAILED(hr)) {
        fwprintf(stderr, L"Failed to EnumObjects() for object id: %s retrying with a sleep.\n", parent_id); fflush(stderr);
        Py_BEGIN_ALLOW_THREADS;
        Sleep(500);
        hr = content->EnumObjects(0, parent_id, NULL, &children);
        Py_END_ALLOW_THREADS;
        if (FAILED(hr)) {
            pyobject_raii parent_name(PyUnicode_FromWideChar(parent_id, -1));
            set_error_from_hresult(wpd::WPDError, __FILE__, __LINE__, hr, "Failed to EnumObjects() of folder from device", parent_name.ptr());
            *enum_failed = true;
            return false;
        }
    }
    *enum_failed = false;

    hr = S_OK;

    while (hr == S_OK) {
		DWORD fetched;
		prop_variant pv(VT_LPWSTR);
		generic_raii_array<wchar_t*, co_task_mem_free, 16> child_ids;
        Py_BEGIN_ALLOW_THREADS;
        hr = children->Next((ULONG)child_ids.size(), child_ids.ptr(), &fetched);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) {
            for (DWORD i = 0; i < fetched; i++) {
                pv.pwszVal = child_ids[i];
                hr2 = object_ids->Add(&pv);
                pv.pwszVal = NULL;
                if (FAILED(hr2)) { hresult_set_exc("Failed to add child ids to propvariantcollection", hr2); return false; }
            }
        }
    }
	return true;
} // }}}

// Single get filesystem {{{

static PyObject*
get_object_properties(IPortableDeviceProperties *devprops, IPortableDeviceKeyCollection *properties, const wchar_t *object_id) {
    CComPtr<IPortableDeviceValues> values;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = devprops->GetValues(object_id, properties, &values);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get properties for object", hr); return NULL; }

	pyobject_raii id(PyUnicode_FromWideChar(object_id, -1));
	if (!id) return NULL;
    PyObject *ans = Py_BuildValue("{s:O}", "id", id.ptr());
    if (ans == NULL) return NULL;
    set_properties(ans, values);
    return ans;
}

static bool
single_get_filesystem(unsigned int level, CComPtr<IPortableDeviceContent> &content, CComPtr<IPortableDevicePropVariantCollection> &object_ids, PyObject *callback, PyObject *ans, PyObject *subfolders) {
    DWORD num;
    HRESULT hr;
    CComPtr<IPortableDeviceProperties> devprops;

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); return false; }

    CComPtr<IPortableDeviceKeyCollection> properties(create_filesystem_properties_collection());
    if (!properties) return false;

    hr = object_ids->GetCount(&num);
    if (FAILED(hr)) { hresult_set_exc("Failed to get object id count", hr); return false; }

    for (DWORD i = 0; i < num; i++) {
		prop_variant pv;
        hr = object_ids->GetAt(i, &pv);
		pyobject_raii recurse;
        if (SUCCEEDED(hr) && pv.pwszVal != NULL) {
            pyobject_raii item(get_object_properties(devprops, properties, pv.pwszVal));
			if (!item) return false;
			pyobject_raii r(PyObject_CallFunction(callback, "OI", item.ptr(), level));
			if (PyDict_SetItem(ans, PyDict_GetItemString(item.ptr(), "id"), item.ptr()) != 0) return false;
			if (r && PyObject_IsTrue(r.ptr())) recurse.attach(item.detach());
        } else { hresult_set_exc("Failed to get item from IPortableDevicePropVariantCollection", hr); return false; }

        if (recurse) {
            if (PyList_Append(subfolders, PyDict_GetItemString(recurse.ptr(), "id")) == -1) return false;
        }
    }
    return true;
}
// }}}

static IPortableDeviceValues*
create_object_properties(const wchar_t *parent_id, const wchar_t *name, const GUID content_type, unsigned PY_LONG_LONG size) { // {{{
    CComPtr<IPortableDeviceValues> values;
    HRESULT hr;
    bool ok = false;
	prop_variant timestamp(VT_DATE);
	SYSTEMTIME  systemtime;
	GetLocalTime(&systemtime);
	if (!SystemTimeToVariantTime(&systemtime, &timestamp.date)) {
		LONG err = GetLastError();
		hr = HRESULT_FROM_WIN32(err);
		hresult_set_exc("Failed to convert system time to variant time", hr); return NULL;
	}

    hr = values.CoCreateInstance(CLSID_PortableDeviceValues, NULL, CLSCTX_INPROC_SERVER);
    if (FAILED(hr)) { hresult_set_exc("Failed to create values interface", hr); return NULL; }

#define A(func, name, key) hr = values->func(name, key); \
	if (FAILED(hr)) { hresult_set_exc("Failed to set " #name " value", hr); return NULL; }
	A(SetStringValue, WPD_OBJECT_PARENT_ID, parent_id);
	A(SetStringValue, WPD_OBJECT_NAME, name);
	A(SetStringValue, WPD_OBJECT_ORIGINAL_FILE_NAME, name);
	A(SetGuidValue, WPD_OBJECT_FORMAT, WPD_OBJECT_FORMAT_UNSPECIFIED);
	A(SetGuidValue, WPD_OBJECT_CONTENT_TYPE, content_type);
	A(SetValue, WPD_OBJECT_DATE_CREATED, &timestamp);
	A(SetValue, WPD_OBJECT_DATE_MODIFIED, &timestamp);
    if (!IsEqualGUID(WPD_CONTENT_TYPE_FOLDER, content_type)) {
		A(SetUnsignedLargeIntegerValue, WPD_OBJECT_SIZE, size);
    }
#undef A
    return values.Detach();
} // }}}

static bool
get_files_and_folders(unsigned int level, IPortableDevice *device, CComPtr<IPortableDeviceContent> &content, IPortableDevicePropertiesBulk *bulk_properties, const wchar_t *parent_id, PyObject *callback, PyObject *ans) { // {{{
    CComPtr<IPortableDevicePropVariantCollection> object_ids;
    HRESULT hr;

    pyobject_raii subfolders(PyList_New(0));
    if (!subfolders) return false;

    Py_BEGIN_ALLOW_THREADS;
    hr = object_ids.CoCreateInstance(CLSID_PortableDevicePropVariantCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create propvariantcollection", hr); return false; }

    bool enum_failed = false;
    if (!find_objects_in(content, object_ids, parent_id, &enum_failed)) {
        return false;
    }

    if (bulk_properties != NULL) {
		if (!bulk_get_filesystem(level, device, bulk_properties, object_ids, callback, ans, subfolders.ptr())) return false;
	} else {
		if (!single_get_filesystem(level, content, object_ids, callback, ans, subfolders.ptr())) return false;
	}

    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(subfolders.ptr()); i++) {
		wchar_raii child_id(PyUnicode_AsWideCharString(PyList_GET_ITEM(subfolders.ptr(), i), NULL));
        if (!child_id) return false;
        if (!get_files_and_folders(level+1, device, content, bulk_properties, child_id.ptr(), callback, ans)) return false;
    }
    return true;
} // }}}

PyObject*
wpd::get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties, PyObject *callback) { // {{{
    CComPtr<IPortableDeviceContent> content;
    HRESULT hr;

    pyobject_raii ans(PyDict_New());
	if (!ans) return NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }

    if (!get_files_and_folders(0, device, content, bulk_properties, storage_id, callback, ans.ptr())) return NULL;
    return ans.detach();
} // }}}

PyObject*
wpd::get_file(IPortableDevice *device, const wchar_t *object_id, PyObject *dest, PyObject *callback) { // {{{
    CComPtr<IPortableDeviceContent> content;
    CComPtr<IPortableDeviceResources> resources;
    CComPtr<IPortableDeviceProperties> devprops;
    CComPtr<IPortableDeviceValues> values;
    CComPtr<IPortableDeviceKeyCollection> properties;
    CComPtr<IStream> stream;

    HRESULT hr;
    DWORD bufsize = 4096;
    ULONG bytes_read = 0, total_read = 0;
    ULONGLONG filesize = 0;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&devprops);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = properties.CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create filesystem properties collection", hr); return NULL; }
    hr = properties->Add(WPD_OBJECT_SIZE);
    if (FAILED(hr)) { hresult_set_exc("Failed to add filesize property to properties collection", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = devprops->GetValues(object_id, properties, &values);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get filesize for object", hr); return NULL; }
    hr = values->GetUnsignedLargeIntegerValue(WPD_OBJECT_SIZE, &filesize);
    if (FAILED(hr)) { hresult_set_exc("Failed to get filesize from values collection", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Transfer(&resources);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create resources interface", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = resources->GetStream(object_id, WPD_RESOURCE_DEFAULT, STGM_READ, &bufsize, &stream);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {
        if (HRESULT_FROM_WIN32(ERROR_BUSY) == hr) {
            PyErr_SetString(WPDFileBusy, "Object is in use");
        } else hresult_set_exc("Failed to create stream interface to read from object", hr);
		return NULL;
    }

	generic_raii<char*, PyMem_Free> buf(reinterpret_cast<char*>(PyMem_Malloc(bufsize)));
	if (!buf) return PyErr_NoMemory();

    while (total_read < filesize) {
        bytes_read = 0;
        Py_BEGIN_ALLOW_THREADS;
        hr = stream->Read(buf.ptr(), bufsize, &bytes_read);
        Py_END_ALLOW_THREADS;
        if (hr == STG_E_ACCESSDENIED) {
			PyErr_SetFromWindowsErr(ERROR_ACCESS_DENIED);
			return NULL;
        } else if (SUCCEEDED(hr)) {
            if (bytes_read > 0) {
				total_read += bytes_read;
                Py_ssize_t br = bytes_read;
                pyobject_raii res(PyObject_CallMethod(dest, "write", "y#", buf.ptr(), br));
				if (!res) { return NULL; }
                if (callback != NULL) {
					pyobject_raii r(PyObject_CallFunction(callback, "kK", total_read, filesize));
				}
            }
        } else { hresult_set_exc("Failed to read file from device", hr); return NULL; }

        if (bytes_read == 0) {
            pyobject_raii r(PyObject_CallMethod(dest, "flush", NULL));
            break;
        }
    }

    if (total_read < filesize) {
        PyErr_SetString(WPDError, "Failed to read all data from file");
		return NULL;
    }
    Py_RETURN_NONE;
} // }}}

PyObject*
wpd::create_folder(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name) { // {{{
    CComPtr<IPortableDeviceContent> content;
    CComPtr<IPortableDeviceValues> values;
    CComPtr<IPortableDeviceProperties> devprops;
    CComPtr<IPortableDeviceKeyCollection> properties;
    HRESULT hr;

    values = create_object_properties(parent_id, name, WPD_CONTENT_TYPE_FOLDER, 0);
    if (!values) return NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); return NULL; }

    properties = create_filesystem_properties_collection();
    if (!properties) return NULL;

	wchar_raii newid;
    Py_BEGIN_ALLOW_THREADS;
    hr = content->CreateObjectWithPropertiesOnly(values, newid.unsafe_address());
    Py_END_ALLOW_THREADS;
    if (FAILED(hr) || !newid) { hresult_set_exc("Failed to create folder", hr); return NULL; }

    return get_object_properties(devprops, properties, newid.ptr());
} // }}}

PyObject*
wpd::delete_object(IPortableDevice *device, const wchar_t *object_id) { // {{{
    CComPtr<IPortableDeviceContent> content;
    CComPtr<IPortableDevicePropVariantCollection> object_ids;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = object_ids.CoCreateInstance(CLSID_PortableDevicePropVariantCollection, NULL, CLSCTX_INPROC_SERVER);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create propvariantcollection", hr); return NULL; }

    prop_variant pv(VT_LPWSTR);
    pv.pwszVal = (wchar_t*)object_id;
    hr = object_ids->Add(&pv);
    pv.pwszVal = NULL;
    if (FAILED(hr)) { hresult_set_exc("Failed to add device id to propvariantcollection", hr); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }

    hr = content->Delete(PORTABLE_DEVICE_DELETE_NO_RECURSION, object_ids, NULL);
    if (hr == HRESULT_FROM_WIN32(ERROR_NOT_FOUND) || SUCCEEDED(hr)) {Py_RETURN_NONE;}

    if (hr == E_ACCESSDENIED) { PyErr_SetExcFromWindowsErr(WPDError, ERROR_ACCESS_DENIED); }
    else if (hr == HRESULT_FROM_WIN32(ERROR_DIR_NOT_EMPTY) || hr == HRESULT_FROM_WIN32(ERROR_INVALID_OPERATION)) {
		PyErr_SetString(WPDError, "Cannot delete object as it has children"); }
    else hresult_set_exc("Cannot delete object", hr);
	return NULL;

} // }}}

PyObject*
wpd::put_file(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name, PyObject *src, unsigned PY_LONG_LONG size, PyObject *callback) { // {{{
    CComPtr<IPortableDeviceContent> content;
    CComPtr<IPortableDeviceValues> values;
    CComPtr<IPortableDeviceProperties> devprops;
    CComPtr<IPortableDeviceKeyCollection> properties;
    CComPtr<IStream> temp;
    CComPtr<IPortableDeviceDataStream> dest;
    HRESULT hr;
    DWORD bufsize = 0;
    Py_ssize_t bytes_read = 0;
    ULONG bytes_written = 0, total_written = 0;

    values = create_object_properties(parent_id, name, WPD_CONTENT_TYPE_GENERIC_FILE, size);
    if (!values) return NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); return NULL; }

    properties = create_filesystem_properties_collection();
    if (!properties) return NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->CreateObjectWithPropertiesAndData(values, &temp, &bufsize, NULL);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {
        if (HRESULT_FROM_WIN32(ERROR_BUSY) == hr) {
            PyErr_SetString(WPDFileBusy, "Object is in use");
        } else hresult_set_exc("Failed to create stream interface to write to object", hr);
        return NULL;
    }

    hr = temp->QueryInterface(IID_PPV_ARGS(&dest));
    if (FAILED(hr)) { hresult_set_exc("Failed to create IPortableDeviceStream", hr); return NULL; }

    while(true) {
#define ABORT { dest->Revert(); return NULL; }
        pyobject_raii raw(PyObject_CallMethod(src, "read", "k", bufsize));
		if (!raw) ABORT;
		char *buffer;
        if (PyBytes_AsStringAndSize(raw.ptr(), &buffer, &bytes_read) == -1) ABORT;
        if (bytes_read > 0) {
            Py_BEGIN_ALLOW_THREADS;
            hr = dest->Write(buffer, (ULONG)bytes_read, &bytes_written);
            Py_END_ALLOW_THREADS;
            if (hr == STG_E_MEDIUMFULL) { PyErr_SetString(WPDError, "Cannot write to device as it is full"); ABORT; }
            if (hr == STG_E_ACCESSDENIED) { PyErr_SetExcFromWindowsErr(WPDError, ERROR_ACCESS_DENIED); ABORT; }
            if (hr == STG_E_WRITEFAULT) { PyErr_SetString(WPDError, "Cannot write to file as there was a disk I/O error"); ABORT; }
            if (FAILED(hr)) { hresult_set_exc("Cannot write to file", hr); ABORT; }
            if (bytes_written != bytes_read) { PyErr_SetString(WPDError, "Writing to file failed, not all bytes were written"); ABORT; }
            total_written += bytes_written;
            if (callback != NULL) { pyobject_raii r(PyObject_CallFunction(callback, "kK", total_written, size)); }
        }
        if (bytes_read == 0) { break; }
#undef ABORT
    }
    Py_BEGIN_ALLOW_THREADS;
    hr = dest->Commit(STGC_DEFAULT);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to write data to file, commit failed", hr); return NULL; }
    if (callback != NULL) Py_XDECREF(PyObject_CallFunction(callback, "kK", total_written, size));

	com_wchar_raii newid;
    Py_BEGIN_ALLOW_THREADS;
    hr = dest->GetObjectID(newid.unsafe_address());
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get id of newly created file", hr); return NULL; }

    return get_object_properties(devprops, properties, newid.ptr());

} // }}}

} // namespace wpd
