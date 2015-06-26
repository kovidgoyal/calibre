#include "dukpy.h"

/* DukObject */

static void DukObject_INIT(DukObject *self, DukContext *context,
                           duk_idx_t index)
{
    duk_context *ctx = context->ctx;
    duk_idx_t index_n = duk_normalize_index(ctx, index);

    Py_INCREF(context);
    self->context = context;
    self->parent = NULL;

    /* heap_stash[(void *)self] = proxied_value */
    duk_push_heap_stash(ctx);
    duk_push_pointer(ctx, self);
    duk_dup(ctx, index_n);
    duk_put_prop(ctx, -3);
    duk_pop(ctx);
}

static void DukObject_DESTRUCT(DukObject *self)
{
    duk_context *ctx = self->context->ctx;

    /* delete heap_stash[(void *)self] */
    duk_push_heap_stash(ctx);
    duk_push_pointer(ctx, self);
    duk_del_prop(ctx, -2);
    duk_pop(ctx);

    Py_XDECREF(self->parent);
    Py_DECREF(self->context);
}

DukObject *DukObject_from_DukContext(DukContext *context, duk_idx_t index)
{
    DukObject *self;

    self = PyObject_New(DukObject, &DukObject_Type);
    if (self == NULL)
        return NULL;

    DukObject_INIT(self, context, index);
    return self;
}

DukObject *DukObject_from_ctx(duk_context *ctx, duk_idx_t index)
{
    DukContext *context = DukContext_get(ctx);

    if (!context) {
        PyErr_Format(PyExc_RuntimeError, "Unknown context %p", ctx);
        return NULL;
    }

    return DukObject_from_DukContext(context, index);
}

