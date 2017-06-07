/*
 * tokenizer.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

// Token type definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    PyObject *is_container;
    PyObject *type;
    PyObject *_as_css;
    PyObject *value;
    PyObject *unit;
    PyObject *line;
    PyObject *column;

} tokenizer_Token;

static void
tokenizer_Token_dealloc(tokenizer_Token* self)
{
    Py_XDECREF(self->is_container); self->is_container = NULL;
    Py_XDECREF(self->type); self->type = NULL;
    Py_XDECREF(self->_as_css); self->_as_css = NULL;
    Py_XDECREF(self->value); self->value = NULL;
    Py_XDECREF(self->unit); self->unit = NULL;
    Py_XDECREF(self->line); self->line = NULL;
    Py_XDECREF(self->column); self->column = NULL;
    self->ob_type->tp_free((PyObject*)self);
}


static PyObject *
tokenizer_Token_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    tokenizer_Token *self = NULL;
    self = (tokenizer_Token *)type->tp_alloc(type, 0);
    if (self == NULL) return PyErr_NoMemory();

    if (!PyArg_ParseTuple(args, "OOOOOO", &(self->type), &(self->_as_css), &(self->value), &(self->unit), &(self->line), &(self->column))) {
        self->ob_type->tp_free((PyObject*)self); return NULL;
    }
    Py_INCREF(self->type); Py_INCREF(self->_as_css); Py_INCREF(self->value); Py_INCREF(self->unit); Py_INCREF(self->line); Py_INCREF(self->column);
    self->is_container = Py_False; Py_INCREF(self->is_container);

    return (PyObject *)self;
}

static PyObject *
tokenizer_Token_repr(tokenizer_Token *self) {
    PyObject *type = NULL, *line = NULL, *column = NULL, *value = NULL, *ans = NULL, *unit = NULL;
    if (!self->type || !self->line || !self->column || !self->value) 
        return PyBytes_FromString("<Token NULL fields>");
    type = PyObject_Unicode(self->type); line = PyObject_Unicode(self->line); column = PyObject_Unicode(self->column); value = PyObject_Unicode(self->value);
    if (type && line && column && value) {
        if (self->unit != NULL && PyObject_IsTrue(self->unit)) {
            unit = PyObject_Unicode(self->unit);
            if (unit != NULL) 
                ans = PyUnicode_FromFormat("<Token %U at %U:%U %U%U>", type, line, column, value, unit);
            else
                PyErr_NoMemory();
        } else
            ans = PyUnicode_FromFormat("<Token %U at %U:%U %U>", type, line, column, value);
    } else PyErr_NoMemory();
    Py_XDECREF(type); Py_XDECREF(line); Py_XDECREF(column); Py_XDECREF(value); Py_XDECREF(unit);
    return ans;
}

static PyObject *
tokenizer_Token_as_css(tokenizer_Token *self, PyObject *args, PyObject *kwargs) {
    if (!self->_as_css) {
        Py_RETURN_NONE;
    }
    Py_INCREF(self->_as_css);
    return self->_as_css;
}

static PyMemberDef tokenizer_Token_members[] = {
    {"is_container", T_OBJECT_EX, offsetof(tokenizer_Token, is_container), 0, "False unless this token is a  container for other tokens"},
    {"type", T_OBJECT_EX, offsetof(tokenizer_Token, type), 0, "The token type"},
    {"_as_css", T_OBJECT_EX, offsetof(tokenizer_Token, _as_css), 0, "Internal variable, use as_css() method instead."},
    {"value", T_OBJECT_EX, offsetof(tokenizer_Token, value), 0, "The token value"},
    {"unit", T_OBJECT_EX, offsetof(tokenizer_Token, unit), 0, "The token unit"},
    {"line", T_OBJECT_EX, offsetof(tokenizer_Token, line), 0, "The token line number"},
    {"column", T_OBJECT_EX, offsetof(tokenizer_Token, column), 0, "The token column number"},
    {NULL}  /* Sentinel */
};

