#include "icu_calibre_utils.h"

#define UPPER_CASE 0
#define LOWER_CASE 1
#define TITLE_CASE 2

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
    int32_t sz = 0;

    loc = ucol_getLocaleByType(self->collator, ULOC_ACTUAL_LOCALE, &status);
    if (loc == NULL) {
        PyErr_SetString(PyExc_Exception, "Failed to get actual locale"); return NULL;
    }
    sz = ucol_getDisplayName(loc, "en", dname, sizeof(dname), &status);
    if (U_FAILURE(status)) {PyErr_SetString(PyExc_ValueError, u_errorName(status)); return NULL; }

    return icu_to_python(dname, sz);
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

// Collator.capsule {{{
static PyObject *
icu_Collator_capsule(icu_Collator *self, void *closure) {
    return PyCapsule_New(self->collator, NULL, NULL);
} // }}}

// Collator.sort_key {{{
static PyObject *
icu_Collator_sort_key(icu_Collator *self, PyObject *input) {
    int32_t sz = 0, key_size = 0, bsz = 0;
    UChar *buf = NULL;
    uint8_t *buf2 = NULL;
    PyObject *ans = NULL;
  
    buf = python_to_icu(input, &sz, 1);
    if (buf == NULL) return NULL;

    bsz = 7 * sz + 1;
    buf2 = (uint8_t*)calloc(bsz, sizeof(uint8_t));
    if (buf2 == NULL) { PyErr_NoMemory(); goto end; }
    key_size = ucol_getSortKey(self->collator, buf, sz, buf2, bsz);
    if (key_size > bsz) {
        buf2 = realloc(buf2, (key_size + 1) * sizeof(uint8_t));
        if (buf2 == NULL) { PyErr_NoMemory(); goto end; }
        key_size = ucol_getSortKey(self->collator, buf, sz, buf2, key_size + 1);
    }
    ans = PyBytes_FromStringAndSize((char*)buf2, key_size);

end:
    if (buf != NULL) free(buf);
    if (buf2 != NULL) free(buf2);

    return ans;
} // }}}

// Collator.strcmp {{{
static PyObject *
icu_Collator_strcmp(icu_Collator *self, PyObject *args) {
    PyObject *a_ = NULL, *b_ = NULL;
    int32_t asz = 0, bsz = 0;
    UChar *a = NULL, *b = NULL;
    UCollationResult res = UCOL_EQUAL;
  
    if (!PyArg_ParseTuple(args, "OO", &a_, &b_)) return NULL;

    a = python_to_icu(a_, &asz, 1);
    if (a == NULL) goto end;
    b = python_to_icu(b_, &bsz, 1);
    if (b == NULL) goto end;
    res = ucol_strcoll(self->collator, a, asz, b, bsz);
end:
    if (a != NULL) free(a); if (b != NULL) free(b);

    return (PyErr_Occurred()) ? NULL : Py_BuildValue("i", res);
} // }}}

// Collator.find {{{
static PyObject *
icu_Collator_find(icu_Collator *self, PyObject *args) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif
    PyObject *a_ = NULL, *b_ = NULL;
    UChar *a = NULL, *b = NULL;
    int32_t asz = 0, bsz = 0, pos = -1, length = -1;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
  
    if (!PyArg_ParseTuple(args, "OO", &a_, &b_)) return NULL;

    a = python_to_icu(a_, &asz, 1);
    if (a == NULL) goto end;
    b = python_to_icu(b_, &bsz, 1);
    if (b == NULL) goto end;

    search = usearch_openFromCollator(a, asz, b, bsz, self->collator, NULL, &status);
    if (U_SUCCESS(status)) {
        pos = usearch_first(search, &status);
        if (pos != USEARCH_DONE) {
            length = usearch_getMatchedLength(search);
#ifdef Py_UNICODE_WIDE
            // We have to return number of unicode characters since the string
            // could contain surrogate pairs which are represented as a single
            // character in python wide builds
            length = u_countChar32(b + pos, length);
            pos = u_countChar32(b, pos);
#endif
        } else pos = -1;
    }
end:
    if (search != NULL) usearch_close(search);
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    return (PyErr_Occurred()) ? NULL : Py_BuildValue("ll", (long)pos, (long)length);
} // }}}

