/*
 * html.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#define COMPARE(attr, op) (PyObject_RichCompareBool(a->attr, b->attr, op) == 1)
static PyObject *bold_tags = NULL, *italic_tags = NULL, *zero = NULL, *spell_property = NULL, *recognized = NULL, *split = NULL;

// Tag type definition {{{

static PyTypeObject html_TagType;

typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    PyObject *name;
    PyObject *bold;
    PyObject *italic;
    PyObject *lang;

} html_Tag;

static void
html_Tag_dealloc(html_Tag* self)
{
    Py_XDECREF(self->name); self->name = NULL;
    Py_XDECREF(self->bold); self->bold = NULL;
    Py_XDECREF(self->italic); self->italic = NULL;
    Py_XDECREF(self->lang); self->lang = NULL;
    self->ob_type->tp_free((PyObject*)self);
}


static PyObject *
html_Tag_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    html_Tag *self = NULL;
    self = (html_Tag *)type->tp_alloc(type, 0);
    if (self == NULL) return PyErr_NoMemory();

    self->bold = NULL; self->italic = NULL; self->lang = NULL;
    if (!PyArg_ParseTuple(args, "O|OOO", &(self->name), &(self->bold), &(self->italic), &(self->lang))) {
        self->ob_type->tp_free((PyObject*)self); return NULL;
    }
    if (self->bold == NULL) {
        self->bold = (PySet_Contains(bold_tags, self->name)) ? Py_True : Py_False;
    }
    if (self->italic == NULL) {
        self->italic = (PySet_Contains(italic_tags, self->name)) ? Py_True : Py_False;
    }
    if (self->lang == NULL) self->lang = Py_None;
    Py_INCREF(self->name); Py_INCREF(self->bold); Py_INCREF(self->italic); Py_INCREF(self->lang);

    return (PyObject *)self;
}

static PyObject *
html_Tag_copy(html_Tag *self, PyObject *args, PyObject *kwargs) {
    return PyObject_CallFunctionObjArgs((PyObject *) &html_TagType, self->name, self->bold, self->italic, self->lang, NULL);
}

static PyObject *
html_Tag_compare(html_Tag *a, html_Tag *b, int op) {
    if (!PyObject_TypeCheck(a, &html_TagType) || !PyObject_TypeCheck(b, &html_TagType)) {
        switch (op) {
            case Py_EQ:
                Py_RETURN_FALSE;
            case Py_NE:
                Py_RETURN_TRUE;
            default:
                break;
        }
    } else {
        switch (op) {
            case Py_EQ:
                if (COMPARE(name, Py_EQ) && COMPARE(lang, Py_EQ)) Py_RETURN_TRUE;
                Py_RETURN_FALSE;
            case Py_NE:
                if (COMPARE(name, Py_NE) || COMPARE(lang, Py_NE)) Py_RETURN_TRUE;
                Py_RETURN_FALSE;
            default:
                break;
        }
    }
    PyErr_SetString(PyExc_TypeError, "Only equals comparison is supported for Tag objects");
    return NULL;
}

static PyObject *
html_Tag_repr(html_Tag *self) {
    PyObject *name = NULL, *bold = NULL, *italic = NULL, *lang = NULL, *ans = NULL;
    name = PyObject_Repr(self->name); bold = PyObject_Repr(self->bold); italic = PyObject_Repr(self->italic); lang = PyObject_Repr(self->lang);
    if (name && bold && italic && lang)
        ans = PyString_FromFormat("Tag(%s, bold=%s, italic=%s, lang=%s)", PyString_AS_STRING(name), PyString_AS_STRING(bold), PyString_AS_STRING(italic), PyString_AS_STRING(lang));
    Py_XDECREF(name); Py_XDECREF(bold); Py_XDECREF(italic); Py_XDECREF(lang);
    return ans;
}

static PyMemberDef html_Tag_members[] = {
    {"name", T_OBJECT_EX, offsetof(html_Tag, name), 0, "Name of the tag in lowercase"},
    {"bold", T_OBJECT_EX, offsetof(html_Tag, bold), 0, "True iff tag is bold"},
    {"italic", T_OBJECT_EX, offsetof(html_Tag, italic), 0, "True iff tag is italic"},
    {"lang", T_OBJECT_EX, offsetof(html_Tag, lang), 0, "The language of this tag"},
    {NULL}  /* Sentinel */
};

static PyMethodDef html_Tag_methods[] = {
    {"copy", (PyCFunction)html_Tag_copy, METH_VARARGS,
     "copy() -> Return a copy of this Tag"
    },

    {NULL}  /* Sentinel */
};

