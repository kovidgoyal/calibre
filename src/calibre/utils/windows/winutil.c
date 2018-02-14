/*
:mod:`winutil` -- Interface to Windows
============================================

.. module:: winutil
    :platform: Windows
    :synopsis: Various methods to interface with the operating system

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2008

This module contains utility functions to interface with the windows operating
system. It should be compiled with the same version of VisualStudio used to
compile python. It hasn't been tested with MinGW. We try to use unicode
wherever possible in this module.

.. function:: special_folder_path(csidl_id) -> path
    Get paths to common system folders.
    See windows documentation of SHGetFolderPath.
    The paths are returned as unicode objects. `csidl_id` should be one
    of the symbolic constants defined in this module. You can also `OR`
    a symbolic constant with :data:`CSIDL_FLAG_CREATE` to force the operating
    system to create a folder if it does not exist. For example::

        >>> from winutil import *
        >>> special_folder_path(CSIDL_APPDATA)
        u'C:\\Documents and Settings\\Kovid Goyal\\Application Data'
        >>>  special_folder_path(CSIDL_PERSONAL)
        u'C:\\Documents and Settings\\Kovid Goyal\\My Documents'

.. function:: argv() -> list of unicode command line arguments
    Get command line arguments as unicode objects. Note that the
    first argument will be the path to the interpreter, *not* the
    script being run. So to replace sys.argv, you should use
    `if len(sys.argv) > 1: sys.argv[1:] = winutil.argv()[1-len(sys.argv):]`

.. function:: internet_connected() -> Return True if there is an active
   internet connection.

*/


#define UNICODE
#include <Windows.h>
#include <Wininet.h>
#include <LMcons.h>
#include <locale.h>
#include <Python.h>
#include <structseq.h>
#include <timefuncs.h>
#include <shlobj.h>
#include <stdio.h>
#include <setupapi.h>
#include <devguid.h>
#include <cfgmgr32.h>
#include <stdarg.h>
#include <time.h>

#define PyStructSequence_GET_ITEM(op, i) \
    (((PyStructSequence *)(op))->ob_item[i])


#define BUFSIZE    512
#define MAX_DRIVES 26
static BOOL DEBUG = FALSE;

//#define debug(fmt, ...) if DEBUG printf(x, __VA_ARGS__);
void
debug(const char *fmt, ...) {
    va_list argList;
    va_start(argList, fmt);
    if (DEBUG) vprintf(fmt, argList);
    va_end(argList);
}

static void console_out(LPCWSTR fmt, LPCWSTR arg) {
    char *bfmt, *barg;
    int sz;

    sz = WideCharToMultiByte(CP_UTF8, 0, fmt, -1, NULL, 0, NULL, NULL);
    bfmt = (char*)calloc(sz+1, sizeof(char));
    WideCharToMultiByte(CP_UTF8, 0, fmt, -1, bfmt, sz, NULL, NULL);

    sz = WideCharToMultiByte(CP_UTF8, 0, arg, -1, NULL, 0, NULL, NULL);
    barg = (char*)calloc(sz+1, sizeof(char));
    WideCharToMultiByte(CP_UTF8, 0, arg, -1, barg, sz, NULL, NULL);

    if (bfmt != NULL && barg != NULL) {
        printf(bfmt, barg);
        fflush(stdout);
        free(bfmt); free(barg);
    }
}

static PyObject *
winutil_folder_path(PyObject *self, PyObject *args) {
    int res; DWORD dwFlags;
    PyObject *ans = NULL;
    TCHAR wbuf[MAX_PATH]; CHAR buf[4*MAX_PATH];
    memset(wbuf, 0, sizeof(TCHAR)*MAX_PATH); memset(buf, 0, sizeof(CHAR)*MAX_PATH);

    if (!PyArg_ParseTuple(args, "l", &dwFlags)) return NULL;

    res = SHGetFolderPath(NULL, dwFlags, NULL, 0, wbuf);
    if (res != S_OK) {
        if (res == E_FAIL) PyErr_SetString(PyExc_ValueError, "Folder does not exist.");
        PyErr_SetString(PyExc_ValueError, "Folder not valid");
        return NULL;
    }
    res = WideCharToMultiByte(CP_UTF8, 0, wbuf, -1, buf, 4*MAX_PATH, NULL, NULL);
    ans = PyUnicode_DecodeUTF8(buf, res-1, "strict");
    return ans;
}

