/*
 * utils.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace wpd;

PyObject *wpd::hresult_set_exc(const char *msg, HRESULT hr) {
    PyObject *o = NULL, *mess;
    LPWSTR desc = NULL;

    FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM|FORMAT_MESSAGE_ALLOCATE_BUFFER|FORMAT_MESSAGE_IGNORE_INSERTS,
            NULL, hr, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPWSTR)&desc, 0, NULL);
    if (desc == NULL) {
        o = PyUnicode_FromString("No description available.");
    } else {
        o = PyUnicode_FromWideChar(desc, wcslen(desc));
        LocalFree(desc);
    }
    if (o == NULL) return PyErr_NoMemory();
    mess = PyUnicode_FromFormat("%s: hr=%lu facility=%u error_code=%u description: %U", msg, hr, HRESULT_FACILITY(hr), HRESULT_CODE(hr), o);
    Py_XDECREF(o);
    if (mess == NULL) return PyErr_NoMemory();
    PyErr_SetObject(WPDError, mess);
    Py_DECREF(mess);
    return NULL;
}

wchar_t *wpd::unicode_to_wchar(PyObject *o) {
    wchar_t *buf;
    Py_ssize_t len;
    if (o == NULL) return NULL;
    if (!PyUnicode_Check(o)) {PyErr_Format(PyExc_TypeError, "The python object must be a unicode object"); return NULL;}
    len = PyUnicode_GET_SIZE(o);
    buf = (wchar_t *)calloc(len+2, sizeof(wchar_t));
    if (buf == NULL) { PyErr_NoMemory(); return NULL; }
    len = PyUnicode_AsWideChar(o, buf, len);
    if (len == -1) { free(buf); PyErr_Format(PyExc_TypeError, "Invalid python unicode object."); return NULL; }
    return buf;
}

PyObject *wpd::wchar_to_unicode(const wchar_t *o) {
    PyObject *ans;
    if (o == NULL) return NULL;
    ans = PyUnicode_FromWideChar(o, wcslen(o));
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}

int wpd::pump_waiting_messages() {
	UINT firstMsg = 0, lastMsg = 0;
    MSG msg;
	int result = 0;
	// Read all of the messages in this next loop,
	// removing each message as we read it.
	while (PeekMessage(&msg, NULL, firstMsg, lastMsg, PM_REMOVE)) {
		// If it's a quit message, we're out of here.
		if (msg.message == WM_QUIT) {
			result = 1;
			break;
		}
		// Otherwise, dispatch the message.
		DispatchMessage(&msg);
	} // End of PeekMessage while loop

    return result;
}