static PyTypeObject html_TagType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "html.Tag",            /*tp_name*/
    sizeof(html_Tag),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)html_Tag_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    (reprfunc)html_Tag_repr,                         /*tp_repr*/
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
    "Token",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    (richcmpfunc)html_Tag_compare,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    html_Tag_methods,             /* tp_methods */
    html_Tag_members,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    html_Tag_new,                 /* tp_new */
}; // }}}
// }}}

// State type definition {{{

static PyTypeObject html_StateType;

typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    PyObject *tag_being_defined; 
    PyObject *tags; 
    PyObject *is_bold; 
    PyObject *is_italic; 
    PyObject *current_lang;
    PyObject *parse; 
    PyObject *css_formats; 
    PyObject *sub_parser_state; 
    PyObject *default_lang; 
    PyObject *attribute_name;

} html_State;

static void
html_State_dealloc(html_State* self)
{
    Py_XDECREF(self->tag_being_defined); self->tag_being_defined = NULL;
    Py_XDECREF(self->tags); self->tags = NULL;
    Py_XDECREF(self->is_bold); self->is_bold = NULL;
    Py_XDECREF(self->is_italic); self->is_italic = NULL;
    Py_XDECREF(self->current_lang); self->current_lang = NULL;
    Py_XDECREF(self->parse); self->parse = NULL;
    Py_XDECREF(self->css_formats); self->css_formats = NULL;
    Py_XDECREF(self->sub_parser_state); self->sub_parser_state = NULL;
    Py_XDECREF(self->default_lang); self->default_lang = NULL;
    Py_XDECREF(self->attribute_name);self->attribute_name = NULL;

    self->ob_type->tp_free((PyObject*)self);
}


static PyObject *
html_State_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    html_State *self = NULL;
    self = (html_State *)type->tp_alloc(type, 0);
    if (self == NULL) return PyErr_NoMemory();

    self->tag_being_defined = NULL;
    self->tags = NULL;
    self->is_bold = NULL;
    self->is_italic = NULL;
    self->current_lang = NULL;
    self->parse = NULL;
    self->css_formats = NULL;
    self->sub_parser_state = NULL;
    self->default_lang = NULL;
    self->attribute_name = NULL;

    if (!PyArg_ParseTuple(args, "|OOOOOOOOOO", 
            &(self->tag_being_defined),
            &(self->tags),
            &(self->is_bold),
            &(self->is_italic),
            &(self->current_lang),
            &(self->parse),
            &(self->css_formats),
            &(self->sub_parser_state),
            &(self->default_lang),
            &(self->attribute_name)))
    {
        self->ob_type->tp_free((PyObject*)self); return NULL;
    }

    if (self->tag_being_defined == NULL) self->tag_being_defined = Py_None;
    if (self->tags == NULL) { self->tags = PyList_New(0); if (self->tags == NULL) return PyErr_NoMemory(); }
    if (self->is_bold == NULL) self->is_bold = Py_False;
    if (self->is_italic == NULL) self->is_italic = Py_False;
    if (self->current_lang == NULL) self->current_lang = Py_None;
    if (self->parse == NULL) self->parse = zero;
    if (self->css_formats == NULL) self->css_formats = Py_None;
    if (self->sub_parser_state == NULL) self->sub_parser_state = Py_None;
    if (self->default_lang == NULL) self->default_lang = Py_None;
    if (self->attribute_name == NULL) self->attribute_name = Py_None;

    Py_INCREF(self->tag_being_defined);
    Py_INCREF(self->tags);
    Py_INCREF(self->is_bold);
    Py_INCREF(self->is_italic);
    Py_INCREF(self->current_lang);
    Py_INCREF(self->parse);
    Py_INCREF(self->css_formats);
    Py_INCREF(self->sub_parser_state);
    Py_INCREF(self->default_lang);
    Py_INCREF(self->attribute_name);

    return (PyObject *)self;
}

static PyObject *
html_State_copy(html_State *self, PyObject *args, PyObject *kwargs) {
    PyObject *ans = NULL, *tags = NULL, *tag_being_defined = NULL, *sub_parser_state = NULL;
    Py_ssize_t i = 0;

    if (self->sub_parser_state == Py_None) {sub_parser_state = Py_None; Py_INCREF(sub_parser_state); }
    else sub_parser_state = PyObject_CallMethod(self->sub_parser_state, "copy", NULL);
    if (sub_parser_state == NULL) goto end;

    if (self->tag_being_defined == Py_None) { tag_being_defined = Py_None; Py_INCREF(Py_None); }
    else tag_being_defined = html_Tag_copy((html_Tag*)self->tag_being_defined, NULL, NULL);
    if (tag_being_defined == NULL) goto end;

    tags = PyList_New(PyList_GET_SIZE(self->tags));
    if (tags == NULL) { PyErr_NoMemory(); goto end; }
    for (i = 0; i < PyList_GET_SIZE(self->tags); i++) {
        PyList_SET_ITEM(tags, i, PyList_GET_ITEM(self->tags, i));
        Py_INCREF(PyList_GET_ITEM(self->tags, i));
    }

    ans = PyObject_CallFunctionObjArgs((PyObject *) &html_StateType,
            tag_being_defined, tags, self->is_bold, self->is_italic, self->current_lang, self->parse, self->css_formats, sub_parser_state, self->default_lang, self->attribute_name, NULL);
end:
    Py_XDECREF(tags); Py_XDECREF(tag_being_defined); Py_XDECREF(sub_parser_state);
    return ans;
}


