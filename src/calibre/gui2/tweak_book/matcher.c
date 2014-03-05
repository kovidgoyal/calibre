/*
 * matcher.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <float.h>
#include <stdlib.h>
#include <search.h>
#include <unicode/uchar.h>
#include <unicode/ustring.h>
#include <unicode/utf16.h>

#ifdef _MSC_VER
// inline does not work with the visual studio C compiler
#define inline
#define qsort qsort_s
#else
#define qsort qsort_r
#endif


typedef unsigned char bool;
#define TRUE 1
#define FALSE 0
#define MIN(x, y) ((x < y) ? x : y)
#define MAX(x, y) ((x > y) ? x : y)
#define nullfree(x) if(x != NULL) free(x); x = NULL;

// Algorithm to sort items by subsequence score {{{
typedef struct {
    UChar *haystack;
    int32_t haystack_len;
    UChar *needle;
    int32_t needle_len;
    double max_score_per_char;
    double **memo;
    UChar *level1;
    UChar *level2;
    UChar *level3;
} MatchInfo;

typedef struct {
    UChar *item;
    char *sort_key;
    uint32_t sort_key_len;
    PyObject *py_item;
    double score;
} Match;

static double recursive_match(MatchInfo *m, int32_t haystack_idx, int32_t needle_idx, int32_t last_idx, double score) {
    double seen_score = 0.0, memoized = DBL_MAX, score_for_char, factor, sub_score; 
    int32_t i = 0, j = 0, distance, curri;
    UChar32 c, d, last;
    bool found;

    // do we have a memoized result we can return?
    memoized = m->memo[needle_idx][haystack_idx];
    if (memoized != DBL_MAX)
        return memoized;

    // bail early if not enough room (left) in haystack for (rest of) needle
    if (m->haystack_len - haystack_idx < m->needle_len - needle_idx) {
        score = 0.0;
        goto memoize;
    }
    for (i = needle_idx; i < m->needle_len; ) {
        curri = i;
        U16_NEXT(m->needle, i, m->needle_len, c);  // i now points to the next codepoint
        found = FALSE;

        // similar to above, we'll stop iterating when we know we're too close
        // to the end of the string to possibly match
        for (j = haystack_idx; j <= m->haystack_len - (m->needle_len - curri); ) {
            haystack_idx = j;
            U16_NEXT(m->haystack, j, m->haystack_len, d);  // j now points to the next codepoint

            if (u_foldCase(c, U_FOLD_CASE_DEFAULT) == u_foldCase(d, U_FOLD_CASE_DEFAULT)) {
                found = TRUE;

                // calculate score
                score_for_char = m->max_score_per_char;
                distance = haystack_idx - last_idx;

                if (distance > 1) {
                    factor = 1.0;
                    U16_GET(m->haystack, haystack_idx - 1, haystack_idx - 1, m->haystack_len, last);
                    if (u_strchr32(m->level1, last))
                        factor = 0.9;
                    else if (u_strchr32(m->level2, last))
                        factor = 0.8;
                    else if (u_isULowercase(last) && u_isUUppercase(d))
                        factor = 0.8;  // CamelCase
                    else if (u_strchr32(m->level3, last))
                        factor = 0.7;
                    else
                        // if no "special" chars behind char, factor diminishes
                        // as distance from last matched char increases
                        factor = (1.0 / distance) * 0.75;
                    score_for_char *= factor;
                }

                if (j < m->haystack_len) {
                    // bump cursor one char to the right and
                    // use recursion to try and find a better match
                    sub_score = recursive_match(m, j, curri, last_idx, score);
                    if (sub_score > seen_score)
                        seen_score = sub_score;
                }
                score += score_for_char;
                last_idx = haystack_idx + 1;
                break;
            }
        } // for(j)

        if (!found) {
            score = 0.0;
            goto memoize;
        }
    }

    score = score > seen_score ? score : seen_score;

memoize:
    m->memo[needle_idx][haystack_idx] = score;
    return score;
}

static double** alloc_memo(size_t rows, size_t cols) {
    double **array, *data; /* Declare this first so we can use it with sizeof. */
    size_t i;
    const size_t row_pointers_bytes = rows * sizeof(*array);
    const size_t row_elements_bytes = cols * sizeof(**array);
    array = malloc(row_pointers_bytes + rows * row_elements_bytes);
    if (array != NULL) {
        data = (double*)(array + rows);
        for(i = 0; i < rows; i++) array[i] = data + i * cols;
    }
    return array;
}

