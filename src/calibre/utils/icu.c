#include "icu_calibre_utils.h"

#include <stdbool.h>

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
    UBreakIterator *word_iterator;

} icu_Collator;

static void
icu_Collator_dealloc(icu_Collator* self)
{
    if (self->collator != NULL) ucol_close(self->collator);
    if (self->contractions != NULL) uset_close(self->contractions);
    if (self->word_iterator) ubrk_close(self->word_iterator);
    self->collator = NULL; self->contractions = NULL;
    self->word_iterator = NULL;
    Py_TYPE(self)->tp_free((PyObject*)self);
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
        self->word_iterator = NULL;
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
    if (PyLong_Check(val)) ucol_setStrength(self->collator, (int)PyLong_AsLong(val));
    else {
        PyErr_SetString(PyExc_TypeError, "Strength must be an integer.");
        return -1;
    }
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

// Collator.numeric {{{
static PyObject *
icu_Collator_get_max_variable(icu_Collator *self, void *closure) {
    return Py_BuildValue("i", ucol_getMaxVariable(self->collator));
}

static int
icu_Collator_set_max_variable(icu_Collator *self, PyObject *val, void *closure) {
    int group = PyLong_AsLong(val);
    UErrorCode status = U_ZERO_ERROR;
    ucol_setMaxVariable(self->collator, group, &status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return -1;
    }
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

    buf = python_to_icu(input, &sz);
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
icu_Collator_strcmp(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *a_ = NULL, *b_ = NULL;
    int32_t asz = 0, bsz = 0;
    UChar *a = NULL, *b = NULL;
    UCollationResult res = UCOL_EQUAL;

    if (nargs != 2) { PyErr_SetString(PyExc_TypeError, "strcmp takes exactly 2 arguments"); return NULL; }
    a_ = args[0]; b_ = args[1];

    a = python_to_icu(a_, &asz);
    if (a == NULL) goto end;
    b = python_to_icu(b_, &bsz);
    if (b == NULL) goto end;
    res = ucol_strcoll(self->collator, a, asz, b, bsz);
end:
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    return (PyErr_Occurred()) ? NULL : Py_BuildValue("i", res);
} // }}}

// Collator.find {{{

static void
create_word_iterator(icu_Collator *self) {
    if (self->word_iterator) return;
    UErrorCode status = U_ZERO_ERROR;
    const char *loc = ucol_getLocaleByType(self->collator, ULOC_VALID_LOCALE, &status);
    if (U_FAILURE(status) || !loc) {
        PyErr_SetString(PyExc_ValueError, "Failed to get locale for collator");
        return;
    }
    self->word_iterator = ubrk_open(UBRK_WORD, loc, NULL, -1, &status);
    if (U_FAILURE(status) || !self->word_iterator) {
        PyErr_SetString(PyExc_ValueError, "Failed to create word break iterator for collator");
        return;
    }
}

static PyObject *
icu_Collator_find(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *a_ = NULL, *b_ = NULL;
    UChar *a = NULL, *b = NULL;
    int32_t asz = 0, bsz = 0, pos = -1, length = -1;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
    int whole_words = 0;

    if (nargs < 2 || nargs > 3) { PyErr_SetString(PyExc_TypeError, "find requires 2 or 3 arguments"); return NULL; }
    a_ = args[0]; b_ = args[1];
    if (!PyUnicode_Check(a_) || !PyUnicode_Check(b_)) { PyErr_SetString(PyExc_TypeError, "pattern and source must be unicode strings"); return NULL; }
    if (nargs > 2) whole_words = PyObject_IsTrue(args[2]);
    if (whole_words == -1) return NULL;
    if (whole_words) create_word_iterator(self);
    if (PyErr_Occurred()) return NULL;

    a = python_to_icu(a_, &asz);
    if (a == NULL) goto end;
    b = python_to_icu(b_, &bsz);
    if (b == NULL) goto end;

    search = usearch_openFromCollator(a, asz, b, bsz, self->collator, whole_words ? self->word_iterator : NULL, &status);
    if (U_SUCCESS(status)) {
        pos = usearch_first(search, &status);
        if (pos != USEARCH_DONE) {
            length = usearch_getMatchedLength(search);
            // We have to return number of unicode characters since the string
            // could contain surrogate pairs which are represented as a single
            // character in python wide builds
            length = u_countChar32(b + pos, length);
            pos = u_countChar32(b, pos);
        } else pos = -1;
    }
end:
    if (search != NULL) usearch_close(search);
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    return (PyErr_Occurred()) ? NULL : Py_BuildValue("ll", (long)pos, (long)length);
} // }}}

// Collator.find_all {{{
static PyObject *
icu_Collator_find_all(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *a_ = NULL, *b_ = NULL, *callback;
    UChar *a = NULL, *b = NULL;
    int32_t asz = 0, bsz = 0, pos = -1, length = -1;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;
    int whole_words = 0;

    if (nargs < 3 || nargs > 4) { PyErr_SetString(PyExc_TypeError, "find_all requires 3 or 4 arguments"); return NULL; }
    a_ = args[0]; b_ = args[1]; callback = args[2];
    if (!PyUnicode_Check(a_) || !PyUnicode_Check(b_)) { PyErr_SetString(PyExc_TypeError, "pattern and source must be unicode strings"); return NULL; }
    if (nargs > 3) whole_words = PyObject_IsTrue(args[3]);
    if (whole_words == -1) return NULL;
    if (whole_words) create_word_iterator(self);
    if (PyErr_Occurred()) return NULL;

    a = python_to_icu(a_, &asz);
    b = python_to_icu(b_, &bsz);
    if (a && b) {
        search = usearch_openFromCollator(a, asz, b, bsz, self->collator, whole_words ? self->word_iterator : NULL, &status);
        if (search && U_SUCCESS(status)) {
            pos = usearch_first(search, &status);
            int32_t pos_for_codepoint_count = 0, utf32pos = 0;
            while (pos != USEARCH_DONE) {
                utf32pos += u_countChar32(b + pos_for_codepoint_count, pos - pos_for_codepoint_count);
                pos_for_codepoint_count = pos;
                length = usearch_getMatchedLength(search);
                length = u_countChar32(b + pos, length);
                PyObject *ret = PyObject_CallFunction(callback, "ii", utf32pos, length);
                if (ret == Py_None) pos = usearch_next(search, &status);
                else { pos = USEARCH_DONE; if (ret == NULL) PyErr_Clear(); }
                Py_CLEAR(ret);
            }
        } else PyErr_SetString(PyExc_ValueError, u_errorName(status));
    }
    if (search != NULL) usearch_close(search);
    if (a != NULL) free(a);
    if (b != NULL) free(b);

    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
} // }}}

// Collator.contains {{{
static PyObject *
icu_Collator_contains(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *a_ = NULL, *b_ = NULL;
    UChar *a = NULL, *b = NULL;
    int32_t asz = 0, bsz = 0, pos = -1;
    uint8_t found = 0;
    UErrorCode status = U_ZERO_ERROR;
    UStringSearch *search = NULL;

    if (nargs != 2) { PyErr_SetString(PyExc_TypeError, "contains takes exactly 2 arguments"); return NULL; }
    a_ = args[0]; b_ = args[1];

    a = python_to_icu(a_, &asz);
    if (a == NULL) goto end;
    if (asz == 0) { found = true; goto end; }
    b = python_to_icu(b_, &bsz);
    if (b == NULL) goto end;

    search = usearch_openFromCollator(a, asz, b, bsz, self->collator, NULL, &status);
    if (U_SUCCESS(status)) {
        pos = usearch_first(search, &status);
        if (pos != USEARCH_DONE) found = true;
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
            // Ranges don't make sense for contractions, ignore them
            PyTuple_SetItem(ans, i, Py_None); Py_INCREF(Py_None);
        }
    }
end:
    if (str != NULL) free(str);

    return ans;
} // }}}

// Collator.startswith {{{
static PyObject *
icu_Collator_startswith(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *a_ = NULL, *b_ = NULL;
    int32_t asz = 0, bsz = 0, start = 0;
    UChar *a = NULL, *b = NULL;
    unsigned offset = 0;
    if (nargs < 2 || nargs > 3) { PyErr_SetString(PyExc_TypeError, "startswith requires 2 or 3 arguments"); return NULL; }
    a_ = args[0]; b_ = args[1];
    if (nargs > 2) {
        unsigned long v = PyLong_AsUnsignedLong(args[2]);
        if (PyErr_Occurred()) return NULL;
        offset = (unsigned)v;
    }
    a = python_to_icu(a_, &asz); if (a == NULL) return NULL;
    b = python_to_icu(b_, &bsz); if (b == NULL) { Py_DECREF(a); return NULL; }
    PyObject *ans = Py_False;
    if (offset > 0) {
        // Advance start by 'offset' Unicode codepoints within the UTF-16 buffer.
        U16_FWD_N(a, start, asz, (uint32_t)offset);
        if (start >= asz) {
            // offset is at or beyond end of string; only an empty prefix can match
            if (bsz == 0) ans = Py_True;
            goto end;
        }
    }
    if (asz - start < bsz) goto end;
    if (bsz == 0) { ans = Py_True; goto end; }
    if (ucol_equal(self->collator, a + start, bsz, b, bsz)) ans = Py_True;
end:
    free(a); free(b); return Py_NewRef(ans);
} // }}}

// Collator.collation_order {{{
static PyObject *
icu_Collator_collation_order(icu_Collator *self, PyObject *a_) {
    int32_t asz = 0;
    UChar *a = NULL;
    UErrorCode status = U_ZERO_ERROR;
    UCollationElements *iter = NULL;
    int order = 0, len = -1;

    a = python_to_icu(a_, &asz);
    if (a == NULL) goto end;

    iter = ucol_openElements(self->collator, a, asz, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); goto end; }
    order = ucol_next(iter, &status);
    len = ucol_getOffset(iter);
end:
    if (iter != NULL) { ucol_closeElements(iter); iter = NULL; }
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


// Collator.get/set_attribute {{{
static PyObject *
icu_Collator_get_attribute(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    if (nargs != 1) { PyErr_SetString(PyExc_TypeError, "get_attribute takes exactly 1 argument"); return NULL; }
    int k = (int)PyLong_AsLong(args[0]);
    if (PyErr_Occurred()) return NULL;
    UErrorCode status = U_ZERO_ERROR;
    long v = ucol_getAttribute(self->collator, k, &status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return NULL;
    }
    return PyLong_FromLong(v);
}

static PyObject *
icu_Collator_set_attribute(icu_Collator *self, PyObject *const *args, Py_ssize_t nargs) {
    if (nargs != 2) { PyErr_SetString(PyExc_TypeError, "set_attribute takes exactly 2 arguments"); return NULL; }
    int k = (int)PyLong_AsLong(args[0]);
    if (PyErr_Occurred()) return NULL;
    int v = (int)PyLong_AsLong(args[1]);
    if (PyErr_Occurred()) return NULL;
    UErrorCode status = U_ZERO_ERROR;
    ucol_setAttribute(self->collator, k, v, &status);
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return NULL;
    }
    Py_RETURN_NONE;
} // }}}

