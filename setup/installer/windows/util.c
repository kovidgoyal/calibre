/*
 * Copyright 2009 Kovid Goyal
 * The memimporter code is taken from the py2exe project
 */

#include "util.h"

#include <delayimp.h>
#include <io.h>
#include <fcntl.h>


static char GUI_APP = 0;
static char python_dll[] = PYDLL;

void set_gui_app(char yes) { GUI_APP = yes; }
char is_gui_app() { return GUI_APP; }

int calibre_show_python_error(const wchar_t *preamble, int code);

// memimporter {{{

#include "MemoryModule.h"

static char **DLL_Py_PackageContext = NULL;
static PyObject **DLL_ImportError = NULL;
static char module_doc[] =
"Importer which can load extension modules from memory";


static void *memdup(void *ptr, Py_ssize_t size)
{
	void *p = malloc(size);
	if (p == NULL)
		return NULL;
	memcpy(p, ptr, size);
	return p;
}

/*
  Be sure to detect errors in FindLibrary - undetected errors lead to
  very strange behaviour.
*/
static void* FindLibrary(char *name, PyObject *callback)
{
	PyObject *result;
	char *p;
	Py_ssize_t size;

	if (callback == NULL)
		return NULL;
	result = PyObject_CallFunction(callback, "s", name);
	if (result == NULL) {
		PyErr_Clear();
		return NULL;
	}
	if (-1 == PyString_AsStringAndSize(result, &p, &size)) {
		PyErr_Clear();
		Py_DECREF(result);
		return NULL;
	}
	p = memdup(p, size);
	Py_DECREF(result);
	return p;
}

static PyObject *
import_module(PyObject *self, PyObject *args)
{
	char *data;
	int size;
	char *initfuncname;
	char *modname;
	char *pathname;
	HMEMORYMODULE hmem;
	FARPROC do_init;

	char *oldcontext;

	/* code, initfuncname, fqmodulename, path */
	if (!PyArg_ParseTuple(args, "s#sss:import_module",
			      &data, &size,
			      &initfuncname, &modname, &pathname))
		return NULL;
	hmem = MemoryLoadLibrary(data);
	if (!hmem) {
		PyErr_Format(*DLL_ImportError,
			     "MemoryLoadLibrary() failed loading %s", pathname);
		return NULL;
	}
	do_init = MemoryGetProcAddress(hmem, initfuncname);
	if (!do_init) {
		MemoryFreeLibrary(hmem);
		PyErr_Format(*DLL_ImportError,
			     "Could not find function %s in memory loaded pyd", initfuncname);
		return NULL;
	}

    oldcontext = *DLL_Py_PackageContext;
	*DLL_Py_PackageContext = modname;
	do_init();
	*DLL_Py_PackageContext = oldcontext;
	if (PyErr_Occurred())
		return NULL;
	/* Retrieve from sys.modules */
	return PyImport_ImportModule(modname);
}

static PyMethodDef methods[] = {
	{ "import_module", import_module, METH_VARARGS,
	  "import_module(code, initfunc, dllname[, finder]) -> module" },
	{ NULL, NULL },		/* Sentinel */
};

// }}}

static int _show_error(const wchar_t *preamble, const wchar_t *msg, const int code) {
    wchar_t *buf;
    char *cbuf;
    buf = (wchar_t*)LocalAlloc(LMEM_ZEROINIT, sizeof(wchar_t)*
            (wcslen(msg) + wcslen(preamble) + 80));

    _snwprintf_s(buf, 
        LocalSize(buf) / sizeof(wchar_t), _TRUNCATE,
        L"%s\r\n  %s (Error Code: %d)\r\n", 
        preamble, msg, code);

    if (GUI_APP) {
        MessageBeep(MB_ICONERROR);
        MessageBox(NULL, buf, NULL, MB_OK|MB_ICONERROR);
    }
    else {
        cbuf = (char*) calloc(10+(wcslen(buf)*4), sizeof(char));
        if (cbuf) {
            if (WideCharToMultiByte(CP_UTF8, 0, buf, -1, cbuf, (int)(10+(wcslen(buf)*4)), NULL, NULL) != 0) printf_s(cbuf);
            free(cbuf);
        }
    }

    LocalFree(buf);
    return code;
}



int show_last_error_crt(wchar_t *preamble) {
    wchar_t buf[1000];
    int err = 0;

    _get_errno(&err);
    _wcserror_s(buf, 1000, err);
    return _show_error(preamble, buf, err);
}

int show_last_error(wchar_t *preamble) {
    wchar_t *msg = NULL;
    DWORD dw = GetLastError(); 
    int ret;

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | 
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&msg, 
        0,
        NULL );

    ret = _show_error(preamble, msg, (int)dw);
    if (msg != NULL) LocalFree(msg);
    return ret;
}

