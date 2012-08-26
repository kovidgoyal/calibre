#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

#include "global.h"

PyObject *pdf::Error = NULL;

static PyMethodDef podofo_methods[] = {
    {NULL}  /* Sentinel */
};


PyMODINIT_FUNC
initpodofo(void) 
{
    PyObject* m;

    if (PyType_Ready(&pdf::PDFDocType) < 0)
        return;

    pdf::Error = PyErr_NewException((char*)"podofo.Error", NULL, NULL);
    if (pdf::Error == NULL) return;

    m = Py_InitModule3("podofo", podofo_methods,
                       "Wrapper for the PoDoFo PDF library");

    Py_INCREF(&pdf::PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&pdf::PDFDocType);

    PyModule_AddObject(m, "Error", pdf::Error);
}

