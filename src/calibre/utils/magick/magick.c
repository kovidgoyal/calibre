#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <wand/MagickWand.h>

#include "magick_constants.h"

// Ensure that the underlying MagickWand has not been deleted
#define NULL_CHECK(x) if(self->wand == NULL) {PyErr_SetString(PyExc_ValueError, "Underlying ImageMagick Wand has been destroyed"); return x; }

// magick_set_exception {{{
PyObject* magick_set_exception(MagickWand *wand) {
    ExceptionType ext;
    char *desc = MagickGetException(wand, &ext);
    PyErr_SetString(PyExc_Exception, desc);
    MagickClearException(wand);
    desc = MagickRelinquishMemory(desc);
    return NULL;
}
// }}}

// PixelWand object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    PixelWand *wand;

} magick_PixelWand;

static void
magick_PixelWand_dealloc(magick_PixelWand* self)
{
    if (self->wand != NULL) self->wand = DestroyPixelWand(self->wand);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
magick_PixelWand_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    magick_PixelWand *self;

    self = (magick_PixelWand *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->wand = NewPixelWand();
        if (self->wand == NULL || self->wand < 0) { 
            PyErr_SetString(PyExc_Exception, "Failed to allocate wand.");
            self->wand = NULL;
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

// PixelWand.color {{{
static PyObject *
magick_PixelWand_color_getter(magick_PixelWand *self, void *closure) {
    const char *fp;
    NULL_CHECK(NULL);
    fp = PixelGetColorAsNormalizedString(self->wand);
    return Py_BuildValue("s", fp);
}

static int
magick_PixelWand_color_setter(magick_PixelWand *self, PyObject *val, void *closure) {
    char *fmt;

    NULL_CHECK(-1);

    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete PixelWand color");
        return -1;
    }

    fmt = PyString_AsString(val);
    if (fmt == NULL) return -1;

    if (!PixelSetColor(self->wand, fmt)) {
        PyErr_SetString(PyExc_ValueError, "Unknown color");
        return -1;
    }

    return 0;
}

// }}}

// PixelWand.destroy {{{

static PyObject *
magick_PixelWand_destroy(magick_PixelWand *self, PyObject *args) {
    NULL_CHECK(NULL)
    self->wand = DestroyPixelWand(self->wand);
    Py_RETURN_NONE;
}
// }}}

// PixelWand attr list {{{
static PyMethodDef magick_PixelWand_methods[] = {
    {"destroy", (PyCFunction)magick_PixelWand_destroy, METH_VARARGS,
    "Destroy the underlying ImageMagick Wand. WARNING: After using this method, all methods on this object will raise an exception."},

    {NULL}  /* Sentinel */
};

static PyGetSetDef  magick_PixelWand_getsetters[] = {
    {(char *)"color", 
     (getter)magick_PixelWand_color_getter, (setter)magick_PixelWand_color_setter,
     (char *)"PixelWand color. ImageMagick color specification.",
     NULL},

    {NULL}  /* Sentinel */
};

// }}}

static PyTypeObject magick_PixelWandType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "magick.PixelWand",            /*tp_name*/
    sizeof(magick_PixelWand),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)magick_PixelWand_dealloc, /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "PixelWand",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    magick_PixelWand_methods,             /* tp_methods */
    0,             /* tp_members */
    magick_PixelWand_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    magick_PixelWand_new,                 /* tp_new */
}; // }}}


// }}}

// DrawingWand object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    DrawingWand *wand;

} magick_DrawingWand;

static void
magick_DrawingWand_dealloc(magick_DrawingWand* self)
{
    if (self->wand != NULL) self->wand = DestroyDrawingWand(self->wand);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
magick_DrawingWand_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    magick_DrawingWand *self;

    self = (magick_DrawingWand *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->wand = NewDrawingWand();
        if (self->wand == NULL || self->wand < 0) { 
            PyErr_SetString(PyExc_Exception, "Failed to allocate wand.");
            self->wand = NULL;
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

// DrawingWand.destroy {{{

static PyObject *
magick_DrawingWand_destroy(magick_DrawingWand *self, PyObject *args) {
    NULL_CHECK(NULL)
    self->wand = DestroyDrawingWand(self->wand);
    Py_RETURN_NONE;
}
// }}}

// DrawingWand.font {{{
static PyObject *
magick_DrawingWand_font_getter(magick_DrawingWand *self, void *closure) {
    const char *fp;
    NULL_CHECK(NULL);
    fp = DrawGetFont(self->wand);
    return Py_BuildValue("s", fp);
}

static int
magick_DrawingWand_font_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    char *fmt;
    NULL_CHECK(-1);

    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand font");
        return -1;
    }

    fmt = PyString_AsString(val);
    if (fmt == NULL) return -1;

    if (!DrawSetFont(self->wand, fmt)) {
        PyErr_SetString(PyExc_ValueError, "Unknown font");
        return -1;
    }

    return 0;
}

// }}}

// DrawingWand.font_size {{{
static PyObject *
magick_DrawingWand_fontsize_getter(magick_DrawingWand *self, void *closure) {
    NULL_CHECK(NULL)
    return Py_BuildValue("d", DrawGetFontSize(self->wand));
}

static int
magick_DrawingWand_fontsize_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    NULL_CHECK(-1)
    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand fontsize");
        return -1;
    }

    if (!PyFloat_Check(val))  {
        PyErr_SetString(PyExc_TypeError, "Font size must be a float");
        return -1;
    }

    DrawSetFontSize(self->wand, PyFloat_AsDouble(val));

    return 0;
}

