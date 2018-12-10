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

#if PY_VERSION_HEX < 0x03030000 && PY_VERSION_HEX > 0x03000000
#error Not implemented for python 3.0 to 3.2
#endif

#if PY_VERSION_HEX < 0x03000000
#define MIN(x, y) ((x)<(y)) ? (x) : (y)
#define IS_HIGH_SURROGATE(x) (0xd800 <= x && x <= 0xdbff)
#define IS_LOW_SURROGATE(x) (0xdc00 <= x && x <= 0xdfff)

// Roundtripping will need to be implemented differently for python 3.3+ where strings are stored with variable widths

#ifndef NO_PYTHON_TO_ICU
static UChar* python_to_icu(PyObject *obj, int32_t *osz) {
    UChar *ans = NULL;
    Py_ssize_t sz = 0;
#ifdef Py_UNICODE_WIDE
    UErrorCode status = U_ZERO_ERROR;
#endif

    if (!PyUnicode_CheckExact(obj)) {
        PyErr_SetString(PyExc_TypeError, "Not a unicode string");
        goto end;
    }
    sz = PyUnicode_GET_SIZE(obj);

#ifdef Py_UNICODE_WIDE
// wide build (UCS 4)
    ans = (UChar*) calloc(2*(sz+1), sizeof(UChar)); // There can be no more than 2 UChars per character + ensure null termination
    if (ans == NULL) { PyErr_NoMemory(); goto end; }
    u_strFromUTF32WithSub(ans, (int32_t)(2*(sz+1)), osz, (UChar32*)PyUnicode_AS_UNICODE(obj), (int32_t)sz, 0xfffd, NULL, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); free(ans); ans = NULL; goto end; }
#else
// narrow build (UTF-16)
    ans = (UChar*) malloc((sz + 1) * sizeof(UChar));
    if (ans == NULL) { PyErr_NoMemory(); goto end; }
    for (Py_ssize_t i = 0; i < sz; i++) {
        UChar ch = PyUnicode_AS_UNICODE(obj)[i];
        if (IS_HIGH_SURROGATE(ch)) {
            if (i >= sz - 1 || !IS_LOW_SURROGATE(PyUnicode_AS_UNICODE(obj)[i+1])) ans[i] = 0xfffd;
            else { ans[i] = ch; ans[i+1] = PyUnicode_AS_UNICODE(obj)[i+1]; i++; }
        } else if (IS_LOW_SURROGATE(ch)) {
            ans[i] = 0xfffd;
        } else ans[i] = ch;
    }
    ans[sz] = 0; // Ensure null termination
    if (osz != NULL) *osz = (int32_t)sz;
#endif
end:
    return ans;
}

#ifndef NO_PYTHON_TO_ICU32
static UChar32* python_to_icu32(PyObject *obj, int32_t *osz) {
    UChar32 *ans = NULL;
    Py_ssize_t sz = 0;
#ifndef Py_UNICODE_WIDE
    UErrorCode status = U_ZERO_ERROR;
#endif

    if (!PyUnicode_CheckExact(obj)) {
        PyErr_SetString(PyExc_TypeError, "Not a unicode string");
        goto end;
    }

    sz = PyUnicode_GET_SIZE(obj);  // number of UCS2 code-points in narrow build and UCS4 code-points in wide build
    ans = (UChar32*) calloc(sz+1, sizeof(UChar32));  // Ensure null termination
    if (ans == NULL) { PyErr_NoMemory(); goto end; }

#ifdef Py_UNICODE_WIDE
// wide build (UCS 4)
    memcpy(ans, PyUnicode_AS_DATA(obj), MIN((sizeof(UChar32)*(sz+1)),PyUnicode_GET_DATA_SIZE(obj)));
    if (osz != NULL) *osz = (int32_t)PyUnicode_GET_SIZE(obj);
#else
// narrow build (UTF-16)
    u_strToUTF32(ans, (int32_t)sz + 1, osz, (UChar*)PyUnicode_AS_UNICODE(obj), (int32_t)sz, &status);
    if (U_FAILURE(status)) { PyErr_SetString(PyExc_ValueError, u_errorName(status)); free(ans); ans = NULL; goto end; }
#endif
end:
    return ans;
}
#endif

#endif

#ifndef NO_ICU_TO_PYTHON
static PyObject* icu_to_python(UChar *src, int32_t sz) {
#ifdef Py_UNICODE_WIDE
    return PyUnicode_DecodeUTF16((char*)src, sz*sizeof(UChar), "strict", NULL);
#else
    return PyUnicode_FromUnicode((Py_UNICODE*)src, sz);
#endif
}
#endif

#else  // end PY2; start PY3.3+

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
    case PyUnicode_1BYTE_KIND:
        ans = (UChar*) malloc((sz+1) * sizeof(UChar));
        if (ans == NULL) {
            PyErr_NoMemory();
            return NULL;
        }
        u_strFromUTF8(
            ans, sz + 1,
            (int32_t*) osz,
            (char*) PyUnicode_1BYTE_DATA(obj),
            (int32_t) sz,
            &status);
        break;
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
    return PyUnicode_DecodeUTF16((char*) src, sz, NULL, NULL);
}
#endif

#endif  // end PY3.3+