// Collator.contains {{{
static PyObject *
icu_Collator_contains(icu_Collator *self, PyObject *args) {
    PyObject *a_ = NULL, *b_ = NULL;
    UChar *a = NULL, *b = NULL;
    int32_t asz = 0, bsz = 0, pos = -1;
    uint8_t found = 0;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
  
    if (!PyArg_ParseTuple(args, "OO", &a_, &b_)) return NULL;

    a = python_to_icu(a_, &asz, 1);
    if (a == NULL) goto end;
    if (asz == 0) { found = TRUE; goto end; }
    b = python_to_icu(b_, &bsz, 1);
    if (b == NULL) goto end;

    search = usearch_openFromCollator(a, asz, b, bsz, self->collator, NULL, &status);
    if (U_SUCCESS(status)) {
        pos = usearch_first(search, &status);
        if (pos != USEARCH_DONE) found = TRUE;
    }
end:
    if (search != NULL) usearch_close(search);
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    if (PyErr_Occurred()) return NULL;
    if (found) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
} // }}}

// Collator.contractions {{{
static PyObject *
icu_Collator_contractions(icu_Collator *self, PyObject *args) {
    UErrorCode status = U_ZERO_ERROR;
    UChar *str = NULL;
    UChar32 start=0, end=0;
    int32_t count = 0, len = 0, i;
    PyObject *ans = Py_None, *pbuf;

    if (self->contractions == NULL) {
        self->contractions = uset_open(1, 0);
        if (self->contractions == NULL) return PyErr_NoMemory();
        self->contractions = ucol_getTailoredSet(self->collator, &status);
    }
    status = U_ZERO_ERROR; 
    count = uset_getItemCount(self->contractions);

    str = (UChar*)calloc(100, sizeof(UChar));
    if (str == NULL) { PyErr_NoMemory(); goto end; }
    ans = PyTuple_New(count);
    if (ans == NULL) { goto end; }

    for (i = 0; i < count; i++) {
        len = uset_getItem(self->contractions, i, &start, &end, str, 1000, &status);
        if (len >= 2) {
            // We have a string
            status = U_ZERO_ERROR;
            pbuf = icu_to_python(str, len);
            if (pbuf == NULL) { Py_DECREF(ans); ans = NULL; goto end; }
            PyTuple_SetItem(ans, i, pbuf);
        } else {
            // Ranges dont make sense for contractions, ignore them
            PyTuple_SetItem(ans, i, Py_None); Py_INCREF(Py_None);
        }
    }
end:
    if (str != NULL) free(str);
  
    return ans;
} // }}}

// Collator.startswith {{{
static PyObject *
icu_Collator_startswith(icu_Collator *self, PyObject *args) {
    PyObject *a_ = NULL, *b_ = NULL;
    int32_t asz = 0, bsz = 0;
    UChar *a = NULL, *b = NULL;
    uint8_t ans = 0;
  
    if (!PyArg_ParseTuple(args, "OO", &a_, &b_)) return NULL;

    a = python_to_icu(a_, &asz, 1);
    if (a == NULL) goto end;
    b = python_to_icu(b_, &bsz, 1);
    if (b == NULL) goto end;

    if (asz < bsz) goto end;
    if (bsz == 0) { ans = 1; goto end; }
    
    ans = ucol_equal(self->collator, a, bsz, b, bsz);

end:
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    if (PyErr_Occurred()) return NULL;
    if (ans) { Py_RETURN_TRUE; }
    Py_RETURN_FALSE;
} // }}}

// Collator.collation_order {{{
static PyObject *
icu_Collator_collation_order(icu_Collator *self, PyObject *a_) {
    int32_t asz = 0;
    UChar *a = NULL;
    UErrorCode status = U_ZERO_ERROR;
    UCollationElements *iter = NULL;
    int order = 0, len = -1;
  
    a = python_to_icu(a_, &asz, 1);
    if (a == NULL) goto end;

    iter = ucol_openElements(self->collator, a, asz, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); goto end; }
    order = ucol_next(iter, &status);
    len = ucol_getOffset(iter);
end:
    if (iter != NULL) ucol_closeElements(iter); iter = NULL;
    if (a != NULL) free(a);
    if (PyErr_Occurred()) return NULL;
    return Py_BuildValue("ii", order, len);
} // }}}

// Collator.upper_first {{{
static PyObject *
icu_Collator_get_upper_first(icu_Collator *self, void *closure) {
    UErrorCode status = U_ZERO_ERROR;
    UColAttributeValue val;

    val = ucol_getAttribute(self->collator, UCOL_CASE_FIRST, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); return NULL; }

    if (val == UCOL_OFF) { Py_RETURN_NONE; }
    if (val) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static int
icu_Collator_set_upper_first(icu_Collator *self, PyObject *val, void *closure) {
    UErrorCode status = U_ZERO_ERROR;
    ucol_setAttribute(self->collator, UCOL_CASE_FIRST, (val == Py_None) ? UCOL_OFF : ((PyObject_IsTrue(val)) ? UCOL_UPPER_FIRST : UCOL_LOWER_FIRST), &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); return -1; }
    return 0;
}
// }}}