char* get_app_dir() {
    char *buf, *buf2, *buf3;
    char drive[4] = "\0\0\0";
    DWORD sz; errno_t err;

    buf = (char*)calloc(MAX_PATH, sizeof(char));
    buf2 = (char*)calloc(MAX_PATH, sizeof(char));
    buf3 = (char*)calloc(MAX_PATH, sizeof(char));
    if (!buf || !buf2 || !buf3) ExitProcess(_show_error(L"Out of memory", L"", 1));
    sz = GetModuleFileNameA(NULL, buf, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));
    err = _splitpath_s(buf, drive, 4, buf2, MAX_PATH, NULL, 0, NULL, 0);
    if (err != 0) ExitProcess(show_last_error_crt(L"Failed to find application directory")); 
    _snprintf_s(buf3, MAX_PATH, _TRUNCATE, "%s%s", drive, buf2);
    free(buf); free(buf2);
    return buf3;
}

wchar_t* get_app_dirw() {
    wchar_t *buf, *buf2, *buf3;
    wchar_t drive[4] = L"\0\0\0";
    DWORD sz; errno_t err;

    buf = (wchar_t*)calloc(MAX_PATH, sizeof(wchar_t));
    buf2 = (wchar_t*)calloc(MAX_PATH, sizeof(wchar_t));
    buf3 = (wchar_t*)calloc(MAX_PATH, sizeof(wchar_t));
    if (!buf || !buf2 || !buf3) ExitProcess(_show_error(L"Out of memory", L"", 1));
    sz = GetModuleFileNameW(NULL, buf, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));
    err = _wsplitpath_s(buf, drive, 4, buf2, MAX_PATH, NULL, 0, NULL, 0);
    if (err != 0) ExitProcess(show_last_error_crt(L"Failed to find application directory")); 
    _snwprintf_s(buf3, MAX_PATH, _TRUNCATE, L"%s%s", drive, buf2);
    free(buf); free(buf2);
    return buf3;
}


void load_python_dll() {
    char *app_dir, *dll_dir, *qt_plugin_dir;
    size_t l;

    app_dir = get_app_dir();
    l = strlen(app_dir)+20;
    dll_dir = (char*) calloc(l, sizeof(char));
    qt_plugin_dir = (char*) calloc(l, sizeof(char));
    if (!dll_dir || !qt_plugin_dir) ExitProcess(_show_error(L"Out of memory", L"", 1));
    _snprintf_s(dll_dir, l, _TRUNCATE, "%sDLLs", app_dir);
    _snprintf_s(qt_plugin_dir, l, _TRUNCATE, "%sqt_plugins", app_dir);
    free(app_dir);

    _putenv_s("MAGICK_HOME", dll_dir);
    _putenv_s("MAGICK_CONFIGURE_PATH", dll_dir);
    _putenv_s("MAGICK_CODER_MODULE_PATH", dll_dir);
    _putenv_s("MAGICK_FILTER_MODULE_PATH", dll_dir);
    _putenv_s("QT_PLUGIN_PATH", qt_plugin_dir);

    if (!SetDllDirectoryA(dll_dir)) ExitProcess(show_last_error(L"Failed to set DLL directory."));
    if (FAILED(__HrLoadAllImportsForDll(python_dll))) 
        ExitProcess(_show_error(L"Failed to delay load the python dll", L"", 1));
}

static char program_name[MAX_PATH];
static char python_home[MAX_PATH];

static wchar_t out_of_memory[] = L"Out of memory";

void setup_stream(const char *name, const char *errors, UINT cp) {
    PyObject *stream;
    char *buf = (char *)calloc(100, sizeof(char));
    if (!buf) ExitProcess(_show_error(out_of_memory, L"", 1));

    if (cp == CP_UTF8) _snprintf_s(buf, 100, _TRUNCATE, "%s", "utf-8");
    else if (cp == CP_UTF7) _snprintf_s(buf, 100, _TRUNCATE, "%s", "utf-7");
    else _snprintf_s(buf, 100, _TRUNCATE, "cp%d", cp);

    stream = PySys_GetObject((char*)name);

    if (!PyFile_SetEncodingAndErrors(stream, buf, (char*)errors)) 
        ExitProcess(calibre_show_python_error(L"Failed to set stream encoding", 1));

    free(buf);
    
}

