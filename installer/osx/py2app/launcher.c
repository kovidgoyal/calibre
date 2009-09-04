#include <stdlib.h>
#include <strings.h>
#include <CoreFoundation/CoreFoundation.h>
#include <mach-o/dyld.h>
#include <Python.h>

static const char *ERR_UNKNOWNPYTHONEXCEPTION = "An uncaught exception was raised during execution of the main script, but its class or name could not be determined";

static int
report_error(const char *msg) {
    fprintf(stderr, msg);
    fprintf(stderr, "\n");
    fflush(stderr);
    return -1;
}

// These variable must be filled in before compiling
static const char *ENV_VARS[] = { /*ENV_VARS*/ NULL };
static const char *ENV_VAR_VALS[] = { /*ENV_VAR_VALS*/ NULL};
static char PROGRAM[] = "**PROGRAM**";
static const char MODULE[] = "**MODULE**";

#define EXE "@executable_path/.."

static void
set_env_vars(const char* exe_path, const char* rpath) {
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
    setenv("CALIBRE_LAUNCH_MODULE", MODULE, 1);
    setenv("RESOURCEPATH", rpath, 1);
    return;
}

int 
main(int argc, char * const *argv, char * const *envp) {
    char *pathPtr = NULL;
    char buf[3*PATH_MAX];
    int ret, i;

    
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

        

    char rpath[PATH_MAX+1];
    strncpy(rpath, pathPtr, strlen(pathPtr));
    strncat(rpath, "/Contents/Resources", 50);
    char exe_path[PATH_MAX+1];
    strncpy(exe_path, pathPtr, strlen(pathPtr));
    strncat(exe_path, "/Contents", 50);
    
    set_env_vars(exe_path, rpath);

    char main_script[PATH_MAX+1];
    strncpy(main_script, rpath, strlen(rpath));
    strncat(main_script, "/launcher.py", 20);

    Py_SetProgramName(PROGRAM);

    Py_Initialize();
    
    char **argv_new = calloc(argc+1, sizeof(char *));
    argv_new[argc] = NULL;
    argv_new[0] = main_script;
    memcpy(&argv_new[1], &argv[1], (argc - 1) * sizeof(char *));
    PySys_SetArgv(argc, argv_new);

    FILE *main_script_file = fopen(main_script, "r");
    int rval = PyRun_SimpleFileEx(main_script_file, main_script, 1);
 
    while (rval != 0) {
        PyObject *exc, *exceptionClassName, *v, *exceptionName;
        exc = PySys_GetObject("last_type");

        if ( !exc ) {
            rval = report_error(ERR_UNKNOWNPYTHONEXCEPTION);
            break;
        }

        exceptionClassName = PyObject_GetAttrString(exc, "__name__");
        if (!exceptionClassName) {
            rval = report_error(ERR_UNKNOWNPYTHONEXCEPTION);
            break;
        }

        v = PySys_GetObject("last_value");
        exceptionName = (v ? PyObject_Str(v) : NULL);

        char *class = PyString_AsString(exceptionClassName);
        char *exception = "";
        Py_DecRef(exceptionClassName);
        if (exceptionName) {
            exception = PyString_AsString(exceptionName);
            Py_DecRef(exceptionName);
        }
        char msg[2000];
        strncpy(msg, "An unexpected error occurred: ", 100);
        strncpy(msg, class, 500);
        strncpy(msg, " : ", 3);
        strncpy(msg, exception, 500);
        rval = report_error(msg);
        break;

    }
    Py_Finalize();
    return rval;
}