static void DukObject_dealloc(DukObject *self)
{
    DukObject_DESTRUCT(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

int DukObject_push(DukObject *self, duk_context *ctx)
{
    /* Push the proxied value to given context's stack */
    duk_push_heap_stash(ctx);
    duk_push_pointer(ctx, self);
    duk_get_prop(ctx, -2);
    duk_replace(ctx, -2);

    return 0;
}

#define PUSH(p) DukObject_push((p), (p)->context->ctx)


static PyObject *DukObject_getattr(DukObject *self, PyObject *name)
{
    duk_context *ctx = self->context->ctx;
    PyObject *value;

    /* Look up normal attributes first */
    if (!(value = PyObject_GenericGetAttr((PyObject *)self, name))) {
        if (!PyErr_ExceptionMatches(PyExc_AttributeError))
            return NULL;
        PyErr_Clear();
    } else {
        return value;
    }

    /* Not found, query the duktape object */
    PUSH(self);

    if (python_to_duk(ctx, name) != 0) {
        duk_pop(ctx);
        return NULL;
    }

    duk_get_prop(ctx, -2);
    value = duk_to_python(ctx, -1);
    duk_pop_n(ctx, 2);

    if (Py_TYPE(value) == &DukFunction_Type) {
        /* Set parent link for method calls */
        Py_INCREF(self);
        ((DukObject *)value)->parent = self;
    }

    return value;
}

static int DukObject_setattr(DukObject *self, PyObject *name, PyObject *value)
{
    duk_context *ctx = self->context->ctx;

    PUSH(self);

    if (python_to_duk(ctx, name) != 0) {
        duk_pop(ctx);
        return -1;
    }

    if (python_to_duk(ctx, value) != 0) {
        duk_pop_n(ctx, 2);
        return -1;
    }

    duk_put_prop(ctx, -3);
    duk_pop(ctx);

    return 0;
}

static PyObject *DukObject_make_enum(DukObject *self, dukenum_mode_t mode)
{
    duk_context *ctx = self->context->ctx;
    PyObject *result;

    PUSH(self);

    duk_enum(ctx, -1, 0);
    result = (PyObject *)DukEnum_from_DukContext(self->context, mode);
    duk_pop(ctx);

    return result;
}


static PyObject *DukObject_iter(DukObject *self)
{
    return DukObject_make_enum(self, DUKENUM_KEYS);
}


static PyObject *DukObject_keys(DukObject *self, PyObject *args)
{
    (void)args;
    return DukObject_make_enum(self, DUKENUM_KEYS);
}

static PyObject *DukObject_values(DukObject *self, PyObject *args)
{
    (void)args;
    return DukObject_make_enum(self, DUKENUM_VALUES);
}

static PyObject *DukObject_items(DukObject *self, PyObject *args)
{
    (void)args;
    return DukObject_make_enum(self, DUKENUM_PAIRS);
}

static PyMappingMethods DukObject_as_mapping = {
    NULL,
    (binaryfunc)DukObject_getattr,
    (objobjargproc)DukObject_setattr
};

static PyMethodDef DukObject_methods[] = {
    {"keys", (PyCFunction)DukObject_keys, METH_NOARGS,
     "Iterate over object keys"},
    {"values", (PyCFunction)DukObject_values, METH_NOARGS,
     "Iterate over object values"},
    {"items", (PyCFunction)DukObject_items, METH_NOARGS,
     "Iterate over key-value pairs"},
    {NULL}
};


PyTypeObject DukObject_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Object proxy",                  /* tp_name */
    sizeof(DukObject),               /* tp_basicsize */
    0,                               /* tp_itemsize */
    (destructor)DukObject_dealloc,   /* tp_dealloc */
    0,                               /* tp_print */
    0,                               /* tp_getattr */
    0,                               /* tp_setattr */
    0,                               /* tp_reserved */
    0,                               /* tp_repr */
    0,                               /* tp_as_number */
    0,                               /* tp_as_sequence */
    &DukObject_as_mapping,           /* tp_as_mapping */
    0,                               /* tp_hash  */
    0,                               /* tp_call */
    0,                               /* tp_str */
    (getattrofunc)DukObject_getattr, /* tp_getattro */
    (setattrofunc)DukObject_setattr, /* tp_setattro */
    0,                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,              /* tp_flags */
    "Duktape object proxy",          /* tp_doc */
    0,                               /* tp_traverse */
    0,                               /* tp_clear */
    0,                               /* tp_richcompare */
    0,                               /* tp_weaklistoffset */
    (getiterfunc)DukObject_iter,     /* tp_iter */
    0,                               /* tp_iternext */
    DukObject_methods,               /* tp_methods */
    0,                               /* tp_members */
    0,                               /* tp_getset */
    0,                               /* tp_base */
    0,                               /* tp_dict */
    0,                               /* tp_descr_get */
    0,                               /* tp_descr_set */
    0,                               /* tp_dictoffset */
    0,                               /* tp_init */
    0,                               /* tp_alloc */
    0                                /* tp_new */
};


/* DukArray */

DukObject *DukArray_from_ctx(duk_context *ctx, duk_idx_t index)
{
    DukObject *self;
    DukContext *context = DukContext_get(ctx);

    if (!context) {
        PyErr_Format(PyExc_RuntimeError, "Unknown context %p", ctx);
        return NULL;
    }

    self = PyObject_New(DukObject, &DukArray_Type);
    if (self == NULL)
        return NULL;

    DukObject_INIT(self, context, index);
    return self;
}

Py_ssize_t DukArray_length(DukObject *self)
{
    duk_context *ctx = self->context->ctx;
    duk_size_t len;

    PUSH(self);
    len = duk_get_length(ctx, -1);
    duk_pop(ctx);

    return (Py_ssize_t)len;
}

static PyObject *DukArray_getitem(DukObject *self, Py_ssize_t i)
{
    duk_context *ctx = self->context->ctx;
    PyObject *result;

    PUSH(self);
    duk_get_prop_index(ctx, -1, (duk_uarridx_t)i);

    result = duk_to_python(ctx, -1);
    if (!result)
        duk_pop(ctx);
    else
        duk_pop_n(ctx, 2);

#if 0
    if (result == Duk_undefined) {
        Py_DECREF(result);
        PyErr_Format(PyExc_IndexError, "%R has no index %li", self, i);
        return NULL;
    }
#endif

    return result;
}

static int DukArray_setitem(DukObject *self, Py_ssize_t i, PyObject *value)
{
    duk_context *ctx = self->context->ctx;
    PUSH(self);

    if (value) {
        /* self[i] = value */
        if (python_to_duk(ctx, value) == -1) {
            duk_pop(ctx);
            return -1;
        }
        duk_put_prop_index(ctx, -2, (duk_uarridx_t)i);
    } else {
        /* del self[i]

           Note that this always succeeds, even if the index doesn't
           exist.
        */
        duk_del_prop_index(ctx, -1, (duk_uarridx_t)i);
        duk_pop(ctx);
    }

    return 0;
}

static PyObject *DukArray_iter(DukObject *self)
{
    duk_context *ctx = self->context->ctx;
    PyObject *result;

    PUSH(self);

    duk_enum(ctx, -1, DUK_ENUM_ARRAY_INDICES_ONLY);
    result = (PyObject *)DukEnum_from_DukContext(self->context, DUKENUM_VALUES);
    duk_pop(ctx);

    return result;
}

static PySequenceMethods DukArray_as_sequence = {
    (lenfunc)DukArray_length,           /* sq_length */
    NULL,                               /* sq_concat */
    NULL,                               /* sq_repeat */
    (ssizeargfunc)DukArray_getitem,     /* sq_item */
    NULL,                               /* unused */
    (ssizeobjargproc)DukArray_setitem,  /* sq_ass_item */
    NULL,                               /* sq_contains */
    NULL,                               /* sq_inplace_concat */
    NULL,                               /* sq_inplace_repeat */
};


PyTypeObject DukArray_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Array proxy",                   /* tp_name */
    sizeof(DukObject),               /* tp_basicsize */
    0,                               /* tp_itemsize */
    (destructor)DukObject_dealloc,   /* tp_dealloc */
    0,                               /* tp_print */
    0,                               /* tp_getattr */
    0,                               /* tp_setattr */
    0,                               /* tp_reserved */
    0,                               /* tp_repr */
    0,                               /* tp_as_number */
    &DukArray_as_sequence,           /* tp_as_sequence */
    0,                               /* tp_as_mapping */
    0,                               /* tp_hash  */
    0,                               /* tp_call */
    0,                               /* tp_str */
    (getattrofunc)DukObject_getattr, /* tp_getattro */
    (setattrofunc)DukObject_setattr, /* tp_setattro */
    0,                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,              /* tp_flags */
    "Duktape array proxy" ,          /* tp_doc */
    0,                               /* tp_traverse */
    0,                               /* tp_clear */
    0,                               /* tp_richcompare */
    0,                               /* tp_weaklistoffset */
    (getiterfunc)DukArray_iter       /* tp_iter */
};


