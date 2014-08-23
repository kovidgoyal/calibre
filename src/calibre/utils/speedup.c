#define UNICODE
#include <Python.h>

#include <stdlib.h>
#include <fcntl.h>
#include <stdio.h>

#define min(x, y) ((x < y) ? x : y)
#define max(x, y) ((x > y) ? x : y)

static PyObject *
speedup_parse_date(PyObject *self, PyObject *args) {
    const char *raw, *orig, *tz;
    char *end;
    long year, month, day, hour, minute, second, tzh = 0, tzm = 0, sign = 0;
    size_t len;
    if(!PyArg_ParseTuple(args, "s", &raw)) return NULL;
    while ((*raw == ' ' || *raw == '\t' || *raw == '\n' || *raw == '\r' || *raw == '\f' || *raw == '\v') && *raw != 0) raw++;
    len = strlen(raw);
    if (len < 19) Py_RETURN_NONE;

    orig = raw;

    year = strtol(raw, &end, 10);
    if ((end - raw) != 4) Py_RETURN_NONE;
    raw += 5;
    

    month = strtol(raw, &end, 10);
    if ((end - raw) != 2) Py_RETURN_NONE;
    raw += 3;

    day = strtol(raw, &end, 10);
    if ((end - raw) != 2) Py_RETURN_NONE;
    raw += 3;
    
    hour = strtol(raw, &end, 10);
    if ((end - raw) != 2) Py_RETURN_NONE;
    raw += 3;

    minute = strtol(raw, &end, 10);
    if ((end - raw) != 2) Py_RETURN_NONE;
    raw += 3;

    second = strtol(raw, &end, 10);
    if ((end - raw) != 2) Py_RETURN_NONE;

    tz = orig + len - 6;

    if (*tz == '+') sign = +1;
    if (*tz == '-') sign = -1;
    if (sign != 0) {
        // We have TZ info
        tz += 1;

        tzh = strtol(tz, &end, 10);
        if ((end - tz) != 2) Py_RETURN_NONE;
        tz += 3;

        tzm = strtol(tz, &end, 10);
        if ((end - tz) != 2) Py_RETURN_NONE;
    }

    return Py_BuildValue("lllllll", year, month, day, hour, minute, second,
            (tzh*60 + tzm)*sign*60);
}


static PyObject*
speedup_pdf_float(PyObject *self, PyObject *args) {
    double f = 0.0, a = 0.0;
    char *buf = "0", *dot;
    void *free_buf = NULL; 
    int precision = 6, l = 0;
    PyObject *ret;

    if(!PyArg_ParseTuple(args, "d", &f)) return NULL;

    a = fabs(f);

    if (a > 1.0e-7) {
        if(a > 1) precision = min(max(0, 6-(int)log10(a)), 6);
        buf = PyOS_double_to_string(f, 'f', precision, 0, NULL);
        if (buf != NULL) {
            free_buf = (void*)buf;
            if (precision > 0) {
                l = strlen(buf) - 1;
                while (l > 0 && buf[l] == '0') l--;
                if (buf[l] == ',' || buf[l] == '.') buf[l] = 0;
                else buf[l+1] = 0;
                if ( (dot = strchr(buf, ',')) ) *dot = '.';
            }
        } else if (!PyErr_Occurred()) PyErr_SetString(PyExc_TypeError, "Float->str failed.");
    }

    ret = PyUnicode_FromString(buf);
    if (free_buf != NULL) PyMem_Free(free_buf);
    return ret;
}

static PyObject*
speedup_detach(PyObject *self, PyObject *args) {
    char *devnull = NULL;
    if (!PyArg_ParseTuple(args, "s", &devnull)) return NULL;
    if (freopen(devnull, "r", stdin) == NULL) return PyErr_SetFromErrno(PyExc_EnvironmentError);
    if (freopen(devnull, "w", stdout) == NULL) return PyErr_SetFromErrno(PyExc_EnvironmentError);
    if (freopen(devnull, "w", stderr) == NULL)  return PyErr_SetFromErrno(PyExc_EnvironmentError);
    Py_RETURN_NONE;
}

static PyMethodDef speedup_methods[] = {
    {"parse_date", speedup_parse_date, METH_VARARGS,
        "parse_date()\n\nParse ISO dates faster."
    },

    {"pdf_float", speedup_pdf_float, METH_VARARGS,
        "pdf_float()\n\nConvert float to a string representation suitable for PDF"
    },

    {"detach", speedup_detach, METH_VARARGS,
        "detach()\n\nRedirect the standard I/O stream to the specified file (usually os.devnull)"
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initspeedup(void) {
    PyObject *m;
    m = Py_InitModule3("speedup", speedup_methods,
    "Implementation of methods in C for speed."
    );
    if (m == NULL) return;
#ifdef O_CLOEXEC
    PyModule_AddIntConstant(m, "O_CLOEXEC", O_CLOEXEC);
#endif
}
