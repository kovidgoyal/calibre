#include "util.h"
#include <Python.h>
#include <stdlib.h>
#include <strings.h>
#include <stdio.h>
#include <errno.h>

static bool GUI_APP = False;

static char exe_path[PATH_MAX];
static char base_dir[PATH_MAX];
static char bin_dir[PATH_MAX];
static char lib_dir[PATH_MAX];
static char qt_dir[PATH_MAX];
static char extensions_dir[PATH_MAX];
static char resources_dir[PATH_MAX];
static char magick_dir[PATH_MAX];

void set_gui_app(bool yes) { GUI_APP = yes; }

int report_error(const char *msg, int code) {
    fprintf(stderr, "%s\n", msg);
    return code;
}

int report_libc_error(const char *msg) {
    char buf[2000];
    int err = errno;
    snprintf("%s::%s", 2000, msg, strerror(err));
    return report_error(buf, err);
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

int report_python_error(const char *preamble, int code) {
    PyObject *exc, *val, *tb, *str;
    int ret, issysexit = 0; char *i, *buf; 

    if (!PyErr_Occurred()) return code;
    issysexit = PyErr_ExceptionMatches(PyExc_SystemExit);

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
            i = PyString_AsString(str);
            if (i == NULL) OOM;
            buf = (char*)calloc(strlen(i)+strlen(preamble)+5, sizeof(char));
            if (buf == NULL) OOM;
            sprintf(buf, "%s::%s", preamble, i);
            ret = report_error(buf, code);
            if (buf) free(buf);
            if (tb != NULL) {
                PyErr_Restore(exc, val, tb);
                PyErr_Print();
            }
            return ret;
        }
    }
    return report_error(preamble, code);
}

static void get_paths()
{
	char linkname[256]; /* /proc/<pid>/exe */
    char *p;
	pid_t pid;
	int ret;
	
	pid = getpid();
	
	if (snprintf(linkname, sizeof(linkname), "/proc/%i/exe", pid) < 0)
		{
		/* This should only happen on large word systems. I'm not sure
		   what the proper response is here.
		   Since it really is an assert-like condition, aborting the
		   program seems to be in order. */
        exit(report_error("PID too large", EXIT_FAILURE));
		}

	
	ret = readlink(linkname, exe_path, PATH_MAX);
	
	if (ret == -1) {
        exit(report_error("Failed to read exe path.", EXIT_FAILURE));
    }
	
	if (ret >= PATH_MAX) {
        exit(report_error("exe path buffer too small.", EXIT_FAILURE));
    }
	
	exe_path[ret] = 0;

    p = rindex(exe_path, '/');

    if (p ==  NULL) {
        exit(report_error("No path separators in executable path", EXIT_FAILURE));
    }
    strncat(base_dir, exe_path, p - exe_path);
    strcat(base_dir, "\0");
    snprintf(bin_dir,        PATH_MAX, "%s/bin", base_dir);
    snprintf(lib_dir,        PATH_MAX, "%s/lib", base_dir);
    snprintf(magick_dir,     PATH_MAX, "%s/ImageMagick", lib_dir);
    snprintf(qt_dir,         PATH_MAX, "%s/qt_plugins", lib_dir);
    snprintf(resources_dir,  PATH_MAX, "%s/resources", base_dir);
    snprintf(extensions_dir, PATH_MAX, "%s/%s/site-packages/calibre/plugins", lib_dir, PYTHON_VER);
}

