/*
 * libmtp.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define UNICODE
#include <Python.h>

#include <stdlib.h>
#include <libmtp.h>

#include "devices.h"

// Macros and utilities {{{
static PyObject *MTPError = NULL;

#define ENSURE_DEV(rval) \
    if (self->device == NULL) { \
        PyErr_SetString(MTPError, "This device has not been initialized."); \
        return rval; \
    }

#define ENSURE_STORAGE(rval) \
    if (self->device->storage == NULL) { \
        PyErr_SetString(MTPError, "The device has no storage information."); \
        return rval; \
    }

// Storage types
#define ST_Undefined            0x0000
#define ST_FixedROM             0x0001
#define ST_RemovableROM         0x0002
#define ST_FixedRAM             0x0003
#define ST_RemovableRAM         0x0004

// Storage Access capability
#define AC_ReadWrite            0x0000
#define AC_ReadOnly             0x0001
#define AC_ReadOnly_with_Object_Deletion    0x0002


typedef struct {
    PyObject *obj;
    PyObject *extra;
    PyThreadState *state;
} ProgressCallback;

static int report_progress(uint64_t const sent, uint64_t const total, void const *const data) {
    PyObject *res;
    ProgressCallback *cb;

    cb = (ProgressCallback *)data;
    if (cb->obj != NULL) {
        PyEval_RestoreThread(cb->state);
        res = PyObject_CallFunction(cb->obj, "KK", (unsigned long long)sent, (unsigned long long)total);
        Py_XDECREF(res);
        cb->state = PyEval_SaveThread();
    }
    return 0;
}

static void dump_errorstack(LIBMTP_mtpdevice_t *dev, PyObject *list) {
    LIBMTP_error_t *stack;
    PyObject *err;

    for(stack = LIBMTP_Get_Errorstack(dev); stack != NULL; stack=stack->next) {
        err = Py_BuildValue("is", stack->errornumber, stack->error_text);
        if (err == NULL) break;
        PyList_Append(list, err);
        Py_DECREF(err);
    }

    LIBMTP_Clear_Errorstack(dev);
}

static uint16_t data_to_python(void *params, void *priv, uint32_t sendlen, unsigned char *data, uint32_t *putlen) {
    PyObject *res;
    ProgressCallback *cb;
    uint16_t ret = LIBMTP_HANDLER_RETURN_OK;

    cb = (ProgressCallback *)priv;
    *putlen = sendlen;
    PyEval_RestoreThread(cb->state);
    res = PyObject_CallMethod(cb->extra, "write", "s#", data, (Py_ssize_t)sendlen);
    if (res == NULL) {
        ret = LIBMTP_HANDLER_RETURN_ERROR;
        *putlen = 0;
        PyErr_Print();
    } else Py_DECREF(res);

    cb->state = PyEval_SaveThread();
    return ret;
}

static uint16_t data_from_python(void *params, void *priv, uint32_t wantlen, unsigned char *data, uint32_t *gotlen) {
    PyObject *res;
    ProgressCallback *cb;
    char *buf = NULL;
    Py_ssize_t len = 0;
    uint16_t ret = LIBMTP_HANDLER_RETURN_ERROR;

    *gotlen = 0;

    cb = (ProgressCallback *)priv;
    PyEval_RestoreThread(cb->state);
    res = PyObject_CallMethod(cb->extra, "read", "k", (unsigned long)wantlen);
    if (res != NULL && PyBytes_AsStringAndSize(res, &buf, &len) != -1 && len <= wantlen) {
        memcpy(data, buf, len);
        *gotlen = len;
        ret = LIBMTP_HANDLER_RETURN_OK;
    } else PyErr_Print();

    Py_XDECREF(res);
    cb->state = PyEval_SaveThread();
    return ret;
}

static PyObject* build_file_metadata(LIBMTP_file_t *nf, uint32_t storage_id) {
    PyObject *ans = NULL;

    ans = Py_BuildValue("{s:s, s:k, s:k, s:k, s:K, s:O}", 
            "name", (unsigned long)nf->filename,
            "id", (unsigned long)nf->item_id,
            "parent_id", (unsigned long)nf->parent_id,
            "storage_id", (unsigned long)storage_id,
            "size", nf->filesize,
            "is_folder", (nf->filetype == LIBMTP_FILETYPE_FOLDER) ? Py_True : Py_False
    );

    return ans;
}

static PyObject* file_metadata(LIBMTP_mtpdevice_t *device, PyObject *errs, uint32_t item_id, uint32_t storage_id) {
    LIBMTP_file_t *nf;
    PyObject *ans = NULL;

    Py_BEGIN_ALLOW_THREADS;
    nf = LIBMTP_Get_Filemetadata(device, item_id);
    Py_END_ALLOW_THREADS;
    if (nf == NULL) dump_errorstack(device, errs);
    else {
        ans = build_file_metadata(nf, storage_id);
        LIBMTP_destroy_file_t(nf);
    }
    return ans;
}
// }}}

// Device object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    LIBMTP_mtpdevice_t *device;
    PyObject *ids;
    PyObject *friendly_name;
    PyObject *manufacturer_name;
    PyObject *model_name;
    PyObject *serial_number;
    PyObject *device_version;

} Device;

// Device.__init__() {{{
static void
Device_dealloc(Device* self)
{
    if (self->device != NULL) {
        Py_BEGIN_ALLOW_THREADS;
        LIBMTP_Release_Device(self->device);
        Py_END_ALLOW_THREADS;
    }
    self->device = NULL;

    Py_XDECREF(self->ids); self->ids = NULL;
    Py_XDECREF(self->friendly_name); self->friendly_name = NULL;
    Py_XDECREF(self->manufacturer_name); self->manufacturer_name = NULL;
    Py_XDECREF(self->model_name); self->model_name = NULL;
    Py_XDECREF(self->serial_number); self->serial_number = NULL;
    Py_XDECREF(self->device_version); self->device_version = NULL;

    self->ob_type->tp_free((PyObject*)self);
}

static int
Device_init(Device *self, PyObject *args, PyObject *kwds)
{
    unsigned long busnum;
    unsigned char devnum;
    unsigned short vendor_id, product_id;
    PyObject *usb_serialnum;
    char *vendor, *product, *friendly_name, *manufacturer_name, *model_name, *serial_number, *device_version;
    LIBMTP_raw_device_t *rawdevs = NULL, rdev;
    int numdevs, c;
    LIBMTP_mtpdevice_t *dev = NULL;
    LIBMTP_error_number_t err;

    if (!PyArg_ParseTuple(args, "kBHHssO", &busnum, &devnum, &vendor_id, &product_id, &vendor, &product, &usb_serialnum)) return -1;

    // We have to build and search the rawdevice list instead of creating a
    // rawdevice directly as otherwise, dynamic bug flag assignment in libmtp
    // does not work
    Py_BEGIN_ALLOW_THREADS;
    err = LIBMTP_Detect_Raw_Devices(&rawdevs, &numdevs);
    Py_END_ALLOW_THREADS;
    if (err == LIBMTP_ERROR_NO_DEVICE_ATTACHED) { PyErr_SetString(MTPError, "No raw devices found"); return -1; }
    if (err == LIBMTP_ERROR_CONNECTING) { PyErr_SetString(MTPError, "There has been an error connecting"); return -1; }
    if (err == LIBMTP_ERROR_MEMORY_ALLOCATION) { PyErr_NoMemory(); return -1; }
    if (err != LIBMTP_ERROR_NONE) { PyErr_SetString(MTPError, "Failed to detect raw MTP devices"); return -1; }

    for (c = 0; c < numdevs; c++) {
        rdev = rawdevs[c];
        if (rdev.bus_location == (uint32_t)busnum && rdev.devnum == (uint8_t)devnum) {
            Py_BEGIN_ALLOW_THREADS;
            dev = LIBMTP_Open_Raw_Device_Uncached(&rdev);
            Py_END_ALLOW_THREADS;
            if (dev == NULL) { free(rawdevs); PyErr_SetString(MTPError, "Unable to open raw device."); return -1; }
            break;
        }
    }

    if (rawdevs != NULL) free(rawdevs);
    if (dev == NULL) { PyErr_Format(MTPError, "No device with busnum=%lu and devnum=%u found", busnum, devnum); return -1; }

    self->device = dev;
    self->ids = Py_BuildValue("kBHHO", busnum, devnum, vendor_id, product_id, usb_serialnum);
    if (self->ids == NULL) return -1;

    Py_BEGIN_ALLOW_THREADS;
    friendly_name = LIBMTP_Get_Friendlyname(self->device);
    manufacturer_name = LIBMTP_Get_Manufacturername(self->device);
    model_name = LIBMTP_Get_Modelname(self->device);
    serial_number = LIBMTP_Get_Serialnumber(self->device);
    device_version = LIBMTP_Get_Deviceversion(self->device);
    Py_END_ALLOW_THREADS;

    if (friendly_name != NULL) {
        self->friendly_name = PyUnicode_FromString(friendly_name);
        free(friendly_name);
    }
    if (self->friendly_name == NULL) { self->friendly_name = Py_None; Py_INCREF(Py_None); }

    if (manufacturer_name != NULL) {
        self->manufacturer_name = PyUnicode_FromString(manufacturer_name);
        free(manufacturer_name);
    }
    if (self->manufacturer_name == NULL) { self->manufacturer_name = Py_None; Py_INCREF(Py_None); }

    if (model_name != NULL) {
        self->model_name = PyUnicode_FromString(model_name);
        free(model_name);
    }
    if (self->model_name == NULL) { self->model_name = Py_None; Py_INCREF(Py_None); }

    if (serial_number != NULL) {
        self->serial_number = PyUnicode_FromString(serial_number);
        free(serial_number);
    }
    if (self->serial_number == NULL) { self->serial_number = Py_None; Py_INCREF(Py_None); }

    if (device_version != NULL) {
        self->device_version = PyUnicode_FromString(device_version);
        free(device_version);
    }
    if (self->device_version == NULL) { self->device_version = Py_None; Py_INCREF(Py_None); }

    return 0;
}
// }}}

// Device.friendly_name {{{
static PyObject *
Device_friendly_name(Device *self, void *closure) {
    Py_INCREF(self->friendly_name); return self->friendly_name;
} // }}}

// Device.manufacturer_name {{{
static PyObject *
Device_manufacturer_name(Device *self, void *closure) {
    Py_INCREF(self->manufacturer_name); return self->manufacturer_name;
} // }}}

// Device.model_name {{{
static PyObject *
Device_model_name(Device *self, void *closure) {
    Py_INCREF(self->model_name); return self->model_name;
} // }}}

// Device.serial_number {{{
static PyObject *
Device_serial_number(Device *self, void *closure) {
    Py_INCREF(self->serial_number); return self->serial_number;
} // }}}

// Device.device_version {{{
static PyObject *
Device_device_version(Device *self, void *closure) {
    Py_INCREF(self->device_version); return self->device_version;
} // }}}

// Device.ids {{{
static PyObject *
Device_ids(Device *self, void *closure) {
    Py_INCREF(self->ids); return self->ids;
} // }}}

// Device.update_storage_info() {{{
static PyObject*
Device_update_storage_info(Device *self, PyObject *args) {
    ENSURE_DEV(NULL);
    if (LIBMTP_Get_Storage(self->device, LIBMTP_STORAGE_SORTBY_NOTSORTED) < 0) {
        PyErr_SetString(MTPError, "Failed to get storage info for device.");
        return NULL;
    }
    Py_RETURN_NONE;
}
// }}}

// Device.storage_info {{{
static PyObject *
Device_storage_info(Device *self, void *closure) {
    PyObject *ans, *loc;
    LIBMTP_devicestorage_t *storage;
    int ro = 0;
    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    ans = PyList_New(0);
    if (ans == NULL) { PyErr_NoMemory(); return NULL; }

    for (storage = self->device->storage; storage != NULL; storage = storage->next) {
        ro = 0;
        // Check if read only storage
        if (storage->StorageType == ST_FixedROM || storage->StorageType == ST_RemovableROM || (storage->id & 0x0000FFFFU) == 0x00000000U || storage->AccessCapability == AC_ReadOnly || storage->AccessCapability == AC_ReadOnly_with_Object_Deletion) ro = 1;

        loc = Py_BuildValue("{s:k,s:O,s:K,s:K,s:K,s:s,s:s,s:O}", 
                "id", (unsigned long)storage->id, 
                "removable", ((storage->StorageType == ST_RemovableRAM) ? Py_True : Py_False),
                "capacity", (unsigned long long)storage->MaxCapacity,
                "freespace_bytes", (unsigned long long)storage->FreeSpaceInBytes,
                "freespace_objects", (unsigned long long)storage->FreeSpaceInObjects,
                "name", storage->StorageDescription,
                "volume_id", storage->VolumeIdentifier,
                "rw", (ro) ? Py_False : Py_True
        );

        if (loc == NULL) return NULL; 
        if (PyList_Append(ans, loc) != 0) return NULL;
        Py_DECREF(loc);

    }

    return ans;
} // }}}

// Device.get_filesystem {{{

static int recursive_get_files(LIBMTP_mtpdevice_t *dev, uint32_t storage_id, uint32_t parent_id, PyObject *ans, PyObject *errs) {
    LIBMTP_file_t *f, *files;
    PyObject *entry;
    int ok = 1;

    Py_BEGIN_ALLOW_THREADS;
    files = LIBMTP_Get_Files_And_Folders(dev, storage_id, parent_id);
    Py_END_ALLOW_THREADS;

    if (files == NULL) return ok;

    for (f = files; ok && f != NULL; f = f->next) {
        entry = build_file_metadata(f, storage_id);
        if (entry == NULL) { ok = 0; }
        else {
            if (PyList_Append(ans, entry) != 0) { ok = 0; }
            Py_DECREF(entry); 
        }

        if (ok && f->filetype == LIBMTP_FILETYPE_FOLDER) {
            if (!recursive_get_files(dev, storage_id, f->item_id, ans, errs)) {
                ok = 0; 
            }
        }
    }

    // Release memory
    f = files;
    while (f != NULL) {
        files = f; f = f->next; LIBMTP_destroy_file_t(files);
    }

    return ok;
}

static PyObject *
Device_get_filesystem(Device *self, PyObject *args) {
    PyObject *ans, *errs;
    unsigned long storage_id;
    int ok = 0;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    if (!PyArg_ParseTuple(args, "k", &storage_id)) return NULL; 
    ans = PyList_New(0);
    errs = PyList_New(0);
    if (errs == NULL || ans == NULL) { PyErr_NoMemory(); return NULL; }

    LIBMTP_Clear_Errorstack(self->device);
    ok = recursive_get_files(self->device, (uint32_t)storage_id, 0, ans, errs);
    dump_errorstack(self->device, errs);
    if (!ok) {
        Py_DECREF(ans);
        Py_DECREF(errs);
        return NULL;
    }

    return Py_BuildValue("NN", ans, errs);

} // }}}

// Device.get_file {{{
static PyObject *
Device_get_file(Device *self, PyObject *args) {
    PyObject *stream, *callback = NULL, *errs;
    ProgressCallback cb;
    unsigned long fileid;
    int ret;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);


    if (!PyArg_ParseTuple(args, "kO|O", &fileid, &stream, &callback)) return NULL; 
    errs = PyList_New(0);
    if (errs == NULL) { PyErr_NoMemory(); return NULL; }
    if (callback == NULL || !PyCallable_Check(callback)) callback = NULL;

    cb.obj = callback; cb.extra = stream;
    Py_XINCREF(callback); Py_INCREF(stream);
    cb.state = PyEval_SaveThread();
    ret = LIBMTP_Get_File_To_Handler(self->device, (uint32_t)fileid, data_to_python, &cb, report_progress, &cb);
    PyEval_RestoreThread(cb.state);
    Py_XDECREF(callback); Py_DECREF(stream);

    if (ret != 0) { 
        dump_errorstack(self->device, errs);
    }
    Py_XDECREF(PyObject_CallMethod(stream, "flush", NULL));
    return Py_BuildValue("ON", (ret == 0) ? Py_True : Py_False, errs);

} // }}}

// Device.put_file {{{
static PyObject *
Device_put_file(Device *self, PyObject *args) {
    PyObject *stream, *callback = NULL, *errs, *fo = NULL;
    ProgressCallback cb;
    unsigned long parent_id, storage_id;
    unsigned long long filesize;
    int ret;
    char *name;
    LIBMTP_file_t f;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    if (!PyArg_ParseTuple(args, "kksOK|O", &storage_id, &parent_id, &name, &stream, &filesize, &callback)) return NULL; 
    errs = PyList_New(0);
    if (errs == NULL) { PyErr_NoMemory(); return NULL; }
    if (callback == NULL || !PyCallable_Check(callback)) callback = NULL;

    cb.obj = callback; cb.extra = stream;
    f.parent_id = (uint32_t)parent_id; f.storage_id = (uint32_t)storage_id; f.item_id = 0; f.filename = name; f.filetype = LIBMTP_FILETYPE_UNKNOWN; f.filesize = (uint64_t)filesize;
    Py_XINCREF(callback); Py_INCREF(stream);
    cb.state = PyEval_SaveThread();
    ret = LIBMTP_Send_File_From_Handler(self->device, data_from_python, &cb, &f, report_progress, &cb);
    PyEval_RestoreThread(cb.state);
    Py_XDECREF(callback); Py_DECREF(stream);

    if (ret != 0) dump_errorstack(self->device, errs);
    else fo = file_metadata(self->device, errs, f.item_id, storage_id);
    if (fo == NULL) { fo = Py_None; Py_INCREF(fo); }

    return Py_BuildValue("NN", fo, errs);

} // }}}

// Device.delete_object {{{
static PyObject *
Device_delete_object(Device *self, PyObject *args) {
    PyObject *errs;
    unsigned long id;
    int res;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    if (!PyArg_ParseTuple(args, "k", &id)) return NULL;
    errs = PyList_New(0);
    if (errs == NULL) { PyErr_NoMemory(); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    res = LIBMTP_Delete_Object(self->device, (uint32_t)id);
    Py_END_ALLOW_THREADS;
    if (res != 0) dump_errorstack(self->device, errs);

    return Py_BuildValue("ON", (res == 0) ? Py_True : Py_False, errs);
} // }}}

// Device.create_folder {{{
static PyObject *
Device_create_folder(Device *self, PyObject *args) {
    PyObject *errs, *fo = NULL;
    unsigned long storage_id, parent_id;
    uint32_t folder_id;
    char *name;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    if (!PyArg_ParseTuple(args, "kks", &storage_id, &parent_id, &name)) return NULL;
    errs = PyList_New(0);
    if (errs == NULL) { PyErr_NoMemory(); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    folder_id = LIBMTP_Create_Folder(self->device, name, (uint32_t)parent_id, (uint32_t)storage_id);
    Py_END_ALLOW_THREADS;

    if (folder_id == 0) dump_errorstack(self->device, errs);
    else fo = file_metadata(self->device, errs, folder_id, storage_id);
    if (fo == NULL) { fo = Py_None; Py_INCREF(fo); }

    return Py_BuildValue("NN", fo, errs);
} // }}}

static PyMethodDef Device_methods[] = {
    {"update_storage_info", (PyCFunction)Device_update_storage_info, METH_VARARGS,
     "update_storage_info() -> Reread the storage info from the device (total, space, free space, storage locations, etc.)"
    },

    {"get_filesystem", (PyCFunction)Device_get_filesystem, METH_VARARGS,
     "get_filesystem(storage_id) -> Get the list of files and folders on the device in storage_id. Returns files, errors."
    },

    {"get_file", (PyCFunction)Device_get_file, METH_VARARGS,
     "get_file(fileid, stream, callback=None) -> Get the file specified by fileid from the device. stream must be a file-like object. The file will be written to it. callback works the same as in get_filelist(). Returns ok, errs, where errs is a list of errors (if any)."
    },

    {"put_file", (PyCFunction)Device_put_file, METH_VARARGS,
     "put_file(storage_id, parent_id, filename, stream, size, callback=None) -> Put a file on the device. The file is read from stream. It is put inside the folder identified by parent_id on the storage identified by storage_id. Use parent_id=0 to put it in the root. stream must be a file-like object. size is the size in bytes of the data in stream. callback works the same as in get_filelist(). Returns fileinfo, errs, where errs is a list of errors (if any), and fileinfo is a file information dictionary, as returned by get_filelist(). fileinfo will be None if case or errors."
    },

    {"create_folder", (PyCFunction)Device_create_folder, METH_VARARGS,
     "create_folder(storage_id, parent_id, name) -> Create a folder named name under parent parent_id (use 0 for root) in the storage identified by storage_id. Returns folderinfo, errors, where folderinfo is the same dict as returned by get_folderlist(), it will be None if there are errors."
    },

    {"delete_object", (PyCFunction)Device_delete_object, METH_VARARGS,
     "delete_object(id) -> Delete the object identified by id from the device. Can be used to delete files, folders, etc. Returns ok, errs."
    },


    {NULL}  /* Sentinel */
};