static PyObject*
icu_Collator_clone(icu_Collator *self, PyObject *args);

static PyMethodDef icu_Collator_methods[] = {
    {"sort_key", (PyCFunction)icu_Collator_sort_key, METH_O,
     "sort_key(unicode object) -> Return a sort key for the given object as a bytestring. The idea is that these bytestring will sort using the builtin cmp function, just like the original unicode strings would sort in the current locale with ICU."
    },

    {"strcmp", (PyCFunction)icu_Collator_strcmp, METH_VARARGS,
     "strcmp(unicode object, unicode object) -> strcmp(a, b) <=> cmp(sorty_key(a), sort_key(b)), but faster."
    },

    {"find", (PyCFunction)icu_Collator_find, METH_VARARGS,
        "find(pattern, source) -> returns the position and length of the first occurrence of pattern in source. Returns (-1, -1) if not found."
    },

    {"contains", (PyCFunction)icu_Collator_contains, METH_VARARGS,
        "contains(pattern, source) -> return True iff the pattern was found in the source."
    },

    {"contractions", (PyCFunction)icu_Collator_contractions, METH_NOARGS,
        "contractions() -> returns the contractions defined for this collator."
    },

    {"clone", (PyCFunction)icu_Collator_clone, METH_NOARGS,
        "clone() -> returns a clone of this collator."
    },

    {"startswith", (PyCFunction)icu_Collator_startswith, METH_VARARGS,
        "startswith(a, b) -> returns True iff a startswith b, following the current collation rules."
    },

    {"collation_order", (PyCFunction)icu_Collator_collation_order, METH_O,
        "collation_order(string) -> returns (order, length) where order is an integer that gives the position of string in a list. length gives the number of characters used for order."
    },

    {NULL}  /* Sentinel */
};

static PyGetSetDef  icu_Collator_getsetters[] = {
    {(char *)"actual_locale", 
     (getter)icu_Collator_actual_locale, NULL,
     (char *)"Actual locale used by this collator.",
     NULL},

    {(char *)"capsule", 
     (getter)icu_Collator_capsule, NULL,
     (char *)"A capsule enclosing the pointer to the ICU collator struct",
     NULL},

    {(char *)"display_name", 
     (getter)icu_Collator_display_name, NULL,
     (char *)"Display name of this collator in English. The name reflects the actual data source used.",
     NULL},

    {(char *)"strength",
     (getter)icu_Collator_get_strength, (setter)icu_Collator_set_strength,
     (char *)"The strength of this collator.",
     NULL},

    {(char *)"upper_first",
     (getter)icu_Collator_get_upper_first, (setter)icu_Collator_set_upper_first,
     (char *)"Whether this collator should always put upper case letters before lower case. Values are: None - means use the tertiary strength of the letters. True - Always sort upper case before lower case. False - Always sort lower case before upper case.",
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
icu_Collator_clone(icu_Collator *self, PyObject *args)
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

// BreakIterator object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UBreakIterator *break_iterator;
    UChar *text;
    int32_t text_len;
    UBreakIteratorType type;

} icu_BreakIterator;

static void
icu_BreakIterator_dealloc(icu_BreakIterator* self)
{
    if (self->break_iterator != NULL) ubrk_close(self->break_iterator);
    if (self->text != NULL) free(self->text);
    self->break_iterator = NULL; self->text = NULL;
    self->ob_type->tp_free((PyObject*)self);
}


static PyObject *
icu_BreakIterator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    icu_BreakIterator *self = NULL;
    const char *locale = NULL;
    int break_iterator_type = UBRK_WORD;
    UErrorCode status = U_ZERO_ERROR;
    UBreakIterator *break_iterator;

    if (!PyArg_ParseTuple(args, "is", &break_iterator_type, &locale)) return NULL;
    break_iterator = ubrk_open(break_iterator_type, locale, NULL, 0, &status);
    if (break_iterator == NULL || U_FAILURE(status)) { 
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return NULL;
    }

    self = (icu_BreakIterator *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->break_iterator = break_iterator;
    }
    self->text = NULL; self->text_len = 0; self->type = break_iterator_type;

    return (PyObject *)self;
}

