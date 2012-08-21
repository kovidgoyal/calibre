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
    ADDPROP(WPD_OBJECT_SYNC_ID);
    ADDPROP(WPD_OBJECT_ISSYSTEM);
    ADDPROP(WPD_OBJECT_ISHIDDEN);
    ADDPROP(WPD_OBJECT_CAN_DELETE);
    ADDPROP(WPD_OBJECT_SIZE);

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
        pval = PyInt_FromSsize_t((Py_ssize_t)val);
        if (pval != NULL) {
            PyDict_SetItemString(dict, pykey, pval);
            Py_DECREF(pval);
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
    set_string_property(obj, WPD_OBJECT_NAME, "name", values);
    set_string_property(obj, WPD_OBJECT_SYNC_ID, "sync_id", values);
    set_string_property(obj, WPD_OBJECT_PERSISTENT_UNIQUE_ID, "persistent_id", values);

    set_bool_property(obj, WPD_OBJECT_ISHIDDEN, "is_hidden", values);
    set_bool_property(obj, WPD_OBJECT_CAN_DELETE, "can_delete", values);
    set_bool_property(obj, WPD_OBJECT_ISSYSTEM, "is_system", values);

    set_size_property(obj, WPD_OBJECT_SIZE, "size", values);
}

// }}}

// Bulk get filesystem {{{
class GetBulkCallback : public IPortableDevicePropertiesBulkCallback {

public:
    PyObject *items;
    HANDLE complete;
    ULONG self_ref;
    PyThreadState *thread_state;

    GetBulkCallback(PyObject *items_dict, HANDLE ev) : items(items_dict), complete(ev), self_ref(1), thread_state(NULL) {}
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
        PyObject *temp, *obj;
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

                    properties->Release(); properties = NULL;
                }
            } // end for loop
            this->thread_state = PyEval_SaveThread();
        }

        return S_OK;
    }

};

static PyObject* bulk_get_filesystem(IPortableDevice *device, IPortableDevicePropertiesBulk *bulk_properties, const wchar_t *storage_id, IPortableDevicePropVariantCollection *object_ids) {
    PyObject *folders = NULL;
    GUID guid_context = GUID_NULL;
    HANDLE ev = NULL;
    IPortableDeviceKeyCollection *properties;
    GetBulkCallback *callback = NULL;
    HRESULT hr;
    DWORD wait_result;
    int pump_result;
    BOOL ok = TRUE;

    ev = CreateEvent(NULL, FALSE, FALSE, NULL);
    if (ev == NULL) return PyErr_NoMemory();

    folders = PyDict_New();
    if (folders == NULL) {PyErr_NoMemory(); goto end;}

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    callback = new (std::nothrow) GetBulkCallback(folders, ev);
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
            if (pump_result == 1) { PyErr_SetString(PyExc_RuntimeError, "Application has been asked to quit."); ok = FALSE; break;}
        } else if (wait_result == WAIT_TIMEOUT) {
            // 60 seconds with no updates, looks bad
            PyErr_SetString(WPDError, "The device seems to have hung."); ok = FALSE; break;
        } else if (wait_result == WAIT_ABANDONED_0) {
            // This should never happen
            PyErr_SetString(WPDError, "An unknown error occurred (mutex abandoned)"); ok = FALSE; break;
        } else {
            // The wait failed for some reason
            PyErr_SetFromWindowsErr(0); ok = FALSE; break;
        }
    }
    PyEval_RestoreThread(callback->thread_state);
    if (!ok) {
        bulk_properties->Cancel(guid_context);
        pump_waiting_messages();
        Py_DECREF(folders); folders = NULL;
    } 
end:
    if (ev != NULL) CloseHandle(ev);
    if (properties != NULL) properties->Release();
    if (callback != NULL) callback->Release();

    return folders;
}

// }}}

