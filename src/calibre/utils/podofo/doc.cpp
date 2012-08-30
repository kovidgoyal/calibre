/*
 * doc.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace pdf;

// Constructor/desctructor {{{
static void
PDFDoc_dealloc(PDFDoc* self)
{
    if (self->doc != NULL) delete self->doc;
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
PDFDoc_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PDFDoc *self;

    self = (PDFDoc *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->doc = new PdfMemDocument();
        if (self->doc == NULL) { Py_DECREF(self); return NULL; }
    }

    return (PyObject *)self;
}
// }}}

// Loading/Opening of PDF files {{{
static PyObject *
PDFDoc_load(PDFDoc *self, PyObject *args) {
    char *buffer; Py_ssize_t size;

    if (PyArg_ParseTuple(args, "s#", &buffer, &size)) {
        try {
            self->doc->Load(buffer, size);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
    }
} else return NULL;


    Py_RETURN_NONE;
}

static PyObject *
PDFDoc_open(PDFDoc *self, PyObject *args) {
    char *fname;

    if (PyArg_ParseTuple(args, "s", &fname)) {
        try {
            self->doc->Load(fname);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;


    Py_RETURN_NONE;
}
// }}}

// Saving/writing of PDF files {{{
static PyObject *
PDFDoc_save(PDFDoc *self, PyObject *args) {
    char *buffer;

    if (PyArg_ParseTuple(args, "s", &buffer)) {
        try {
            self->doc->Write(buffer);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
}

static PyObject *
PDFDoc_write(PDFDoc *self, PyObject *args) {
    PyObject *ans;
    
    try {
        PdfRefCountedBuffer buffer(1*1024*1024);
        PdfOutputDevice out(&buffer);
        self->doc->Write(&out);
        ans = PyBytes_FromStringAndSize(buffer.GetBuffer(), out.Tell());
        if (ans == NULL) PyErr_NoMemory();
    } catch(const PdfError &err) {
        podofo_set_exception(err);
        return NULL;
    } catch (...) {
        return PyErr_NoMemory();
    }

    return ans;
}
// }}}

// extract_first_page() {{{
static PyObject *
PDFDoc_extract_first_page(PDFDoc *self, PyObject *args) {
    try {
        while (self->doc->GetPageCount() > 1) self->doc->GetPagesTree()->DeletePage(1);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
}
// }}}

// page_count() {{{
static PyObject *
PDFDoc_page_count(PDFDoc *self, PyObject *args) {
    int count;
    try {
        count = self->doc->GetPageCount();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    return Py_BuildValue("i", count);
} // }}}

// delete_page {{{
static PyObject *
PDFDoc_delete_page(PDFDoc *self, PyObject *args) {
    int num = 0;
    if (PyArg_ParseTuple(args, "i", &num)) {
        try {
            self->doc->DeletePages(num, 1);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
} // }}}

// append() {{{
static PyObject *
PDFDoc_append(PDFDoc *self, PyObject *args) {
    PyObject *doc;
    int typ;

    if (!PyArg_ParseTuple(args, "O", &doc)) return NULL;

    typ = PyObject_IsInstance(doc, (PyObject*)&PDFDocType);
    if (typ == -1) return NULL;
    if (typ == 0) { PyErr_SetString(PyExc_TypeError, "You must pass a PDFDoc instance to this method"); return NULL; }

    try {
        self->doc->Append(*((PDFDoc*)doc)->doc, true);
    } catch (const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// set_box() {{{
static PyObject *
PDFDoc_set_box(PDFDoc *self, PyObject *args) {
    int num = 0;
    double left, bottom, width, height;
    char *box;
    if (!PyArg_ParseTuple(args, "isdddd", &num, &box, &left, &bottom, &width, &height)) return NULL;

    try {
        PdfRect r(left, bottom, width, height);
        PdfObject o;
        r.ToVariant(o);
        self->doc->GetPage(num)->GetObject()->GetDictionary().AddKey(PdfName(box), o);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the box");
        return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// create_outline() {{{
static PyObject *
PDFDoc_create_outline(PDFDoc *self, PyObject *args) {
    PyObject *p;
    PDFOutlineItem *ans;
    PdfString *title;
    int pagenum;

    if (!PyArg_ParseTuple(args, "Ui", &p, &pagenum)) return NULL;
    title = podofo_convert_pystring(p);
    if (title == NULL) return NULL;

    ans = PyObject_New(PDFOutlineItem, &PDFOutlineItemType);
    if (ans == NULL) goto error;

    try {
        PdfOutlines *outlines = self->doc->GetOutlines();
        if (outlines == NULL) {PyErr_NoMemory(); goto error;}
        ans->item = outlines->CreateRoot(*title);
        if (ans->item == NULL) {PyErr_NoMemory(); goto error;}
        ans->doc = self->doc;
        PdfDestination dest(self->doc->GetPage(pagenum));
        ans->item->SetDestination(dest);
    } catch(const PdfError & err) {
        podofo_set_exception(err); goto error;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to create the outline");
        goto error;
    }

    delete title;
    return (PyObject*)ans;
error:
    Py_XDECREF(ans); delete title;
    return NULL;

} // }}}

// Properties {{{

static PyObject *
PDFDoc_pages_getter(PDFDoc *self, void *closure) {
    int pages = self->doc->GetPageCount();
    PyObject *ans = PyInt_FromLong(static_cast<long>(pages));
    if (ans != NULL) Py_INCREF(ans);
    return ans;
}

static PyObject *
PDFDoc_version_getter(PDFDoc *self, void *closure) {
    int version;
    try {
        version = self->doc->GetPdfVersion();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    switch(version) {
        case ePdfVersion_1_0:
            return Py_BuildValue("s", "1.0");
        case ePdfVersion_1_1:
            return Py_BuildValue("s", "1.1");
        case ePdfVersion_1_2:
            return Py_BuildValue("s", "1.2");
        case ePdfVersion_1_3:
            return Py_BuildValue("s", "1.3");
        case ePdfVersion_1_4:
            return Py_BuildValue("s", "1.4");
        case ePdfVersion_1_5:
            return Py_BuildValue("s", "1.5");
        case ePdfVersion_1_6:
            return Py_BuildValue("s", "1.6");
        case ePdfVersion_1_7:
            return Py_BuildValue("s", "1.7");
        default:
            return Py_BuildValue("");
    }
    return Py_BuildValue("");
}


static PyObject *
PDFDoc_getter(PDFDoc *self, int field)
{
    PyObject *ans;
    PdfString s;
    PdfInfo *info = self->doc->GetInfo();
    if (info == NULL) {
        PyErr_SetString(PyExc_Exception, "You must first load a PDF Document");
        return NULL;
    }
    switch (field) {
        case 0:
            s = info->GetTitle(); break;
        case 1:
            s = info->GetAuthor(); break;
        case 2:
            s = info->GetSubject(); break;
        case 3:
            s = info->GetKeywords(); break;
        case 4:
            s = info->GetCreator(); break;
        case 5:
            s = info->GetProducer(); break;
        default:
            PyErr_SetString(PyExc_Exception, "Bad field");
            return NULL;
    }

    ans = podofo_convert_pdfstring(s);
    if (ans == NULL) {PyErr_NoMemory(); return NULL;}
    PyObject *uans = PyUnicode_FromEncodedObject(ans, "utf-8", "replace");
    Py_DECREF(ans);
    if (uans == NULL) {return NULL;}
    Py_INCREF(uans);
    return uans;
}

static int
PDFDoc_setter(PDFDoc *self, PyObject *val, int field) {
    if (val == NULL || !PyUnicode_Check(val)) {
        PyErr_SetString(PyExc_ValueError, "Must use unicode objects to set metadata");
        return -1;
    }
    PdfInfo *info = new PdfInfo(*self->doc->GetInfo());
    if (info == NULL) {
        PyErr_SetString(PyExc_Exception, "You must first load a PDF Document");
        return -1;
    }
    PdfString *s = NULL;

    if (self->doc->GetEncrypted()) s = podofo_convert_pystring_single_byte(val);
    else s = podofo_convert_pystring(val); 
    if (s == NULL) return -1;


    switch (field) {
        case 0:
            info->SetTitle(*s); break;
        case 1:
            info->SetAuthor(*s); break;
        case 2:
            info->SetSubject(*s); break;
        case 3:
            info->SetKeywords(*s); break;
        case 4:
            info->SetCreator(*s); break;
        case 5:
            info->SetProducer(*s); break;
        default:
            PyErr_SetString(PyExc_Exception, "Bad field");
            return -1;
    }

    return 0;
}

static PyObject *
PDFDoc_title_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 0);
}
static PyObject *
PDFDoc_author_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 1);
}
static PyObject *
PDFDoc_subject_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 2);
}
static PyObject *
PDFDoc_keywords_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 3);
}
static PyObject *
PDFDoc_creator_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 4);
}
static PyObject *
PDFDoc_producer_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 5);
}
static int
PDFDoc_title_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 0);
}
static int
PDFDoc_author_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 1);
}
static int
PDFDoc_subject_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 2);
}
static int
PDFDoc_keywords_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 3);
}
static int
PDFDoc_creator_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 4);
}
static int
PDFDoc_producer_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 5);
}

static PyGetSetDef PDFDoc_getsetters[] = {
    {(char *)"title", 
     (getter)PDFDoc_title_getter, (setter)PDFDoc_title_setter,
     (char *)"Document title",
     NULL},
    {(char *)"author", 
     (getter)PDFDoc_author_getter, (setter)PDFDoc_author_setter,
     (char *)"Document author",
     NULL},
    {(char *)"subject", 
     (getter)PDFDoc_subject_getter, (setter)PDFDoc_subject_setter,
     (char *)"Document subject",
     NULL},
    {(char *)"keywords", 
     (getter)PDFDoc_keywords_getter, (setter)PDFDoc_keywords_setter,
     (char *)"Document keywords",
     NULL},
    {(char *)"creator", 
     (getter)PDFDoc_creator_getter, (setter)PDFDoc_creator_setter,
     (char *)"Document creator",
     NULL},
    {(char *)"producer", 
     (getter)PDFDoc_producer_getter, (setter)PDFDoc_producer_setter,
     (char *)"Document producer",
     NULL},
    {(char *)"pages", 
     (getter)PDFDoc_pages_getter, NULL,
     (char *)"Number of pages in document (read only)",
     NULL},
    {(char *)"version", 
     (getter)PDFDoc_version_getter, NULL,
     (char *)"The PDF version (read only)",
     NULL},

    {NULL}  /* Sentinel */
};