static PyObject *
winutil_argv(PyObject *self, PyObject *args) {
    PyObject *argv, *v;
    LPWSTR *_argv;
    int argc, i;
    if (!PyArg_ParseTuple(args, "")) return NULL;
    _argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (_argv == NULL) { PyErr_NoMemory(); return NULL; }
    argv = PyList_New(argc);
    if (argv != NULL) {
        for (i = 0; i < argc; i++) {
            v = PyUnicode_FromWideChar(_argv[i], wcslen(_argv[i]));
            if ( v == NULL) {
                Py_DECREF(argv); argv = NULL; PyErr_NoMemory(); break;
            }
            PyList_SetItem(argv, i, v);
        }
    }
    LocalFree(_argv);
    return argv;
}


static LPVOID
format_last_error() {
    /* Format the last error as a string. The returned pointer should
       be freed with :cfunction:`LocalFree(lpMsgBuf)`. It can be printed with
       :cfunction:`printf("\n%ws\n", (LPCTSTR)lpMsgBuf)`.
    */

    LPVOID lpMsgBuf;
    FormatMessage(
    FORMAT_MESSAGE_ALLOCATE_BUFFER |
    FORMAT_MESSAGE_FROM_SYSTEM |
    FORMAT_MESSAGE_IGNORE_INSERTS,
    NULL,
    GetLastError(),
    0, // Default language
    (LPTSTR) &lpMsgBuf,
    0,
    NULL
    );
    return lpMsgBuf;
}

static PyObject *
winutil_set_debug(PyObject *self, PyObject *args) {
    PyObject *yes;
    if (!PyArg_ParseTuple(args, "O", &yes)) return NULL;
    DEBUG = (BOOL)PyObject_IsTrue(yes);
    return Py_None;
}

static int
gettmarg(PyObject *args, struct tm *p)
{
    int y;
    memset((void *) p, '\0', sizeof(struct tm));

    if (!PyArg_Parse(args, "(iiiiiiiii)",
             &y,
             &p->tm_mon,
             &p->tm_mday,
             &p->tm_hour,
             &p->tm_min,
             &p->tm_sec,
             &p->tm_wday,
             &p->tm_yday,
             &p->tm_isdst))
        return 0;
    if (y < 1900) {
        if (69 <= y && y <= 99)
            y += 1900;
        else if (0 <= y && y <= 68)
            y += 2000;
        else {
            PyErr_SetString(PyExc_ValueError,
                    "year out of range");
            return 0;
        }
    }
    p->tm_year = y - 1900;
    p->tm_mon--;
    p->tm_wday = (p->tm_wday + 1) % 7;
    p->tm_yday--;
    return 1;
}

