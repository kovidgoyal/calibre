/*
 * Copyright 2009 Kovid Goyal
 */

#define UNICODE
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

typedef int (__cdecl *ENTRYPROC)(const char*, const char*, const char*, int); 

static ENTRYPROC load_launcher_dll() {
    wchar_t buf[MAX_PATH];  // Cannot use a zero initializer for the array as it generates an implicit call to memset()
    wchar_t *dll_point = NULL;
    int i = 0;
    DWORD sz = 0; 
    HMODULE dll = 0;
    ENTRYPROC entrypoint = NULL;

    if ((sz = GetModuleFileNameW(NULL, buf, MAX_PATH)) >= MAX_PATH - 30) {
        show_error(L"Installation directory path too long", L"", 1);
        return NULL;
    }

    while (sz > 0) {
        if (buf[sz] == L'\\' || buf[sz] == L'/') { dll_point = buf + sz + 1; break; }
        sz--;
    }
    if (dll_point == NULL) {
        show_error(L"Executable path has no path separators", L"", 1);
        return NULL;
    }
    wsprintf(dll_point, L"%s\0\0", L"app\\DLLs");
    if (SetDllDirectoryW(buf) == 0) {
        show_last_error(L"Failed to set DLL directory");
        return NULL;
    }
    if (!LoadLibraryW(L"ucrtbase.dll")) {
        show_last_error(L"Unable to find ucrtbase.dll. You should install all Windows updates on your computer to get this file.");
        return NULL;
    }
    if (!(dll = LoadLibraryW(L"calibre-launcher.dll"))) {
        show_last_error(L"Failed to load: calibre-launcher.dll");
        return NULL;
    }
    if (!(entrypoint = (ENTRYPROC) GetProcAddress(dll, "execute_python_entrypoint"))) {
        show_last_error(L"Failed to get the calibre-launcher dll entry point");
        return NULL;
    }
    return entrypoint;
}

int __stdcall start_here() {
    int ret = 0;
    ENTRYPROC entrypoint = load_launcher_dll();
    if (entrypoint) {
#ifdef GUI_APP
        // This should really be returning the value set in the WM_QUIT message, but I cannot be bothered figuring out how to get that.
        entrypoint(BASENAME, MODULE, FUNCTION, 1);
#else
        ret = entrypoint(BASENAME, MODULE, FUNCTION, 0);
#endif
    } else ret = 1;
    ExitProcess(ret);
    return ret;
}