static PyObject*
icu_Collator_clone(icu_Collator *self, PyObject *args);

static PyMethodDef icu_Collator_methods[] = {
    {"sort_key", (PyCFunction)icu_Collator_sort_key, METH_O,
     "sort_key(unicode object) -> Return a sort key for the given object as a bytestring. The idea is that these bytestring will sort using the builtin cmp function, just like the original unicode strings would sort in the current locale with ICU."
    },

    {"get_attribute", (PyCFunction)(void(*)(void))icu_Collator_get_attribute, METH_FASTCALL,
     "get_attribute(key) -> get the specified attribute on this collator."
    },

    {"set_attribute", (PyCFunction)(void(*)(void))icu_Collator_set_attribute, METH_FASTCALL,
     "set_attribute(key, val) -> set the specified attribute on this collator."
    },

    {"strcmp", (PyCFunction)(void(*)(void))icu_Collator_strcmp, METH_FASTCALL,
     "strcmp(unicode object, unicode object) -> strcmp(a, b) <=> cmp(sorty_key(a), sort_key(b)), but faster."
    },

    {"find_all", (PyCFunction)(void(*)(void))icu_Collator_find_all, METH_FASTCALL,
        "find(pattern, source, callback) -> reports the position and length of all occurrences of pattern in source to callback. Aborts if callback returns anything other than None."
    },

    {"find", (PyCFunction)(void(*)(void))icu_Collator_find, METH_FASTCALL,
        "find(pattern, source) -> returns the position and length of the first occurrence of pattern in source. Returns (-1, -1) if not found."
    },

    {"contains", (PyCFunction)(void(*)(void))icu_Collator_contains, METH_FASTCALL,
        "contains(pattern, source) -> return True iff the pattern was found in the source."
    },

    {"contractions", (PyCFunction)icu_Collator_contractions, METH_NOARGS,
        "contractions() -> returns the contractions defined for this collator."
    },

    {"clone", (PyCFunction)icu_Collator_clone, METH_NOARGS,
        "clone() -> returns a clone of this collator."
    },

    {"startswith", (PyCFunction)(void(*)(void))icu_Collator_startswith, METH_FASTCALL,
        "startswith(a, b, offset=0) -> returns True iff a startswith b at the given codepoint offset, following the current collation rules."
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

    {(char *)"max_variable",
     (getter)icu_Collator_get_max_variable, (setter)icu_Collator_set_max_variable,
     (char *)"The highest sorting character affected by alternate handling",
     NULL},


    {NULL}  /* Sentinel */
};

static PyTypeObject icu_CollatorType = { // {{{
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "icu.Collator",
    /* tp_basicsize      */ sizeof(icu_Collator),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)icu_Collator_dealloc,
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
    /* tp_flags          */ Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,
    /* tp_doc            */ "Collator",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ icu_Collator_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ icu_Collator_getsetters,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ icu_Collator_new,
}; // }}}

// }}

