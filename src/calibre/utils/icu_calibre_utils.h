/*
 * icu.h
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <unicode/uversion.h>
#include <unicode/utypes.h>
#include <unicode/uclean.h>
#include <unicode/utf16.h>
#include <unicode/ucol.h>
#include <unicode/ucoleitr.h>
#include <unicode/ustring.h>
#include <unicode/usearch.h>
#include <unicode/utrans.h>
#include <unicode/unorm2.h>
#include <unicode/ubrk.h>

#if PY_VERSION_HEX < 0x03030000
#error Not implemented for python < 3.3
#endif

static UChar* python_to_icu(PyObject *obj, int32_t *osz) {
    UChar *ans = NULL;
    Py_ssize_t sz = 0;
    UErrorCode status = U_ZERO_ERROR;
    Py_UCS2 *data;
    int i;

    if (!PyUnicode_CheckExact(obj)) {
        PyErr_SetString(PyExc_TypeError, "Not a unicode string");
        return NULL;
    }
    if(PyUnicode_READY(obj) == -1) {
        return NULL;
    }
    sz = PyUnicode_GET_LENGTH(obj);


    switch(PyUnicode_KIND(obj)) {
    case PyUnicode_1BYTE_KIND: {
        Py_ssize_t data_sz;
        const char *utf8_data = PyUnicode_AsUTF8AndSize(obj, &data_sz);
        if (!utf8_data) return NULL;
        size_t buf_sz = (sz > data_sz ? sz : data_sz) + 1;
        ans = (UChar*) malloc(buf_sz * sizeof(UChar));
        if (ans == NULL) { PyErr_NoMemory(); return NULL; }
        u_strFromUTF8Lenient(ans, buf_sz, (int32_t*) osz, utf8_data, (int32_t)data_sz, &status);
        // add null terminator
        ans[buf_sz-1] = 0;
        break;
    }
    case PyUnicode_2BYTE_KIND:
        ans = (UChar*) malloc((sz+1) * sizeof(UChar));
        data = PyUnicode_2BYTE_DATA(obj);
        // if UChar is more than 2 bytes, we need to copy manually.
        if(sizeof(UChar) != sizeof(Py_UCS2)) {
            for(i = 0; i < sz; i++) {
                ans[i] = data[i];
            }
        } else {
            memcpy(ans, data, sz * sizeof(UChar));
        }
        // add null terminator
        ans[sz] = 0;
        if (osz != NULL) *osz = sz;
        break;
    case PyUnicode_4BYTE_KIND:
        // +1 for null terminator
        ans = (UChar*) malloc(2 * (sz+1) * sizeof(UChar));
        if (ans == NULL) {
            PyErr_NoMemory();
            return NULL;
        }
        u_strFromUTF32(
            ans, 2 * (sz+1),
            (int32_t*) osz,
            (UChar32*) PyUnicode_4BYTE_DATA(obj),
            (int32_t) sz,
            &status);
        break;
    }

    if (U_FAILURE(status)) {
        PyErr_SetString(PyExc_ValueError, u_errorName(status));
        free(ans);
        ans = NULL;
        return NULL;
    }

    return ans;
}

#ifndef NO_PYTHON_TO_ICU32
static UChar32* python_to_icu32(PyObject *obj, int32_t *osz) {
    UChar32 *ans = NULL;
    Py_ssize_t sz = 0;
    int i;

    if (!PyUnicode_CheckExact(obj)) {
        PyErr_SetString(PyExc_TypeError, "Not a unicode string");
        return NULL;
    }
    if(PyUnicode_READY(obj) == -1) {
        return NULL;
    }
    sz = PyUnicode_GET_LENGTH(obj);
    ans = (UChar32*) malloc((sz+1) * sizeof(UChar32));
    if (ans == NULL) { PyErr_NoMemory(); return NULL; }
	int kind;
	if ((kind = PyUnicode_KIND(obj)) == PyUnicode_4BYTE_KIND) {
		memcpy(ans, PyUnicode_4BYTE_DATA(obj), sz * 4);
	} else {
		for(i = 0; i < sz; i++) {
			// Work around strict aliasing rules by manually memcpy.
			// This should get optimized.
			ans[i] = PyUnicode_READ(kind, PyUnicode_DATA(obj), i);
		}
	}
    ans[sz] = 0;

    if (osz != NULL) *osz = sz;

    return ans;
}
#endif

#ifndef NO_ICU_TO_PYTHON
static PyObject* icu_to_python(UChar *src, int32_t sz) {
    return PyUnicode_DecodeUTF16((char*) src, sz * sizeof(UChar), "replace", NULL);
}
#endif
