#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define USING_SHARED_PODOFO
#include <podofo.h>
using namespace PoDoFo;

#include "global.h"

PyObject *pdf::Error = NULL;

static PyMethodDef podofo_methods[] = {
    {NULL}  /* Sentinel */
};

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


#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
static struct PyModuleDef podofo_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "podofo",
    .m_doc = "Wrapper for the PoDoFo PDF library",
    .m_size = -1,
    .m_methods = podofo_methods,
};

CALIBRE_MODINIT_FUNC PyInit_podofo(void) {
#else
#define INITERROR return
CALIBRE_MODINIT_FUNC initpodofo(void) {
#endif

    if (PyType_Ready(&pdf::PDFDocType) < 0)
        INITERROR;

    if (PyType_Ready(&pdf::PDFOutlineItemType) < 0)
        INITERROR;

    pdf::Error = PyErr_NewException((char*)"podofo.Error", NULL, NULL);
    if (pdf::Error == NULL) INITERROR;

    PdfError::SetLogMessageCallback((PdfError::LogMessageCallback*)&log_message);
    PdfError::EnableDebug(false);

#if PY_MAJOR_VERSION >= 3
    PyObject *mod = PyModule_Create(&podofo_module);
#else
    PyObject *mod = Py_InitModule3("podofo", podofo_methods, "Wrapper for the PoDoFo PDF library");
#endif

    if (mod == NULL) INITERROR;
    Py_INCREF(&pdf::PDFDocType);
    PyModule_AddObject(mod, "PDFDoc", (PyObject *)&pdf::PDFDocType);

    PyModule_AddObject(mod, "Error", pdf::Error);

#if PY_MAJOR_VERSION >= 3
    return mod;
#endif
}