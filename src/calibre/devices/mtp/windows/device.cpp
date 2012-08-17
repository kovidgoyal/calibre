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
    PyObject *storage_id, *ans = NULL;
    wchar_t *storage;

    if (!PyArg_ParseTuple(args, "O", &storage_id)) return NULL;
    storage = unicode_to_wchar(storage_id);
    if (storage == NULL) return NULL;

    return wpd::get_filesystem(self->device, storage, self->bulk_properties);
} // }}}

static PyMethodDef Device_methods[] = {
    {"update_data", (PyCFunction)update_data, METH_VARARGS,
     "update_data() -> Reread the basic device data from the device (total, space, free space, storage locations, etc.)"
    },

    {"get_filesystem", (PyCFunction)py_get_filesystem, METH_VARARGS,
     "get_filesystem(storage_id) -> Get all files/folders on the storage identified by storage_id. Tries to use bulk operations when possible."
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

