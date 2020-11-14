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
#include <stdio.h>

#define BUFFER 6000

#define MIN(x, y) ( ((x) < (y)) ? (x) : (y) )
#define MAX(x, y) ( ((x) > (y)) ? (x) : (y) )

typedef unsigned short int Byte;
typedef struct {
	Byte	*data;
	Py_ssize_t len;
} buffer;

#ifdef	bool
#undef	bool
#endif
#define	bool		int

#ifdef	false
#undef	false
#endif
#define	false		0

#ifdef	true
#undef	true
#endif
#define	true		1

#define CHAR(x) (( (x) > 127 ) ? (x)-256 : (x))

static PyObject *
cpalmdoc_decompress(PyObject *self, PyObject *args) {
    const char *_input = NULL; Py_ssize_t input_len = 0;
    Byte *input; char *output; Byte c; PyObject *ans;
    Py_ssize_t i = 0, o = 0, j = 0, di, n;
    if (!PyArg_ParseTuple(args, "y#", &_input, &input_len))
		return NULL;
    input = (Byte *) PyMem_Malloc(sizeof(Byte)*input_len);
    if (input == NULL) return PyErr_NoMemory();
    // Map chars to bytes
    for (j = 0; j < input_len; j++)
        input[j] = (_input[j] < 0) ? _input[j]+256 : _input[j];
    output = (char *)PyMem_Malloc(sizeof(char)*(MAX(BUFFER, 8*input_len)));
    if (output == NULL) return PyErr_NoMemory();

    while (i < input_len) {
        c = input[i++];
        if (c >= 1 && c <= 8)  // copy 'c' bytes
            while (c--) output[o++] = (char)input[i++];

        else if (c <= 0x7F)  // 0, 09-7F = self
            output[o++] = (char)c;

        else if (c >= 0xC0) { // space + ASCII char
            output[o++] = ' ';
            output[o++] = c ^ 0x80;
        }
        else { // 80-BF repeat sequences
            c = (c << 8) + input[i++];
            di = (c & 0x3FFF) >> 3;
            for ( n = (c & 7) + 3; n--; ++o )
                output[o] = output[o - di];
        }
    }
    ans = Py_BuildValue("y#", output, o);
    if (output != NULL) PyMem_Free(output);
    if (input != NULL) PyMem_Free(input);
    return ans;
}

static bool
cpalmdoc_memcmp( Byte *a, Byte *b, Py_ssize_t len) {
    Py_ssize_t i;
    for (i = 0; i < len; i++) if (a[i] != b[i]) return false;
    return true;
}

static Py_ssize_t
cpalmdoc_rfind(Byte *data, Py_ssize_t pos, Py_ssize_t chunk_length) {
    Py_ssize_t i;
    for (i = pos - chunk_length; i > -1; i--)
        if (cpalmdoc_memcmp(data+i, data+pos, chunk_length)) return i;
    return pos;
}


static Py_ssize_t
cpalmdoc_do_compress(buffer *b, char *output) {
    Py_ssize_t i = 0, j, chunk_len, dist;
    unsigned int compound;
    Byte c, n;
    bool found;
    char *head;
    buffer temp;
    head = output;
    temp.data = (Byte *)PyMem_Malloc(sizeof(Byte)*8); temp.len = 0;
    if (temp.data == NULL) return 0;
    while (i < b->len) {
        c = b->data[i];
        //do repeats
        if ( i > 10 && (b->len - i) > 10) {
            found = false;
            for (chunk_len = 10; chunk_len > 2; chunk_len--) {
                j = cpalmdoc_rfind(b->data, i, chunk_len);
                dist = i - j;
                if (j < i && dist <= 2047) {
                    found = true;
                    compound = (unsigned int)((dist << 3) + chunk_len-3);
                    *(output++) = CHAR(0x80 + (compound >> 8 ));
                    *(output++) = CHAR(compound & 0xFF);
                    i += chunk_len;
                    break;
                }
            }
            if (found) continue;
        }

        //write single character
        i++;
        if (c == 32 && i < b->len) {
            n = b->data[i];
            if ( n >= 0x40 && n <= 0x7F) {
                *(output++) = CHAR(n^0x80); i++; continue;
            }
        }
        if (c == 0 || (c > 8 && c < 0x80))
            *(output++) = CHAR(c);
        else { // Write binary data
            j = i;
            temp.data[0] = c; temp.len = 1;
            while (j < b->len && temp.len < 8) {
                c = b->data[j];
                if (c == 0 || (c > 8 && c < 0x80)) break;
                temp.data[temp.len++] = c; j++;
            }
            i += temp.len - 1;
            *(output++) = (char)temp.len;
            for (j=0; j < temp.len; j++) *(output++) = (char)temp.data[j];
        }
    }
    PyMem_Free(temp.data);
    return output - head;
}

static PyObject *
cpalmdoc_compress(PyObject *self, PyObject *args) {
    const char *_input = NULL; Py_ssize_t input_len = 0;
    char *output; PyObject *ans;
    Py_ssize_t j = 0;
    buffer b;
    if (!PyArg_ParseTuple(args, "y#", &_input, &input_len))
		return NULL;
    b.data = (Byte *)PyMem_Malloc(sizeof(Byte)*input_len);
    if (b.data == NULL) return PyErr_NoMemory();
    // Map chars to bytes
    for (j = 0; j < input_len; j++)
        b.data[j] = (_input[j] < 0) ? _input[j]+256 : _input[j];
    b.len = input_len;
    // Make the output buffer larger than the input as sometimes
    // compression results in a larger block
    output = (char *)PyMem_Malloc(sizeof(char) * (int)(1.25*b.len));
    if (output == NULL) return PyErr_NoMemory();
    j = cpalmdoc_do_compress(&b, output);
    if ( j == 0) return PyErr_NoMemory();
    ans = Py_BuildValue("y#", output, j);
    PyMem_Free(output);
    PyMem_Free(b.data);
    return ans;
}

static char cPalmdoc_doc[] = "Compress and decompress palmdoc strings.";

static PyMethodDef cPalmdoc_methods[] = {
    {"decompress", cpalmdoc_decompress, METH_VARARGS,
    "decompress(bytestring) -> decompressed bytestring\n\n"
    		"Decompress a palmdoc compressed byte string. "
    },

    {"compress", cpalmdoc_compress, METH_VARARGS,
    "compress(bytestring) -> compressed bytestring\n\n"
    		"Palmdoc compress a byte string. "
    },
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *module) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "cPalmdoc",
    .m_doc      = cPalmdoc_doc,
    .m_methods  = cPalmdoc_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_cPalmdoc(void) { return PyModuleDef_Init(&module_def); }
