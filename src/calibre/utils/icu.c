#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <unicode/utypes.h>
#include <unicode/uclean.h>
#include <unicode/ucol.h>
#include <unicode/ustring.h>
#include <unicode/usearch.h>


// Collator object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UCollator *collator;

} icu_Collator;

static void
icu_Collator_dealloc(icu_Collator* self)
{
    if (self->collator != NULL) ucol_close(self->collator);
    self->collator = NULL;
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
icu_Collator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    icu_Collator *self;
    const char *loc;
    UErrorCode status = U_ZERO_ERROR;

    if (!PyArg_ParseTuple(args, "s", &loc)) return NULL;

    self = (icu_Collator *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->collator = ucol_open(loc, &status);
        if (self->collator == NULL || U_FAILURE(status)) { 
            PyErr_SetString(PyExc_Exception, "Failed to create collator.");
            self->collator = NULL;
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

// Collator.display_name {{{
static PyObject *
icu_Collator_display_name(icu_Collator *self, void *closure) {
    const char *loc = NULL;
    UErrorCode status = U_ZERO_ERROR;
    UChar dname[400];
    char buf[100];

    loc = ucol_getLocaleByType(self->collator, ULOC_ACTUAL_LOCALE, &status);
    if (loc == NULL || U_FAILURE(status)) {
        PyErr_SetString(PyExc_Exception, "Failed to get actual locale"); return NULL;
    }
    ucol_getDisplayName(loc, "en", dname, 100, &status);
    if (U_FAILURE(status)) return PyErr_NoMemory();

    u_strToUTF8(buf, 100, NULL, dname, -1, &status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_Exception, "Failed to convert dname to UTF-8"); return NULL;
    }
    return Py_BuildValue("s", buf);
}

// }}}

// Collator.actual_locale {{{
static PyObject *
icu_Collator_actual_locale(icu_Collator *self, void *closure) {
    const char *loc = NULL;
    UErrorCode status = U_ZERO_ERROR;

    loc = ucol_getLocaleByType(self->collator, ULOC_ACTUAL_LOCALE, &status);
    if (loc == NULL || U_FAILURE(status)) {
        PyErr_SetString(PyExc_Exception, "Failed to get actual locale"); return NULL;
    }
    return Py_BuildValue("s", loc);
}

// }}}

// Collator.sort_key {{{
static PyObject *
icu_Collator_sort_key(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    char *input;
    Py_ssize_t sz;
    UChar *buf;
    uint8_t *buf2;
    PyObject *ans;
    int32_t key_size;
    UErrorCode status = U_ZERO_ERROR;
  
    if (!PyArg_ParseTuple(args, "es", "UTF-8", &input)) return NULL;

    sz = strlen(input);

    buf = (UChar*)calloc(sz*4 + 1, sizeof(UChar));

    if (buf == NULL) return PyErr_NoMemory();

    u_strFromUTF8(buf, sz*4 + 1, &key_size, input, sz, &status);
    PyMem_Free(input);

    if (U_SUCCESS(status)) {
        buf2 = (uint8_t*)calloc(7*sz+1, sizeof(uint8_t));
        if (buf2 == NULL) return PyErr_NoMemory();

        key_size = ucol_getSortKey(self->collator, buf, -1, buf2, 7*sz+1);

        if (key_size == 0) {
            ans = PyBytes_FromString("");
        } else {
            if (key_size >= 7*sz+1) {
                free(buf2);
                buf2 = (uint8_t*)calloc(key_size+1, sizeof(uint8_t));
                if (buf2 == NULL) return PyErr_NoMemory();
                ucol_getSortKey(self->collator, buf, -1, buf2, key_size+1);
            }
            ans = PyBytes_FromString((char *)buf2);
        }
        free(buf2);
    } else ans = PyBytes_FromString("");

    free(buf);
    if (ans == NULL) return PyErr_NoMemory();

    return ans;
} // }}}

// Collator.strcmp {{{
static PyObject *
icu_Collator_strcmp(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    char *a_, *b_;
    size_t asz, bsz;
    UChar *a, *b;
    UErrorCode status = U_ZERO_ERROR;
    UCollationResult res = UCOL_EQUAL;
  
    if (!PyArg_ParseTuple(args, "eses", "UTF-8", &a_, "UTF-8", &b_)) return NULL;
    
    asz = strlen(a_); bsz = strlen(b_);

    a = (UChar*)calloc(asz*4 + 1, sizeof(UChar));
    b = (UChar*)calloc(bsz*4 + 1, sizeof(UChar));


    if (a == NULL || b == NULL) return PyErr_NoMemory();

    u_strFromUTF8(a, asz*4 + 1, NULL, a_, asz, &status);
    u_strFromUTF8(b, bsz*4 + 1, NULL, b_, bsz, &status);
    PyMem_Free(a_); PyMem_Free(b_);

    if (U_SUCCESS(status))
        res = ucol_strcoll(self->collator, a, -1, b, -1);

    free(a); free(b);

    return Py_BuildValue("i", res);
} // }}}

// Collator.find {{{
static PyObject *
icu_Collator_find(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    PyObject *a_, *b_;
    size_t asz, bsz;
    UChar *a, *b;
    wchar_t *aw, *bw;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
    int32_t pos = -1, length = -1;
  
    if (!PyArg_ParseTuple(args, "UU", &a_, &b_)) return NULL;
    asz = PyUnicode_GetSize(a_); bsz = PyUnicode_GetSize(b_);
    
    a = (UChar*)calloc(asz*4 + 2, sizeof(UChar));
    b = (UChar*)calloc(bsz*4 + 2, sizeof(UChar));
    aw = (wchar_t*)calloc(asz*4 + 2, sizeof(wchar_t));
    bw = (wchar_t*)calloc(bsz*4 + 2, sizeof(wchar_t));

    if (a == NULL || b == NULL || aw == NULL || bw == NULL) return PyErr_NoMemory();

    PyUnicode_AsWideChar((PyUnicodeObject*)a_, aw, asz*4+1);
    PyUnicode_AsWideChar((PyUnicodeObject*)b_, bw, bsz*4+1);
    u_strFromWCS(a, asz*4 + 1, NULL, aw, -1, &status);
    u_strFromWCS(b, bsz*4 + 1, NULL, bw, -1, &status);

    if (U_SUCCESS(status)) {
        search = usearch_openFromCollator(a, -1, b, -1, self->collator, NULL, &status);
        if (U_SUCCESS(status)) {
            pos = usearch_first(search, &status);
            if (pos != USEARCH_DONE) 
                length = (pos == USEARCH_DONE) ? -1 : usearch_getMatchedLength(search);
            else
                pos = -1;
        }
        if (search != NULL) usearch_close(search);
    }

    free(a); free(b); free(aw); free(bw);

    return Py_BuildValue("ii", pos, length);
} // }}}

// Collator.contractions {{{
static PyObject *
icu_Collator_contractions(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    USet *contractions;
    UErrorCode status = U_ZERO_ERROR;
    UChar *str;
    UChar32 start=0, end=0;
    int32_t count = 0, len = 0, dlen = 0, i;
    PyObject *ans = Py_None, *pbuf;
    wchar_t *buf;

    str = (UChar*)calloc(100, sizeof(UChar));
    buf = (wchar_t*)calloc(4*100+2, sizeof(wchar_t));
    if (str == NULL || buf == NULL) return PyErr_NoMemory();

    contractions = uset_open(1, 0);
    ucol_getContractionsAndExpansions(self->collator, contractions, NULL, 0, &status);
    if (U_SUCCESS(status)) {
        count = uset_getItemCount(contractions);
        ans = PyTuple_New(count);
        if (ans != NULL) {
            for (i = 0; i < count; i++) {
                len = uset_getItem(contractions, i, &start, &end, str, 1000, &status);
                if (len >= 2) {
                    // We have a string
                    status = U_ZERO_ERROR;
                    u_strToWCS(buf, 4*100 + 1, &dlen, str, len, &status);
                    pbuf = PyUnicode_FromWideChar(buf, dlen);
                    if (pbuf == NULL) return PyErr_NoMemory();
                    PyTuple_SetItem(ans, i, pbuf);
                } else {
                    // Ranges dont make sense for contractions, ignore them
                    PyTuple_SetItem(ans, i, Py_None);
                }
            }
        }
    }
    uset_close(contractions);
    free(str); free(buf);
  
    return Py_BuildValue("O", ans);
} // }}}

static PyMethodDef icu_Collator_methods[] = {
    {"sort_key", (PyCFunction)icu_Collator_sort_key, METH_VARARGS,
     "sort_key(unicode object) -> Return a sort key for the given object as a bytestring. The idea is that these bytestring will sort using the builtin cmp function, just like the original unicode strings would sort in the current locale with ICU."
    },

    {"strcmp", (PyCFunction)icu_Collator_strcmp, METH_VARARGS,
     "strcmp(unicode object, unicode object) -> strcmp(a, b) <=> cmp(sorty_key(a), sort_key(b)), but faster."
    },

    {"find", (PyCFunction)icu_Collator_find, METH_VARARGS,
        "find(pattern, source) -> returns the position and length of the first occurrence of pattern in source. Returns (-1, -1) if not found."
    },

    {"contractions", (PyCFunction)icu_Collator_contractions, METH_VARARGS,
        "contractions() -> returns the contractions defined for this collator."
    },
    {NULL}  /* Sentinel */
};

static PyGetSetDef  icu_Collator_getsetters[] = {
    {(char *)"actual_locale", 
     (getter)icu_Collator_actual_locale, NULL,
     (char *)"Actual locale used by this collator.",
     NULL},

    {(char *)"display_name", 
     (getter)icu_Collator_display_name, NULL,
     (char *)"Display name of this collator in English. The name reflects the actual data source used.",
     NULL},

    {NULL}  /* Sentinel */
};

static PyTypeObject icu_CollatorType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "icu.Collator",            /*tp_name*/
    sizeof(icu_Collator),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)icu_Collator_dealloc, /*tp_dealloc*/
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
    "Collator",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    icu_Collator_methods,             /* tp_methods */
    0,             /* tp_members */
    icu_Collator_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    icu_Collator_new,                 /* tp_new */
}; // }}}