static PyObject *
winutil_internet_connected(PyObject *self, PyObject *args) {
    DWORD flags;
    BOOL ans = InternetGetConnectedState(&flags, 0);
    if (ans) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyObject *
winutil_prepare_for_restart(PyObject *self, PyObject *args) {
    FILE *f1 = NULL, *f2 = NULL;
    if (stdout != NULL) fclose(stdout);
    if (stderr != NULL) fclose(stderr);
    _wfreopen_s(&f1, L"NUL", L"a+t", stdout);
    _wfreopen_s(&f2, L"NUL", L"a+t", stderr);
    Py_RETURN_NONE;
}

static PyObject *
winutil_get_max_stdio(PyObject *self, PyObject *args) {
    return Py_BuildValue("i", _getmaxstdio());
}

static PyObject *
winutil_set_max_stdio(PyObject *self, PyObject *args) {
    int num = 0;
    if (!PyArg_ParseTuple(args, "i", &num)) return NULL;
    if (_setmaxstdio(num) == -1) return PyErr_SetFromErrno(PyExc_ValueError);
    Py_RETURN_NONE;
}

static PyObject *
winutil_getenv(PyObject *self, PyObject *args) {
    const Py_UNICODE *q;
    if (!PyArg_ParseTuple(args, "u", &q)) return NULL;
    wchar_t *buf = NULL;
    size_t sz = 0;
    PyObject *ans = NULL;
    if (_wdupenv_s(&buf, &sz, q) != 0 || buf == NULL || sz == 0) { ans = Py_None; Py_INCREF(ans); }
    else ans = PyUnicode_FromWideChar(buf, sz - 1);
    if (buf) free(buf);
    return ans;
}

static PyObject*
winutil_move_file(PyObject *self, PyObject *args) {
    Py_UNICODE *a, *b;
    unsigned int flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH;
    if (!PyArg_ParseTuple(args, "uu|I", &a, &b, &flags)) return NULL;
    if (!MoveFileExW(a, b, flags)) { PyErr_SetFromWindowsErr(0); return NULL; }
    Py_RETURN_NONE;
}

static PyObject *
winutil_username(PyObject *self) {
    wchar_t buf[UNLEN + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetUserName(buf, &sz)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}

static PyObject *
winutil_temp_path(PyObject *self) {
    wchar_t buf[MAX_PATH + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetTempPath(sz, buf)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}


static PyObject *
winutil_locale_name(PyObject *self) {
    wchar_t buf[LOCALE_NAME_MAX_LENGTH + 1] = {0};
    if (!GetUserDefaultLocaleName(buf, sizeof(buf)/sizeof(buf[0]))) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}


static PyObject *
winutil_localeconv(PyObject *self) {
    struct lconv *d = localeconv();
#define W(name) #name, d->_W_##name
    return Py_BuildValue(
        "{su su su su su su su su}",
        W(decimal_point), W(thousands_sep), W(int_curr_symbol), W(currency_symbol),
        W(mon_decimal_point), W(mon_thousands_sep), W(positive_sign), W(negative_sign)
    );
#undef W
}


static PyObject *
winutil_strftime(PyObject *self, PyObject *args)
{
    PyObject *tup = NULL;
    struct tm buf;
    size_t buflen;
    wchar_t *outbuf = NULL;
    Py_UNICODE *fmt = NULL;
    int fmtlen;
    size_t i;
    memset((void *) &buf, 0, sizeof(buf));

    if (!PyArg_ParseTuple(args, "u#|O:strftime", &fmt, &fmtlen, &tup)) return NULL;

    if (tup == NULL) {
        time_t tt = time(NULL);
        if(localtime_s(&buf, &tt) != 0) {
            PyErr_SetString(PyExc_ValueError, "Failed to get localtime()");
            return NULL;
        }
    } else if (!gettmarg(tup, &buf)) return NULL;

    if (buf.tm_mon == -1) buf.tm_mon = 0;
    else if (buf.tm_mon < 0 || buf.tm_mon > 11) {
        PyErr_SetString(PyExc_ValueError, "month out of range");
        return NULL;
    }
    if (buf.tm_mday == 0) buf.tm_mday = 1;
    else if (buf.tm_mday < 0 || buf.tm_mday > 31) {
        PyErr_SetString(PyExc_ValueError, "day of month out of range");
        return NULL;
    }
    if (buf.tm_hour < 0 || buf.tm_hour > 23) {
        PyErr_SetString(PyExc_ValueError, "hour out of range");
        return NULL;
    }
    if (buf.tm_min < 0 || buf.tm_min > 59) {
        PyErr_SetString(PyExc_ValueError, "minute out of range");
        return NULL;
    }
    if (buf.tm_sec < 0 || buf.tm_sec > 61) {
        PyErr_SetString(PyExc_ValueError, "seconds out of range");
        return NULL;
    }
    /* tm_wday does not need checking of its upper-bound since taking
       ``% 7`` in gettmarg() automatically restricts the range. */
    if (buf.tm_wday < 0) {
        PyErr_SetString(PyExc_ValueError, "day of week out of range");
        return NULL;
    }
    if (buf.tm_yday == -1) buf.tm_yday = 0;
    else if (buf.tm_yday < 0 || buf.tm_yday > 365) {
        PyErr_SetString(PyExc_ValueError, "day of year out of range");
        return NULL;
    }
    if (buf.tm_isdst < -1 || buf.tm_isdst > 1) {
        PyErr_SetString(PyExc_ValueError,
                "daylight savings flag out of range");
        return NULL;
    }

    for (i = 5*(unsigned int)fmtlen; ; i += i) {
        outbuf = (wchar_t *)PyMem_Malloc(i*sizeof(wchar_t));
        if (outbuf == NULL) {
            PyErr_NoMemory(); return NULL;
        }
        buflen = wcsftime(outbuf, i, fmt, &buf);
        if (buflen > 0 || i >= 256 * (unsigned int)fmtlen) {
            /* If the buffer is 256 times as long as the format,
               it's probably not failing for lack of room!
               More likely, the format yields an empty result,
               e.g. an empty format, or %Z when the timezone
               is unknown. */
            PyObject *ret;
            ret = PyUnicode_FromWideChar(outbuf, buflen);
            PyMem_Free(outbuf);
            return ret;
        }
        PyMem_Free(outbuf);
        /* VisualStudio .NET 2005 does this properly */
        if (buflen == 0 && errno == EINVAL) {
            PyErr_SetString(PyExc_ValueError, "Invalid format string");
            return NULL;
        }
    }
    return NULL;
}


static PyMethodDef WinutilMethods[] = {
    {"special_folder_path", winutil_folder_path, METH_VARARGS,
    "special_folder_path(csidl_id) -> path\n\n"
            "Get paths to common system folders. "
            "See windows documentation of SHGetFolderPath. "
            "The paths are returned as unicode objects. csidl_id should be one "
            "of the symbolic constants defined in this module. You can also OR "
            "a symbolic constant with CSIDL_FLAG_CREATE to force the operating "
            "system to create a folder if it does not exist."},

    {"argv", winutil_argv, METH_VARARGS,
    "argv() -> list of command line arguments\n\n"
            "Get command line arguments as unicode objects. Note that the "
            "first argument will be the path to the interpreter, *not* the "
            "script being run. So to replace sys.argv, you should use "
            "sys.argv[1:] = argv()[1:]."},

    {"set_debug", winutil_set_debug, METH_VARARGS,
            "set_debug(bool)\n\nSet debugging mode."
    },

    {"strftime", winutil_strftime, METH_VARARGS,
        "strftime(format[, tuple]) -> string\n\
\n\
Convert a time tuple to a string according to a format specification.\n\
See the library reference manual for formatting codes. When the time tuple\n\
is not present, current time as returned by localtime() is used. format must\n\
be a unicode string. Returns unicode strings."
     },

    {"internet_connected", winutil_internet_connected, METH_VARARGS,
        "internet_connected()\n\nReturn True if there is an active internet connection"
    },

    {"prepare_for_restart", winutil_prepare_for_restart, METH_VARARGS,
        "prepare_for_restart()\n\nRedirect output streams so that the child process does not lock the temp files"
    },

    {"getmaxstdio", winutil_get_max_stdio, METH_VARARGS,
        "getmaxstdio()\n\nThe maximum number of open file handles."
    },

    {"setmaxstdio", winutil_set_max_stdio, METH_VARARGS,
        "setmaxstdio(num)\n\nSet the maximum number of open file handles."
    },

    {"getenv", (PyCFunction)winutil_getenv, METH_VARARGS,
        "getenv(name)\n\nGet the value of the specified env var as a unicode string."
    },

    {"username", (PyCFunction)winutil_username, METH_NOARGS,
        "username()\n\nGet the current username as a unicode string."
    },

    {"temp_path", (PyCFunction)winutil_temp_path, METH_NOARGS,
        "temp_path()\n\nGet the current temporary dir as a unicode string."
    },

    {"locale_name", (PyCFunction)winutil_locale_name, METH_NOARGS,
        "locale_name()\n\nGet the current locale name as a unicode string."
    },

    {"localeconv", (PyCFunction)winutil_localeconv, METH_NOARGS,
        "localeconv()\n\nGet the locale conventions as unicode strings."
    },

    {"move_file", (PyCFunction)winutil_move_file, METH_VARARGS,
        "move_file()\n\nRename the specified file."
    },

    {NULL, NULL, 0, NULL}
};

CALIBRE_MODINIT_FUNC
initwinutil(void) {
    PyObject *m;
    m = Py_InitModule3("winutil", WinutilMethods,
    "Defines utility methods to interface with windows."
    );
    if (m == NULL) return;

    PyModule_AddIntConstant(m, "CSIDL_ADMINTOOLS", CSIDL_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_APPDATA", CSIDL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_ADMINTOOLS", CSIDL_COMMON_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_APPDATA", CSIDL_COMMON_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_DOCUMENTS", CSIDL_COMMON_DOCUMENTS);
    PyModule_AddIntConstant(m, "CSIDL_COOKIES", CSIDL_COOKIES);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_CREATE", CSIDL_FLAG_CREATE);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_DONT_VERIFY", CSIDL_FLAG_DONT_VERIFY);
    PyModule_AddIntConstant(m, "CSIDL_FONTS", CSIDL_FONTS);
    PyModule_AddIntConstant(m, "CSIDL_HISTORY", CSIDL_HISTORY);
    PyModule_AddIntConstant(m, "CSIDL_INTERNET_CACHE", CSIDL_INTERNET_CACHE);
    PyModule_AddIntConstant(m, "CSIDL_LOCAL_APPDATA", CSIDL_LOCAL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_MYPICTURES", CSIDL_MYPICTURES);
    PyModule_AddIntConstant(m, "CSIDL_PERSONAL", CSIDL_PERSONAL);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES", CSIDL_PROGRAM_FILES);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES_COMMON", CSIDL_PROGRAM_FILES_COMMON);
    PyModule_AddIntConstant(m, "CSIDL_SYSTEM", CSIDL_SYSTEM);
    PyModule_AddIntConstant(m, "CSIDL_WINDOWS", CSIDL_WINDOWS);
    PyModule_AddIntConstant(m, "CSIDL_PROFILE", CSIDL_PROFILE);

}
