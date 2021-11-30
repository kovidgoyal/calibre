/* __license__   = 'GPL v3'
 * __copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'
 *
 * Python/C implementation of an LZX compressor type.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <structmember.h>
#include <lzxc.h>

extern PyObject *LZXError;
extern PyTypeObject CompressorType;

#define BUFFER_INIT(buffer)                                             \
    do {                                                                \
        (buffer).data = NULL;                                           \
        (buffer).size = 0;                                              \
        (buffer).offset = 0;                                            \
    } while (0)

#define COMPRESSOR_REMAINING(compressor)                                \
    (((compressor)->residue.size - (compressor)->residue.offset)        \
     + ((compressor)->input.size - (compressor)->input.offset))

typedef struct buffer_t {
    char *data;
    unsigned int size;
    unsigned int offset;
} buffer_t;

typedef struct Compressor {
    PyObject_HEAD
    int reset;
    int wbits;
    int blocksize;
    int flushing;
    struct lzxc_data *stream;
    buffer_t residue;
    buffer_t input;
    buffer_t output;
    PyObject *rtable;
} Compressor;

static PyMemberDef Compressor_members[] = {
    { "reset", T_INT, offsetof(Compressor, reset), READONLY,
      "whether or not the Compressor resets each block" },
    { "wbits", T_INT, offsetof(Compressor, wbits), READONLY,
      "window size in bits" },
    { "blocksize", T_INT, offsetof(Compressor, blocksize), READONLY,
      "block size in bytes" },
    { NULL }
};

static int
Compressor_traverse(Compressor *self, visitproc visit, void *arg)
{
    Py_VISIT(self->rtable);
    return 0;
}

static int
Compressor_clear(Compressor *self)
{
    Py_CLEAR(self->rtable);
    return 0;
}

static void
Compressor_dealloc(Compressor *self)
{
    Compressor_clear(self);

    if (self->stream) {
        lzxc_finish(self->stream, NULL);
        self->stream = NULL;
    }
    if (self->residue.data) {
        PyMem_Free(self->residue.data);
        self->residue.data = NULL;
    }
    if (self->output.data) {
        PyMem_Free(self->output.data);
        self->output.data = NULL;
    }

    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
Compressor_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Compressor *self = NULL;

    self = (Compressor *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->rtable = PyList_New(0);
        if (self->rtable == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->wbits = 0;
        self->blocksize = 0;
        self->flushing = 0;

        BUFFER_INIT(self->residue);
        BUFFER_INIT(self->input);
        BUFFER_INIT(self->output);
    }

    return (PyObject *)self;
}

static int
get_bytes(void *context, int nbytes, void *buf)
{
    Compressor *self = (Compressor *)context;
    unsigned char *data = (unsigned char *)buf;
    buffer_t *residue = &self->residue;
    buffer_t *input = &self->input;
    int resrem = residue->size - residue->offset;
    int inrem = input->size - input->offset;

    if (resrem > 0) {
        if (resrem <= nbytes) {
            memcpy(data, residue->data + residue->offset, nbytes);
            residue->offset += nbytes;
            return nbytes;
        } else {
            memcpy(data, residue->data + residue->offset, resrem);
            residue->offset += resrem;
            data += resrem;
            nbytes -= resrem;
        }
    }

    if (inrem == 0) {
        return resrem;
    } else if (nbytes > inrem) {
        nbytes = inrem;
    }
    memcpy(data, input->data + input->offset, nbytes);
    input->offset += nbytes;

    return nbytes + resrem;
}

static int
at_eof(void *context)
{
    Compressor *self = (Compressor *)context;
    return (self->flushing && (COMPRESSOR_REMAINING(self) == 0));
}

static int
put_bytes(void *context, int nbytes, void *data)
{
    Compressor *self = (Compressor *)context;
    buffer_t *output = &self->output;
    int remaining = output->size - output->offset;

    if (nbytes > remaining) {
        PyErr_SetString(LZXError,
            "Attempt to write compressed data beyond end of buffer");
        nbytes = remaining;
    }

    memcpy(output->data + output->offset, data, nbytes);
    output->offset += nbytes;

    return nbytes;
}

static void
mark_frame(void *context, uint32_t uncomp, uint32_t comp)
{
    Compressor *self = (Compressor *)context;
    PyObject *rtable = self->rtable;
    PyObject *entry = NULL;

    entry = Py_BuildValue("(II)", uncomp, comp);
    if (entry) {
        PyList_Append(rtable, entry);
        Py_DECREF(entry);
    }
}

static int
Compressor_init(Compressor *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"wbits", "reset", NULL};
    int wbits = 0;
    int retval = 0;

    self->reset = 1;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "I|b", kwlist, &wbits, &self->reset)) {
        return -1;
    }
    /* TODO: check window size. */

    self->wbits = wbits;
    self->blocksize = 1 << wbits;

    self->residue.data = PyMem_Realloc(self->residue.data, self->blocksize);
    if (self->residue.data == NULL) {
        PyErr_NoMemory();
        return -1;
    }

    if (self->stream != NULL) {
        lzxc_finish(self->stream, NULL);
    }
    retval = lzxc_init(&self->stream, wbits, get_bytes, self, at_eof,
                       put_bytes, self, mark_frame, self);
    if (retval != 0) {
        self->stream = NULL;
        PyErr_SetString(LZXError, "Failed to create compression stream");
        return -1;
    }

    return 0;
}