static PyMethodDef tokenizer_Token_methods[] = {
    {"as_css", (PyCFunction)tokenizer_Token_as_css, METH_VARARGS,
     "as_css() -> Return the CSS representation of this token"
    },

    {NULL}  /* Sentinel */
};

static PyTypeObject tokenizer_TokenType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "tokenizer.Token",            /*tp_name*/
    sizeof(tokenizer_Token),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)tokenizer_Token_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    (reprfunc)tokenizer_Token_repr,                         /*tp_repr*/
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
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    tokenizer_Token_methods,             /* tp_methods */
    tokenizer_Token_members,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    tokenizer_Token_new,                 /* tp_new */
}; // }}}
// }}}

static PyObject *COMPILED_TOKEN_REGEXPS = NULL, *UNICODE_UNESCAPE = NULL, *NEWLINE_UNESCAPE = NULL, *SIMPLE_UNESCAPE = NULL, *FIND_NEWLINES = NULL, *TOKEN_DISPATCH = NULL; 
static PyObject *COLON = NULL, *SCOLON = NULL, *LPAR = NULL, *RPAR = NULL, *LBRACE = NULL, *RBRACE = NULL, *LBOX = NULL, *RBOX = NULL, *DELIM_TOK = NULL, *INTEGER = NULL, *STRING_TOK = NULL;

static Py_ssize_t BAD_COMMENT, BAD_STRING, PERCENTAGE, DIMENSION, ATKEYWORD, FUNCTION, COMMENT, NUMBER, STRING, IDENT, HASH, URI, DELIM = -1;
 
#define CLEANUP(x) Py_XDECREF((x)); x = NULL; 

static PyObject*
tokenize_cleanup(PyObject *self, PyObject *args) {
    CLEANUP(COMPILED_TOKEN_REGEXPS); CLEANUP(UNICODE_UNESCAPE); CLEANUP(NEWLINE_UNESCAPE); CLEANUP(SIMPLE_UNESCAPE); CLEANUP(FIND_NEWLINES); CLEANUP(TOKEN_DISPATCH); 
    CLEANUP(COLON); CLEANUP(SCOLON); CLEANUP(LPAR); CLEANUP(RPAR); CLEANUP(LBRACE); CLEANUP(RBRACE); CLEANUP(LBOX); CLEANUP(RBOX); CLEANUP(DELIM_TOK); CLEANUP(INTEGER); CLEANUP(STRING_TOK);
    Py_RETURN_NONE;
}

static PyObject*
tokenize_init(PyObject *self, PyObject *args) {
    PyObject *cti = NULL;

    if (COMPILED_TOKEN_REGEXPS != NULL) {
        tokenize_cleanup(NULL, NULL);
    }
    if (!PyArg_ParseTuple(args, "OOOOOOOOOOOOOOOOOO", &COMPILED_TOKEN_REGEXPS, &UNICODE_UNESCAPE, &NEWLINE_UNESCAPE, &SIMPLE_UNESCAPE, &FIND_NEWLINES, &TOKEN_DISPATCH, &cti, &COLON, &SCOLON, &LPAR, &RPAR, &LBRACE, &RBRACE, &LBOX, &RBOX, &DELIM_TOK, &INTEGER, &STRING_TOK)) return NULL;
    Py_INCREF(COMPILED_TOKEN_REGEXPS); Py_INCREF(UNICODE_UNESCAPE); Py_INCREF(NEWLINE_UNESCAPE); Py_INCREF(SIMPLE_UNESCAPE); Py_INCREF(FIND_NEWLINES); Py_INCREF(TOKEN_DISPATCH);
    Py_INCREF(COLON); Py_INCREF(SCOLON); Py_INCREF(LPAR); Py_INCREF(RPAR); Py_INCREF(LBRACE); Py_INCREF(RBRACE); Py_INCREF(LBOX); Py_INCREF(RBOX); Py_INCREF(DELIM_TOK); Py_INCREF(INTEGER); Py_INCREF(STRING_TOK);

#define SETCONST(x) x = PyInt_AsSsize_t(PyDict_GetItemString(cti, #x))
    SETCONST(BAD_COMMENT); SETCONST(BAD_STRING); SETCONST(PERCENTAGE); SETCONST(DIMENSION); SETCONST(ATKEYWORD); SETCONST(FUNCTION); SETCONST(COMMENT); SETCONST(NUMBER); SETCONST(STRING); SETCONST(IDENT); SETCONST(HASH); SETCONST(URI);

    Py_RETURN_NONE;
}

