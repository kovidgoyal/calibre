/*
 * hunspell.c
 * Python wrapper for the hunspell library.
 * Copyright (C) 2013 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN 1
#include <Python.h>
#include <new>
#include <string>
#include <hunspell.hxx>

typedef struct {
	PyObject_HEAD
    Hunspell *handle;
    char *encoding;
} Dictionary;

static PyObject *HunspellError = NULL;

static int
init_type(Dictionary *self, PyObject *args, PyObject *kwds) {
	char *dic = NULL, *aff = NULL;

    self->handle = NULL;
    self->encoding = NULL;

	if (!PyArg_ParseTuple(args, "ss", &dic, &aff)) return 1;

    try {
        self->handle = new (std::nothrow) Hunspell(aff, dic);
    } catch (const std::exception &ex) {
        PyErr_SetString(HunspellError, ex.what());
        return 1;
    } catch (const std::string &ex) {
        PyErr_SetString(HunspellError, ex.c_str());
        return 1;
    } catch (...) {
        PyErr_SetString(HunspellError, "Failed to create dictionary, unknown error");
        return 1;
    }
    if (self->handle == NULL) { PyErr_NoMemory(); return 1; }
    self->encoding = self->handle->get_dic_encoding();
    if (self->encoding == NULL) { delete self->handle; self->handle = NULL; PyErr_SetString(HunspellError, "Failed to get dictionary encoding"); return 1; }
	return 0;
}

static void
dealloc(Dictionary *self) {
    if (self->handle != NULL) delete self->handle;
    /* We do not free encoding, since it is managed by hunspell */
    self->encoding = NULL; self->handle = NULL;
	Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
recognized(Dictionary *self, PyObject *args) {
	char *w = NULL;
	if (!PyArg_ParseTuple(args, "es", self->encoding, &w)) return NULL;
    std::string word(w);
    PyMem_Free(w);

    if (!self->handle->spell(word)) { Py_RETURN_FALSE;}
    Py_RETURN_TRUE;
}

static PyObject *
suggest(Dictionary *self, PyObject *args) {
	char *w = NULL;
	PyObject *ans, *temp;

	if (!PyArg_ParseTuple(args, "es", self->encoding, &w)) return NULL;
    const std::string word(w);
    PyMem_Free(w);

    const std::vector<std::string>& word_list = self->handle->suggest(word);
	ans = PyTuple_New(word_list.size());
    if (ans == NULL) PyErr_NoMemory();
    Py_ssize_t i = 0;
    for(auto const& s: word_list) {
        temp = PyUnicode_Decode(s.c_str(), s.size(), self->encoding, "strict");
        if (temp == NULL) { Py_DECREF(ans); ans = NULL; break; }
        PyTuple_SET_ITEM(ans, i++, temp);
    }
	return ans;
}

static PyObject *
add(Dictionary *self, PyObject *args) {
	char *word = NULL;

	if (!PyArg_ParseTuple(args, "es", self->encoding, &word)) return NULL;
	if (self->handle->add(word) == 0) { PyMem_Free(word); Py_RETURN_TRUE; }
    PyMem_Free(word);
    Py_RETURN_FALSE;
}

static PyObject *
remove_word(Dictionary *self, PyObject *args) {
	char *word = NULL;

	if (!PyArg_ParseTuple(args, "es", self->encoding, &word)) return NULL;
	if (self->handle->remove(word) == 0) { PyMem_Free(word); Py_RETURN_TRUE; }
    PyMem_Free(word);
    Py_RETURN_FALSE;
}

static PyMethodDef HunSpell_methods[] = {
	{"recognized", (PyCFunction)recognized, METH_VARARGS,
	 "Checks the spelling of the given word. The word must be a unicode "
	 "object. If encoding of the word to the encoding of the dictionary fails, "
	 "a UnicodeEncodeError is raised. Returns False if the input word is not "
	 "recognized."},
	{"suggest", (PyCFunction)suggest, METH_VARARGS,
	 "Provide suggestions for the given word. The input word must be a unicode "
	 "object. If encoding of the word to the encoding of the dictionary fails, "
	 "a UnicodeEncodeError is raised. Returns the list of suggested words as "
	 "unicode objects."},
	{"add", (PyCFunction)add, METH_VARARGS,
	 "Adds the given word into the runtime dictionary"},
	{"remove", (PyCFunction)remove_word, METH_VARARGS,
	 "Removes the given word from the runtime dictionary"},
	{NULL}
};

static PyTypeObject DictionaryType = {
	PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "Dictionary",
    /* tp_basicsize      */ sizeof(Dictionary),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor) dealloc,
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
    /* tp_flags          */ Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    /* tp_doc            */ "Dictionary object",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ HunSpell_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ (initproc) init_type,
    /* tp_alloc          */ 0,
    /* tp_new            */ 0,
};

static int
exec_module(PyObject *mod) {
    HunspellError = PyErr_NewException((char*)"hunspell.HunspellError", NULL, NULL);
    if (HunspellError == NULL) return -1;
    PyModule_AddObject(mod, "HunspellError", HunspellError);

    // Fill in some slots in the type, and make it ready
    DictionaryType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&DictionaryType) < 0) return -1;
    // Add the type to the module.
    Py_INCREF(&DictionaryType);
    if (PyModule_AddObject(mod, "Dictionary", (PyObject *)&DictionaryType) != 0) return -1;

    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_hunspell(void) {
	module_def.m_name = "hunspell";
	module_def.m_slots = slots;
	return PyModuleDef_Init(&module_def);
}
