/*
 * utils.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace pdf;

void pdf::podofo_set_exception(const PdfError &err) {
    const char *msg = PdfError::ErrorMessage(err.GetError());
    if (msg == NULL) msg = err.what();
    PyErr_SetString(Error, msg);
}

PyObject *
pdf::podofo_convert_pdfstring(const PdfString &s) {
    std::string raw = s.GetStringUtf8();
	return PyBytes_FromStringAndSize(raw.c_str(), raw.length());
}

PdfString *
pdf::podofo_convert_pystring(PyObject *py) {
    PyObject *u8 = PyUnicode_AsEncodedString(py, "UTF-8", "replace");
    if (u8 == NULL) { return NULL; }
    pdf_utf8 *s8 = reinterpret_cast<pdf_utf8 *>(PyBytes_AS_STRING(u8));
    PdfString *ans = new PdfString(s8);
    Py_DECREF(u8);
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}

PdfString *
pdf::podofo_convert_pystring_single_byte(PyObject *py) {
    PyObject *s = PyUnicode_AsEncodedString(py, "cp1252", "replace");
    if (s == NULL) { return NULL; }
    PdfString *ans = new PdfString(PyBytes_AS_STRING(s));
    Py_DECREF(s);
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}
