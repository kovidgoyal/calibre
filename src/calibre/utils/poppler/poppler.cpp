#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <poppler-qt4.h>
#include <QtCore/QBuffer>
#include <QtGui/QImage>

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
    Poppler::Document *doc;

} poppler_PDFDoc;

extern "C" {
static void
poppler_PDFDoc_dealloc(poppler_PDFDoc* self)
{
    if (self->doc != NULL) delete self->doc;
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
poppler_PDFDoc_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    poppler_PDFDoc *self;

    self = (poppler_PDFDoc *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->doc = NULL;
    }

    return (PyObject *)self;
}

static PyObject *
poppler_PDFDoc_load(poppler_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    char *buffer; Py_ssize_t size; QByteArray data;

    if (!PyArg_ParseTuple(args, "s#", &buffer, &size)) return NULL;

    data = QByteArray::fromRawData(buffer, size);
    self->doc = Poppler::Document::loadFromData(data);
    if (self->doc == NULL) {PyErr_SetString(PyExc_ValueError, "Could not load PDF file from data."); return NULL;}
    Py_RETURN_NONE;
}
}
static QString 
poppler_convert_pystring(PyObject *py) {
    QString ans;
    Py_UNICODE* u = PyUnicode_AS_UNICODE(py);
    PyObject *u8 = PyUnicode_EncodeUTF8(u, PyUnicode_GET_SIZE(py), "replace");
    if (u8 == NULL) { PyErr_NoMemory(); return NULL; }
    ans = QString::fromUtf8(PyString_AS_STRING(u8));
    Py_DECREF(u8);
    return ans;
}
extern "C" {
static PyObject *
poppler_convert_qstring(const QString &src) {
    QByteArray data = src.toUtf8();
    const char *cdata = data.constData();
    int sz = data.size();
    return PyUnicode_Decode(cdata, sz, "utf-8", "error");
}


static PyObject *
poppler_PDFDoc_open(poppler_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    PyObject *fname; QString _fname;
    if (!PyArg_ParseTuple(args, "O", &fname)) return NULL;
    _fname = poppler_convert_pystring(fname);
    self->doc = Poppler::Document::load(_fname);
    Py_RETURN_NONE;
}

static PyObject *
poppler_PDFDoc_getter(poppler_PDFDoc *self, int field)
{
    PyObject *ans;
    const char *s;
    switch (field) {
        case 0:
            s = "Title"; break;
        case 1:
            s = "Author"; break;
        case 2:
            s = "Subject"; break;
        case 3:
            s = "Keywords"; break;
        case 4:
            s = "Creator"; break;
        case 5:
            s = "Producer"; break;
        default:
            PyErr_SetString(PyExc_Exception, "Bad field");
            return NULL;
    }
    ans = poppler_convert_qstring(self->doc->info(QString(s)));
    if (ans != NULL) Py_INCREF(ans);
    return ans;

}

static int
poppler_PDFDoc_setter(poppler_PDFDoc *self, PyObject *val, int field) {
    return -1;
}

static PyObject *
poppler_PDFDoc_title_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 0);
}
static PyObject *
poppler_PDFDoc_author_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 1);
}
static PyObject *
poppler_PDFDoc_subject_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 2);
}
static PyObject *
poppler_PDFDoc_keywords_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 3);
}
static PyObject *
poppler_PDFDoc_creator_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 4);
}
static PyObject *
poppler_PDFDoc_producer_getter(poppler_PDFDoc *self, void *closure) {
    return  poppler_PDFDoc_getter(self, 5);
}
static PyObject *
poppler_PDFDoc_version_getter(poppler_PDFDoc *self, void *closure) {
    PyObject *ans = PyFloat_FromDouble(self->doc->pdfVersion());
    if (ans != NULL) Py_INCREF(ans);
    return ans;
}


static int
poppler_PDFDoc_title_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 0);
}
static int
poppler_PDFDoc_author_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 1);
}
static int
poppler_PDFDoc_subject_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 2);
}
static int
poppler_PDFDoc_keywords_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 3);
}
static int
poppler_PDFDoc_creator_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 4);
}
static int
poppler_PDFDoc_producer_setter(poppler_PDFDoc *self, PyObject *val, void *closure) {
    return  poppler_PDFDoc_setter(self, val, 5);
}
}

