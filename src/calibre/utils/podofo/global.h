/*
 * global.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#pragma once

#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

namespace pdf {

// Module exception types
extern PyObject *Error;

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
    PdfMemDocument *doc;

} PDFDoc;

typedef struct {
    PyObject_HEAD
    PdfMemDocument *doc;
    PdfOutlineItem *item;
} PDFOutlineItem;

extern PyTypeObject PDFDocType;
extern PyTypeObject PDFOutlineItemType;
extern PyObject *Error;

// Utilities
extern void podofo_set_exception(const PdfError &err);
extern PyObject * podofo_convert_pdfstring(const PdfString &s);
extern PdfString * podofo_convert_pystring(PyObject *py);
extern PdfString * podofo_convert_pystring_single_byte(PyObject *py);

}