// }}}

// DrawingWand.stroke_color {{{
static PyObject *
magick_DrawingWand_stroke_color_getter(magick_DrawingWand *self, void *closure) {
    magick_PixelWand *pw;
    PixelWand *wand;

    NULL_CHECK(NULL)
    wand = NewPixelWand();

    if (wand == NULL) return PyErr_NoMemory();
    DrawGetStrokeColor(self->wand, wand);

    pw = (magick_PixelWand*) magick_PixelWandType.tp_alloc(&magick_PixelWandType, 0);
    if (pw == NULL) return PyErr_NoMemory();
    pw->wand = wand;
    return Py_BuildValue("O", (PyObject *)pw);
}

static int
magick_DrawingWand_stroke_color_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    magick_PixelWand *pw;

    NULL_CHECK(-1)
    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand stroke color");
        return -1;
    }

    
    pw = (magick_PixelWand*)val;
    if (!IsPixelWand(pw->wand)) { PyErr_SetString(PyExc_TypeError, "Invalid PixelWand"); return -1; }

    DrawSetStrokeColor(self->wand, pw->wand);

    return 0;
}

// }}}

// DrawingWand.fill_color {{{
static PyObject *
magick_DrawingWand_fill_color_getter(magick_DrawingWand *self, void *closure) {
    magick_PixelWand *pw;
    PixelWand *wand;

    NULL_CHECK(NULL)
    wand = NewPixelWand();

    if (wand == NULL) return PyErr_NoMemory();
    DrawGetFillColor(self->wand, wand);

    pw = (magick_PixelWand*) magick_PixelWandType.tp_alloc(&magick_PixelWandType, 0);
    if (pw == NULL) return PyErr_NoMemory();
    pw->wand = wand;
    return Py_BuildValue("O", (PyObject *)pw);
}

static int
magick_DrawingWand_fill_color_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    magick_PixelWand *pw;

    NULL_CHECK(-1)
    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand fill color");
        return -1;
    }

    
    pw = (magick_PixelWand*)val;
    if (!IsPixelWand(pw->wand)) { PyErr_SetString(PyExc_TypeError, "Invalid PixelWand"); return -1; }

    DrawSetFillColor(self->wand, pw->wand);

    return 0;
}

// }}}

// DrawingWand.text_antialias {{{
static PyObject *
magick_DrawingWand_textantialias_getter(magick_DrawingWand *self, void *closure) {
    NULL_CHECK(NULL);
    if (DrawGetTextAntialias(self->wand)) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static int
magick_DrawingWand_textantialias_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    NULL_CHECK(-1);
    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand textantialias");
        return -1;
    }
    DrawSetTextAntialias(self->wand, (MagickBooleanType)PyObject_IsTrue(val));

    return 0;
}

// }}}

// DrawingWand.gravity {{{
static PyObject *
magick_DrawingWand_gravity_getter(magick_DrawingWand *self, void *closure) {
    NULL_CHECK(NULL);
    return Py_BuildValue("n", DrawGetGravity(self->wand));
}

static int
magick_DrawingWand_gravity_setter(magick_DrawingWand *self, PyObject *val, void *closure) {
    int grav;

    NULL_CHECK(-1);

    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete DrawingWand gravity");
        return -1;
    }

    if (!PyInt_Check(val))  {
        PyErr_SetString(PyExc_TypeError, "Gravity must be an integer");
        return -1;
    }

    grav = (int)PyInt_AS_LONG(val);

    DrawSetGravity(self->wand, grav);

    return 0;
}

// }}}

// DrawingWand attr list {{{
static PyMethodDef magick_DrawingWand_methods[] = {
    {"destroy", (PyCFunction)magick_DrawingWand_destroy, METH_VARARGS,
    "Destroy the underlying ImageMagick Wand. WARNING: After using this method, all methods on this object will raise an exception."},

    {NULL}  /* Sentinel */
};