// BreakIterator.set_text {{{
static PyObject *
icu_BreakIterator_set_text(icu_BreakIterator *self, PyObject *input) {
    int32_t sz = 0;
    UChar *buf = NULL;
    UErrorCode status = U_ZERO_ERROR;
  
    buf = python_to_icu(input, &sz, 1);
    if (buf == NULL) return NULL;
    ubrk_setText(self->break_iterator, buf, sz, &status);
    if (U_FAILURE(status)) {
        free(buf); buf = NULL;
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
    } else { self->text = buf; self->text_len = sz; }

    Py_RETURN_NONE;

} // }}}

#define IS_HYPHEN_CHAR(x) ((x) == 0x2d || (x) == 0x2010)

// BreakIterator.index {{{
static PyObject *
icu_BreakIterator_index(icu_BreakIterator *self, PyObject *token) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif

    UChar *buf = NULL, *needle = NULL;
    int32_t word_start = 0, p = 0, sz = 0, ans = -1, leading_hyphen = 0, trailing_hyphen = 0;
  
    buf = python_to_icu(token, &sz, 1);
    if (buf == NULL) return NULL;
    if (sz < 1) goto end;
    needle = buf;
    if (sz > 1 && IS_HYPHEN_CHAR(buf[0])) { needle = buf + 1; leading_hyphen = 1; sz -= 1; }
    if (sz > 1 && IS_HYPHEN_CHAR(buf[sz-1])) trailing_hyphen = 1;

    Py_BEGIN_ALLOW_THREADS;
    p = ubrk_first(self->break_iterator);
    while (p != UBRK_DONE) {
        word_start = p; p = ubrk_next(self->break_iterator);
        if (self->type == UBRK_WORD && ubrk_getRuleStatus(self->break_iterator) == UBRK_WORD_NONE) 
            continue;  // We are not at the start of a word

        if (self->text_len >= word_start + sz && memcmp(self->text + word_start, needle, sz * sizeof(UChar)) == 0) {
            if (word_start > 0 && (
                    (leading_hyphen && !IS_HYPHEN_CHAR(self->text[word_start-1])) ||
                    (!leading_hyphen && IS_HYPHEN_CHAR(self->text[word_start-1]))
            )) continue;
            if (!trailing_hyphen && IS_HYPHEN_CHAR(self->text[word_start + sz])) continue;

            if (p == UBRK_DONE || self->text_len <= word_start + sz) { ans = word_start; break; }

            if (
                    // Check that the found word is followed by a word boundary
                    ubrk_isBoundary(self->break_iterator, word_start + sz) &&
                    // If there is a leading hyphen check  that the leading
                    // hyphen is preceded by a word boundary
                    (!leading_hyphen || (word_start > 1 && ubrk_isBoundary(self->break_iterator, word_start - 2))) &&
                    // Check that there is a word boundary *after* the trailing
                    // hyphen. We cannot rely on ubrk_isBoundary() as that
                    // always returns true because of the trailing hyphen.
                    (!trailing_hyphen || ubrk_following(self->break_iterator, word_start + sz) == UBRK_DONE || ubrk_getRuleStatus(self->break_iterator) == UBRK_WORD_NONE)
            ) { ans = word_start; break; }

            if (p != UBRK_DONE) ubrk_isBoundary(self->break_iterator, p); // Reset the iterator to its position before the call to ubrk_isBoundary()
        }
    }
    if (leading_hyphen && ans > -1) ans -= 1;
#ifdef Py_UNICODE_WIDE
    if (ans > 0) ans = u_countChar32(self->text, ans);
#endif
    Py_END_ALLOW_THREADS;

end:
    free(buf);
    return Py_BuildValue("l", (long)ans);

} // }}}

