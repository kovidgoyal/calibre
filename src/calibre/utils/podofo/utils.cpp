/*
 * utils.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <sstream>

using namespace pdf;

void
pdf::podofo_set_exception(const PdfError &err) {
    const char *msg = err.what();
    std::stringstream stream;
    stream << msg << "\n";
    const PdErrorInfoStack &s = err.GetCallStack();
    for (auto info : s) {
        stream << "File: " << info.GetFilePath() << " Line: " << info.GetLine() << " " << info.GetInformation() << "\n";
    }
    PyErr_SetString(Error, stream.str().c_str());
}

PyObject *
pdf::podofo_convert_pdfstring(const PdfString &s) {
    return PyUnicode_FromString(s.GetString().c_str());
}

const PdfString
pdf::podofo_convert_pystring(PyObject *val) {
    return PdfString(reinterpret_cast<const char*>(PyUnicode_AsUTF8(val)));
}