static PyGetSetDef  magick_DrawingWand_getsetters[] = {
    {(char *)"font_", 
     (getter)magick_DrawingWand_font_getter, (setter)magick_DrawingWand_font_setter,
     (char *)"DrawingWand font path. Absolute path to font file.",
     NULL},

    {(char *)"font_size_", 
     (getter)magick_DrawingWand_fontsize_getter, (setter)magick_DrawingWand_fontsize_setter,
     (char *)"DrawingWand fontsize",
     NULL},

    {(char *)"stroke_color_", 
     (getter)magick_DrawingWand_stroke_color_getter, (setter)magick_DrawingWand_stroke_color_setter,
     (char *)"DrawingWand stroke color",
     NULL},

    {(char *)"fill_color_", 
     (getter)magick_DrawingWand_fill_color_getter, (setter)magick_DrawingWand_fill_color_setter,
     (char *)"DrawingWand fill color",
     NULL},

    {(char *)"text_antialias", 
     (getter)magick_DrawingWand_textantialias_getter, (setter)magick_DrawingWand_textantialias_setter,
     (char *)"DrawingWand text antialias",
     NULL},

    {(char *)"gravity_", 
     (getter)magick_DrawingWand_gravity_getter, (setter)magick_DrawingWand_gravity_setter,
     (char *)"DrawingWand gravity",
     NULL},

    {NULL}  /* Sentinel */
};

// }}}

static PyTypeObject magick_DrawingWandType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "magick.DrawingWand",            /*tp_name*/
    sizeof(magick_DrawingWand),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)magick_DrawingWand_dealloc, /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "DrawingWand",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    magick_DrawingWand_methods,             /* tp_methods */
    0,             /* tp_members */
    magick_DrawingWand_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    magick_DrawingWand_new,                 /* tp_new */
}; // }}}


// }}}

// Image object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    MagickWand *wand;

} magick_Image;

// Method declarations {{{
static PyObject* magick_Image_compose(magick_Image *self, PyObject *args);
static PyObject* magick_Image_copy(magick_Image *self, PyObject *args);
static PyObject* magick_Image_texture(magick_Image *self, PyObject *args);
// }}}