void init_env() {
    char buf[PATH_MAX];

    if (setenv("QT_PLUGIN_PATH", qt_dir, 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

    snprintf(buf, PATH_MAX, "%s/config", magick_dir);
    if (setenv("MAGICK_CONFIGURE_PATH", buf, 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

    snprintf(buf, PATH_MAX, "%s/modules-Q16/coders", magick_dir);
    if (setenv("MAGICK_CODER_MODULE_PATH", buf, 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

    snprintf(buf, PATH_MAX, "%s/modules-Q16/filters", magick_dir);
    if (setenv("MAGICK_CODER_FILTER_PATH", buf, 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

    if (setenv("PYTHONIOENCODING", "utf-8", 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

    if (setenv("PYTHONHOME", base_dir, 1) == -1) 
        exit(report_libc_error("Failed to set environment variable"));

}

void setup_stream(const char *name, const char *errors) {
    PyObject *stream;
    char *buf = (char *)calloc(100, sizeof(char));
    if (!buf) OOM;

    snprintf(buf, 100, "%s", "utf-8");

    stream = PySys_GetObject(name);

    if (!PyFile_SetEncodingAndErrors(stream, buf, errors)) 
        exit(report_python_error("Failed to set stream encoding", 1));

    free(buf);
    
}

void setup_streams() {
    if (!GUI_APP) { // Remove buffering
        setvbuf(stdin,  NULL, _IONBF, 2);
        setvbuf(stdout, NULL, _IONBF, 2);                                                   
        setvbuf(stderr, NULL, _IONBF, 2);
    }

    /*setup_stream("stdin", "strict");
    setup_stream("stdout", "strict");
    setup_stream("stderr", "strict");*/
}

void initialize_interpreter(int argc, char **argv, char *outr, char *errr,
        const char *basename, const char *module, const char *function) {
    char *path;

    get_paths();
    init_env();

    path = (char*)calloc(3*PATH_MAX, sizeof(char));
    if (!path) OOM;

    snprintf(path, 3*PATH_MAX,
            "%s/%s:%s/%s/plat-linux2:%s/%s/lib-dynload:%s/%s/site-packages",
            lib_dir, PYTHON_VER, lib_dir, PYTHON_VER, lib_dir, PYTHON_VER,
            lib_dir, PYTHON_VER);

    Py_OptimizeFlag = 2;
    Py_NoSiteFlag = 1;
    Py_DontWriteBytecodeFlag = 1;
    Py_IgnoreEnvironmentFlag = 1;
    Py_NoUserSiteDirectory = 1;
    Py_VerboseFlag = 0;
    Py_DebugFlag = 0;

    Py_SetProgramName(exe_path);
    Py_SetPythonHome(base_dir);

    //printf("Path before Py_Initialize(): %s\r\n\n", Py_GetPath()); 
    Py_Initialize();
    setup_streams();

    PySys_SetArgv(argc, argv);
    //printf("Path after Py_Initialize(): %s\r\n\n", Py_GetPath());
    PySys_SetPath(path);
    //printf("Path set by me: %s\r\n\n", path);
    PySys_SetObject("gui_app", PyBool_FromLong((long)GUI_APP));
    PySys_SetObject("app_dir", PyString_FromString(base_dir));

    PySys_SetObject("calibre_basename", PyBytes_FromString(basename));
    PySys_SetObject("calibre_module",   PyBytes_FromString(module));
    PySys_SetObject("calibre_function", PyBytes_FromString(function));

    //if (GUI_APP && outr && errr) {
    //    PySys_SetObject("stdout_redirect", PyUnicode_FromWideChar(outr, wcslen(outr)));
    //    PySys_SetObject("stderr_redirect", PyUnicode_FromWideChar(errr, wcslen(outr)));
    //}

}

int execute_python_entrypoint(int argc, char **argv, const char *basename, const char *module, const char *function,
        char *outr, char *errr) {
    PyObject *site, *pmain, *res;
    int ret = 0;

    initialize_interpreter(argc, argv, outr, errr, basename, module, function);

    site = PyImport_ImportModule("site");

    if (site == NULL)
        ret = report_python_error("Failed to import site module",  1);
    else {
        Py_XINCREF(site);

        pmain = PyObject_GetAttrString(site, "main");
        if (pmain == NULL || !PyCallable_Check(pmain)) 
            ret = report_python_error("site module has no main function", 1);
        else {
            Py_XINCREF(pmain);
            res = PyObject_CallObject(pmain, NULL);

            if (res == NULL) 
                ret = report_python_error("Python function terminated unexpectedly", 1);
        }
    }
    PyErr_Clear();
    Py_Finalize();

    //printf("11111 Returning: %d\r\n", ret);
    return ret;
}


