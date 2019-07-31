/*
 * utils.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace pdf;

void
pdf::podofo_set_exception(const PdfError &err) {
    const char *msg = PdfError::ErrorMessage(err.GetError());
    if (msg == NULL) msg = err.what();
    std::stringstream stream;
    stream << msg << "\n";
    const TDequeErrorInfo &s = err.GetCallstack();
    for (TDequeErrorInfo::const_iterator it = s.begin(); it != s.end(); it++) {
        const PdfErrorInfo &info = (*it);
        stream << "File: " << info.GetFilename() << " Line: " << info.GetLine() << " " << info.GetInformation() << "\n";
    }
    PyErr_SetString(Error, stream.str().c_str());
}

PyObject *
pdf::podofo_convert_pdfstring(const PdfString &s) {
    return PyUnicode_FromString(s.GetStringUtf8().c_str());
}

const PdfString
pdf::podofo_convert_pystring(PyObject *val) {
#if PY_MAJOR_VERSION > 2
    return PdfString(reinterpret_cast<const pdf_utf8*>(PyUnicode_AsUTF8(val)));
#else
    pyunique_ptr temp(PyUnicode_AsUTF8String(val));
    if (!temp) throw std::bad_alloc();
    return PdfString(reinterpret_cast<const pdf_utf8*>(PyBytes_AS_STRING(temp.get())));
#endif
}
