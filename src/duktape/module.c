#include "dukpy.h"

PyObject *JSError = NULL;

/* ARGSUSED */
static PyObject *
undefined_repr(PyObject *op)
{
#if PY_MAJOR_VERSION < 3
    return PyBytes_FromString("undefined");
#else
    return PyUnicode_FromString("undefined");
#endif
}

/* ARGUSED */
static void
undefined_dealloc(PyObject* ignore)
{   
    /* This should never get called, but we also don't want to SEGV if
     * we accidentally decref undef out of existence.
     */
    Py_FatalError("deallocating undefined");
}

static PyTypeObject DukUndefined_Type = {
#if PY_MAJOR_VERSION < 3
    PyVarObject_HEAD_INIT(NULL, 0)
#else
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
#endif
    "UndefinedType",
    0,
    0,
    undefined_dealloc,
    0,                  /*tp_print*/
    0,                  /*tp_getattr*/
    0,                  /*tp_setattr*/
    0,                  /*tp_compare*/
    undefined_repr,     /*tp_repr*/
    0,                  /*tp_as_number*/
    0,                  /*tp_as_sequence*/
    0,                  /*tp_as_mapping*/
};

PyObject DukUndefined = {
    _PyObject_EXTRA_INIT
  1, &DukUndefined_Type
};


#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "dukpy",  /* m_name */
    NULL,       /* m_doc */
    0,          /* m_size */
    NULL,       /* m_methods */
    NULL,       /* m_reload */
    NULL,       /* m_traverse */
    NULL,       /* m_clear */
    NULL        /* m_free */
};
#endif

#ifndef _MSC_VER
__attribute__ ((visibility ("default")))
#endif
PyMODINIT_FUNC
#if PY_MAJOR_VERSION >= 3
PyInit_dukpy(void)
#else 
initdukpy(void)
#endif
{
    PyObject *mod;

#if PY_MAJOR_VERSION < 3
    DukUndefined_Type.ob_type = &PyType_Type;
#endif
    if (PyType_Ready(&DukUndefined_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

    DukContext_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DukContext_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

    DukObject_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DukObject_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

    DukArray_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DukArray_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

    DukFunction_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DukFunction_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

    DukEnum_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DukEnum_Type) < 0)
#if PY_MAJOR_VERSION >= 3
        return NULL;
#else
        return;
#endif

#if PY_MAJOR_VERSION >= 3
    mod = PyModule_Create(&moduledef);
#else
    mod = Py_InitModule3("dukpy", NULL, "Python bindings for duktape");
#endif
    if (mod != NULL) {
        Py_INCREF(&DukContext_Type);
        PyModule_AddObject(mod, "Context", (PyObject *)&DukContext_Type);

        Py_INCREF(Duk_undefined);
        PyModule_AddObject(mod, "undefined", (PyObject *)Duk_undefined);

        JSError = PyErr_NewException("dukpy.JSError", NULL, NULL);
        if (JSError) PyModule_AddObject(mod, "JSError", JSError);
    }

#if PY_MAJOR_VERSION >= 3
    return mod;
#endif
}