static PyGetSetDef Device_getsetters[] = {
    {(char *)"friendly_name", 
     (getter)Device_friendly_name, NULL,
     (char *)"The friendly name of this device, can be None.",
     NULL},

    {(char *)"manufacturer_name", 
     (getter)Device_manufacturer_name, NULL,
     (char *)"The manufacturer name of this device, can be None.",
     NULL},

    {(char *)"model_name", 
     (getter)Device_model_name, NULL,
     (char *)"The model name of this device, can be None.",
     NULL},

    {(char *)"serial_number", 
     (getter)Device_serial_number, NULL,
     (char *)"The serial number of this device, can be None.",
     NULL},

    {(char *)"device_version", 
     (getter)Device_device_version, NULL,
     (char *)"The device version of this device, can be None.",
     NULL},

    {(char *)"ids", 
     (getter)Device_ids, NULL,
     (char *)"The ids of the device (busnum, devnum, vendor_id, product_id, usb_serialnum)",
     NULL},

    {(char *)"storage_info",
     (getter)Device_storage_info, NULL,
     (char *)"Information about the storage locations on the device. Returns a list of dictionaries where each dictionary corresponds to the LIBMTP_devicestorage_struct.",
     NULL},

    {NULL}  /* Sentinel */
};

static PyTypeObject DeviceType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "libmtp.Device",            /*tp_name*/
    sizeof(Device),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Device_dealloc, /*tp_dealloc*/
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
    (initproc)Device_init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

