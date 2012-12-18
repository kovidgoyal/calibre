/*
 * content_enumeration.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

#include <new>

#define ADDPROP(x) hr = properties->Add(x); if (FAILED(hr)) { hresult_set_exc("Failed to add property to filesystem properties collection", hr); properties->Release(); return NULL; }

namespace wpd {

static IPortableDeviceKeyCollection* create_filesystem_properties_collection() { // {{{
    IPortableDeviceKeyCollection *properties = NULL;
    HRESULT hr;

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDeviceKeyCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&properties));
    Py_END_ALLOW_THREADS;

    if (FAILED(hr)) { hresult_set_exc("Failed to create filesystem properties collection", hr); return NULL; }

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
    ADDPROP(WPD_OBJECT_DATE_MODIFIED);

    return properties;

} // }}}

// Convert properties from COM to python {{{
static void set_string_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, IPortableDeviceValues *properties) {
    HRESULT hr;
    wchar_t *property = NULL;
    PyObject *val;

    hr = properties->GetStringValue(key, &property);
    if (SUCCEEDED(hr)) {
        val = wchar_to_unicode(property);
        if (val != NULL) {
            PyDict_SetItemString(dict, pykey, val);
            Py_DECREF(val);
        }
        CoTaskMemFree(property);
    }
}

static void set_bool_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, IPortableDeviceValues *properties) {
    BOOL ok = 0;
    HRESULT hr;

    hr = properties->GetBoolValue(key, &ok);
    if (SUCCEEDED(hr)) 
        PyDict_SetItemString(dict, pykey, (ok)?Py_True:Py_False);
}

static void set_size_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, IPortableDeviceValues *properties) {
    ULONGLONG val = 0;
    HRESULT hr;
    PyObject *pval;

    hr = properties->GetUnsignedLargeIntegerValue(key, &val);

    if (SUCCEEDED(hr)) {
        pval = PyLong_FromUnsignedLongLong(val);
        if (pval != NULL) {
            PyDict_SetItemString(dict, pykey, pval);
            Py_DECREF(pval);
        }
    }
}

static void set_date_property(PyObject *dict, REFPROPERTYKEY key, const char *pykey, IPortableDeviceValues *properties) {
    FLOAT val = 0;
    SYSTEMTIME st;
    unsigned int microseconds;
    PyObject *t;

    if (SUCCEEDED(properties->GetFloatValue(key, &val))) {
        if (VariantTimeToSystemTime(val, &st)) {
            microseconds = 1000 * st.wMilliseconds;
            t = Py_BuildValue("H H H H H H I", (unsigned short)st.wYear,
                    (unsigned short)st.wMonth, (unsigned short)st.wDay,
                    (unsigned short)st.wHour, (unsigned short)st.wMinute,
                    (unsigned short)st.wSecond, microseconds);
            if (t != NULL) { PyDict_SetItemString(dict, pykey, t); Py_DECREF(t); }
        }
    }
}

static void set_content_type_property(PyObject *dict, IPortableDeviceValues *properties) {
    GUID guid = GUID_NULL;
    BOOL is_folder = 0;

    if (SUCCEEDED(properties->GetGuidValue(WPD_OBJECT_CONTENT_TYPE, &guid)) && IsEqualGUID(guid, WPD_CONTENT_TYPE_FOLDER)) is_folder = 1;
    PyDict_SetItemString(dict, "is_folder", (is_folder) ? Py_True : Py_False);
}

static void set_properties(PyObject *obj, IPortableDeviceValues *values) {
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

}

// }}}

// Bulk get filesystem {{{
class GetBulkCallback : public IPortableDevicePropertiesBulkCallback {

public:
    PyObject *items;
    PyObject *subfolders;
    unsigned int level;
    HANDLE complete;
    ULONG self_ref;
    PyThreadState *thread_state;
    PyObject *callback;

    GetBulkCallback(PyObject *items_dict, PyObject *subfolders, unsigned int level, HANDLE ev, PyObject* pycallback) : items(items_dict), subfolders(subfolders), level(level), complete(ev), self_ref(1), thread_state(NULL), callback(pycallback) {}
    ~GetBulkCallback() {}

    HRESULT __stdcall OnStart(REFGUID Context) { return S_OK; }

    HRESULT __stdcall OnEnd(REFGUID Context, HRESULT hrStatus) { SetEvent(this->complete); return S_OK; }

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
 
    HRESULT __stdcall OnProgress(REFGUID Context, IPortableDeviceValuesCollection* values) { 
        DWORD num = 0, i;
        wchar_t *property = NULL;
        IPortableDeviceValues *properties = NULL;
        PyObject *temp, *obj, *r;
        HRESULT hr;

        if (SUCCEEDED(values->GetCount(&num))) {
            PyEval_RestoreThread(this->thread_state);
            for (i = 0; i < num; i++) {
                hr = values->GetAt(i, &properties);
                if (SUCCEEDED(hr)) {

                    hr = properties->GetStringValue(WPD_OBJECT_ID, &property);
                    if (!SUCCEEDED(hr)) continue;
                    temp = wchar_to_unicode(property);
                    CoTaskMemFree(property); property = NULL;
                    if (temp == NULL) continue;
                    obj = PyDict_GetItem(this->items, temp);
                    if (obj == NULL) {
                        obj = Py_BuildValue("{s:O}", "id", temp);
                        if (obj == NULL) continue;
                        PyDict_SetItem(this->items, temp, obj);
                        Py_DECREF(obj); // We want a borrowed reference to obj
                    } 
                    Py_DECREF(temp);

                    set_properties(obj, properties);
                    r = PyObject_CallFunction(callback, "OI", obj, this->level);
                    if (r != NULL && PyObject_IsTrue(r)) {
                        PyList_Append(this->subfolders, PyDict_GetItemString(obj, "id"));
                    }
                    Py_XDECREF(r);

                    properties->Release(); properties = NULL;
                }
            } // end for loop
            this->thread_state = PyEval_SaveThread();
        }

        return S_OK;
    }

};

static bool bulk_get_filesystem(unsigned int level, IPortableDevice *device, IPortableDevicePropertiesBulk *bulk_properties, IPortableDevicePropVariantCollection *object_ids, PyObject *pycallback, PyObject *ans, PyObject *subfolders) {
    GUID guid_context = GUID_NULL;
    HANDLE ev = NULL;
    IPortableDeviceKeyCollection *properties;
    GetBulkCallback *callback = NULL;
    HRESULT hr;
    DWORD wait_result;
    int pump_result;
    bool ok = true;

    ev = CreateEvent(NULL, FALSE, FALSE, NULL);
    if (ev == NULL) {PyErr_NoMemory(); return false; }

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    callback = new (std::nothrow) GetBulkCallback(ans, subfolders, level, ev, pycallback);
    if (callback == NULL) { PyErr_NoMemory(); goto end; }

    hr = bulk_properties->QueueGetValuesByObjectList(object_ids, properties, callback, &guid_context);
    if (FAILED(hr)) { hresult_set_exc("Failed to queue bulk property retrieval", hr); goto end; }

    hr = bulk_properties->Start(guid_context);
    if (FAILED(hr)) { hresult_set_exc("Failed to start bulk operation", hr); goto end; }

    callback->thread_state = PyEval_SaveThread();
    while (TRUE) {
        wait_result = MsgWaitForMultipleObjects(1, &(callback->complete), FALSE, 60000, QS_ALLEVENTS);
        if (wait_result == WAIT_OBJECT_0) {
            break; // Event was signalled, bulk operation complete
        } else if (wait_result == WAIT_OBJECT_0 + 1) { // Messages need to be dispatched
            pump_result = pump_waiting_messages();
            if (pump_result == 1) { PyErr_SetString(PyExc_RuntimeError, "Application has been asked to quit."); ok = false; break;}
        } else if (wait_result == WAIT_TIMEOUT) {
            // 60 seconds with no updates, looks bad
            PyErr_SetString(WPDError, "The device seems to have hung."); ok = false; break;
        } else if (wait_result == WAIT_ABANDONED_0) {
            // This should never happen
            PyErr_SetString(WPDError, "An unknown error occurred (mutex abandoned)"); ok = false; break;
        } else {
            // The wait failed for some reason
            PyErr_SetFromWindowsErr(0); ok = FALSE; break;
        }
    }
    PyEval_RestoreThread(callback->thread_state);
    if (!ok) {
        bulk_properties->Cancel(guid_context);
        pump_waiting_messages();
    } 
end:
    if (ev != NULL) CloseHandle(ev);
    if (properties != NULL) properties->Release();
    if (callback != NULL) callback->Release();

    return ok;
}

// }}}

// find_objects_in() {{{
static bool find_objects_in(IPortableDeviceContent *content, IPortableDevicePropVariantCollection *object_ids, const wchar_t *parent_id) {
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

static PyObject* get_object_properties(IPortableDeviceProperties *devprops, IPortableDeviceKeyCollection *properties, const wchar_t *object_id) {
    IPortableDeviceValues *values = NULL;
    HRESULT hr;
    PyObject *ans = NULL, *temp = NULL;

    Py_BEGIN_ALLOW_THREADS;
    hr = devprops->GetValues(object_id, properties, &values);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to get properties for object", hr); goto end; }
    
    ans = Py_BuildValue("{s:N}", "id", wchar_to_unicode(object_id));
    if (ans == NULL) goto end;
    set_properties(ans, values);
     
end:
    Py_XDECREF(temp);
    if (values != NULL) values->Release();
    return ans;
}

static bool single_get_filesystem(unsigned int level, IPortableDeviceContent *content, IPortableDevicePropVariantCollection *object_ids, PyObject *callback, PyObject *ans, PyObject *subfolders) {
    DWORD num, i;
    PROPVARIANT pv;
    HRESULT hr;
    bool ok = true;
    PyObject *item = NULL, *r = NULL, *recurse = NULL;
    IPortableDeviceProperties *devprops = NULL;
    IPortableDeviceKeyCollection *properties = NULL;

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); goto end; }

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    hr = object_ids->GetCount(&num);
    if (FAILED(hr)) { hresult_set_exc("Failed to get object id count", hr); goto end; }

    for (i = 0; i < num; i++) {
        ok = false;
        recurse = NULL;
        PropVariantInit(&pv);
        hr = object_ids->GetAt(i, &pv);
        if (SUCCEEDED(hr) && pv.pwszVal != NULL) {
            item = get_object_properties(devprops, properties, pv.pwszVal);
            if (item != NULL) {
                r = PyObject_CallFunction(callback, "OI", item, level);
                if (r != NULL && PyObject_IsTrue(r)) recurse = item;
                Py_XDECREF(r);
                PyDict_SetItem(ans, PyDict_GetItemString(item, "id"), item);
                Py_DECREF(item); item = NULL;
                ok = true;
            }
        } else hresult_set_exc("Failed to get item from IPortableDevicePropVariantCollection", hr);
            
        PropVariantClear(&pv);
        if (!ok) break;
        if (recurse != NULL) {
            if (PyList_Append(subfolders, PyDict_GetItemString(recurse, "id")) == -1) ok = false;
        }
        if (!ok) break;
    }

end:
    if (devprops != NULL) devprops->Release();
    if (properties != NULL) properties->Release();

    return ok;
} 
// }}}

static IPortableDeviceValues* create_object_properties(const wchar_t *parent_id, const wchar_t *name, const GUID content_type, unsigned PY_LONG_LONG size) { // {{{
    IPortableDeviceValues *values = NULL;
    HRESULT hr;
    BOOL ok = FALSE;

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

    if (!IsEqualGUID(WPD_CONTENT_TYPE_FOLDER, content_type)) {
        hr = values->SetUnsignedLargeIntegerValue(WPD_OBJECT_SIZE, size);
        if (FAILED(hr)) { hresult_set_exc("Failed to set size value", hr); goto end; }
    }

    ok = TRUE;

end:
    if (!ok && values != NULL) { values->Release(); values = NULL; }
    return values;
} // }}}

static bool get_files_and_folders(unsigned int level, IPortableDevice *device, IPortableDeviceContent *content, IPortableDevicePropertiesBulk *bulk_properties, const wchar_t *parent_id, PyObject *callback, PyObject *ans) {
    bool ok = true;
    IPortableDevicePropVariantCollection *object_ids = NULL;
    PyObject *subfolders = NULL;
    HRESULT hr;

    subfolders = PyList_New(0);
    if (subfolders == NULL) { ok = false; goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDevicePropVariantCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&object_ids));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create propvariantcollection", hr); ok = false; goto end; }

    ok = find_objects_in(content, object_ids, parent_id);
    if (!ok) goto end;

    if (bulk_properties != NULL) ok = bulk_get_filesystem(level, device, bulk_properties, object_ids, callback, ans, subfolders);
    else ok = single_get_filesystem(level, content, object_ids, callback, ans, subfolders);
    if (!ok) goto end;

    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(subfolders); i++) { 
        const wchar_t *child_id = unicode_to_wchar(PyList_GET_ITEM(subfolders, i));
        if (child_id == NULL) { ok = false; break; }
        ok = get_files_and_folders(level+1, device, content, bulk_properties, child_id, callback, ans);
        if (!ok) break;
    }
end:
    if (object_ids != NULL) object_ids->Release();
    Py_XDECREF(subfolders);
    return ok;
}

PyObject* wpd::get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties, PyObject *callback) { // {{{
    PyObject *ans = NULL;
    IPortableDeviceContent *content = NULL;
    HRESULT hr;

    ans = PyDict_New();
    if (ans == NULL) return PyErr_NoMemory();
    
    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    if (!get_files_and_folders(0, device, content, bulk_properties, storage_id, callback, ans)) {
        Py_DECREF(ans); ans = NULL;
    }

end:
    if (content != NULL) content->Release();
    return ans;
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
                res = PyObject_CallMethod(dest, "write", "s#", buf, bytes_read);
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
