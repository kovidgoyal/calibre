#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

#include "global.h"

PyObject *pdf::Error = NULL;

class PyLogMessage : public PdfError::LogMessageCallback {

    public:
        ~PyLogMessage() {}

        void LogMessage(ELogSeverity severity, const char* prefix, const char* msg, va_list & args ) {
            if (severity > eLogSeverity_Warning) return;
            if (prefix)
                fprintf(stderr, "%s", prefix);

            vfprintf(stderr, msg, args);
        }

        void LogMessage(ELogSeverity severity, const wchar_t* prefix, const wchar_t* msg, va_list & args ) {
            if (severity > eLogSeverity_Warning) return;
            if (prefix)
                fwprintf(stderr, prefix);

            vfwprintf(stderr, msg, args);
        }
};

PyLogMessage log_message;

static char podofo_doc[] = "Wrapper for the PoDoFo PDF library";

static int
exec_module(PyObject *m) {
    if (PyType_Ready(&pdf::PDFDocType) < 0) return -1;
    if (PyType_Ready(&pdf::PDFOutlineItemType) < 0) return -1;

    pdf::Error = PyErr_NewException((char*)"podofo.Error", NULL, NULL);
    if (pdf::Error == NULL) return -1;
    PyModule_AddObject(m, "Error", pdf::Error);

    PdfError::SetLogMessageCallback((PdfError::LogMessageCallback*)&log_message);
    PdfError::EnableDebug(false);

    Py_INCREF(&pdf::PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&pdf::PDFDocType);
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