// }}} End Device object definition

static PyObject *
set_debug_level(PyObject *self, PyObject *args) {
    int level;
    if (!PyArg_ParseTuple(args, "i", &level)) return NULL;
    LIBMTP_Set_Debug(level);
    Py_RETURN_NONE;
}


static PyObject *
is_mtp_device(PyObject *self, PyObject *args) {
    int busnum, devnum, ans = 0;

    if (!PyArg_ParseTuple(args, "ii", &busnum, &devnum)) return NULL;

    /*
     * LIBMTP_Check_Specific_Device does not seem to work at least on my linux
     * system. Need to investigate why later. Most devices are in the device
     * table so this is not terribly important.
     */
    /* LIBMTP_Set_Debug(LIBMTP_DEBUG_ALL); */
    /* printf("Calling check: %d %d\n", busnum, devnum); */
    Py_BEGIN_ALLOW_THREADS;
    ans = LIBMTP_Check_Specific_Device(busnum, devnum);
    Py_END_ALLOW_THREADS;

    if (ans) Py_RETURN_TRUE;

    Py_RETURN_FALSE;

}

static PyObject*
known_devices(PyObject *self, PyObject *args) {
    PyObject *ans, *d;
    size_t i;

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    for (i = 0; ; i++) {
        if (calibre_mtp_device_table[i].vendor == NULL && calibre_mtp_device_table[i].product == NULL && calibre_mtp_device_table[i].vendor_id == 0xffff) break;
        d = Py_BuildValue("(HH)", (unsigned short)calibre_mtp_device_table[i].vendor_id, (unsigned short)calibre_mtp_device_table[i].product_id);
        if (d == NULL) { Py_DECREF(ans); ans = NULL; break; }
        if (PyList_Append(ans, d) != 0) { Py_DECREF(d); Py_DECREF(ans); ans = NULL; PyErr_NoMemory(); break; }
        Py_DECREF(d);
    }

    return ans;
}

