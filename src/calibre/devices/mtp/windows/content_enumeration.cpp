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
_pump_waiting_messages() {
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
	PROPVARIANT ts = {0};
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
    PyThreadState *thread_state;
    PyObject *callback;

	void release_python_gil() { if (thread_state == NULL) thread_state = PyEval_SaveThread(); }
    void acquire_python_gil() { PyEval_RestoreThread(thread_state); thread_state = NULL; }

	void do_one_object(CComPtr<IPortableDeviceValues> &properties) {
		com_wchar_raii property;
		if (!SUCCEEDED(properties->GetStringValue(WPD_OBJECT_ID, property.unsafe_address()))) return;
		pyobject_raii temp(PyUnicode_FromWideChar(property.ptr(), -1));
		if (!temp) { PyErr_Clear(); return; }
		pyobject_raii obj(PyDict_GetItem(this->items, temp.ptr()));
		if (!obj) {
			obj.attach(Py_BuildValue("{s:O}", "id", temp.ptr()));
			if (!obj) { PyErr_Clear(); return; }
			if (PyDict_SetItem(this->items, temp.ptr(), obj.ptr()) != 0) { PyErr_Clear(); return; }
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
		acquire_python_gil();

		for (DWORD i = 0; i < num; i++) {
			CComPtr<IPortableDeviceValues> properties;
			if (SUCCEEDED(values->GetAt(i, &properties))) do_one_object(properties);
		}

		release_python_gil();
	}


public:
	GetBulkPropertiesCallback() : items(NULL), subfolders(NULL), level(0), complete(INVALID_HANDLE_VALUE), self_ref(0), thread_state(NULL), callback(NULL) {}
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
		items = NULL; subfolders = NULL; level = 0; complete = INVALID_HANDLE_VALUE; callback = NULL; thread_state = NULL;
	}

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
		release_python_gil();
		DWORD wait_result = MsgWaitForMultipleObjects(1, &complete, FALSE, seconds * 1000, QS_ALLEVENTS);
		acquire_python_gil();
		return wait_result;
	}

	int pump_waiting_messages() {
		release_python_gil();
		int pump_result = _pump_waiting_messages();
		acquire_python_gil();
		return pump_result;
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

    while (!PyErr_Occurred()) {
		DWORD wait_result = bulk_properties_callback->wait_for_messages();

        if (wait_result == WAIT_OBJECT_0) {
            break; // Event was signalled, bulk operation complete
        } else if (wait_result == WAIT_OBJECT_0 + 1) { // Messages need to be dispatched
            int pump_result = bulk_properties_callback->pump_waiting_messages();
            if (pump_result == 1) PyErr_SetString(PyExc_RuntimeError, "Application has been asked to quit.");
        } else if (wait_result == WAIT_TIMEOUT) {
            // 60 seconds with no updates, looks bad
            PyErr_SetString(WPDError, "The device seems to have hung.");
        } else if (wait_result == WAIT_ABANDONED_0) {
            // This should never happen
            PyErr_SetString(WPDError, "An unknown error occurred (mutex abandoned)");
        } else {
            // The wait failed for some reason
            PyErr_SetFromWindowsErr(0);
        }
    }
	bulk_properties_callback->end_processing();
    if (PyErr_Occurred()) {
        bulk_properties->Cancel(guid_context);
        bulk_properties_callback->pump_waiting_messages();
    }
    return PyErr_Occurred() ? false : true;
}

// }}}

