/*
 * outlines.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
using namespace pdf;


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

}

static PyObject*
create_outline_node() {
	pyunique_ptr ans(PyDict_New());
	if (!ans) return NULL;
	pyunique_ptr children(PyList_New(0));
	if (!children) return NULL;
	if (PyDict_SetItemString(ans.get(), "children", children.get()) != 0) return NULL;
	return ans.release();
}

static void
convert_outline(PDFDoc *self, PyObject *parent, PdfOutlineItem *item) {
	pyunique_ptr title(podofo_convert_pdfstring(item->GetTitle()));
	if (!title) return;
	pyunique_ptr node(create_outline_node());
	if (!node) return;
	if (PyDict_SetItemString(node.get(), "title", title.get()) != 0) return;
	PdfDestination* dest = item->GetDestination(self->doc);
	if (dest) {
		PdfPage *page = dest->GetPage(self->doc);
		long pnum = page ? page->GetPageNumber() : -1;
		pyunique_ptr d(Py_BuildValue("{sl sd sd sd}", "page", pnum, "top", dest->GetTop(), "left", dest->GetLeft(), "zoom", dest->GetZoom()));
		if (!d) return;
		if (PyDict_SetItemString(node.get(), "dest", d.get()) != 0) return;
	}
	PyObject *children = PyDict_GetItemString(parent, "children");
	if (PyList_Append(children, node.get()) != 0) return;

	if (item->First()) {
		convert_outline(self, node.get(), item->First());
		if (PyErr_Occurred()) return;
	}

	if (item->Next()) {
		convert_outline(self, parent, item->Next());
		if (PyErr_Occurred()) return;
	}
}

static PyObject *
get_outline(PDFDoc *self, PyObject *args) {
	PdfOutlines *root = self->doc->GetOutlines(PoDoFo::ePdfDontCreateObject);
	if (!root || !root->First()) Py_RETURN_NONE;
	PyObject *ans = create_outline_node();
	if (!ans) return NULL;
	convert_outline(self, ans, root->First());
	if (PyErr_Occurred()) { Py_DECREF(ans); return NULL; }
	if (!ans) return NULL;

	return ans;
}

PYWRAP(create_outline)
PYWRAP(get_outline)
