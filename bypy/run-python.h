/*
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define PY_SSIZE_T_CLEAN
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
#include <bypy-freeze.h>


static void
pre_initialize_interpreter(bool is_gui_app) {
    bypy_pre_initialize_interpreter(is_gui_app);
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
	int argc;
	wchar_t exe_path[PATH_MAX], python_home_path[PATH_MAX], python_lib_path[PATH_MAX];
	wchar_t extensions_path[PATH_MAX], resources_path[PATH_MAX], executables_path[PATH_MAX];
#ifdef __APPLE__
	wchar_t bundle_resource_path[PATH_MAX], frameworks_path[PATH_MAX];
#elif defined(_WIN32)
	wchar_t app_dir[PATH_MAX];
#endif
	const wchar_t *basename, *module, *function;
#ifdef _WIN32
	wchar_t* const *argv;
#else
	char* const *argv;
#endif
} InterpreterData;

static InterpreterData interpreter_data = {0};

static void
run_interpreter() {
    bypy_initialize_interpreter(
            interpreter_data.exe_path, interpreter_data.python_home_path, L"site", interpreter_data.extensions_path,
            interpreter_data.argc, interpreter_data.argv);
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

    int ret = bypy_run_interpreter();
	exit(ret);
}
