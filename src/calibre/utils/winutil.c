#define UNICODE
#include <shlobj.h>
#include <Windows.h>
#include <Python.h>
#include <stdio.h>


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
    LPSTR buf;
    int argc, i, bytes;
    if (!PyArg_ParseTuple(args, "")) return NULL;
    _argv = CommandLineToArgvW(GetCommandLine(), &argc);
    if (_argv == NULL) { PyErr_SetString(PyExc_RuntimeError, "Out of memory."); return NULL; }
    argv = PyList_New(argc);
    if (argv != NULL) {
        for (i = 0; i < argc; i++) {
            bytes = WideCharToMultiByte(CP_UTF8, 0, _argv[i], -1, NULL, 0, NULL, NULL);
            buf = (LPSTR)PyMem_Malloc(sizeof(CHAR)*bytes);
            if (buf == NULL) { Py_DECREF(argv); argv = NULL; break; }
            WideCharToMultiByte(CP_UTF8, 0, _argv[i], -1, buf, bytes, NULL, NULL);
            v = PyUnicode_DecodeUTF8(buf, bytes-1, "strict");
            PyMem_Free(buf);
            if (v == NULL) { Py_DECREF(argv); argv = NULL; break; }
            PyList_SetItem(argv, i, v);
        }
    }
    LocalFree(_argv);
    return argv;
}

static PyMethodDef WinutilMethods[] = {
    {"folder_path", winutil_folder_path, METH_VARARGS, 
    "folder_path(csidl_id) -> path\n\n"
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

    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
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
    PyModule_AddIntConstant(m, "CSIDL_HISTORY", CSIDL_HISTORY);
    PyModule_AddIntConstant(m, "CSIDL_INTERNET_CACHE", CSIDL_INTERNET_CACHE);
    PyModule_AddIntConstant(m, "CSIDL_LOCAL_APPDATA", CSIDL_LOCAL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_MYPICTURES", CSIDL_MYPICTURES);
    PyModule_AddIntConstant(m, "CSIDL_PERSONAL", CSIDL_PERSONAL);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES", CSIDL_PROGRAM_FILES);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES_COMMON", CSIDL_PROGRAM_FILES_COMMON);
    PyModule_AddIntConstant(m, "CSIDL_SYSTEM", CSIDL_SYSTEM);
    PyModule_AddIntConstant(m, "CSIDL_WINDOWS", CSIDL_WINDOWS);
    
}
    
