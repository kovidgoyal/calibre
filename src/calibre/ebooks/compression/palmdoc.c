/*
:mod:`cPalmdoc` -- Palmdoc compression/decompression
=====================================================

.. module:: cPalmdoc
    :platform: All
    :synopsis: Compression decompression of Palmdoc implemented in C for speed

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2009

*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define BUFFER 6000

#define MIN(x, y) (((x) < (y)) ? (x) : (y))
#define MAX(x, y) (((x) > (y)) ? (x) : (y))

typedef unsigned short int Byte;
typedef struct {
    Byte *data;
    Py_ssize_t len;
} buffer;

#ifdef bool
#undef bool
#endif
#define bool int

#ifdef false
#undef false
#endif
#define false 0

#ifdef true
#undef true
#endif
#define true 1

#define CHAR(x) (((x) > 127) ? (x) - 256 : (x))

static bool
write_to_bytes_object(PyObject **output, size_t pos, char ch) {
    if (pos >= PyBytes_GET_SIZE(*output)) {
        if (_PyBytes_Resize(output, 2 * pos) != 0) return false;
    }
    PyBytes_AS_STRING(*output)[pos] = ch;
    return true;
}

static PyObject *
cpalmdoc_decompress(PyObject *self, PyObject *args) {
    const char *_input = NULL;
    Py_ssize_t input_len = 0;
    Byte *input;
    Byte c;
    PyObject *ans = NULL;
    Py_ssize_t i = 0, j = 0;
    size_t o = 0, di = 0, n = 0;
    if (!PyArg_ParseTuple(args, "y#", &_input, &input_len)) return NULL;
    input = (Byte *)PyMem_Malloc(sizeof(Byte) * input_len);
    if (input == NULL) return PyErr_NoMemory();
    // Map chars to bytes
    for (j = 0; j < input_len; j++) { input[j] = (_input[j] < 0) ? _input[j] + 256 : _input[j]; }
    ans = PyBytes_FromStringAndSize(NULL, 8 * input_len);
    if (ans == NULL) {
        PyMem_Free(input);
        return NULL;
    }

#define write(ch)                                \
    if (!write_to_bytes_object(&ans, o++, ch)) { \
        PyMem_Free(input);                       \
        return NULL;                             \
    }
    while (i < input_len) {
        c = input[i++];
        if (c >= 1 && c <= 8) { // copy 'c' bytes
            while (c-- && i < input_len) { write(input[i++]); }
        } else if (c <= 0x7F) { // 0, 09-7F = self
            write((char)c);
        } else if (c >= 0xC0) { // space + ASCII char
            write(' ');
            write(c ^ 0x80);
        } else if (i < input_len) { // 80-BF repeat sequences
            c = (c << 8) + input[i++];
            di = (c & 0x3FFF) >> 3;
            if (di <= o) {
                for (n = (c & 7) + 3; n--; ++o) {
                    if (!write_to_bytes_object(&ans, o, PyBytes_AS_STRING(ans)[o - di])) {
                        PyMem_Free(input);
                        return NULL;
                    }
                }
            }
        }
    }
#undef write
    PyMem_Free(input);
    if (_PyBytes_Resize(&ans, o) != 0) return NULL;
    return ans;
}

// The compressor looks for the nearest earlier occurrence of the text at the
// current position, trying match lengths from MAX_MATCH_LEN down to
// MIN_MATCH_LEN. To avoid scanning backwards over the whole buffer for every
// length at every position, all earlier positions are indexed by a hash of
// their first MIN_MATCH_LEN bytes, in a chain ordered nearest first. Walking
// that chain visits only positions that can possibly match, and gives exactly
// the same result as the exhaustive scan.
#define MIN_MATCH_LEN 3
#define MAX_MATCH_LEN 10
#define MAX_MATCH_DIST 2047
#define HASH_BITS 16
#define HASH_SIZE (1 << HASH_BITS)

static inline uint32_t
cpalmdoc_hash(const Byte *p) {
    return (((uint32_t)p[0] << 16 | (uint32_t)p[1] << 8 | p[2]) * UINT32_C(2654435761)) >> (32 - HASH_BITS);
}

// Add positions [*indexed, pos) to the hash chains. head[h] is the nearest
// indexed position with hash h and prev[p] the next nearest one after p,
// both -1 at the end of the chain. The caller must ensure that
// MIN_MATCH_LEN bytes are available at every position below pos.
static void
cpalmdoc_index_positions(const buffer *b, int32_t *head, int32_t *prev, Py_ssize_t *indexed, Py_ssize_t pos) {
    for (; *indexed < pos; (*indexed)++) {
        uint32_t h = cpalmdoc_hash(b->data + *indexed);
        prev[*indexed] = head[h];
        head[h] = (int32_t)*indexed;
    }
}

// Return the length of the longest match (at most MAX_MATCH_LEN) for the text
// at pos that starts at least that many bytes earlier (matches may not
// overlap pos) and no more than MAX_MATCH_DIST bytes earlier, setting *dist to
// the distance of the nearest such match of that length. Returns 0 if there is
// no match of at least MIN_MATCH_LEN. The caller must ensure that
// MAX_MATCH_LEN bytes are available at pos.
static Py_ssize_t
cpalmdoc_find_match(const buffer *b, const int32_t *head, const int32_t *prev, Py_ssize_t pos, Py_ssize_t *dist) {
    Py_ssize_t best = MIN_MATCH_LEN - 1, len, d;
    const Byte *cur = b->data + pos;
    for (Py_ssize_t p = head[cpalmdoc_hash(cur)]; p >= 0; p = prev[p]) {
        d = pos - p;
        if (d > MAX_MATCH_DIST) break;
        const Byte *cand = b->data + p;
        for (len = 0; len < MAX_MATCH_LEN && cand[len] == cur[len]; len++);
        if (len > d) len = d; // the match must end at or before pos
        if (len > best) {
            best = len;
            *dist = d;
            if (best == MAX_MATCH_LEN) break;
        }
    }
    return best >= MIN_MATCH_LEN ? best : 0;
}

// Compress b into output, returning the number of bytes written, or -1 with
// a Python exception set on failure.
static Py_ssize_t
cpalmdoc_do_compress(buffer *b, char *output, Py_ssize_t output_len) {
    Py_ssize_t i = 0, j, chunk_len, dist = 0, indexed = 0;
    unsigned int compound;
    Byte c, n;
    char *out_start = output, *end = output + output_len;
    Byte temp[8];
    Py_ssize_t temp_len;
    int32_t *hash_head, *hash_prev;
    if (b->len > INT32_MAX) { // positions are stored as int32_t
        PyErr_SetString(PyExc_OverflowError, "Input too large for palmdoc compression");
        return -1;
    }
    hash_head = (int32_t *)PyMem_Malloc(sizeof(int32_t) * (HASH_SIZE + b->len));
    if (hash_head == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    hash_prev = hash_head + HASH_SIZE;
    memset(hash_head, 0xff, sizeof(int32_t) * HASH_SIZE); // all -1
#define NEED(n)                                                                            \
    if (output + n > end) {                                                                \
        PyMem_Free(hash_head);                                                             \
        PyErr_SetString(PyExc_RuntimeError, "palmdoc compression output buffer overflow"); \
        return -1;                                                                         \
    }
#define WRITE(ch) *(output++) = ch;
#define CHECK_WRITE(ch) \
    NEED(1);            \
    WRITE(ch);

    while (i < b->len) {
        c = b->data[i];
        // do repeats
        if (i > 10 && (b->len - i) > 10) {
            cpalmdoc_index_positions(b, hash_head, hash_prev, &indexed, i);
            chunk_len = cpalmdoc_find_match(b, hash_head, hash_prev, i, &dist);
            if (chunk_len > 0) {
                compound = (unsigned int)((dist << 3) + chunk_len - 3);
                NEED(2);
                WRITE(CHAR(0x80 + (compound >> 8)));
                WRITE(CHAR(compound & 0xFF));
                i += chunk_len;
                continue;
            }
        }

        // write single character
        i++;
        if (c == 32 && i < b->len) {
            n = b->data[i];
            if (n >= 0x40 && n <= 0x7F) {
                CHECK_WRITE(CHAR(n ^ 0x80));
                i++;
                continue;
            }
        }
        if (c == 0 || (c > 8 && c < 0x80)) {
            CHECK_WRITE(CHAR(c));
        } else { // Write binary data
            j = i;
            temp[0] = c;
            temp_len = 1;
            while (j < b->len && temp_len < 8) {
                c = b->data[j];
                if (c == 0 || (c > 8 && c < 0x80)) break;
                temp[temp_len++] = c;
                j++;
            }
            i += temp_len - 1;
            CHECK_WRITE((char)temp_len);
            NEED(temp_len);
            for (j = 0; j < temp_len; j++) { WRITE((char)temp[j]); }
        }
    }
#undef NEED
#undef WRITE
#undef CHECK_WRITE
    PyMem_Free(hash_head);
    return output - out_start;
}

static PyObject *
cpalmdoc_compress(PyObject *self, PyObject *args) {
    const char *_input = NULL;
    Py_ssize_t input_len = 0;
    char *output;
    PyObject *ans = NULL;
    Py_ssize_t j = 0;
    buffer b;
    if (!PyArg_ParseTuple(args, "y#", &_input, &input_len)) return NULL;
    b.data = (Byte *)PyMem_Malloc(sizeof(Byte) * input_len);
    if (b.data == NULL) return PyErr_NoMemory();
    // Map chars to bytes
    for (j = 0; j < input_len; j++) b.data[j] = (_input[j] < 0) ? _input[j] + 256 : _input[j];
    b.len = input_len;
    // Make the output buffer larger than the input as sometimes
    // compression results in a larger block
    Py_ssize_t output_len = (2 * b.len + 1);
    output = (char *)PyMem_Malloc(sizeof(char) * output_len);
    if (output == NULL) {
        PyMem_Free(b.data);
        return PyErr_NoMemory();
    }
    j = cpalmdoc_do_compress(&b, output, output_len);
    if (j >= 0) ans = Py_BuildValue("y#", output, j);
    PyMem_Free(output);
    PyMem_Free(b.data);
    return ans;
}

static char cPalmdoc_doc[] = "Compress and decompress palmdoc strings.";

static PyMethodDef cPalmdoc_methods[] = {
    {"decompress",
     cpalmdoc_decompress,
     METH_VARARGS,
     "decompress(bytestring) -> decompressed bytestring\n\n"
     "Decompress a palmdoc compressed byte string. "},

    {"compress",
     cpalmdoc_compress,
     METH_VARARGS,
     "compress(bytestring) -> compressed bytestring\n\n"
     "Palmdoc compress a byte string. "},
    {NULL, NULL, 0, NULL}};

static int
exec_module(PyObject *module) {
    return 0;
}

static PyModuleDef_Slot slots[] = {{Py_mod_exec, exec_module}, {0, NULL}};

static struct PyModuleDef module_def = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "cPalmdoc",
    .m_doc = cPalmdoc_doc,
    .m_methods = cPalmdoc_methods,
    .m_slots = slots,
};

CALIBRE_MODINIT_FUNC
PyInit_cPalmdoc(void) { return PyModuleDef_Init(&module_def); }