// BreakIterator.split2 {{{
static PyObject *
icu_BreakIterator_split2(icu_BreakIterator *self, PyObject *args) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif

    int32_t word_start = 0, p = 0, sz = 0, last_pos = 0, last_sz = 0;
    int is_hyphen_sep = 0, leading_hyphen = 0, trailing_hyphen = 0;
    UChar sep = 0;
    PyObject *ans = NULL, *temp = NULL, *t = NULL;
  
    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    p = ubrk_first(self->break_iterator);
    while (p != UBRK_DONE) {
        word_start = p; p = ubrk_next(self->break_iterator);
        if (self->type == UBRK_WORD && ubrk_getRuleStatus(self->break_iterator) == UBRK_WORD_NONE) 
            continue;  // We are not at the start of a word
        sz = (p == UBRK_DONE) ? self->text_len - word_start : p - word_start;
        if (sz > 0) {
            // ICU breaks on words containing hyphens, we do not want that, so we recombine manually
            is_hyphen_sep = 0; leading_hyphen = 0; trailing_hyphen = 0;
            if (word_start > 0) { // Look for a leading hyphen
                sep = *(self->text + word_start - 1);
                if (IS_HYPHEN_CHAR(sep)) {
                    leading_hyphen = 1;
                    if (last_pos > 0 && word_start - last_pos == 1) is_hyphen_sep = 1;
                }
            }
            if (word_start + sz < self->text_len) { // Look for a trailing hyphen
                sep = *(self->text + word_start + sz);
                if (IS_HYPHEN_CHAR(sep)) trailing_hyphen = 1;
            }
            last_pos = p;
#ifdef Py_UNICODE_WIDE
            sz = u_countChar32(self->text + word_start, sz);
            word_start = u_countChar32(self->text, word_start);
#endif
            if (is_hyphen_sep && PyList_GET_SIZE(ans) > 0) {
                sz = last_sz + sz + trailing_hyphen;
                last_sz = sz;
                t = PyInt_FromLong((long)sz);
                if (t == NULL) { Py_DECREF(ans); ans = NULL; break; }
                temp = PyList_GET_ITEM(ans, PyList_GET_SIZE(ans) - 1);
                Py_DECREF(PyTuple_GET_ITEM(temp, 1));
                PyTuple_SET_ITEM(temp, 1, t);
            } else {
                sz += leading_hyphen + trailing_hyphen;
                last_sz = sz;
                temp = Py_BuildValue("ll", (long)(word_start - leading_hyphen), (long)sz); 
                if (temp == NULL) {
                    Py_DECREF(ans); ans = NULL; break; 
                } 
                if (PyList_Append(ans, temp) != 0) {
                    Py_DECREF(temp); Py_DECREF(ans); ans = NULL; break; 
                }
                Py_DECREF(temp);
            }
        }
    }

    return ans;

} // }}}

static PyMethodDef icu_BreakIterator_methods[] = {
    {"set_text", (PyCFunction)icu_BreakIterator_set_text, METH_O,
     "set_text(unicode object) -> Set the text this iterator will operate on"
    },

    {"split2", (PyCFunction)icu_BreakIterator_split2, METH_NOARGS,
     "split2() -> Split the current text into tokens, returning a list of 2-tuples of the form (position of token, length of token). The numbers are suitable for indexing python strings regardless of narrow/wide builds."
    },

    {"index", (PyCFunction)icu_BreakIterator_index, METH_O,
     "index(token) -> Find the index of the first match for token. Useful to find, for example, words that could also be a part of a larger word. For example, index('i') in 'string i' will be 7 not 3. Returns -1 if not found."
    },

    {NULL}  /* Sentinel */
};


static PyTypeObject icu_BreakIteratorType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "icu.BreakIterator",            /*tp_name*/
    sizeof(icu_BreakIterator),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)icu_BreakIterator_dealloc, /*tp_dealloc*/
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
    "Break Iterator",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    icu_BreakIterator_methods,             /* tp_methods */
    0,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    icu_BreakIterator_new,                 /* tp_new */
}; // }}}

// }}}

// change_case {{{

static PyObject* icu_change_case(PyObject *self, PyObject *args) {
    char *locale = NULL;
    PyObject *input = NULL, *result = NULL;
    int which = UPPER_CASE;
    UErrorCode status = U_ZERO_ERROR;
    UChar *input_buf = NULL, *output_buf = NULL;
    int32_t sz = 0;

    if (!PyArg_ParseTuple(args, "Oiz", &input, &which, &locale)) return NULL;
    if (locale == NULL) {
        PyErr_SetString(PyExc_NotImplementedError, "You must specify a locale");  // We deliberately use NotImplementedError so that this error can be unambiguously identified
        return NULL;
    }

    input_buf = python_to_icu(input, &sz, 1);
    if (input_buf == NULL) goto end;
    output_buf = (UChar*) calloc(3 * sz, sizeof(UChar));
    if (output_buf == NULL) { PyErr_NoMemory(); goto end; }

    switch (which) {
        case TITLE_CASE:
            sz = u_strToTitle(output_buf, 3 * sz, input_buf, sz, NULL, locale, &status);
            break;
        case UPPER_CASE:
            sz = u_strToUpper(output_buf, 3 * sz, input_buf, sz, locale, &status);
            break;
        default:
            sz = u_strToLower(output_buf, 3 * sz, input_buf, sz, locale, &status);
    }
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); goto end; }
    result = icu_to_python(output_buf, sz);

end:
    if (input_buf != NULL) free(input_buf);
    if (output_buf != NULL) free(output_buf);
    return result;

} // }}}

// swap_case {{{

