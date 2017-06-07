/*
 * monotonic.c
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#include <Python.h>

/* To millisecond (10^-3) */
#define SEC_TO_MS 1000

/* To microseconds (10^-6) */
#define MS_TO_US 1000
#define SEC_TO_US (SEC_TO_MS * MS_TO_US)

/* To nanoseconds (10^-9) */
#define US_TO_NS 1000
#define MS_TO_NS (MS_TO_US * US_TO_NS)
#define SEC_TO_NS (SEC_TO_MS * MS_TO_NS)

/* Conversion from nanoseconds */
#define NS_TO_MS (1000 * 1000)
#define NS_TO_US (1000)

#ifdef _MSC_VER
#include <Windows.h>

static PyObject* monotonic(PyObject *self, PyObject *args) {
	return PyFloat_FromDouble(((double)GetTickCount64())/SEC_TO_MS);
}

/* QueryPerformanceCounter() is wildly inaccurate, so we use the more stable
 * the lower resolution GetTickCount64() (this is what python 3.x uses)
 * static LARGE_INTEGER frequency = {0}, ts = {0};
 * static PyObject* monotonic(PyObject *self, PyObject *args) { 
 * 	if (!QueryPerformanceCounter(&ts)) { PyErr_SetFromWindowsErr(0); return NULL; }
 * 	return PyFloat_FromDouble(((double)ts.QuadPart)/frequency.QuadPart); 
 * } 
 */

#elif defined(__APPLE__)
#include <mach/mach_time.h>
static mach_timebase_info_data_t timebase = {0};
static PyObject* monotonic(PyObject *self, PyObject *args) {
	return PyFloat_FromDouble(((double)(mach_absolute_time() * timebase.numer) / timebase.denom)/SEC_TO_NS);
}

#else
#include <time.h>
static struct timespec ts = {0};
#ifdef CLOCK_HIGHRES
const static clockid_t clk_id = CLOCK_HIGHRES;
#elif defined(CLOCK_MONOTONIC_RAW)
const static clockid_t clk_id = CLOCK_MONOTONIC_RAW;
#else
const static clockid_t clk_id = CLOCK_MONOTONIC;
#endif
static PyObject* monotonic(PyObject *self, PyObject *args) {
	if (clock_gettime(clk_id, &ts) != 0) { PyErr_SetFromErrno(PyExc_OSError); return NULL; }
	return PyFloat_FromDouble((((double)ts.tv_nsec) / SEC_TO_NS) + (double)ts.tv_sec);
}
#endif

static PyMethodDef monotonic_methods[] = {
	{"monotonic", monotonic, METH_NOARGS,
		"monotonic()\n\nReturn a monotonically increasing time value."
	},

    {NULL, NULL, 0, NULL}
};

CALIBRE_MODINIT_FUNC
initmonotonic(void) {
    PyObject *m;
#ifdef _MSC_VER
	/* if(!QueryPerformanceFrequency(&frequency)) { PyErr_SetFromWindowsErr(0); return; } */
#endif
#ifdef __APPLE__
	mach_timebase_info(&timebase);
#endif
    m = Py_InitModule3("monotonic", monotonic_methods,
    "Implementation of time.monotonic() in C for speed"
    );
    if (m == NULL) return;
}