// find_all_objects_in() {{{
static BOOL find_all_objects_in(IPortableDeviceContent *content, IPortableDevicePropVariantCollection *object_ids, const wchar_t *parent_id) {
    /*
     * Find all children of the object identified by parent_id, recursively.
     * The child ids are put into object_ids. Returns False if any errors
     * occurred (also sets the python exception).
     */
    IEnumPortableDeviceObjectIDs *children;
    HRESULT hr = S_OK, hr2 = S_OK;
    PWSTR child_ids[10];
    DWORD fetched, i;
    PROPVARIANT pv;
    BOOL ok = 1;

    PropVariantInit(&pv);
    pv.vt      = VT_LPWSTR;

    Py_BEGIN_ALLOW_THREADS;
    hr = content->EnumObjects(0, parent_id, NULL, &children);
    Py_END_ALLOW_THREADS;

    if (FAILED(hr)) {hresult_set_exc("Failed to get children from device", hr); ok = 0; goto end;}

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
                ok = find_all_objects_in(content, object_ids, child_ids[i]);
                if (!ok) break;
            }
            for (i = 0; i < fetched; i++) { CoTaskMemFree(child_ids[i]); child_ids[i] = NULL; }
            if (FAILED(hr2) || !ok) { ok = 0; goto end; }
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
    
    temp = wchar_to_unicode(object_id);
    if (temp == NULL) goto end;

    ans = PyDict_New();
    if (ans == NULL) { PyErr_NoMemory(); goto end; }
    if (PyDict_SetItemString(ans, "id", temp) != 0) { Py_DECREF(ans); ans = NULL; PyErr_NoMemory(); goto end; }

    set_properties(ans, values);
     
end:
    Py_XDECREF(temp);
    if (values != NULL) values->Release();
    return ans;
}

static PyObject* single_get_filesystem(IPortableDeviceContent *content, const wchar_t *storage_id, IPortableDevicePropVariantCollection *object_ids) {
    DWORD num, i;
    PROPVARIANT pv;
    HRESULT hr;
    BOOL ok = 1;
    PyObject *ans = NULL, *item = NULL;
    IPortableDeviceProperties *devprops = NULL;
    IPortableDeviceKeyCollection *properties = NULL;

    hr = content->Properties(&devprops);
    if (FAILED(hr)) { hresult_set_exc("Failed to get IPortableDeviceProperties interface", hr); goto end; }

    properties = create_filesystem_properties_collection();
    if (properties == NULL) goto end;

    hr = object_ids->GetCount(&num);
    if (FAILED(hr)) { hresult_set_exc("Failed to get object id count", hr); goto end; }

    ans = PyDict_New();
    if (ans == NULL) goto end;

    for (i = 0; i < num; i++) {
        ok = 0;
        PropVariantInit(&pv);
        hr = object_ids->GetAt(i, &pv);
        if (SUCCEEDED(hr) && pv.pwszVal != NULL) {
            item = get_object_properties(devprops, properties, pv.pwszVal);
            if (item != NULL) {
                PyDict_SetItem(ans, PyDict_GetItemString(item, "id"), item);
                Py_DECREF(item); item = NULL;
                ok = 1;
            }
        } else hresult_set_exc("Failed to get item from IPortableDevicePropVariantCollection", hr);
            
        PropVariantClear(&pv);
        if (!ok) { Py_DECREF(ans); ans = NULL; break; }
    }

end:
    if (devprops != NULL) devprops->Release();
    if (properties != NULL) properties->Release();

    return ans;
} 
// }}}

PyObject* wpd::get_filesystem(IPortableDevice *device, const wchar_t *storage_id, IPortableDevicePropertiesBulk *bulk_properties) { // {{{
    PyObject *folders = NULL;
    IPortableDevicePropVariantCollection *object_ids = NULL;
    IPortableDeviceContent *content = NULL;
    HRESULT hr;
    BOOL ok;
    
    Py_BEGIN_ALLOW_THREADS;
    hr = device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); goto end; }

    Py_BEGIN_ALLOW_THREADS;
    hr = CoCreateInstance(CLSID_PortableDevicePropVariantCollection, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&object_ids));
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create propvariantcollection", hr); goto end; }

    ok = find_all_objects_in(content, object_ids, storage_id);
    if (!ok) goto end;

    if (bulk_properties != NULL) folders = bulk_get_filesystem(device, bulk_properties, storage_id, object_ids);
    else folders = single_get_filesystem(content, storage_id, object_ids);

end:
    if (content != NULL) content->Release();
    if (object_ids != NULL) object_ids->Release();

    return folders;
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
        } else if (hr == S_OK || hr == S_FALSE) {
            if (bytes_read > 0) {
                res = PyObject_CallMethod(dest, "write", "s#", buf, bytes_read);
                if (res == NULL) break;
                Py_DECREF(res); res = NULL;
                if (callback != NULL) Py_XDECREF(PyObject_CallFunction(callback, "kK", total_read, filesize));
            }
        } else { hresult_set_exc("Failed to read file from device", hr); break; }

        if (hr == S_FALSE || bytes_read < bufsize) { 
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

} // namespace wpd