static PyObject *
html_State_compare(html_State *a, html_State *b, int op) {
    if (!PyObject_TypeCheck(a, &html_StateType) || !PyObject_TypeCheck(b, &html_StateType)) {
        switch (op) {
            case Py_EQ:
                Py_RETURN_FALSE;
            case Py_NE:
                Py_RETURN_TRUE;
            default:
                break;
        }
    } else {
        switch (op) {
            case Py_EQ:
                if (COMPARE(parse, Py_EQ) && COMPARE(sub_parser_state, Py_EQ) && COMPARE(tag_being_defined, Py_EQ) && COMPARE(attribute_name, Py_EQ) && COMPARE(tags, Py_EQ)) Py_RETURN_TRUE;
                Py_RETURN_FALSE;
            case Py_NE:
                if (COMPARE(parse, Py_NE) || COMPARE(sub_parser_state, Py_NE) || COMPARE(tag_being_defined, Py_NE) || COMPARE(attribute_name, Py_NE) || COMPARE(tags, Py_NE)) Py_RETURN_TRUE;
                Py_RETURN_FALSE;
            default:
                break;
        }
    }
    PyErr_SetString(PyExc_TypeError, "Only equals comparison is supported for State objects");
    return NULL;
}

static PyObject *
html_State_repr(html_State *self) {
    PyObject *bold = NULL, *italic = NULL, *lang = NULL, *ans = NULL;
    bold = PyObject_Repr(self->is_bold); italic = PyObject_Repr(self->is_italic); lang = PyObject_Repr(self->current_lang);
    if (bold && italic && lang)
        ans = PyString_FromFormat("State(bold=%s, italic=%s, lang=%s)", PyString_AS_STRING(bold), PyString_AS_STRING(italic), PyString_AS_STRING(lang));
    Py_XDECREF(bold); Py_XDECREF(italic); Py_XDECREF(lang);
    return ans;
}

static PyMemberDef html_State_members[] = {
    {"tag_being_defined", T_OBJECT_EX, offsetof(html_State, tag_being_defined), 0, "xxx"},
    {"tags", T_OBJECT_EX, offsetof(html_State, tags), 0, "xxx"},
    {"is_bold", T_OBJECT_EX, offsetof(html_State, is_bold), 0, "xxx"},
    {"is_italic", T_OBJECT_EX, offsetof(html_State, is_italic), 0, "xxx"},
    {"current_lang", T_OBJECT_EX, offsetof(html_State, current_lang), 0, "xxx"},
    {"parse", T_OBJECT_EX, offsetof(html_State, parse), 0, "xxx"},
    {"css_formats", T_OBJECT_EX, offsetof(html_State, css_formats), 0, "xxx"},
    {"sub_parser_state", T_OBJECT_EX, offsetof(html_State, sub_parser_state), 0, "xxx"},
    {"default_lang", T_OBJECT_EX, offsetof(html_State, default_lang), 0, "xxx"},
    {"attribute_name", T_OBJECT_EX, offsetof(html_State, attribute_name), 0, "xxx"},
    {NULL}  /* Sentinel */
};

static PyMethodDef html_State_methods[] = {
    {"copy", (PyCFunction)html_State_copy, METH_VARARGS,
     "copy() -> Return a copy of this Tag"
    },

    {NULL}  /* Sentinel */
};

static PyTypeObject html_StateType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "html.State",            /*tp_name*/
    sizeof(html_State),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)html_State_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    (reprfunc)html_State_repr,                         /*tp_repr*/
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
    "Token",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    (richcmpfunc)html_State_compare,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    html_State_methods,             /* tp_methods */
    html_State_members,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    html_State_new,                 /* tp_new */
}; // }}}
// }}}

static PyObject*
html_init(PyObject *self, PyObject *args) {
    Py_XDECREF(spell_property); Py_XDECREF(recognized); Py_XDECREF(split);
    if (!PyArg_ParseTuple(args, "OOO", &spell_property, &recognized, &split)) return NULL;
    Py_INCREF(spell_property); Py_INCREF(recognized); Py_INCREF(split);
    Py_RETURN_NONE;
}