// find_objects_in() {{{
static bool
find_objects_in(CComPtr<IPortableDeviceContent> &content, CComPtr<IPortableDevicePropVariantCollection> &object_ids, const wchar_t *parent_id) {
    /*
     * Find all children of the object identified by parent_id.
     * The child ids are put into object_ids. Returns False if any errors
     * occurred (also sets the python exception).
     */
    IEnumPortableDeviceObjectIDs *children;
    HRESULT hr = S_OK, hr2 = S_OK;
    PWSTR child_ids[10];
    DWORD fetched, i;
    PROPVARIANT pv;
    bool ok = true;

    PropVariantInit(&pv);
    pv.vt      = VT_LPWSTR;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->EnumObjects(0, parent_id, NULL, &children);
    Py_END_ALLOW_THREADS;

    if (FAILED(hr)) {hresult_set_exc("Failed to get children from device", hr); ok = false; goto end;}

    hr = S_OK;

    while (hr == S_OK) {
        Py_BEGIN_ALLOW_THREADS;
        hr = children->Next(10, child_ids, &fetched);
        Py_END_ALLOW_THREADS;
        if (SUCCEEDED(hr)) {
            for(i = 0; i < fetched; i++) {
                pv.pwszVal = child_ids[i];
                hr2 = object_ids->Add(&pv);
                pv.pwszVal = NULL;
                if (FAILED(hr2)) { hresult_set_exc("Failed to add child ids to propvariantcollection", hr2); break; }
            }
            for (i = 0; i < fetched; i++) { CoTaskMemFree(child_ids[i]); child_ids[i] = NULL; }
            if (FAILED(hr2) || !ok) { ok = false; goto end; }
        }
    }

end:
    if (children != NULL) children->Release();
    PropVariantClear(&pv);
    return ok;
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
    PROPVARIANT pv;
    HRESULT hr;
    CComPtr<IPortableDeviceProperties> devprops;

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); return false; }

    CComPtr<IPortableDeviceKeyCollection> properties(create_filesystem_properties_collection());
    if (!properties) return false;

    hr = object_ids->GetCount(&num);
    if (FAILED(hr)) { hresult_set_exc("Failed to get object id count", hr); return false; }

    for (DWORD i = 0; i < num; i++) {
        bool ok = false;
        PropVariantInit(&pv);
        hr = object_ids->GetAt(i, &pv);
		pyobject_raii recurse;
        if (SUCCEEDED(hr) && pv.pwszVal != NULL) {
            pyobject_raii item(get_object_properties(devprops, properties, pv.pwszVal));
            if (item) {
				PyObject_Print(item.ptr(), stdout, 0);
				printf("\n");
                pyobject_raii r(PyObject_CallFunction(callback, "OI", item.ptr(), level));
                PyDict_SetItem(ans, PyDict_GetItemString(item.ptr(), "id"), item.ptr());
                if (r && PyObject_IsTrue(r.ptr())) recurse.attach(item.detach());
                ok = true;
            }
        } else hresult_set_exc("Failed to get item from IPortableDevicePropVariantCollection", hr);

        PropVariantClear(&pv);
        if (!ok) return false;
        if (recurse) {
            if (PyList_Append(subfolders, PyDict_GetItemString(recurse.ptr(), "id")) == -1) ok = false;
        }
        if (!ok) return false;
    }
    return true;
}
// }}}

