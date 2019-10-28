/*
 * html_as_json.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Python.h>
#include <algorithm>

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
	PyObject *buf;
	size_t used;
} Serializer;


static PyObject *
alloc(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Serializer *self;

    self = (Serializer *)type->tp_alloc(type, 0);
	if (self != NULL) {
		self->used = 0;
		self->buf = NULL;
	}
    return (PyObject *)self;
}


static void
dealloc(Serializer* self)
{
	Py_CLEAR(self->buf);
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static bool
write_data(Serializer *self, const char *data, size_t sz) {
	if (!self->buf) {
		self->buf = PyBytes_FromStringAndSize(NULL, std::max(sz, static_cast<size_t>(128u * 1024u)));
		if (!self->buf) return false;
	}
	size_t new_used = self->used + sz;
	if (new_used > static_cast<size_t>(PyBytes_GET_SIZE(self->buf))) {
		if (_PyBytes_Resize(&(self->buf), std::max(new_used, static_cast<size_t>(2 * PyBytes_GET_SIZE(self->buf)))) != 0) return false;
	}
	memcpy(PyBytes_AS_STRING(self->buf) + self->used, data, sz);
	self->used = new_used;
	return true;
}


static PyObject*
pywrite(Serializer *self, PyObject *arg) {
	const char *data;
	size_t sz;
	PyObject *temp = NULL;
	if (PyBytes_Check(arg)) {
		data = PyBytes_AS_STRING(arg);
		sz = PyBytes_GET_SIZE(arg);
	} else if (PyUnicode_Check(arg)) {
#if PY_MAJOR_VERSION > 2
		Py_ssize_t ssz;
		data = PyUnicode_AsUTF8AndSize(arg, &ssz);
		sz = ssz;
		if (data == NULL) return NULL;
#else
		temp = PyUnicode_AsUTF8String(arg);
		if (temp == NULL) return NULL;
		data = PyBytes_AS_STRING(temp);
		sz = PyBytes_GET_SIZE(temp);
#endif
	} else {
		PyErr_SetString(PyExc_TypeError, "A unicode or bytes object expected");
		return NULL;
	}
	bool ok = write_data(self, data, sz);
	Py_CLEAR(temp);
	if (!ok) return NULL;
	Py_RETURN_NONE;
}

static PyObject*
done(Serializer *self, PyObject *arg) {
	(void)arg;
	if (!self->buf) return PyBytes_FromString("");
	if (_PyBytes_Resize(&self->buf, self->used) != 0) return NULL;
	PyObject *ans = self->buf;
	self->buf = NULL;
	self->used = 0;
	return ans;
}

// Type definition {{{

static PyMethodDef Serializer_methods[] = {
    {"write", (PyCFunction)pywrite, METH_O,
     "Write the specified unicode or bytes object"
    },
    {"done", (PyCFunction)done, METH_NOARGS,
     "Get the serialized output"
    },
    {NULL}  /* Sentinel */
};

PyTypeObject SerializerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "html_as_json.Serializer",
    /* tp_basicsize      */ sizeof(Serializer),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)dealloc,
    /* tp_print          */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_compare        */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */ "Serializer",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ Serializer_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ alloc,
};
// }}}

static char doc[] = "Serialize HTML as JSON efficiently";
static PyMethodDef methods[] = {
    {NULL}  /* Sentinel */
};

#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
#define INITMODULE PyModule_Create(&module)
static struct PyModuleDef module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "html_as_json",
    /* m_doc      */ doc,
    /* m_size     */ -1,
    /* m_methods  */ methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};
CALIBRE_MODINIT_FUNC PyInit_html_as_json(void) {
#else
#define INITERROR return
#define INITMODULE Py_InitModule3("html_as_json", methods, doc)
CALIBRE_MODINIT_FUNC inithtml_as_json(void) {
#endif

    PyObject* m;

    if (PyType_Ready(&SerializerType) < 0) {
        INITERROR;
    }


    m = INITMODULE;
    if (m == NULL) {
        INITERROR;
    }

    PyModule_AddObject(m, "Serializer", (PyObject *)&SerializerType);


#if PY_MAJOR_VERSION >= 3
    return m;
#endif
}
