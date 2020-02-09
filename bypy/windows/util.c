/*
 * Copyright 2009 Kovid Goyal
 */

#define UNICODE

#define _WIN32_WINNT 0x0502
#define WINDOWS_LEAN_AND_MEAN

#include <windows.h>
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <Shellapi.h>
#include <delayimp.h>
#include <io.h>
#include <fcntl.h>

#define arraysz(x) (sizeof((x))/sizeof((x)[0]))

static int GUI_APP = 0;
static char python_dll[] = PYDLL;

void set_gui_app(int yes) { GUI_APP = yes; }

int calibre_show_python_error(const wchar_t *preamble, int code);

static int _show_error(const wchar_t *preamble, const wchar_t *msg, const int code) {
    static wchar_t buf[4096];
	static char utf8_buf[4096] = {0};
	int n = WideCharToMultiByte(CP_UTF8, 0, preamble, -1, utf8_buf, sizeof(utf8_buf) - 1, NULL, NULL);
	if (n > 0) fprintf(stderr, "%s\r\n  ", utf8_buf);
	n = WideCharToMultiByte(CP_UTF8, 0, msg, -1, utf8_buf, sizeof(utf8_buf) - 1, NULL, NULL);
	if (n > 0) fprintf(stderr, "%s (Error Code: %d)\r\n ", utf8_buf, code);
    fflush(stderr);

    if (GUI_APP) {
        _snwprintf_s(buf, arraysz(buf), _TRUNCATE, L"%ls\r\n  %ls (Error Code: %d)\r\n", preamble, msg, code);
        MessageBeep(MB_ICONERROR);
        MessageBox(NULL, buf, NULL, MB_OK|MB_ICONERROR);
    }
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

static char    app_dir[MAX_PATH] = {0};
static wchar_t dll_dir[MAX_PATH] = {0};
static wchar_t qt_prefix_dir[MAX_PATH] = {0};
static char    program_name[MAX_PATH] = {0};
static wchar_t w_program_name[MAX_PATH] = {0};
static wchar_t w_app_dir[MAX_PATH] = {0};
#if PY_VERSION_MAJOR >= 3
static wchar_t python_path[MAX_PATH] = {0};
#else
static char python_path[MAX_PATH] = {0};
#endif

static void
get_app_dir(void) {
    char drive[4] = "\0\0\0";
    DWORD sz; errno_t err;
    char buf[MAX_PATH] = {0};

    sz = GetModuleFileNameA(NULL, program_name, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));
    err = _splitpath_s(program_name, drive, 4, buf, MAX_PATH, NULL, 0, NULL, 0);
    if (err != 0) ExitProcess(show_last_error_crt(L"Failed to find application directory"));
    _snprintf_s(app_dir, MAX_PATH, _TRUNCATE, "%s%s", drive, buf);
}

static void
get_app_dirw(void) {
    wchar_t buf[MAX_PATH] = {0};
    wchar_t drive[4] = L"\0\0\0";
    DWORD sz; errno_t err;

    sz = GetModuleFileNameW(NULL, w_program_name, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));
    err = _wsplitpath_s(w_program_name, drive, 4, buf, MAX_PATH, NULL, 0, NULL, 0);
    if (err != 0) ExitProcess(show_last_error_crt(L"Failed to find application directory"));
    _snwprintf_s(w_app_dir, MAX_PATH, _TRUNCATE, L"%ls%ls", drive, buf);
}

static void
get_install_locations(void) {
    get_app_dir();
    get_app_dirw();
    _snwprintf_s(qt_prefix_dir, MAX_PATH-1, _TRUNCATE, L"%ls\\app", w_app_dir);
    _wputenv_s(L"CALIBRE_QT_PREFIX", qt_prefix_dir);
    _snwprintf_s(dll_dir, MAX_PATH-1, _TRUNCATE, L"%ls\\app\\bin", w_app_dir);
#if PY_VERSION_MAJOR >= 3
    _snwprintf_s(python_path, MAX_PATH-1, _TRUNCATE, L"%ls\\app\\pylib.zip", w_app_dir);
#else
    _snprintf_s(python_path, MAX_PATH-1, _TRUNCATE, "%s\\app\\pylib.zip", app_dir);
#endif

}

static void
load_python_dll() {
    get_install_locations();
    if (FAILED(__HrLoadAllImportsForDll(python_dll)))
        ExitProcess(_show_error(L"Failed to delay load the python dll", L"", 1));
}

const static wchar_t out_of_memory[] = L"Out of memory";

static void
setup_stream(const char *name, const char *errors, UINT cp) {
    PyObject *stream;
    char buf[128] = {0};

    if (cp == CP_UTF8) _snprintf_s(buf, 100, _TRUNCATE, "%s", "utf-8");
    else if (cp == CP_UTF7) _snprintf_s(buf, 100, _TRUNCATE, "%s", "utf-7");
    else _snprintf_s(buf, 100, _TRUNCATE, "cp%d", cp);

    stream = PySys_GetObject((char*)name);

    if (!PyFile_SetEncodingAndErrors(stream, buf, (char*)errors))
        ExitProcess(calibre_show_python_error(L"Failed to set stream encoding", 1));
}

UINT
setup_streams() {
    UINT code_page = GetConsoleOutputCP();
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
    return code_page;
}