/* DukFunction */

DukObject *DukFunction_from_ctx(duk_context *ctx, duk_idx_t index)
{
    DukObject *self;
    DukContext *context = DukContext_get(ctx);

    if (!context) {
        PyErr_Format(PyExc_RuntimeError, "Unknown context %p", ctx);
        return NULL;
    }

    self = PyObject_New(DukObject, &DukFunction_Type);
    if (self == NULL)
        return NULL;

    DukObject_INIT(self, context, index);
    return self;
}

PyObject* DukFunction_call(DukObject *self, PyObject *args, PyObject *kw)
{
    duk_context *ctx = self->context->ctx;
    Py_ssize_t nargs, i;
    int return_none = 0, ret = 0;
    PyObject *result, *temp;

    /* NULL if no parent */
    PyObject *this = (PyObject *)self->parent;

    if (kw) {

        temp = PyDict_GetItemString(kw, "this");
        if (temp)
            this = temp;

        temp = PyDict_GetItemString(kw, "return_none");
        if (temp)
            return_none = PyObject_IsTrue(temp);
    }
    nargs = PyTuple_Size(args);

    /* Push the function */
    PUSH(self);

    if (this) {
        /* Push the "this" binding */
        if (python_to_duk(ctx, this) == -1) {
            duk_pop(ctx);
            return NULL;
        }
    }
    /* Push args */
    for (i = 0; i < nargs; i++) {
        PyObject *arg = PyTuple_GetItem(args, i);
        if (python_to_duk(ctx, arg) == -1) {
            duk_pop_n(ctx, 1 + (this ? 1 : 0) + (duk_idx_t)i);
            return NULL;
        }
    }

    if (this)
        ret = duk_pcall_method(ctx, (duk_idx_t)nargs);
    else
        ret = duk_pcall(ctx, (duk_idx_t)nargs);

    if (ret != DUK_EXEC_SUCCESS) {
        temp = duk_to_python(ctx, -1);
        duk_pop(ctx);
        if (temp) {
            PyErr_SetObject(JSError, temp);
            Py_DECREF(temp);
        } else PyErr_SetString(PyExc_RuntimeError, "The was an error during call(), but the error could not be read of the stack");
        return NULL;
    }

    if (return_none) {
        /* Always return None. This saves converting the function's
           return value. */
        duk_pop(ctx);
        Py_RETURN_NONE;
    } else {
        result = duk_to_python(ctx, -1);
        duk_pop(ctx);
        return result;
    }
}