// Collator.clone {{{
static PyObject*
icu_Collator_clone(icu_Collator *self, PyObject *args)
{
    UCollator *collator;
    UErrorCode status = U_ZERO_ERROR;
    icu_Collator *clone;

#if U_ICU_VERSION_MAJOR_NUM > 70
    collator = ucol_clone(self->collator, &status);
#else
    collator = ucol_safeClone(self->collator, NULL, NULL, &status);
#endif

    if (collator == NULL || U_FAILURE(status)) {
        PyErr_SetString(PyExc_Exception, "Failed to create collator.");
        return NULL;
    }

    clone = PyObject_New(icu_Collator, &icu_CollatorType);
    if (clone == NULL) return PyErr_NoMemory();

    clone->collator = collator;
    clone->contractions = NULL;
#if U_ICU_VERSION_MAJOR_NUM > 68
    if (self->word_iterator) clone->word_iterator = ubrk_clone(self->word_iterator, &status);
#else
    if (self->word_iterator) clone->word_iterator = ubrk_safeClone(self->word_iterator, NULL, NULL, &status);
#endif
    else clone->word_iterator = NULL;

    return (PyObject*) clone;

} // }}}

// }}}

// Transliterator object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UTransliterator *transliterator;
} icu_Transliterator;

static void
icu_Transliterator_dealloc(icu_Transliterator* self)
{
    if (self->transliterator != NULL) utrans_close(self->transliterator);
    self->transliterator = NULL;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
icu_Transliterator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    icu_Transliterator *self = NULL;
    UErrorCode status = U_ZERO_ERROR;
    PyObject *idp, *rulesp;
    int forward = 1;

    if (!PyArg_ParseTuple(args, "UU|p", &idp, &rulesp, &forward)) return NULL;
    int32_t id_sz, rules_sz = 0;
    UChar *id = python_to_icu(idp, &id_sz);
    if (!id) return NULL;
    UChar *rules = PyUnicode_GET_LENGTH(rulesp) > 0 ? python_to_icu(rulesp, &rules_sz) : NULL;
    if (PyErr_Occurred()) { free(id); return NULL; }
    UParseError pe;
    UTransliterator* t = utrans_openU(id, id_sz, forward ? UTRANS_FORWARD : UTRANS_REVERSE, rules, rules_sz, &pe, &status);
    free(id); free(rules); id = NULL; rules = NULL;
    if (t == NULL || U_FAILURE(status)) {
        PyObject *pre = icu_to_python(pe.preContext, u_strlen(pe.preContext)), *post = icu_to_python(pe.postContext, u_strlen(pe.postContext));
        PyErr_Format(PyExc_ValueError, "Failed to compile Transliterator with error: %s line: %d offset: %d pre: %U post: %U", u_errorName(status), pe.line, pe.offset, pre, post);
        Py_CLEAR(pre); Py_CLEAR(post);
        if (t != NULL) utrans_close(t);
        return NULL;
    }
    self = (icu_Transliterator *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->transliterator = t;
    } else utrans_close(t);

    return (PyObject *)self;
}

typedef struct Replaceable {
    UChar *buf;
    int32_t sz, capacity;
} Replaceable;

static int32_t replaceable_length(const UReplaceable* rep) {
    const Replaceable* x = (const Replaceable*)rep;
    return x->sz;
}

static UChar replaceable_charAt(const UReplaceable* rep, int32_t offset) {
    const Replaceable* x = (const Replaceable*)rep;
    if (offset >= x->sz || offset < 0) return 0xffff;
    return x->buf[offset];
}

static UChar32 replaceable_char32At(const UReplaceable* rep, int32_t offset) {
    const Replaceable* x = (const Replaceable*)rep;
    if (offset >= x->sz || offset < 0) return 0xffff;
    UChar32 c;
    U16_GET_OR_FFFD(x->buf, 0, offset, x->sz, c);
    return c;
}

static void replaceable_replace(UReplaceable* rep, int32_t start, int32_t limit, const UChar* text, int32_t repl_len) {
    Replaceable* x = (Replaceable*)rep;
    /* printf("start replace: start=%d limit=%d x->sz: %d text=%s repl_len=%d\n", start, limit, x->sz, PyUnicode_AsUTF8(icu_to_python(text, repl_len)), repl_len); */
    const int32_t src_len = limit - start;
    if (repl_len <= src_len) {
        u_memcpy(x->buf + start, text, repl_len);
        if (repl_len < src_len) {
            u_memmove(x->buf + start + repl_len, x->buf + limit, x->sz - limit);
            x->sz -= src_len - repl_len;
        }
    } else {
        const int32_t sz = x->sz + (repl_len - src_len);
        UChar *n = x->buf;
        if (sz > x->capacity) n = realloc(x->buf, sizeof(UChar) * (sz + 256));
        if (n) {
            u_memmove(n + start + repl_len, n + limit, x->sz - limit);
            u_memcpy(n + start, text, repl_len);
            x->buf = n; x->sz = sz; x->capacity = sz + 256;
        }
    }
    /* printf("end replace: %s\n", PyUnicode_AsUTF8(icu_to_python(x->buf, x->sz))); */
}

static void replaceable_copy(UReplaceable* rep, int32_t start, int32_t limit, int32_t dest) {
    Replaceable* x = (Replaceable*)rep;
    /* printf("start copy: start=%d limit=%d x->sz: %d dest=%d\n", start, limit, x->sz, dest); */
    int32_t sz = x->sz + limit - start;
    UChar *n = malloc((sz + 256) * sizeof(UChar));
    if (n) {
        u_memcpy(n, x->buf, dest);
        u_memcpy(n + dest, x->buf + start, limit - start);
        u_memcpy(n + dest + limit - start, x->buf + dest, x->sz - dest);
        free(x->buf);
        x->buf = n; x->sz = sz; x->capacity = sz + 256;
    }
    /* printf("end copy: %s\n", PyUnicode_AsUTF8(icu_to_python(x->buf, x->sz))); */
}

static void replaceable_extract(UReplaceable* rep, int32_t start, int32_t limit, UChar* dst) {
    Replaceable* x = (Replaceable*)rep;
    memcpy(dst, x->buf + start, sizeof(UChar) * (limit - start));
}

const static UReplaceableCallbacks replaceable_callbacks = {
    .length = replaceable_length,
    .charAt = replaceable_charAt,
    .char32At = replaceable_char32At,
    .replace = replaceable_replace,
    .extract = replaceable_extract,
    .copy = replaceable_copy,
};

static PyObject *
icu_Transliterator_transliterate(icu_Transliterator *self, PyObject *input) {
    Replaceable r;
    UErrorCode status = U_ZERO_ERROR;
    r.buf = python_to_icu(input, &r.sz);
    if (r.buf == NULL) return NULL;
    r.capacity = r.sz;
    int32_t limit = r.sz;
    utrans_trans(self->transliterator, (UReplaceable*)&r, &replaceable_callbacks, 0, &limit, &status);
    PyObject *ans = NULL;
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
    } else ans = icu_to_python(r.buf, limit);
    free(r.buf); r.buf = NULL;
    return ans;
}

static PyMethodDef icu_Transliterator_methods[] = {
    {"transliterate", (PyCFunction)icu_Transliterator_transliterate, METH_O,
     "transliterate(text) -> Run the transliterator on the specified text"
    },

    {NULL}  /* Sentinel */
};


