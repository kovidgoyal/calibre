/*
 * unicode_names.c
 * Copyright (C) 2018 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "names.h"

static inline void
add_matches(const word_trie *wt, char_type *codepoints, size_t *pos, const size_t sz) {
    size_t num = mark_groups[wt->match_offset];
    for (size_t i = wt->match_offset + 1; i < wt->match_offset + 1 + num && *pos < sz; i++, (*pos)++) {
        codepoints[*pos] = mark_to_cp[mark_groups[i]];
    }
}

static void
process_trie_node(const word_trie *wt, char_type *codepoints, size_t *pos, const size_t sz) {
    if (wt->match_offset) add_matches(wt, codepoints, pos, sz);
    size_t num_children = children_array[wt->children_offset];
    if (!num_children) return;
    for (size_t c = wt->children_offset + 1; c < wt->children_offset + 1 + num_children; c++) {
        if (*pos > sz) return;
        uint32_t x = children_array[c];
        process_trie_node(&all_trie_nodes[x >> 8], codepoints, pos, sz);
    }
}

static inline PyObject*
codepoints_for_word(const char *word, size_t len) {
    const word_trie *wt = all_trie_nodes;
    for (size_t i = 0; i < len; i++) {
        unsigned char ch = word[i];
        size_t num_children = children_array[wt->children_offset];
        if (!num_children) return PyFrozenSet_New(NULL);
        bool found = false;
        for (size_t c = wt->children_offset + 1; c < wt->children_offset + 1 + num_children; c++) {
            uint32_t x = children_array[c];
            if ((x & 0xff) == ch) {
                found = true;
                wt = &all_trie_nodes[x >> 8];
                break;
            }
        }
        if (!found) return PyFrozenSet_New(NULL);
    }
    static char_type codepoints[1024];
    size_t cpos = 0;
    process_trie_node(wt, codepoints, &cpos, arraysz(codepoints));
    PyObject *ans = PyFrozenSet_New(NULL); if (ans == NULL) return NULL;
    for (size_t i = 0; i < cpos; i++) {
        PyObject *t = PyLong_FromUnsignedLong(codepoints[i]); if (t == NULL) { Py_DECREF(ans); return NULL; }
        int ret = PySet_Add(ans, t); Py_DECREF(t); if (ret != 0) { Py_DECREF(ans); return NULL; }
    }
    return ans;
}

static PyObject*
cfw(PyObject *self UNUSED, PyObject *args) {
    const char *word;
    if (!PyArg_ParseTuple(args, "s", &word)) return NULL;
    return codepoints_for_word(word, strlen(word));
}

static PyObject*
nfc(PyObject *self UNUSED, PyObject *args) {
    unsigned int cp;
    if (!PyArg_ParseTuple(args, "I", &cp)) return NULL;
    const char *n = name_for_codepoint(cp);
    if (n == NULL) Py_RETURN_NONE;
    return PyUnicode_FromString(n);
}

static PyMethodDef unicode_names_methods[] = {
    {"codepoints_for_word", (PyCFunction)cfw, METH_VARARGS,
     "Return a set of integer codepoints for where each codepoint's name "
     "contains ``word``,"},
    {"name_for_codepoint", (PyCFunction)nfc, METH_VARARGS,
     "Returns the given codepoint's name"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static int
exec_module(PyObject *module) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "unicode_names",
    .m_doc      = "A library to assist with selecting special characters",
    .m_methods  = unicode_names_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_unicode_names(void) { return PyModuleDef_Init(&module_def); }
