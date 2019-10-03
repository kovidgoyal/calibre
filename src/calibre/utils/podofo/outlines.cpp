/*
 * outlines.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
using namespace pdf;


// create_outline() {{{
static PyObject *
create_outline(PDFDoc *self, PyObject *args) {
    PDFOutlineItem *ans;
    PyObject *title_buf;
    unsigned int pagenum;
    double left = 0, top = 0, zoom = 0;
    PdfPage *page;

    if (!PyArg_ParseTuple(args, "UI|ddd", &title_buf, &pagenum, &left, &top, &zoom)) return NULL;

    ans = PyObject_New(PDFOutlineItem, &PDFOutlineItemType);
    if (ans == NULL) goto error;

    try {
        PdfString title = podofo_convert_pystring(title_buf);
        PdfOutlines *outlines = self->doc->GetOutlines();
        if (outlines == NULL) {PyErr_NoMemory(); goto error;}
        ans->item = outlines->CreateRoot(title);
        if (ans->item == NULL) {PyErr_NoMemory(); goto error;}
        ans->doc = self->doc;
        try {
            page = self->doc->GetPage(pagenum - 1);
        } catch (const PdfError &err) {
            (void)err;
            PyErr_Format(PyExc_ValueError, "Invalid page number: %u", pagenum - 1); goto error;
        }
        PdfDestination dest(page, left, top, zoom);
        ans->item->SetDestination(dest);
    } catch(const PdfError & err) {
        podofo_set_exception(err); goto error;
    } catch(const std::exception & err) {
        PyErr_Format(PyExc_ValueError, "An error occurred while trying to create the outline: %s", err.what());
        goto error;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to create the outline");
        goto error;
    }

    return (PyObject*)ans;
error:
    Py_XDECREF(ans);
    return NULL;

} // }}}

PYWRAP(create_outline)