static PyTypeObject icu_TransliteratorType = { // {{{
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "icu.Transliterator",
    /* tp_basicsize      */ sizeof(icu_Transliterator),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)icu_Transliterator_dealloc,
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
    /* tp_flags          */ Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,
    /* tp_doc            */ "Transliterator",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ icu_Transliterator_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ icu_Transliterator_new,
}; // }}}
// }}}

#define IS_HYPHEN_CHAR(x) ((x) == 0x2d || (x) == 0x2010)

// BreakIterator object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UBreakIterator *break_iterator;
    UChar *text;
    int32_t text_len;
    UBreakIteratorType type;
    unsigned long counter;  /* incremented on mutating method calls to invalidate live iterators */
    UChar32 *extra_word_break_chars;     /* optional sorted array of extra word-break codepoints */
    int32_t  num_extra_word_break_chars; /* length of the array; 0 = disabled (fast path) */
    int      hyphen_is_extra_break;      /* 1 if a hyphen char is in extra_word_break_chars */
} icu_BreakIterator;

static void
icu_BreakIterator_dealloc(icu_BreakIterator* self)
{
    if (self->break_iterator != NULL) ubrk_close(self->break_iterator);
    if (self->text != NULL) free(self->text);
    if (self->extra_word_break_chars != NULL) free(self->extra_word_break_chars);
    self->break_iterator = NULL; self->text = NULL; self->extra_word_break_chars = NULL;
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
icu_BreakIterator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    icu_BreakIterator *self = NULL;
    const char *locale = NULL;
    int break_iterator_type = UBRK_WORD;
    UErrorCode status = U_ZERO_ERROR;
    UBreakIterator *break_iterator;
    PyObject *extra_chars_obj = NULL;

    if (!PyArg_ParseTuple(args, "is|O", &break_iterator_type, &locale, &extra_chars_obj)) return NULL;
    break_iterator = ubrk_open(break_iterator_type, locale, NULL, 0, &status);
    if (break_iterator == NULL || U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return NULL;
    }

    self = (icu_BreakIterator *)type->tp_alloc(type, 0);
    if (self == NULL) { ubrk_close(break_iterator); return NULL; }
    self->break_iterator = break_iterator;
    self->counter = 0;
    self->text = NULL; self->text_len = 0; self->type = break_iterator_type;
    self->extra_word_break_chars = NULL; self->num_extra_word_break_chars = 0;
    self->hyphen_is_extra_break = 0;

    /* Parse optional extra break characters (only meaningful for UBRK_WORD). */
    if (extra_chars_obj != NULL && extra_chars_obj != Py_None
            && break_iterator_type == UBRK_WORD) {
        int32_t extra_sz = 0;
        UChar *extra_buf = python_to_icu(extra_chars_obj, &extra_sz);
        if (extra_buf == NULL) { Py_DECREF(self); return NULL; }
        int32_t count = u_countChar32(extra_buf, extra_sz);
        if (count > 0) {
            UChar32 *chars = (UChar32*)malloc(count * sizeof(UChar32));
            if (chars == NULL) { free(extra_buf); Py_DECREF(self); return PyErr_NoMemory(); }
            int32_t i = 0, j = 0;
            while (i < extra_sz) { U16_NEXT(extra_buf, i, extra_sz, chars[j]); j++; }
            free(extra_buf);
            /* Sort using insertion sort — sets are expected to be tiny. */
            for (int32_t k = 1; k < count; k++) {
                UChar32 key = chars[k]; int32_t m = k - 1;
                while (m >= 0 && chars[m] > key) { chars[m + 1] = chars[m]; m--; }
                chars[m + 1] = key;
            }
            self->extra_word_break_chars     = chars;
            self->num_extra_word_break_chars = count;
            /* Check if any hyphen character is in the extra break set. */
            for (int32_t k = 0; k < count; k++) {
                if (IS_HYPHEN_CHAR(chars[k])) { self->hyphen_is_extra_break = 1; break; }
            }
        } else {
            free(extra_buf);
        }
    }

    return (PyObject *)self;
}

// BreakIterator.set_text {{{
static PyObject *
icu_BreakIterator_set_text(icu_BreakIterator *self, PyObject *input) {
    int32_t sz = 0;
    UChar *buf = NULL;
    UErrorCode status = U_ZERO_ERROR;

    self->counter++;
    buf = python_to_icu(input, &sz);
    if (buf == NULL) return NULL;
    ubrk_setText(self->break_iterator, buf, sz, &status);
    if (U_FAILURE(status)) {
        free(buf); buf = NULL;
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
    } else { self->text = buf; self->text_len = sz; }

    Py_RETURN_NONE;

} // }}}

// BreakIterator.index {{{
static PyObject *
icu_BreakIterator_index(icu_BreakIterator *self, PyObject *token) {

    UChar *buf = NULL, *needle = NULL;
    int32_t word_start = 0, p = 0, sz = 0, ans = -1, leading_hyphen = 0, trailing_hyphen = 0;

    self->counter++;
    buf = python_to_icu(token, &sz);
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
    if (ans > 0) ans = u_countChar32(self->text, ans);
    Py_END_ALLOW_THREADS;

end:
    free(buf);
    return Py_BuildValue("l", (long)ans);

} // }}}

// BreakIterator iteration machinery {{{

static inline void
unicode_code_point_count(UChar **count_start, int32_t *last_count, int *last_count32, int32_t *word_start, int32_t *sz) {
	int32_t chars_to_new_word_from_last_pos = *word_start - *last_count;
	int32_t sz32 = u_countChar32(*count_start + chars_to_new_word_from_last_pos, *sz);
	int32_t codepoints_to_new_word_from_last_pos = u_countChar32(*count_start, chars_to_new_word_from_last_pos);
	*count_start += chars_to_new_word_from_last_pos + *sz;
	*last_count += chars_to_new_word_from_last_pos + *sz;
	*last_count32 += codepoints_to_new_word_from_last_pos;
	*word_start = *last_count32;
	*last_count32 += sz32;
	*sz = sz32;
}

/* State for lazily stepping through the break positions of an icu_BreakIterator.
   Usable from both C (split2, count_words) and Python (BreakIteratorIter). */
typedef struct {
    int32_t p;             /* current ICU iterator position */
    int32_t last_pos;      /* ICU end-position of last processed segment */
    int32_t last_sz;       /* code-point size of the pending (buffered) token */
    int32_t last_count;    /* UTF-16 offset bookkeeping for unicode_code_point_count */
    int     last_count32;  /* code-point offset bookkeeping */
    UChar  *count_start;   /* cursor through the text for unicode_code_point_count */
    int     found_one;     /* whether any token has been buffered yet */
    int     done;          /* whether the ICU iterator is exhausted */
    int     has_pending;   /* whether a buffered token is waiting to be yielded */
    int32_t pending_pos;
    int32_t pending_sz;
    /* Extra break character sub-segmentation state */
    int32_t extra_break_seg_start; /* UTF-16 start of the remaining sub-segment */
    int32_t extra_break_seg_end;   /* UTF-16 end (exclusive) of the remaining sub-segment */
    int     extra_break_active;    /* 1 if there is a pending sub-segment to process */
} BreakIterState;

static void
break_iter_state_init(icu_BreakIterator *bi, BreakIterState *state) {
    memset(state, 0, sizeof(state[0]));
    state->p            = ubrk_first(bi->break_iterator);
    state->count_start  = bi->text;
}