static PyObject *
poppler_PDFDoc_render_page(poppler_PDFDoc *self, PyObject *args, PyObject *kwargs) {
    QImage img;
    float xdpi = 166.0, ydpi = 166.0;
    Poppler::Page *page;
    QByteArray ba;
    PyObject *ans = NULL;
    QBuffer buffer(&ba);
    int num;

    if (!PyArg_ParseTuple(args, "i|ff", &num, &xdpi, &ydpi)) return ans;
    if ( self->doc->isLocked()) { 
        PyErr_SetString(PyExc_ValueError, "This document is copyrighted.");
        return ans;
    }

    if ( num < 0 || num >= self->doc->numPages()) {
        PyErr_SetString(PyExc_ValueError, "Invalid page number");
        return ans;
    }

    page = self->doc->page(num);
    img = page->renderToImage(xdpi, ydpi);
    if (img.isNull()) {
        PyErr_SetString(PyExc_Exception, "Failed to render first page of PDF");
        return ans;
    }
    buffer.open(QIODevice::WriteOnly);
    if (!img.save(&buffer, "JPEG")) {
        PyErr_SetString(PyExc_Exception, "Failed to save rendered page");
        return ans;
    }
    ans = PyString_FromStringAndSize(ba.data(), ba.size());
    if (ans != NULL) { Py_INCREF(ans); }
    return ans;
}

static PyMethodDef poppler_PDFDoc_methods[] = {
    {"load", (PyCFunction)poppler_PDFDoc_load, METH_VARARGS,
     "Load a PDF document from a byte buffer (string)"
    },
    {"open", (PyCFunction)poppler_PDFDoc_open, METH_VARARGS,
     "Load a PDF document from a file path (string)"
    },
    {"render_page", (PyCFunction)poppler_PDFDoc_render_page, METH_VARARGS,
     "render_page(page_num, xdpi=166, ydpi=166) -> Render a page to a JPEG image. Page numbers start from zero."
    },
    {NULL}  /* Sentinel */
};

static PyObject *
poppler_PDFDoc_pages_getter(poppler_PDFDoc *self, void *closure) {
    int pages = self->doc->numPages();
    PyObject *ans = PyInt_FromLong(static_cast<long>(pages));
    if (ans != NULL) Py_INCREF(ans);
    return ans;
}

static PyGetSetDef poppler_PDFDoc_getsetters[] = {
    {(char *)"title", 
     (getter)poppler_PDFDoc_title_getter, (setter)poppler_PDFDoc_title_setter,
     (char *)"Document title",
     NULL},
    {(char *)"author", 
     (getter)poppler_PDFDoc_author_getter, (setter)poppler_PDFDoc_author_setter,
     (char *)"Document author",
     NULL},
    {(char *)"subject", 
     (getter)poppler_PDFDoc_subject_getter, (setter)poppler_PDFDoc_subject_setter,
     (char *)"Document subject",
     NULL},
    {(char *)"keywords", 
     (getter)poppler_PDFDoc_keywords_getter, (setter)poppler_PDFDoc_keywords_setter,
     (char *)"Document keywords",
     NULL},
    {(char *)"creator", 
     (getter)poppler_PDFDoc_creator_getter, (setter)poppler_PDFDoc_creator_setter,
     (char *)"Document creator",
     NULL},
    {(char *)"producer", 
     (getter)poppler_PDFDoc_producer_getter, (setter)poppler_PDFDoc_producer_setter,
     (char *)"Document producer",
     NULL},
    {(char *)"pages", 
     (getter)poppler_PDFDoc_pages_getter, NULL,
     (char *)"Number of pages in document (read only)",
     NULL},
    {(char *)"version", 
     (getter)poppler_PDFDoc_version_getter, NULL,
     (char *)"The PDF version (read only)",
     NULL},

    {NULL}  /* Sentinel */
};



static PyTypeObject poppler_PDFDocType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "calibre_poppler.PDFDoc",             /*tp_name*/
    sizeof(poppler_PDFDoc), /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)poppler_PDFDoc_dealloc,                         /*tp_dealloc*/
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
    poppler_PDFDoc_methods,             /* tp_methods */
    0,             /* tp_members */
    poppler_PDFDoc_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    poppler_PDFDoc_new,                 /* tp_new */
};



static PyMethodDef poppler_methods[] = {
    {NULL}  /* Sentinel */
};

extern "C" {

PyMODINIT_FUNC
initcalibre_poppler(void) 
{
    PyObject* m;

    if (PyType_Ready(&poppler_PDFDocType) < 0)
        return;

    m = Py_InitModule3("calibre_poppler", poppler_methods,
                       "Wrapper for the Poppler PDF library");

    Py_INCREF(&poppler_PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&poppler_PDFDocType);
}
}