void setup_streams() {
    SetConsoleOutputCP(CP_UTF8);
    _putenv_s("PYTHONIOENCODING", "UTF-8");
    _setmode(_fileno(stdin),  _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    _setmode(_fileno(stderr), _O_BINARY);
    if (!GUI_APP) { // Remove buffering
        setvbuf(stdin,  NULL, _IONBF, 2);
        setvbuf(stdout, NULL, _IONBF, 2);                                                   
        setvbuf(stderr, NULL, _IONBF, 2);
    }

    //printf("input cp: %d output cp: %d\r\n", GetConsoleCP(), GetConsoleOutputCP());
    
    setup_stream("stdin", "strict", GetConsoleCP());
    setup_stream("stdout", "strict", CP_UTF8);
    setup_stream("stderr", "strict", CP_UTF8);
}

void initialize_interpreter(wchar_t *outr, wchar_t *errr,
        const char *basename, const char *module, const char *function) {
    DWORD sz; char *buf, *path; HMODULE dll;
    int *flag, i, argc;
    wchar_t *app_dir, **wargv;
    PyObject *argv, *v;
    char *dummy_argv[1] = {""};

    buf  = (char*)calloc(MAX_PATH, sizeof(char));
    path = (char*)calloc(MAX_PATH, sizeof(char));
    if (!buf || !path) ExitProcess(_show_error(L"Out of memory", L"", 1));

    sz = GetModuleFileNameA(NULL, buf, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));

    _snprintf_s(program_name, MAX_PATH, _TRUNCATE, "%s", buf);
    free(buf);

    buf = get_app_dir();
    buf[strlen(buf)-1] = '\0';

    _snprintf_s(python_home, MAX_PATH, _TRUNCATE, "%s", buf);
    _snprintf_s(path, MAX_PATH, _TRUNCATE, "%s\\pylib.zip", buf);
    free(buf);


    dll = GetModuleHandleA(python_dll);
    if (!dll) ExitProcess(show_last_error(L"Failed to get python dll handle"));
    flag = (int*)GetProcAddress(dll, "Py_OptimizeFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get optimize flag", L"", 1));
    *flag = 2;
    flag = (int*)GetProcAddress(dll, "Py_NoSiteFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get no_site flag", L"", 1));
    *flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_DontWriteBytecodeFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get no_bytecode flag", L"", 1));
    *flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_IgnoreEnvironmentFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get ignore_environment flag", L"", 1));
    *flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_NoUserSiteDirectory");
    if (!flag) ExitProcess(_show_error(L"Failed to get user_site flag", L"", 1));
    *flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_VerboseFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get verbose flag", L"", 1));
    //*flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_DebugFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get debug flag", L"", 1));
    //*flag = 1;

    DLL_Py_PackageContext = (char**)GetProcAddress(dll, "_Py_PackageContext");
    if (!DLL_Py_PackageContext) ExitProcess(_show_error(L"Failed to load _Py_PackageContext from dll", L"", 1));
    DLL_ImportError = (PyObject**)GetProcAddress(dll, "PyExc_ImportError");
    if (!DLL_ImportError) ExitProcess(_show_error(L"Failed to load PyExc_ImportError from dll", L"", 1));

    Py_SetProgramName(program_name);
    Py_SetPythonHome(python_home);

    //printf("Path before Py_Initialize(): %s\r\n\n", Py_GetPath()); 
    Py_Initialize();
    setup_streams();

    PySys_SetArgv(1, dummy_argv);
    //printf("Path after Py_Initialize(): %s\r\n\n", Py_GetPath());
    PySys_SetPath(path);
    //printf("Path set by me: %s\r\n\n", path);
    PySys_SetObject("gui_app", PyBool_FromLong((long)GUI_APP));
    app_dir = get_app_dirw();
    PySys_SetObject("app_dir", PyUnicode_FromWideChar(app_dir, wcslen(app_dir)));

    PySys_SetObject("calibre_basename", PyBytes_FromString(basename));
    PySys_SetObject("calibre_module", PyBytes_FromString(module));
    PySys_SetObject("calibre_function", PyBytes_FromString(function));

    if (GUI_APP && outr && errr) {
        PySys_SetObject("stdout_redirect", PyUnicode_FromWideChar(outr, wcslen(outr)));
        PySys_SetObject("stderr_redirect", PyUnicode_FromWideChar(errr, wcslen(outr)));
    }

    wargv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (wargv == NULL) ExitProcess(show_last_error(L"Failed to get command line"));
    argv = PyList_New(argc);
    if (argv == NULL) ExitProcess(_show_error(out_of_memory, L"", 1));
    for (i = 0; i < argc; i++) {
        v = PyUnicode_FromWideChar(wargv[i], wcslen(wargv[i]));
        if (v == NULL) ExitProcess(_show_error(out_of_memory, L"", 1));
        PyList_SetItem(argv, i, v);
    }
    PySys_SetObject("argv", argv);

	Py_InitModule3("_memimporter", methods, module_doc);

}


