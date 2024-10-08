/*
 * Copyright 2009 Kovid Goyal
 */

#define UNICODE
#define PY_SSIZE_T_CLEAN

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
#include "../run-python.h"

static char python_dll[] = PYDLL;



static wchar_t qt_prefix_dir[MAX_PATH] = {0};

static void
get_app_dirw(void) {
    wchar_t buf[MAX_PATH] = {0};
    wchar_t drive[4] = L"\0\0\0";
    DWORD sz; errno_t err;

    sz = GetModuleFileNameW(NULL, interpreter_data.exe_path, MAX_PATH);
    if (sz >= MAX_PATH-1) ExitProcess(_show_error(L"Installation directory path too long", L"", 1));
    err = _wsplitpath_s(interpreter_data.exe_path, drive, 4, buf, MAX_PATH, NULL, 0, NULL, 0);
    if (err != 0) ExitProcess(show_last_error_crt(L"Failed to find application directory"));
    _snwprintf_s(interpreter_data.app_dir, MAX_PATH, _TRUNCATE, L"%ls%ls", drive, buf);
    _snwprintf_s(interpreter_data.resources_path, MAX_PATH, _TRUNCATE, L"%ls%lsapp\\resources", drive, buf);
    _snwprintf_s(interpreter_data.extensions_path, MAX_PATH, _TRUNCATE, L"%ls%lsapp\\bin", drive, buf);
    _snwprintf_s(interpreter_data.executables_path, MAX_PATH, _TRUNCATE, L"%ls%lsapp\\bin", drive, buf);
}

static void
get_install_locations(void) {
    get_app_dirw();
    _snwprintf_s(qt_prefix_dir, MAX_PATH-1, _TRUNCATE, L"%ls\\ossl-modules", interpreter_data.executables_path);
    _wputenv_s(L"OPENSSL_MODULES", qt_prefix_dir);
    // Have to disable sandbox or Qt WebEngine Render Process crashes as of Qt 6.6
    _wputenv_s(L"QTWEBENGINE_DISABLE_SANDBOX", "1");
    _snwprintf_s(qt_prefix_dir, MAX_PATH-1, _TRUNCATE, L"%ls\\app", interpreter_data.app_dir);
    _wputenv_s(L"CALIBRE_QT_PREFIX", qt_prefix_dir);
    // Lots of people have trouble with various websites failing to download
    // because of missing intermediate certificates in the windows store
    // so use the Mozilla certificate bundle
    _snwprintf_s(qt_prefix_dir, MAX_PATH-1, _TRUNCATE, L"%ls\\mozilla-ca-certs.pem", interpreter_data.resources_path);
    const char *s = getenv("CALIBRE_USE_SYSTEM_CERTIFICATES");
    if (!s || strcmp(s, "1") != 0) _wputenv_s(L"SSL_CERT_FILE", qt_prefix_dir);
}

static void
load_python_dll() {
    get_install_locations();
	bypy_setup_python(python_dll);
}

const static wchar_t out_of_memory[] = L"Out of memory";


static void
redirect_out_stream(FILE *stream) {
    FILE *f = NULL;
    errno_t err;

    err = _wfreopen_s(&f, L"NUL", L"wt", stream);
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
execute_python_entrypoint(const wchar_t *basename, const wchar_t *module, const wchar_t *function, int is_gui_app) {
    int ret = 0;
    // Prevent Windows' idiotic error dialog popups when various win32 api functions fail
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOALIGNMENTFAULTEXCEPT | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    // Disable the invalid parameter handler
    _set_invalid_parameter_handler(null_invalid_parameter_handler);
    detect_tty();

    if (is_gui_app) {
        // Redirect stdout and stderr to NUL so that python does not fail writing to them
        if (!stdout_is_a_tty) redirect_out_stream(stdout);
        if (!stderr_is_a_tty) redirect_out_stream(stderr);
    }
    GUI_APP = is_gui_app;
    interpreter_data.argv = CommandLineToArgvW(GetCommandLineW(), &interpreter_data.argc);
    if (interpreter_data.argv == NULL) ExitProcess(show_last_error(L"Failed to get command line"));
    interpreter_data.basename = basename; interpreter_data.module = module; interpreter_data.function = function;
    load_python_dll();
    pre_initialize_interpreter(is_gui_app);
	run_interpreter();


    /* printf("111111111111 returning: %d\r\n", ret); */

    return ret;
}
