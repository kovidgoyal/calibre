#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <unicode/utypes.h>
#include <unicode/uclean.h>
#include <unicode/ucol.h>
#include <unicode/ucoleitr.h>
#include <unicode/ustring.h>
#include <unicode/usearch.h>
#include <unicode/utrans.h>

static PyObject* uchar_to_unicode(const UChar *src, int32_t len) {
    wchar_t *buf = NULL;
    PyObject *ans = NULL;
    UErrorCode status = U_ZERO_ERROR;

    if (len < 0) { len = u_strlen(src); }
    buf = (wchar_t *)calloc(4*len, sizeof(wchar_t));
    if (buf == NULL) return PyErr_NoMemory();
    u_strToWCS(buf, 4*len, NULL, src, len, &status);
    if (U_SUCCESS(status)) {
        ans = PyUnicode_FromWideChar(buf, wcslen(buf));
        if (ans == NULL) PyErr_NoMemory();
    } else PyErr_SetString(PyExc_TypeError, "Failed to convert UChar* to wchar_t*");

    free(buf);
    return ans;
}

// Collator object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UCollator *collator;
    USet *contractions;

} icu_Collator;

static void
icu_Collator_dealloc(icu_Collator* self)
{
    if (self->collator != NULL) ucol_close(self->collator);
    if (self->contractions != NULL) uset_close(self->contractions);
    self->collator = NULL;
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
icu_Collator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    icu_Collator *self;
    const char *loc;
    UErrorCode status = U_ZERO_ERROR;
    UCollator *collator;

    if (!PyArg_ParseTuple(args, "s", &loc)) return NULL;
    collator = ucol_open(loc, &status);
    if (collator == NULL || U_FAILURE(status)) { 
        PyErr_SetString(PyExc_Exception, "Failed to create collator.");
        return NULL;
    }

    self = (icu_Collator *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->collator = collator;
        self->contractions = NULL;
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

// Collator.strength {{{
static PyObject *
icu_Collator_get_strength(icu_Collator *self, void *closure) {
    return Py_BuildValue("i", ucol_getStrength(self->collator));
}

static int
icu_Collator_set_strength(icu_Collator *self, PyObject *val, void *closure) {
    if (!PyInt_Check(val)) {
        PyErr_SetString(PyExc_TypeError, "Strength must be an integer.");
        return -1;
    }
    ucol_setStrength(self->collator, (int)PyInt_AS_LONG(val));
    return 0;
}
// }}}

// Collator.numeric {{{
static PyObject *
icu_Collator_get_numeric(icu_Collator *self, void *closure) {
    UErrorCode status = U_ZERO_ERROR;
    return Py_BuildValue("O", (ucol_getAttribute(self->collator, UCOL_NUMERIC_COLLATION, &status) == UCOL_ON) ? Py_True : Py_False);
}

static int
icu_Collator_set_numeric(icu_Collator *self, PyObject *val, void *closure) {
    UErrorCode status = U_ZERO_ERROR;
    ucol_setAttribute(self->collator, UCOL_NUMERIC_COLLATION, (PyObject_IsTrue(val)) ? UCOL_ON : UCOL_OFF, &status);
    return 0;
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
    int32_t sz;
    UChar *buf;
    uint8_t *buf2;
    PyObject *ans;
    int32_t key_size;
    UErrorCode status = U_ZERO_ERROR;
  
    if (!PyArg_ParseTuple(args, "es", "UTF-8", &input)) return NULL;

    sz = (int32_t)strlen(input);

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
    int32_t asz, bsz;
    UChar *a, *b;
    UErrorCode status = U_ZERO_ERROR;
    UCollationResult res = UCOL_EQUAL;
  
    if (!PyArg_ParseTuple(args, "eses", "UTF-8", &a_, "UTF-8", &b_)) return NULL;
    
    asz = (int32_t)strlen(a_); bsz = (int32_t)strlen(b_);

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
    int32_t asz, bsz;
    UChar *a, *b;
    wchar_t *aw, *bw;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
    int32_t pos = -1, length = -1;
  
    if (!PyArg_ParseTuple(args, "UU", &a_, &b_)) return NULL;
    asz = (int32_t)PyUnicode_GetSize(a_); bsz = (int32_t)PyUnicode_GetSize(b_);
    
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
                length = usearch_getMatchedLength(search);
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
    UErrorCode status = U_ZERO_ERROR;
    UChar *str;
    UChar32 start=0, end=0;
    int32_t count = 0, len = 0, dlen = 0, i;
    PyObject *ans = Py_None, *pbuf;
    wchar_t *buf;

    if (self->contractions == NULL) {
        self->contractions = uset_open(1, 0);
        if (self->contractions == NULL) return PyErr_NoMemory();
        self->contractions = ucol_getTailoredSet(self->collator, &status);
    }
    status = U_ZERO_ERROR; 

    str = (UChar*)calloc(100, sizeof(UChar));
    buf = (wchar_t*)calloc(4*100+2, sizeof(wchar_t));
    if (str == NULL || buf == NULL) return PyErr_NoMemory();

    count = uset_getItemCount(self->contractions);
    ans = PyTuple_New(count);
    if (ans != NULL) {
        for (i = 0; i < count; i++) {
            len = uset_getItem(self->contractions, i, &start, &end, str, 1000, &status);
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
    free(str); free(buf);
  
    return Py_BuildValue("O", ans);
} // }}}

// Collator.startswith {{{
static PyObject *
icu_Collator_startswith(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    PyObject *a_, *b_;
    int32_t asz, bsz;
    int32_t actual_a, actual_b;
    UChar *a, *b;
    wchar_t *aw, *bw;
    UErrorCode status = U_ZERO_ERROR;
    int ans = 0;
  
    if (!PyArg_ParseTuple(args, "UU", &a_, &b_)) return NULL;
    asz = (int32_t)PyUnicode_GetSize(a_); bsz = (int32_t)PyUnicode_GetSize(b_);
    if (asz < bsz) Py_RETURN_FALSE;
    if (bsz == 0) Py_RETURN_TRUE;
    
    a = (UChar*)calloc(asz*4 + 2, sizeof(UChar));
    b = (UChar*)calloc(bsz*4 + 2, sizeof(UChar));
    aw = (wchar_t*)calloc(asz*4 + 2, sizeof(wchar_t));
    bw = (wchar_t*)calloc(bsz*4 + 2, sizeof(wchar_t));

    if (a == NULL || b == NULL || aw == NULL || bw == NULL) return PyErr_NoMemory();

    actual_a = (int32_t)PyUnicode_AsWideChar((PyUnicodeObject*)a_, aw, asz*4+1);
    actual_b = (int32_t)PyUnicode_AsWideChar((PyUnicodeObject*)b_, bw, bsz*4+1);
    if (actual_a > -1 && actual_b > -1) {
        u_strFromWCS(a, asz*4 + 1, &actual_a, aw, -1, &status);
        u_strFromWCS(b, bsz*4 + 1, &actual_b, bw, -1, &status);

        if (U_SUCCESS(status) && ucol_equal(self->collator, a, actual_b, b, actual_b))
            ans = 1;
    }

    free(a); free(b); free(aw); free(bw);
    if (ans) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
} // }}}

// Collator.startswith {{{
static PyObject *
icu_Collator_collation_order(icu_Collator *self, PyObject *args, PyObject *kwargs) {
    PyObject *a_;
    int32_t asz;
    int32_t actual_a;
    UChar *a;
    wchar_t *aw;
    UErrorCode status = U_ZERO_ERROR;
    UCollationElements *iter = NULL;
    int order = 0, len = -1;
  
    if (!PyArg_ParseTuple(args, "U", &a_)) return NULL;
    asz = (int32_t)PyUnicode_GetSize(a_); 
    
    a = (UChar*)calloc(asz*4 + 2, sizeof(UChar));
    aw = (wchar_t*)calloc(asz*4 + 2, sizeof(wchar_t));

    if (a == NULL || aw == NULL ) return PyErr_NoMemory();

    actual_a = (int32_t)PyUnicode_AsWideChar((PyUnicodeObject*)a_, aw, asz*4+1);
    if (actual_a > -1) {
        u_strFromWCS(a, asz*4 + 1, &actual_a, aw, -1, &status);
        iter = ucol_openElements(self->collator, a, actual_a, &status);
        if (iter != NULL && U_SUCCESS(status)) {
            order = ucol_next(iter, &status);
            len = ucol_getOffset(iter);
            ucol_closeElements(iter); iter = NULL;
        }
    }

    free(a); free(aw); 
    return Py_BuildValue("ii", order, len);
} // }}}

static PyObject*
icu_Collator_clone(icu_Collator *self, PyObject *args, PyObject *kwargs);

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

    {"clone", (PyCFunction)icu_Collator_clone, METH_VARARGS,
        "clone() -> returns a clone of this collator."
    },

    {"startswith", (PyCFunction)icu_Collator_startswith, METH_VARARGS,
        "startswith(a, b) -> returns True iff a startswith b, following the current collation rules."
    },

    {"collation_order", (PyCFunction)icu_Collator_collation_order, METH_VARARGS,
        "collation_order(string) -> returns (order, length) where order is an integer that gives the position of string in a list. length gives the number of characters used for order."
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

    {(char *)"strength",
     (getter)icu_Collator_get_strength, (setter)icu_Collator_set_strength,
     (char *)"The strength of this collator.",
     NULL},

    {(char *)"numeric",
     (getter)icu_Collator_get_numeric, (setter)icu_Collator_set_numeric,
     (char *)"If True the collator sorts contiguous digits as numbers rather than strings, so 2 will sort before 10.",
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

// Collator.clone {{{
static PyObject*
icu_Collator_clone(icu_Collator *self, PyObject *args, PyObject *kwargs)
{
    UCollator *collator;
    UErrorCode status = U_ZERO_ERROR;
    int32_t bufsize = -1;
    icu_Collator *clone;

    collator = ucol_safeClone(self->collator, NULL, &bufsize, &status);

    if (collator == NULL || U_FAILURE(status)) {
        PyErr_SetString(PyExc_Exception, "Failed to create collator.");
        return NULL;
    }

    clone = PyObject_New(icu_Collator, &icu_CollatorType);
    if (clone == NULL) return PyErr_NoMemory();

    clone->collator = collator;
    clone->contractions = NULL;

    return (PyObject*) clone;

} // }}}

// }}}

// Module initialization {{{

// upper {{{
static PyObject *
icu_upper(PyObject *self, PyObject *args) {
    char *input, *ans, *buf3 = NULL;
    const char *loc;
    int32_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = (int32_t)strlen(input);

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
    int32_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = (int32_t)strlen(input);

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
    int32_t sz;
    UChar *buf, *buf2;
    PyObject *ret;
    UErrorCode status = U_ZERO_ERROR;
  

    if (!PyArg_ParseTuple(args, "ses", &loc, "UTF-8", &input)) return NULL;
    
    sz = (int32_t)strlen(input);

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

// set_default_encoding {{{
static PyObject *
icu_get_available_transliterators(PyObject *self, PyObject *args) {
    PyObject *ans, *l;
    UErrorCode status = U_ZERO_ERROR;
    const UChar *id = NULL;
    UEnumeration *i;

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    i = utrans_openIDs(&status);
    if (i == NULL || U_FAILURE(status)) {Py_DECREF(ans); PyErr_SetString(PyExc_RuntimeError, "Failed to create enumerator"); return NULL; }

    do {
        id = uenum_unext(i, NULL, &status);
        if (U_SUCCESS(status) && id != NULL) {
            l = uchar_to_unicode(id, -1);
            if (l == NULL) break;
            PyList_Append(ans, l);
            Py_DECREF(l);
        }
    } while(id != NULL);
    uenum_close(i);

    return ans;
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

    {"get_available_transliterators", icu_get_available_transliterators, METH_VARARGS,
        "get_available_transliterators() -> Return list of available transliterators. This list is rather limited on OS X."
    },

    {NULL}  /* Sentinel */
};

#define ADDUCONST(x) PyModule_AddIntConstant(m, #x, x)

PyMODINIT_FUNC
initicu(void) 
{
    PyObject* m;
    UErrorCode status = U_ZERO_ERROR;

    u_init(&status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_RuntimeError, u_errorName(status));
        return;
    }

    if (PyType_Ready(&icu_CollatorType) < 0)
        return;

    m = Py_InitModule3("icu", icu_methods,
                       "Wrapper for the ICU internationalization library");

    Py_INCREF(&icu_CollatorType);
    PyModule_AddObject(m, "Collator", (PyObject *)&icu_CollatorType);
    // uint8_t must be the same size as char
    PyModule_AddIntConstant(m, "ok", (U_SUCCESS(status) && sizeof(uint8_t) == sizeof(char)) ? 1 : 0);

    ADDUCONST(USET_SPAN_NOT_CONTAINED);
    ADDUCONST(USET_SPAN_CONTAINED);
    ADDUCONST(USET_SPAN_SIMPLE);
    ADDUCONST(UCOL_DEFAULT);
    ADDUCONST(UCOL_PRIMARY);
    ADDUCONST(UCOL_SECONDARY);
    ADDUCONST(UCOL_TERTIARY);
    ADDUCONST(UCOL_DEFAULT_STRENGTH);
    ADDUCONST(UCOL_QUATERNARY);
    ADDUCONST(UCOL_IDENTICAL);
    ADDUCONST(UCOL_OFF);
    ADDUCONST(UCOL_ON);
    ADDUCONST(UCOL_SHIFTED);
    ADDUCONST(UCOL_NON_IGNORABLE);
    ADDUCONST(UCOL_LOWER_FIRST);
    ADDUCONST(UCOL_UPPER_FIRST);

}
// }}}
