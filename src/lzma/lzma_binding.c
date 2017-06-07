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
#include "Lzma2Enc.h"
#define UNUSED_VAR(x) (void)x;

static void *Alloc(void *p, size_t size) { UNUSED_VAR(p); return PyMem_Malloc(size); }
static void Free(void *p, void *address) { UNUSED_VAR(p); PyMem_Free(address); }
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

typedef struct {
    ISeqInStream stream;
    PyObject *read;
    PyThreadState **thread_state;
} InStream;

typedef struct {
    ISeqOutStream stream;
    PyObject *write;
    PyThreadState **thread_state;
} OutStream;

typedef struct {
    ICompressProgress progress;
    PyObject *callback;
    PyThreadState **thread_state;
} Progress;

static PyObject *LZMAError = NULL;

// Utils {{{
static UInt64 crc64_table[256];

static void init_crc_table() {
    static const UInt64 poly64 = (UInt64)(0xC96C5795D7870F42);
    size_t i, j;
    for (i = 0; i < 256; ++i) {
        UInt64 crc64 = i;
        for (j = 0; j < 8; ++j) {
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
    size_t i;
    if (!PyArg_ParseTuple(args, "s#|K", &data, &size, &crc)) return NULL;
    crc = ~crc;
    for (i = 0; i < (size_t)size; ++i)
        crc = crc64_table[data[i] ^ (crc & 0xFF)] ^ (crc >> 8);

    return Py_BuildValue("K", ~crc);
}

static PyObject*
delta_decode(PyObject *self, PyObject *args) {
    PyObject *array = NULL, *histarray = NULL;
    unsigned char *data = NULL, pos = 0, *history = NULL;
    unsigned int distance = 0;
    Py_ssize_t datalen = 0, i;
    if (!PyArg_ParseTuple(args, "O!O!BB", &PyByteArray_Type, &array, &PyByteArray_Type, &histarray, &pos, &distance)) return NULL;
    if (PyByteArray_GET_SIZE(histarray) != 256) {
        PyErr_SetString(PyExc_TypeError, "histarray must be 256 bytes long");
        return NULL;
    }
    data = (unsigned char*)PyByteArray_AS_STRING(array); history = (unsigned char*)PyByteArray_AS_STRING(histarray);
    datalen = PyBytes_GET_SIZE(array);

    for (i = 0; i < datalen; i++) {
        data[i] += history[(unsigned char)(pos + distance)]; 
        history[pos--] = data[i];
    }
    return Py_BuildValue("B", pos);
}
// }}}

// LZMA2 decompress {{{
static PyObject *
decompress2(PyObject *self, PyObject *args) {
    PyObject *read = NULL, *seek = NULL, *write = NULL, *rres = NULL;
    SizeT bufsize = 0, bytes_written = 0, bytes_read = 0, inbuf_pos = 0, inbuf_len = 0;
    Py_ssize_t leftover = 0;
    unsigned char props = 0;
    char *inbuf = NULL, *outbuf = NULL;
    CLzma2Dec state;
    SRes res = SZ_OK;
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
        if (bytes_read) {
            Py_BEGIN_ALLOW_THREADS;
            res = Lzma2Dec_DecodeToBuf(&state, (Byte*)outbuf, &bytes_written, (Byte*)(inbuf) + inbuf_pos, &bytes_read, LZMA_FINISH_ANY, &status);
            Py_END_ALLOW_THREADS;
        } else { res = SZ_OK; bytes_written = 0; status = LZMA_STATUS_NEEDS_MORE_INPUT; }
        if (res != SZ_OK) { SET_ERROR(res); goto exit; }
        if (bytes_written > 0) {
            if(!PyObject_CallFunction(write, "s#", outbuf, bytes_written)) goto exit;
        }
        if (inbuf_len > inbuf_pos && !bytes_read && !bytes_written && status != LZMA_STATUS_NEEDS_MORE_INPUT && status != LZMA_STATUS_FINISHED_WITH_MARK) {
            SET_ERROR(SZ_ERROR_DATA); goto exit;
        }
        if (bytes_read > 0) inbuf_pos += bytes_read;
        if (status == LZMA_STATUS_NEEDS_MORE_INPUT) {
            leftover = inbuf_len - inbuf_pos;
            inbuf_pos = 0;
            if (!PyObject_CallFunction(seek, "ii", -leftover, SEEK_CUR)) goto exit;
            rres = PyObject_CallFunction(read, "n", bufsize);
            if (rres == NULL) goto exit;
            inbuf_len = PyBytes_GET_SIZE(rres);
            if (inbuf_len == 0) { PyErr_SetString(LZMAError, "LZMA2 block was truncated"); goto exit; }
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
// }}}

// LZMA1 decompress {{{
static PyObject*
decompress(PyObject *self, PyObject *args) {
    PyObject *read = NULL, *seek = NULL, *write = NULL, *rres = NULL;
    UInt64 decompressed_size = 0;
    int size_known = 0;
    Py_ssize_t header_size = 0, leftover = 0;
    unsigned char *header = NULL, *inbuf = NULL, *outbuf = NULL;
    CLzmaDec state;
    SRes res = 0;
    SizeT bufsize = 0, bytes_written = 0, bytes_read = 0, inbuf_pos = 0, inbuf_len = 0, total_written = 0;
    ELzmaStatus status = LZMA_STATUS_NOT_FINISHED;
    ELzmaFinishMode finish_mode = LZMA_FINISH_ANY;

    if(!PyArg_ParseTuple(args, "OOOKs#k", &read, &seek, &write, &decompressed_size, &header, &header_size, &bufsize)) return NULL;
    size_known = (decompressed_size != (UInt64)(Int64)-1);
    if (header_size != 13) { PyErr_SetString(LZMAError, "Header must be exactly 13 bytes long"); return NULL; }
    if (!decompressed_size) { PyErr_SetString(LZMAError, "Cannot decompress empty file"); return NULL; }

    LzmaDec_Construct(&state);
    res = LzmaDec_Allocate(&state, header, LZMA_PROPS_SIZE, &allocator);
    if (res == SZ_ERROR_MEM) { PyErr_NoMemory(); return NULL; }
    if (res != SZ_OK) { PyErr_SetString(PyExc_TypeError, "Incorrect stream properties"); goto exit; }
    inbuf = (unsigned char*)PyMem_Malloc(bufsize);
    outbuf = (unsigned char*)PyMem_Malloc(bufsize);
    if (!inbuf || !outbuf) {PyErr_NoMemory(); goto exit;}

    LzmaDec_Init(&state);

    while (status != LZMA_STATUS_FINISHED_WITH_MARK) {
        bytes_written = bufsize; bytes_read = inbuf_len - inbuf_pos;
        if (bytes_read) {
            Py_BEGIN_ALLOW_THREADS;
            finish_mode = LZMA_FINISH_ANY;
            if (size_known && total_written + bufsize > decompressed_size) finish_mode = LZMA_FINISH_END;
            res = LzmaDec_DecodeToBuf(&state, (Byte*)outbuf, &bytes_written, (Byte*)(inbuf) + inbuf_pos, &bytes_read, finish_mode, &status);
            Py_END_ALLOW_THREADS;
        } else { res = SZ_OK; bytes_written = 0; status = LZMA_STATUS_NEEDS_MORE_INPUT; }
        if (res != SZ_OK) { SET_ERROR(res); goto exit; }
        if (bytes_written > 0) {
            if(!PyObject_CallFunction(write, "s#", outbuf, bytes_written)) goto exit;
            total_written += bytes_written;
        }
        if (inbuf_len > inbuf_pos && !bytes_read && !bytes_written && status != LZMA_STATUS_NEEDS_MORE_INPUT && status != LZMA_STATUS_FINISHED_WITH_MARK) {
            SET_ERROR(SZ_ERROR_DATA); goto exit;
        }
        if (bytes_read > 0) inbuf_pos += bytes_read;
        if (size_known && total_written >= decompressed_size) break;
        if (status == LZMA_STATUS_NEEDS_MORE_INPUT) {
            leftover = inbuf_len - inbuf_pos;
            inbuf_pos = 0;
            if (!PyObject_CallFunction(seek, "ii", -leftover, SEEK_CUR)) goto exit;
            rres = PyObject_CallFunction(read, "n", bufsize);
            if (rres == NULL) goto exit;
            inbuf_len = PyBytes_GET_SIZE(rres);
            if (inbuf_len == 0) { PyErr_SetString(LZMAError, "LZMA block was truncated"); goto exit; }
            memcpy(inbuf, PyBytes_AS_STRING(rres), inbuf_len);
            Py_DECREF(rres); rres = NULL;
        } 
    }
    leftover = inbuf_len - inbuf_pos;
    if (leftover > 0) {
        if (!PyObject_CallFunction(seek, "ii", -leftover, SEEK_CUR)) goto exit;
    }

exit:
    LzmaDec_Free(&state, &allocator);
    PyMem_Free(inbuf); PyMem_Free(outbuf);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}

// }}}

// LZMA2 Compress {{{
static void
init_props(CLzma2EncProps *props, int preset) {
    int level = (preset < 0) ? 0 : ((preset > 9) ? 9 : preset);
    props->blockSize = 0;
    props->numBlockThreads = 1;
    props->numTotalThreads = 1;
    props->lzmaProps.numThreads = 1;
    props->lzmaProps.writeEndMark = 1;

    props->lzmaProps.level = level;
    props->lzmaProps.dictSize = 0;
    props->lzmaProps.reduceSize = 0xFFFFFFFF;
    props->lzmaProps.lc = -1;
    props->lzmaProps.lp = -1;
    props->lzmaProps.pb = -1;
    props->lzmaProps.algo = -1;
    props->lzmaProps.fb = -1;
    props->lzmaProps.btMode = -1;
    props->lzmaProps.numHashBytes = -1;
    props->lzmaProps.mc = 0;
}

#define ACQUIRE_GIL PyEval_RestoreThread(*(self->thread_state)); *(self->thread_state) = NULL;
#define RELEASE_GIL *(self->thread_state) = PyEval_SaveThread();

static SRes iread(void *p, void *buf, size_t *size) {
    InStream *self = (InStream*)p;
    PyObject *res = NULL;
    char *str = NULL;
    if (*size == 0) return SZ_OK;
    ACQUIRE_GIL
    res = PyObject_CallFunction(self->read, "n", size);
    if (res == NULL) return SZ_ERROR_READ;
    str = PyBytes_AsString(res);
    if (str == NULL) { Py_DECREF(res); return SZ_ERROR_READ; }
    *size = PyBytes_Size(res);
    if(*size) memcpy(buf, str, *size);
    Py_DECREF(res);
    RELEASE_GIL
    return SZ_OK;
}

static size_t owrite(void *p, const void *buf, size_t size) {
    OutStream *self = (OutStream*)p;
    PyObject *res = NULL;
    if (!size) return 0;
    ACQUIRE_GIL
    res = PyObject_CallFunction(self->write, "s#", (char*)buf, size);
    if (res == NULL) return 0;
    Py_DECREF(res);
    RELEASE_GIL
    return size;
}

static SRes report_progress(void *p, UInt64 in_size, UInt64 out_size) {
    Progress *self = (Progress*)p;
    PyObject *res = NULL;
    if (!self->callback) return SZ_OK;
    ACQUIRE_GIL
    res = PyObject_CallFunction(self->callback, "KK", in_size, out_size);
    if (!res || !PyObject_IsTrue(res)) { Py_DECREF(res); return SZ_ERROR_PROGRESS; }
    Py_DECREF(res);
    RELEASE_GIL
    return SZ_OK;
}

static PyObject*
get_lzma2_properties(int preset) {
    CLzma2EncHandle lzma2 = NULL;
    CLzma2EncProps props;
    Byte props_out = 0;
    SRes res = SZ_OK;
    lzma2 = Lzma2Enc_Create(&allocator, &allocator);
    if (lzma2 == NULL) { PyErr_NoMemory(); goto exit; }

    // Initialize parameters based on the preset
    init_props(&props, preset);
    res = Lzma2Enc_SetProps(lzma2, &props);
    if (res != SZ_OK) { SET_ERROR(res); goto exit; }
    props_out = Lzma2Enc_WriteProperties(lzma2);
exit:
    if (lzma2) Lzma2Enc_Destroy(lzma2);
    if (PyErr_Occurred()) return NULL;
    return Py_BuildValue("s#", &props_out, 1);
}


static PyObject*
compress(PyObject *self, PyObject *args) {
    PyObject *read = NULL, *write = NULL, *progress_callback = NULL;
    CLzma2EncHandle lzma2 = NULL;
    CLzma2EncProps props;
    int preset = 5;
    InStream in_stream;
    OutStream out_stream;
    Progress progress;
    SRes res = SZ_OK;
    Byte props_out = 0;
    PyThreadState *ts = NULL;

    if (!PyArg_ParseTuple(args, "OO|Oi", &read, &write, &progress_callback, &preset)) return NULL;
    if (progress_callback && !PyCallable_Check(progress_callback)) progress_callback = NULL;

    lzma2 = Lzma2Enc_Create(&allocator, &allocator);
    if (lzma2 == NULL) { PyErr_NoMemory(); goto exit; }

    // Initialize parameters based on the preset
    init_props(&props, preset);
    res = Lzma2Enc_SetProps(lzma2, &props);
    if (res != SZ_OK) { SET_ERROR(res); goto exit; }

    // Write the dict size to the output stream
    props_out = Lzma2Enc_WriteProperties(lzma2);

    // Create the streams and progress callback
    in_stream.stream.Read = iread;
    in_stream.read = read;
    out_stream.stream.Write = owrite;
    out_stream.write = write;
    progress.progress.Progress = report_progress;
    progress.callback = progress_callback;

    // Run the compressor
    ts = PyEval_SaveThread();
    in_stream.thread_state = &ts;
    out_stream.thread_state = &ts;
    progress.thread_state = &ts;
    res = Lzma2Enc_Encode(lzma2, (ISeqOutStream*)&out_stream, (ISeqInStream*)&in_stream, (ICompressProgress*)&progress);
    if (res != SZ_OK && !PyErr_Occurred()) SET_ERROR(res);
    if (ts) PyEval_RestoreThread(ts);
exit:
    if (lzma2) Lzma2Enc_Destroy(lzma2);
    if (PyErr_Occurred()) return NULL;
    return Py_BuildValue("s#", &props_out, 1);
}

// }}}
 
static PyMethodDef lzma_binding_methods[] = {
    {"decompress2", decompress2, METH_VARARGS,
        "Decompress an LZMA2 encoded block, of unknown compressed size (reads till LZMA2 EOS marker)"
    },

    {"compress", compress, METH_VARARGS,
        "Compress data into an LZMA2 block, writing it to outfile. Returns the LZMA2 properties as a bytestring."
    },

    {"decompress", decompress, METH_VARARGS,
        "Decompress an LZMA encoded block, of (un)known size (reads till LZMA EOS marker when size unknown)"
    },

    {"crc64", crc64, METH_VARARGS,
        "crc64(bytes) -> CRC 64 for the provided python bytes object"
    },

    {"delta_decode", delta_decode, METH_VARARGS,
        "delta_decode(rawarray, histarray, pos, distance) -> Apply the delta decode filter to the bytearray rawarray"
    },

    {NULL, NULL, 0, NULL}
};


CALIBRE_MODINIT_FUNC
initlzma_binding(void) {
    PyObject *m = NULL, *preset_map = NULL, *temp = NULL;
    int i = 0;
    init_crc_table();
    LZMAError = PyErr_NewException("lzma_binding.error", NULL, NULL);
    if (!LZMAError) return;
    m = Py_InitModule3("lzma_binding", lzma_binding_methods, "Bindings to the LZMA (de)compression C code");
    if (m == NULL) return;
    preset_map = PyTuple_New(10);
    if (preset_map == NULL) return;
    for (i = 0; i < 10; i++) {
        temp = get_lzma2_properties(i);
        if (temp == NULL) return;
        PyTuple_SET_ITEM(preset_map, i, temp);
    }
    PyModule_AddObject(m, "preset_map", preset_map);
    Py_INCREF(LZMAError);
    PyModule_AddObject(m, "error", LZMAError);
}
