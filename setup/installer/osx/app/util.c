#include "util.h"
#include <stdlib.h>
#include <strings.h>
#include <CoreFoundation/CoreFoundation.h>
#include <mach-o/dyld.h>
#include <Python.h>

#define EXPORT __attribute__((visibility("default")))

static const char *ERR_OOM = "Out of memory";

static int
report_error(const char *msg) {
    fprintf(stderr, msg);
    fprintf(stderr, "\n");
    fflush(stderr);
    return -1;
}

static int
report_code(const char *preamble, const char* msg, int code) {
    fprintf(stderr, "%s: %s\n", preamble, msg);
    fflush(stderr);
    return code;
}

#define EXE "@executable_path/.."

static void
set_env_vars(const char **ENV_VARS, const char **ENV_VAR_VALS, const char* exe_path) {
    int i = 0;
    char buf[3*PATH_MAX];
    const char *env_var, *val;

    while(1) {
        env_var = ENV_VARS[i];
        if (env_var == NULL) break;
        val = ENV_VAR_VALS[i++];
        if (strstr(val, EXE) == val && strlen(val) >= strlen(EXE)+1) {
            strncpy(buf, exe_path, 3*PATH_MAX-150);
            strncpy(buf+strlen(exe_path), val+strlen(EXE), 150);
            setenv(env_var, buf, 1);
        } else
            setenv(env_var, val, 1);
    }
    return;
}

void initialize_interpreter(const char **ENV_VARS, const char **ENV_VAR_VALS,
        char *PROGRAM, const char *MODULE, const char *FUNCTION, const char *PYVER,
        const char* exe_path, const char *rpath, int argc, const char **argv) {
    PyObject *pargv, *v;
    int i;
    Py_OptimizeFlag = 2;
    Py_NoSiteFlag = 1;
    Py_DontWriteBytecodeFlag = 1;
    Py_IgnoreEnvironmentFlag = 1;
    Py_NoUserSiteDirectory = 1;

    //Py_VerboseFlag = 1;
    //Py_DebugFlag = 1;
    
    Py_SetProgramName(PROGRAM);

    char pyhome[1000];
    snprintf(pyhome, 1000, "%s/Python", rpath);
    Py_SetPythonHome(pyhome);

    set_env_vars(ENV_VARS, ENV_VAR_VALS, exe_path);

    //printf("Path before Py_Initialize(): %s\r\n\n", Py_GetPath());
    Py_Initialize();

    char *dummy_argv[1] = {""};
    PySys_SetArgv(1, dummy_argv);
    //printf("Path after Py_Initialize(): %s\r\n\n", Py_GetPath());
    char path[3000];
    snprintf(path, 3000, "%s/lib/python%s:%s/lib/python%s/lib-dynload:%s/site-packages", pyhome, PYVER, pyhome, PYVER, pyhome);

    PySys_SetPath(path);
    //printf("Path set by me: %s\r\n\n", path);

    PySys_SetObject("calibre_basename", PyBytes_FromString(PROGRAM));
    PySys_SetObject("calibre_module", PyBytes_FromString(MODULE));
    PySys_SetObject("calibre_function", PyBytes_FromString(FUNCTION));
    PySys_SetObject("resourcepath", PyBytes_FromString(rpath));
    snprintf(path, 3000, "%s/site-packages", pyhome);
    PySys_SetObject("site_packages", PyBytes_FromString(pyhome));


    pargv = PyList_New(argc);
    if (pargv == NULL) exit(report_error(ERR_OOM));
    for (i = 0; i < argc; i++) {
        v = PyBytes_FromString(argv[i]);
        if (v == NULL) exit(report_error(ERR_OOM));
        PyList_SetItem(pargv, i, v);
    }
    PySys_SetObject("argv", pargv);

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

int calibre_show_python_error(const char *preamble, int code) {
    PyObject *exc, *val, *tb, *str;
    int ret, issysexit = 0; char *i; 

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
            ret = report_code(preamble, (i==NULL)?ERR_OOM:i, code);
            if (tb != NULL) {
                PyErr_Restore(exc, val, tb);
                PyErr_Print();
            }
            return ret;
        }
    }
    return report_code(preamble, "", code);
}

EXPORT
int
run(const char **ENV_VARS, const char **ENV_VAR_VALS, char *PROGRAM,
        const char *MODULE, const char *FUNCTION, const char *PYVER,
        int argc, const char **argv, const char **envp) {
    char *pathPtr = NULL;
    char buf[3*PATH_MAX];
    int ret = 0, i;
    PyObject *site, *mainf, *res;

    
    uint32_t buf_size = PATH_MAX+1;
    char *ebuf = calloc(buf_size, sizeof(char));
    ret = _NSGetExecutablePath(ebuf, &buf_size);
    if (ret == -1) {
        free(ebuf);
        ebuf = calloc(buf_size, sizeof(char));
        if (_NSGetExecutablePath(ebuf, &buf_size) != 0)
            return report_error("Failed to find real path of executable.");
    }
    pathPtr = realpath(ebuf, buf);
    if (pathPtr == NULL) {
        return report_error(strerror(errno));
    }
    char *t;
    for (i = 0; i < 3; i++) {
        t = rindex(pathPtr, '/');
        if (t == NULL) return report_error("Failed to determine bundle path.");
        *t = '\0';
    }

        

    char rpath[PATH_MAX+1], exe_path[PATH_MAX+1];
    snprintf(exe_path, PATH_MAX+1, "%s/Contents", pathPtr);
    snprintf(rpath, PATH_MAX+1, "%s/Resources", exe_path);
    initialize_interpreter(ENV_VARS, ENV_VAR_VALS, PROGRAM, MODULE, FUNCTION, PYVER,
            exe_path, rpath, argc, argv);

    site = PyImport_ImportModule("site");

    if (site == NULL)
        ret = calibre_show_python_error("Failed to import site module",  -1);
    else {
        Py_XINCREF(site);

        mainf = PyObject_GetAttrString(site, "main");
        if (mainf == NULL || !PyCallable_Check(mainf)) 
            ret = calibre_show_python_error("site module has no main function", -1);
        else {
            Py_XINCREF(mainf);
            res = PyObject_CallObject(mainf, NULL);

            if (res == NULL) 
                ret = calibre_show_python_error("Python function terminated unexpectedly", -1);
            else {
            }
        }
    }
    PyErr_Clear();
    Py_Finalize();

    //printf("11111 Returning: %d\r\n", ret);
    return ret;
}



