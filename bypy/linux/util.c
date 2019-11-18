#include "util.h"
#include <Python.h>
#include <stdlib.h>
#include <strings.h>
#include <stdio.h>
#include <errno.h>

#define arraysz(x) (sizeof(x)/sizeof(x[0]))

static bool GUI_APP = false;
static char exe_path_char[PATH_MAX];
static wchar_t exe_path[PATH_MAX];
static wchar_t base_dir[PATH_MAX];
static wchar_t bin_dir[PATH_MAX];
static wchar_t lib_dir[PATH_MAX];
static wchar_t extensions_dir[PATH_MAX];
static wchar_t resources_dir[PATH_MAX];

void set_gui_app(bool yes) { GUI_APP = yes; }

static int
report_error(const char *msg, int code) {
    fprintf(stderr, "%s\n", msg);
    return code;
}

static void
get_paths() {
	char linkname[256]; /* /proc/<pid>/exe */
    wchar_t *p;
	pid_t pid;
	int ret;

	pid = getpid();

	if (snprintf(linkname, sizeof(linkname), "/proc/%i/exe", pid) < 0) {
		/* This should only happen on large word systems. I'm not sure
		   what the proper response is here.
		   Since it really is an assert-like condition, aborting the
		   program seems to be in order. */
        exit(report_error("PID too large", EXIT_FAILURE));
    }

	ret = readlink(linkname, exe_path_char, sizeof(exe_path_char));
	if (ret == -1) {
        exit(report_error("Failed to read exe path.", EXIT_FAILURE));
    }
	if ((size_t)ret >= sizeof(exe_path_char)) {
        exit(report_error("exe path buffer too small.", EXIT_FAILURE));
    }
	exe_path_char[ret] = 0;
    size_t tsz;
    wchar_t* temp = Py_DecodeLocale(exe_path_char, &tsz);
    if (!temp) {
        exit(report_error("Failed to decode exe path", EXIT_FAILURE));
    }
    memcpy(exe_path, temp, tsz * sizeof(wchar_t));
    exe_path[tsz] = 0;
    PyMem_RawFree(temp);

    p = wcsrchr(exe_path, '/');
    if (p == NULL) {
        exit(report_error("No path separators in executable path", EXIT_FAILURE));
    }
    wcsncat(base_dir, exe_path, p - exe_path);
    p = wcsrchr(base_dir, '/');
    if (p == NULL) {
        exit(report_error("Only one path separator in executable path", EXIT_FAILURE));
    }
    *p = 0;
    if (wcslen(base_dir) == 0) {
        exit(report_error("base directory empty", EXIT_FAILURE));
    }

    swprintf(bin_dir,        arraysz(bin_dir), L"%ls/bin", base_dir);
    swprintf(lib_dir,        arraysz(lib_dir), L"%ls/lib", base_dir);
    swprintf(resources_dir,  arraysz(resources_dir), L"%ls/resources", base_dir);
    swprintf(extensions_dir, arraysz(extensions_dir), L"%ls/%ls/site-packages/calibre/plugins", lib_dir, PYTHON_VER);
}

static void
set_sys_string(const char* key, const wchar_t* val) {
    PyObject *temp = PyUnicode_FromWideChar(val, -1);
    if (temp) {
        if (PySys_SetObject(key, temp) != 0) {
            exit(report_error("Failed to set attribute on sys", EXIT_FAILURE));
        }
        Py_DECREF(temp);
    } else {
        exit(report_error("Failed to set attribute on sys, decode failed", EXIT_FAILURE));
    }
}

static int
initialize_interpreter(int argc, char * const *argv, const wchar_t *basename, const wchar_t *module, const wchar_t *function) {
    PyStatus status;
    PyPreConfig preconfig;
    PyConfig config;
    PyPreConfig_InitIsolatedConfig(&preconfig);

    preconfig.utf8_mode = 1;
    preconfig.coerce_c_locale = 1;
    preconfig.isolated = 1;

#define CHECK_STATUS if (PyStatus_Exception(status)) { PyConfig_Clear(&config); Py_ExitStatusException(status); return 1; }
    status = Py_PreInitialize(&preconfig);
    CHECK_STATUS;
    PyConfig_InitIsolatedConfig(&config);

    get_paths();
    static wchar_t* items[3];
    static wchar_t path[arraysz(items)*PATH_MAX];
    for (size_t i = 0; i < arraysz(items); i++) items[i] = path + i * PATH_MAX;
    swprintf(items[0], PATH_MAX, L"%ls/%ls", lib_dir, PYTHON_VER);
    swprintf(items[1], PATH_MAX, L"%ls/%ls/lib-dynload", lib_dir, PYTHON_VER);
    swprintf(items[2], PATH_MAX, L"%ls/%ls/site-packages", lib_dir, PYTHON_VER);
    status = PyConfig_SetWideStringList(&config, &config.module_search_paths, arraysz(items), items);
    CHECK_STATUS;
    config.module_search_paths_set = 1;
    config.optimization_level = 2;
    config.write_bytecode = 0;
    config.use_environment = 0;
    config.user_site_directory = 0;
    config.configure_c_stdio = 1;
    config.isolated = 1;

    status = PyConfig_SetString(&config, &config.program_name, exe_path);
    CHECK_STATUS;
    status = PyConfig_SetString(&config, &config.home, base_dir);
    CHECK_STATUS;
    status = PyConfig_SetString(&config, &config.run_module, L"site");
    CHECK_STATUS;
    status = PyConfig_SetBytesArgv(&config, argc, argv);
    CHECK_STATUS;
    status = Py_InitializeFromConfig(&config);
    CHECK_STATUS;
#undef CHECK_STATUS

    PySys_SetObject("gui_app", GUI_APP ? Py_True : Py_False);
    PySys_SetObject("frozen", Py_True);
    set_sys_string("calibre_basename", basename);
    set_sys_string("calibre_module",   module);
    set_sys_string("calibre_function", function);
    set_sys_string("extensions_location", extensions_dir);
    set_sys_string("resources_location", resources_dir);
    set_sys_string("executables_location", base_dir);
    set_sys_string("frozen_path", base_dir);

    int ret = Py_RunMain();
    PyConfig_Clear(&config);
    return ret;
}

int
execute_python_entrypoint(int argc, char * const *argv, const wchar_t *basename, const wchar_t *module, const wchar_t *function) {
    return initialize_interpreter(argc, argv, basename, module, function);
}