UINT
initialize_interpreter(const char *basename, const char *module, const char *function) {
    HMODULE dll;
    int *flag, i, argc;
    wchar_t **wargv;
    PyObject *argv, *v;
    char *dummy_argv[1] = {""};

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
    flag = (int*)GetProcAddress(dll, "Py_HashRandomizationFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get hash randomization flag", L"", 1));
    *flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_VerboseFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get verbose flag", L"", 1));
    //*flag = 1;
    flag = (int*)GetProcAddress(dll, "Py_DebugFlag");
    if (!flag) ExitProcess(_show_error(L"Failed to get debug flag", L"", 1));
    //*flag = 1;

#if PY_VERSION_MAJOR >= 3
    Py_SetProgramName(w_program_name);
    Py_SetPythonHome(w_app_dir);
#else
    Py_SetProgramName(program_name);
    Py_SetPythonHome(app_dir);
#endif

    //printf("Path before Py_Initialize(): %s\r\n\n", Py_GetPath());
    Py_Initialize();
    UINT code_page = setup_streams();

    PySys_SetArgv(1, dummy_argv);
    //printf("Path after Py_Initialize(): %s\r\n\n", Py_GetPath());
    PySys_SetPath(python_path);
    //printf("Path set by me: %s\r\n\n", path);
    PySys_SetObject("gui_app", PyBool_FromLong((long)GUI_APP));
    PySys_SetObject("app_dir", PyUnicode_FromWideChar(w_app_dir, wcslen(w_app_dir)));

    PySys_SetObject("calibre_basename", PyBytes_FromString(basename));
    PySys_SetObject("calibre_module", PyBytes_FromString(module));
    PySys_SetObject("calibre_function", PyBytes_FromString(function));

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
    return code_page;
}


static const wchar_t*
pyobject_to_wchar(PyObject *o) {
    PyObject *t = NULL;
    size_t s;
    static wchar_t ans[4096];

    if (!PyUnicode_Check(o)) {
        t = PyUnicode_FromEncodedObject(o, NULL, "replace");
        if (t == NULL) return NULL;
    }

    s = PyUnicode_AsWideChar((PyUnicodeObject*)(t ? t : o), ans, arraysz(ans)-1);
    Py_XDECREF(t);
    if (s >= 0) ans[s] = 0;
    else ans[s] = 0;

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
    if (!PyInt_Check(code)) {
        PyObject_Print(code, stderr, Py_PRINT_RAW);
        fflush(stderr);
    }
    return pyobject_to_int(code);
}

int calibre_show_python_error(const wchar_t *preamble, int code) {
    PyObject *exc, *val, *tb, *str, **system_exit;
    HMODULE dll;
    int ret, issysexit = 0; const wchar_t *i;

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
            if (tb != NULL) {
                PyErr_Restore(exc, val, tb);
                PyErr_Print();
            }
            return ret;
        }
    }
    return _show_error(preamble, L"", code);
}

void redirect_out_stream(FILE *stream) {
    FILE *f = NULL;
    errno_t err;

    err = freopen_s(&f, "NUL", "wt", stream);
    if (err != 0) {
        ExitProcess(show_last_error_crt(L"Failed to redirect stdout/stderr to NUL. This indicates a corrupted Windows install.\r\n You should contact Microsoft for assistance and/or follow the steps described here:\r\n http://bytes.com/topic/net/answers/264804-compile-error-null-device-missing"));
    }
}

static void
null_invalid_parameter_handler(
   const wchar_t * expression,
   const wchar_t * function,
   const wchar_t * file,
   unsigned int line,
   uintptr_t pReserved
) {
    // The python runtime expects various system calls with invalid parameters
    // to return errors instead of aborting the program. So get the windows CRT
    // to do that.
}
__declspec(dllexport) int __cdecl
simple_print(const wchar_t *msg) {
    int n = wprintf(L"%ls", msg); fflush(stdout);
	return n;
}

__declspec(dllexport) int __cdecl
execute_python_entrypoint(const char *basename, const char *module, const char *function, int is_gui_app) {
    PyObject *site, *main, *res;
    int ret = 0;
    // Prevent Windows' idiotic error dialog popups when various win32 api functions fail
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOALIGNMENTFAULTEXCEPT | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);

    if (is_gui_app) {
        // Redirect stdout and stderr to NUL so that python does not fail writing to them
        redirect_out_stream(stdout);
        redirect_out_stream(stderr);
    }
    set_gui_app(is_gui_app);
    // Disable the invalid parameter handler
    _set_invalid_parameter_handler(null_invalid_parameter_handler);

    load_python_dll();
    UINT code_page = initialize_interpreter(basename, module, function);

    site = PyImport_ImportModule("site");

    if (site == NULL)
        ret = calibre_show_python_error(L"Failed to import site module",  1);
    else {
        Py_INCREF(site);

        main = PyObject_GetAttrString(site, "main");
        if (main == NULL || !PyCallable_Check(main))
            ret = calibre_show_python_error(L"site module has no main function", 1);
        else {
            Py_INCREF(main);
            res = PyObject_CallObject(main, NULL);

            if (res == NULL)
                ret = calibre_show_python_error(L"Python function terminated unexpectedly", 1);
            else {
#if PY_VERSION_MAJOR < 3
                if (PyInt_Check(res)) {
                    ret = PyInt_AS_LONG(res);
                }
#else
                if (PyLong_Check(res)) {
                    ret = PyLong_AsLong(res);
                }
#endif
                Py_DECREF(res);
            }
        }
    }
    PyErr_Clear();
    Py_Finalize();
    if (code_page != CP_UTF8) SetConsoleOutputCP(code_page);
    /* printf("111111111111 returning: %d\r\n", ret); */

    return ret;
}
