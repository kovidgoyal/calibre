#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

#include "global.h"
#include <iostream>

PyObject *pdf::Error = NULL;

static char podofo_doc[] = "Wrapper for the PoDoFo PDF library";

static void
pdf_log_message(PdfLogSeverity logSeverity, const std::string_view& msg) {
    if (logSeverity == PdfLogSeverity::Error || logSeverity == PdfLogSeverity::Warning) {
        const char *level = logSeverity == PdfLogSeverity::Error ? "ERROR" : "WARNING";
        std::cerr << "PoDoFo" << level << ": " << msg << std::endl;
    }
}

static int
exec_module(PyObject *m) {
    if (PyType_Ready(&pdf::PDFDocType) < 0) return -1;
    if (PyType_Ready(&pdf::PDFOutlineItemType) < 0) return -1;

    pdf::Error = PyErr_NewException((char*)"podofo.Error", NULL, NULL);
    if (pdf::Error == NULL) return -1;
    PyModule_AddObject(m, "Error", pdf::Error);

    Py_INCREF(&pdf::PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&pdf::PDFDocType);

    PdfCommon::SetLogMessageCallback(pdf_log_message);
	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_podofo(void) {
	module_def.m_name = "podofo";
	module_def.m_doc = podofo_doc;
	module_def.m_slots = slots;
	return PyModuleDef_Init(&module_def);
}