/* Find the first extra word-break character in the UTF-16 segment [start, end).
   Returns the UTF-16 offset of the character if found (and sets *char_len_out to its
   UTF-16 length), or -1 if not found. */
static inline int32_t
find_extra_word_break(const icu_BreakIterator *bi, int32_t start, int32_t end,
                      int32_t *char_len_out) {
    int32_t i = start;
    const UChar32 *chars = bi->extra_word_break_chars;
    const int32_t  n     = bi->num_extra_word_break_chars;
    while (i < end) {
        UChar32 c;
        int32_t prev_i = i;
        U16_NEXT(bi->text, i, end, c);
        for (int32_t k = 0; k < n; k++) {
            if (chars[k] == c) { *char_len_out = i - prev_i; return prev_i; }
        }
    }
    return -1;
}

/* Advance one step.
   Returns 1 with the next token stored in *pos_out / *sz_out.
   Returns 0 when there are no more tokens. */
static int
break_iter_state_next(icu_BreakIterator *bi, BreakIterState *state,
                      int32_t *pos_out, int32_t *sz_out) {
    int32_t word_start, sz;
    int is_hyphen_sep, leading_hyphen, trailing_hyphen, had_pending;
    int32_t prev_pos, prev_sz;
    UChar sep;

    if (state->done) {
        if (state->has_pending) {
            state->has_pending = 0;
            *pos_out = state->pending_pos;
            *sz_out  = state->pending_sz;
            return 1;
        }
        return 0;
    }

    for (;;) {
        /* --- Extra-break sub-segmentation ---
           When a prior ICU segment contained an extra break character, the remainder
           of that segment is stored in extra_break_seg_[start,end).  Drain it before
           fetching more data from the ICU iterator. */
        if (state->extra_break_active) {
            if (state->extra_break_seg_start >= state->extra_break_seg_end) {
                /* Sub-segment exhausted; fall through to the ICU loop. */
                state->extra_break_active = 0;
            } else {
                int32_t char_len;
                int32_t q = find_extra_word_break(bi,
                        state->extra_break_seg_start, state->extra_break_seg_end, &char_len);
                int32_t sub_ws = state->extra_break_seg_start; /* UTF-16 start of piece */
                if (q >= 0) {
                    sz = q - sub_ws;
                    state->extra_break_seg_start = q + char_len;
                } else {
                    sz = state->extra_break_seg_end - sub_ws;
                    state->extra_break_active = 0;
                }
                if (sz == 0) continue; /* empty piece (adjacent extra-break chars) */
                /* Check for a trailing hyphen at the UTF-16 level (before conversion)
                   so that a subsequent ICU segment can be hyphen-joined with this piece.
                   Skip when hyphens are themselves extra break chars. */
                int sub_trailing = 0;
                if (!bi->hyphen_is_extra_break && sub_ws + sz < bi->text_len) {
                    UChar trail = *(bi->text + sub_ws + sz);
                    if (IS_HYPHEN_CHAR(trail)) sub_trailing = 1;
                }
                word_start = sub_ws;
                unicode_code_point_count(&state->count_start, &state->last_count,
                                         &state->last_count32, &word_start, &sz);
                sz += sub_trailing; /* extend to include the trailing hyphen */
                had_pending        = state->has_pending;
                prev_pos           = state->pending_pos;
                prev_sz            = state->pending_sz;
                state->found_one   = 1;
                state->last_sz     = sz;
                state->has_pending = 1;
                state->pending_pos = word_start;
                state->pending_sz  = sz;
                if (had_pending) { *pos_out = prev_pos; *sz_out = prev_sz; return 1; }
                continue; /* look for more sub-segments or the next ICU token */
            }
        }

        /* --- ICU break iterator --- */
        if (state->p == UBRK_DONE) {
            /* ICU exhausted — flush the final buffered token. */
            state->done = 1;
            if (state->has_pending) {
                state->has_pending = 0;
                *pos_out = state->pending_pos;
                *sz_out  = state->pending_sz;
                return 1;
            }
            return 0;
        }

        word_start = state->p;
        state->p   = ubrk_next(bi->break_iterator);
        if (bi->type == UBRK_WORD &&
                ubrk_getRuleStatus(bi->break_iterator) == UBRK_WORD_NONE)
            continue; /* skip non-word runs (spaces, punctuation, …) */
        sz = (state->p == UBRK_DONE) ? bi->text_len - word_start
                                      : state->p     - word_start;
        if (sz <= 0) continue;

        /* Check for extra break characters inside this ICU word segment.
           Split at the first one; the tail is deferred into extra_break_seg. */
        if (bi->num_extra_word_break_chars > 0) {
            int32_t char_len;
            int32_t q = find_extra_word_break(bi, word_start, word_start + sz, &char_len);
            if (q >= 0) {
                state->extra_break_active    = 1;
                state->extra_break_seg_start = q + char_len;
                state->extra_break_seg_end   = word_start + sz;
                sz = q - word_start;
                if (sz == 0) continue; /* segment begins with an extra break char */
            }
        }

        is_hyphen_sep = 0; leading_hyphen = 0; trailing_hyphen = 0;
        if (!bi->hyphen_is_extra_break) {
            if (word_start > 0) {
                sep = *(bi->text + word_start - 1);
                if (IS_HYPHEN_CHAR(sep)) {
                    leading_hyphen = 1;
                    if (state->last_pos > 0 && word_start - state->last_pos == 1) is_hyphen_sep = 1;
                }
            }
            if (word_start + sz < bi->text_len) {
                sep = *(bi->text + word_start + sz);
                if (IS_HYPHEN_CHAR(sep)) trailing_hyphen = 1;
            }
        }
        state->last_pos = state->p;
        unicode_code_point_count(&state->count_start, &state->last_count,
                                  &state->last_count32, &word_start, &sz);
        if (is_hyphen_sep && state->found_one) {
            /* Extend the already-buffered token across the hyphen. */
            sz = state->last_sz + sz + trailing_hyphen;
            state->last_sz    = sz;
            state->pending_sz = sz;
        } else {
            /* Yield the previously buffered token (if any), then buffer this one. */
            had_pending = state->has_pending;
            prev_pos    = state->pending_pos;
            prev_sz     = state->pending_sz;
            state->found_one   = 1;
            sz += leading_hyphen + trailing_hyphen;
            state->last_sz     = sz;
            state->has_pending = 1;
            state->pending_pos = word_start - leading_hyphen;
            state->pending_sz  = sz;
            if (had_pending) { *pos_out = prev_pos; *sz_out = prev_sz; return 1; }
        }
    }
}

static PyObject *
icu_BreakIterator_count_words(icu_BreakIterator *self, PyObject *args) {
    unsigned long ans = 0;
    int32_t pos, sz;
    BreakIterState state;
    self->counter++;
    break_iter_state_init(self, &state);
    while (break_iter_state_next(self, &state, &pos, &sz)) ans++;
    return Py_BuildValue("k", ans);
}