static PyObject* icu_swap_case(PyObject *self, PyObject *input) {
    PyObject *result = NULL;
    UErrorCode status = U_ZERO_ERROR;
    UChar *input_buf = NULL, *output_buf = NULL;
    UChar32 *buf = NULL;
    int32_t sz = 0, sz32 = 0, i = 0;

    input_buf = python_to_icu(input, &sz, 1);
    if (input_buf == NULL) goto end;
    output_buf = (UChar*) calloc(3 * sz, sizeof(UChar));
    buf = (UChar32*) calloc(2 * sz, sizeof(UChar32));
    if (output_buf == NULL || buf == NULL) { PyErr_NoMemory(); goto end; }
    u_strToUTF32(buf, 2 * sz, &sz32, input_buf, sz, &status);

    for (i = 0; i < sz32; i++) {
        if (u_islower(buf[i])) buf[i] = u_toupper(buf[i]);
        else if (u_isupper(buf[i])) buf[i] = u_tolower(buf[i]);
    }
    u_strFromUTF32(output_buf, 3*sz, &sz, buf, sz32, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); goto end; }
    result = icu_to_python(output_buf, sz);

end:
    if (input_buf != NULL) free(input_buf);
    if (output_buf != NULL) free(output_buf);
    if (buf != NULL) free(buf);
    return result;

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

// set_filesystem_encoding {{{
static PyObject *
icu_set_filesystem_encoding(PyObject *self, PyObject *args) {
    char *encoding;
    if (!PyArg_ParseTuple(args, "s:setfilesystemencoding", &encoding))
        return NULL;
    Py_FileSystemDefaultEncoding = strdup(encoding);
    Py_RETURN_NONE;

}
// }}}

// get_available_transliterators {{{
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

// character_name {{{
static PyObject *
icu_character_name(PyObject *self, PyObject *args) {
    char name[512] = {0}; 
    int32_t sz = 0, alias = 0;
    UChar *buf;
    UErrorCode status = U_ZERO_ERROR;
    PyObject *palias = NULL, *result = NULL, *input = NULL;
    UChar32 code = 0;
  
    if (!PyArg_ParseTuple(args, "O|O", &input, &palias)) return NULL;

    if (palias != NULL && PyObject_IsTrue(palias)) alias = 1; 
    buf = python_to_icu(input, &sz, 1);
    if (buf == NULL) goto end; 
    U16_GET(buf, 0, 0, sz, code);
    if (alias) {
        sz = u_charName(code, U_CHAR_NAME_ALIAS, name, 511, &status);
    } else {
        sz = u_charName(code, U_UNICODE_CHAR_NAME, name, 511, &status);
    }
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "Failed to get name for code"); goto end; }
    result = PyUnicode_DecodeUTF8(name, sz, "strict");
end:
    if (buf != NULL) free(buf);

    return result;
} // }}}

// character_name_from_code {{{
static PyObject *
icu_character_name_from_code(PyObject *self, PyObject *args) {
    char name[512] = {0}; 
    int32_t sz, alias = 0;
    UErrorCode status = U_ZERO_ERROR;
    PyObject *palias = NULL, *result = NULL;
    UChar32 code = 0;
  
    if (!PyArg_ParseTuple(args, "I|O", &code, &palias)) return NULL;

    if (palias != NULL && PyObject_IsTrue(palias)) alias = 1; 
    
    if (alias) {
        sz = u_charName(code, U_CHAR_NAME_ALIAS, name, 511, &status);
    } else {
        sz = u_charName(code, U_UNICODE_CHAR_NAME, name, 511, &status);
    }
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "Failed to get name for code"); goto end; }
    result = PyUnicode_DecodeUTF8(name, sz, "strict");
end:
    return result;
} // }}}

// chr {{{
static PyObject *
icu_chr(PyObject *self, PyObject *args) {
    UErrorCode status = U_ZERO_ERROR;
    UChar32 code = 0;
    UChar buf[5] = {0};
    int32_t sz = 0;
  
    if (!PyArg_ParseTuple(args, "I", &code)) return NULL;

    u_strFromUTF32(buf, 4, &sz, &code, 1, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "arg not in range(0x110000)"); return NULL; }
    return icu_to_python(buf, sz);
} // }}}

// ord_string {{{
static PyObject *
icu_ord_string(PyObject *self, PyObject *input) {
    UChar32 *input_buf = NULL;
    int32_t sz = 0, i = 0;
    PyObject *ans = NULL, *temp = NULL;

    input_buf = python_to_icu32(input, &sz, 1);
    if (input_buf == NULL) goto end;
    ans = PyTuple_New(sz);
    if (ans == NULL) goto end;
    for (i = 0; i < sz; i++) {
        temp = PyInt_FromLong((long)input_buf[i]);
        if (temp == NULL) { Py_DECREF(ans); ans = NULL; PyErr_NoMemory(); goto end; }
        PyTuple_SET_ITEM(ans, i, temp);
    }
end:
    if (input_buf != NULL) free(input_buf);
    return ans;
  
} // }}}

