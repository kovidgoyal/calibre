/*
 * lzma_binding.c
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#include "Python.h"
#include "Lzma2Dec.h"

static void *Alloc(void *p, size_t size) { p = p; return PyMem_Malloc(size); }
static void Free(void *p, void *address) { p = p; PyMem_Free(address); }
static ISzAlloc allocator = { Alloc, Free };
static const char* error_codes[18] = {
    "OK",
    "SZ_ERROR_DATA",
    "SZ_ERROR_MEM",
    "SZ_ERROR_CRC",
    "SZ_ERROR_UNSUPPORTED",
    "SZ_ERROR_PARAM",
    "SZ_ERROR_INPUT_EOF",
    "SZ_ERROR_OUTPUT_EOF",
    "SZ_ERROR_READ",
    "SZ_ERROR_WRITE",
    "SZ_ERROR_PROGRESS",
    "SZ_ERROR_FAIL",
    "SZ_ERROR_THREAD",
    "UNKNOWN", "UNKNOWN", "UNKNOWN",
    "SZ_ERROR_ARCHIVE",
    "SZ_ERROR_NO_ARCHIVE",
};
#define SET_ERROR(x) PyErr_SetString(LZMAError, ((x) > 0 && (x) < 17) ? error_codes[(x)] : "UNKNOWN")

static PyObject *LZMAError = NULL;
static UInt64 crc64_table[256];

static void init_crc_table() {
    static const UInt64 poly64 = (UInt64)(0xC96C5795D7870F42);
    for (size_t i = 0; i < 256; ++i) {
        UInt64 crc64 = i;
        for (size_t j = 0; j < 8; ++j) {
            if (crc64 & 1)
                crc64 = (crc64 >> 1) ^ poly64;
            else
                crc64 >>= 1;
        }
        crc64_table[i] = crc64;
    }
}

static PyObject *
crc64(PyObject *self, PyObject *args) {
    unsigned char *data = NULL;
    Py_ssize_t size = 0;
    UInt64 crc = 0;
    if (!PyArg_ParseTuple(args, "s#|K", &data, &size, &crc)) return NULL;
    crc = ~crc;
    for (size_t i = 0; i < size; ++i)
        crc = crc64_table[data[i] ^ (crc & 0xFF)] ^ (crc >> 8);

    return Py_BuildValue("K", ~crc);
}

static PyObject*
delta_decode(PyObject *self, PyObject *args) {
    PyObject *array = NULL, *histarray = NULL;
    unsigned char *data = NULL, pos = 0, *history = NULL;
    unsigned int distance = 0;
    Py_ssize_t datalen = 0;
    if (!PyArg_ParseTuple(args, "O!O!BB", &PyByteArray_Type, &array, &PyByteArray_Type, &histarray, &pos, &distance)) return NULL;
    if (PyByteArray_GET_SIZE(histarray) != 256) {
        PyErr_SetString(PyExc_TypeError, "histarray must be 256 bytes long");
        return NULL;
    }
    data = (unsigned char*)PyByteArray_AS_STRING(array); history = (unsigned char*)PyByteArray_AS_STRING(histarray);
    datalen = PyBytes_GET_SIZE(array);

    for (Py_ssize_t i = 0; i < datalen; i++) {
        data[i] += history[(unsigned char)(pos + distance)]; 
        history[pos--] = data[i];
    }
    return Py_BuildValue("B", pos);
}

static PyObject *
decompress2(PyObject *self, PyObject *args) {
    PyObject *read = NULL, *seek = NULL, *write = NULL, *rres = NULL;
    unsigned long bufsize = 0, bytes_written = 0, bytes_read = 0, inbuf_pos = 0, inbuf_len = 0, leftover = 0;
    unsigned char props = 0;
    char *inbuf = NULL, *outbuf = NULL;
    CLzma2Dec state;
    SRes res = 0;
    ELzmaStatus status = LZMA_STATUS_NOT_FINISHED;

    if (!PyArg_ParseTuple(args, "OOOBk", &read, &seek, &write, &props, &bufsize)) return NULL;
    
    Lzma2Dec_Construct(&state);
    res = Lzma2Dec_Allocate(&state, (Byte)props, &allocator);
    if (res == SZ_ERROR_MEM) { PyErr_NoMemory(); return NULL; }
    if (res != SZ_OK) { PyErr_SetString(PyExc_TypeError, "Incorrect stream properties"); goto exit; }
    inbuf = (char*)PyMem_Malloc(bufsize);
    outbuf = (char*)PyMem_Malloc(bufsize);
    if (!inbuf || !outbuf) {PyErr_NoMemory(); goto exit;}

    Lzma2Dec_Init(&state);

    while (status != LZMA_STATUS_FINISHED_WITH_MARK) {
        bytes_written = bufsize; bytes_read = inbuf_len - inbuf_pos;
        Py_BEGIN_ALLOW_THREADS;
        res = Lzma2Dec_DecodeToBuf(&state, (Byte*)outbuf, &bytes_written, (Byte*)(inbuf) + inbuf_pos, &bytes_read, LZMA_FINISH_ANY, &status);
        Py_END_ALLOW_THREADS;
        if (res != SZ_OK) { SET_ERROR(res); goto exit; }
        if (bytes_written > 0) {
            if(!PyObject_CallFunction(write, "s#", outbuf, bytes_written)) goto exit;
        }
        if (bytes_read > 0) inbuf_pos += bytes_read;
        if (status == LZMA_STATUS_NEEDS_MORE_INPUT) {
            leftover = inbuf_len - inbuf_pos;
            inbuf_pos = 0;
            if (!PyObject_CallFunction(seek, "ii", -leftover, SEEK_CUR)) goto exit;
            rres = PyObject_CallFunction(read, "n", bufsize);
            if (rres == NULL) goto exit;
            inbuf_len = PyBytes_GET_SIZE(rres);
            if (inbuf_len == 0) { PyErr_SetString(PyExc_ValueError, "LZMA2 block was truncated"); goto exit; }
            memcpy(inbuf, PyBytes_AS_STRING(rres), inbuf_len);
            Py_DECREF(rres); rres = NULL;
        } 
    }
    leftover = inbuf_len - inbuf_pos;
    if (leftover > 0) {
        if (!PyObject_CallFunction(seek, "ii", -leftover, SEEK_CUR)) goto exit;
    }


exit:
    Lzma2Dec_Free(&state, &allocator);
    PyMem_Free(inbuf); PyMem_Free(outbuf);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}

static PyMethodDef lzma_binding_methods[] = {
    {"decompress2", decompress2, METH_VARARGS,
        "Decompress an LZMA2 encoded block, of unknown compressed size (reads till LZMA2 EOS marker)"
    },

    {"crc64", crc64, METH_VARARGS,
        "crc64(bytes) -> CRC 64 for the provided python bytes object"
    },

    {"delta_decode", delta_decode, METH_VARARGS,
        "delta_decode(rawarray, histarray, pos, distance) -> Apply the delta decode filter to the bytearray rawarray"
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initlzma_binding(void) {
    PyObject *m = NULL;
    init_crc_table();
    LZMAError = PyErr_NewException("lzma_binding.error", NULL, NULL);
    if (!LZMAError) return;
    m = Py_InitModule3("lzma_binding", lzma_binding_methods,
    "Bindings to the LZMA (de)compression C code"
    );
    Py_INCREF(LZMAError);
    PyModule_AddObject(m, "error", LZMAError);
    PyModule_AddIntMacro(m, SZ_OK);
    PyModule_AddIntMacro(m, SZ_ERROR_DATA);
    PyModule_AddIntMacro(m, SZ_ERROR_MEM);
    PyModule_AddIntMacro(m, SZ_ERROR_CRC);
    PyModule_AddIntMacro(m, SZ_ERROR_UNSUPPORTED);
    PyModule_AddIntMacro(m, SZ_ERROR_PARAM);
    PyModule_AddIntMacro(m, SZ_ERROR_INPUT_EOF);
    PyModule_AddIntMacro(m, SZ_ERROR_OUTPUT_EOF);
    PyModule_AddIntMacro(m, SZ_ERROR_READ);
    PyModule_AddIntMacro(m, SZ_ERROR_WRITE);
    PyModule_AddIntMacro(m, SZ_ERROR_PROGRESS);
    PyModule_AddIntMacro(m, SZ_ERROR_FAIL);
    PyModule_AddIntMacro(m, SZ_ERROR_THREAD);
    PyModule_AddIntMacro(m, SZ_ERROR_ARCHIVE);
    PyModule_AddIntMacro(m, SZ_ERROR_NO_ARCHIVE);

    if (m == NULL) return;
}
