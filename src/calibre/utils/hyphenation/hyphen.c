/*
 * hyphen.c
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <hyphen.h>

#ifdef _MSC_VER
#define fdopen _fdopen
#endif

#define CAPSULE_NAME "hyphen-dict"

void
free_dict(PyObject *capsule) {
	HyphenDict *dict = PyCapsule_GetPointer(capsule, CAPSULE_NAME);
	if (dict) hnj_hyphen_free(dict);
}


static PyObject*
load_dictionary(PyObject *self, PyObject *args) {
	int fd;
	if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;
	FILE *file = fdopen(fd, "rb");
	if (!file) return PyErr_SetFromErrno(PyExc_OSError);
	HyphenDict *dict = hnj_hyphen_load_file(file);
	if (!dict) {
		fclose(file);
		PyErr_SetString(PyExc_ValueError, "Failed to load hyphen dictionary from the specified file");
		return NULL;
	}
	PyObject *ans = PyCapsule_New(dict, CAPSULE_NAME, free_dict);
	if (!ans) fclose(file);
	return ans;
}

HyphenDict*
get_dict_from_args(PyObject *args) {
	if (PyTuple_GET_SIZE(args) < 1) { PyErr_SetString(PyExc_TypeError, "dictionary argument required"); return NULL; }
	return PyCapsule_GetPointer(PyTuple_GET_ITEM(args, 0), CAPSULE_NAME);
}


static PyObject*
simple_hyphenate(PyObject *self, PyObject *args) {
    char hyphenated_word[2*MAX_CHARS] = {0}, hyphens[MAX_CHARS * 3] = {0}, *word_str;
	PyObject *dict_obj;
	char **rep = NULL; int *pos = NULL, *cut = NULL;

	HyphenDict *dict = get_dict_from_args(args);
	if (!dict) return NULL;
    if (!PyArg_ParseTuple(args, "Oes", &dict_obj, &dict->cset, &word_str)) return NULL;
    size_t wd_size = strlen(word_str);

    if (wd_size >= MAX_CHARS) {
        PyErr_Format(PyExc_ValueError, "Word to be hyphenated (%s) may have at most %u characters, has %zu.", word_str, MAX_CHARS-1, wd_size);
        PyMem_Free(word_str);
        return NULL;
    }

    if (hnj_hyphen_hyphenate2(dict, word_str, (int)wd_size, hyphens, hyphenated_word, &rep, &pos, &cut)) {
        PyErr_Format(PyExc_ValueError, "Cannot hyphenate word: %s", word_str);
	}
	PyMem_Free(word_str);
	if (rep) {
        PyErr_Format(PyExc_ValueError, "Cannot hyphenate word as it requires replacements: %s", word_str);
		for (size_t i = 0; i < wd_size; i++) {
			if (rep[i]) free(rep[i]);
		}
		free(rep);
	}
	free(pos); free(cut);
	if (PyErr_Occurred()) return NULL;

	return PyUnicode_Decode(hyphenated_word, strlen(hyphenated_word), dict->cset, "replace");
}


// Boilerplate {{{
static char doc[] = "Wrapper for the hyphen C library";
static PyMethodDef methods[] = {
    {"load_dictionary", (PyCFunction)load_dictionary, METH_VARARGS,
     "load_dictionary(fd) -> Load the specified hyphenation dictionary from the file descriptor which must have been opened for binary reading"
    },
    {"simple_hyphenate", (PyCFunction)simple_hyphenate, METH_VARARGS,
     "simple_hyphenate(dict, unicode_word) -> Return hyphenated word or raise ValueError"
    },

    {NULL}  /* Sentinel */
};

static int
exec_module(PyObject *module) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "hyphen",
    .m_doc      = doc,
    .m_methods  = methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_hyphen(void) { return PyModuleDef_Init(&module_def); }
// }}}
