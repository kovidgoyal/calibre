/* __license__   = 'GPL v3'
 * __copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'
 *
 * Python module C glue code.
 */


#include <Python.h>

#include <d3des.h>

static char msdes_doc[] = 
"Provide LIT-specific DES en/decryption.";

static PyObject *MsDesError = NULL;

static PyObject *
msdes_deskey(PyObject *self, PyObject *args)
{
    unsigned char *key = NULL;
    unsigned int len = 0;
    short int edf = 0;

    if (!PyArg_ParseTuple(args, "s#h", &key, &len, &edf)) {
        return NULL;
    }

    if (len != 8) {
        PyErr_SetString(MsDesError, "Key length incorrect");
        return NULL;
    }

    if ((edf != EN0) && (edf != DE1)) {
        PyErr_SetString(MsDesError, "En/decryption direction invalid");
        return NULL;
    }    

    deskey(key, edf);
    
    Py_RETURN_NONE;
}

static PyObject *
msdes_des(PyObject *self, PyObject *args)
{
    unsigned char *inbuf = NULL;
    unsigned char *outbuf = NULL;
    unsigned int len = 0;
    unsigned int off = 0;
    PyObject *retval = NULL;

    if (!PyArg_ParseTuple(args, "s#", &inbuf, &len)) {
        return NULL;
    }

    if ((len == 0) || ((len % 8) != 0)) {
        PyErr_SetString(MsDesError,
            "Input length not a multiple of the block size");
        return NULL;
    }

    retval = PyString_FromStringAndSize(NULL, len);
    if (retval == NULL) {
        return NULL;
    }
    outbuf = (unsigned char *)PyString_AS_STRING(retval);

    for (off = 0; off < len; off += 8) {
        des((inbuf + off), (outbuf + off));
    }
    
    return retval;
}

static PyMethodDef msdes_methods[] = {
    { "deskey", &msdes_deskey, METH_VARARGS, "Provide a new key for DES en/decryption." },
    { "des", &msdes_des, METH_VARARGS, "Perform DES en/decryption." },
    { NULL, NULL }
};

CALIBRE_MODINIT_FUNC
initmsdes(void)
{
    PyObject *m;

    m = Py_InitModule3("msdes", msdes_methods, msdes_doc);
    if (m == NULL) {
        return;
    }
    
    MsDesError = PyErr_NewException("msdes.MsDesError", NULL, NULL);
    Py_INCREF(MsDesError);
    PyModule_AddObject(m, "MsDesError", MsDesError);
    PyModule_AddObject(m, "EN0", PyInt_FromLong(EN0));
    PyModule_AddObject(m, "DE1", PyInt_FromLong(DE1));
    
    return;
}