static IPortableDeviceValues* create_object_properties(const wchar_t *parent_id, const wchar_t *name, const GUID content_type, unsigned PY_LONG_LONG size) { // {{{
    IPortableDeviceValues *values = NULL;
    HRESULT hr;
    BOOL ok = FALSE;
	PROPVARIANT timestamp = {0};
	SYSTEMTIME  systemtime;
	GetLocalTime(&systemtime);
	timestamp.vt = VT_DATE;
	if (!SystemTimeToVariantTime(&systemtime, &timestamp.date)) {
		LONG err = GetLastError();
		hr = HRESULT_FROM_WIN32(err);
		hresult_set_exc("Failed to convert system time to variant time", hr); goto end;
	}

    hr = CoCreateInstance(CLSID_PortableDeviceValues, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&values));
    if (FAILED(hr)) { hresult_set_exc("Failed to create values interface", hr); goto end; }

    hr = values->SetStringValue(WPD_OBJECT_PARENT_ID, parent_id);
    if (FAILED(hr)) { hresult_set_exc("Failed to set parent_id value", hr); goto end; }

    hr = values->SetStringValue(WPD_OBJECT_NAME, name);
    if (FAILED(hr)) { hresult_set_exc("Failed to set name value", hr); goto end; }

    hr = values->SetStringValue(WPD_OBJECT_ORIGINAL_FILE_NAME, name);
    if (FAILED(hr)) { hresult_set_exc("Failed to set original_file_name value", hr); goto end; }

    hr = values->SetGuidValue(WPD_OBJECT_FORMAT, WPD_OBJECT_FORMAT_UNSPECIFIED);
    if (FAILED(hr)) { hresult_set_exc("Failed to set object_format value", hr); goto end; }

    hr = values->SetGuidValue(WPD_OBJECT_CONTENT_TYPE, content_type);
    if (FAILED(hr)) { hresult_set_exc("Failed to set content_type value", hr); goto end; }

	hr = values->SetValue(WPD_OBJECT_DATE_CREATED, &timestamp);
	if (FAILED(hr)) { hresult_set_exc("Failed to set created timestamp", hr); goto end; }
	hr = values->SetValue(WPD_OBJECT_DATE_MODIFIED, &timestamp);
	if (FAILED(hr)) { hresult_set_exc("Failed to set modified timestamp", hr); goto end; }

    if (!IsEqualGUID(WPD_CONTENT_TYPE_FOLDER, content_type)) {
        hr = values->SetUnsignedLargeIntegerValue(WPD_OBJECT_SIZE, size);
        if (FAILED(hr)) { hresult_set_exc("Failed to set size value", hr); goto end; }
    }

    ok = TRUE;

end:
    if (!ok && values != NULL) { values->Release(); values = NULL; }
    return values;
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

    if (!find_objects_in(content, object_ids, parent_id)) return false;

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

