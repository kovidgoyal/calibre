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

static PyMethodDef podofo_methods[] = {
    {NULL}  /* Sentinel */
};

#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
#define INITMODULE PyModule_Create(&podofo_module)
static struct PyModuleDef podofo_module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "podofo",
    /* m_doc      */ podofo_doc,
    /* m_size     */ -1,
    /* m_methods  */ podofo_methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};
CALIBRE_MODINIT_FUNC PyInit_podofo(void) {
#else
#define INITERROR return
#define INITMODULE Py_InitModule3("podofo", podofo_methods, podofo_doc)
CALIBRE_MODINIT_FUNC initpodofo(void) {
#endif

    PyObject* m;

    if (PyType_Ready(&pdf::PDFDocType) < 0) {
        INITERROR;
    }

    if (PyType_Ready(&pdf::PDFOutlineItemType) < 0) {
        INITERROR;
    }

    pdf::Error = PyErr_NewException((char*)"podofo.Error", NULL, NULL);
    if (pdf::Error == NULL) {
        INITERROR;
    }

    PdfError::SetLogMessageCallback((PdfError::LogMessageCallback*)&log_message);

    PdfError::EnableDebug(false);

    m = INITMODULE;
    if (m == NULL) {
        INITERROR;
    }

    Py_INCREF(&pdf::PDFDocType);
    PyModule_AddObject(m, "PDFDoc", (PyObject *)&pdf::PDFDocType);

    PyModule_AddObject(m, "Error", pdf::Error);

#if PY_MAJOR_VERSION >= 3
    return m;
#endif
}