static int
contains_char(PyObject *haystack, Py_UNICODE c) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    Py_ssize_t i = 0;
    Py_UNICODE *data = PyUnicode_AS_UNICODE(haystack);
    for (i = 0; i < PyUnicode_GET_SIZE(haystack); i++) {
        if (data[i] == c) return 1;
    }
    return 0;
}

static PyObject *unicode_to_number(PyObject *src) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    PyObject *raw = NULL, *ans = NULL;
    raw = PyUnicode_AsASCIIString(src);
    if (raw == NULL) { return NULL; }
    if (contains_char(src, '.')) {
        ans = PyFloat_FromString(raw, NULL);
    } else {
        ans = PyInt_FromString(PyString_AS_STRING(raw), NULL, 10);
    }
    Py_DECREF(raw);
    return ans;
}

static void lowercase(PyObject *x) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    Py_ssize_t i = 0;
    Py_UNICODE *data = PyUnicode_AS_UNICODE(x);
    for (i = 0; i < PyUnicode_GET_SIZE(x); i++) 
        data[i] = Py_UNICODE_TOLOWER(data[i]);
}

static PyObject* clone_unicode(Py_UNICODE *x, Py_ssize_t sz) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    PyObject *ans = PyUnicode_FromUnicode(NULL, sz);
    if (ans == NULL) return PyErr_NoMemory();
    memcpy(PyUnicode_AS_UNICODE(ans), x, sz * sizeof(Py_UNICODE));
    return ans;
}

static PyObject*
tokenize_flat(PyObject *self, PyObject *args) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    Py_UNICODE *css_source = NULL, c = 0, codepoint = 0;
    PyObject *ic = NULL, *token = NULL, *tokens = NULL, *type_name = NULL, *css_value = NULL, *value = NULL, *unit = NULL, *tries = NULL, *match = NULL, *match_func = NULL, *py_source = NULL, *item = NULL, *newlines = NULL;
    int ignore_comments = 0;
    Py_ssize_t pos = 0, line = 1, column = 1, i = 0;
    Py_ssize_t length = 0, next_pos = 0, type_ = -1, source_len = 0;


    if (COMPILED_TOKEN_REGEXPS == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "tokenizer module not initialized. You must call init() first."); return NULL;
    }

    if (!PyArg_ParseTuple(args, "UO", &py_source, &ic)) return NULL;
    if (PyObject_IsTrue(ic)) ignore_comments = 1;
    source_len = PyUnicode_GET_SIZE(py_source);
    css_source = PyUnicode_AS_UNICODE(py_source);

    tokens = PyList_New(0);
    if (tokens == NULL) return PyErr_NoMemory();

#define UNESCAPE(x, func) item = PyObject_CallFunctionObjArgs(func, x, NULL); if (item == NULL) { goto error; } Py_DECREF(x); x = item; item = NULL;

#define TONUMBER(x) item = unicode_to_number(x); if (item == NULL) goto error; Py_DECREF(x); x = item; item = NULL;

