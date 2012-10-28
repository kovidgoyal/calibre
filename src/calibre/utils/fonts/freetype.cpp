/*
 * freetype.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define _UNICODE
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <ft2build.h> 
#include FT_FREETYPE_H

static PyObject *FreeTypeError = NULL;

typedef struct {
    PyObject_HEAD
    FT_Face face;
    // Every face must keep a reference to the FreeType library object to
    // ensure it is garbage collected before the library object, to prevent
    // segfaults.
    PyObject *library;
    PyObject *data;
} Face;

typedef struct {
    PyObject_HEAD
    FT_Library library;
} FreeType;

// Face.__init__() {{{
static void
Face_dealloc(Face* self)
{
    if (self->face != NULL) {
        Py_BEGIN_ALLOW_THREADS;
        FT_Done_Face(self->face);
        Py_END_ALLOW_THREADS;
    }
    self->face = NULL;

    Py_XDECREF(self->library);
    self->library = NULL;

    Py_XDECREF(self->data);
    self->data = NULL;

    self->ob_type->tp_free((PyObject*)self);
}

static int
Face_init(Face *self, PyObject *args, PyObject *kwds)
{
    FT_Error error = 0;
    char *data;
    Py_ssize_t sz;
    PyObject *ft;

    if (!PyArg_ParseTuple(args, "Os#", &ft, &data, &sz)) return -1;

    Py_BEGIN_ALLOW_THREADS;
    error = FT_New_Memory_Face( ( (FreeType*)ft )->library,
            (const FT_Byte*)data, (FT_Long)sz, 0, &self->face);
    Py_END_ALLOW_THREADS;
    if (error) {
        self->face = NULL;
        if ( error == FT_Err_Unknown_File_Format || error == FT_Err_Invalid_Stream_Operation)
            PyErr_SetString(FreeTypeError, "Not a supported font format");
        else
            PyErr_Format(FreeTypeError, "Failed to initialize the Font with error: 0x%x", error);
        return -1;
    }
    self->library = ft;
    Py_XINCREF(ft);

    self->data = PySequence_GetItem(args, 1);
    return 0;
}

// }}}

static PyObject *
family_name(Face *self, void *closure) {
    return Py_BuildValue("s", self->face->family_name);
} 

static PyObject *
style_name(Face *self, void *closure) {
    return Py_BuildValue("s", self->face->style_name);
} 

static PyObject*
supports_text(Face *self, PyObject *args) {
    PyObject *chars, *fast, *ret = Py_True;
    Py_ssize_t sz, i;
    FT_ULong code;

    if (!PyArg_ParseTuple(args, "O", &chars)) return NULL;
    fast = PySequence_Fast(chars, "List of chars is not a sequence");
    if (fast == NULL) return NULL;
    sz = PySequence_Fast_GET_SIZE(fast);

    for (i = 0; i < sz; i++) {
        code = (FT_ULong)PyNumber_AsSsize_t(PySequence_Fast_GET_ITEM(fast, i), NULL);
        if (FT_Get_Char_Index(self->face, code) == 0) {
            ret = Py_False;
            break;
        }
    }

    Py_DECREF(fast);
    Py_XINCREF(ret);
    return ret;
}

static PyGetSetDef Face_getsetters[] = {
    {(char *)"family_name", 
     (getter)family_name, NULL,
     (char *)"The family name of this font.",
     NULL},

    {(char *)"style_name", 
     (getter)style_name, NULL,
     (char *)"The style name of this font.",
     NULL},

    {NULL}  /* Sentinel */
};

static PyMethodDef Face_methods[] = {
    {"supports_text", (PyCFunction)supports_text, METH_VARARGS,
     "supports_text(sequence of unicode character codes) -> Return True iff this font has glyphs for all the specified characters."
    },

    {NULL}  /* Sentinel */
};

// FreeType.__init__() {{{
static void
dealloc(FreeType* self)
{
    if (self->library != NULL) {
        Py_BEGIN_ALLOW_THREADS;
        FT_Done_FreeType(self->library);
        Py_END_ALLOW_THREADS;
    }
    self->library = NULL;

    self->ob_type->tp_free((PyObject*)self);
}

static int
init(FreeType *self, PyObject *args, PyObject *kwds)
{
    FT_Error error = 0;
    Py_BEGIN_ALLOW_THREADS;
    error = FT_Init_FreeType(&self->library);
    Py_END_ALLOW_THREADS;
    if (error) {
        self->library = NULL;
        PyErr_Format(FreeTypeError, "Failed to initialize the FreeType library with error: %d", error);
        return -1;
    }
    return 0;
}

// }}}

static PyTypeObject FaceType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "freetype.Face",            /*tp_name*/
    sizeof(Face),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Face_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Face",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    Face_methods,             /* tp_methods */
    0,             /* tp_members */
    Face_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Face_init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

static PyObject*
load_font(FreeType *self, PyObject *args) {
    PyObject *ret, *arg_list, *bytes;

    if (!PyArg_ParseTuple(args, "O", &bytes)) return NULL;

    arg_list = Py_BuildValue("OO", self, bytes);
    if (arg_list == NULL) return NULL;

    ret = PyObject_CallObject((PyObject *) &FaceType, arg_list);
    Py_DECREF(arg_list);

    return ret;
}

static PyMethodDef FreeType_methods[] = {
    {"load_font", (PyCFunction)load_font, METH_VARARGS,
     "load_font(bytestring) -> Load a font from font data."
    },

    {NULL}  /* Sentinel */
};


static PyTypeObject FreeTypeType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "freetype.FreeType",            /*tp_name*/
    sizeof(FreeType),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "FreeType",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    FreeType_methods,             /* tp_methods */
    0,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

static 
PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initfreetype(void) {
    PyObject *m;

    FreeTypeType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&FreeTypeType) < 0)
        return;

    FaceType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&FaceType) < 0)
        return;

    m = Py_InitModule3(
            "freetype", methods,
            "FreeType API"
    );
    if (m == NULL) return;

    FreeTypeError = PyErr_NewException((char*)"freetype.FreeTypeError", NULL, NULL);
    if (FreeTypeError == NULL) return;
    PyModule_AddObject(m, "FreeTypeError", FreeTypeError);

    Py_INCREF(&FreeTypeType);
    PyModule_AddObject(m, "FreeType", (PyObject *)&FreeTypeType);
    PyModule_AddObject(m, "Face", (PyObject *)&FaceType);
}