// }}}

static PyMethodDef PDFDoc_methods[] = {
    {"load", (PyCFunction)PDFDoc_load, METH_VARARGS,
     "Load a PDF document from a byte buffer (string)"
    },
    {"open", (PyCFunction)PDFDoc_open, METH_VARARGS,
     "Load a PDF document from a file path (string)"
    },
    {"save", (PyCFunction)PDFDoc_save, METH_VARARGS,
     "Save the PDF document to a path on disk"
    },
    {"write", (PyCFunction)PDFDoc_write, METH_VARARGS,
     "Return the PDF document as a bytestring."
    },
    {"extract_first_page", (PyCFunction)PDFDoc_extract_first_page, METH_VARARGS,
     "extract_first_page() -> Remove all but the first page."
    },
    {"page_count", (PyCFunction)PDFDoc_page_count, METH_VARARGS,
     "page_count() -> Number of pages in the PDF."
    },
    {"delete_page", (PyCFunction)PDFDoc_delete_page, METH_VARARGS,
     "delete_page(page_num) -> Delete the specified page from the pdf (0 is the first page)."
    },
    {"append", (PyCFunction)PDFDoc_append, METH_VARARGS,
     "append(doc) -> Append doc (which must be a PDFDoc) to this document."
    },
    {"set_box", (PyCFunction)PDFDoc_set_box, METH_VARARGS,
     "set_box(page_num, box, left, bottom, width, height) -> Set the PDF bounding box for the page numbered nu, box must be one of: MediaBox, CropBox, TrimBox, BleedBox, ArtBox. The numbers are interpreted as pts."
    },
    {"create_outline", (PyCFunction)PDFDoc_create_outline, METH_VARARGS,
     "create_outline(title, pagenum) -> Create an outline, return the first outline item."
    },

    {NULL}  /* Sentinel */
};

// Type definition {{{
PyTypeObject pdf::PDFDocType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "podofo.PDFDoc",             /*tp_name*/
    sizeof(PDFDoc), /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)PDFDoc_dealloc,                         /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,        /*tp_flags*/
    "PDF Documents",           /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    PDFDoc_methods,             /* tp_methods */
    0,             /* tp_members */
    PDFDoc_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    PDFDoc_new,                 /* tp_new */

};
// }}}