static PyMethodDef libmtp_methods[] = {
    {"set_debug_level", set_debug_level, METH_VARARGS,
        "set_debug_level(level)\n\nSet the debug level bit mask, see LIBMTP_DEBUG_* constants."
    },

    {"is_mtp_device", is_mtp_device, METH_VARARGS,
        "is_mtp_device(busnum, devnum)\n\nA probe is done and True returned if the probe succeeds. Note that probing can cause some devices to malfunction, and it is not very reliable, which is why we prefer to use the device database."
    },

    {"known_devices", known_devices, METH_VARARGS,
        "known_devices() -> Return the list of known (vendor_id, product_id) combinations."
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initlibmtp(void) {
    PyObject *m;

    DeviceType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DeviceType) < 0)
        return;
    
    m = Py_InitModule3("libmtp", libmtp_methods, "Interface to libmtp.");
    if (m == NULL) return;

    MTPError = PyErr_NewException("libmtp.MTPError", NULL, NULL);
    if (MTPError == NULL) return;
    PyModule_AddObject(m, "MTPError", MTPError);

    LIBMTP_Init();
    LIBMTP_Set_Debug(LIBMTP_DEBUG_NONE);

    Py_INCREF(&DeviceType);
    PyModule_AddObject(m, "Device", (PyObject *)&DeviceType);

    PyModule_AddStringMacro(m, LIBMTP_VERSION_STRING);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_NONE);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_PTP);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_PLST);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_USB);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_DATA);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_ALL);
}
