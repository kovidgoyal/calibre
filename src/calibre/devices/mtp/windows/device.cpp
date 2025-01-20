/*
 * device.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace wpd;
// Device.__init__() {{{
static void
dealloc(Device* self)
{
	self->pnp_id.release();
    if (self->bulk_properties) self->bulk_properties.Release();

    if (self->device) {
        Py_BEGIN_ALLOW_THREADS;
        self->device->Close();
		self->device.Release();
        Py_END_ALLOW_THREADS;
    }

	self->device_information.release();
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static int
init(Device *self, PyObject *args, PyObject *kwds)
{
    int ret = -1;
    if (!PyArg_ParseTuple(args, "O&", py_to_wchar_no_none, &self->pnp_id)) return -1;
    self->bulk_properties.Release();
    CComPtr<IPortableDeviceValues> client_information = get_client_information();
    if (client_information) {
        self->device = open_device(self->pnp_id.ptr(), client_information);
        if (self->device) {
            self->device_information.attach(get_device_information(self->device, self->bulk_properties));
            if (self->device_information) ret = 0;
        }
    }
    return ret;
}

// }}}

// update_device_data() {{{
static PyObject*
update_data(Device *self, PyObject *args) {
    PyObject *di = NULL;
    CComPtr<IPortableDevicePropertiesBulk> bulk_properties;
    di = get_device_information(self->device, bulk_properties);
    if (di == NULL) return NULL;
    self->device_information.attach(di);
    Py_RETURN_NONE;
} // }}}

// get_filesystem() {{{
static PyObject*
py_get_filesystem(Device *self, PyObject *args) {
    PyObject *callback;
	wchar_raii storage;

    if (!PyArg_ParseTuple(args, "O&O", py_to_wchar_no_none, &storage, &callback)) return NULL;
    if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback is not a callable"); return NULL; }
    return wpd::get_filesystem(self->device, storage.ptr(), self->bulk_properties, callback);
} // }}}

// get_file() {{{
static PyObject*
py_get_file(Device *self, PyObject *args) {
    PyObject *stream, *callback = NULL;
    wchar_raii object;

    if (!PyArg_ParseTuple(args, "O&O|O", py_to_wchar, &object, &stream, &callback)) return NULL;
    if (callback == NULL || !PyCallable_Check(callback)) callback = NULL;
    return wpd::get_file(self->device, object.ptr(), stream, callback);
} // }}}

// list_folder_by_name() {{{

static PyObject*
list_folder_by_name(Device *self, PyObject *args) {
    wchar_raii parent_id; PyObject *names;
    CComPtr<IPortableDeviceContent> content;
    HRESULT hr; bool found = false;

    Py_BEGIN_ALLOW_THREADS;
    hr = self->device->Content(&content);
    Py_END_ALLOW_THREADS;
    if (FAILED(hr)) { hresult_set_exc("Failed to create content interface", hr); return NULL; }


    if (!PyArg_ParseTuple(args, "O&O!", py_to_wchar, &parent_id, &PyTuple_Type, &names)) return NULL;
    for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(names); i++) {
        PyObject *k = PyTuple_GET_ITEM(names, i);
        if (!PyUnicode_Check(k)) { PyErr_SetString(PyExc_TypeError, "names must contain only unicode strings"); return NULL; }
        pyobject_raii l(PyObject_CallMethod(k, "lower", NULL)); if (!l) return NULL;
        pyobject_raii object_id(wpd::find_in_parent(content, self->bulk_properties, parent_id.ptr(), l.ptr()));
        if (!object_id) {
            if (PyErr_Occurred()) return NULL;
            Py_RETURN_NONE;
        }
        if (!py_to_wchar_(object_id.ptr(), &parent_id)) return NULL;
        found = true;
    }
    if (!found) Py_RETURN_NONE;
    return wpd::list_folder(content, self->bulk_properties, parent_id.ptr());
} // }}}

// create_folder() {{{
static PyObject*
py_create_folder(Device *self, PyObject *args) {
    wchar_raii parent_id, name;
    if (!PyArg_ParseTuple(args, "O&O&", py_to_wchar, &parent_id, py_to_wchar, &name)) return NULL;
    return wpd::create_folder(self->device, parent_id.ptr(), name.ptr());
} // }}}

// delete_object() {{{
static PyObject*
py_delete_object(Device *self, PyObject *args) {
    wchar_raii object_id;

    if (!PyArg_ParseTuple(args, "O&", py_to_wchar, &object_id)) return NULL;
    return wpd::delete_object(self->device, object_id.ptr());
} // }}}

// put_file() {{{
static PyObject*
py_put_file(Device *self, PyObject *args) {
    PyObject *stream, *callback = NULL;
    wchar_raii parent_id, name;
    unsigned long long size;

    if (!PyArg_ParseTuple(args, "O&O&OK|O", py_to_wchar, &parent_id, py_to_wchar, &name, &stream, &size, &callback)) return NULL;
    if (callback == NULL || !PyCallable_Check(callback)) callback = NULL;
    return wpd::put_file(self->device, parent_id.ptr(), name.ptr(), stream, size, callback);
} // }}}

static PyMethodDef Device_methods[] = {
    {"update_data", (PyCFunction)update_data, METH_VARARGS,
     "update_data() -> Reread the basic device data from the device (total, space, free space, storage locations, etc.)"
    },

    {"get_filesystem", (PyCFunction)py_get_filesystem, METH_VARARGS,
     "get_filesystem(storage_id, callback) -> Get all files/folders on the storage identified by storage_id. Tries to use bulk operations when possible. callback must be a callable that is called as (object, level). It is called with every found object. If the callback returns False and the object is a folder, it is not recursed into."
    },

    {"list_folder_by_name", (PyCFunction)list_folder_by_name, METH_VARARGS,
     "list_folder_by_name(parent_id, names) -> List the folder specified by names (a tuple of name components) relative to parent_id from the device. Return None or a list of entries."
    },

    {"get_file", (PyCFunction)py_get_file, METH_VARARGS,
     "get_file(object_id, stream, callback=None) -> Get the file identified by object_id from the device. The file is written to the stream object, which must be a file like object. If callback is not None, it must be a callable that accepts two arguments: (bytes_read, total_size). It will be called after each chunk is read from the device. Note that it can be called multiple times with the same values."
    },

    {"create_folder", (PyCFunction)py_create_folder, METH_VARARGS,
     "create_folder(parent_id, name) -> Create a folder. Returns the folder metadata."
    },

    {"delete_object", (PyCFunction)py_delete_object, METH_VARARGS,
     "delete_object(object_id) -> Delete the object identified by object_id. Note that trying to delete a non-empty folder will raise an error."
    },

    {"put_file", (PyCFunction)py_put_file, METH_VARARGS,
     "put_file(parent_id, name, stream, size_in_bytes, callback=None) -> Copy a file from the stream object, creating a new file on the device with parent identified by parent_id. Returns the file metadata of the newly created file. callback should be a callable that accepts two argument: (bytes_written, total_size). It will be called after each chunk is written to the device. Note that it can be called multiple times with the same arguments."
    },

    {NULL}
};

// Device.data {{{
static PyObject *
Device_data(Device *self, void *closure) {
	PyObject *ans = self->device_information.ptr();
	Py_INCREF(ans); return ans;
} // }}}


static PyGetSetDef Device_getsetters[] = {
    {(char *)"data",
     (getter)Device_data, NULL,
     (char *)"The basic device information.",
     NULL},

    {NULL}  /* Sentinel */
};


PyTypeObject wpd::DeviceType = { // {{{
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "wpd.Device",
    /* tp_basicsize      */ sizeof(Device),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)dealloc,
    /* tp_print          */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_compare        */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,
    /* tp_doc            */ "Device",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ Device_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ Device_getsetters,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ (initproc)init,
    /* tp_alloc          */ 0,
    /* tp_new            */ 0,
}; // }}}