static bool match(UChar **items, int32_t *item_lengths, uint32_t item_count, UChar *needle, int32_t needle_len, Match *match_results, UChar *level1, UChar *level2, UChar *level3) {
    uint32_t i = 0, maxhl = 0; 
    int32_t r = 0, c = 0;
    MatchInfo *matches = NULL;
    bool ok = FALSE;
    double **memo = NULL;

    if (needle_len == 0) {
        for (i = 0; i < item_count; i++) match_results[i].score = 0.0;
        ok = TRUE;
        goto end;
    }

    matches = (MatchInfo*)calloc(item_count, sizeof(MatchInfo));
    if (matches == NULL) goto end;

    for (i = 0; i < item_count; i++) {
        matches[i].haystack = items[i];
        matches[i].haystack_len = item_lengths[i];
        matches[i].needle = needle;
        matches[i].needle_len = needle_len;
        matches[i].max_score_per_char = (1.0 / matches[i].haystack_len + 1.0 / needle_len) / 2.0;
        matches[i].level1 = level1;
        matches[i].level2 = level2;
        matches[i].level3 = level3;
        maxhl = MAX(maxhl, matches[i].haystack_len);
    }

    memo = alloc_memo(needle_len, maxhl);
    if (memo == NULL) {PyErr_NoMemory(); goto end;}

    for (i = 0; i < item_count; i++) {
        for (r = 0; r < needle_len; r++) {
            for (c = 0; c < maxhl; c++) memo[r][c] = DBL_MAX;
        }
        matches[i].memo = memo;
        match_results[i].score = recursive_match(&matches[i], 0, 0, 0, 0.0);
    }

    ok = TRUE;
end:
    nullfree(matches);
    nullfree(memo);
    return ok;
}

int cmp_score(const void *a, const void *b, void *arg)
{
    Match a_match = *(Match *)a;
    Match b_match = *(Match *)b;

    if (a_match.score > b_match.score)
        return -1; // a scores higher, a should appear sooner
    else if (a_match.score < b_match.score)
        return 1; // b scores higher, a should appear later
    else
        return strncmp(a_match.sort_key, b_match.sort_key, MIN(a_match.sort_key_len, b_match.sort_key_len));
}
// }}}

// Matcher object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    UChar **items;
    char **sort_items;
    uint32_t item_count;
    int32_t *item_lengths;
    int32_t *sort_item_lengths;
    PyObject *py_items;
    PyObject *py_sort_keys;
    UChar *level1;
    UChar *level2;
    UChar *level3;

} Matcher;
// Matcher.__init__() {{{

static void free_matcher(Matcher *self) {
    uint32_t i = 0;
    if (self->items != NULL) {
        for (i = 0; i < self->item_count; i++) { nullfree(self->items[i]); }
    }
    nullfree(self->items); nullfree(self->sort_items); nullfree(self->item_lengths); nullfree(self->sort_item_lengths); Py_XDECREF(self->py_items); Py_XDECREF(self->py_sort_keys); 
    nullfree(self->level1); nullfree(self->level2); nullfree(self->level3);
}
static void
Matcher_dealloc(Matcher* self)
{
    free_matcher(self);
    self->ob_type->tp_free((PyObject*)self);
}

#define alloc_uchar(x) (x * 3 + 1)
static int
Matcher_init(Matcher *self, PyObject *args, PyObject *kwds)
{
    PyObject *items = NULL, *sort_keys = NULL, *p = NULL;
    char *utf8 = NULL, *level1 = NULL, *level2 = NULL, *level3 = NULL;
    int32_t i = 0;
    Py_ssize_t cap = 0, l1s, l2s, l3s;
    UErrorCode status = U_ZERO_ERROR;

    if (!PyArg_ParseTuple(args, "OOs#s#s#", &items, &sort_keys, &level1, &l1s, &level2, &l2s, &level3, &l3s)) return -1;
    self->py_items = PySequence_Fast(items,  "Must pass in two sequence objects");
    self->py_sort_keys = PySequence_Fast(sort_keys, "Must pass in two sequence objects");
    if (self->py_items == NULL || self->py_sort_keys == NULL) goto end;
    self->item_count = (uint32_t)PySequence_Size(items);
    if (self->item_count != (uint32_t)PySequence_Size(sort_keys)) { PyErr_SetString(PyExc_TypeError, "The sequences must have the same length."); }

    self->items = (UChar**)calloc(self->item_count, sizeof(UChar*));
    self->sort_items = (char**)calloc(self->item_count, sizeof(char*));
    self->item_lengths = (int32_t*)calloc(self->item_count, sizeof(uint32_t));
    self->sort_item_lengths = (int32_t*)calloc(self->item_count, sizeof(uint32_t));
    self->level1 = (UChar*)calloc(alloc_uchar(l1s), sizeof(UChar));
    self->level2 = (UChar*)calloc(alloc_uchar(l2s), sizeof(UChar));
    self->level3 = (UChar*)calloc(alloc_uchar(l3s), sizeof(UChar));

    if (self->items == NULL || self->sort_items == NULL || self->item_lengths == NULL || self->sort_item_lengths == NULL || self->level1 == NULL || self->level2 == NULL || self->level3 == NULL) {
        PyErr_NoMemory(); goto end; 
    }
    u_strFromUTF8Lenient(self->level1, alloc_uchar(l1s), &i, level1, (int32_t)l1s, &status);
    u_strFromUTF8Lenient(self->level2, alloc_uchar(l2s), &i, level2, (int32_t)l2s, &status);
    u_strFromUTF8Lenient(self->level3, alloc_uchar(l3s), &i, level3, (int32_t)l3s, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "Failed to convert bytes for level string from UTF-8 to UTF-16"); goto end; }

    for (i = 0; i < self->item_count; i++) {
        p = PySequence_Fast_GET_ITEM(self->py_items, i);
        utf8 = PyBytes_AsString(p);
        if (utf8 == NULL) goto end;
        cap = PyBytes_GET_SIZE(p); 
        self->items[i] = (UChar*)calloc(alloc_uchar(cap), sizeof(UChar));
        if (self->items[i] == NULL) { PyErr_NoMemory(); goto end; }
        u_strFromUTF8Lenient(self->items[i], alloc_uchar(cap), &(self->item_lengths[i]), utf8, cap, &status);
        if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "Failed to convert bytes from UTF-8 to UTF-16"); goto end; }

        p = PySequence_Fast_GET_ITEM(self->py_sort_keys, i);
        self->sort_items[i] = PyBytes_AsString(p);
        if (self->sort_items[i] == NULL) goto end;
        self->sort_item_lengths[i] = (uint32_t) PyBytes_GET_SIZE(p);
    }

