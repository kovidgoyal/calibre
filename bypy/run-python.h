/*
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <stdio.h>
#include <stdbool.h>
#include <time.h>
#include <stdlib.h>
#include <stdarg.h>
#ifdef _WIN32
#include <string.h>
#define PATH_MAX MAX_PATH
#else
#include <strings.h>
#endif
#include <errno.h>
#include <Python.h>
#ifdef __APPLE__
#include <os/log.h>
#endif

#define arraysz(x) (sizeof(x)/sizeof(x[0]))

static bool use_os_log = false;

#ifdef _WIN32
static void
log_error(const char *fmt, ...) {
    va_list ar;
    va_start(ar, fmt);
    vfprintf(stderr, fmt, ar);
    va_end(ar);
	fprintf(stderr, "\n");
}

static bool stdout_is_a_tty = false, stderr_is_a_tty = false;
DWORD console_old_mode = 0;
static bool console_mode_changed = false;

static void
detect_tty() {
    stdout_is_a_tty = _isatty(_fileno(stdout));
    stderr_is_a_tty = _isatty(_fileno(stderr));
}

static void
setup_vt_terminal_mode() {
    if (stdout_is_a_tty || stderr_is_a_tty) {
        HANDLE h = GetStdHandle(stdout_is_a_tty ? STD_OUTPUT_HANDLE : STD_ERROR_HANDLE);
        if (h != INVALID_HANDLE_VALUE) {
            if (GetConsoleMode(h, &console_old_mode)) {
                console_mode_changed = true;
                SetConsoleMode(h, console_old_mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
            }
        }
    }
}

static void
restore_vt_terminal_mode() {
    if (console_mode_changed) SetConsoleMode(GetStdHandle(stdout_is_a_tty ? STD_OUTPUT_HANDLE : STD_ERROR_HANDLE), console_old_mode);
}
#else
static void
log_error(const char *fmt, ...) __attribute__ ((format (printf, 1, 2)));


static void
log_error(const char *fmt, ...) {
    va_list ar;
    struct timeval tv;
#ifdef __APPLE__
    // Apple does not provide a varargs style os_logv
    char logbuf[16 * 1024] = {0};
#else
    char logbuf[4];
#endif
    char *p = logbuf;
#define bufprint(func, ...) { if ((size_t)(p - logbuf) < sizeof(logbuf) - 2) { p += func(p, sizeof(logbuf) - (p - logbuf), __VA_ARGS__); } }
    if (!use_os_log) {  // Apple's os_log already records timestamps
        gettimeofday(&tv, NULL);
        struct tm *tmp = localtime(&tv.tv_sec);
        if (tmp) {
            char tbuf[256] = {0}, buf[256] = {0};
            if (strftime(buf, sizeof(buf), "%j %H:%M:%S.%%06u", tmp) != 0) {
                snprintf(tbuf, sizeof(tbuf), buf, tv.tv_usec);
                fprintf(stderr, "[%s] ", tbuf);
            }
        }
    }
    va_start(ar, fmt);
    if (use_os_log) { bufprint(vsnprintf, fmt, ar); }
    else vfprintf(stderr, fmt, ar);
    va_end(ar);
#ifdef __APPLE__
    if (use_os_log) os_log(OS_LOG_DEFAULT, "%{public}s", logbuf);
#endif
    if (!use_os_log) fprintf(stderr, "\n");
}
#endif


#define fatal(...) { log_error(__VA_ARGS__); exit(EXIT_FAILURE); }

static void
set_sys_string(const char* key, const wchar_t* val) {
    PyObject *temp = PyUnicode_FromWideChar(val, -1);
    if (temp) {
        if (PySys_SetObject(key, temp) != 0) fatal("Failed to set attribute on sys: %s", key);
        Py_DECREF(temp);
    } else {
        fatal("Failed to set attribute on sys, PyUnicode_FromWideChar failed");
    }
}

static void
set_sys_bool(const char* key, const bool val) {
	PyObject *pyval = PyBool_FromLong(val);
	if (PySys_SetObject(key, pyval) != 0) fatal("Failed to set attribute on sys: %s", key);
	Py_DECREF(pyval);
}

static void
pre_initialize_interpreter(bool is_gui_app) {
    PyStatus status;
	use_os_log = is_gui_app;
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    preconfig.coerce_c_locale = 1;
    preconfig.isolated = 1;

    status = Py_PreInitialize(&preconfig);
	if (PyStatus_Exception(status)) Py_ExitStatusException(status);
}

#define decode_char_buf(src, dest) { \
    size_t tsz; \
    wchar_t* t__ = Py_DecodeLocale(src, &tsz); \
    if (!t__) fatal("Failed to decode path: %s", src); \
	if (tsz > sizeof(dest) - 1) tsz = sizeof(dest) - 1; \
    memcpy(dest, t__, tsz * sizeof(wchar_t)); \
	dest[tsz] = 0; \
    PyMem_RawFree(t__); \
}

#define MAX_SYS_PATHS 3

typedef struct {
	wchar_t* sys_paths[MAX_SYS_PATHS];
	wchar_t sys_path_buf[MAX_SYS_PATHS * PATH_MAX];
	size_t sys_paths_count;
	wchar_t exe_path[PATH_MAX], python_home_path[PATH_MAX], python_lib_path[PATH_MAX];
	wchar_t extensions_path[PATH_MAX], resources_path[PATH_MAX], executables_path[PATH_MAX];
#ifdef __APPLE__
	wchar_t bundle_resource_path[PATH_MAX], frameworks_path[PATH_MAX];
#elif defined(_WIN32)
	wchar_t app_dir[PATH_MAX];
#endif
	const wchar_t *basename, *module, *function;
	int argc;
#ifdef _WIN32
	wchar_t* const *argv;
#else
	char* const *argv;
#endif
} InterpreterData;

static InterpreterData interpreter_data = {{0}};

static wchar_t*
add_sys_path() {
	if (interpreter_data.sys_paths_count >= MAX_SYS_PATHS) fatal("Trying to add too many entries to sys.path");
	wchar_t *ans = interpreter_data.sys_path_buf + PATH_MAX * interpreter_data.sys_paths_count;
	interpreter_data.sys_paths[interpreter_data.sys_paths_count] = ans;
	interpreter_data.sys_paths_count++;
	return ans;
}

static void
add_sys_paths() {
#ifdef _WIN32
    swprintf(add_sys_path(), PATH_MAX, L"%ls\\app\\pylib.zip", interpreter_data.app_dir);
    swprintf(add_sys_path(), PATH_MAX, L"%ls\\app\\bin", interpreter_data.app_dir);
#else
    swprintf(add_sys_path(), PATH_MAX, L"%ls", interpreter_data.python_lib_path);
    swprintf(add_sys_path(), PATH_MAX, L"%ls/lib-dynload", interpreter_data.python_lib_path);
#ifdef __APPLE__
    swprintf(add_sys_path(), PATH_MAX, L"%ls/Python/site-packages", interpreter_data.bundle_resource_path);
#else
    swprintf(add_sys_path(), PATH_MAX, L"%ls/site-packages", interpreter_data.python_lib_path);
#endif
#endif
}

static void
run_interpreter() {
#define CHECK_STATUS if (PyStatus_Exception(status)) { PyConfig_Clear(&config); Py_ExitStatusException(status); }
    PyStatus status;
    PyConfig config;

    PyConfig_InitIsolatedConfig(&config);
	add_sys_paths();
    status = PyConfig_SetWideStringList(&config, &config.module_search_paths, interpreter_data.sys_paths_count, interpreter_data.sys_paths);
    CHECK_STATUS;

    config.module_search_paths_set = 1;
    config.optimization_level = 2;
    config.write_bytecode = 0;
    config.use_environment = 0;
    config.user_site_directory = 0;
    config.configure_c_stdio = 1;
    config.isolated = 1;

    status = PyConfig_SetString(&config, &config.program_name, interpreter_data.exe_path);
    CHECK_STATUS;
#ifndef _WIN32
    status = PyConfig_SetString(&config, &config.home, interpreter_data.python_home_path);
    CHECK_STATUS;
#endif
    status = PyConfig_SetString(&config, &config.run_module, L"site");
    CHECK_STATUS;
#ifdef _WIN32
    status = PyConfig_SetArgv(&config, interpreter_data.argc, interpreter_data.argv);
#else
    status = PyConfig_SetBytesArgv(&config, interpreter_data.argc, interpreter_data.argv);
#endif
    CHECK_STATUS;
    status = Py_InitializeFromConfig(&config);
    CHECK_STATUS;

	set_sys_bool("gui_app", use_os_log);
    set_sys_bool("frozen", true);
    set_sys_string("calibre_basename", interpreter_data.basename);
    set_sys_string("calibre_module",   interpreter_data.module);
    set_sys_string("calibre_function", interpreter_data.function);
    set_sys_string("extensions_location", interpreter_data.extensions_path);
    set_sys_string("resources_location", interpreter_data.resources_path);
    set_sys_string("executables_location", interpreter_data.executables_path);
#ifdef __APPLE__
    set_sys_string("resourcepath", interpreter_data.bundle_resource_path);
    set_sys_string("frameworks_dir", interpreter_data.frameworks_path);
    set_sys_bool("new_app_bundle", true);
#elif defined(_WIN32)
    set_sys_string("app_dir", interpreter_data.app_dir);
    set_sys_bool("new_app_layout", true);
#else
    set_sys_string("frozen_path", interpreter_data.executables_path);
#endif

#ifdef _WIN32
    UINT code_page = GetConsoleOutputCP();
    if (code_page != CP_UTF8) SetConsoleOutputCP(CP_UTF8);
    setup_vt_terminal_mode();
#endif

    int ret = Py_RunMain();
    PyConfig_Clear(&config);
#ifdef _WIN32
    if (code_page != CP_UTF8) SetConsoleOutputCP(CP_UTF8);
    restore_vt_terminal_mode();
#endif
	exit(ret);
#undef CHECK_STATUS
}