wchar_t* pyobject_to_wchar(PyObject *o) {
    PyUnicodeObject *t;
    size_t s;
    wchar_t *ans;

    if (!PyUnicode_Check(o)) {
        t = (PyUnicodeObject*)PyUnicode_FromEncodedObject(o, NULL, "replace");
        if (t == NULL) return NULL;
    } else t = (PyUnicodeObject*)o;


    s = 2*PyUnicode_GET_SIZE(t) +1; 
    ans = (wchar_t*)calloc(s, sizeof(wchar_t));
    if (ans == NULL) return NULL;
    s = PyUnicode_AsWideChar(t, ans, s-1);
    ans[s] = L'\0';
    
    return ans;
}

int pyobject_to_int(PyObject *res) {
    int ret; PyObject *tmp;
    tmp = PyNumber_Int(res);
    if (tmp == NULL) ret = (PyObject_IsTrue(res)) ? 1 : 0;
    else ret = (int)PyInt_AS_LONG(tmp);

    return ret;
}

int handle_sysexit(PyObject *e) {
    PyObject *code;

    code = PyObject_GetAttrString(e, "code");
    if (!code) return 0;
    return pyobject_to_int(code);
}

int calibre_show_python_error(const wchar_t *preamble, int code) {
    PyObject *exc, *val, *tb, *str, **system_exit;
    HMODULE dll;
    int ret, issysexit = 0; wchar_t *i; 

    if (!PyErr_Occurred()) return code;
    dll = GetModuleHandleA(python_dll);
    if (!dll) ExitProcess(show_last_error(L"Failed to get python dll handle"));
    system_exit = (PyObject**)GetProcAddress(dll, "PyExc_SystemExit");
    issysexit = PyErr_ExceptionMatches(*system_exit);


    PyErr_Fetch(&exc, &val, &tb);

    if (exc != NULL) {
        PyErr_NormalizeException(&exc, &val, &tb);

        if (issysexit) {
            return (val) ? handle_sysexit(val) : 0;
        }
        if (val != NULL) {
            str = PyObject_Unicode(val);
            if (str == NULL) {
                PyErr_Clear();
                str = PyObject_Str(val);
            }
            i = pyobject_to_wchar(str);
            ret = _show_error(preamble, (i==NULL)?out_of_memory:i, code);
            if (i) free(i);
            if (tb != NULL) {
                PyErr_Restore(exc, val, tb);
                PyErr_Print();
            }
            return ret;
        }
    }
    return _show_error(preamble, L"", code);
}

int execute_python_entrypoint(const char *basename, const char *module, const char *function,
        wchar_t *outr, wchar_t *errr) {
    PyObject *site, *main, *res;
    int ret = 0;

    load_python_dll();
    initialize_interpreter(outr, errr, basename, module, function);

    site = PyImport_ImportModule("site");

    if (site == NULL)
        ret = calibre_show_python_error(L"Failed to import site module",  1);
    else {
        Py_XINCREF(site);

        main = PyObject_GetAttrString(site, "main");
        if (main == NULL || !PyCallable_Check(main)) 
            ret = calibre_show_python_error(L"site module has no main function", 1);
        else {
            Py_XINCREF(main);
            res = PyObject_CallObject(main, NULL);

            if (res == NULL) 
                ret = calibre_show_python_error(L"Python function terminated unexpectedly", 1);
            else {
            }
        }
    }
    PyErr_Clear();
    Py_Finalize();

    //printf("11111 Returning: %d\r\n", ret);
    return ret;
}


wchar_t* get_temp_filename(const wchar_t *prefix) {
    DWORD dwRetVal;
    UINT uRetVal;

    wchar_t *szTempName;
    wchar_t lpPathBuffer[MAX_PATH];
    szTempName = (wchar_t *)LocalAlloc(LMEM_ZEROINIT, sizeof(wchar_t)*MAX_PATH);

    dwRetVal = GetTempPath(MAX_PATH, lpPathBuffer);

    if (dwRetVal > MAX_PATH || (dwRetVal == 0)) {
        ExitProcess(show_last_error(L"Failed to get temp path."));
    }

    uRetVal = GetTempFileName(lpPathBuffer, // directory for tmp files
                              prefix,       // temp file name prefix 
                              0,            // create unique name 
                              szTempName);  // buffer for name 

     if (uRetVal == 0) {
         ExitProcess(show_last_error(L"Failed to get temp file name"));
     }
     return szTempName;
}

wchar_t* redirect_out_stream(const wchar_t *prefix, char outstream) {
    FILE *f = NULL;
    wchar_t *temp_file;
    errno_t err;

    temp_file = get_temp_filename(prefix);

    err = _wfreopen_s(&f, temp_file, L"a+t", (outstream) ? stdout : stderr);
    if (err != 0) {
        ExitProcess(show_last_error_crt(L"Failed to redirect stdout."));
    }

    return temp_file;

}
