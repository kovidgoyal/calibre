/*
 * crc32.c
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#include <Python.h>
#include <zlib.h>

#define DEF_BUF_SIZE (16*1024)
/* The following parameters are copied from zutil.h, version 0.95 */
#define DEFLATED   8
#if MAX_MEM_LEVEL >= 8
#  define DEF_MEM_LEVEL 8
#else
#  define DEF_MEM_LEVEL  MAX_MEM_LEVEL
#endif


static PyTypeObject Comptype;

static PyObject *ZlibError = NULL;

typedef struct
{
    PyObject_HEAD
    z_stream zst;
    PyObject *unused_data;
    PyObject *unconsumed_tail;
    char eof;
    int is_initialised;
    PyObject *zdict;
} compobject;

static void
zlib_error(z_stream zst, int err, char *msg)
{
    const char *zmsg = Z_NULL;
    /* In case of a version mismatch, zst.msg won't be initialized.
       Check for this case first, before looking at zst.msg. */
    if (err == Z_VERSION_ERROR)
        zmsg = "library version mismatch";
    if (zmsg == Z_NULL)
        zmsg = zst.msg;
    if (zmsg == Z_NULL) {
        switch (err) {
        case Z_BUF_ERROR:
            zmsg = "incomplete or truncated stream";
            break;
        case Z_STREAM_ERROR:
            zmsg = "inconsistent stream state";
            break;
        case Z_DATA_ERROR:
            zmsg = "invalid input data";
            break;
        }
    }
    if (zmsg == Z_NULL)
        PyErr_Format(ZlibError, "Error %d %s", err, msg);
    else
        PyErr_Format(ZlibError, "Error %d %s: %.200s", err, msg, zmsg);
}

