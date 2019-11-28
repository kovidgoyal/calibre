/*
 * Copyright 2009 Kovid Goyal
 */

#ifndef UNICODE
#define UNICODE
#endif
#define WINDOWS_LEAN_AND_MEAN
#include<windows.h>
#include<strsafe.h>

static size_t mystrlen(const wchar_t *buf) {
    size_t ans = 0;
    if (FAILED(StringCbLengthW(buf, 500, &ans))) return 0;
    return ans;
}

static int show_error(const wchar_t *preamble, const wchar_t *msg, const int code) {
    wchar_t *buf;
    buf = (wchar_t*)LocalAlloc(LMEM_ZEROINIT, sizeof(wchar_t)*
            (mystrlen(msg) + mystrlen(preamble) + 80));
    if (!buf) {
        MessageBox(NULL, preamble, NULL, MB_OK|MB_ICONERROR);
        return code;
    }

    MessageBeep(MB_ICONERROR);
    wsprintf(buf, L"%s\r\n  %s (Error Code: %d)\r\n", preamble, msg, code);
    MessageBox(NULL, buf, NULL, MB_OK|MB_ICONERROR);
    LocalFree(buf);
    return code;
}

static int show_last_error(wchar_t *preamble) {
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

    ret = show_error(preamble, msg, (int)dw);
    if (msg != NULL) LocalFree(msg);
    return ret;
}

typedef int (__cdecl *ENTRYPROC)(const wchar_t*, const wchar_t*, const wchar_t*, int);
typedef void (__cdecl *SIMPLEPRINT)(const wchar_t*);
typedef BOOL (*SETDEFAULTDIRS)(DWORD);
static ENTRYPROC entrypoint = NULL;
static SIMPLEPRINT simple_print = NULL;
static HMODULE dll = 0;

static void
load_launcher_dll() {
    static wchar_t buf[MAX_PATH];  // Cannot use a zero initializer for the array as it generates an implicit call to memset()
    wchar_t *dll_point = NULL;
    int i = 0;
    DWORD sz = 0;

    if ((sz = GetModuleFileNameW(NULL, buf, MAX_PATH)) >= MAX_PATH - 30) {
        show_error(L"Installation directory path too long", L"", 1);
        return;
    }

    while (sz > 0) {
        if (buf[sz] == L'\\' || buf[sz] == L'/') { dll_point = buf + sz + 1; break; }
        sz--;
    }
    if (dll_point == NULL) {
        show_error(L"Executable path has no path separators", L"", 1);
        return;
    }
    wsprintf(dll_point, L"%s\0\0", L"app\\bin");
#if _WIN64
    // Restrict the directories from which DLLs can be loaded
    // For some reason I cannot determine, using this in 32bit builds causes
    // a crash even if no dlls are loaded.
    SETDEFAULTDIRS SetDefaultDllDirectories = (SETDEFAULTDIRS)GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "SetDefaultDllDirectories");
    if (SetDefaultDllDirectories) SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
#endif
    if (SetDllDirectoryW(buf) == 0) {
        show_last_error(L"Failed to set DLL directory");
        return;
    }
    // Have to load ucrtbase manually first, otherwise loading fails on systems where the
    // Universal CRT is not installed.
    if (!LoadLibraryW(L"ucrtbase.dll")) {
        show_last_error(L"Unable to find ucrtbase.dll. You should install all Windows updates on your computer to get this file.");
        return;
    }
    if (!(dll = LoadLibraryW(L"calibre-launcher.dll"))) {
        show_last_error(L"Failed to load: calibre-launcher.dll");
        return;
    }
    if (!(entrypoint = (ENTRYPROC) GetProcAddress(dll, "execute_python_entrypoint"))) {
        show_last_error(L"Failed to get the calibre-launcher dll entry point");
        return;
    }
    simple_print = (SIMPLEPRINT) GetProcAddress(dll, "simple_print");
}

int __stdcall start_here() {
    int ret = 0;
    load_launcher_dll();
    if (entrypoint) {
#ifdef GUI_APP
        // This should really be returning the value set in the WM_QUIT message, but I cannot be bothered figuring out how to get that.
        entrypoint(BASENAME, MODULE, FUNCTION, 1);
#else
        ret = entrypoint(BASENAME, MODULE, FUNCTION, 0);
#endif
    } else ret = 1;
    if (dll != 0) {
        FreeLibrary(dll);
        dll = 0;
    }
    ExitProcess(ret);
    return ret;
}
