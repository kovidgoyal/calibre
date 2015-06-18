#include "dukpy.h"

static int get_repr(PyObject *value, char *buf, int bufsz) {
    PyObject *temp = NULL, *repr = NULL;
    memset(buf, 0, bufsz);
    
    if (!value) return 0;
    repr = PyObject_Repr(value);

    if (repr && !PyBytes_Check(repr)) {
        temp = PyUnicode_AsUTF8String(repr);
        Py_DECREF(repr); repr = temp;
    }
    if (!repr) return 0;
    strncpy(buf, PyBytes_AS_STRING(repr), bufsz - 1);
    Py_DECREF(repr);
    return 1;
}

static duk_ret_t python_function_caller(duk_context *ctx)
{
    PyObject *func, *args, *result;
    duk_idx_t nargs, i;
    static char buf1[200], buf2[1024];

    nargs = duk_get_top(ctx);

    duk_push_current_function(ctx);
    duk_get_prop_string(ctx, -1, "\xff" "py_object");
    func = duk_get_pointer(ctx, -1);

    args = PyTuple_New(nargs);
    if (!args)
        return DUK_RET_ALLOC_ERROR;

    for (i = 0; i < nargs; i++) {
        PyObject *arg = duk_to_python(ctx, i);
        if (arg == NULL)
            return DUK_RET_TYPE_ERROR;

        PyTuple_SET_ITEM(args, i, arg);
    }

    result = PyObject_Call(func, args, NULL);
    if (!result) {
        get_repr(func, buf1, 200);
        if (!PyErr_Occurred())
            duk_error(ctx, DUK_ERR_ERROR, "Python function (%s) failed", buf1);
        PyObject *ptype = NULL, *pval = NULL, *tb = NULL;
        PyErr_Fetch(&ptype, &pval, &tb);
        if (!get_repr(pval, buf2, 1024)) get_repr(ptype, buf2, 1024);
        Py_XDECREF(ptype); Py_XDECREF(pval); Py_XDECREF(tb);
        PyErr_Clear();  /* In case there was an error in get_repr() */
        duk_error(ctx, DUK_ERR_ERROR, "Python function (%s) failed with error: %s", buf1, buf2);

    }
    python_to_duk(ctx, result);
    Py_DECREF(result);
    return 1;
}

static duk_ret_t python_object_decref(duk_context *ctx) {
    int deleted = 0;
    duk_get_prop_string(ctx, 0, "\xff""deleted");
    deleted = duk_to_boolean(ctx, -1);
    duk_pop(ctx);
    if (!deleted) {
        duk_get_prop_string(ctx, 0, "\xff""py_object");
        Py_XDECREF(duk_get_pointer(ctx, -1));
        duk_pop(ctx);

        // Mark as deleted
        duk_push_boolean(ctx, 1);
        duk_put_prop_string(ctx, 0, "\xff""deleted");
    }
    return 0;
}

