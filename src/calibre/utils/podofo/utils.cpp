/*
 * utils.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <sstream>
#include <stdexcept>
#include <string_view>

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
    Py_ssize_t len;
    const char *data = PyUnicode_AsUTF8AndSize(val, &len);
    if (data == NULL) throw std::runtime_error("Failed to convert python string to UTF-8, possibly not a string object");
    return PdfString(std::string_view(data, len));
}