PyTypeObject DukFunction_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Function proxy",                /* tp_name */
    sizeof(DukObject),               /* tp_basicsize */
    0,                               /* tp_itemsize */
    (destructor)DukObject_dealloc,   /* tp_dealloc */
    0,                               /* tp_print */
    0,                               /* tp_getattr */
    0,                               /* tp_setattr */
    0,                               /* tp_reserved */
    0,                               /* tp_repr */
    0,                               /* tp_as_number */
    0,                               /* tp_as_sequence */
    0,                               /* tp_as_mapping */
    0,                               /* tp_hash  */
    (ternaryfunc)DukFunction_call,   /* tp_call */
    0,                               /* tp_str */
    (getattrofunc)DukObject_getattr, /* tp_getattro */
    (setattrofunc)DukObject_setattr, /* tp_setattro */
    0,                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,              /* tp_flags */
    "Duktape function proxy"         /* tp_doc */
};


/* DukEnum */

DukEnum *DukEnum_from_DukContext(DukContext *context, dukenum_mode_t mode)
{
    DukEnum *self;

    self = PyObject_New(DukEnum, &DukEnum_Type);
    if (self == NULL)
        return NULL;

    DukObject_INIT(&self->base, context, -1);
    self->mode = mode;

    return self;
}

static void DukEnum_dealloc(DukEnum *self)
{
    DukObject_DESTRUCT(&self->base);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *DukEnum_iter(DukEnum *self)
{
    Py_INCREF(self);
    return (PyObject *)self;
}

static PyObject *DukEnum_iternext(DukEnum *self)
{
    duk_context *ctx = self->base.context->ctx;
    PyObject *result = NULL;
    int mode = self->mode;
    int get_value = mode == DUKENUM_VALUES || mode == DUKENUM_PAIRS;
    int pop = 1;

    PUSH(&self->base);

    if (duk_next(ctx, -1, get_value)) {
        switch (mode) {
            case DUKENUM_KEYS:
                result = duk_to_python(ctx, -1);
                pop = 2;
                break;
            case DUKENUM_VALUES:
                result = duk_to_python(ctx, -1);
                pop = 3;
                break;
            case DUKENUM_PAIRS:
                result = Py_BuildValue("(NN)",
                                       duk_to_python(ctx, -2),
                                       duk_to_python(ctx, -1));
                pop = 3;
                break;
        }
    }

    duk_pop_n(ctx, pop);
    return result;
}

PyTypeObject DukEnum_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Enumerator",                    /* tp_name */
    sizeof(DukEnum),                 /* tp_basicsize */
    0,                               /* tp_itemsize */
    (destructor)DukEnum_dealloc,     /* tp_dealloc */
    0,                               /* tp_print */
    0,                               /* tp_getattr */
    0,                               /* tp_setattr */
    0,                               /* tp_reserved */
    0,                               /* tp_repr */
    0,                               /* tp_as_number */
    0,                               /* tp_as_sequence */
    0,                               /* tp_as_mapping */
    0,                               /* tp_hash  */
    0,                               /* tp_call */
    0,                               /* tp_str */
    0,                               /* tp_getattro */
    0,                               /* tp_setattro */
    0,                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,              /* tp_flags */
    "Duktape enumerator",            /* tp_doc */
    0,                               /* tp_traverse */
    0,                               /* tp_clear */
    0,                               /* tp_richcompare */
    0,                               /* tp_weaklistoffset */
    (getiterfunc)DukEnum_iter,       /* tp_iter */
    (iternextfunc)DukEnum_iternext,  /* tp_iternext */
};