// normalize {{{
static PyObject *
icu_normalize(PyObject *self, PyObject *args) {
    UErrorCode status = U_ZERO_ERROR;
    int32_t sz = 0, mode = UNORM_DEFAULT, cap = 0, rsz = 0;
    UChar *dest = NULL, *source = NULL;
    PyObject *ret = NULL, *src = NULL;
  
    if (!PyArg_ParseTuple(args, "iO", &mode, &src)) return NULL;
    source = python_to_icu(src, &sz, 1);
    if (source == NULL) goto end; 
    cap = 2 * sz;
    dest = (UChar*) calloc(cap, sizeof(UChar));
    if (dest == NULL) { PyErr_NoMemory(); goto end; }

    while (1) {
        rsz = unorm_normalize(source, sz, (UNormalizationMode)mode, 0, dest, cap, &status);
        if (status == U_BUFFER_OVERFLOW_ERROR) {
            cap *= 2;
            dest = (UChar*) realloc(dest, cap*sizeof(UChar));
            if (dest == NULL) { PyErr_NoMemory(); goto end; }
            continue;
        }
        break;
    }

    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        goto end;
    }
 
    ret = icu_to_python(dest, rsz);

end:
    if (source != NULL) free(source);
    if (dest != NULL) free(dest);
    return ret;
} // }}}

// roundtrip {{{
static PyObject *
icu_roundtrip(PyObject *self, PyObject *src) {
    int32_t sz = 0;
    UChar *icu = NULL;
    PyObject *ret = NULL;
  
    icu = python_to_icu(src, &sz, 1);
    if (icu != NULL) {
        ret = icu_to_python(icu, sz);
        free(icu);
    }
    return ret;
} // }}}

// available_locales_for_break_iterator {{{
static PyObject *
icu_break_iterator_locales(PyObject *self, PyObject *args) {
    int32_t count = 0, i = 0;
    const char *loc = NULL;
    PyObject *ret = NULL, *t = NULL;

    count = ubrk_countAvailable();
    ret = PyTuple_New(count);
    if (ret != NULL) {
        for (i = 0; i < count; i++) {
            loc = ubrk_getAvailable(i);
            if (!loc) loc = "";
            t = PyBytes_FromString(loc);
            if (t == NULL) { Py_DECREF(ret); ret = NULL; PyErr_NoMemory(); break; }
            PyTuple_SET_ITEM(ret, i, t);
        }
    }
  
    return ret;
} // }}}

// string_length {{{
static PyObject *
icu_string_length(PyObject *self, PyObject *src) {
    int32_t sz = 0;
    UChar *icu = NULL;
  
    icu = python_to_icu(src, &sz, 1);
    if (icu == NULL) return NULL;
    sz = u_countChar32(icu, sz);
    free(icu);
    return Py_BuildValue("l", (long)sz);
} // }}}

// utf16_length {{{
static PyObject *
icu_utf16_length(PyObject *self, PyObject *src) {
#if PY_VERSION_HEX >= 0x03030000 
#error Not implemented for python >= 3.3
#endif

    int32_t sz = 0;
#ifdef Py_UNICODE_WIDE
    int32_t i = 0, t = 0;
    Py_UNICODE *data = NULL;
#endif
  
    if (!PyUnicode_Check(src)) { PyErr_SetString(PyExc_TypeError, "Must be a unicode object"); return NULL; }
    sz = (int32_t)PyUnicode_GET_SIZE(src);
#ifdef Py_UNICODE_WIDE
    data = PyUnicode_AS_UNICODE(src);
    for (i = 0; i < sz; i++) {
        t += (data[i] > 0xffff) ? 2 : 1;
    }
    sz = t;
#endif
    return Py_BuildValue("l", (long)sz);
} // }}}

