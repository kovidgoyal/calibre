/*
 * outline.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace pdf;

// Constructor/destructor {{{
static void
dealloc(PDFOutlineItem* self)
{
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
new_item(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PDFOutlineItem *self;

    self = (PDFOutlineItem *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->item = NULL;
    }

    return (PyObject *)self;
}
// }}}

// erase() {{{
static PyObject *
erase(PDFOutlineItem *self, PyObject *args) {
    try {
        self->item->Erase();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
} // }}}

static PyObject *
create(PDFOutlineItem *self, PyObject *args) {
    PyObject *as_child;
    PDFOutlineItem *ans;
    unsigned int num;
    double left = 0, top = 0, zoom = 0;
    PdfPage *page;
    PyObject *title_buf;

    if (!PyArg_ParseTuple(args, "UIO|ddd", &title_buf, &num, &as_child, &left, &top, &zoom)) return NULL;

    ans = PyObject_New(PDFOutlineItem, &PDFOutlineItemType);
    if (ans == NULL) goto error;
    ans->doc = self->doc;

    try {
        PdfString title = podofo_convert_pystring(title_buf);
        try {
            page = self->doc->GetPage(num - 1);
        } catch(const PdfError &err) { (void)err; page = NULL; }
        if (page == NULL) { PyErr_Format(PyExc_ValueError, "Invalid page number: %u", num); goto error; }
        PdfDestination dest(page, left, top, zoom);
        if (PyObject_IsTrue(as_child)) {
            ans->item = self->item->CreateChild(title, dest);
        } else
            ans->item = self->item->CreateNext(title, dest);
    } catch (const PdfError &err) {
        podofo_set_exception(err); goto error;
    } catch(const std::exception & err) {
        PyErr_Format(PyExc_ValueError, "An error occurred while trying to create the outline: %s", err.what());
        goto error;
    } catch (...) {
        PyErr_SetString(PyExc_Exception, "An unknown error occurred while trying to create the outline item");
        goto error;
    }

    return (PyObject*) ans;
error:
    Py_XDECREF(ans);
    return NULL;
}

static PyMethodDef methods[] = {

    {"create", (PyCFunction)create, METH_VARARGS,
        "create(title, pagenum, as_child=False) -> Create a new outline item with title 'title', pointing to page number pagenum. If as_child is True the new item will be a child of this item otherwise it will be a sibling. Returns the newly created item."
    },

    {"erase", (PyCFunction)erase, METH_VARARGS,
        "erase() -> Delete this item and all its children, removing it from the outline tree completely."
    },

    {NULL}  /* Sentinel */
};


// Type definition {{{
PyTypeObject pdf::PDFOutlineItemType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "podofo.PDFOutlineItem",
    /* tp_basicsize      */ sizeof(PDFOutlineItem),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)dealloc,
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
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */ "PDF Outline items",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ new_item,
};
// }}}