static PyObject *
icu_BreakIterator_split2(icu_BreakIterator *self, PyObject *args) {
    PyObject *ans, *item;
    int32_t pos, sz;
    BreakIterState state;
    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();
    self->counter++;
    break_iter_state_init(self, &state);
    while (break_iter_state_next(self, &state, &pos, &sz)) {
        item = Py_BuildValue("ll", (long)pos, (long)sz);
        if (item == NULL || PyList_Append(ans, item) != 0) { Py_XDECREF(item); Py_DECREF(ans); return NULL; }
        Py_DECREF(item);
    }
    return ans;
}

// BreakIteratorIter object {{{

typedef struct {
    PyObject_HEAD
    icu_BreakIterator *parent;         /* strong reference */
    unsigned long      counter_at_creation;
    BreakIterState     state;
    int                positions_only; /* 0 = yield (pos,sz) tuples; 1 = yield pos ints */
} icu_BreakIteratorIterObject;

static void
icu_BreakIteratorIter_dealloc(icu_BreakIteratorIterObject *self)
{
    Py_CLEAR(self->parent);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
icu_BreakIteratorIter_iternext(icu_BreakIteratorIterObject *self)
{
    int32_t pos, sz;
    if (self->parent->counter != self->counter_at_creation) {
        PyErr_SetString(PyExc_RuntimeError,
            "BreakIterator was modified while iterating over it");
        return NULL;
    }
    if (!break_iter_state_next(self->parent, &self->state, &pos, &sz))
        return NULL;  /* StopIteration */
    if (self->positions_only) return PyLong_FromLong((long)pos);
    return Py_BuildValue("ll", (long)pos, (long)sz);
}

static PyTypeObject icu_BreakIteratorIterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "icu.BreakIteratorIter",
    /* tp_basicsize      */ sizeof(icu_BreakIteratorIterObject),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)icu_BreakIteratorIter_dealloc,
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
    /* tp_doc            */ "Break Iterator Iterator",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ PyObject_SelfIter,
    /* tp_iternext       */ (iternextfunc)icu_BreakIteratorIter_iternext,
}; // }}}

static PyObject *
make_break_iterator_iter(icu_BreakIterator *parent, int positions_only)
{
    icu_BreakIteratorIterObject *iter;
    if (parent->text == NULL || parent->text_len < 1) {
        PyErr_SetString(PyExc_ValueError, "No text has been set on this BreakIterator");
        return NULL;
    }
    iter = PyObject_New(icu_BreakIteratorIterObject, &icu_BreakIteratorIterType);
    if (iter == NULL) return NULL;
    parent->counter++;
    break_iter_state_init(parent, &iter->state);
    iter->counter_at_creation = parent->counter;
    iter->positions_only = positions_only;
    Py_INCREF(parent);
    iter->parent = parent;
    return (PyObject *)iter;
}

static PyObject *
icu_BreakIterator_iter_breaks(icu_BreakIterator *self, PyObject *args) {
    return make_break_iterator_iter(self, 0);
}

static PyObject *
icu_BreakIterator_iter_positions(icu_BreakIterator *self, PyObject *args) {
    return make_break_iterator_iter(self, 1);

} // }}}

static PyMethodDef icu_BreakIterator_methods[] = {
    {"set_text", (PyCFunction)icu_BreakIterator_set_text, METH_O,
     "set_text(unicode object) -> Set the text this iterator will operate on"
    },

    {"split2", (PyCFunction)icu_BreakIterator_split2, METH_NOARGS,
     "split2() -> Split the current text into tokens, returning a list of 2-tuples of the form (position of token, length of token). The numbers are suitable for indexing python strings regardless of narrow/wide builds."
    },

    {"iter_breaks", (PyCFunction)icu_BreakIterator_iter_breaks, METH_NOARGS,
     "iter_breaks() -> Split the current text into tokens, returning an iterator that yields 2-tuples of the form (position of token, length of token). The numbers are suitable for indexing python strings regardless of narrow/wide builds."
    },

    {"iter_positions", (PyCFunction)icu_BreakIterator_iter_positions, METH_NOARGS,
     "iter_positions() -> Split the current text into tokens, returning an iterator that yields the position of each token as an integer. The numbers are suitable for indexing python strings regardless of narrow/wide builds."
    },

    {"count_words", (PyCFunction)icu_BreakIterator_count_words, METH_NOARGS,
     "count_words() -> Split the current text into tokens as in split2() and count the number of tokens."
    },

    {"index", (PyCFunction)icu_BreakIterator_index, METH_O,
     "index(token) -> Find the index of the first match for token. Useful to find, for example, words that could also be a part of a larger word. For example, index('i') in 'string i' will be 7 not 3. Returns -1 if not found."
    },

    {NULL}  /* Sentinel */
};


static PyTypeObject icu_BreakIteratorType = { // {{{
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "icu.BreakIterator",
    /* tp_basicsize      */ sizeof(icu_BreakIterator),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)icu_BreakIterator_dealloc,
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
    /* tp_flags          */ Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,
    /* tp_doc            */ "BreakIterator(type, locale[, extra_word_break_chars]) -> Create a break iterator.\nFor UBRK_WORD iterators, extra_word_break_chars is an optional string of characters\nthat act as additional word-break points beyond the ICU defaults.",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ icu_BreakIterator_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ icu_BreakIterator_new,
}; // }}}

// }}}

// change_case {{{

