#define UNICODE
#include <Python.h>

#include <stdlib.h>
#include <fcntl.h>
#include <stdio.h>
#define _USE_MATH_DEFINES
#include <math.h>
#include <string.h>

#define MIN(x, y) ((x < y) ? x : y)
#define MAX(x, y) ((x > y) ? x : y)
#define CLAMP(value, lower, upper) ((value > upper) ? upper : ((value < lower) ? lower : value))
#define STRIDE(width, r, c) ((width * (r)) + (c))

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
        if(a > 1) precision = MIN(MAX(0, 6-(int)log10(a)), 6);
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

static void calculate_gaussian_kernel(Py_ssize_t size, double *kernel, double radius) {
    const double sqr = radius * radius;
    const double factor = 1.0 / (2 * M_PI * sqr);
    const double denom = 2 * sqr;
    double *t, sum = 0;
    Py_ssize_t r, c, center = size / 2;

    for (r = 0; r < size; r++) {
        t = kernel + (r * size);
        for (c = 0; c < size; c++) {
            t[c] = factor * pow(M_E, - ( ( (r - center) * (r - center) + (c - center) * (c - center) ) / denom ));
        }
    }

    // Normalize matrix
    for (r = 0; r < size * size; r++) sum += kernel[r];
    sum = 1 / sum;
    for (r = 0; r < size * size; r++) kernel[r] *= sum;
}

static PyObject*
speedup_create_texture(PyObject *self, PyObject *args, PyObject *kw) {
    PyObject *ret = NULL;
    Py_ssize_t width, height, weight = 3, i, j, r, c, half_weight;
    double pixel, *mask = NULL, radius = 1, *kernel = NULL, blend_alpha = 0.1;
    float density = 0.7f;
    unsigned char base_r, base_g, base_b, blend_r = 0, blend_g = 0, blend_b = 0, *ppm = NULL, *t = NULL;
    char header[100] = {0};
    static char* kwlist[] = {"blend_red", "blend_green", "blend_blue", "blend_alpha", "density", "weight", "radius", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kw, "nnbbb|bbbdfnd", kwlist, &width, &height, &base_r, &base_g, &base_b, &blend_r, &blend_g, &blend_b, &blend_alpha, &density, &weight, &radius)) return NULL;
    if (weight % 2 != 1 || weight < 1) { PyErr_SetString(PyExc_ValueError, "The weight must be an odd positive number"); return NULL; }
    if (radius <= 0) { PyErr_SetString(PyExc_ValueError, "The radius must be positive"); return NULL; }
    if (width > 100000 || height > 10000) { PyErr_SetString(PyExc_ValueError, "The width or height is too large"); return NULL; }
    if (width < 1 || height < 1) { PyErr_SetString(PyExc_ValueError, "The width or height is too small"); return NULL; }
    snprintf(header, 99, "P6\n%d %d\n255\n", (int)width, (int)height);

    kernel = (double*)calloc(weight * weight, sizeof(double));
    if (kernel == NULL) { PyErr_NoMemory(); return NULL; }
    mask = (double*)calloc(width * height, sizeof(double));
    if (mask == NULL) { free(kernel); PyErr_NoMemory(); return NULL;}
    ppm = (unsigned char*)calloc(strlen(header) + (3 * width * height), sizeof(unsigned char));
    if (ppm == NULL) { free(kernel); free(mask); PyErr_NoMemory(); return NULL; }

    calculate_gaussian_kernel(weight, kernel, radius);

    // Random noise, noisy pixels are blend_alpha, other pixels are 0
    for (i = 0; i < width * height; i++) {
        if (((float)(rand()) / RAND_MAX) <= density) mask[i] = blend_alpha;
    }

    // Blur the noise using the gaussian kernel
    half_weight = weight / 2;
    for (r = 0; r < height; r++) {
        for (c = 0; c < width; c++) {
            pixel = 0;
            for (i = -half_weight; i <= half_weight; i++) {
                for (j = -half_weight; j <= half_weight; j++) {
                    pixel += (*(mask + STRIDE(width, CLAMP(r + i, 0, height - 1), CLAMP(c + j, 0, width - 1)))) * (*(kernel + STRIDE(weight, half_weight + i, half_weight + j)));
                }
            }
            *(mask + STRIDE(width, r, c)) = CLAMP(pixel, 0, 1);
        }
    }

    // Create the texture in PPM (P6) format 
    memcpy(ppm, header, strlen(header));
    t = ppm + strlen(header);
    for (i = 0, j = 0; j < width * height; i += 3, j += 1) {
#define BLEND(src, dest) ( ((unsigned char)(src * mask[j])) + ((unsigned char)(dest * (1 - mask[j]))) )
        t[i] = BLEND(blend_r, base_r);
        t[i+1] = BLEND(blend_g, base_g);
        t[i+2] = BLEND(blend_b, base_b);
    }

    ret = Py_BuildValue("s", ppm);
    free(mask); mask = NULL;
    free(kernel); kernel = NULL;
    free(ppm); ppm = NULL;
    return ret;
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

    {"create_texture", (PyCFunction)speedup_create_texture, METH_VARARGS | METH_KEYWORDS,
        "create_texture(width, height, red, green, blue, blend_red=0, blend_green=0, blend_blue=0, blend_alpha=0.1, density=0.7, weight=3, radius=1)\n\n"
            "Create a texture of the specified width and height from the specified color."
            " The texture is created by blending in random noise of the specified blend color into a flat image."
            " All colors are numbers between 0 and 255. 0 <= blend_alpha <= 1 with 0 being fully transparent."
            " 0 <= density <= 1 is used to control the amount of noise in the texture."
            " weight and radius control the Gaussian convolution used for blurring of the noise. weight must be an odd positive integer. Increasing the weight will tend to blur out the noise. Decreasing it will make it sharper."
            " This function returns an image (bytestring) in the PPM format as the texture."
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