// }}


// }}}

// Module initialization {{{

// upper {{{
static PyObject *
icu_upper(PyObject *self, PyObject *args) {
    char *input, *ans, *buf3 = NULL;
    const char *loc;
    size_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = strlen(input);

    buf = (UChar*)calloc(sz*4 + 1, sizeof(UChar));
    buf2 = (UChar*)calloc(sz*8 + 1, sizeof(UChar));


    if (buf == NULL || buf2 == NULL) return PyErr_NoMemory();

    u_strFromUTF8(buf, sz*4, NULL, input, sz, &status);
    u_strToUpper(buf2, sz*8, buf, -1, loc, &status);

    ans = input;
    sz = u_strlen(buf2);
    free(buf);

    if (U_SUCCESS(status) && sz > 0) {
        buf3 = (char*)calloc(sz*5+1, sizeof(char));
        if (buf3 == NULL) return PyErr_NoMemory();
        u_strToUTF8(buf3, sz*5, NULL, buf2, -1, &status);
        if (U_SUCCESS(status)) ans = buf3;
    }

    ret = PyUnicode_DecodeUTF8(ans, strlen(ans), "replace");
    if (ret == NULL) return PyErr_NoMemory();

    free(buf2);
    if (buf3 != NULL) free(buf3);
    PyMem_Free(input);

    return ret;
} // }}}

