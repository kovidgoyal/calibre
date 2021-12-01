/* __license__   = 'GPL v3'
 * __copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'
 *
 * Python module C glue code.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>

#include <mspack.h>
#include <lzxd.h>

extern PyObject *LZXError;
extern PyTypeObject CompressorType;

static char lzx_doc[] =
    "Provide basic LZX compression and decompression using the code from\n"
    "liblzxcomp and libmspack respectively.";

PyObject *LZXError = NULL;

typedef struct memory_file {
    unsigned int magic;	/* 0xB5 */
    void *buffer;
    int total_bytes;
    int current_bytes;
} memory_file;

static void *
glue_alloc(struct mspack_system *this, size_t bytes)
{
    void *p = NULL;
    p = (void *)malloc(bytes);
    if (p == NULL) {
        return (void *)PyErr_NoMemory();
    }
    return p;
}

static void
glue_free(void *p)
{
    free(p);
}

static void
glue_copy(void *src, void *dest, size_t bytes)
{
    memcpy(dest, src, bytes);
}

static struct mspack_file *
glue_open(struct mspack_system *this, char *filename, int mode)
{
    PyErr_SetString(LZXError, "MSPACK_OPEN unsupported");
    return NULL;
}

static void
glue_close(struct mspack_file *file)
{
    return;
}

static int
glue_read(struct mspack_file *file, void *buffer, int bytes)
{
    memory_file *mem;
    int remaining;

    mem = (memory_file *)file;
    if (mem->magic != 0xB5) return -1;

    remaining = mem->total_bytes - mem->current_bytes;
    if (!remaining) return 0;
    if (bytes > remaining) bytes = remaining;
    memcpy(buffer, (unsigned char *)mem->buffer + mem->current_bytes, bytes);
    mem->current_bytes += bytes;

    return bytes;
}

static int
glue_write(struct mspack_file *file, void *buffer, int bytes)
{
    memory_file *mem;
    int remaining;

    mem = (memory_file *)file;
    if (mem->magic != 0xB5) return -1;

    remaining = mem->total_bytes - mem->current_bytes;
    if (bytes > remaining) {
        PyErr_SetString(LZXError,
            "MSPACK_WRITE tried to write beyond end of buffer");
        bytes = remaining;
    }
    memcpy((unsigned char *)mem->buffer + mem->current_bytes, buffer, bytes);
    mem->current_bytes += bytes;
    return bytes;
}

struct mspack_system lzxglue_system = {
    glue_open,
    glue_close,
    glue_read,   /* Read */
    glue_write,  /* Write */
    NULL,        /* Seek */
    NULL,        /* Tell */
    NULL,        /* Message */
    glue_alloc,
    glue_free,
    glue_copy,
    NULL         /* Termination */
};


int LZXwindow = 0;
struct lzxd_stream * lzx_stream = NULL;

/* Can't really init here, don't know enough */
static PyObject *
init(PyObject *self, PyObject *args)
{
    int window = 0;

    if (!PyArg_ParseTuple(args, "i", &window)) {
        return NULL;
    }

    LZXwindow = window;
    lzx_stream = NULL;

    Py_RETURN_NONE;
}

/* Doesn't exist.  Oh well, reinitialize state every time anyway */
static PyObject *
reset(PyObject *self, PyObject *args)
{
    if (!PyArg_ParseTuple(args, "")) {
        return NULL;
    }

    Py_RETURN_NONE;
}

//int LZXdecompress(unsigned char *inbuf, unsigned char *outbuf,
//    unsigned int inlen, unsigned int outlen)
static PyObject *
decompress(PyObject *self, PyObject *args)
{
    unsigned char *inbuf;
    unsigned char *outbuf;
    Py_ssize_t inlen;
    unsigned int outlen;
    int err;
    memory_file source;
    memory_file dest;
    PyObject *retval = NULL;

    if (!PyArg_ParseTuple(args, "y#I", &inbuf, &inlen, &outlen)) {
        return NULL;
    }

    retval = PyBytes_FromStringAndSize(NULL, outlen);
    if (retval == NULL) {
        return NULL;
    }
    outbuf = (unsigned char *)PyBytes_AS_STRING(retval);

    source.magic = 0xB5;
    source.buffer = inbuf;
    source.current_bytes = 0;
    source.total_bytes = inlen;

    dest.magic = 0xB5;
    dest.buffer = outbuf;
    dest.current_bytes = 0;
    dest.total_bytes = outlen;

    lzx_stream = lzxd_init(&lzxglue_system, (struct mspack_file *)&source,
        (struct mspack_file *)&dest, LZXwindow,
        0x7fff /* Never reset, I do it */, 4096, outlen);
    err = -1;
    if (lzx_stream) err = lzxd_decompress(lzx_stream, outlen);

    lzxd_free(lzx_stream);
    lzx_stream = NULL;

    if (err != MSPACK_ERR_OK) {
        Py_DECREF(retval);
        retval = NULL;
        PyErr_SetString(LZXError, "LZX decompression failed");
    }

    return retval;
}

static PyMethodDef lzx_methods[] = {
    { "init", &init, METH_VARARGS, "Initialize the LZX decompressor" },
    { "reset", &reset, METH_VARARGS, "Reset the LZX decompressor" },
    { "decompress", &decompress, METH_VARARGS, "Run the LZX decompressor" },
    { NULL }
};

static int
exec_module(PyObject *m) {
    if (PyType_Ready(&CompressorType) < 0) return -1;

    LZXError = PyErr_NewException("lzx.LZXError", NULL, NULL);
    Py_INCREF(LZXError);
    PyModule_AddObject(m, "LZXError", LZXError);

    Py_INCREF(&CompressorType);
    PyModule_AddObject(m, "Compressor", (PyObject *)&CompressorType);

	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "lzx",
    .m_doc      = lzx_doc,
    .m_methods  = lzx_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_lzx(void) { return PyModuleDef_Init(&module_def); }