static PyObject *
Compressor_compress__(
    Compressor *self, char *data, unsigned int inlen, int flush)
{
    buffer_t *residue = &self->residue;
    buffer_t *input = &self->input;
    buffer_t *output = &self->output;
    unsigned int outlen, remainder;
    int reset = self->reset;
    unsigned int blocksize = self->blocksize;
    int retval = 0;
    PyObject *cdata = NULL;
    PyObject *rtable = NULL;
    PyObject *result = NULL;

    self->flushing = flush;
    input->data = data;
    input->size = inlen;
    input->offset = 0;

    outlen = inlen;
    remainder = outlen % blocksize;
    if (remainder != 0) {
        outlen += (blocksize - remainder) + 1;
    }
    if (output->size < outlen) {
        output->data = PyMem_Realloc(output->data, outlen);
        if (output->data == NULL) {
            return PyErr_NoMemory();
        }
        output->size = outlen;
    }
    output->offset = 0;

    while (COMPRESSOR_REMAINING(self) >= blocksize) {
        retval = lzxc_compress_block(self->stream, blocksize, 1);
        if (retval != 0) {
            PyErr_SetString(LZXError, "Error during compression");
            return NULL;
        }
        if (reset) {
            lzxc_reset(self->stream);
        }
    }
    if (flush && COMPRESSOR_REMAINING(self) > 0) {
        retval = lzxc_compress_block(self->stream, blocksize, 1);
        if (retval != 0) {
            PyErr_SetString(LZXError, "Error during compression");
            return NULL;
        }
        if (reset) {
            lzxc_reset(self->stream);
        }
        residue->size = 0;
        residue->offset = 0;
    } else {
        int reslen = input->size - input->offset;
        memcpy(residue->data, input->data + input->offset, reslen);
        residue->size = reslen;
        residue->offset = 0;
    }

    rtable = self->rtable;
    self->rtable = PyList_New(0);
    if (self->rtable == NULL) {
        self->rtable = rtable;
        return NULL;
    }
    cdata = PyBytes_FromStringAndSize(output->data, output->offset);
    if (cdata == NULL) {
        Py_DECREF(rtable);
        return NULL;
    }

    result = Py_BuildValue("(OO)", cdata, rtable);
    Py_DECREF(rtable);
    Py_DECREF(cdata);

    return result;
}

static PyObject *
Compressor_compress(Compressor *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"data", "flush", NULL};
    char *data = NULL;
    unsigned int inlen = 0;
    int flush = 0;

    if (!PyArg_ParseTupleAndKeywords(
#if PYTHON_MAJOR_VERSION >= 3
            args, kwds, "y#|b", kwlist, &data, &inlen, &flush)) {
#else
            args, kwds, "s#|b", kwlist, &data, &inlen, &flush)) {
#endif
        return NULL;
    }

    return Compressor_compress__(self, data, inlen, flush);
}

static PyObject *
Compressor_flush(Compressor *self)
{
    return Compressor_compress__(self, NULL, 0, 1);
}

static PyMethodDef Compressor_methods[] = {
    { "compress", (PyCFunction)Compressor_compress,
      METH_VARARGS | METH_KEYWORDS,
      "Return a string containing data LZX compressed." },
    { "flush", (PyCFunction)Compressor_flush, METH_NOARGS,
      "Return a string containing any remaining LZX compressed data." },
    { NULL }
};

PyTypeObject CompressorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name             */  "lzx.Compressor",
    /* tp_basicsize        */  sizeof(Compressor),
    /* tp_itemsize         */  0,
    /* tp_dealloc          */  (destructor)Compressor_dealloc,
    /* tp_print            */  0,
    /* tp_getattr          */  0,
    /* tp_setattr          */  0,
    /* tp_compare          */  0,
    /* tp_repr             */  0,
    /* tp_as_number        */  0,
    /* tp_as_sequence      */  0,
    /* tp_as_mapping       */  0,
    /* tp_hash             */  0,
    /* tp_call             */  0,
    /* tp_str              */  0,
    /* tp_getattro         */  0,
    /* tp_setattro         */  0,
    /* tp_as_buffer        */  0,
    /* tp_flags            */  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,
    /* tp_doc              */  "Compressor objects",
    /* tp_traverse         */  (traverseproc)Compressor_traverse,
    /* tp_clear            */  (inquiry)Compressor_clear,
    /* tp_richcompare      */  0,
    /* tp_weaklistoffset   */  0,
    /* tp_iter             */  0,
    /* tp_iternext         */  0,
    /* tp_methods          */  Compressor_methods,
    /* tp_members          */  Compressor_members,
    /* tp_getset           */  0,
    /* tp_base             */  0,
    /* tp_dict             */  0,
    /* tp_descr_get        */  0,
    /* tp_descr_set        */  0,
    /* tp_dictoffset       */  0,
    /* tp_init             */  (initproc)Compressor_init,
    /* tp_alloc            */  0,
    /* tp_new              */  Compressor_new,
};