// Module initialization {{{
static PyMethodDef icu_methods[] = {
    {"change_case", icu_change_case, METH_VARARGS,
        "change_case(unicode object, which, locale) -> change case to one of UPPER_CASE, LOWER_CASE, TITLE_CASE"
    },

    {"swap_case", icu_swap_case, METH_O,
        "swap_case(unicode object) -> swaps the case using the simple, locale independent unicode algorithm"
    },

    {"set_default_encoding", icu_set_default_encoding, METH_VARARGS,
        "set_default_encoding(encoding) -> Set the default encoding for the python unicode implementation."
    },

    {"set_filesystem_encoding", icu_set_filesystem_encoding, METH_VARARGS,
        "set_filesystem_encoding(encoding) -> Set the filesystem encoding for python."
    },

    {"get_available_transliterators", icu_get_available_transliterators, METH_NOARGS,
        "get_available_transliterators() -> Return list of available transliterators. This list is rather limited on OS X."
    },

    {"character_name", icu_character_name, METH_VARARGS, 
     "character_name(char, alias=False) -> Return name for the first character in char, which must be a unicode string."
    },

    {"character_name_from_code", icu_character_name_from_code, METH_VARARGS, 
     "character_name_from_code(code, alias=False) -> Return the name for the specified unicode code point"
    },

    {"chr", icu_chr, METH_VARARGS, 
     "chr(code) -> Return a python unicode string corresponding to the specified character code. The string can have length 1 or 2 (for non BMP codes on narrow python builds)."
    },

    {"ord_string", icu_ord_string, METH_O, 
     "ord_string(code) -> Convert a python unicode string to a tuple of unicode codepoints."
    },

    {"normalize", icu_normalize, METH_VARARGS, 
     "normalize(mode, unicode_text) -> Return a python unicode string which is normalized in the specified mode."
    },

    {"roundtrip", icu_roundtrip, METH_O, 
     "roundtrip(string) -> Roundtrip a unicode object from python to ICU back to python (useful for testing)"
    },

    {"available_locales_for_break_iterator", icu_break_iterator_locales, METH_NOARGS, 
     "available_locales_for_break_iterator() -> Return tuple of all available locales for the BreakIterator"
    },

    {"string_length", icu_string_length, METH_O, 
     "string_length(string) -> Return the length of a string (number of unicode code points in the string). Useful on narrow python builds where len() returns an incorrect answer if the string contains surrogate pairs."
    },

    {"utf16_length", icu_utf16_length, METH_O, 
     "utf16_length(string) -> Return the length of a string (number of UTF-16 code points in the string). Useful on wide python builds where len() returns an incorrect answer if the string contains surrogate pairs."
    },

    {NULL}  /* Sentinel */
};

#define ADDUCONST(x) PyModule_AddIntConstant(m, #x, x)

CALIBRE_MODINIT_FUNC
initicu(void) 
{
    PyObject* m;
    UVersionInfo ver, uver;
    UErrorCode status = U_ZERO_ERROR;
    char version[U_MAX_VERSION_STRING_LENGTH+1] = {0}, uversion[U_MAX_VERSION_STRING_LENGTH+5] = {0};

    if (sizeof(Py_UNICODE) != 2 && sizeof(Py_UNICODE) != 4) {
        PyErr_SetString(PyExc_RuntimeError, "This module only works on python versions <= 3.2");
        return;
    }

    u_init(&status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_RuntimeError, u_errorName(status));
        return;
    }
    u_getVersion(ver);
    u_versionToString(ver, version);
    u_getUnicodeVersion(uver);
    u_versionToString(uver, uversion);

    if (PyType_Ready(&icu_CollatorType) < 0)
        return;
    if (PyType_Ready(&icu_BreakIteratorType) < 0)
        return;

    m = Py_InitModule3("icu", icu_methods,
                       "Wrapper for the ICU internationalization library");

    Py_INCREF(&icu_CollatorType); Py_INCREF(&icu_BreakIteratorType);
    PyModule_AddObject(m, "Collator", (PyObject *)&icu_CollatorType);
    PyModule_AddObject(m, "BreakIterator", (PyObject *)&icu_BreakIteratorType);
    // uint8_t must be the same size as char
    PyModule_AddIntConstant(m, "ok", (U_SUCCESS(status) && sizeof(uint8_t) == sizeof(char)) ? 1 : 0);
    PyModule_AddStringConstant(m, "icu_version", version);
    PyModule_AddStringConstant(m, "unicode_version", uversion);

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

    ADDUCONST(UNORM_NONE);
    ADDUCONST(UNORM_NFD);
    ADDUCONST(UNORM_NFKD);
    ADDUCONST(UNORM_NFC);
    ADDUCONST(UNORM_DEFAULT);
    ADDUCONST(UNORM_NFKC);
    ADDUCONST(UNORM_FCD);

    ADDUCONST(UPPER_CASE);
    ADDUCONST(LOWER_CASE);
    ADDUCONST(TITLE_CASE);

    ADDUCONST(UBRK_CHARACTER);
    ADDUCONST(UBRK_WORD);
    ADDUCONST(UBRK_LINE);
    ADDUCONST(UBRK_SENTENCE);

}
// }}}