static PyObject*
html_check_spelling(PyObject *self, PyObject *args) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    PyObject *ans = NULL, *temp = NULL, *items = NULL, *text = NULL, *fmt = NULL, *locale = NULL, *sfmt = NULL, *_store_locale = NULL, *t = NULL, *utmp = NULL;
    long text_len = 0, start = 0, length = 0, ppos = 0; 
    int store_locale = 0, ok = 0;
    Py_ssize_t i = 0, j = 0;

    if (!PyArg_ParseTuple(args, "OlOOOO", &text, &text_len, &fmt, &locale, &sfmt, &_store_locale)) return NULL;
    store_locale = PyObject_IsTrue(_store_locale);
    temp = PyObject_GetAttrString(locale, "langcode");
    if (temp == NULL) goto error;
    items = PyObject_CallFunctionObjArgs(split, text, temp, NULL); 
    Py_DECREF(temp); temp = NULL;
    if (items == NULL) goto error;
    ans = PyTuple_New((2 * PyList_GET_SIZE(items)) + 1);
    if (ans == NULL) { PyErr_NoMemory(); goto error; }

#define APPEND(x, y) t = Py_BuildValue("lO", (x), y); if (t == NULL) goto error; PyTuple_SET_ITEM(ans, j, t); j += 1;

    for (i = 0, j = 0; i < PyList_GET_SIZE(items); i++) {
        temp = PyList_GET_ITEM(items, i);
        start = PyInt_AS_LONG(PyTuple_GET_ITEM(temp, 0)); length = PyInt_AS_LONG(PyTuple_GET_ITEM(temp, 1));
        temp = NULL;

        if (start > ppos) { APPEND(start - ppos, fmt) }
        ppos = start + length;

        utmp = PyUnicode_FromUnicode(PyUnicode_AS_UNICODE(text) + start, length);
        if (utmp == NULL) { PyErr_NoMemory(); goto error; }
        temp = PyObject_CallFunctionObjArgs(recognized, utmp, locale, NULL);
        Py_DECREF(utmp); utmp = NULL;
        if (temp == NULL) goto error;
        ok = PyObject_IsTrue(temp);
        Py_DECREF(temp); temp = NULL;

        if (ok) {
            APPEND(length, fmt)
        } else {
            if (store_locale) {
                temp = PyObject_CallFunctionObjArgs(spell_property, sfmt, locale, NULL);
                if (temp == NULL) goto error;
                APPEND(length, temp);
                Py_DECREF(temp); temp = NULL;
            } else {
                APPEND(length, sfmt);
            }
        }
    }
    if (ppos < text_len) {
        APPEND(text_len - ppos, fmt)
    }

    if (j < PyTuple_GET_SIZE(ans)) _PyTuple_Resize(&ans, j);
    goto end;

error:
    Py_XDECREF(ans); ans = NULL;
end:
    Py_XDECREF(items); Py_XDECREF(temp); 
    return ans;
}

static PyMethodDef html_methods[] = {
    {"init", html_init, METH_VARARGS,
        "init()\n\n Initialize this module"
    },

    {"check_spelling", html_check_spelling, METH_VARARGS,
        "html_check_spelling()\n\n Speedup inner loop for spell check"
    },

    {NULL, NULL, 0, NULL}
};


CALIBRE_MODINIT_FUNC
inithtml(void) {
    PyObject *m, *temp;
    if (PyType_Ready(&html_TagType) < 0)
        return;
    if (PyType_Ready(&html_StateType) < 0)
        return;

    temp = Py_BuildValue("ssssssss", "b", "strong", "h1", "h2", "h3", "h4", "h5", "h6", "h7");
    if (temp == NULL) return;
    bold_tags = PyFrozenSet_New(temp); Py_DECREF(temp);
    temp = Py_BuildValue("ss", "i", "em");
    if (temp == NULL) return;
    italic_tags = PyFrozenSet_New(temp); Py_DECREF(temp); temp = NULL;
    zero = PyInt_FromLong(0);
    if (bold_tags == NULL || italic_tags == NULL || zero == NULL) return;
    Py_INCREF(bold_tags); Py_INCREF(italic_tags);

    m = Py_InitModule3("html", html_methods,
    "Speedups for the html syntax highlighter."
    );
    if (m == NULL) return;
    Py_INCREF(&html_TagType);
    Py_INCREF(&html_StateType);
    PyModule_AddObject(m, "Tag", (PyObject *)&html_TagType);
    PyModule_AddObject(m, "State", (PyObject *)&html_StateType);
    PyModule_AddObject(m, "bold_tags", bold_tags);
    PyModule_AddObject(m, "italic_tags", italic_tags);
}
