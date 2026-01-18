/*
 * main.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE

#include <Python.h>
#include "mo_parser.h"

typedef struct {
    PyObject_HEAD

    PyObject *fallbacks;
    MOParser parser;
} Translator;

extern PyTypeObject Translator_Type;
static Translator *qt_translator = NULL;

static PyObject *
new_translator(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    const char *mo_data = NULL; Py_ssize_t sz = 0;
    if (!PyArg_ParseTuple(args, "|z#", &mo_data, &sz)) return NULL;
    Translator *self = (Translator *)(&Translator_Type)->tp_alloc(&Translator_Type, 0);
    if (self != NULL) {
        new (&self->parser) MOParser();
        if (mo_data != NULL) {
            std::string err;
            Py_BEGIN_ALLOW_THREADS;
            err = self->parser.load(mo_data, sz);
            Py_END_ALLOW_THREADS;
            if (err.size()) {
                Py_CLEAR(self);
                PyErr_SetString(PyExc_ValueError, err.c_str()); return NULL;
            }
        }
        self->fallbacks = PyList_New(0);
        if (!self->fallbacks) { Py_CLEAR(self); return NULL; }
    }
    return (PyObject*) self;
}

static void
dealloc_translator(Translator* self) {
    Py_CLEAR(self->fallbacks);
    self->parser.~MOParser();
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
plural(PyObject *self_, PyObject *pn) {
    if (!PyLong_Check(pn)) { PyErr_SetString(PyExc_TypeError, "n must be an integer"); return NULL; }
    unsigned long n = PyLong_AsUnsignedLong(pn);
    Translator *self = (Translator*)self_;
    return PyLong_FromUnsignedLong(self->parser.plural(n));
}

static PyObject*
add_fallback(PyObject *self_, PyObject *pn) {
    Translator *self = (Translator*)self_;
    if (Py_TYPE(pn) != &Translator_Type) { PyErr_SetString(PyExc_TypeError, "other must be a translator instance"); return NULL; }
    if (PyList_Append(self->fallbacks, pn) != 0) return NULL;
    Py_RETURN_NONE;
}

static PyObject*
info(PyObject *self_, PyObject *pn) {
    Translator *self = (Translator*)self_;
    PyObject *ans = PyDict_New();
    if (ans) {
        for (const auto& [key, value] : self->parser.info) {
            PyObject *val = PyUnicode_FromStringAndSize(value.data(), value.size());
            if (!val) { Py_CLEAR(ans); return NULL; }
            bool ok = PyDict_SetItemString(ans, key.c_str(), val) == 0;
            Py_DECREF(val);
            if (!ok) { Py_CLEAR(ans); return NULL; }
        }
    }
    return ans;
}


static PyObject*
charset(PyObject *s, PyObject *pn) {
    Translator *self = (Translator*)s;
    return self->parser.isLoaded() ? PyUnicode_FromString("UTF-8") : Py_NewRef(Py_None);
}

static PyObject*
install(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *names = NULL, *builtins_module = NULL, *builtins_dict = NULL;
    static const char *kwlist[] = {"names", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O", kwlist, &names)) return NULL;
    if (names != NULL && names != Py_None && !PySequence_Check(names)) {
        PyErr_SetString(PyExc_TypeError, "names must be a sequence"); return NULL; }

    builtins_module = PyImport_ImportModule("builtins");
    if (builtins_module == NULL) return NULL;
    builtins_dict = PyObject_GetAttrString(builtins_module, "__dict__");
    if (builtins_dict == NULL) { Py_DECREF(builtins_module); return NULL; }

#define S(name, method_name) { \
    PyObject *method = PyObject_GetAttrString(self, method_name); \
    if (method == NULL) { Py_DECREF(builtins_dict); Py_DECREF(builtins_module); return NULL; } \
    int ret = PyDict_SetItemString(builtins_dict, name, method); Py_DECREF(method); \
    if (ret != 0) { Py_DECREF(builtins_dict); Py_DECREF(builtins_module); return NULL; } }

    if (names != NULL && names != Py_None) {
#define N(name) { \
        PyObject *u = PyUnicode_FromString(name); \
        if (!u) { Py_DECREF(builtins_dict); Py_DECREF(builtins_module); return NULL; }  \
        int ok = PySequence_Contains(names, u); \
        Py_DECREF(u); \
        if (ok == -1) { Py_DECREF(builtins_dict); Py_DECREF(builtins_module); return NULL; }  \
        if (ok == 1) { S(name, name); } }

        N("ngettext"); N("pgettext"); N("npgettext");
#undef N
    }
    S("_", "gettext");
#undef S
    Py_DECREF(builtins_dict); Py_DECREF(builtins_module);
    Py_RETURN_NONE;
}

static bool
has_data(Translator *self) { return self->parser.isLoaded() || PyList_GET_SIZE(self->fallbacks) != 0; }

static PyObject*
gettext(PyObject *s, PyObject *msg) {
    Translator *self = (Translator*)s;
    if (!has_data(self)) return Py_NewRef(msg);
    if (!PyUnicode_Check(msg)) { PyErr_SetString(PyExc_TypeError, "message must be a string"); return NULL; }
    Py_ssize_t sz;
    const char *x = PyUnicode_AsUTF8AndSize(msg, &sz);
    std::string_view msgid(x, sz);
    auto ans = self->parser.gettext(msgid);
    if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(self->fallbacks); i++) {
        Translator *f = (Translator*)PyList_GET_ITEM(self->fallbacks, i);
        ans = f->parser.gettext(msgid);
        if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    }
    return Py_NewRef(msg);
}

static PyObject*
ngettext(PyObject *s, PyObject *args) {
    Translator *self = (Translator*)s;
    const char *singular, *plural; unsigned long n; Py_ssize_t sl, pl;
    if (!PyArg_ParseTuple(args, "s#s#k", &singular, &sl, &plural, &pl, &n)) return NULL;
    if (!has_data(self)) return Py_NewRef(PyTuple_GET_ITEM(args, n == 1 ? 0: 1));
    auto ans = self->parser.gettext(std::string_view(singular, sl), std::string_view(plural, pl), n);
    if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(self->fallbacks); i++) {
        Translator *f = (Translator*)PyList_GET_ITEM(self->fallbacks, i);
        ans = f->parser.gettext(std::string_view(singular, sl), std::string_view(plural, pl), n);
        if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    }
    return Py_NewRef(PyTuple_GET_ITEM(args, n == 1 ? 0: 1));
}

static PyObject*
pgettext(PyObject *s, PyObject *args) {
    Translator *self = (Translator*)s;
    if (!has_data(self)) return Py_NewRef(PyTuple_GET_ITEM(args, 1));
    const char *context, *message; Py_ssize_t cl, ml;
    if (!PyArg_ParseTuple(args, "s#s#", &context, &cl, &message, &ml)) return NULL;
    auto ans = self->parser.gettext(std::string_view(context, cl), std::string_view(message, ml));
    if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(self->fallbacks); i++) {
        Translator *f = (Translator*)PyList_GET_ITEM(self->fallbacks, i);
        ans = f->parser.gettext(std::string_view(context, cl), std::string_view(message, ml));
        if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    }
    return Py_NewRef(PyTuple_GET_ITEM(args, 1));
}

static PyObject*
npgettext(PyObject *s, PyObject *args) {
    Translator *self = (Translator*)s;
    const char *context, *singular, *plural; unsigned long n; Py_ssize_t cl, sl, pl;
    if (!PyArg_ParseTuple(args, "s#s#s#k", &context, &cl, &singular, &sl, &plural, &pl, &n)) return NULL;
    if (!has_data(self)) return Py_NewRef(PyTuple_GET_ITEM(args, n == 1 ? 1: 2));
    auto ans = self->parser.gettext(std::string_view(context, cl), std::string_view(singular, sl), std::string_view(plural, pl), n);
    if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(self->fallbacks); i++) {
        Translator *f = (Translator*)PyList_GET_ITEM(self->fallbacks, i);
        ans = f->parser.gettext(std::string_view(context, cl), std::string_view(singular, sl), std::string_view(plural, pl), n);
        if (ans.data() != NULL) return PyUnicode_FromStringAndSize(ans.data(), ans.size());
    }
    return Py_NewRef(PyTuple_GET_ITEM(args, n == 1 ? 1: 2));
}

static std::string_view
qt_translate(const char *context, const char *text) {
    if (qt_translator == NULL || !has_data(qt_translator)) return std::string_view(NULL, 0);
    const char *key = text;
    std::string buffer;  // must be thread safe so cannot use self->buffer
    if (context && context[0]) {
        buffer.append(context).push_back('\0'); buffer.append(text);
        key = buffer.c_str();
    }
    std::string_view msgid(key);
    auto ans = qt_translator->parser.gettext(msgid);
    if (ans.data() != NULL) return ans;
    for (Py_ssize_t i = 0; i < PyList_GET_SIZE(qt_translator->fallbacks); i++) {
        Translator *f = (Translator*)PyList_GET_ITEM(qt_translator->fallbacks, i);
        ans = f->parser.gettext(msgid);
        if (ans.data() != NULL) return ans;
    }
    return std::string_view(NULL, 0);
}

static PyObject*
set_as_qt_translator(PyObject *self, PyObject*) {
    Py_CLEAR(qt_translator);
    qt_translator = (Translator*)Py_NewRef(self);
    return PyLong_FromVoidPtr((void*)qt_translate);
}

static PyMethodDef translator_methods[] = {
    {"plural", plural, METH_O, "plural(n: int) -> int:\n\n"
        "Get the message catalog index based on the plural form specification."
    },
    {"add_fallback", add_fallback, METH_O, "add_fallback(other: Translator) -> None:\n\n"
        "Add a fallback translator."
    },
    {"install", (PyCFunction)install, METH_VARARGS | METH_KEYWORDS, "install(names=None) -> None:\n\n"
        "install translation functions into global namespace"
    },
    {"info", info, METH_NOARGS, "info() -> dict[str, str]:\n\n"
        "Return information about the mo file as a dict"
    },
    {"charset", charset, METH_NOARGS, "charset() -> str:\n\n"
        "Return the character set for this catalog"
    },
    {"gettext", gettext, METH_O, "gettext(message: str) -> str:\n\n"
        "Translate the provided message"
    },
    {"ngettext", ngettext, METH_VARARGS, "gettext(singular: str, plural: str, n: int) -> str:\n\n"
        "Translate the provided message"
    },
    {"pgettext", pgettext, METH_VARARGS, "pgettext(context: str, message: str) -> str:\n\n"
        "Translate the provided message"
    },
    {"npgettext", npgettext, METH_VARARGS, "gettext(context: str, singular: str, plural: str, n: int) -> str:\n\n"
        "Translate the provided message"
    },
    {"set_as_qt_translator", set_as_qt_translator, METH_NOARGS, "set_as_qt_translator() -> int:\n\n"
        "Set this translator to use as the translator for Qt and return a pointer to the qt_translate() function."
    },

    {NULL}  /* Sentinel */
};

PyTypeObject Translator_Type = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "translator.Translator",
    .tp_basicsize = sizeof(Translator),
    .tp_dealloc = (destructor)dealloc_translator,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "Translator",
    .tp_methods = translator_methods,
    .tp_new = new_translator,
};


static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *m) {
    if (PyType_Ready(&Translator_Type) < 0) return -1;
    if (PyModule_AddObject(m, "Translator", (PyObject *)&Translator_Type) != 0) return -1;
    Py_INCREF(&Translator_Type);
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

static void
module_free(void *module) { Py_CLEAR(qt_translator); }

CALIBRE_MODINIT_FUNC PyInit_translator(void) {
    module_def.m_name     = "translator";
    module_def.m_doc      = "Support for GNU gettext translations without holding the GIL so that it can be used in Qt as well";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
    module_def.m_free     = module_free;
	return PyModuleDef_Init(&module_def);
}