// lower {{{
static PyObject *
icu_lower(PyObject *self, PyObject *args) {
    char *input, *ans, *buf3 = NULL;
    const char *loc;
    size_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = strlen(input);

    buf = (UChar*)calloc(sz*4 + 1, sizeof(UChar));
    buf2 = (UChar*)calloc(sz*8 + 1, sizeof(UChar));


    if (buf == NULL || buf2 == NULL) return PyErr_NoMemory();

    u_strFromUTF8(buf, sz*4, NULL, input, sz, &status);
    u_strToLower(buf2, sz*8, buf, -1, loc, &status);

    ans = input;
    sz = u_strlen(buf2);
    free(buf);

    if (U_SUCCESS(status) && sz > 0) {
        buf3 = (char*)calloc(sz*5+1, sizeof(char));
        if (buf3 == NULL) return PyErr_NoMemory();
        u_strToUTF8(buf3, sz*5, NULL, buf2, -1, &status);
        if (U_SUCCESS(status)) ans = buf3;
    }

    ret = PyUnicode_DecodeUTF8(ans, strlen(ans), "replace");
    if (ret == NULL) return PyErr_NoMemory();

    free(buf2);
    if (buf3 != NULL) free(buf3);
    PyMem_Free(input);

    return ret;
} // }}}

