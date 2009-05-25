#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

class podofo_pdfmem_wrapper : public PdfMemDocument {
    public:
        inline void set_info(PdfInfo *i) { this->SetInfo(i); }
};

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
    podofo_pdfmem_wrapper *doc;

} podofo_PDFDoc;

extern "C" {
static void
podofo_PDFDoc_dealloc(podofo_PDFDoc* self)
{
    if (self->doc != NULL) delete self->doc;
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
podofo_PDFDoc_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    podofo_PDFDoc *self;

    self = (podofo_PDFDoc *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->doc = new podofo_pdfmem_wrapper();
        if (self->doc == NULL) { Py_DECREF(self); return NULL; }
    }

    return (PyObject *)self;
}

static void podofo_set_exception(const PdfError &err) {
    const char *msg = PdfError::ErrorMessage(err.GetError());
    if (msg == NULL) msg = err.what();
    PyErr_SetString(PyExc_ValueError, msg);
}

static PyObject *
podofo_PDFDoc_load(podofo_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    char *buffer; Py_ssize_t size;

    if (PyArg_ParseTuple(args, "s#", &buffer, &size)) {
        try {
            self->doc->Load(buffer, size);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
    }
} else return NULL;


    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
podofo_PDFDoc_open(podofo_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    char *fname;

    if (PyArg_ParseTuple(args, "s", &fname)) {
        try {
            self->doc->Load(fname);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
    }
} else return NULL;


    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
podofo_PDFDoc_save(podofo_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    char *buffer;

    if (PyArg_ParseTuple(args, "s", &buffer)) {
        try {
            self->doc->Write(buffer);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;


    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
podofo_convert_pdfstring(const PdfString &s) {
    std::string raw = s.GetStringUtf8();
	return PyString_FromStringAndSize(raw.c_str(), raw.length());
}

static PdfString *
podofo_convert_pystring(PyObject *py) {
    Py_UNICODE* u = PyUnicode_AS_UNICODE(py);
    PyObject *u8 = PyUnicode_EncodeUTF8(u, PyUnicode_GET_SIZE(py), "replace");
    if (u8 == NULL) { PyErr_NoMemory(); return NULL; }
    pdf_utf8 *s8 = (pdf_utf8 *)PyString_AS_STRING(u8);
    PdfString *ans = new PdfString(s8);
    Py_DECREF(u8);
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}

static PyObject *
podofo_PDFDoc_getter(podofo_PDFDoc *self, int field)
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
podofo_PDFDoc_setter(podofo_PDFDoc *self, PyObject *val, int field) {
    if (val == NULL || !PyUnicode_Check(val)) {
        PyErr_SetString(PyExc_ValueError, "Must use unicode objects to set metadata");
        return -1;
    }
    PdfInfo *info = new PdfInfo(*self->doc->GetInfo());
    if (info == NULL) {
        PyErr_SetString(PyExc_Exception, "You must first load a PDF Document");
        return -1;
    }

    PdfString *s = podofo_convert_pystring(val); 
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

    self->doc->set_info(info);
    return 0;
}

static PyObject *
podofo_PDFDoc_title_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 0);
}
static PyObject *
podofo_PDFDoc_author_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 1);
}
static PyObject *
podofo_PDFDoc_subject_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 2);
}
static PyObject *
podofo_PDFDoc_keywords_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 3);
}
static PyObject *
podofo_PDFDoc_creator_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 4);
}
static PyObject *
podofo_PDFDoc_producer_getter(podofo_PDFDoc *self, void *closure) {
    return  podofo_PDFDoc_getter(self, 5);
}
static int
podofo_PDFDoc_title_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 0);
}
static int
podofo_PDFDoc_author_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 1);
}
static int
podofo_PDFDoc_subject_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 2);
}
static int
podofo_PDFDoc_keywords_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 3);
}
static int
podofo_PDFDoc_creator_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 4);
}
static int
podofo_PDFDoc_producer_setter(podofo_PDFDoc *self, PyObject *val, void *closure) {
    return  podofo_PDFDoc_setter(self, val, 5);
}





} /* extern "C" */

static PyMethodDef podofo_PDFDoc_methods[] = {
    {"load", (PyCFunction)podofo_PDFDoc_load, METH_VARARGS,
     "Load a PDF document from a byte buffer (string)"
    },
    {"open", (PyCFunction)podofo_PDFDoc_open, METH_VARARGS,
     "Load a PDF document from a file path (string)"
    },
    {"save", (PyCFunction)podofo_PDFDoc_save, METH_VARARGS,
     "Save the PDF document to a path on disk"
    },
    {NULL}  /* Sentinel */
};

static PyGetSetDef podofo_PDFDoc_getseters[] = {
    {"title", 
     (getter)podofo_PDFDoc_title_getter, (setter)podofo_PDFDoc_title_setter,
     "Document title",
     NULL},
    {"author", 
     (getter)podofo_PDFDoc_author_getter, (setter)podofo_PDFDoc_author_setter,
     "Document author",
     NULL},
    {"subject", 
     (getter)podofo_PDFDoc_subject_getter, (setter)podofo_PDFDoc_subject_setter,
     "Document subject",
     NULL},
    {"keywords", 
     (getter)podofo_PDFDoc_keywords_getter, (setter)podofo_PDFDoc_keywords_setter,
     "Document keywords",
     NULL},
    {"creator", 
     (getter)podofo_PDFDoc_creator_getter, (setter)podofo_PDFDoc_creator_setter,
     "Document creator",
     NULL},
    {"producer", 
     (getter)podofo_PDFDoc_producer_getter, (setter)podofo_PDFDoc_producer_setter,
     "Document producer",
     NULL},

    {NULL}  /* Sentinel */
};

static PyTypeObject podofo_PDFDocType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "podofo.PDFDoc",             /*tp_name*/
    sizeof(podofo_PDFDoc), /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)podofo_PDFDoc_dealloc,                         /*tp_dealloc*/
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
    podofo_PDFDoc_methods,             /* tp_methods */
    0,             /* tp_members */
    podofo_PDFDoc_getseters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    podofo_PDFDoc_new,                 /* tp_new */

};

static PyMethodDef podofo_methods[] = {
    {NULL}  /* Sentinel */
};

extern "C" {


PyMODINIT_FUNC
initpodofo(void) 
{
    PyObject* m;

    if (PyType_Ready(&podofo_PDFDocType) < 0)
        return;

    m = Py_InitModule3("podofo", podofo_methods,
                       "Wrapper for the PoDoFo pDF library");

    Py_INCREF(&podofo_PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&podofo_PDFDocType);
}
}