PyObject* wpd::get_file(IPortableDevice *device, const wchar_t *object_id, PyObject *dest, PyObject *callback) { // {{{
    IPortableDeviceContent *content = NULL;
    IPortableDeviceResources *resources = NULL;
    IPortableDeviceProperties *devprops = NULL;
    IPortableDeviceValues *values = NULL;
    IPortableDeviceKeyCollection *properties = NULL;
    IStream *stream = NULL;
    HRESULT hr;
    DWORD bufsize = 4096;
    char *buf = NULL;
    ULONG bytes_read = 0, total_read = 0;
    BOOL ok = FALSE;
    PyObject *res = NULL;
    ULONGLONG filesize = 0;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Properties(&devprops);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&properties));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create filesystem properties collection", hr); goto end; }
    hr = properties->Add(WPD_OBJECT_SIZE);
    if (FAILED(hr)) { hresult_set_exc("Failed to add filesize property to properties collection", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = devprops->GetValues(object_id, properties, &values);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get filesize for object", hr); goto end; }
    hr = values->GetUnsignedLargeIntegerValue(WPD_OBJECT_SIZE, &filesize);
    if (FAILED(hr)) { hresult_set_exc("Failed to get filesize from values collection", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = content->Transfer(&resources);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create resources interface", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = resources->GetStream(object_id, WPD_RESOURCE_DEFAULT, STGM_READ, &bufsize, &stream);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {
        if (HRESULT_FROM_WIN32(ERROR_BUSY) == hr) {
            PyErr_SetString(WPDFileBusy, "Object is in use");
        } else hresult_set_exc("Failed to create stream interface to read from object", hr);
        goto end;
    }

    buf = (char *)calloc(bufsize+10, 1);
    if (buf == NULL) { PyErr_NoMemory(); goto end; }

    while (TRUE) {
        bytes_read = 0;
        Py_BEGIN_ALLOW_THREADS;
        hr = stream->Read(buf, bufsize, &bytes_read);
        Py_END_ALLOW_THREADS;
        total_read = total_read + bytes_read;
        if (hr == STG_E_ACCESSDENIED) {
            PyErr_SetString(PyExc_IOError, "Read access is denied to this object"); break;
        } else if (SUCCEEDED(hr)) {
            if (bytes_read > 0) {
                res = PyObject_CallMethod(dest, "write", "y#", buf, bytes_read);
                if (res == NULL) break;
                Py_DECREF(res); res = NULL;
                if (callback != NULL) Py_XDECREF(PyObject_CallFunction(callback, "kK", total_read, filesize));
            }
        } else { hresult_set_exc("Failed to read file from device", hr); break; }

        if (bytes_read == 0) {
            ok = TRUE;
            Py_XDECREF(PyObject_CallMethod(dest, "flush", NULL));
            break;
        }
    }

    if (ok && total_read != filesize) {
        ok = FALSE;
        PyErr_SetString(WPDError, "Failed to read all data from file");
    }

end:
    if (content != NULL) content->Release();
    if (devprops != NULL) devprops->Release();
    if (resources != NULL) resources->Release();
    if (stream != NULL) stream->Release();
    if (values != NULL) values->Release();
    if (properties != NULL) properties->Release();
    if (buf != NULL) free(buf);
    if (!ok) return NULL;
    Py_RETURN_NONE;
} // }}}

PyObject* wpd::create_folder(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name) { // {{{
    IPortableDeviceContent *content = NULL;
    IPortableDeviceValues *values = NULL;
    IPortableDeviceProperties *devprops = NULL;
    IPortableDeviceKeyCollection *properties = NULL;
    wchar_t *newid = NULL;
    PyObject *ans = NULL;
    HRESULT hr;

    values = create_object_properties(parent_id, name, WPD_CONTENT_TYPE_FOLDER, 0);
    if (values == NULL) goto end;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); goto end; }

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->CreateObjectWithPropertiesOnly(values, &newid);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr) || newid == NULL) { hresult_set_exc("Failed to create folder", hr); goto end; }

    ans = get_object_properties(devprops, properties, newid);
end:
    if (content != NULL) content->Release();
    if (values != NULL) values->Release();
    if (devprops != NULL) devprops->Release();
    if (properties != NULL) properties->Release();
    if (newid != NULL) CoTaskMemFree(newid);
    return ans;

} // }}}

