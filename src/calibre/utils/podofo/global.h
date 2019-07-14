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
void podofo_set_exception(const PdfError &err);
PyObject * podofo_convert_pdfstring(const PdfString &s);
const PdfString podofo_convert_pystring(PyObject *py);
PyObject* write_doc(PdfMemDocument *doc, PyObject *f);

struct PyObjectDeleter {
    void operator()(PyObject *obj) {
        Py_XDECREF(obj);
    }
};
// unique_ptr that uses Py_XDECREF as the destructor function.
typedef std::unique_ptr<PyObject, PyObjectDeleter> pyunique_ptr;

template<typename T>
static inline bool
dictionary_has_key_name(const PdfDictionary &d, T key, const char *name) {
	const PdfObject *val = d.GetKey(key);
	if (val && val->IsName() && val->GetName().GetName() == name) return true;
	return false;
}

extern "C" {
PyObject* list_fonts(PDFDoc*, PyObject*);
PyObject* used_fonts_in_page_range(PDFDoc *self, PyObject *args);
PyObject* remove_fonts(PDFDoc *self, PyObject *args);
}
}