int python_to_duk(duk_context *ctx, PyObject *value)
{
    /* Python to duktape conversion. If successful, leaves the
       converted value on the top of the stack and returns 0.
       Otherwise, raises a Python exception and returns -1.
    */
#if PY_MAJOR_VERSION < 3
    int ret;
#endif
    static char buf[200];

    if (value == Duk_undefined) {
        duk_push_undefined(ctx);
    }
    else if (value == Py_None) {
        /* Map None to null */
        duk_push_null(ctx);
    }
    else if (value == Py_True) {
        duk_push_true(ctx);
    }
    else if (value == Py_False) {
        duk_push_false(ctx);
    }
    else if (Py_TYPE(value) == &DukObject_Type) {
        DukObject_push((DukObject *)value, ctx);
    }
    else if (PyUnicode_Check(value)) {
        /* Unicode string */
#ifdef PyUnicode_AsUTF8AndSize
        char *str;
        Py_ssize_t len;
        str = PyUnicode_AsUTF8AndSize(value, &len);
        if (str == NULL)
            return -1;

        duk_push_lstring(ctx, str, len);
#else
        PyObject *utf8str = PyUnicode_AsUTF8String(value);
        if (utf8str == NULL)
            return -1;
        duk_push_lstring(ctx, PyBytes_AS_STRING(utf8str), PyBytes_GET_SIZE(utf8str));
        Py_DECREF(utf8str);
#endif
    }
#if PY_MAJOR_VERSION < 3
    else if (PyBytes_Check(value)) {
        /* Happens in python 2 for attribute access, for example*/
        PyObject *urepr = PyUnicode_FromObject(value);
        if (urepr == NULL) 
            return -1;
        ret = python_to_duk(ctx, urepr);
        Py_DECREF(urepr);
        return ret;
    }
#endif
    else if (PyLong_Check(value)) {
        double val =  PyLong_AsDouble(value);
        if (PyErr_Occurred())
            return -1;

        duk_push_number(ctx, val);
    }
#if PY_MAJOR_VERSION < 3
    else if (PyInt_Check(value)) {
        double val = (double)PyInt_AsLong(value);
        duk_push_number(ctx, val);
    }
#endif
    else if (PyFloat_Check(value)) {
        double val =  PyFloat_AsDouble(value);
        if (PyErr_Occurred())
            return -1;

        duk_push_number(ctx, val);
    }
    else if (PyDict_Check(value)) {
        PyObject *key, *val;
        Py_ssize_t pos = 0;

        duk_push_object(ctx);

        while (PyDict_Next(value, &pos, &key, &val)) {
            if (python_to_duk(ctx, key) == -1) {
                /* Pop the object */
                duk_pop(ctx);
                return -1;
            }

            if (python_to_duk(ctx, val) == -1) {
                /* Pop the key and the object */
                duk_pop_n(ctx, 2);
                return -1;
            }

            duk_put_prop(ctx, -3);
        }
    }
    else if (PyList_Check(value)) {
        PyObject *val;
        Py_ssize_t i, len;

        duk_push_array(ctx);

        len = PyList_Size(value);
        for (i = 0; i < len; i++) {
            val = PyList_GetItem(value, i);
            if (python_to_duk(ctx, val) == -1) {
                /* Pop the array */
                duk_pop(ctx);
                return -1;
            }
            duk_put_prop_index(ctx, -2, (duk_uarridx_t)i);
        }
    }
    else if (PyCallable_Check(value)) {
        // Store the callable
        duk_push_c_function(ctx, python_function_caller, DUK_VARARGS);
        duk_push_pointer(ctx, value);
        Py_INCREF(value);
        duk_put_prop_string(ctx, -2, "\xff" "py_object");
        // Store a boolean flag to mark the object as deleted because the destructor may be called several times
        duk_push_boolean(ctx, 0);
        duk_put_prop_string(ctx, -2, "\xff""deleted");
        // Store the function destructor
        duk_push_c_function(ctx, python_object_decref, 1);
        duk_set_finalizer(ctx, -2);
    }
    else {
        if(get_repr(value, buf, 200))
            PyErr_Format(PyExc_TypeError, "%s is not coercible", buf);
        return -1;
    }

    return 0;
}

PyObject *duk_to_python(duk_context *ctx, duk_idx_t index)
{
    /* Duktape to Python conversion. If successful, returns a pointer
       to a new PyObject reference. If not, raises a Python exception
       and returns NULL.
    */
    duk_idx_t index_n = duk_normalize_index(ctx, index);
    PyObject *result;

    if (duk_is_undefined(ctx, index_n)) {
        Py_INCREF(Duk_undefined);
        return Duk_undefined;
    }
    else if (duk_is_null(ctx, index_n)) {
        Py_RETURN_NONE;
    }
    else if (duk_is_boolean(ctx, index_n)) {
        if (duk_get_boolean(ctx, index_n))
            Py_RETURN_TRUE;
        else
            Py_RETURN_FALSE;
    }
    else if (duk_is_number(ctx, index_n)) {
        double number, temp;
        number = duk_get_number(ctx, index_n);
        if (modf(number, &temp) == 0) {
            /* No fractional part */
            return PyLong_FromDouble(number);
        } else {
            /* Has fractional part */
            return PyFloat_FromDouble(number);
        }
    }
    else if (duk_is_string(ctx, index_n)) {
        const char *str;
        duk_size_t len;

        /* Duplicate the string because it's replaced by duk_to_lstring() */
        duk_dup(ctx, index_n);
        str = duk_to_lstring(ctx, -1, &len);

        result = PyUnicode_DecodeUTF8(str, len, NULL);

        /* Pop the duplicate */
        duk_pop(ctx);

        return result;
    }
    else if (duk_is_array(ctx, index_n)) {
        return (PyObject *)DukArray_from_ctx(ctx, index_n);
    }
    else if (duk_is_function(ctx, index_n)) {
        return (PyObject *)DukFunction_from_ctx(ctx, index_n);
    }
    else if (duk_is_object(ctx, index_n)) {
        /* Other objects than arrays or functions */
        return (PyObject *)DukObject_from_ctx(ctx, index_n);
    }
    else if (duk_check_type(ctx, index_n, DUK_TYPE_BUFFER)) {
        PyErr_SetString(PyExc_TypeError, "'buffer' is not coercible");
        return NULL;

    }
    else if (duk_check_type(ctx, index_n, DUK_TYPE_POINTER)) {
        PyErr_SetString(PyExc_TypeError, "'pointer' is not coercible");
        return NULL;
    }

    /* Not reached */
    return NULL;
}