static PyObject* icu_change_case(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    const char *locale = NULL;
    PyObject *input = NULL, *result = NULL;
    int which = UPPER_CASE;
    UErrorCode status = U_ZERO_ERROR;
    UChar *input_buf = NULL, *output_buf = NULL;
    int32_t sz = 0;

    if (nargs != 3) { PyErr_SetString(PyExc_TypeError, "change_case takes exactly 3 arguments"); return NULL; }
    input = args[0];
    which = (int)PyLong_AsLong(args[1]);
    if (PyErr_Occurred()) return NULL;
    if (args[2] == Py_None) locale = NULL;
    else if (PyUnicode_Check(args[2])) { locale = PyUnicode_AsUTF8(args[2]); if (!locale) return NULL; }
    else if (PyBytes_Check(args[2])) { locale = PyBytes_AS_STRING(args[2]); }
    else { PyErr_SetString(PyExc_TypeError, "locale must be a string or None"); return NULL; }
    if (locale == NULL) {
        PyErr_SetString(PyExc_NotImplementedError, "You must specify a locale");  // We deliberately use NotImplementedError so that this error can be unambiguously identified
        return NULL;
    }

    input_buf = python_to_icu(input, &sz);
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

    input_buf = python_to_icu(input, &sz);
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
icu_set_default_encoding(PyObject *self, PyObject *Py_UNUSED(ignored)) {
    Py_INCREF(Py_None);
    return Py_None;

}
// }}}

// set_filesystem_encoding {{{
static PyObject *
icu_set_filesystem_encoding(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    const char *encoding;
    if (nargs != 1) { PyErr_SetString(PyExc_TypeError, "set_filesystem_encoding takes exactly 1 argument"); return NULL; }
    if (PyUnicode_Check(args[0])) {
        encoding = PyUnicode_AsUTF8(args[0]);
        if (!encoding) return NULL;
    } else if (PyBytes_Check(args[0])) {
        encoding = PyBytes_AS_STRING(args[0]);
    } else {
        PyErr_SetString(PyExc_TypeError, "encoding must be a string");
        return NULL;
    }
#if PY_VERSION_HEX < 0x03012000
    // The nitwits at Python deprecated this in 3.12 claiming we should use
    // PyConfig.filesystem_encoding instead. But that can only be used if we
    // control the interpreter, which we do not in Linux distro builds. Sigh.
    // Well, if this causes issues we just continue to tell people not to use
    // Linux distro builds. On frozen aka non-distro builds we set
    // PyPreConfig.utf8_mode = 1 which supposedly sets this to utf-8 anyway.
    Py_FileSystemDefaultEncoding = strdup(encoding);
#endif
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
icu_character_name(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    char name[512] = {0};
    int32_t sz = 0, alias = 0;
    UChar *buf;
    UErrorCode status = U_ZERO_ERROR;
    PyObject *palias = NULL, *result = NULL, *input = NULL;
    UChar32 code = 0;

    if (nargs < 1 || nargs > 2) { PyErr_SetString(PyExc_TypeError, "character_name takes 1 or 2 arguments"); return NULL; }
    input = args[0];
    palias = (nargs > 1) ? args[1] : NULL;

    if (palias != NULL && PyObject_IsTrue(palias)) alias = 1;
    buf = python_to_icu(input, &sz);
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
icu_character_name_from_code(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    char name[512] = {0};
    int32_t sz, alias = 0;
    UErrorCode status = U_ZERO_ERROR;
    PyObject *palias = NULL, *result = NULL;
    UChar32 code = 0;

    if (nargs < 1 || nargs > 2) { PyErr_SetString(PyExc_TypeError, "character_name_from_code takes 1 or 2 arguments"); return NULL; }
    unsigned long code_ul = PyLong_AsUnsignedLong(args[0]);
    if (PyErr_Occurred()) return NULL;
    if (code_ul > 0x10FFFF) { PyErr_SetString(PyExc_ValueError, "code point out of range(0x110000)"); return NULL; }
    code = (UChar32)code_ul;
    palias = (nargs > 1) ? args[1] : NULL;

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
icu_chr(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    UErrorCode status = U_ZERO_ERROR;
    UChar32 code = 0;
    UChar buf[5] = {0};
    int32_t sz = 0;

    if (nargs != 1) { PyErr_SetString(PyExc_TypeError, "chr takes exactly 1 argument"); return NULL; }
    unsigned long code_ul = PyLong_AsUnsignedLong(args[0]);
    if (PyErr_Occurred()) return NULL;
    if (code_ul > 0x10FFFF) { PyErr_SetString(PyExc_ValueError, "arg not in range(0x110000)"); return NULL; }
    code = (UChar32)code_ul;

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

    input_buf = python_to_icu32(input, &sz);
    if (input_buf == NULL) goto end;
    ans = PyTuple_New(sz);
    if (ans == NULL) goto end;
    for (i = 0; i < sz; i++) {
        temp = PyLong_FromLong((long)input_buf[i]);
        if (temp == NULL) { Py_DECREF(ans); ans = NULL; PyErr_NoMemory(); goto end; }
        PyTuple_SET_ITEM(ans, i, temp);
    }
end:
    if (input_buf != NULL) free(input_buf);
    return ans;

} // }}}

// normalize {{{
typedef enum { NFC, NFKC, NFD, NFKD } NORM_MODES;

static PyObject *
icu_normalize(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    UErrorCode status = U_ZERO_ERROR;
    int32_t sz = 0, cap = 0, rsz = 0;
    NORM_MODES mode;
    UChar *dest = NULL, *source = NULL;
    PyObject *ret = NULL, *src = NULL;

    if (nargs != 2) { PyErr_SetString(PyExc_TypeError, "normalize takes exactly 2 arguments"); return NULL; }
    int mode_int = (int)PyLong_AsLong(args[0]);
    if (PyErr_Occurred()) return NULL;
    mode = (NORM_MODES)mode_int;
    src = args[1];
    const UNormalizer2 *n = NULL;
    switch (mode) {
        case NFC:
            n = unorm2_getNFCInstance(&status);
            break;
        case NFKC:
            n = unorm2_getNFKCInstance(&status);
            break;
        case NFD:
            n = unorm2_getNFDInstance(&status);
            break;
        case NFKD:
            n = unorm2_getNFKDInstance(&status);
            break;
    }
    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        goto end;
    }

    source = python_to_icu(src, &sz);
    if (source == NULL) goto end;
    cap = 2 * sz;
    dest = (UChar*) calloc(cap, sizeof(UChar));
    if (dest == NULL) { PyErr_NoMemory(); goto end; }


    while (1) {
        rsz = unorm2_normalize(n, source, sz, dest, cap, &status);
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

    icu = python_to_icu(src, &sz);
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

    icu = python_to_icu(src, &sz);
    if (icu == NULL) return NULL;
    sz = u_countChar32(icu, sz);
    free(icu);
    return Py_BuildValue("l", (long)sz);
} // }}}

// utf16_length {{{
static PyObject *
icu_utf16_length(PyObject *self, PyObject *src) {
    Py_ssize_t sz = 0;
    Py_ssize_t unit_length, i;
    Py_UCS4 *data = NULL;

    if(PyUnicode_READY(src) != 0) { return NULL; }

    unit_length = sz = PyUnicode_GET_LENGTH(src);
    // UCS8 or UCS16? length==utf16 length already. UCS32? count big code points.
    if(PyUnicode_KIND(src) == PyUnicode_4BYTE_KIND) {
        data = PyUnicode_4BYTE_DATA(src);
        for(i = 0; i < unit_length; i++) {
            if(data[i] > 0xffff) {
                sz++;
            }
        }
    }

    return Py_BuildValue("n", sz);
} // }}}

// word_prefix_find {{{
// C implementation of word_prefix_find() from complete2.py.
// Converts python strings to ICU strings only once, then iterates over
// word positions and returns the first matching position or -1 on failure.
static PyObject *
icu_word_prefix_find(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    PyObject *collator_obj = NULL, *it_obj = NULL, *x_ = NULL, *prefix_ = NULL;
    icu_Collator *collator = NULL;
    icu_BreakIterator *it = NULL;
    UChar *x_icu = NULL, *prefix_icu = NULL;
    int32_t xsz = 0, prefix_sz = 0, pos, sz, utf16_start = 0, prev_cp_pos = 0;
    UErrorCode status = U_ZERO_ERROR;
    long ans = -1;
    BreakIterState state;

    if (nargs != 4) { PyErr_SetString(PyExc_TypeError, "word_prefix_find takes exactly 4 arguments"); return NULL; }
    collator_obj = args[0]; it_obj = args[1]; x_ = args[2]; prefix_ = args[3];
    if (!PyObject_TypeCheck(collator_obj, &icu_CollatorType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Collator");
        return NULL;
    }
    if (!PyObject_TypeCheck(it_obj, &icu_BreakIteratorType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a BreakIterator");
        return NULL;
    }
    collator = (icu_Collator *)collator_obj;
    it = (icu_BreakIterator *)it_obj;

    // Convert x to ICU and set it on the break iterator (equivalent to it.set_text(x))
    x_icu = python_to_icu(x_, &xsz);
    if (x_icu == NULL) return NULL;
    it->counter++;
    ubrk_setText(it->break_iterator, x_icu, xsz, &status);
    if (U_FAILURE(status)) {
        free(x_icu);
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        return NULL;
    }
    free(it->text); it->text = x_icu; it->text_len = xsz; x_icu = NULL;  // ownership transferred to it->text

    // Convert prefix to ICU once
    prefix_icu = python_to_icu(prefix_, &prefix_sz);
    if (prefix_icu == NULL) return NULL;

    // Iterate over word positions and find the first where x starts with prefix
    break_iter_state_init(it, &state);
    while (break_iter_state_next(it, &state, &pos, &sz)) {
        // pos is a codepoint offset; advance the UTF-16 cursor incrementally
        if (pos > prev_cp_pos) {
            U16_FWD_N(it->text, utf16_start, it->text_len, (uint32_t)(pos - prev_cp_pos));
            prev_cp_pos = pos;
        }
        if (utf16_start >= it->text_len) break;
        // Empty prefix matches at the first word position
        if (prefix_sz == 0) { ans = (long)pos; break; }
        // Check if x starting at utf16_start begins with prefix using the collator
        if (it->text_len - utf16_start >= prefix_sz &&
                ucol_equal(collator->collator, it->text + utf16_start, prefix_sz, prefix_icu, prefix_sz)) {
            ans = (long)pos;
            break;
        }
    }
    free(prefix_icu);
    return Py_BuildValue("l", ans);
} // }}}

// Module initialization {{{
static PyMethodDef icu_methods[] = {
    {"change_case", (PyCFunction)(void(*)(void))icu_change_case, METH_FASTCALL,
        "change_case(unicode object, which, locale) -> change case to one of UPPER_CASE, LOWER_CASE, TITLE_CASE"
    },

    {"swap_case", icu_swap_case, METH_O,
        "swap_case(unicode object) -> swaps the case using the simple, locale independent unicode algorithm"
    },

    {"set_default_encoding", icu_set_default_encoding, METH_NOARGS,
        "set_default_encoding(encoding) -> Set the default encoding for the python unicode implementation. In Py3, this operation is a no-op"
    },

    {"set_filesystem_encoding", (PyCFunction)(void(*)(void))icu_set_filesystem_encoding, METH_FASTCALL,
        "set_filesystem_encoding(encoding) -> Set the filesystem encoding for python."
    },

    {"get_available_transliterators", icu_get_available_transliterators, METH_NOARGS,
        "get_available_transliterators() -> Return list of available transliterators. This list is rather limited on OS X."
    },

    {"character_name", (PyCFunction)(void(*)(void))icu_character_name, METH_FASTCALL,
     "character_name(char, alias=False) -> Return name for the first character in char, which must be a unicode string."
    },

    {"character_name_from_code", (PyCFunction)(void(*)(void))icu_character_name_from_code, METH_FASTCALL,
     "character_name_from_code(code, alias=False) -> Return the name for the specified unicode code point"
    },

    {"chr", (PyCFunction)(void(*)(void))icu_chr, METH_FASTCALL,
     "chr(code) -> Return a python unicode string corresponding to the specified character code. The string can have length 1 or 2 (for non BMP codes on narrow python builds)."
    },

    {"ord_string", icu_ord_string, METH_O,
     "ord_string(code) -> Convert a python unicode string to a tuple of unicode codepoints."
    },

    {"normalize", (PyCFunction)(void(*)(void))icu_normalize, METH_FASTCALL,
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

    {"word_prefix_find", (PyCFunction)(void(*)(void))icu_word_prefix_find, METH_FASTCALL,
     "word_prefix_find(collator, break_iterator, string, prefix) -> Return the codepoint offset of the first word in string that starts with prefix according to collator, or -1 if none."
    },

    {NULL}  /* Sentinel */
};

static int
exec_module(PyObject *mod) {
    UVersionInfo ver, uver;
    UErrorCode status = U_ZERO_ERROR;
    char version[U_MAX_VERSION_STRING_LENGTH+1] = {0}, uversion[U_MAX_VERSION_STRING_LENGTH+5] = {0};

    u_init(&status);
    if (U_FAILURE(status)) {
        PyErr_Format(PyExc_RuntimeError, "u_init() failed with error: %s", u_errorName(status));
        return -1;
    }
    u_getVersion(ver);
    u_versionToString(ver, version);
    u_getUnicodeVersion(uver);
    u_versionToString(uver, uversion);

    if (PyType_Ready(&icu_CollatorType) < 0)
        return -1;
    if (PyType_Ready(&icu_BreakIteratorType) < 0)
        return -1;
    if (PyType_Ready(&icu_BreakIteratorIterType) < 0)
        return -1;
    if (PyType_Ready(&icu_TransliteratorType) < 0)
        return -1;

    Py_INCREF(&icu_CollatorType); Py_INCREF(&icu_BreakIteratorType); Py_INCREF(&icu_TransliteratorType);
    PyModule_AddObject(mod, "Collator", (PyObject *)&icu_CollatorType);
    PyModule_AddObject(mod, "BreakIterator", (PyObject *)&icu_BreakIteratorType);
    PyModule_AddObject(mod, "Transliterator", (PyObject *)&icu_TransliteratorType);
    // uint8_t must be the same size as char
    PyModule_AddIntConstant(mod, "ok", (U_SUCCESS(status) && sizeof(uint8_t) == sizeof(char)) ? 1 : 0);
    PyModule_AddStringConstant(mod, "icu_version", version);
    PyModule_AddStringConstant(mod, "unicode_version", uversion);

#define ADDUCONST(x) PyModule_AddIntConstant(mod, #x, x)
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
    ADDUCONST(UCOL_FRENCH_COLLATION);
    ADDUCONST(UCOL_ALTERNATE_HANDLING);
    ADDUCONST(UCOL_CASE_FIRST);
    ADDUCONST(UCOL_CASE_LEVEL);
    ADDUCONST(UCOL_NORMALIZATION_MODE);
    ADDUCONST(UCOL_DECOMPOSITION_MODE);
    ADDUCONST(UCOL_STRENGTH);
    ADDUCONST(UCOL_NUMERIC_COLLATION);
    ADDUCONST(UCOL_REORDER_CODE_SPACE);
    ADDUCONST(UCOL_REORDER_CODE_PUNCTUATION);
    ADDUCONST(UCOL_REORDER_CODE_SYMBOL);
    ADDUCONST(UCOL_REORDER_CODE_CURRENCY);
    ADDUCONST(UCOL_REORDER_CODE_DEFAULT);

    ADDUCONST(NFD);
    ADDUCONST(NFKD);
    ADDUCONST(NFC);
    ADDUCONST(NFKC);

    ADDUCONST(UPPER_CASE);
    ADDUCONST(LOWER_CASE);
    ADDUCONST(TITLE_CASE);

    ADDUCONST(UBRK_CHARACTER);
    ADDUCONST(UBRK_WORD);
    ADDUCONST(UBRK_LINE);
    ADDUCONST(UBRK_SENTENCE);

	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "icu",
    .m_doc      =  "Wrapper for the ICU internationalization library",
    .m_methods  = icu_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_icu(void) { return PyModuleDef_Init(&module_def); }

// }}}