#define SINGLE(x) { type_ = -1; type_name = x; Py_INCREF(type_name); css_value = x; Py_INCREF(css_value); }

    while (pos < source_len) {
        c = css_source[pos];

        css_value = NULL; type_name = NULL; value = NULL; unit = NULL; match = NULL;

        if (c == ':') SINGLE(COLON) else if (c == ';') SINGLE(SCOLON) else if (c == '(') SINGLE(LPAR) else if (c == ')') SINGLE(RPAR) else if (c == '{') SINGLE(LBRACE) else if (c == '}') SINGLE(RBRACE) else if (c == '[') SINGLE(LBOX) else if (c == ']') SINGLE(RBOX) else 
        {
            codepoint = (c > 160) ? 160: c;
            tries = PyList_GET_ITEM(TOKEN_DISPATCH, codepoint);
            for (i = 0; i < PyList_Size(tries); i++) {
                item = PyList_GET_ITEM(tries, i);
                match_func = PyTuple_GET_ITEM(item, 2);
                match = PyObject_CallFunction(match_func, "On", py_source, pos); 
                if (match == NULL) { goto error; }
                if (match != Py_None) {
                    css_value = PyObject_CallMethod(match, "group", NULL);
                    if (css_value == NULL) { goto error; }
                    type_ = PyInt_AsSsize_t(PyTuple_GET_ITEM(item, 0));
                    type_name = PyTuple_GET_ITEM(item, 1);
                    Py_INCREF(type_name);
                    break;
                }
            }
            if (css_value == NULL) {  // No match
                type_ = DELIM; type_name = DELIM_TOK; Py_INCREF(type_name); css_value = clone_unicode(&c, 1);
                if (css_value == NULL) { goto error; }
            }
        }

        length = PyUnicode_GET_SIZE(css_value);
        next_pos = pos + length;

        // Now calculate the value and unit for this token (if any)
        if (! (ignore_comments && (type_ == COMMENT || type_ == BAD_COMMENT))) { 
            if (type_ == DIMENSION) {
                value = PyObject_CallMethod(match, "group", "I", 1);
                if (value == NULL) { goto error; }
                TONUMBER(value);
                unit = PyObject_CallMethod(match, "group", "I", 2);
                if (unit == NULL) { goto error; }
                UNESCAPE(unit, SIMPLE_UNESCAPE);
                UNESCAPE(unit, UNICODE_UNESCAPE);
                lowercase(unit);
            } else 

            if (type_ == PERCENTAGE) {
                if (PyUnicode_GET_SIZE(css_value) > 0) {
                    value = clone_unicode(PyUnicode_AS_UNICODE(css_value), PyUnicode_GET_SIZE(css_value) - 1);
                    if (value == NULL) goto error;
                } else { value = css_value; Py_INCREF(value); }
                if (value == NULL) goto error;
                TONUMBER(value);
                unit = PyUnicode_FromString("%");
                if (unit == NULL) goto error;
            } else

            if (type_ == NUMBER) {
                value = css_value; Py_INCREF(value);
                TONUMBER(value);
                if (!PyFloat_Check(value)) {
                    Py_XDECREF(type_name);
                    type_name = INTEGER;
                    Py_INCREF(type_name);
                }
            } else

            if (type_ == IDENT || type_ == ATKEYWORD || type_ == HASH || type_ == FUNCTION) {
                value = PyObject_CallFunctionObjArgs(SIMPLE_UNESCAPE, css_value, NULL);
                if (value == NULL) goto error;
                UNESCAPE(value, UNICODE_UNESCAPE);
            } else

            if (type_ == URI) {
                value = PyObject_CallMethod(match, "group", "I", 1);
                if (value == NULL) { goto error; }
                if (PyObject_IsTrue(value) && PyUnicode_GET_SIZE(value) > 1 && (PyUnicode_AS_UNICODE(value)[0] == '"' || PyUnicode_AS_UNICODE(value)[0] == '\'')) {
                    item = clone_unicode(PyUnicode_AS_UNICODE(value) + 1, PyUnicode_GET_SIZE(value) - 2);
                    if (item == NULL) goto error;
                    Py_DECREF(value); value = item; item = NULL;
                    UNESCAPE(value, NEWLINE_UNESCAPE);
                }
                UNESCAPE(value, SIMPLE_UNESCAPE);
                UNESCAPE(value, UNICODE_UNESCAPE);
            } else

            if (type_ == STRING) {
                if (PyObject_IsTrue(css_value) && PyUnicode_GET_SIZE(css_value) > 1) {  // remove quotes
                    value = clone_unicode(PyUnicode_AS_UNICODE(css_value) + 1, PyUnicode_GET_SIZE(css_value) - 2);
                } else {
                    value = css_value; Py_INCREF(value);
                }
                UNESCAPE(value, NEWLINE_UNESCAPE);
                UNESCAPE(value, SIMPLE_UNESCAPE);
                UNESCAPE(value, UNICODE_UNESCAPE);
            } else

            if (type_ == BAD_STRING && next_pos == source_len) {
                Py_XDECREF(type_name); type_name = STRING_TOK; Py_INCREF(type_name);
                if (PyObject_IsTrue(css_value) && PyUnicode_GET_SIZE(css_value) > 0) {  // remove quote
                    value = clone_unicode(PyUnicode_AS_UNICODE(css_value) + 1, PyUnicode_GET_SIZE(css_value) - 1);
                } else {
                    value = css_value; Py_INCREF(value);
                }
                UNESCAPE(value, NEWLINE_UNESCAPE);
                UNESCAPE(value, SIMPLE_UNESCAPE);
                UNESCAPE(value, UNICODE_UNESCAPE);
            } else {
                value = css_value; Py_INCREF(value);
            }  // if(type_ == ...)

            if (unit == NULL) { unit = Py_None; Py_INCREF(unit); }
            item = Py_BuildValue("OOOOnn", type_name, css_value, value, unit, line, column);
            if (item == NULL) goto error;
            token = PyObject_CallObject((PyObject *) &tokenizer_TokenType, item);
            Py_DECREF(item); item = NULL;
            if (token == NULL) goto error;
            if (PyList_Append(tokens, token) != 0) { Py_DECREF(token); token = NULL; goto error; }
            Py_DECREF(token);

        }  // if(!(ignore_comments...

        Py_XDECREF(match); match = NULL;

        pos = next_pos;
        newlines = PyObject_CallFunctionObjArgs(FIND_NEWLINES, css_value, NULL);
        if (newlines == NULL) goto error;
        Py_XDECREF(css_value); css_value = NULL; Py_XDECREF(type_name); type_name = NULL; Py_XDECREF(value); value = NULL; Py_XDECREF(unit); unit = NULL;
        if (PyObject_IsTrue(newlines)) {
            line += PyList_Size(newlines);
            item = PyObject_CallMethod(PyList_GET_ITEM(newlines, PyList_Size(newlines) - 1), "end", NULL);
            if (item == NULL) { Py_DECREF(newlines); newlines = NULL; goto error; }
            column = length - PyInt_AsSsize_t(item) + 1;
            Py_DECREF(item); item = NULL; 
        } else column += length;
        Py_DECREF(newlines); newlines = NULL;

    }  // while (pos < ...)

    return tokens;
error:
    Py_XDECREF(tokens); Py_XDECREF(css_value); Py_XDECREF(type_name); Py_XDECREF(value); Py_XDECREF(unit); Py_XDECREF(match);
    return NULL;
}

static PyMethodDef tokenizer_methods[] = {
    {"tokenize_flat", tokenize_flat, METH_VARARGS,
        "tokenize_flat(css_source, ignore_comments)\n\n Convert CSS source into a flat list of tokens"
    },

    {"init", tokenize_init, METH_VARARGS,
        "init()\n\nInitialize the module."
    },

    {"cleanup", tokenize_cleanup, METH_VARARGS,
        "cleanup()\n\nRelease resources allocated by init(). Safe to call multiple times."
    },

    {NULL, NULL, 0, NULL}
};


CALIBRE_MODINIT_FUNC
inittokenizer(void) {
    PyObject *m;
    if (PyType_Ready(&tokenizer_TokenType) < 0)
        return;

    m = Py_InitModule3("tokenizer", tokenizer_methods,
    "Implementation of tokenizer in C for speed."
    );
    if (m == NULL) return;
    Py_INCREF(&tokenizer_TokenType);
    PyModule_AddObject(m, "Token", (PyObject *)&tokenizer_TokenType);
}