static compobject *
newcompobject(PyTypeObject *type)
{
    compobject *self;
    self = PyObject_New(compobject, type);
    if (self == NULL)
        return NULL;
    self->eof = 0;
    self->is_initialised = 0;
    self->zdict = NULL;
    self->unused_data = PyBytes_FromStringAndSize("", 0);
    if (self->unused_data == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    self->unconsumed_tail = PyBytes_FromStringAndSize("", 0);
    if (self->unconsumed_tail == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    return self;
}


static PyObject *
PyZlib_compressobj(PyObject *selfptr, PyObject *args)
{
    compobject *self = NULL;
    int level=Z_DEFAULT_COMPRESSION, method=DEFLATED;
    int wbits=MAX_WBITS, memLevel=DEF_MEM_LEVEL, strategy=Z_DEFAULT_STRATEGY, err;

    if (!PyArg_ParseTuple(args, "|iiiii:compressobj", &level, &method, &wbits,
                          &memLevel, &strategy))
        return NULL;

    self = newcompobject(&Comptype);
    if (self==NULL) return NULL;

    self->zst.zalloc = (alloc_func)Z_NULL;
    self->zst.zfree = (free_func)Z_NULL;
    self->zst.next_in = Z_NULL;
    self->zst.avail_in = 0;
    err = deflateInit2(&self->zst, level, method, wbits, memLevel, strategy);
    switch(err) {
    case (Z_OK):
        self->is_initialised = 1;
        return (PyObject*)self;
    case (Z_MEM_ERROR):
        Py_DECREF(self);
        PyErr_SetString(PyExc_MemoryError,
                        "Can't allocate memory for compression object");
        return NULL;
    case(Z_STREAM_ERROR):
        Py_DECREF(self);
        PyErr_SetString(PyExc_ValueError, "Invalid initialization option");
        return NULL;
    default:
        zlib_error(self->zst, err, "while creating compression object");
        Py_DECREF(self);
        return NULL;
    }
    return (PyObject*) self;
}

static void
Dealloc(compobject *self)
{
    Py_XDECREF(self->unused_data);
    Py_XDECREF(self->unconsumed_tail);
    Py_XDECREF(self->zdict);
    PyObject_Del(self);
}

static void
Comp_dealloc(compobject *self)
{
    if (self->is_initialised)
        deflateEnd(&self->zst);
    Dealloc(self);
}

static PyObject *
Compress_compress(compobject *self, PyObject *data_obj)
/*[clinic end generated code: output=5d5cd791cbc6a7f4 input=0d95908d6e64fab8]*/
{
    int err = 0, len = 0;
    unsigned int inplen = 0;
    unsigned int length = DEF_BUF_SIZE, new_length = 0;
    PyObject *RetVal = NULL;
    Py_buffer indata = {0};
    Byte *input = NULL;
    unsigned long start_total_out = 0;

	if (PyObject_GetBuffer(data_obj, &indata, PyBUF_SIMPLE) != 0) return NULL;
    input = indata.buf; len = indata.len;

    if ((size_t)len > UINT_MAX) {
        PyErr_SetString(PyExc_OverflowError, "Size does not fit in an unsigned int");
        goto done;
    }
    inplen = (unsigned int)len;

    if (!(RetVal = PyBytes_FromStringAndSize(NULL, length))) goto done;

    start_total_out = self->zst.total_out;
    self->zst.avail_in = inplen;
    self->zst.next_in = input;
    self->zst.avail_out = length;
    self->zst.next_out = (unsigned char *)PyBytes_AS_STRING(RetVal);

    Py_BEGIN_ALLOW_THREADS
    err = deflate(&(self->zst), Z_NO_FLUSH);
    Py_END_ALLOW_THREADS

    /* while Z_OK and the output buffer is full, there might be more output,
       so extend the output buffer and try again */
    while (err == Z_OK && self->zst.avail_out == 0) {
        if (length <= (UINT_MAX >> 1))
            new_length = length << 1;
        else
            new_length = UINT_MAX;
        if (_PyBytes_Resize(&RetVal, new_length) < 0) {
            Py_CLEAR(RetVal);
            goto done;
        }
        self->zst.next_out =
            (unsigned char *)PyBytes_AS_STRING(RetVal) + length;
        self->zst.avail_out = length;
        length = new_length;

        Py_BEGIN_ALLOW_THREADS
        err = deflate(&(self->zst), Z_NO_FLUSH);
        Py_END_ALLOW_THREADS
    }
    /* We will only get Z_BUF_ERROR if the output buffer was full but
       there wasn't more output when we tried again, so it is not an error
       condition.
    */

    if (err != Z_OK && err != Z_BUF_ERROR) {
        zlib_error(self->zst, err, "while compressing data");
        Py_CLEAR(RetVal);
        goto done;
    }
    if (_PyBytes_Resize(&RetVal, self->zst.total_out - start_total_out) < 0) {
        Py_CLEAR(RetVal);
    }

 done:
    if (indata.obj) PyBuffer_Release(&indata);
    return RetVal;
}

static PyObject *
Compress_flush(compobject *self, PyObject *args)
{
    int err = 0, mode=Z_FINISH;
    unsigned int length = DEF_BUF_SIZE, new_length = 0;
    PyObject *RetVal = NULL;
    unsigned long start_total_out = 0;

    if (!PyArg_ParseTuple(args, "|i:flush", &mode)) return NULL;

    /* Flushing with Z_NO_FLUSH is a no-op, so there's no point in
       doing any work at all; just return an empty string. */
    if (mode == Z_NO_FLUSH) {
        return PyBytes_FromStringAndSize(NULL, 0);
    }

    if (!(RetVal = PyBytes_FromStringAndSize(NULL, length)))
        return NULL;

    start_total_out = self->zst.total_out;
    self->zst.avail_in = 0;
    self->zst.avail_out = length;
    self->zst.next_out = (unsigned char *)PyBytes_AS_STRING(RetVal);

    Py_BEGIN_ALLOW_THREADS
    err = deflate(&(self->zst), mode);
    Py_END_ALLOW_THREADS

    /* while Z_OK and the output buffer is full, there might be more output,
       so extend the output buffer and try again */
    while (err == Z_OK && self->zst.avail_out == 0) {
        if (length <= (UINT_MAX >> 1))
            new_length = length << 1;
        else
            new_length = UINT_MAX;
        if (_PyBytes_Resize(&RetVal, new_length) < 0) {
            Py_CLEAR(RetVal);
            goto error;
        }
        self->zst.next_out =
            (unsigned char *)PyBytes_AS_STRING(RetVal) + length;
        self->zst.avail_out = length;
        length = new_length;

        Py_BEGIN_ALLOW_THREADS
        err = deflate(&(self->zst), mode);
        Py_END_ALLOW_THREADS
    }

    /* If mode is Z_FINISH, we also have to call deflateEnd() to free
       various data structures. Note we should only get Z_STREAM_END when
       mode is Z_FINISH, but checking both for safety*/
    if (err == Z_STREAM_END && mode == Z_FINISH) {
        err = deflateEnd(&(self->zst));
        if (err != Z_OK) {
            zlib_error(self->zst, err, "while finishing compression");
            Py_DECREF(RetVal);
            RetVal = NULL;
            goto error;
        }
        else
            self->is_initialised = 0;

        /* We will only get Z_BUF_ERROR if the output buffer was full
           but there wasn't more output when we tried again, so it is
           not an error condition.
        */
    } else if (err!=Z_OK && err!=Z_BUF_ERROR) {
        zlib_error(self->zst, err, "while flushing");
        Py_DECREF(RetVal);
        RetVal = NULL;
        goto error;
    }

    if (_PyBytes_Resize(&RetVal, self->zst.total_out - start_total_out) < 0) {
        Py_CLEAR(RetVal);
    }

 error:

    return RetVal;
}

static PyMethodDef comp_methods[] =
{
    {"compress", (PyCFunction)Compress_compress, METH_O, "compress(data) -- returns compressed data, dont forget to call flush when done."},

    {"flush", (PyCFunction)Compress_flush, METH_VARARGS, "flush([mode]) -- returns any remaining data"},

    {NULL}
};

static PyTypeObject Comptype = {
    PyVarObject_HEAD_INIT(0, 0)
    "zlib2.Compress",
    sizeof(compobject),
    0,
    (destructor)Comp_dealloc,       /*tp_dealloc*/
    0,                              /*tp_print*/
    0,                              /*tp_getattr*/
    0,                              /*tp_setattr*/
    0,                              /*tp_reserved*/
    0,                              /*tp_repr*/
    0,                              /*tp_as_number*/
    0,                              /*tp_as_sequence*/
    0,                              /*tp_as_mapping*/
    0,                              /*tp_hash*/
    0,                              /*tp_call*/
    0,                              /*tp_str*/
    0,                              /*tp_getattro*/
    0,                              /*tp_setattro*/
    0,                              /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,             /*tp_flags*/
    0,                              /*tp_doc*/
    0,                              /*tp_traverse*/
    0,                              /*tp_clear*/
    0,                              /*tp_richcompare*/
    0,                              /*tp_weaklistoffset*/
    0,                              /*tp_iter*/
    0,                              /*tp_iternext*/
    comp_methods,                   /*tp_methods*/
};


static PyObject *
zlib_crc32(PyObject *self, PyObject *args)
{
    int signed_val = 0, len = 0;
	unsigned int value = 0;
	unsigned char *buf = NULL;
    Py_buffer indata = {0};
    PyObject* obj = NULL;

	if(!PyArg_ParseTuple(args, "O|I:crc32", &obj, &value)) return NULL;
	if (PyObject_GetBuffer(obj, &indata, PyBUF_SIMPLE) != 0) return NULL;
    buf = indata.buf; len = indata.len;

    /* Releasing the GIL for very small buffers is inefficient
       and may lower performance */
    if (len > 1024*5) {
        Py_BEGIN_ALLOW_THREADS
        /* Avoid truncation of length for very large buffers. crc32() takes
           length as an unsigned int, which may be narrower than Py_ssize_t. */
        while ((size_t)len > UINT_MAX) {
            value = crc32(value, buf, UINT_MAX);
            buf += (size_t) UINT_MAX;
            len -= (size_t) UINT_MAX; 
        }   
        signed_val = crc32(value, buf, (unsigned int)len);
        Py_END_ALLOW_THREADS
    } else {
        signed_val = crc32(value, buf, len);
    } 
    if (indata.obj) PyBuffer_Release(&indata);
    return PyLong_FromUnsignedLong(signed_val & 0xffffffffU);
}   

static PyMethodDef methods[] = {
	{"crc32", zlib_crc32, METH_VARARGS,
		"crc32(data, [, state=0)\n\nCalculate crc32 for the given data starting from the given state."
	},
    {"compressobj", (PyCFunction)PyZlib_compressobj, METH_VARARGS, "Create compression object"},


    {NULL, NULL, 0, NULL}
};

CALIBRE_MODINIT_FUNC
initzlib2(void) {
    PyObject *m, *ver;
    Comptype.tp_new = PyType_GenericNew;
    if (PyType_Ready(&Comptype) < 0)
        return;
 
    m = Py_InitModule3("zlib2", methods,
    "Implementation of zlib compression with support for the buffer protocol, which is missing in Python2. Code taken from the Python3 zlib module"
    );
    if (m == NULL) return;
    PyModule_AddIntMacro(m, MAX_WBITS);
    PyModule_AddIntMacro(m, DEFLATED);
    PyModule_AddIntMacro(m, DEF_MEM_LEVEL);
    PyModule_AddIntMacro(m, DEF_BUF_SIZE);
    PyModule_AddIntMacro(m, Z_BEST_SPEED);
    PyModule_AddIntMacro(m, Z_BEST_COMPRESSION);
    PyModule_AddIntMacro(m, Z_DEFAULT_COMPRESSION);
    PyModule_AddIntMacro(m, Z_FILTERED);
    PyModule_AddIntMacro(m, Z_HUFFMAN_ONLY);
    PyModule_AddIntMacro(m, Z_DEFAULT_STRATEGY);

    PyModule_AddIntMacro(m, Z_FINISH);
    PyModule_AddIntMacro(m, Z_NO_FLUSH);
    PyModule_AddIntMacro(m, Z_SYNC_FLUSH);
    PyModule_AddIntMacro(m, Z_FULL_FLUSH);

    ver = PyUnicode_FromString(ZLIB_VERSION);
    if (ver != NULL)
        PyModule_AddObject(m, "ZLIB_VERSION", ver);

    ver = PyUnicode_FromString(zlibVersion());
    if (ver != NULL)
        PyModule_AddObject(m, "ZLIB_RUNTIME_VERSION", ver);

    ZlibError = PyErr_NewException("zlib2.error", NULL, NULL);
    if (ZlibError != NULL) {
        Py_INCREF(ZlibError);
        PyModule_AddObject(m, "error", ZlibError);
    }   
}