static void
magick_Image_dealloc(magick_Image* self)
{
    if (self->wand != NULL) self->wand = DestroyMagickWand(self->wand);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
magick_Image_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    magick_Image *self;

    self = (magick_Image *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->wand = NewMagickWand();
        if (self->wand == NULL || self->wand < 0) { 
            PyErr_SetString(PyExc_Exception, "Failed to allocate wand.");
            self->wand = NULL;
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}


// Image.load {{{
static PyObject *
magick_Image_load(magick_Image *self, PyObject *args) {
    const char *data;
	Py_ssize_t dlen;
    MagickBooleanType res;
    
    NULL_CHECK(NULL)
    if (!PyArg_ParseTuple(args, "s#", &data, &dlen)) return NULL;

    res = MagickReadImageBlob(self->wand, data, dlen);

    if (!res)
        return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}

// }}}

// Image.identify {{{
static PyObject *
magick_Image_identify(magick_Image *self, PyObject *args) {
    const char *data;
	Py_ssize_t dlen;
    MagickBooleanType res;
    
    NULL_CHECK(NULL)
    if (!PyArg_ParseTuple(args, "s#", &data, &dlen)) return NULL;

    res = MagickPingImageBlob(self->wand, data, dlen);

    if (!res)
        return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}

// }}}

// Image.open {{{
static PyObject *
magick_Image_read(magick_Image *self, PyObject *args) {
    const char *data;
    MagickBooleanType res;
    
   NULL_CHECK(NULL)
   if (!PyArg_ParseTuple(args, "s", &data)) return NULL;

    res = MagickReadImage(self->wand, data);

    if (!res)
        return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}

// }}}

// Image.create_canvas {{{
static PyObject *
magick_Image_create_canvas(magick_Image *self, PyObject *args)
{
    Py_ssize_t width, height;
    char *bgcolor;
    PixelWand *pw;
    MagickBooleanType res = MagickFalse;

    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "nns", &width, &height, &bgcolor)) return NULL;

    pw = NewPixelWand();
    if (pw == NULL) return PyErr_NoMemory();
    PixelSetColor(pw, bgcolor);
    res = MagickNewImage(self->wand, width, height, pw);
    pw = DestroyPixelWand(pw);
    if (!res) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.font_metrics {{{

static PyObject *
magick_Image_font_metrics(magick_Image *self, PyObject *args) {
    char *text;
    PyObject *dw_, *ans, *m;
    Py_ssize_t i;
    DrawingWand *dw;
    double *metrics;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!s", &magick_DrawingWandType, &dw_, &text)) return NULL;
    dw = ((magick_DrawingWand*)dw_)->wand;
    if (!IsDrawingWand(dw)) { PyErr_SetString(PyExc_TypeError, "Invalid drawing wand"); return NULL; }
    ans = PyTuple_New(13);
    if (ans == NULL)  return PyErr_NoMemory();

    metrics = MagickQueryFontMetrics(self->wand, dw, text);

    for (i = 0; i < 13; i++) {
        m = PyFloat_FromDouble(metrics[i]);
        if (m == NULL) { return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(ans, i, m);
    }

    return ans;
}
// }}}

// Image.annotate {{{

static PyObject *
magick_Image_annotate(magick_Image *self, PyObject *args) {
    char *text;
    PyObject *dw_;
    DrawingWand *dw;
    double x, y, angle;

    NULL_CHECK(NULL)
    
    if (!PyArg_ParseTuple(args, "O!ddds", &magick_DrawingWandType, &dw_, &x, &y, &angle, &text)) return NULL;
    dw = ((magick_DrawingWand*)dw_)->wand;
    if (!IsDrawingWand(dw)) { PyErr_SetString(PyExc_TypeError, "Invalid drawing wand"); return NULL; }

    if (!MagickAnnotateImage(self->wand, dw, x, y, angle, text)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.export {{{

static PyObject *
magick_Image_export(magick_Image *self, PyObject *args) {
    char *fmt;
    unsigned char *data;
    PyObject *ans;
    size_t len = 0;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "s", &fmt)) return NULL;

    if (!MagickSetFormat(self->wand, fmt)) {
        PyErr_SetString(PyExc_ValueError, "Unknown image format");
        return NULL;
    }

    data = MagickGetImageBlob(self->wand, &len);

    if (data == NULL || len < 1) 
        return magick_set_exception(self->wand);

    ans = Py_BuildValue("s#", data, len);
    data = MagickRelinquishMemory(data);

    return ans;
}
// }}}

// Image.size {{{
static PyObject *
magick_Image_size_getter(magick_Image *self, void *closure) {
    size_t width, height;
    NULL_CHECK(NULL)

    width = MagickGetImageWidth(self->wand);
    height = MagickGetImageHeight(self->wand);
    return Py_BuildValue("nn", width, height);
}

static int
magick_Image_size_setter(magick_Image *self, PyObject *val, void *closure) {
    Py_ssize_t width, height;
    int filter;
    double blur;
    MagickBooleanType res;

    NULL_CHECK(-1)


    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete image size");
        return -1;
    }

    if (!PySequence_Check(val) || PySequence_Length(val) < 4) {
        PyErr_SetString(PyExc_TypeError, "Must use at least a 4 element sequence to set size");
        return -1;
    }

    if (!PyInt_Check(PySequence_ITEM(val, 2))) {
        PyErr_SetString(PyExc_TypeError, "Filter must be an integer");
        return -1;
    }


    width = PyInt_AsSsize_t(PySequence_ITEM(val, 0));
    height = PyInt_AsSsize_t(PySequence_ITEM(val, 1));
    filter = (int)PyInt_AS_LONG(PySequence_ITEM(val, 2));
    blur = PyFloat_AsDouble(PySequence_ITEM(val, 3));

    if (PyErr_Occurred()) {
        PyErr_SetString(PyExc_TypeError, "Width, height, filter or blur not a number");
        return -1;
    }

    if ( filter <= UndefinedFilter || filter >= SentinelFilter) {
        PyErr_SetString(PyExc_ValueError, "Invalid filter");
        return -1;
    }

    res = MagickResizeImage(self->wand, width, height, filter, blur);

    if (!res) {
        magick_set_exception(self->wand);
        return -1;
    }

    return 0;
    
}
// }}}

// Image.format {{{
static PyObject *
magick_Image_format_getter(magick_Image *self, void *closure) {
    const char *fmt;
    NULL_CHECK(NULL)

    fmt = MagickGetImageFormat(self->wand);
    return Py_BuildValue("s", fmt);
}

static int
magick_Image_format_setter(magick_Image *self, PyObject *val, void *closure) {
    char *fmt;
    NULL_CHECK(-1)


    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete image format");
        return -1;
    }

    fmt = PyString_AsString(val);
    if (fmt == NULL) return -1;

    if (!MagickSetImageFormat(self->wand, fmt)) {
        PyErr_SetString(PyExc_ValueError, "Unknown image format");
        return -1;
    }

    return 0;
}

// }}}

// Image.distort {{{

static PyObject *
magick_Image_distort(magick_Image *self, PyObject *args) {
    int method;
    Py_ssize_t i, number;
    PyObject *bestfit, *argv, *t;
    MagickBooleanType res;
    double *arguments = NULL;
   
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "iOO", &method, &argv, &bestfit)) return NULL;

    if (!PySequence_Check(argv)) { PyErr_SetString(PyExc_TypeError, "arguments must be a sequence"); return NULL; }

    number = PySequence_Length(argv);
    if (number > 0) {
        arguments = (double *)PyMem_Malloc(sizeof(double) * number);
        if (arguments == NULL) return PyErr_NoMemory(); 
        for (i = 0; i < number; i++) {
            t = PySequence_ITEM(argv, i);
            if (t == NULL || !PyFloat_Check(t)) { PyErr_SetString(PyExc_TypeError, "Arguments must all be floats"); PyMem_Free(arguments); return NULL; }
            arguments[i] = PyFloat_AsDouble(t);
        }
    }

    res = MagickDistortImage(self->wand, method, number, arguments, PyObject_IsTrue(bestfit));
    if (arguments != NULL) PyMem_Free(arguments);

    if (!res) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.trim {{{

static PyObject *
magick_Image_trim(magick_Image *self, PyObject *args) {
    double fuzz;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "d", &fuzz)) return NULL;

    if (!MagickTrimImage(self->wand, fuzz)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.thumbnail {{{

static PyObject *
magick_Image_thumbnail(magick_Image *self, PyObject *args) {
    Py_ssize_t width, height;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "nn", &width, &height)) return NULL;

    if (!MagickThumbnailImage(self->wand, width, height)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.crop {{{

static PyObject *
magick_Image_crop(magick_Image *self, PyObject *args) {
    Py_ssize_t width, height, x, y;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "nnnn", &width, &height, &x, &y)) return NULL;

    if (!MagickCropImage(self->wand, width, height, x, y)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.set_border_color {{{

static PyObject *
magick_Image_set_border_color(magick_Image *self, PyObject *args) {
    PyObject *obj;
    magick_PixelWand *pw;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!", &magick_PixelWandType, &obj)) return NULL;
    pw = (magick_PixelWand*)obj;
    if (!IsPixelWand(pw->wand)) { PyErr_SetString(PyExc_TypeError, "Invalid PixelWand"); return NULL; }

    if (!MagickSetImageBorderColor(self->wand, pw->wand)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.rotate {{{

static PyObject *
magick_Image_rotate(magick_Image *self, PyObject *args) {
    PyObject *obj;
    magick_PixelWand *pw;
    double degrees;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!d", &magick_PixelWandType, &obj, &degrees)) return NULL;
    pw = (magick_PixelWand*)obj;
    if (!IsPixelWand(pw->wand)) { PyErr_SetString(PyExc_TypeError, "Invalid PixelWand"); return NULL; }

    if (!MagickRotateImage(self->wand, pw->wand, degrees)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.rotate {{{

static PyObject *
magick_Image_flip(magick_Image *self, PyObject *args) {
    PyObject *obj = NULL;
    MagickBooleanType ret = 0;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "|O", &obj)) return NULL;
    ret = (obj != NULL && PyObject_IsTrue(obj)) ? MagickFlopImage(self->wand) : MagickFlipImage(self->wand);
    if (!ret) { PyErr_SetString(PyExc_ValueError, "Failed to flip image"); return NULL; }

    Py_RETURN_NONE;
}
// }}}

// Image.set_page {{{

static PyObject *
magick_Image_set_page(magick_Image *self, PyObject *args) {
    Py_ssize_t width, height, x, y;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "nnnn", &width, &height, &x, &y)) return NULL;

    if (!MagickSetImagePage(self->wand, width, height, x, y)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.set_compression_quality {{{

static PyObject *
magick_Image_set_compression_quality(magick_Image *self, PyObject *args) {
    Py_ssize_t quality;
    
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "n", &quality)) return NULL;

    if (!MagickSetImageCompressionQuality(self->wand, quality)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.has_transparent_pixels {{{

static PyObject *
magick_Image_has_transparent_pixels(magick_Image *self, PyObject *args) {
    PixelIterator *pi = NULL;
    PixelWand **pixels = NULL;
    int found = 0;
    size_t r, c, width, height;
    double alpha;

    NULL_CHECK(NULL)

    height = MagickGetImageHeight(self->wand);
    pi = NewPixelIterator(self->wand);

    for (r = 0; r < height; r++) {
        pixels = PixelGetNextIteratorRow(pi, &width);
        for (c = 0; c < width; c++) {
            alpha = PixelGetAlpha(pixels[c]);
            if (alpha < 1.00) {
                found = 1;
                c = width; r = height;
            }
        }
    }
    pi = DestroyPixelIterator(pi);
    if (found) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}
// }}}

// Image.normalize {{{

static PyObject *
magick_Image_normalize(magick_Image *self, PyObject *args) {
    NULL_CHECK(NULL)

    if (!MagickNormalizeImage(self->wand)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.add_border {{{

static PyObject *
magick_Image_add_border(magick_Image *self, PyObject *args) {
    Py_ssize_t dx, dy;
    PyObject *obj;
    magick_PixelWand *pw;
   
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!nn", &magick_PixelWandType, &obj, &dx, &dy)) return NULL;
    pw = (magick_PixelWand*)obj;
    if (!IsPixelWand(pw->wand)) { PyErr_SetString(PyExc_TypeError, "Invalid PixelWand"); return NULL; }

    if (!MagickBorderImage(self->wand, pw->wand, dx, dy)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.sharpen {{{

static PyObject *
magick_Image_sharpen(magick_Image *self, PyObject *args) {
    double radius, sigma;
   
    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "dd", &radius, &sigma)) return NULL;

    if (!MagickSharpenImage(self->wand, radius, sigma)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.quantize {{{

static PyObject *
magick_Image_quantize(magick_Image *self, PyObject *args) {
    Py_ssize_t number_colors, treedepth;
    int colorspace;
    PyObject *dither, *measure_error;

    NULL_CHECK(NULL)

   
    if (!PyArg_ParseTuple(args, "ninOO", &number_colors, &colorspace, &treedepth, &dither, &measure_error)) return NULL;

    if (!MagickQuantizeImage(self->wand, number_colors, colorspace, treedepth, PyObject_IsTrue(dither), PyObject_IsTrue(measure_error))) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.despeckle {{{

static PyObject *
magick_Image_despeckle(magick_Image *self, PyObject *args) {
    NULL_CHECK(NULL)

    if (!MagickDespeckleImage(self->wand)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.type {{{
static PyObject *
magick_Image_type_getter(magick_Image *self, void *closure) {
   NULL_CHECK(NULL)

    return Py_BuildValue("n", MagickGetImageType(self->wand));
}

static int
magick_Image_type_setter(magick_Image *self, PyObject *val, void *closure) {
    int type;

    NULL_CHECK(-1)

    if (val == NULL) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete image type");
        return -1;
    }

    if (!PyInt_Check(val)) {
        PyErr_SetString(PyExc_TypeError, "Type must be an integer");
        return -1;
    }

    type = (int)PyInt_AS_LONG(val);
    if (!MagickSetImageType(self->wand, type)) {
        PyErr_SetString(PyExc_ValueError, "Unknown image type");
        return -1;
    }

    return 0;
}

// }}}

// Image.destroy {{{

static PyObject *
magick_Image_destroy(magick_Image *self, PyObject *args) {
    NULL_CHECK(NULL)
    self->wand = DestroyMagickWand(self->wand);
    Py_RETURN_NONE;
}
// }}}

// Image.set_opacity {{{

static PyObject *
magick_Image_set_opacity(magick_Image *self, PyObject *args) {
    double opacity;
    NULL_CHECK(NULL)

   
    if (!PyArg_ParseTuple(args, "d", &opacity)) return NULL;

    if (!MagickSetImageOpacity(self->wand, opacity)) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image attr list {{{
static PyMethodDef magick_Image_methods[] = {
    {"destroy", (PyCFunction)magick_Image_destroy, METH_VARARGS,
    "Destroy the underlying ImageMagick Wand. WARNING: After using this method, all methods on this object will raise an exception."},

    {"identify", (PyCFunction)magick_Image_identify, METH_VARARGS,
     "Identify an image from a byte buffer (string)"
    },

    {"load", (PyCFunction)magick_Image_load, METH_VARARGS,
     "Load an image from a byte buffer (string)"
    },

    {"read", (PyCFunction)magick_Image_read, METH_VARARGS,
     "Read image from path. Path must be a bytestring in the filesystem encoding"
    },

    {"export", (PyCFunction)magick_Image_export, METH_VARARGS,
     "export(format) -> bytestring\n\n Export the image as the specified format"
    },

    {"create_canvas", (PyCFunction)magick_Image_create_canvas, METH_VARARGS,
     "create_canvas(width, height, bgcolor)\n\n"
            "Create a blank canvas\n"
    		"bgcolor should be an ImageMagick color specification (string)"
    },

    {"compose", (PyCFunction)magick_Image_compose, METH_VARARGS,
     "compose(img, left, top, op) \n\n Compose img using operation op at (left, top)"
    },

    {"texture", (PyCFunction)magick_Image_texture, METH_VARARGS,
     "texture(img)) \n\n Repeatedly tile img across and down the canvas."
    },

    {"set_opacity", (PyCFunction)magick_Image_set_opacity, METH_VARARGS,
     "set_opacity(opacity)) \n\n Set the opacity of this image (between 0.0 - transparent and 1.0 - opaque)"
    },

    {"copy", (PyCFunction)magick_Image_copy, METH_VARARGS,
     "copy(img) \n\n Copy img to self."
    },

    {"font_metrics", (PyCFunction)magick_Image_font_metrics, METH_VARARGS,
     "font_metrics(drawing_wand, text) \n\n Return font metrics for specified drawing wand and text."
    },

    {"annotate", (PyCFunction)magick_Image_annotate, METH_VARARGS,
     "annotate(drawing_wand, x, y, angle, text) \n\n Annotate image with text."
    },

    {"distort", (PyCFunction)magick_Image_distort, METH_VARARGS,
     "distort(method, arguments, best_fit) \n\n Distort image."
    },

    {"trim", (PyCFunction)magick_Image_trim, METH_VARARGS,
     "trim(fuzz) \n\n Trim image."
    },

    {"crop", (PyCFunction)magick_Image_crop, METH_VARARGS,
     "crop(width, height, x, y) \n\n Crop image."
    },

    {"set_page", (PyCFunction)magick_Image_set_page, METH_VARARGS,
     "set_page(width, height, x, y) \n\n Sets the page geometry of the image."
    },

    {"set_compression_quality", (PyCFunction)magick_Image_set_compression_quality, METH_VARARGS,
     "set_compression_quality(quality) \n\n Sets the compression quality when exporting the image."
    },

    {"has_transparent_pixels", (PyCFunction)magick_Image_has_transparent_pixels, METH_VARARGS,
     "has_transparent_pixels() \n\n Returns True iff image has a (semi-) transparent pixel"
    },

    {"thumbnail", (PyCFunction)magick_Image_thumbnail, METH_VARARGS,
     "thumbnail(width, height) \n\n Convert to a thumbnail of specified size."
    },

    {"set_border_color", (PyCFunction)magick_Image_set_border_color, METH_VARARGS,
     "set_border_color(pixel_wand) \n\n Set border color to the specified PixelWand."
    },

    {"rotate", (PyCFunction)magick_Image_rotate, METH_VARARGS,
     "rotate(background_pixel_wand, degrees) \n\n Rotate image by specified degrees."
    },
    {"flip", (PyCFunction)magick_Image_flip, METH_VARARGS,
     "flip(horizontal=False) \n\n Flip image about a vertical axis. If horizontal is True, flip about horizontal axis instead."
    },


    {"normalize", (PyCFunction)magick_Image_normalize, METH_VARARGS,
     "normalize() \n\n enhances the contrast of a color image by adjusting the pixels color to span the entire range of colors available."
    },

    {"add_border", (PyCFunction)magick_Image_add_border, METH_VARARGS,
     "add_border(pixel_wand, width, height) \n\n surrounds the image with a border of the color defined by the bordercolor pixel wand."
    },

    {"sharpen", (PyCFunction)magick_Image_sharpen, METH_VARARGS,
     "sharpen(radius, sigma) \n\n sharpens an image. We convolve the image with a Gaussian operator of the given radius and standard deviation (sigma). For reasonable results, the radius should be larger than sigma. Use a radius of 0 and MagickSharpenImage() selects a suitable radius for you." 
    },

    {"despeckle", (PyCFunction)magick_Image_despeckle, METH_VARARGS,
     "despeckle() \n\n reduces the speckle noise in an image while perserving the edges of the original image." 
    },

    {"quantize", (PyCFunction)magick_Image_quantize, METH_VARARGS,
     "quantize(number_colors, colorspace, treedepth, dither, measure_error) \n\n analyzes the colors within a reference image and chooses a fixed number of colors to represent the image. The goal of the algorithm is to minimize the color difference between the input and output image while minimizing the processing time." 
    },

    {NULL}  /* Sentinel */
};

static PyGetSetDef  magick_Image_getsetters[] = {
    {(char *)"size_", 
     (getter)magick_Image_size_getter, (setter)magick_Image_size_setter,
     (char *)"Image size (width, height). When setting pass in (width, height, filter, blur). See MagickResizeImage docs.",
     NULL},

    {(char *)"format_", 
     (getter)magick_Image_format_getter, (setter)magick_Image_format_setter,
     (char *)"Image format",
     NULL},

    {(char *)"type_", 
     (getter)magick_Image_type_getter, (setter)magick_Image_type_setter,
     (char *)"the image type: UndefinedType, BilevelType, GrayscaleType, GrayscaleMatteType, PaletteType, PaletteMatteType, TrueColorType, TrueColorMatteType, ColorSeparationType, ColorSeparationMatteType, or OptimizeType.",
     NULL},

    {NULL}  /* Sentinel */
};

// }}}


static PyTypeObject magick_ImageType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "magick.Image",            /*tp_name*/
    sizeof(magick_Image),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)magick_Image_dealloc, /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Images",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    magick_Image_methods,             /* tp_methods */
    0,             /* tp_members */
    magick_Image_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    magick_Image_new,                 /* tp_new */
}; // }}}

// Image.compose {{{
static PyObject *
magick_Image_compose(magick_Image *self, PyObject *args)
{
    PyObject *img, *op_;
    ssize_t left, top;
    CompositeOperator op;
    magick_Image *src;
    MagickBooleanType res = MagickFalse;

    NULL_CHECK(NULL)


    if (!PyArg_ParseTuple(args, "O!nnO", &magick_ImageType, &img, &left, &top, &op_)) return NULL;
    src = (magick_Image*)img;
    if (!IsMagickWand(src->wand)) {PyErr_SetString(PyExc_TypeError, "Not a valid ImageMagick wand"); return NULL;}

    op = (CompositeOperator)PyInt_AsSsize_t(op_);
    if (PyErr_Occurred() || op <= UndefinedCompositeOp) {
        PyErr_SetString(PyExc_TypeError, "Invalid composite operator");
        return NULL;
    }

    res = MagickCompositeImage(self->wand, src->wand, op, left, top);

    if (!res) return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}
// }}}

// Image.clone {{{
static PyObject *
magick_Image_copy(magick_Image *self, PyObject *args)
{
    PyObject *img;
    magick_Image *src;

    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!", &magick_ImageType, &img)) return NULL;
    src = (magick_Image*)img;
    if (!IsMagickWand(src->wand)) {PyErr_SetString(PyExc_TypeError, "Not a valid ImageMagick wand"); return NULL;}
    self->wand = DestroyMagickWand(self->wand);
    self->wand = CloneMagickWand(src->wand);
    if (self->wand == NULL) { return PyErr_NoMemory(); }

    Py_RETURN_NONE;
}
// }}}

// Image.texture {{{
static PyObject *
magick_Image_texture(magick_Image *self, PyObject *args) {
    PyObject *img;
    magick_Image *texture;

    NULL_CHECK(NULL)

    if (!PyArg_ParseTuple(args, "O!", &magick_ImageType, &img)) return NULL;
    texture = (magick_Image*)img;
    if (!IsMagickWand(texture->wand)) {PyErr_SetString(PyExc_TypeError, "Not a valid ImageMagick wand"); return NULL;}

    self->wand = MagickTextureImage(self->wand, texture->wand);

    Py_RETURN_NONE;
}

// }}}

// Module functions {{{

static PyObject *
magick_genesis(PyObject *self, PyObject *args)
{
    MagickWandGenesis();
    Py_RETURN_NONE;
}

static PyObject *
magick_terminus(PyObject *self, PyObject *args)
{
    MagickWandTerminus();
    Py_RETURN_NONE;
}


static PyMethodDef magick_methods[] = {
    {"genesis", magick_genesis, METH_VARARGS,
    "genesis()\n\n"
            "Initializes ImageMagick.\n"
    		"Must be called before any other use of this module is made. "
    },

    {"terminus", magick_terminus, METH_VARARGS,
    "terminus()\n\n"
            "Cleans up ImageMagick memory structures.\n"
    		"Must be called after you are done using this module. You can call genesis() again after this to resume using the module."
    },


    {NULL}  /* Sentinel */
};
// }}}

// Module initialization {{{
PyMODINIT_FUNC
initmagick(void) 
{
    PyObject* m;

    if (PyType_Ready(&magick_ImageType) < 0)
        return;
    if (PyType_Ready(&magick_DrawingWandType) < 0)
        return;
    if (PyType_Ready(&magick_PixelWandType) < 0)
        return;

    m = Py_InitModule3("magick", magick_methods,
                       "Wrapper for the ImageMagick imaging library");

    Py_INCREF(&magick_ImageType);
    PyModule_AddObject(m, "Image", (PyObject *)&magick_ImageType);
    Py_INCREF(&magick_DrawingWandType);
    PyModule_AddObject(m, "DrawingWand", (PyObject *)&magick_DrawingWandType);
    Py_INCREF(&magick_PixelWandType);
    PyModule_AddObject(m, "PixelWand", (PyObject *)&magick_PixelWandType);

    magick_add_module_constants(m);
    MagickWandGenesis();
}
// }}}

