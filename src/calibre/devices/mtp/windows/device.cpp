/*
 * device.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

extern IPortableDevice* wpd::open_device(const wchar_t *pnp_id, IPortableDeviceValues *client_information);
extern IPortableDeviceValues* wpd::get_client_information();
extern PyObject* wpd::get_device_information(IPortableDevice *device, IPortableDevicePropertiesBulk **pb);

using namespace wpd;
// Device.__init__() {{{
static void
dealloc(Device* self)
{
    if (self->pnp_id != NULL) free(self->pnp_id);
    self->pnp_id = NULL;

    if (self->bulk_properties != NULL) { self->bulk_properties->Release(); self->bulk_properties = NULL; }

    if (self->device != NULL) { 
        Py_BEGIN_ALLOW_THREADS;
        self->device->Close(); self->device->Release();
        self->device = NULL; 
        Py_END_ALLOW_THREADS;
    }

    if (self->client_information != NULL) { self->client_information->Release(); self->client_information = NULL; }

    Py_XDECREF(self->device_information); self->device_information = NULL;

    self->ob_type->tp_free((PyObject*)self);
}

static int
init(Device *self, PyObject *args, PyObject *kwds)
{
    PyObject *pnp_id;
    int ret = -1;

    if (!PyArg_ParseTuple(args, "O", &pnp_id)) return -1;

    self->pnp_id = unicode_to_wchar(pnp_id);
    if (self->pnp_id == NULL) return -1;

    self->bulk_properties = NULL;

    self->client_information = get_client_information();
    if (self->client_information != NULL) {
        self->device = open_device(self->pnp_id, self->client_information);
        if (self->device != NULL) {
            self->device_information = get_device_information(self->device, &(self->bulk_properties));
            if (self->device_information != NULL) {
                ret = 0;
            }

        }
    }

    return ret;
}

// }}}

// update_device_data() {{{
static PyObject*
update_data(Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *di = NULL;
    di = get_device_information(self->device, NULL);
    if (di == NULL) return NULL;
    Py_XDECREF(self->device_information); self->device_information = di;
    Py_RETURN_NONE;
} // }}}
 
// get_filesystem() {{{
static PyObject*
py_get_filesystem(Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *storage_id, *ret;
    wchar_t *storage;

    if (!PyArg_ParseTuple(args, "O", &storage_id)) return NULL;
    storage = unicode_to_wchar(storage_id);
    if (storage == NULL) return NULL;

    ret = wpd::get_filesystem(self->device, storage, self->bulk_properties);
    free(storage);
    return ret;
} // }}}

// get_file() {{{
static PyObject*
py_get_file(Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *object_id, *stream, *callback = NULL, *ret;
    wchar_t *object;

    if (!PyArg_ParseTuple(args, "OO|O", &object_id, &stream, &callback)) return NULL;
    object = unicode_to_wchar(object_id);
    if (object == NULL) return NULL;

    if (callback == NULL || !PyCallable_Check(callback)) callback = NULL;

    ret = wpd::get_file(self->device, object, stream, callback);
    free(object);
    return ret;
} // }}}

// create_folder() {{{
static PyObject*
py_create_folder(Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *pparent_id, *pname, *ret;
    wchar_t *parent_id, *name;

    if (!PyArg_ParseTuple(args, "OO", &pparent_id, &pname)) return NULL;
    parent_id = unicode_to_wchar(pparent_id);
    name = unicode_to_wchar(pname);
    if (parent_id == NULL || name == NULL) return NULL;

    ret = wpd::create_folder(self->device, parent_id, name);
    free(parent_id); free(name);
    return ret;
} // }}}

// delete_object() {{{
static PyObject*
py_delete_object(Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *pobject_id, *ret;
    wchar_t *object_id;

    if (!PyArg_ParseTuple(args, "O", &pobject_id)) return NULL;
    object_id = unicode_to_wchar(pobject_id);
    if (object_id == NULL) return NULL;

    ret =  wpd::delete_object(self->device, object_id);
    free(object_id);
    return ret;
} // }}}

static PyMethodDef Device_methods[] = {
    {"update_data", (PyCFunction)update_data, METH_VARARGS,
     "update_data() -> Reread the basic device data from the device (total, space, free space, storage locations, etc.)"
    },

    {"get_filesystem", (PyCFunction)py_get_filesystem, METH_VARARGS,
     "get_filesystem(storage_id) -> Get all files/folders on the storage identified by storage_id. Tries to use bulk operations when possible."
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

    {NULL}
};

// Device.data {{{
static PyObject *
Device_data(Device *self, void *closure) {
    Py_INCREF(self->device_information); return self->device_information;
} // }}}


static PyGetSetDef Device_getsetters[] = {
    {(char *)"data", 
     (getter)Device_data, NULL,
     (char *)"The basic device information.",
     NULL},

    {NULL}  /* Sentinel */
};


PyTypeObject wpd::DeviceType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "wpd.Device",            /*tp_name*/
    sizeof(Device),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Device",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    Device_methods,             /* tp_methods */
    0,             /* tp_members */
    Device_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