end:
    if (PyErr_Occurred()) { free_matcher(self); }
    return (PyErr_Occurred()) ? -1 : 0;
}
// Matcher.__init__() }}}
 
// Matcher.get_matches {{{
static PyObject *
Matcher_get_matches(Matcher *self, PyObject *args) {
    char *cneedle = NULL;
    int32_t qsize = 0;
    Match *matches = NULL;
    bool ok = FALSE;
    uint32_t i = 0;
    PyObject *items = NULL;
    UErrorCode status = U_ZERO_ERROR;
    UChar *needle = NULL;

    if (!PyArg_ParseTuple(args, "s#", &cneedle, &qsize)) return NULL;

    needle = (UChar*)calloc(alloc_uchar(qsize), sizeof(UChar));
    if (needle == NULL) return PyErr_NoMemory();
    u_strFromUTF8Lenient(needle, alloc_uchar(qsize), &qsize, cneedle, qsize, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, "Failed to convert bytes from UTF-8 to UTF-16"); goto end; }

    items = PyTuple_New(self->item_count);
    matches = (Match*)calloc(self->item_count, sizeof(Match));
    if (items == NULL || matches == NULL) {PyErr_NoMemory(); goto end;}
    for (i = 0; i < self->item_count; i++) {
        matches[i].item = self->items[i];
        matches[i].sort_key = self->sort_items[i];
        matches[i].sort_key_len = self->sort_item_lengths[i];
        matches[i].py_item = PySequence_Fast_GET_ITEM(self->py_items, (Py_ssize_t)i);
    }

    Py_BEGIN_ALLOW_THREADS;
    ok = match(self->items, self->item_lengths, self->item_count, needle, (uint32_t)qsize, matches, self->level1, self->level2, self->level3);
    if (ok) qsort(matches, self->item_count, sizeof(Match), cmp_score, NULL);
    Py_END_ALLOW_THREADS;

    if (ok) {
        for (i = 0; i < self->item_count; i++) {
            PyTuple_SET_ITEM(items, (Py_ssize_t)i, matches[i].py_item);
            Py_INCREF(matches[i].py_item);
        }
    } else { PyErr_NoMemory(); goto end; }

end:
    nullfree(needle);
    nullfree(matches);
    if (PyErr_Occurred()) { Py_XDECREF(items); return NULL; }
    return items;
} // }}}

static PyMethodDef Matcher_methods[] = {
    {"get_matches", (PyCFunction)Matcher_get_matches, METH_VARARGS,
     "get_matches(query) -> Return the sorted list of matches for query which must be a UTF-8 encoded string."
    },

    {NULL}  /* Sentinel */
};


// }}}

static PyTypeObject MatcherType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "matcher.Matcher",            /*tp_name*/
    sizeof(Matcher),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Matcher_dealloc, /*tp_dealloc*/
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
    "Matcher",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    Matcher_methods,             /* tp_methods */
    0,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Matcher_init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

static PyMethodDef matcher_methods[] = {
    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initmatcher(void) {
    PyObject *m;
    MatcherType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&MatcherType) < 0)
        return;
    m = Py_InitModule3("matcher", matcher_methods, "Find subsequence matches");
    if (m == NULL) return;

    Py_INCREF(&MatcherType);
    PyModule_AddObject(m, "Matcher", (PyObject *)&MatcherType);

}



