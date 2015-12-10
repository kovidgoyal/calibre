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
    wchar_t drive[4] = L"\0\0\0";
    int i = 0;
    DWORD sz = 0; 
    HMODULE dll = 0;
    ENTRYPROC entrypoint = 0;

    if ((sz = GetModuleFileNameW(NULL, buf, MAX_PATH)) >= MAX_PATH - 30)
        ExitProcess(show_error(L"Installation directory path too long", L"", 1));

    while (sz > 0) {
        if (buf[sz] == L'\\' || buf[sz] == L'/') break;
        sz--;
    }
    if (sz <= 0)
        ExitProcess(show_error(L"Executable path has no path separators", L"", 1));
    buf[sz+1] = L'a'; buf[sz+2] = L'p'; buf[sz+3] = L'p'; buf[sz+4] = L'\\';
    buf[sz+5] = L'D'; buf[sz+6] = L'L'; buf[sz+7] = L'L'; buf[sz+8] = L's';
    buf[sz+9] = 0; buf[sz+10] = 0;
    if (SetDllDirectoryW(buf) == 0) {
        show_last_error(L"Failed to set DLL directory");
        ExitProcess(1);
    }
    dll = LoadLibraryW(L"calibre-launcher.dll");
    if (!dll) ExitProcess(show_last_error(L"Failed to get the calibre-launcher dll handle"));
    entrypoint = (ENTRYPROC) GetProcAddress(dll, "execute_python_entrypoint");
    if (!entrypoint) ExitProcess(show_last_error(L"Failed to get the calibre-launcher dll entry point"));
    return entrypoint;
}

int __stdcall start_here() {
    int ret = 0;
#ifdef GUI_APP
    // This should really be returning the value set in the WM_QUIT message, but I cannot be bothered figuring out how to get that.
    load_launcher_dll()(BASENAME, MODULE, FUNCTION, 1);
#else
    ret = load_launcher_dll()(BASENAME, MODULE, FUNCTION, 0);
#endif
    ExitProcess(ret);
    return ret;
}
