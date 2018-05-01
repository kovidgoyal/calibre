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

#if PY_VERSION_HEX >= 0x03030000
#error Not implemented for python >= 3.3
#endif

#define MIN(x, y) ((x)<(y)) ? (x) : (y)
#define IS_HIGH_SURROGATE(x) (0xd800 <= x && x <= 0xdbff)
#define IS_LOW_SURROGATE(x) (0xdc00 <= x && x <= 0xdfff)

// Roundtripping will need to be implemented differently for python 3.3+ where strings are stored with variable widths

#ifndef NO_PYTHON_TO_ICU
static UChar* python_to_icu(PyObject *obj, int32_t *osz, uint8_t do_check) {
    UChar *ans = NULL;
    Py_ssize_t sz = 0;
#ifdef Py_UNICODE_WIDE
    UErrorCode status = U_ZERO_ERROR;
#endif

    if (do_check && !PyUnicode_CheckExact(obj)) {
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
static UChar32* python_to_icu32(PyObject *obj, int32_t *osz, uint8_t do_check) {
    UChar32 *ans = NULL;
    Py_ssize_t sz = 0;
#ifndef Py_UNICODE_WIDE
    UErrorCode status = U_ZERO_ERROR;
#endif

    if (do_check && !PyUnicode_CheckExact(obj)) {
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