// title {{{
static PyObject *
icu_title(PyObject *self, PyObject *args) {
    char *input, *ans, *buf3 = NULL;
    const char *loc;
    size_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = strlen(input);

    buf = (UChar*)calloc(sz*4 + 1, sizeof(UChar));
    buf2 = (UChar*)calloc(sz*8 + 1, sizeof(UChar));


    if (buf == NULL || buf2 == NULL) return PyErr_NoMemory();

    u_strFromUTF8(buf, sz*4, NULL, input, sz, &status);
    u_strToTitle(buf2, sz*8, buf, -1, NULL, loc, &status);

    ans = input;
    sz = u_strlen(buf2);
    free(buf);

    if (U_SUCCESS(status) && sz > 0) {
        buf3 = (char*)calloc(sz*5+1, sizeof(char));
        if (buf3 == NULL) return PyErr_NoMemory();
        u_strToUTF8(buf3, sz*5, NULL, buf2, -1, &status);
        if (U_SUCCESS(status)) ans = buf3;
    }

    ret = PyUnicode_DecodeUTF8(ans, strlen(ans), "replace");
    if (ret == NULL) return PyErr_NoMemory();

    free(buf2);
    if (buf3 != NULL) free(buf3);
    PyMem_Free(input);

    return ret;
} // }}}


// set_default_encoding {{{
static PyObject *
icu_set_default_encoding(PyObject *self, PyObject *args) {
    char *encoding;
    if (!PyArg_ParseTuple(args, "s:setdefaultencoding", &encoding))
        return NULL;
    if (PyUnicode_SetDefaultEncoding(encoding))
        return NULL;
    Py_INCREF(Py_None);
    return Py_None;

}
// }}}

static PyMethodDef icu_methods[] = {
    {"upper", icu_upper, METH_VARARGS,
        "upper(locale, unicode object) -> upper cased unicode object using locale rules."
    },

    {"lower", icu_lower, METH_VARARGS,
        "lower(locale, unicode object) -> lower cased unicode object using locale rules."
    },

    {"title", icu_title, METH_VARARGS,
        "title(locale, unicode object) -> Title cased unicode object using locale rules."
    },

    {"set_default_encoding", icu_set_default_encoding, METH_VARARGS,
        "set_default_encoding(encoding) -> Set the default encoding for the python unicode implementation."
    },

    {NULL}  /* Sentinel */
};


PyMODINIT_FUNC
initicu(void) 
{
    PyObject* m;
    UErrorCode status = U_ZERO_ERROR;

    u_init(&status);


    if (PyType_Ready(&icu_CollatorType) < 0)
        return;

    m = Py_InitModule3("icu", icu_methods,
                       "Wrapper for the ICU internationalization library");

    Py_INCREF(&icu_CollatorType);
    PyModule_AddObject(m, "Collator", (PyObject *)&icu_CollatorType);
    // uint8_t must be the same size as char
    PyModule_AddIntConstant(m, "ok", (U_SUCCESS(status) && sizeof(uint8_t) == sizeof(char)) ? 1 : 0);

}
// }}}