PyObject* wpd::delete_object(IPortableDevice *device, const wchar_t *object_id) { // {{{
    IPortableDeviceContent *content = NULL;
    HRESULT hr;
    BOOL ok = FALSE;
    PROPVARIANT pv;
    IPortableDevicePropVariantCollection *object_ids = NULL;

    PropVariantInit(&pv);
    pv.vt      = VT_LPWSTR;

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDevicePropVariantCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&object_ids));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create propvariantcollection", hr); goto end; }
    pv.pwszVal = (wchar_t*)object_id;
    hr = object_ids->Add(&pv);
    pv.pwszVal = NULL;
    if (FAILED(hr)) { hresult_set_exc("Failed to add device id to propvariantcollection", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    hr = content->Delete(PORTABLE_DEVICE_DELETE_NO_RECURSION, object_ids, NULL);
    if (hr == E_ACCESSDENIED) PyErr_SetString(WPDError, "Do not have permission to delete this object");
    else if (hr == HRESULT_FROM_WIN32(ERROR_DIR_NOT_EMPTY) || hr == HRESULT_FROM_WIN32(ERROR_INVALID_OPERATION)) PyErr_SetString(WPDError, "Cannot delete object as it has children");
    else if (hr == HRESULT_FROM_WIN32(ERROR_NOT_FOUND) || SUCCEEDED(hr)) ok = TRUE;
    else hresult_set_exc("Cannot delete object", hr);

end:
    PropVariantClear(&pv);
    if (content != NULL) content->Release();
    if (object_ids != NULL) object_ids->Release();
    if (!ok) return NULL;
    Py_RETURN_NONE;

} // }}}

PyObject* wpd::put_file(IPortableDevice *device, const wchar_t *parent_id, const wchar_t *name, PyObject *src, unsigned PY_LONG_LONG size, PyObject *callback) { // {{{
    IPortableDeviceContent *content = NULL;
    IPortableDeviceValues *values = NULL;
    IPortableDeviceProperties *devprops = NULL;
    IPortableDeviceKeyCollection *properties = NULL;
    IStream *temp = NULL;
    IPortableDeviceDataStream *dest = NULL;
    char *buf = NULL;
    wchar_t *newid = NULL;
    PyObject *ans = NULL, *raw;
    HRESULT hr;
    DWORD bufsize = 0;
    BOOL ok = FALSE;
    Py_ssize_t bytes_read = 0;
    ULONG bytes_written = 0, total_written = 0;

    values = create_object_properties(parent_id, name, WPD_CONTENT_TYPE_GENERIC_FILE, size);
    if (values == NULL) goto end;

    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); goto end; }

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->CreateObjectWithPropertiesAndData(values, &temp, &bufsize, NULL);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) {
        if (HRESULT_FROM_WIN32(ERROR_BUSY) == hr) {
            PyErr_SetString(WPDFileBusy, "Object is in use");
        } else hresult_set_exc("Failed to create stream interface to write to object", hr);
        goto end;
    }

    hr = temp->QueryInterface(IID_PPV_ARGS(&dest));
    if (FAILED(hr)) { hresult_set_exc("Failed to create IPortableDeviceStream", hr); goto end; }

    while(TRUE) {
        raw = PyObject_CallMethod(src, "read", "k", bufsize);
        if (raw == NULL) break;
        PyBytes_AsStringAndSize(raw, &buf, &bytes_read);
        if (bytes_read > 0) {
            Py_BEGIN_ALLOW_THREADS;
            hr = dest->Write(buf, (ULONG)bytes_read, &bytes_written);
            Py_END_ALLOW_THREADS;
            Py_DECREF(raw);
            if (hr == STG_E_MEDIUMFULL) { PyErr_SetString(WPDError, "Cannot write to device as it is full"); break; }
            if (hr == STG_E_ACCESSDENIED) { PyErr_SetString(WPDError, "Cannot write to file as access is denied"); break; }
            if (hr == STG_E_WRITEFAULT) { PyErr_SetString(WPDError, "Cannot write to file as there was a disk I/O error"); break; }
            if (FAILED(hr)) { hresult_set_exc("Cannot write to file", hr); break; }
            if (bytes_written != bytes_read) { PyErr_SetString(WPDError, "Writing to file failed, not all bytes were written"); break; }
            total_written += bytes_written;
            if (callback != NULL) Py_XDECREF(PyObject_CallFunction(callback, "kK", total_written, size));
        } else Py_DECREF(raw);
        if (bytes_read == 0) { ok = TRUE; break; }
    }
    if (!ok) {dest->Revert(); goto end;}
    Py_BEGIN_ALLOW_THREADS;
    hr = dest->Commit(STGC_DEFAULT);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to write data to file, commit failed", hr); goto end; }
    if (callback != NULL) Py_XDECREF(PyObject_CallFunction(callback, "kK", total_written, size));

    Py_BEGIN_ALLOW_THREADS;
    hr = dest->GetObjectID(&newid);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get id of newly created file", hr); goto end; }

    ans = get_object_properties(devprops, properties, newid);
end:
    if (content != NULL) content->Release();
    if (values != NULL) values->Release();
    if (devprops != NULL) devprops->Release();
    if (properties != NULL) properties->Release();
    if (temp != NULL) temp->Release();
    if (dest != NULL) dest->Release();
    if (newid != NULL) CoTaskMemFree(newid);
    return ans;

} // }}}

} // namespace wpd
